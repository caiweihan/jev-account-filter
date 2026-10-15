"""Integrated reference evaluation, deterministic clustering, and single-page layout."""
import json

import pytest

from test_viewer import browser, viewer, data, pick_csv, ready, sized
from test_second_review import csv_text, load_review


def test_clustering_uses_prediction_and_five_scores_without_label_leakage(viewer):
    page, _, _ = viewer
    rows = []
    patterns = [('A', '手语频道', [.95, .9, .85, .8, .75]),
                ('B', '不是手语频道', [.05, .04, .03, .02, .01]),
                ('C', '手语频道', [.5] * 5), ('D', '不是手语频道', [.5] * 5)]
    for name, prediction, scores in patterns:
        for copy in range(2 if name in 'AB' else 1):
            rows.append([name+str(copy), f'https://example.com/{name}/{copy}', prediction, prediction, '.5', *scores])
    rows += [['missing', 'https://example.com/missing', '手语频道', '手语频道', '.5', 0, 0, 0, 0, ''],
             ['failed', 'https://example.com/fail', '失败：测试', '手语频道', '', 0, 0, 0, 0, 0]]
    headers = ['账户名称', '频道网址', '预测结果', '人工标注', '频道概率', *[f'视频{i}分数' for i in range(1, 6)]]
    pick_csv(page, csv_text(headers, rows))
    ready(page, '已载入 8 个频道')
    frame = page.frame_locator('#report')
    result = frame.locator('body').evaluate('()=>({n:clusterResult.eligible.length,k:clusterResult.groups.length,missing:clusterResult.missing,invalid:clusterResult.invalid,ids:[...clusterResult.byId],variance:clusterResult.variance,sse:clusterResult.sse})')
    assert result['n'] == 6 and result['k'] == 4
    assert result['missing'] == 1 and result['invalid'] == 1
    mapping = dict(result['ids'])
    assert mapping[1] == mapping[2] and mapping[3] == mapping[4]
    assert mapping[5] != mapping[6]  # identical scores, different predictions
    assert result['sse'] == pytest.approx(0)
    assert 0 <= result['variance'][1] <= result['variance'][0] <= 1
    assert sum(result['variance']) <= 1 + 1e-8
    independent = frame.locator('body').evaluate("()=>[...clusterAccounts(D.rows.map(r=>({...r,manual:'changed',second_review:{status:'valid',label:'changed'}})),5).byId]")
    assert independent == result['ids']
    frame.locator('#cluster-profiles [data-cluster]').first.click()
    assert frame.locator('#case-table tbody tr').count() == 2
    frame.locator('#clear-cluster').click()
    assert frame.locator('#case-table tbody tr').count() == 8
    frame.locator('#cluster-k').select_option('2')
    assert frame.locator('body').evaluate('()=>clusterResult.groups.length') == 2
    assert data(page)['rows'][0]['prediction'] == '手语频道'


