"""Read the selected Videos tab from YouTube's initial page data; no pagination."""
import re
from urllib.parse import quote, unquote, urlparse
from ...errors import CollectionError, RiskControlError, UserNotFoundError
from .common import (parse_response, exclusion_reason, prefer_bio, normalize_data,
                     excluded_post_counts, recover_saved_failure, folder_id)

LOGIN_COOKIES = ('SAPISID', '__Secure-3PAPISID', 'LOGIN_INFO')
CDN_DOMAINS = ('ytimg.com', 'ggpht.com', 'googleusercontent.com')


def collection_url(url, user_id):
    path = quote(user_id, safe='@') if user_id.startswith('@') else 'channel/' + user_id
    return 'https://www.youtube.com/' + path + '/videos'


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def text(value):
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ''
    return value.get('simpleText') or value.get('content') or ''.join(run.get('text', '') for run in value.get('runs', []))


def parse_initial_data(data, user_id):
    metadata = data.get('metadata', {}).get('channelMetadataRenderer', {})
    result = {'name': metadata.get('title', ''), 'bio': metadata.get('description', ''), 'videos': [], 'no_posts': False}
    # Only the selected /videos tab belongs to this collection, not recommendations,
    # Shorts, playlists, or continuation pages elsewhere in the page data.
    if user_id.startswith('UC') and metadata.get('externalId') != user_id:
        return {**result, 'name': '', 'bio': ''}
    owners = [unquote(urlparse(u).path).rstrip('/').casefold() for u in metadata.get('ownerUrls', [])]
    if user_id.startswith('@') and owners and user_id.casefold() not in [p.lstrip('/') for p in owners]:
        return {**result, 'name': '', 'bio': ''}
    selected = next((o['tabRenderer'] for o in walk(data.get('contents', {}))
                     if o.get('tabRenderer', {}).get('selected') and
                     urlparse(o['tabRenderer'].get('endpoint', {}).get('commandMetadata', {}).get('webCommandMetadata', {}).get('url', '')).path.rstrip('/').endswith('/videos')), None)
    if selected is None:
        return result
    known = set()
    for obj in walk(selected.get('content', {})):
        old = obj.get('videoRenderer') or obj.get('gridVideoRenderer')
        new = obj.get('lockupViewModel', {})
        if old:
            identity, title = old.get('videoId'), text(old.get('title', {}))
            covers = old.get('thumbnail', {}).get('thumbnails', [])
        elif new.get('contentType') == 'LOCKUP_CONTENT_TYPE_VIDEO':
            identity = new.get('contentId')
            title = text(new.get('metadata', {}).get('lockupMetadataViewModel', {}).get('title', {}))
            covers = new.get('contentImage', {}).get('thumbnailViewModel', {}).get('image', {}).get('sources', [])
        else:
            continue
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}', identity or '') or identity in known:
            continue
        known.add(identity)
        cover = max(covers, key=lambda c: c.get('width', 0), default={}).get('url', '')
        result['videos'].append({'id': identity, 'title': title, 'url': f'https://www.youtube.com/watch?v={identity}',
                                 'cover_url': cover, 'content_type': 'video', 'source': 'initial_page_data',
                                 'type_evidence': ['selected_videos_tab', 'video_renderer']})
    if not result['videos']:
        messages = ' '.join(text(o['messageRenderer'].get('text', {})) for o in walk(selected) if 'messageRenderer' in o)
        result['no_posts'] = bool(re.search(r"没有任何视频|尚未发布|没有视频|has no videos|hasn't uploaded", messages, re.I))
    return result


async def read_dom(page):
    data = await page.evaluate('()=>window.ytInitialData || {}')
    from ..browser import profile_info
    result = parse_initial_data(data, profile_info(page.url)[1])
    return result


def check_page(dom, body_text):
    if re.search(r"unusual traffic|confirm you.re not a bot|确认您不是机器人|確認您不是機器人", body_text, re.I):
        raise RiskControlError('YouTube 要求验证访问者身份；已停止采集，请在浏览器正常完成验证后重试。')
    if not dom.get('name') and re.search(r"This channel does not exist|This page isn't available|此频道不存在|此页面无法显示|这个页面无法显示", body_text, re.I):
        raise UserNotFoundError('YouTube 频道不存在或不可访问。')


def finalize(channel, dom, output, first_page_posts, first_feed_received, require_video_types):
    if channel['name'] and not channel['videos'] and not dom.get('no_posts'):
        raise CollectionError('YouTube 未读到 Videos 标签的首屏视频；可能需要同意隐私提示、登录或完成验证，不将其视为空频道。')
    channel['first_page_source'] = 'initial_page_data'
    channel['scope'] = 'All videos from the selected Videos tab in the initial page data; no continuation requests or scrolling.'
    return channel


async def begin_login(page):
    link = page.locator('a[href*="accounts.google.com/ServiceLogin"]')
    if await link.count():
        await link.first.click()
