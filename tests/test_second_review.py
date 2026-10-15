"""Independent reannotation statistics and safe record matching in the local viewer."""
import csv
import io

from test_viewer import browser, viewer, data, pick_csv, ready
from task_helpers import TASK


def csv_text(headers, rows):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(headers)
    writer.writerows(rows)
    return stream.getvalue()


def load_review(page, headers, rows):
    text = csv_text(headers, rows)
    page.locator('#review-file').set_input_files({
        'name': 'review.csv', 'mimeType': 'text/csv', 'buffer': text.encode('utf-8-sig')})
    ready(page, '二次核验匹配')
    page.frame_locator('#report').locator('#eval-summary .value').first.wait_for()


def test_dataset_composition_counts_failures_blanks_duplicates_and_zero_scores(viewer):
    page, _, _ = viewer
    page.locator('#category').select_option(label=TASK['name'])
    text = csv_text(['账户名称', '频道网址', '预测结果', '人工标注', '频道概率', '视频1分数', '视频1链接'], [
        ['A', 'https://example.com/a', '手语频道', '手语频道', '.8', '0', ''],
        ['B', 'https://example.com/a?source=search', '不是手语频道', '不是手语频道', '', '', ''],
        ['C', 'https://example.com/c', '失败：测试', '疑难', '', '', ''],
        ['D', '', '', '', '', '', ''],
    ])
    pick_csv(page, text)
    ready(page, '已载入 4 个频道')
    frame = page.frame_locator('#report')
    assert frame.locator('#dataset-kpis b').all_text_contents() == ['4', '2', '2', '2']
    assert '未标注' in frame.locator('#manual-composition').inner_text()
    assert '无预测' in frame.locator('#prediction-composition').inner_text()
    assert '其它标签 / 非类别结果' in frame.locator('#prediction-composition').inner_text()
    assert frame.locator('#candidate-composition').count() == 0
    assert '缺少完整五条分数 2' in frame.locator('#cluster-note').inner_text()
    for chart in ('manual-composition', 'prediction-composition'):
        negative = frame.locator(f'#{chart} .composition-line').filter(has_text='不是手语频道')
        assert negative.locator('.dot').evaluate("e=>getComputedStyle(e).backgroundColor") == 'rgb(23, 136, 120)'
    assert frame.locator('#second-review').count() == 0
    frame.locator('#manual-composition button').first.click()
    assert frame.locator('#case-table tbody tr').count() == 1
    assert frame.locator('#dataset-kpis b').first.inner_text() == '4'


def test_reannotation_preserves_original_and_uses_fixed_denominators(viewer):
    page, _, _ = viewer
    page.locator('#category').select_option(label=TASK['name'])
    headers = ['账户名称', '频道网址', '预测结果', '人工标注', '频道概率', '账户id']
    pick_csv(page, csv_text(headers, [
        ['A', 'https://example.com/a', '手语频道', '不是手语频道', '.9', '001'],
        ['B', 'https://example.com/b', '不是手语频道', '手语频道', '.1', '002'],
        ['C', 'https://example.com/c', '不是手语频道', '疑难', '.2', '003'],
        ['D', 'https://example.com/d', '手语频道', '手语频道', '.8', '004'],
        ['E', 'https://example.com/e', '手语频道', '不是手语频道', '.8', '005'],
    ]))
    ready(page, '已载入 5 个频道')
    original = data(page)['summary']
    load_review(page, ['账户id', '主页网址', '审核结果'], [
        ['001', 'https://example.com/a?source=search', '1'],
        ['002', 'https://example.com/b', '1'],
        ['003', 'https://example.com/c', '1'],
        ['004', 'https://example.com/d', '1'],
    ])
    frame = page.frame_locator('#report')
    stats = frame.locator('body').evaluate('()=>secondStats()')
    assert stats['counts'] == {'model': 1, 'original': 1, 'both': 1, 'neither': 1}
    assert stats['fixed_total'] == 4
    assert stats['fixed_original_matches'] == 1
    assert stats['fixed_updated_matches'] == 2
    assert stats['updated_total'] == 5 and stats['updated_matches'] == 2
    assert data(page)['summary'] == original
    assert data(page)['rows'][0]['manual'] == '不是手语频道'
    assert data(page)['rows'][0]['second_review']['label'] == '手语频道'
    frame.locator('#review-filter').select_option('both-error')
    assert frame.locator('#case-table tbody tr').count() == 1
    frame.locator('#case-table [data-case]').click()
    assert '二次人工核验' in frame.locator('#detail-content .verify-detail').inner_text()
    frame.locator('#close-detail').click()
    frame.locator('#comparison-basis').select_option('original')
    frame.locator('#review-filter').select_option('pending-review')
    assert frame.locator('#case-table tbody tr').count() == 1
    frame.locator('#metric').select_option('mean')
    assert '0 /' in frame.locator('#distribution-stats').inner_text()
    page.locator('#clear-review').click()
    ready(page, '已载入 5 个频道')
    assert frame.locator('#second-review').count() == 0
    assert data(page)['summary'] == original


