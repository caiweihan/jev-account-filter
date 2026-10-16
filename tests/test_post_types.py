from task_helpers import parse_task_args
import asyncio
import json
from contextlib import asynccontextmanager

import pytest
from PIL import Image

from account_filter.collection import runner as cli
from account_filter.experiments import write_json
from account_filter.collection.browser import CollectionError, collect, save_channel, recover_post_type_failure
from account_filter.collection.platforms.douyin import DOM_SCRIPT, parse_douyin_payload, reconcile_dom_types, filter_image_posts, excluded_post_counts


def test_image_with_play_address_is_not_video_and_unknown_type_is_preserved():
    _, posts = parse_douyin_payload({'aweme_list': [
        {'aweme_id': '1', 'aweme_type': 68, 'images': [{}],
         'video': {'duration': 0, 'play_addr': {'url_list': ['image-play']}}},
        {'aweme_id': '2', 'aweme_type': 0, 'video': {'duration': 1234}},
        {'aweme_id': '3', 'aweme_type': 999, 'video': {'play_addr': {'url_list': ['uncertain']}}},
    ]}, 'abc', include_images=True)
    assert [v['content_type'] for v in posts] == ['image', 'video', 'unknown']
    assert posts[0]['has_play_addr'] and posts[0]['image_count'] == 1
    assert posts[1]['duration_ms'] == 1234


def test_dom_evidence_excludes_only_matching_id_without_changing_order():
    channel = {'platform': 'douyin', 'videos': [
        {'id': '1', 'content_type': 'video'}, {'id': '2', 'content_type': 'unknown'}]}
    dom = {'videos': [{'id': '1', 'content_type': 'image', 'image_stack_icon': True},
                      {'id': '2', 'content_type': 'video'}, {'id': '3', 'content_type': 'video'}]}
    result = reconcile_dom_types(channel, dom)
    assert [v['id'] for v in result['videos']] == ['2']
    assert result['videos'][0]['content_type'] == 'video'
    assert result['excluded_posts'][0]['id'] == '1'


def test_article_163_is_not_video_even_with_play_address_and_no_images():
    payload = {'aweme_list': [
        {'aweme_id': '1', 'aweme_type': 163, 'desc': '文字文章', 'images': [],
         'article_info': {'article_id': '1', 'article_title': '文章标题', 'article_content': '正文'},
         'video': {'duration': 0, 'play_addr': {'url_list': ['article-play']}}},
        {'aweme_id': '2', 'aweme_type': 0, 'article_info': {}, 'desc': '视频'},
        {'aweme_id': '3', 'aweme_type': 68, 'images': [{}]},
    ]}
    _, videos = parse_douyin_payload(payload, 'abc')
    assert [v['id'] for v in videos] == ['2']
    _, posts = parse_douyin_payload(payload, 'abc', include_images=True)
    assert posts[0]['content_type'] == 'article' and posts[0]['url'].endswith('/article/1')
    assert posts[0]['has_play_addr'] and posts[0]['article_info'] == {'article_id': '1', 'article_title': '文章标题'}
    # 旧失败快照虽误拼了/video/，已有类型163足以离线排除。
    posts[0].update(content_type='unknown', url='https://www.douyin.com/video/1')
    channel = filter_image_posts({'platform': 'douyin', 'videos': posts})
    assert [v['id'] for v in channel['videos']] == ['2']
    assert excluded_post_counts(channel) == {'excluded_post_count': 2, 'excluded_article_count': 1, 'excluded_image_count': 1}
    assert '文字文章' in channel['excluded_posts'][0]['exclusion_reason']


