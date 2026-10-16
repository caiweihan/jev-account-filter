"""Read the first creator-page response produced by the normal Douyin website."""
import re
import json
from ...errors import CollectionError, RiskControlError, UserNotFoundError
from urllib.parse import parse_qs, urlparse

POST_TYPE_VERSION = 'douyin-post-types-v4-articles'


def is_douyin_response(url, user_id):
    parsed = urlparse(url)
    if parsed.hostname not in ('douyin.com', 'www.douyin.com'):
        return False
    query = parse_qs(parsed.query)
    if query.get('sec_user_id', [''])[0] != user_id:
        return False
    if parsed.path == '/aweme/v1/web/user/profile/other/':
        return True
    return parsed.path == '/aweme/v1/web/aweme/post/' and query.get('max_cursor', ['0'])[0] in ('', '0')


def is_image_post(post):
    """只用明确的类型证据排除图文；旧封面地址和拼出的 /video/ 链接不能证明类型。"""
    return (post.get('content_type') == 'image' or bool(post.get('images'))
            or bool(post.get('image_count')) or str(post.get('aweme_type')) in ('2', '68', '150')
            or bool(post.get('image_post_info')) or bool(post.get('image_stack_icon'))
            or '/note/' in post.get('url', ''))


def is_article_post(post):
    """实测163是文字文章：页面链接为/article/，响应包含article_info。"""
    info = post.get('article_info')
    article_metadata = isinstance(info, dict) and bool(info.get('article_id') or info.get('article_content'))
    return (post.get('content_type') == 'article' or str(post.get('aweme_type')) == '163'
            or article_metadata or '/article/' in post.get('url', ''))


def is_non_video_post(post):
    return is_image_post(post) or is_article_post(post)


def excluded_post_counts(channel):
    posts = channel.get('excluded_posts', [])
    return {'excluded_post_count': len(posts), 'excluded_article_count': sum(is_article_post(p) for p in posts),
            'excluded_image_count': sum(is_image_post(p) and not is_article_post(p) for p in posts)}


def normalize_dom_type(post):
    """实际作者卡片的视频链接可以作证据；旧程序拼出的链接不能作证据。"""
    if is_article_post(post):
        return {**post, 'content_type': 'article'}
    if is_image_post(post):
        return {**post, 'content_type': 'image'}
    url = urlparse(post.get('url', ''))
    # v2 DOM回退已检查图文角标，但遗漏了正常视频类型；只恢复这些有完整检查记录的作品。
    inspected = 'image_stack_icon' in post and isinstance(post.get('type_evidence'), list)
    if (post.get('source') == 'profile_dom' and inspected and url.scheme == 'https'
            and url.hostname in ('douyin.com', 'www.douyin.com')
            and url.path.rstrip('/') == f"/video/{post.get('id')}"):
        evidence = list(dict.fromkeys([*post['type_evidence'], 'actual_video_link']))
        return {**post, 'content_type': 'video', 'type_evidence': evidence}
    return post


def filter_image_posts(channel):
    """排除图片图文和文字文章，保留排除资料供复查；不修改旧快照文件。"""
    if channel.get('platform') != 'douyin':
        return channel
    excluded = list(channel.get('excluded_posts', []))
    known = {v['id'] for v in excluded}
    videos = []
    for post in channel.get('videos', []):
        post = normalize_dom_type(post)
        if is_non_video_post(post):
            if post['id'] not in known:
                reason = '文字文章，不作为视频候选' if is_article_post(post) else '图文/图集，不作为视频候选'
                excluded.append({**post, 'exclusion_reason': reason})
                known.add(post['id'])
        else:
            videos.append(post)
    return {**channel, 'videos': videos, 'excluded_posts': excluded,
            'no_video_posts': bool(excluded) and not videos}


def reconcile_dom_types(channel, dom):
    """以作品ID补充页面类型证据；接口作品顺序不变，不混入页面额外作品。"""
    by_id = {v['id']: v for v in dom.get('videos', [])}
    for video in channel.get('videos', []):
        evidence = by_id.get(video['id'])
        if not evidence:
            continue
        for key in ('image_stack_icon', 'type_evidence'):
            if evidence.get(key):
                video[key] = evidence[key]
        if is_article_post(evidence):
            video['content_type'] = 'article'
        elif is_image_post(evidence):
            video['content_type'] = 'image'
        elif evidence.get('content_type') == 'video' and video.get('content_type') != 'image':
            video['content_type'] = 'video'
    return filter_image_posts(channel)