def test_integrated_accuracy_and_error_filters_share_reference_cohort(viewer):
    page, _, _ = viewer
    headers = ['账户名称', '频道网址', '预测结果', '人工标注', '频道概率']
    pick_csv(page, csv_text(headers, [
        ['A', 'https://example.com/a', '手语频道', '不是手语频道', '.9'],
        ['B', 'https://example.com/b', '不是手语频道', '手语频道', '.1'],
        ['C', 'https://example.com/c', '不是手语频道', '疑难', '.2'],
        ['D', 'https://example.com/d', '手语频道', '手语频道', '.8'],
        ['E', 'https://example.com/e', '手语频道', '不是手语频道', '.8'],
    ]))
    ready(page, '已载入 5 个频道')
    original = json.dumps(data(page), ensure_ascii=False)
    load_review(page, ['主页网址', '审核结果'], [[f'https://example.com/{key}', '1'] for key in 'abcd'])
    frame = page.frame_locator('#report')
    assert frame.locator('#second-review').count() == 0
    assert frame.locator('#comparison-basis').input_value() == 'reviewed'
    assert frame.locator('#eval-summary .value').all_text_contents() == ['4', '50.00%', '50.00%', '+0.00 pp']
    assert '不能外推' in frame.locator('#evaluation-note').inner_text()
    assert frame.locator('#distribution-stats tbody tr').first.locator('td').nth(1).inner_text() == '2 / 0'
    frame.locator('#review-filter').select_option('human-error')
    assert frame.locator('#case-table tbody tr').count() == 2
    frame.locator('#review-filter').select_option('model-error')
    assert frame.locator('#case-table tbody tr').count() == 2
    frame.locator('#comparison-basis').select_option('combined')
    assert frame.locator('#eval-summary .value').all_text_contents() == ['5', '60.00%', '40.00%', '-20.00 pp']
    assert '条件估计' in frame.locator('#evaluation-note').inner_text()
    frame.locator('#comparison-basis').select_option('original')
    assert frame.locator('#eval-summary .value').all_text_contents() == ['5', '—', '20.00%', '—']
    assert data(page)['rows'][0]['manual'] == json.loads(original)['rows'][0]['manual']
    assert frame.locator('#error-profile tbody tr').count() == 3


def test_file_controls_scroll_away_and_settings_are_optional(tmp_path, viewer):
    page, _, _ = viewer
    page.locator('#advanced-settings').evaluate('el=>el.open=false')
    text = '账户名称,频道网址,预测结果,人工标注,频道概率\n自动识别,https://example.com/a,手语频道,不是手语频道,.8\n'
    page.locator('#csv-file').set_input_files({'name': 'gbk.csv', 'mimeType': 'text/csv', 'buffer': text.encode('gb18030')})
    ready(page, '已载入 1 个频道')
    assert not page.locator('#advanced-settings').evaluate('el=>el.open')
    assert 'gb18030' in page.locator('#selection-summary').inner_text()
    assert '手语' in page.locator('#selection-summary').inner_text()
    assert page.locator('#csv-selected').inner_text() == 'gbk.csv'
    folder = tmp_path / 'evidence-cache'
    folder.mkdir()
    (folder / 'channel.json').write_text(json.dumps({'url': 'https://example.com/a', 'videos': []}), encoding='utf-8')
    page.locator('#cache-folder').set_input_files(folder)
    ready(page, '缓存匹配 1/1')
    assert page.locator('#folder-selected').inner_text() == 'evidence-cache'
    assert page.locator('#cache-folder').input_value() == ''
    assert page.locator('#cache-folder').is_hidden()
    assert page.locator('#choose-folder').is_visible()
    sized(page)
    page.evaluate('()=>window.scrollTo(0,1000)')
    assert page.locator('header').evaluate('el=>el.getBoundingClientRect().bottom') < 0
    assert page.frame_locator('#report').locator('html').evaluate('()=>window.scrollY') <= 2
    page.evaluate('()=>window.scrollTo(0,0)')
    pick_csv(page, '账户名称,频道网址,预测结果,人工标注,频道概率\n健身样例,https://example.com/f,健身账户,不是健身账户,.8\n')
    ready(page, '已载入 1 个频道')
    assert data(page)['category']['id'] == 'fitness'


def test_identical_features_form_one_cluster_and_missing_values_are_excluded(viewer):
    page, _, _ = viewer
    headers = ['账户名称', '频道网址', '预测结果', '人工标注', '频道概率', *[f'视频{i}分数' for i in range(1, 6)]]
    rows = [[str(i), f'https://example.com/{i}', '手语频道', '手语频道', '.8', *([0] * 5)] for i in range(3)]
    pick_csv(page, csv_text(headers, rows))
    ready(page, '已载入 3 个频道')
    frame = page.frame_locator('#report')
    assert frame.locator('body').evaluate('()=>clusterResult.groups.length') == 1
    assert frame.locator('body').evaluate('()=>clusterResult.variance') == [0, 0]
    assert frame.locator('body').evaluate('()=>clusterResult.points.every(p=>p.x===0&&p.y===0)')
