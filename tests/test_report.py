import csv
import json
from pathlib import Path

import pytest

from account_filter.report import generate, load_rows
from task_helpers import summarize, TASK


def test_report_can_reference_formal_cache_but_not_other_external_files(tmp_path, monkeypatch):
    from account_filter import report
    root = tmp_path / 'experiment'
    root.mkdir()
    shared = tmp_path / 'data' / 'channels'
    shared.mkdir(parents=True)
    monkeypatch.setattr(report, 'SHARED_CACHE', shared)
    image = shared / 'cover.jpg'
    image.write_bytes(b'local')
    relative = report.relative_file(image, root)
    assert relative and (root / relative).resolve() == image.resolve()
    other = tmp_path / 'unrelated.jpg'
    other.write_bytes(b'other')
    assert report.relative_file(other, root) is None


def fixture_csv(tmp_path):
    path = tmp_path / 'results.csv'
    (tmp_path / 'category.json').write_text(json.dumps(TASK), encoding='utf-8')
    headings = ['账户名称', '频道网址', '预测结果', '频道概率', '人工标注', '视频1分数', '视频1链接']
    rows = [
        ['正常', 'https://www.douyin.com/user/a', '手语频道', '.99', '手语频道', '.98', 'https://www.douyin.com/video/1'],
        ['不符</script><img src=x onerror=alert(1)>', 'https://www.douyin.com/user/b', '手语频道', '.98', '不是手语频道', '.97', ''],
        ['未投稿', 'https://www.douyin.com/user/c', '不是手语频道', '', '不是手语频道', '', ''],
        ['人工疑难', 'https://www.douyin.com/user/d', '手语频道', '.9', '疑难', '.8', ''],
        ['未完成', 'https://www.douyin.com/user/e', '失败：超时', '', '手语频道', '', ''],
    ]
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headings)
        writer.writerows(rows)
    return path


def test_missing_scores_and_unavailable_results_are_not_zeros_or_mismatches(tmp_path):
    path = fixture_csv(tmp_path)
    rows, ranks = load_rows(path)
    summary = summarize(rows)
    assert ranks == [1]
    assert summary['total'] == 5 and summary['comparable'] == 4
    assert summary['mismatch'] == 2 and summary['high_confidence_mismatch'] == 1
    assert summary['missing_p'] == 2
    assert summary['precision'] == .5  # 人工“疑难”不混入明确正负类的精确率分母。
    assert summary['recall'] == 1  # 失败行未产生预测，不纳入可对照分母。
    assert rows[2]['p'] is None and rows[2]['max'] is None
    assert not rows[4]['wrong'] and not rows[4]['comparable']


def test_html_embeds_data_safely_and_does_not_modify_csv(tmp_path):
    path = fixture_csv(tmp_path)
    original = path.read_bytes()
    html, _ = generate(path)
    text = html.read_text(encoding='utf-8')
    assert path.read_bytes() == original
    data_text = text.split('<script id="report-data" type="application/json">')[1].split('</script>')[0]
    data = json.loads(data_text)
    assert data['rows'][1]['name'].startswith('不符</script>')
    assert '</script><img' not in data_text
    assert '__REPORT_DATA__' not in text
    with pytest.raises(ValueError, match='不能覆盖'):
        generate(path, path)


def test_cover_links_follow_channel_url_after_deleted_csv_rows(tmp_path):
    path = fixture_csv(tmp_path)
    folder = tmp_path / 'intermediate' / '999_douyin_a'
    (folder / 'covers').mkdir(parents=True)
    (folder / 'covers' / '1.jpg').write_bytes(b'local')
    (folder / 'channel.json').write_text(json.dumps({'url': 'https://www.douyin.com/user/a', 'bio': '测试简介',
        'videos': [{'id': '1', 'url': 'https://www.douyin.com/video/1', 'title': '测试标题'}]}), encoding='utf-8')
    destination = tmp_path / 'report' / 'analysis.html'
    html, _ = generate(path, destination)
    text = html.read_text(encoding='utf-8')
    data = json.loads(text.split('<script id="report-data" type="application/json">')[1].split('</script>')[0])
    r = data['rows'][0]
    assert r['bio'] == '测试简介' and r['videos'][0]['title'] == '测试标题'
    assert (destination.parent / r['videos'][0]['cover']).is_file()
