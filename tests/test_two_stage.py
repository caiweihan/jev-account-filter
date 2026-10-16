from task_helpers import parse_task_args
import asyncio
import json

import pytest
from PIL import Image

from account_filter.collection import runner as cli
from account_filter.screening.classifier import rank_titles
from task_helpers import build_title_request, build_request
from account_filter.collection.browser import profile_info
from account_filter.collection.platforms.douyin import is_douyin_response, parse_douyin_payload


def test_douyin_excludes_image_posts_and_preserves_type_evidence():
    from account_filter.collection.platforms.douyin import filter_image_posts, is_image_post
    payload = {'aweme_list': [
        {'aweme_id': '101', 'aweme_type': 0, 'desc': '视频', 'video': {'cover': {'url_list': ['video.jpg']}}},
        {'aweme_id': '102', 'aweme_type': 68, 'desc': '图文', 'images': [{'display_image': {'url_list': ['photo.jpg']}}]},
        {'aweme_id': '103', 'desc': '图片列表图文', 'images': [{'display_image': {'url_list': ['photo2.jpg']}}]},
        {'aweme_id': '104', 'aweme_type': 150, 'desc': '特殊图集'},
    ]}
    _, videos = parse_douyin_payload(payload, 'abc')
    assert [v['id'] for v in videos] == ['101']
    _, posts = parse_douyin_payload(payload, 'abc', include_images=True)
    assert posts[1]['url'].endswith('/note/102')
    assert posts[1]['aweme_type'] == 68 and posts[1]['image_count'] == 1
    channel = {'platform': 'douyin', 'videos': posts}
    filtered = filter_image_posts(channel)
    assert len(channel['videos']) == 4  # 原始资料不被原地删改。
    assert [v['id'] for v in filtered['videos']] == ['101']
    assert len(filtered['excluded_posts']) == 3
    assert len(filter_image_posts(filtered)['excluded_posts']) == 3
    assert is_image_post({'url': 'https://www.douyin.com/note/123'})
    assert not is_image_post({'url': 'https://www.douyin.com/video/123', 'cover_url': 'photo.jpg'})
    assert filter_image_posts({'platform': 'douyin', 'videos': posts[1:]})['no_video_posts']




def test_douyin_author_and_first_page_filter():
    url = 'https://www.douyin.com/aweme/v1/web/aweme/post/?sec_user_id=abc&max_cursor=0'
    assert profile_info('https://www.douyin.com/user/abc') == ('douyin', 'abc')
    assert is_douyin_response(url, 'abc')
    assert not is_douyin_response(url, 'other')
    assert not is_douyin_response(url.replace('max_cursor=0', 'max_cursor=123'), 'abc')
    profile, videos = parse_douyin_payload({'user': {'sec_uid': 'abc', 'nickname': '姓名', 'signature': '简介'},
        'aweme_list': [{'aweme_id': '123', 'desc': '标题', 'author': {'sec_uid': 'abc'},
                       'video': {'cover': {'url_list': ['https://x.douyinpic.com/a.jpg']}}},
                      {'aweme_id': '456', 'desc': '别人的视频', 'author': {'sec_uid': 'other'}}]}, 'abc')
    assert profile == {'name': '姓名', 'bio': '简介'}
    assert len(videos) == 1 and videos[0]['url'] == 'https://www.douyin.com/video/123'




def test_login_popup_waits_before_collecting(tmp_path, capsys):
    from account_filter.collection.browser import collect
    events = []
    class Page:
        logged_in = False
        @property
        def context(self):
            return self
        async def cookies(self, site):
            return [{'name': 'sessionid', 'value': 'test-session'}] if self.logged_in else []
        async def goto(self, *args, **kwargs):
            events.append('goto')
        def on(self, *args):
            pass
        def remove_listener(self, *args):
            pass
        async def evaluate(self, script):
            return {'name': '测试', 'bio': '', 'captcha': False, 'login_required': not self.logged_in,
                    'videos': [{'id': '123', 'title': '手语', 'url': 'https://www.douyin.com/video/123',
                                'content_type': 'video'}] if self.logged_in else []}
        def locator(self, selector):
            return self
        async def inner_text(self):
            return '扫码登录' if not self.logged_in else '作品'
        async def wait_for_timeout(self, ms):
            if not self.logged_in:
                events.append('login')
                self.logged_in = True
            await asyncio.sleep(ms / 1000)
        async def screenshot(self, **kwargs):
            assert self.logged_in
            events.append('screenshot')
    channel = asyncio.run(collect('https://www.douyin.com/user/abc',tmp_path,tmp_path / 'browser',page=Page(),timeout=5))
    assert len(channel['videos']) == 1 and events == ['goto', 'login', 'screenshot']
    assert '登录前不会关闭窗口' in capsys.readouterr().out


