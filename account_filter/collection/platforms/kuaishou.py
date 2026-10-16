"""Kuaishou response parsing and initial profile DOM; no request signing."""
import re
from urllib.parse import parse_qs, urlparse
from ...errors import RiskControlError

def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def first(obj, *keys):
    return next((obj[k] for k in keys if obj.get(k) is not None and obj.get(k) != ''), '')


def parse_profile_payload(payload: dict) -> tuple[dict, list[dict]]:
    """Only pass target-profile responses here, never recommendation/search responses."""
    profile = {}
    videos = []
    for obj in walk(payload):
        for key in ('userProfile', 'profile'):
            user = obj.get(key)
            if isinstance(user, dict):
                user = user.get('profile', user)
                name = first(user, 'user_name', 'userName', 'name', 'nickname')
                if isinstance(name, str) and name:
                    profile = {'name': name, 'bio': str(first(user, 'user_text', 'userText', 'bio', 'description'))}
        photo = obj.get('photo')
        if not isinstance(photo, dict):
            continue
        video_id = first(photo, 'id', 'photoId', 'photo_id')
        if not video_id or not re.fullmatch(r'[A-Za-z0-9_-]+', str(video_id)):
            continue
        cover = first(photo, 'coverUrl', 'cover_url', 'poster', 'cover')
        if not cover:
            urls = photo.get('coverUrls', photo.get('cover_urls', []))
            if urls:
                cover = urls[0].get('url', '') if isinstance(urls[0], dict) else urls[0]
        videos.append({'id': str(video_id), 'title': str(first(photo, 'caption', 'title', 'description')),
                       'cover_url': cover if isinstance(cover, str) else '',
                       'url': f'https://www.kuaishou.com/short-video/{video_id}', 'source': 'profile_response'})
    return profile, videos


def is_profile_response(url: str, request_body: dict, user_id: str) -> bool:
    if urlparse(url).hostname not in ('www.kuaishou.com', 'kuaishou.com'):
        return False
    path = urlparse(url).path
    if path.startswith('/rest/v/profile/'):
        return str(first(request_body, 'user_id', 'userId')) == user_id
    if path == '/graphql':
        return request_body.get('operationName') in ('visionProfile', 'visionProfilePhotoList') and str(first(request_body.get('variables', {}), 'userId', 'user_id')) == user_id
    return False


DOM_SCRIPT = r"""() => {
 const text = (...selectors) => {
   for (const selector of selectors) {
     const el = document.querySelector(selector);
     if (el && el.textContent.trim()) return el.textContent.trim();
   }
   return '';
 };
 const videos = [];
 for (const a of document.querySelectorAll('a[href*="/short-video/"]')) {
   const id = a.href.match(/\/short-video\/([\w-]+)/)?.[1];
   if (!id) continue;
   const img = a.querySelector('img');
   videos.push({id, title: a.querySelector('[class*="caption"], [class*="title"]')?.textContent?.trim() || img?.alt || a.textContent.trim(),
     cover_url: img?.currentSrc || img?.src || '', url: a.href, source:'profile_dom'});
 }
 // 排除简介和作品标题里引用的文字，只匹配可见的独立错误提示。
 const feed_error = [...document.querySelectorAll('div, p, span')].some(el => {
   if (el.closest('.profile-user-desc, .user-desc, .user-bio, .text-count, .profile-user-name, .user-name, a[href*="/short-video/"]')) return false;
   const rect = el.getBoundingClientRect();
   if (!rect.width || !rect.height || getComputedStyle(el).visibility === 'hidden') return false;
   return /^服务器异常[，,]?稍后重试[。.!！]?$/.test(el.textContent.replace(/\s+/g, ''));
 });
 return {name: text('.profile-user-name', '.user-name', '[class*="profile"] h1'),
   bio: text('.profile-user-desc', '.user-desc', '.user-bio', '[class*="profile"] .text-count .text[title]', '[class*="profile"] [class*="desc"]'), videos, feed_error};
}"""


def check_risk_control(dom, body_text):
    if re.match(r'^\s*\{\s*"result"\s*:\s*2', body_text):
        raise RiskControlError('快手返回 result:2 风控页面；已停止采集，请稍后恢复正常访问后再运行。')
    # 以当前页面的作品为准，不能用已收到的网络数据掩盖作品区域加载失败。
    if dom.get('feed_error') and not dom['videos']:
        raise RiskControlError('快手风控：作品区域仅显示“服务器异常，稍后重试”，未加载作品；已停止采集，请稍后再运行。')

LOGIN_COOKIES = ('passToken',)


async def parse_response(response, user_id):
    body = {key: values[0] for key, values in parse_qs(urlparse(response.url).query).items()}
    if response.request.post_data:
        body.update(response.request.post_data_json or {})
    if not is_profile_response(response.url, body, user_id):
        return None
    if first(body.get('variables', body), 'pcursor', 'cursor') not in ('', '0', 0):
        return None
    profile, videos = parse_profile_payload(await response.json())
    return profile, videos, bool(videos)


def check_page(dom, body_text):
    check_risk_control(dom, body_text)


async def read_dom(page):
    return await page.evaluate(DOM_SCRIPT)


def exclusion_reason(video):
    return None


def prefer_bio(current, dom):
    return False


def finalize(channel, dom, output, first_page_posts, first_feed_received, require_video_types):
    return channel


def normalize_data(channel):
    return channel


def excluded_post_counts(channel):
    return {'excluded_post_count': 0, 'excluded_image_count': 0, 'excluded_article_count': 0}


def recover_saved_failure(output, url):
    return False


CDN_DOMAINS = ('kuaishou.com', 'kwimgs.com', 'yximgs.com', 'gifshow.com')


def folder_id(user_id):
    return user_id


async def begin_login(page):
    button = page.get_by_text('登录', exact=True)
    if await button.count():
        await button.first.click()
