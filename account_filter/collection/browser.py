"""Collect the normal browser page and its profile responses; no private API signing."""
import asyncio
import json
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright
from .platforms.registry import PLATFORMS, adapter


from ..errors import CollectionError, RiskControlError, UserNotFoundError


def profile_info(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    if parsed.scheme == 'https' and parsed.port in (None, 443):
        for platform, adapter in PLATFORMS.items():
            hosts, path = adapter['hosts'], adapter['profile_path']
            match = re.fullmatch(rf'/{path}/([A-Za-z0-9_-]+)/?', parsed.path)
            if parsed.hostname in hosts and match:
                return platform, match[1]
    raise ValueError('请输入已配置平台的 HTTPS 账户主页链接：' + '；'.join(f"{item['name']} https://{item['hosts'][0]}/{item['profile_path']}/<id>" for item in PLATFORMS.values()))


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
        if not any(domain.lstrip('.') == host or domain.endswith('.' + host) for item in PLATFORMS.values() for host in item['hosts']):
            continue
        item = {k: cookie[k] for k in ('name', 'value', 'domain', 'path', 'expires', 'httpOnly', 'secure', 'sameSite') if k in cookie}
        item.setdefault('path', '/')
        if item.get('sameSite') not in ('Strict', 'Lax', 'None'):
            item.pop('sameSite', None)
        clean.append(item)
    if not clean:
        raise ValueError('Cookie 文件中没有已配置平台的 Cookie。')
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
    platform_adapter = adapter(platform)
    output.mkdir(parents=True, exist_ok=True)
    context = page.context
    channel = {'platform': platform, 'id': user_id, 'url': url, 'name': '', 'bio': '',
               'videos': [], 'excluded_posts': [], 'warnings': [], 'collected_at': datetime.now(timezone.utc).isoformat(),
               'scope': 'All items from the first creator-feed response; no scrolling or pagination.'}
    pending = set()
    first_feed_received = False
    first_page_posts = []
    async def capture(response):
        nonlocal first_feed_received, first_page_posts
        try:
            parsed = await platform_adapter.parse_response(response, user_id)
            if parsed is None:
                return
            profile, videos, is_feed = parsed
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
            reason = platform_adapter.exclusion_reason(video)
            if reason:
                if video['id'] not in excluded:
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
        platform_adapter.check_page(dom, body_text)
    async def read_dom():
        return await platform_adapter.read_dom(page)
    try:
        if cookies:
            await context.add_cookies(import_cookies(cookies))
        if login:
            site = 'https://' + PLATFORMS[platform]['hosts'][0]
            login_cookies = platform_adapter.LOGIN_COOKIES
            if on_status:
                on_status('等待扫码（请在浏览器登录）')
            else:
                print('请在当前浏览器窗口完成扫码登录；会话仅保存在项目 .browser 目录。', flush=True)
            await page.goto(site, wait_until='domcontentloaded', timeout=timeout * 1000)
            await page.wait_for_timeout(2000)
            login_deadline = asyncio.get_running_loop().time() + login_timeout
            if not any(c['name'] in login_cookies and c['value'] for c in await context.cookies(site)):
                await platform_adapter.begin_login(page)
            while not any(c['name'] in login_cookies and c['value'] for c in await context.cookies(site)):
                body_text = await page.locator('body').inner_text()
                check_page({'videos': []}, body_text)
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
            if dom['bio'] and (not channel['bio'] or platform_adapter.prefer_bio(channel['bio'], dom)):
                channel['bio'] = dom['bio']
            check_page(dom, await page.locator('body').inner_text())
            if dom.get('login_required') and not any(c['name'] in platform_adapter.LOGIN_COOKIES and c['value'] for c in await context.cookies('https://' + PLATFORMS[platform]['hosts'][0])):
                if headless:
                    raise CollectionError('平台要求登录，请用有窗口模式运行 login 完成扫码。')
                if on_status:
                    on_status('等待扫码（请在浏览器登录）')
                else:
                    print('平台要求登录；请在当前窗口扫码，登录前不会关闭窗口或调用模型。', flush=True)
                login_deadline = asyncio.get_running_loop().time() + login_timeout
                while not any(c['name'] in platform_adapter.LOGIN_COOKIES and c['value'] for c in await context.cookies('https://' + PLATFORMS[platform]['hosts'][0])):
                    current = await read_dom()
                    check_page(current, await page.locator('body').inner_text())
                    if asyncio.get_running_loop().time() >= login_deadline:
                        raise CollectionError('等待扫码登录超时；请重新运行 login。')
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
        channel = platform_adapter.finalize(channel, dom, output, first_page_posts, first_feed_received, require_video_types)
        no_posts = dom.get('no_posts') and not channel['videos']
        is_private = dom.get('is_private') and not channel['videos']
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
        if dom['bio'] and (not channel['bio'] or platform_adapter.prefer_bio(channel['bio'], dom)):
            channel['bio'] = dom['bio']
        if not channel['bio']:
            channel['warnings'].append('未获取个人简介（可能为空或解析失败），保留空值。')
        await page.screenshot(path=str(output / 'channel-page.png'), full_page=True)
        save_channel(channel, output)
        (output / 'page-text.txt').write_text(await page.locator('body').inner_text(), encoding='utf-8')
        (output / 'collection-status.json').write_text(json.dumps({'status': 'success', 'channel_url': url,
            'collected_at': channel['collected_at'], 'video_count': len(channel['videos']),
            **platform_adapter.excluded_post_counts(channel), 'no_video_posts': channel['no_video_posts'],
            'no_posts': bool(no_posts), 'is_private': bool(is_private)}, ensure_ascii=False, indent=2), encoding='utf-8')
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
        raise
    finally:
        page.remove_listener('response', on_response)
        if pending:
            await asyncio.gather(*list(pending), return_exceptions=True)



async def download_cover(context, url: str, destination: Path):
    """Reuse browser cookies only for the CDN request; cookies never enter model input."""
    host = urlparse(url).hostname or ''
    domains = [domain for name in PLATFORMS for domain in adapter(name).CDN_DOMAINS]
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
        return adapter(profile_info(url)[0]).normalize_data(channel)
    except (OSError, ValueError, KeyError):
        return None


def recover_post_type_failure(output, url):
    return adapter(profile_info(url)[0]).recover_saved_failure(output, url)


def attach_saved_covers(channel, root):
    for video in channel['videos']:
        path = root / 'covers' / f"{video['id']}.jpg"
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
            destination = root / 'covers' / f"{video['id']}.jpg"
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
    return status
