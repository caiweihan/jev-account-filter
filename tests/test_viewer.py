"""Offline browser checks for CSV parsing, cache alignment, and data isolation."""
import csv
import io
import json
import hashlib

import pytest
from PIL import Image
from playwright.sync_api import sync_playwright

from account_filter.viewer import build
from task_helpers import TASK, summarize
from test_report import fixture_csv


@pytest.fixture(scope='module')
def browser():
    with sync_playwright() as p:
        instance = p.chromium.launch(channel='msedge', headless=True)
        yield instance
        instance.close()


@pytest.fixture
def viewer(tmp_path, browser):
    page = browser.new_page()
    errors, network = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda request: network.append(request.url)
            if request.url.startswith(('http:', 'https:')) else None)
    page.goto(build(tmp_path / 'viewer.html').as_uri())
    page.locator('#advanced-settings').evaluate('el=>el.open=true')
    yield page, errors, network
    assert not errors
    assert not network
    page.close()


def pick_csv(page, text, name='results.csv'):
    page.locator('#csv-file').set_input_files({
        'name': name, 'mimeType': 'text/csv', 'buffer': text.encode('utf-8-sig')})


def data(page):
    return page.frame_locator('#report').locator('#report-data').evaluate(
        'node=>JSON.parse(node.textContent)')


def ready(page, fragment):
    page.wait_for_function('(text)=>document.querySelector("#status").textContent.includes(text)', arg=fragment)
    page.wait_for_function('()=>!document.querySelector("#csv-file").disabled')
    if fragment.startswith('已载入') or fragment.startswith(('封面 ', '数据匹配 ')):
        page.frame_locator('#report').locator('#eval-summary .value').first.wait_for()
        sized(page)


def sized(page):
    height = page.frame_locator('#report').locator('body').evaluate('el=>Math.ceil(el.getBoundingClientRect().height)')
    page.wait_for_function('(height)=>Math.abs(document.querySelector("#report").getBoundingClientRect().height-height)<2', arg=height)


def parent_click(page, selector):
    # Cross-frame layout changes need a compositor paint after scrolling the
    # outer page; otherwise Edge can dispatch the click at its old coordinates.
    page.locator(selector).scroll_into_view_if_needed()
    page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
    page.locator(selector).click()


def report_click(page, selector):
    sized(page)
    button = page.frame_locator('#report').locator(selector)
    button.scroll_into_view_if_needed()
    page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
    button.click()


def test_viewer_matches_existing_statistics_and_reloads_without_stale_state(tmp_path, viewer):
    page, _, _ = viewer
    source = fixture_csv(tmp_path)
    original = source.read_bytes()
    page.locator('#category').select_option(label=TASK['name'])
    page.locator('#csv-file').set_input_files(source)
    ready(page, '已载入 5 个频道')
    payload = data(page)
    assert payload['summary'] == summarize(payload['rows'])
    frame = page.frame_locator('#report')
    frame.locator('#agreement').select_option('wrong')
    assert frame.locator('#case-table tbody tr').count() == 2
    assert frame.locator('#case-table img').count() == 0
    report_click(page, '#case-table [data-case] >> nth=0')
    assert frame.locator('#detail-content h2').inner_text().startswith('不符</script>')
    assert frame.locator('#detail-content img').count() == 0
    frame.locator('#close-detail').click()
    assert not frame.locator('#detail').evaluate('el=>el.open')
    text = '账户名称,频道网址,预测结果,人工标注,频道概率,视频1分数,视频1链接\r\n"重载,账户\n含引号""测试",https://example.com/a,手语频道,手语频道,0,1,https://example.com/v\r\n'
    pick_csv(page, text, 'other.csv')
    ready(page, '已载入 1 个频道')
    assert data(page)['rows'][0]['name'] == '重载,账户\n含引号"测试'
    assert data(page)['rows'][0]['p'] == 0
    assert frame.locator('#agreement').input_value() == ''
    assert frame.locator('#manual option').count() == 2
    assert source.read_bytes() == original