def test_douyin_dom_excludes_recommendations_and_reads_target_profile(tmp_path):
    from playwright.async_api import async_playwright
    from account_filter.collection.platforms.douyin import DOM_SCRIPT
    async def check():
        async with async_playwright() as playwright:
            context = await playwright.chromium.launch_persistent_context(str(tmp_path / 'browser'),
                         channel=cli.DEFAULT_BROWSER, headless=True)
            try:
                page = context.pages[0]
                await page.route('**/*', lambda route: route.abort())
                await page.route('https://www.douyin.com/**', lambda route: route.fulfill(
                    content_type='text/html; charset=utf-8', body='''<meta charset="utf-8"><div data-e2e="user-info"><h1>目标</h1></div>
                    <script id="RENDER_DATA">{"user":{"secUid":"abc","nickname":"目标","signature":"简介"}}</script>
                    <a href="/video/999">推荐视频</a><div data-e2e="user-post-list">
                    <a href="/video/123"><img src="https://x.douyinpic.com/a.jpg" alt="带作者的标题"><p>自己的标题</p></a></div>'''))
                await page.goto('https://www.douyin.com/user/abc')
                dom = await page.evaluate(DOM_SCRIPT)
                assert dom['name'] == '目标' and dom['bio'] == '简介'
                assert [v['id'] for v in dom['videos']] == ['123']
                assert dom['videos'][0]['title'] == '自己的标题'
                # 实际主页没有 user-desc 标签或可用 SSR 简介时，从作者资料中的简介块读取。
                await page.set_content('''<meta charset="utf-8"><div data-e2e="user-info"><h1>虚构测试账号A</h1>
                    <div>关注10 粉丝20 获赞30</div><p>抖音号：DEMO_ACCOUNT_A IP属地：示例地区</p>
                    <div class="t_m2gjO6"><span>这是一段虚构的测试简介，用于验证完整文本提取。</span></div>
                    <div>精彩直播回放</div></div>''')
                dom = await page.evaluate(DOM_SCRIPT)
                assert dom['bio'] == '这是一段虚构的测试简介，用于验证完整文本提取。'
                # 类名变化时保留结构回退，并保留简介的换行。
                await page.set_content('''<div data-e2e="user-info"><h1>目标</h1><p>抖音号：123</p>
                    <div class="changed-class">第一行<br>第二行</div><div>精彩直播回放</div></div>''')
                assert (await page.evaluate(DOM_SCRIPT))['bio'] == '第一行\n第二行'
                await page.set_content('''<div data-e2e="user-info"><h1>目标</h1><p>抖音号：123</p>
                    <div class="t_m2gjO6"><span>折叠简介...</span><div><span>更多</span></div></div></div>''')
                dom = await page.evaluate(DOM_SCRIPT)
                assert dom['bio_collapsed'] and dom['bio'] == '折叠简介...'
                await page.evaluate(r'''() => { const tooltip=document.createElement('div'); tooltip.className='custom-hashed-class'; tooltip.innerText='折叠简介的完整内容\n还有第二行'; document.body.appendChild(tooltip); }''')
                dom = await page.evaluate(DOM_SCRIPT)
                assert not dom['bio_collapsed'] and dom['bio'] == '折叠简介的完整内容\n还有第二行'
                await page.set_content('''<div data-e2e="user-info"><h1>目标</h1><p>抖音号：123</p>
                    <div class="t_m2gjO6"><span>完整简介<br>第二行</span><div><span>收起</span></div></div></div>''')
                dom = await page.evaluate(DOM_SCRIPT)
                assert not dom['bio_collapsed'] and dom['bio'] == '完整简介\n第二行'
                await page.set_content('<h1>空频道</h1><div data-e2e="user-post-list"><p>暂无内容</p><p>该账号还未发布过作品哦~</p></div>')
                assert (await page.evaluate(DOM_SCRIPT))['no_posts']
                await page.set_content('<h1>空频道</h1><div data-e2e="user-post-list"><p>暂无内容</p></div>')
                assert not (await page.evaluate(DOM_SCRIPT))['no_posts']
                await page.set_content('<h1>私密频道</h1><p>私密账号</p>')
                dom = await page.evaluate(DOM_SCRIPT)
                assert dom['is_private'] and not dom['no_posts']
                await page.set_content('<h1>登录页</h1><div role="dialog">扫码登录 验证码登录</div><p>该账号还未发布过作品哦~</p>')
                dom = await page.evaluate(DOM_SCRIPT)
                assert dom['login_required'] and not dom['no_posts']
                await page.set_content('<div><span>用户不存在</span></div>')
                dom = await page.evaluate(DOM_SCRIPT)
                assert dom['user_not_found'] and not dom['no_posts']
                await page.set_content('<h1>用户不存在</h1>')
                assert (await page.evaluate(DOM_SCRIPT))['user_not_found']
                await page.set_content('<div data-e2e="user-info"><h1>正常用户</h1><p>用户不存在</p></div>')
                assert not (await page.evaluate(DOM_SCRIPT))['user_not_found']
                await page.set_content('<div data-e2e="user-post-list"><a href="/video/123"><p>用户不存在</p></a></div>')
                assert not (await page.evaluate(DOM_SCRIPT))['user_not_found']
                await page.set_content('<div role="dialog">扫码登录 验证码登录</div><p>用户不存在</p>')
                assert not (await page.evaluate(DOM_SCRIPT))['user_not_found']
                await page.set_content('<div id="captcha">验证</div><p>用户不存在</p>')
                assert not (await page.evaluate(DOM_SCRIPT))['user_not_found']
            finally:
                await context.close()
    asyncio.run(check())


