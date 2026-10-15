"""Collect the normal browser page and its profile responses; no private API signing."""
import asyncio
import json
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright
from .platforms.registry import PLATFORMS
from .platforms.kuaishou import DOM_SCRIPT, first, walk, is_profile_response, parse_profile_payload


class CollectionError(RuntimeError):
    pass


class RiskControlError(CollectionError):
    pass


class UserNotFoundError(CollectionError):
    pass


def check_risk_control(dom, body_text):
    if re.match(r'^\s*\{\s*"result"\s*:\s*2', body_text):
        raise RiskControlError('快手返回 result:2 风控页面；已停止采集，请稍后恢复正常访问后再运行。')
    # 以当前页面的作品为准，不能用已收到的网络数据掩盖作品区域加载失败。
    if dom.get('feed_error') and not dom['videos']:
        raise RiskControlError('快手风控：作品区域仅显示“服务器异常，稍后重试”，未加载作品；已停止采集，请稍后再运行。')


def profile_info(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    if parsed.scheme == 'https' and parsed.port in (None, 443):
        for platform, adapter in PLATFORMS.items():
            hosts, path = adapter['hosts'], adapter['profile_path']
            match = re.fullmatch(rf'/{path}/([A-Za-z0-9_-]+)/?', parsed.path)
            if parsed.hostname in hosts and match:
                return platform, match[1]
    raise ValueError('请输入快手 https://www.kuaishou.com/profile/<id> 或抖音 https://www.douyin.com/user/<id> 主页链接。')


def profile_id(url: str) -> str:
    return profile_info(url)[1]


def import_cookies(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    cookies = data.get('cookies', []) if isinstance(data, dict) else data
    if not isinstance(cookies, list):
        raise ValueError('Cookie 文件需为 Playwright storage_state 或 Cookie 数组。')
    clean = []
    for cookie in cookies:
        domain = cookie.get('domain', '')
        if not any(domain.lstrip('.') == host or domain.endswith('.' + host) for host in ('kuaishou.com', 'douyin.com')):
            continue
        item = {k: cookie[k] for k in ('name', 'value', 'domain', 'path', 'expires', 'httpOnly', 'secure', 'sameSite') if k in cookie}
        item.setdefault('path', '/')
        if item.get('sameSite') not in ('Strict', 'Lax', 'None'):
            item.pop('sameSite', None)
        clean.append(item)
    if not clean:
        raise ValueError('Cookie 文件中没有快手或抖音 Cookie。')
    return clean


@asynccontextmanager
async def browser_session(browser_dir, *, headless=False, browser_channel=None, cookies=None):
    browser_dir.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(str(browser_dir.resolve()),
            channel=browser_channel, headless=headless, viewport={'width': 1440, 'height': 1000}, locale='zh-CN')
        try:
            if cookies:
                await context.add_cookies(import_cookies(cookies))
            page = context.pages[0] if context.pages else await context.new_page()
            yield page
        finally:
            await context.close()


async def collect(url: str, output: Path, browser_dir: Path, *, max_videos: int = 12,
                  headless: bool = False, login: bool = False, timeout: int = 45,
                  login_timeout: int = 300, cookies: Path | None = None,
                  browser_channel: str | None = None, page=None, on_status=None,
                  require_video_types: bool = True) -> dict:
    platform, user_id = profile_info(url)
    if page is None:
        async with browser_session(browser_dir, headless=headless, browser_channel=browser_channel, cookies=cookies) as active_page:
            return await collect(url, output, browser_dir, login=login, timeout=timeout,
                                 login_timeout=login_timeout, headless=headless, page=active_page, on_status=on_status,
                                 require_video_types=require_video_types)
    from .platforms import douyin
    output.mkdir(parents=True, exist_ok=True)
    context = page.context
    channel = {'platform': platform, 'id': user_id, 'url': url, 'name': '', 'bio': '',
               'videos': [], 'excluded_posts': [], 'warnings': [], 'collected_at': datetime.now(timezone.utc).isoformat(),
               'scope': 'All items from the first creator-feed response; no scrolling or pagination.'}
    dom_script = DOM_SCRIPT if platform == 'kuaishou' else douyin.DOM_SCRIPT
    pending = set()
    first_feed_received = False
    first_page_posts = []
    async def capture(response):
        nonlocal first_feed_received, first_page_posts
        try:
            if platform == 'douyin':
                if not douyin.is_douyin_response(response.url, user_id):
                    return
                payload = await response.json()
                profile, videos = douyin.parse_douyin_payload(payload, user_id, include_images=True)
                is_feed = urlparse(response.url).path.endswith('/aweme/post/')
            else:
                body = {key: values[0] for key, values in parse_qs(urlparse(response.url).query).items()}
                if response.request.post_data:
                    body.update(response.request.post_data_json or {})
                if not is_profile_response(response.url, body, user_id):
                    return
                variables = body.get('variables', body)
                if first(variables, 'pcursor', 'cursor') not in ('', '0', 0):
                    return
                profile, videos = parse_profile_payload(await response.json())
                is_feed = bool(videos)
            if profile:
                channel['name'] = profile['name']
                if profile['bio']:
                    channel['bio'] = profile['bio']
            if is_feed and not first_feed_received:
                # 第一条作者作品响应就是本轮第一页；后续分页响应不会混入。
                channel['videos'] = []
                channel['excluded_posts'] = []
                first_page_posts = [dict(v) for v in videos]
                merge(videos)
                first_feed_received = True
        except Exception:
            # Non-JSON responses and aborted requests are normal during navigation.
            return
    def merge(videos):
        known = {v['id'] for v in channel['videos']}
        excluded = {v['id'] for v in channel['excluded_posts']}
        for video in videos:
            if platform == 'douyin' and douyin.is_non_video_post(video):
                if video['id'] not in excluded:
                    reason = '文字文章，不作为视频候选' if douyin.is_article_post(video) else '图文/图集，不作为视频候选'
                    channel['excluded_posts'].append({**video, 'exclusion_reason': reason})
                    excluded.add(video['id'])
                continue
            if video['id'] not in known:
                channel['videos'].append(video)
                known.add(video['id'])
    def on_response(response):
        task = asyncio.create_task(capture(response))
        pending.add(task)
        task.add_done_callback(pending.discard)
    page.on('response', on_response)
    def check_page(dom, body_text):
        if platform == 'kuaishou':
            check_risk_control(dom, body_text)
        elif dom.get('captcha') or any(message in body_text for message in ('访问过于频繁', '操作过于频繁', '请完成下列验证后继续')):
            raise RiskControlError('抖音出现风控/验证码页面；已停止采集，请在正常浏览器中完成验证后再运行。')
        elif dom.get('user_not_found'):
            raise UserNotFoundError('抖音主页明确显示“用户不存在”，无法获取频道资料；不是登录失败或未投稿。')
    async def read_dom():
        dom = await page.evaluate(dom_script)
        if platform == 'douyin' and dom.get('bio_collapsed'):
            more = page.locator('[data-e2e="user-info"] > .t_m2gjO6, [data-e2e="user-info"] > p + div').get_by_text('更多', exact=True)
            if await more.count() and await more.first.is_visible():
                await more.first.click()
                await page.wait_for_timeout(300)
                dom = await page.evaluate(dom_script)
        return dom
    try:
        if cookies:
            await context.add_cookies(import_cookies(cookies))
        if login:
            site = 'https://www.kuaishou.com' if platform == 'kuaishou' else 'https://www.douyin.com'
            login_cookies = ('passToken',) if platform == 'kuaishou' else ('sessionid', 'sessionid_ss')
            if on_status:
                on_status('等待扫码（请在浏览器登录）')
            else:
                print('请在当前浏览器窗口完成扫码登录；会话仅保存在项目 .browser 目录。', flush=True)
            await page.goto(site, wait_until='domcontentloaded', timeout=timeout * 1000)
            await page.wait_for_timeout(2000)
            login_deadline = asyncio.get_running_loop().time() + login_timeout
            if not any(c['name'] in login_cookies and c['value'] for c in await context.cookies(site)):
                button = page.get_by_text('登录', exact=True)
                if await button.count():
                    await button.first.click()
            while not any(c['name'] in login_cookies and c['value'] for c in await context.cookies(site)):
                body_text = await page.locator('body').inner_text()
                if re.match(r'^\s*\{\s*"result"\s*:\s*2', body_text):
                    raise RiskControlError('登录首页返回 result:2 风控，无法显示扫码页面；已停止采集，请稍后再运行。')
                if asyncio.get_running_loop().time() >= login_deadline:
                    raise CollectionError('等待登录超时；请重新运行 login 并完成扫码。')
                await page.wait_for_timeout(1500)
            if on_status:
                on_status('采集频道')
            else:
                print('检测到登录会话，开始获取频道。', flush=True)
        await page.goto(url, wait_until='domcontentloaded', timeout=timeout * 1000)
        deadline = asyncio.get_running_loop().time() + timeout
        last_count, stable_since = -1, asyncio.get_running_loop().time()
        while asyncio.get_running_loop().time() < deadline:
            dom = await read_dom()
            if not channel['name'] and dom['name']:
                channel['name'], channel['bio'] = dom['name'], dom['bio']
            if dom['bio'] and (not channel['bio'] or (platform == 'douyin' and not dom.get('bio_collapsed') and len(dom['bio']) > len(channel['bio']))):
                channel['bio'] = dom['bio']
            check_page(dom, await page.locator('body').inner_text())
            if platform == 'douyin' and dom.get('login_required') and not any(c['name'] in ('sessionid', 'sessionid_ss') and c['value'] for c in await context.cookies('https://www.douyin.com')):
                if headless:
                    raise CollectionError('抖音要求登录，请用有窗口模式运行 login 完成扫码。')
                if on_status:
                    on_status('等待抖音扫码（请在浏览器登录）')
                else:
                    print('抖音要求登录；请在当前窗口扫码，登录前不会关闭窗口或调用模型。', flush=True)
                login_deadline = asyncio.get_running_loop().time() + login_timeout
                while not any(c['name'] in ('sessionid', 'sessionid_ss') and c['value'] for c in await context.cookies('https://www.douyin.com')):
                    current = await page.evaluate(dom_script)
                    check_page(current, await page.locator('body').inner_text())
                    if asyncio.get_running_loop().time() >= login_deadline:
                        raise CollectionError('等待抖音扫码登录超时；请重新运行 login。')
                    await page.wait_for_timeout(1000)
                deadline = asyncio.get_running_loop().time() + timeout
                if on_status:
                    on_status('采集频道')
                last_count, stable_since = -1, asyncio.get_running_loop().time()
                continue
            if not first_feed_received:
                merge(dom['videos'])
            if len(channel['videos']) != last_count:
                last_count, stable_since = len(channel['videos']), asyncio.get_running_loop().time()
            if channel['name'] and (channel['videos'] or channel['excluded_posts'] or dom.get('no_posts') or dom.get('is_private')) and asyncio.get_running_loop().time() - stable_since >= 2:
                break
            await page.wait_for_timeout(500)
        if pending:
            await asyncio.gather(*list(pending))
        dom = await read_dom()
        check_page(dom, await page.locator('body').inner_text())
        if platform == 'douyin':
            channel = douyin.reconcile_dom_types(channel, dom)
            if not first_feed_received:
                first_page_posts = [dict(v) for v in dom['videos']]
            unknown = [v['id'] for v in channel['videos'] if v.get('content_type') != 'video']
            # 保存接口/DOM中的作品级证据，后续可离线调整过滤，不必再访问网页。
            evidence = {'platform': platform, 'channel_url': url, 'collected_at': channel['collected_at'],
                        'post_type_version': douyin.POST_TYPE_VERSION,
                        'source': 'profile_response' if first_feed_received else 'initial_dom',
                        'posts': first_page_posts}
            (output / 'first-page-posts.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
            type_status = {'post_type_version': douyin.POST_TYPE_VERSION, 'video_count': len(channel['videos']),
                           **douyin.excluded_post_counts(channel), 'unknown_ids': unknown,
                           'complete': not unknown}
            (output / 'post-type-status.json').write_text(json.dumps(type_status, ensure_ascii=False, indent=2), encoding='utf-8')
            if unknown and require_video_types:
                raise CollectionError(f'有{len(unknown)}个作品缺少可靠的视频类型证据，未更新正式缓存；请重试。作品ID：{", ".join(unknown[:5])}')
            channel['post_type_version'] = douyin.POST_TYPE_VERSION if not unknown else 'unverified'
            if unknown:
                channel['warnings'].append(f'{len(unknown)}个作品的类型尚未确认；请用 --refresh-cache 重新采集核实。')
        no_posts = platform == 'douyin' and dom.get('no_posts') and not channel['videos']
        is_private = platform == 'douyin' and dom.get('is_private') and not channel['videos']
        if not channel['name'] or (not channel['videos'] and not channel['excluded_posts'] and not no_posts and not is_private):
            raise CollectionError('未获得频道名称和作品。请先运行 login 完成扫码，或导入有效 Cookie；也可能是风控、空频道或页面结构变化。')
        channel['no_posts'] = bool(no_posts)
        channel['is_private'] = bool(is_private)
        channel['no_video_posts'] = bool(channel['excluded_posts']) and not channel['videos']
        channel['collection_state'] = 'private' if is_private else 'no_posts' if no_posts else 'ready'
        if no_posts:
            channel['empty_reason'] = '主页明确显示：该账号还未发布过作品。'
        channel['first_page_source'] = 'profile_response' if first_feed_received else 'initial_dom'
        if not first_feed_received:
            channel['scope'] = 'All loaded creator posts in the initial DOM; no scrolling or pagination.'
            channel['warnings'].append('未捕获第一页作品响应，使用首次加载的页面作品；没有翻页或滚动。')
        # Feed responses can arrive before the profile text has rendered.
        # Finish response callbacks, then read the page again before saving.
        page.remove_listener('response', on_response)
        if pending:
            await asyncio.gather(*list(pending))
        dom = await read_dom()
        check_page(dom, await page.locator('body').inner_text())
        if dom['bio'] and (not channel['bio'] or (platform == 'douyin' and not dom.get('bio_collapsed') and len(dom['bio']) > len(channel['bio']))):
            channel['bio'] = dom['bio']
        if not channel['bio']:
            channel['warnings'].append('未获取个人简介（可能为空或解析失败），保留空值。')
        await page.screenshot(path=str(output / 'channel-page.png'), full_page=True)
        save_channel(channel, output)
        (output / 'page-text.txt').write_text(await page.locator('body').inner_text(), encoding='utf-8')
        (output / 'collection-status.json').write_text(json.dumps({'status': 'success', 'channel_url': url,
            'collected_at': channel['collected_at'], 'video_count': len(channel['videos']),
            **douyin.excluded_post_counts(channel), 'no_video_posts': channel['no_video_posts'],
            'no_posts': bool(no_posts), 'is_private': bool(is_private)}, ensure_ascii=False, indent=2), encoding='utf-8')
        from .cache import remember
        remember(output, channel['url'])
        return channel
    except Exception as exc:
        missing_user = isinstance(exc, UserNotFoundError)
        channel['collection_state'] = 'user_not_found' if missing_user else 'failed'
        if missing_user:
            channel.update(user_not_found=True, no_posts=False, is_private=False, name='', bio='', videos=[],
                           unavailable_reason=str(exc))
        save_channel(channel, output)
        try:
            (output / 'page-text.txt').write_text(await page.locator('body').inner_text(), encoding='utf-8')
        except Exception:
            pass
        try:
            await page.screenshot(path=str(output / 'collection-error.png'), full_page=True)
        except Exception:
            pass
        status = {'status': 'user_not_found' if missing_user else 'collection_failed', 'channel_url': url, 'error_type': type(exc).__name__, 'error': str(exc),
                  'has_name': bool(channel['name']), 'video_count': len(channel['videos'])}
        (output / 'collection-status.json').write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
        if missing_user:
            from .cache import remember
            remember(output, url)
        raise
    finally:
        page.remove_listener('response', on_response)
        if pending:
            await asyncio.gather(*list(pending), return_exceptions=True)



async def download_cover(context, url: str, destination: Path):
    """Reuse browser cookies only for the CDN request; cookies never enter model input."""
    host = urlparse(url).hostname or ''
    domains = ('kuaishou.com', 'kwimgs.com', 'yximgs.com', 'gifshow.com', 'douyin.com', 'douyinpic.com',
               'byteimg.com', 'bytecdn.cn', 'ibytedtos.com', 'pstatp.com', 'bytedance.com')
    if urlparse(url).scheme != 'https' or not any(host == d or host.endswith('.' + d) for d in domains):
        raise ValueError('封面地址不属于支持的平台 HTTPS CDN。')
    response = await context.request.get(url, timeout=30000)
    if not response.ok:
        raise ValueError(f'封面 HTTP {response.status}。')
    content = await response.body()
    if len(content) > 10 * 1024 * 1024:
        raise ValueError('封面过大。')
    from PIL import Image
    from pillow_heif import register_heif_opener
    import io
    # CDN即使地址以.jpeg结尾也可能返回HEIC；解码后统一保存为JPEG缓存。
    register_heif_opener()
    with Image.open(io.BytesIO(content)) as image:
        image = image.convert('RGB')
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(destination, 'JPEG', quality=90)


async def download_selected_covers(channel, videos, root, output, page):
    for video in videos:
        existing = root / video['cover_path'] if video.get('cover_path') else None
        if existing and existing.is_file():
            video['cover_path'] = str(existing.resolve())
            continue
        if not video.get('cover_url'):
            channel['warnings'].append(f"候选 {video['id']} 缺少封面地址，使用标题。")
            continue
        try:
            from .cache import channel_dir
            destination = channel_dir(channel['url']) / 'covers' / f"{video['id']}.jpg"
            await download_cover(page.context, video['cover_url'], destination)
            video['cover_path'] = str(destination.resolve())
        except Exception as exc:
            channel['warnings'].append(f"候选 {video['id']} 封面下载失败：{type(exc).__name__}: {exc}")


def save_channel(channel, output):
    output.mkdir(parents=True, exist_ok=True)
    temporary = output / 'channel.json.tmp'
    temporary.write_text(json.dumps(channel, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(output / 'channel.json')


def saved_channel(output, url):
    """只复用完整采集或明确未投稿的快照，失败的半成品不当作成功。"""
    try:
        channel = json.loads((output / 'channel.json').read_text(encoding='utf-8-sig'))
        if profile_info(channel['url']) != profile_info(url):
            return None
        if channel.get('user_not_found') and channel.get('collection_state') == 'user_not_found' and not channel.get('videos'):
            return channel
        if not channel.get('name'):
            return None
        if channel.get('collection_state') == 'failed':
            return None
        if not channel.get('videos') and not channel.get('no_posts') and not channel.get('is_private') and not channel.get('no_video_posts'):
            return None
        from .platforms.douyin import filter_image_posts
        return filter_image_posts(channel)
    except (OSError, ValueError, KeyError):
        return None


def recover_post_type_failure(output, url):
    """仅修复类型核实失败的完整作品快照，不把其它采集错误的半成品当成功。"""
    from .platforms.douyin import filter_image_posts, excluded_post_counts, POST_TYPE_VERSION
    try:
        status = json.loads((output / 'collection-status.json').read_text(encoding='utf-8'))
        if status.get('error_type') != 'CollectionError' or '个作品缺少可靠的视频类型证据' not in status.get('error', ''):
            return False
        channel = json.loads((output / 'channel.json').read_text(encoding='utf-8-sig'))
        evidence = json.loads((output / 'first-page-posts.json').read_text(encoding='utf-8'))
        if (channel.get('collection_state') != 'failed' or not channel.get('name')
                or channel.get('platform') != 'douyin' or evidence.get('source') not in ('initial_dom', 'profile_response')
                or profile_info(channel['url']) != profile_info(url)
                or profile_info(evidence['channel_url']) != profile_info(url)):
            return False
        channel = filter_image_posts(channel)
        if any(v.get('content_type') != 'video' for v in channel['videos']):
            return False
        if not channel['videos'] and not channel['excluded_posts']:
            return False
    except (OSError, ValueError, KeyError):
        return False
    source = evidence['source']
    channel.update(collection_state='ready', post_type_version=POST_TYPE_VERSION,
                   first_page_source=source, no_posts=False, is_private=False,
                   scope='All loaded creator posts in the initial DOM; no scrolling or pagination.' if source == 'initial_dom'
                         else 'All items from the first creator-feed response; no scrolling or pagination.')
    channel.setdefault('warnings', []).append('已用保存的作品类型证据修复过滤；没有重新访问主页。')
    save_channel(channel, output)
    type_status = {'post_type_version': POST_TYPE_VERSION, 'video_count': len(channel['videos']),
                   **excluded_post_counts(channel), 'unknown_ids': [], 'complete': True,
                   'recovered_from_saved_dom': source == 'initial_dom', 'recovered_from_saved_evidence': True}
    (output / 'post-type-status.json').write_text(json.dumps(type_status, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'collection-status.json').write_text(json.dumps({'status': 'success', 'channel_url': url,
        'video_count': len(channel['videos']), **excluded_post_counts(channel),
        'recovered_from_saved_evidence': True, 'previous_error': status['error']}, ensure_ascii=False, indent=2), encoding='utf-8')
    return True


def attach_saved_covers(channel, root):
    for video in channel['videos']:
        path = root / 'covers' / f"{video['id']}.jpg"
        if not path.is_file() and channel.get('url'):
            from .cache import channel_dir
            path = channel_dir(channel['url']) / 'covers' / f"{video['id']}.jpg"
        if path.is_file():
            video['cover_path'] = str(path.relative_to(root)) if path.is_relative_to(root) else str(path.resolve())


async def archive_covers(channel, root, page, on_status=None):
    """下载第一页所有缺失封面；已有图片不发请求，地址失效时保留明确缺失记录。"""
    attach_saved_covers(channel, root)
    missing = []
    for index, video in enumerate(channel['videos'], 1):
        existing = root / video['cover_path'] if video.get('cover_path') else None
        if existing and existing.is_file():
            continue
        if on_status:
            on_status(f"缓存封面 {index}/{len(channel['videos'])}")
        if not video.get('cover_url'):
            missing.append({'id': video['id'], 'reason': '未采集到封面地址'})
            continue
        try:
            from .cache import channel_dir
            destination = (channel_dir(channel['url']) if channel.get('url') else root) / 'covers' / f"{video['id']}.jpg"
            await download_cover(page.context, video['cover_url'], destination)
            video['cover_path'] = str(destination.relative_to(root)) if destination.is_relative_to(root) else str(destination.resolve())
            save_channel(channel, root)
        except Exception as exc:
            missing.append({'id': video['id'], 'reason': f'{type(exc).__name__}: {exc}'})
            # CDN 限流时不继续发送封面请求；不为刷新地址重新打开作者主页。
            if 'HTTP 429' in str(exc):
                missing.extend({'id': v['id'], 'reason': '封面CDN限流，暂停下载'} for v in channel['videos'][index:]
                               if not v.get('cover_path') or not (root / v['cover_path']).is_file())
                break
        await asyncio.sleep(0.1)
    save_channel(channel, root)
    status = {'complete': not missing, 'video_count': len(channel['videos']),
              'saved_count': len(channel['videos']) - len(missing), 'missing': missing}
    (root / 'archive-status.json').write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
    from .cache import remember
    if channel.get('url'):
        remember(root, channel['url'])
    return status