def test_external_cache_and_second_cover_folder_follow_video_links(tmp_path, viewer):
    page, _, _ = viewer
    experiment = tmp_path / 'external-experiment'
    folder = experiment / 'intermediate/999_arbitrary'
    folder.mkdir(parents=True)
    header = ['账户名称', '频道网址', '预测结果', '人工标注', '频道概率', '视频1分数', '视频1链接', '视频2分数', '视频2链接']
    out = io.StringIO(newline='')
    writer = csv.writer(out)
    writer.writerow(header)
    writer.writerow(['虚构账户', 'https://example.com/user/a?source=search', TASK['positive_label'], TASK['negative_label'], '.8', '.9', 'https://example.com/video/2', '.2', 'https://example.com/video/1'])
    source = experiment / 'results.csv'
    source.write_text(out.getvalue(), encoding='utf-8-sig', newline='')
    (experiment / 'category.json').write_text(json.dumps(TASK), encoding='utf-8')
    channel = {'url': 'https://example.com/user/a', 'bio': '外部采集简介', 'videos': [
        {'id': '1', 'url': 'https://example.com/video/1', 'title': '低分标题', 'cover_path': r'C:\old-project\data\channels\demo\a\covers\1.jpg'},
        {'id': '2', 'url': 'https://example.com/video/2', 'title': '高分标题', 'cover_path': r'C:\old-project\data\channels\demo\a\covers\2.jpg'}]}
    (folder / 'channel.json').write_text(json.dumps(channel), encoding='utf-8')
    (folder / 'title-ranking.json').write_text(json.dumps({'videos': [{'id': '2', 'title_probability': .95}]}), encoding='utf-8')
    audit_folder = experiment / 'cover-audit/run'
    audit_folder.mkdir(parents=True)
    (audit_folder.parent / 'latest.json').write_text(json.dumps({'path': 'cover-audit/run/audit-results.json'}), encoding='utf-8')
    (audit_folder / 'audit-results.json').write_text(json.dumps({
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'rows': [],
        'model': 'mock', 'prompt_version': 'mock', 'generated': 'test', 'csv': 'cover-audit/run/cover-audit.csv',
    }), encoding='utf-8')
    (audit_folder / 'cover-audit.csv').write_text('虚构测试\n', encoding='utf-8')
    page.locator('#csv-file').set_input_files(source)
    ready(page, '已载入 1 个频道')
    page.locator('#cache-folder').set_input_files(experiment)
    ready(page, '已载入 1 个频道')
    assert page.locator('#category').input_value() != ''
    assert data(page)['rows'][0]['bio'] == '外部采集简介'
    assert data(page)['rows'][0]['videos'][0]['title'] == '高分标题'
    assert data(page)['rows'][0]['videos'][0]['title_p'] == .95
    assert data(page)['summary']['missing_cover'] == 2
    assert data(page)['cover_audit']['source_sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert page.frame_locator('#report').locator('#front-audit').is_visible()
    covers = tmp_path / 'independent-covers'
    covers.mkdir()
    Image.new('RGB', (11, 17), 'red').save(covers / '1.jpg')
    Image.new('RGB', (17, 11), 'blue').save(covers / '2.jpg')
    page.locator('#cache-folder').set_input_files(covers)
    ready(page, '封面 2 张')
    frame = page.frame_locator('#report')
    frame.locator('#case-table [data-case]').click()
    images = frame.locator('#detail-content .video img')
    images.first.wait_for()
    assert images.first.evaluate('img=>img.decode().then(()=>img.naturalWidth)') == 17
    assert images.nth(1).evaluate('img=>img.decode().then(()=>img.naturalWidth)') == 11
    assert data(page)['rows'][0]['videos'][0]['cover'].startswith('viewer-asset:')
    frame.locator('#close-detail').click()
    assert not frame.locator('#detail').evaluate('el=>el.open'), 'dialog still open'
    sized(page)
    parent_click(page, '#clear-cache')
    ready(page, '数据匹配 0/1')
    assert data(page)['rows'][0]['bio'] == ''
    assert data(page)['summary']['missing_cover'] == 2


def test_invalid_csv_keeps_previous_report_and_custom_labels_are_safe(viewer):
    page, _, _ = viewer
    page.locator('#category').select_option('custom')
    pick_csv(page, '账户名称,频道网址,预测结果,人工标注,频道概率\nA,https://example.com/a,"<img src=x onerror=alert(1)>",negative,.4\n')
    ready(page, '自定义正类')
    page.locator('#positive').select_option('<img src=x onerror=alert(1)>')
    page.wait_for_function('()=>!document.querySelector("#positive").disabled')
    page.locator('#negative').select_option('negative')
    ready(page, '已载入 1 个频道')
    frame = page.frame_locator('#report')
    assert frame.locator('#matrix img').count() == 0
    assert frame.locator('#eval-summary img').count() == 0
    assert '<img src=x' in frame.locator('#case-table').inner_text()
    for text, expected in [
        ('账户名称,频道网址,预测结果,人工标注,频道概率\nA,x,yes,no,NaN\n', '无效概率'),
        ('账户名称,频道网址,预测结果,人工标注,频道概率\nA,x,yes,no,1.1\n', '无效概率'),
        ('账户名称,频道网址,预测结果,人工标注,频道概率\n"A,x,yes,no,.5', '未闭合'),
        ('账户名称,频道概率\nA,.1\n', '缺少必要列'),
    ]:
        pick_csv(page, text, 'invalid.csv')
        ready(page, expected)
        assert '上一次' in page.locator('#status').inner_text()
        assert len(data(page)['rows']) == 1


def test_build_contains_only_templates_and_requires_html_output(tmp_path):
    with pytest.raises(ValueError, match='不能覆盖'):
        build(tmp_path / 'private.csv')
    html = build(tmp_path / 'viewer.html').read_text(encoding='utf-8')
    assert '__VIEWER_SCRIPT__' not in html and '__VIEWER_BUNDLE__' not in html
    bundle = json.loads(html.split('<script id="viewer-bundle" type="application/json">')[1].split('</script>')[0])
    assert bundle['categories'] and bundle['templates']
    assert 'channel.json' not in bundle['templates']['']  # no collected snapshots embedded
    assert 'connect-src \'none\'' in html


def test_ambiguous_cover_files_remain_missing(tmp_path, viewer):
    page, _, _ = viewer
    page.locator('#category').select_option(label=TASK['name'])
    pick_csv(page, '账户名称,频道网址,预测结果,人工标注,频道概率,视频1分数,视频1链接\nA,https://example.com/a,手语频道,手语频道,.8,.9,https://example.com/v\n')
    ready(page, '已载入 1 个频道')
    folder = tmp_path / 'cache'
    folder.mkdir()
    (folder / 'channel.json').write_text(json.dumps({'url': 'https://example.com/a', 'videos': [
        {'id': 'v', 'url': 'https://example.com/v', 'title': '唯一标题', 'cover_path': 'C:/unknown/covers/duplicate.jpg'}
    ]}), encoding='utf-8')
    for sub in ('first/covers', 'second/covers'):
        target = folder / sub
        target.mkdir(parents=True)
        Image.new('RGB', (10, 10)).save(target / 'duplicate.jpg')
    page.locator('#cache-folder').set_input_files(folder)
    ready(page, '数据匹配 1/1')
    assert data(page)['rows'][0]['videos'][0]['title'] == '唯一标题'
    assert data(page)['rows'][0]['videos'][0]['cover'] is None


def test_csv_encoding_can_be_changed_without_reselecting_file(viewer):
    page, _, _ = viewer
    page.locator('#category').select_option(label=TASK['name'])
    csv_text = '账户名称,频道网址,预测结果,人工标注,频道概率\n虚构中文,https://example.com/a,手语频道,不是手语频道,.8\n'
    page.locator('#csv-file').set_input_files({'name': 'gbk.csv', 'mimeType': 'text/csv', 'buffer': csv_text.encode('gb18030')})
    ready(page, '已载入 1 个频道')
    assert 'gb18030' in page.locator('#selection-summary').inner_text()
    page.locator('#encoding').select_option('utf-8')
    ready(page, '编码无法解码')
    page.locator('#encoding').select_option('gb18030')
    ready(page, '已载入 1 个频道')
    assert data(page)['rows'][0]['name'] == '虚构中文'