def test_titles_all_included_and_budget_does_not_truncate(tmp_path):
    channel = {'platform': 'douyin', 'name': '测试', 'videos': [
        {'id': str(i), 'title': f'标题{i}', 'url': f'https://www.douyin.com/video/{i}'} for i in range(20)]}
    payload, selection = build_title_request(channel, model='test')
    assert len(payload['questions']) == 20
    assert all(isinstance(part, str) for part in payload['state'])
    raw = {'answers': {v['key']: {'type': 'noul', 'noul': i / 20} for i, v in enumerate(selection['videos'])}}
    assert rank_titles(raw, selection)[0]['id'] == '19'
    with pytest.raises(ValueError, match='不会丢弃标题'):
        build_title_request(channel, model='test', context_budget=1)
    with pytest.raises(ValueError, match='全部候选'):
        build_request(channel, tmp_path, model='test', context_budget=5000, require_all=True)


@pytest.mark.parametrize('api', ['decisions', 'chat'])
def test_first_stage_cannot_use_account_metadata(api):
    # 名称、简介和平台的变化不能影响实际请求；甚至无需提供这些字段。
    titles = [{'id': '1', 'title': '今天学手语'}, {'id': '2', 'title': '城市新闻'}]
    personal = {'name': 'PRIVATE_PERSON_MARKER', 'bio': 'PRIVATE_BIO_MARKER', 'platform': 'douyin', 'videos': titles}
    media = {'name': 'PRIVATE_MEDIA_MARKER', 'bio': 'PRIVATE_NEWS_BIO_MARKER', 'platform': 'kuaishou', 'videos': titles}
    a, _ = build_title_request(personal, model='test', api=api)
    b, _ = build_title_request(media, model='test', api=api)
    c, _ = build_title_request({'videos': titles}, model='test', api=api)
    assert a == b == c
    assert 'PRIVATE_' not in json.dumps(a)