def parse_douyin_payload(payload, user_id, *, include_images=False):
    profile, videos = {}, []
    user = payload.get('user', {})
    if user.get('nickname') and user.get('sec_uid', user_id) == user_id:
        profile = {'name': user['nickname'], 'bio': user.get('signature', '')}
    for post in payload.get('aweme_list', []) or []:
        if post.get('author', {}).get('sec_uid', user_id) != user_id:
            continue
        video_id = str(post.get('aweme_id', ''))
        if not re.fullmatch(r'\d+', video_id):
            continue
        image_post = is_image_post(post)
        article_post = is_article_post(post)
        if (image_post or article_post) and not include_images:
            continue
        cover = ''
        for key in ('cover', 'origin_cover', 'dynamic_cover'):
            urls = post.get('video', {}).get(key, {}).get('url_list', [])
            if urls:
                cover = urls[0]
                break
        if not cover and post.get('images'):
            urls = post['images'][0].get('display_image', {}).get('url_list', [])
            cover = urls[0] if urls else ''
        duration = post.get('video', {}).get('duration')
        has_play_addr = bool(post.get('video', {}).get('play_addr', {}).get('url_list'))
        # 图文也可能有 play_addr，不能单凭播放地址认定为视频。
        video_post = str(post.get('aweme_type')) in ('0', '4') or (
            isinstance(duration, (int, float)) and duration > 0 and has_play_addr)
        article = post.get('article_info')
        article = article if isinstance(article, dict) else {}
        videos.append({'id': video_id, 'title': post.get('desc', ''), 'cover_url': cover,
                       'url': f'https://www.douyin.com/{"article" if article_post else "note" if image_post else "video"}/{video_id}',
                       'source': 'profile_response', 'content_type': 'article' if article_post else 'image' if image_post else 'video' if video_post else 'unknown',
                       'aweme_type': post.get('aweme_type'), 'image_count': len(post.get('images') or []),
                       'image_post_info': bool(post.get('image_post_info')), 'duration_ms': duration,
                       'has_play_addr': has_play_addr,
                       'article_info': {k: article[k] for k in ('article_id', 'article_title') if k in article}})
    return profile, videos