def test_conflicting_unknown_unmatched_and_ambiguous_reviews_are_not_silently_used(viewer):
    page, _, _ = viewer
    page.locator('#category').select_option(label=TASK['name'])
    pick_csv(page, csv_text(['账户名称', '频道网址', '预测结果', '人工标注', '频道概率', '账户id'], [
        ['A', 'https://example.com/a', '手语频道', '不是手语频道', '.9', '001'],
        ['B', 'https://example.com/b', '手语频道', '不是手语频道', '.8', '002'],
        ['C', 'https://example.com/c', '手语频道', '不是手语频道', '.8', '003'],
        ['D', 'https://example.com/d', '手语频道', '不是手语频道', '.8', '004'],
        ['D duplicate', 'https://example.com/d', '手语频道', '不是手语频道', '.8', '004'],
    ]))
    ready(page, '已载入 5 个频道')
    load_review(page, ['账户id', '主页网址', '审核结果'], [
        ['001', 'https://example.com/a', '1'], ['001', '', '手语频道'],
        ['002', 'https://example.com/b', '1'], ['002', 'https://example.com/b', '-1'],
        ['003', 'https://example.com/c', 'unknown'],
        ['004', 'https://example.com/d', '-1'],
        ['999', 'https://example.com/missing', '1'],
        ['wrong-id', 'https://example.com/a', '-1'],
    ])
    payload = data(page)
    summary = payload['second_review']
    assert summary['total'] == 8 and summary['matched'] == 1 and summary['duplicates'] == 1
    assert summary['conflicts'] == 1 and summary['unknown'] == 1
    assert summary['matched'] + summary['duplicates'] + len(summary['issues']) == summary['total']
    assert payload['rows'][1]['second_review']['status'] == 'conflict'
    assert payload['rows'][2]['second_review']['status'] == 'unknown'
    assert 'second_review' not in payload['rows'][3]
    frame = page.frame_locator('#report')
    assert frame.locator('#review-diagnostics').is_visible()
    frame.locator('#review-diagnostics').evaluate('el=>el.open=true')
    assert frame.locator('#second-issues').is_visible()
    assert frame.locator('body').evaluate('()=>secondStats().paired') == 1


def test_review_switching_csv_rematches_instead_of_reusing_row_numbers(viewer):
    page, _, _ = viewer
    page.locator('#category').select_option(label=TASK['name'])
    headers = ['账户名称', '频道网址', '预测结果', '人工标注', '频道概率']
    pick_csv(page, csv_text(headers, [['A', 'https://example.com/a', '手语频道', '不是手语频道', '.9']]))
    ready(page, '已载入 1 个频道')
    load_review(page, ['主页网址', '审核结果'], [['https://example.com/a', '1']])
    pick_csv(page, csv_text(headers, [['Other', 'https://example.com/b', '手语频道', '不是手语频道', '.9']]), 'new.csv')
    ready(page, '已载入 1 个频道')
    assert data(page)['second_review']['matched'] == 0
    assert 'second_review' not in data(page)['rows'][0]