def test_dom_detects_stack_icon_even_on_video_link_and_does_not_use_title(tmp_path):
    from playwright.async_api import async_playwright
    async def check():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(channel=cli.DEFAULT_BROWSER, headless=True)
            try:
                page = await browser.new_page()
                await page.route('**/*', lambda route: route.abort())
                await page.route('https://www.douyin.com/**', lambda route: route.fulfill(
                    content_type='text/html; charset=utf-8', body='''<meta charset="utf-8">
                    <div data-e2e="user-post-list">
                    <a href="/video/1"><svg viewBox="0 0 12 12"><path d="M1.455 0C.65 0 0 .651 0 1.455V8"/>
                    <path d="M4 12a1.455 1.455 0 0 1-1.455-1.454"/></svg><p>图文作品</p></a>
                    <a href="/video/2"><p title="图片">图片</p></a>
                    <a href="/note/3"><p>只有一张图片的图文</p></a>
                    <a href="/video/4"><span aria-label="Tag: 图文"></span><p>标签图文</p></a>
                    </div><script id="RENDER_DATA">{"posts":[{"aweme_id":"1","aweme_type":0},
                    {"aweme_id":"2","aweme_type":0}]}</script>'''))
                await page.goto('https://www.douyin.com/user/abc')
                dom = await page.evaluate(DOM_SCRIPT)
                assert [v['content_type'] for v in dom['videos']] == ['image', 'video', 'image', 'image']
                assert dom['videos'][0]['image_stack_icon']
                assert 'image_label' in dom['videos'][3]['type_evidence']
                # SSR首屏没有接口响应，也没有RENDER_DATA时，真实作者卡片的视频链接仍可核实。
                await page.set_content('''<div data-e2e="user-post-list">
                    <a href="/video/5"><p>正常视频</p></a><a href="/note/6"><p>图文</p></a>
                    <a href="/article/7"><p>文字文章</p></a></div>
                    <script id="RENDER_DATA">{"posts":[{"aweme_id":"5","aweme_type":0,"article_info":{}},
                    {"aweme_id":"7","aweme_type":163}]}</script>''')
                dom = await page.evaluate(DOM_SCRIPT)
                assert [v['content_type'] for v in dom['videos']] == ['video', 'image', 'article']
                assert dom['videos'][0]['type_evidence'] == ['actual_video_link']
                assert dom['videos'][2]['type_evidence'] == ['article_link']
            finally:
                await browser.close()
    asyncio.run(check())


def test_only_inspected_dom_links_can_restore_missing_video_type():
    posts = [
        {'id': '1', 'url': 'https://www.douyin.com/video/1', 'source': 'profile_dom',
         'content_type': 'unknown', 'image_stack_icon': False, 'type_evidence': []},
        {'id': '2', 'url': 'https://www.douyin.com/video/2', 'source': 'profile_response',
         'content_type': 'unknown', 'image_stack_icon': False, 'type_evidence': []},
        {'id': '3', 'url': 'https://www.douyin.com/video/3', 'source': 'profile_dom', 'content_type': 'unknown'},
        {'id': '4', 'url': 'https://www.douyin.com/video/4', 'source': 'profile_dom',
         'image_stack_icon': True, 'type_evidence': []},
    ]
    filtered = filter_image_posts({'platform': 'douyin', 'videos': posts})
    assert [v.get('content_type') for v in filtered['videos']] == ['video', 'unknown', 'unknown']
    assert filtered['videos'][0]['type_evidence'] == ['actual_video_link']
    assert filtered['excluded_posts'][0]['id'] == '4'
    assert posts[0]['content_type'] == 'unknown'




def test_saved_api_article_type_failure_recovers_without_website(tmp_path):
    url = 'https://www.douyin.com/user/abc'
    posts = [{'id': '1', 'aweme_type': 163, 'content_type': 'unknown', 'source': 'profile_response'},
             {'id': '2', 'aweme_type': 0, 'content_type': 'video', 'source': 'profile_response'}]
    save_channel({'platform': 'douyin', 'name': '文章和视频', 'url': url, 'videos': posts,
                  'collection_state': 'failed'}, tmp_path)
    write_json(tmp_path / 'collection-status.json', {'error_type': 'CollectionError',
        'error': '有1个作品缺少可靠的视频类型证据，未更新正式缓存；请重试。'})
    write_json(tmp_path / 'first-page-posts.json', {'source': 'profile_response', 'channel_url': url, 'posts': posts})
    assert recover_post_type_failure(tmp_path, url)
    restored = json.loads((tmp_path / 'channel.json').read_text(encoding='utf-8'))
    assert [v['id'] for v in restored['videos']] == ['2']
    assert restored['excluded_posts'][0]['content_type'] == 'article'
    assert restored['first_page_source'] == 'profile_response'
    status = json.loads((tmp_path / 'post-type-status.json').read_text(encoding='utf-8'))
    assert status['excluded_article_count'] == 1 and status['excluded_image_count'] == 0