DOM_SCRIPT = r"""() => {
 const text = (...selectors) => {
   for (const selector of selectors) {
     const el = document.querySelector(selector);
     if (el && el.textContent.trim()) return el.textContent.trim();
   }
   return '';
 };
 const videos = [];
 // 仅作者作品容器；页面推荐、SEO 链接、喜欢列表都不能混入作者作品。
 for (const a of document.querySelectorAll('[data-e2e="user-post-list"] a[href*="/video/"], [data-e2e="user-post-list"] a[href*="/note/"], [data-e2e="user-post-list"] a[href*="/article/"]')) {
   const id = a.href.match(/\/(?:video|note|article)\/(\d+)/)?.[1];
   if (!id) continue;
   const img = a.querySelector('img');
   const title = a.querySelector('[data-e2e*="title"], [class*="title"], p:last-child');
   // 实测图文角标是右上角叠放图片 SVG；匹配图形而非易变的哈希类名，不把点赞 SVG 当角标。
   const image_stack_icon = [...a.querySelectorAll('svg[viewBox="0 0 12 12"]')].some(svg => {
     const paths = [...svg.querySelectorAll('path')].map(p => (p.getAttribute('d') || '').replace(/\s/g, ''));
     return paths.some(d => d.startsWith('M1.4550C')) && paths.some(d => d.startsWith('M412a1.455'));
   });
   const image_label = [...a.querySelectorAll('[aria-label], .user-video-tag [title]')].some(el =>
     /^(?:Tag:\s*)?(?:图文|图集|图片)(?:作品)?$/.test((el.getAttribute('aria-label') || el.getAttribute('title') || '').trim()));
   const image_post = a.href.includes('/note/') || image_stack_icon || image_label;
   const article_post = a.href.includes('/article/');
   // 这里是页面作者作品卡片的真实链接，不是根据作品ID拼出的已有资料链接。
   const video_link = /^https:\/\/(?:www\.)?douyin\.com\/video\/\d+(?:[/?#]|$)/.test(a.href);
   videos.push({id, title: title?.getAttribute('title') || title?.textContent?.trim() || img?.alt || a.textContent.trim(),
     cover_url: img?.currentSrc || img?.src || '', url: a.href, source: 'profile_dom',
     content_type: article_post ? 'article' : image_post ? 'image' : video_link ? 'video' : 'unknown', image_stack_icon,
     type_evidence: [article_post ? 'article_link' : '', a.href.includes('/note/') ? 'note_link' : '', image_stack_icon ? 'image_stack_icon' : '',
                     image_label ? 'image_label' : '', video_link && !image_post ? 'actual_video_link' : ''].filter(Boolean)});
 }
 const visible = el => el.getBoundingClientRect().width && el.getBoundingClientRect().height;
 const captcha = [...document.querySelectorAll('[id*="captcha"], [class*="captcha"], iframe[src*="verify"]')].some(visible);
 let signature = '';
 // 页面初始状态中的作者资料可补足没有稳定 DOM 标签的简介；只读目标作者字段。
 try {
   const data = JSON.parse(decodeURIComponent(document.getElementById('RENDER_DATA')?.textContent || '{}'));
   const userId = location.pathname.split('/')[2];
   const walk = value => {
     if (!value || typeof value !== 'object') return;
     const id = value.secUid || value.sec_uid || value.secUserId || value.sec_user_id;
     if ((id === userId || (!id && value.nickname === text('[data-e2e="user-info"] h1'))) && typeof value.signature === 'string') signature = value.signature;
     // DOM 链接可能仍是 /video/；若初始状态保存了作品类型，用明确的类型/图片列表补足。
     const postId = value.aweme_id || value.awemeId;
     const post = postId && videos.find(v => v.id === String(postId));
     if (post) {
       const type = value.aweme_type ?? value.awemeType;
       const imageCount = Array.isArray(value.images) ? value.images.length : 0;
       if (type != null) post.aweme_type = type;
       if (imageCount) post.image_count = imageCount;
       const article = value.article_info || value.articleInfo;
       if (Number(type) === 163 || (article && (article.article_id || article.article_content || article.articleId || article.articleContent)) || post.content_type === 'article') post.content_type = 'article';
       else if ([2, 68, 150].includes(Number(type)) || imageCount) post.content_type = 'image';
       else if ([0, 4].includes(Number(type)) && type != null && post.content_type !== 'image') post.content_type = 'video';
     }
     for (const child of Object.values(value)) walk(child);
   };
   walk(data);
 } catch (_) {}
 const login_required = [...document.querySelectorAll('[role="dialog"], [class*="login"]')].some(el=>visible(el) && /扫码登录/.test(el.textContent) && /验证码登录/.test(el.textContent));
 const profileName = text('[data-e2e="user-title"]', '[data-e2e="user-info"] h1', 'h1');
 // 仅识别独立错误页的可见提示，简介/视频标题引用这几个字不能判为账号不存在。
 const user_not_found = !videos.length && !captcha && !login_required &&
   (!profileName || profileName === '用户不存在') && [...document.querySelectorAll('p, span, div, h1, h2')]
     .some(el => visible(el) && !el.children.length &&
       !el.closest('[data-e2e="user-info"], [data-e2e="user-post-list"], a') &&
       /^用户不存在[。！？\s]*$/.test(el.textContent.trim()));
 // “暂无内容”本身也可能表示私密或加载失败；只接受明确的未投稿说明。
 const postArea = document.querySelector('[data-e2e="user-post-list"]') || document.body;
 const is_private = [...postArea.querySelectorAll('p, span, div')]
   .some(el => visible(el) && /^(?:该账号为|这是)?私密账号[。\s]*$/.test(el.textContent.trim()));
 const no_posts = !videos.length && !captcha && !login_required && [...postArea.querySelectorAll('p, span, div')]
   .some(el => visible(el) && !el.closest('a[href*="/video/"], a[href*="/note/"]') &&
     /^该账号还未发布过作品(?:哦)?[~～!！。\s]*$/.test(el.textContent.trim()));
 // 实际主页的简介位于作者资料内、抖音号/IP 等信息行之后；不能取整个 user-info 混入统计数据。
 const bioElement = document.querySelector('[data-e2e="user-desc"], [data-e2e="user-signature"], [data-e2e="user-info"] > .t_m2gjO6, [data-e2e="user-info"] > p + div');
 const controls = [...(bioElement?.querySelectorAll('span, button, a') || [])].filter(el => !el.children.length && ['更多', '收起'].includes(el.textContent.trim()));
 let bio_collapsed = controls.some(el => el.textContent.trim() === '更多' && visible(el));
 const bioCopy = bioElement?.cloneNode(true);
 for (const el of [...(bioCopy?.querySelectorAll('span, button, a') || [])]) {
   if (!el.children.length && ['更多', '收起'].includes(el.textContent.trim())) el.remove();
 }
 for (const br of bioCopy?.querySelectorAll('br') || []) br.replaceWith('\n');
 let bio = (bioCopy?.textContent || '').trim();
 // “更多”也可能打开浮层而不是在资料区展开。只接收与当前简介开头匹配的可见浮层。
 if (bio_collapsed) {
   const prefix = bio.split('...')[0].replace(/\s/g, '').slice(0, 12);
   const expanded = [...document.querySelectorAll('[role="tooltip"], div, p, span')]
     .filter(el => visible(el) && !el.contains(bioElement) && !el.closest('[data-e2e="user-post-list"]'))
     .map(el => (el.innerText || el.textContent || '').trim())
     .filter(value => prefix && value.replace(/\s/g, '').startsWith(prefix) && value.length > bio.length)
     .sort((a, b) => b.length - a.length)[0];
   if (expanded) { bio = expanded; bio_collapsed = false; }
 }
 return {name: profileName,
   bio: bio || signature, bio_collapsed, videos, captcha, login_required, no_posts, is_private, user_not_found};
}"""


LOGIN_COOKIES = ('sessionid', 'sessionid_ss')


async def parse_response(response, user_id):
    if not is_douyin_response(response.url, user_id):
        return None
    profile, videos = parse_douyin_payload(await response.json(), user_id, include_images=True)
    return profile, videos, urlparse(response.url).path.endswith('/aweme/post/')


def exclusion_reason(video):
    if not is_non_video_post(video):
        return None
    return '文字文章，不作为视频候选' if is_article_post(video) else '图文/图集，不作为视频候选'


def check_page(dom, body_text):
    if dom.get('captcha') or any(text in body_text for text in ('访问过于频繁', '操作过于频繁', '请完成下列验证后继续')):
        raise RiskControlError('抖音出现风控/验证码页面；已停止采集，请在正常浏览器中完成验证后再运行。')
    if dom.get('user_not_found'):
        raise UserNotFoundError('抖音主页明确显示“用户不存在”，无法获取频道资料；不是登录失败或未投稿。')


async def read_dom(page):
    dom = await page.evaluate(DOM_SCRIPT)
    if dom.get('bio_collapsed'):
        more = page.locator('[data-e2e="user-info"] > .t_m2gjO6, [data-e2e="user-info"] > p + div').get_by_text('更多', exact=True)
        if await more.count() and await more.first.is_visible():
            await more.first.click()
            await page.wait_for_timeout(300)
            dom = await page.evaluate(DOM_SCRIPT)
    return dom


def prefer_bio(current, dom):
    return not dom.get('bio_collapsed') and len(dom['bio']) > len(current)


def finalize(channel, dom, output, first_page_posts, first_feed_received, require_video_types):
    platform = channel['platform']
    url = channel['url']
    channel = reconcile_dom_types(channel, dom)
    if not first_feed_received:
        first_page_posts = [dict(v) for v in dom['videos']]
    unknown = [v['id'] for v in channel['videos'] if v.get('content_type') != 'video']
    # 保存接口/DOM中的作品级证据，后续可离线调整过滤，不必再访问网页。
    evidence = {'platform': platform, 'channel_url': url, 'collected_at': channel['collected_at'],
                'post_type_version': POST_TYPE_VERSION,
                'source': 'profile_response' if first_feed_received else 'initial_dom',
                'posts': first_page_posts}
    (output / 'first-page-posts.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    type_status = {'post_type_version': POST_TYPE_VERSION, 'video_count': len(channel['videos']),
                   **excluded_post_counts(channel), 'unknown_ids': unknown,
                   'complete': not unknown}
    (output / 'post-type-status.json').write_text(json.dumps(type_status, ensure_ascii=False, indent=2), encoding='utf-8')
    if unknown and require_video_types:
        raise CollectionError(f'有{len(unknown)}个作品缺少可靠的视频类型证据，未保存为完整采集数据；请重试。作品ID：{", ".join(unknown[:5])}')
    channel['post_type_version'] = POST_TYPE_VERSION if not unknown else 'unverified'
    if unknown:
        channel['warnings'].append(f'{len(unknown)}个作品的类型尚未确认；请用 collect --resume 重新采集核实。')
    return channel


normalize_data = filter_image_posts


def recover_saved_failure(output, url):
    """仅修复类型核实失败的完整作品快照，不把其它采集错误的半成品当成功。"""
    from ..browser import profile_info, save_channel
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



CDN_DOMAINS = ('douyin.com', 'douyinpic.com', 'byteimg.com', 'bytecdn.cn', 'ibytedtos.com', 'pstatp.com', 'bytedance.com')


def folder_id(user_id):
    return 'douyin_' + user_id[-16:]


async def begin_login(page):
    button = page.get_by_text('登录', exact=True)
    if await button.count():
        await button.first.click()
