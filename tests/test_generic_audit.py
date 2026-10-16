import csv
import hashlib
import json

from account_filter.category import load_category, CONFIGS
from account_filter.report import generate
from test_viewer import browser, viewer, ready, data, report_click


def audit_files(root, source, category):
    folder = root / 'cover-audit/text-check'
    folder.mkdir(parents=True)
    (folder.parent / 'latest.json').write_text(json.dumps({
        'path': 'cover-audit/text-check/audit-results.json'}), encoding='utf-8')
    (root / 'category.json').write_text(json.dumps(category), encoding='utf-8')
    overall = {'choice': 'no', 'label': '不符合', 'probabilities': {'yes': .1, 'no': .9, 'unclear': 0}}
    audit = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
             'title': 'Custom cover check', 'criteria': '<img src=x onerror=alert(1)> Readable captions',
             'population': 'Selected examples', 'model': 'mock', 'prompt_version': 'text-v1',
             'generated': 'test', 'csv': 'cover-audit/text-check/cover-audit.csv',
             'rows': [{'id': 1, 'url': 'https://example.org/a', 'name': 'Example',
                       'manual': category['positive_label'], 'prediction': category['negative_label'],
                       'status': '不符合', 'overall': overall, 'any_front': overall, 'videos': []}]}
    path = folder / 'audit-results.json'
    path.write_text(json.dumps(audit), encoding='utf-8')
    (folder / 'cover-audit.csv').write_text('result\nno\n', encoding='utf-8')
    return path, audit


def test_generic_cover_audit_uses_file_metadata_without_domain_heuristics(tmp_path, viewer):
    page, _, _ = viewer
    category = load_category(CONFIGS / 'categories/fitness.example.toml')
    source = tmp_path / 'results.csv'
    with source.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['账户名称', '频道网址', '预测结果', '人工标注', '频道概率'])
        writer.writerow(['Example', 'https://example.org/a', category['negative_label'], category['positive_label'], .1])
    _, audit = audit_files(tmp_path, source, category)
    page.locator('#csv-file').set_input_files(source)
    ready(page, '已载入 1 个频道')
    page.locator('#cache-folder').set_input_files(tmp_path)
    ready(page, '已载入 1 个频道')
    frame = page.frame_locator('#report')
    assert frame.locator('#front-title').inner_text() == audit['title']
    assert frame.locator('#front-criteria').inner_text() == audit['criteria']
    assert frame.locator('#front-criteria img').count() == 0
    assert 'Selected examples' in frame.locator('#front-meta').inner_text()
    assert frame.locator('#evidence').count() == 0
    assert len(data(page)['cover_audit']['rows']) == 1
    report_click(page, '#front-table [data-front-case]')
    assert frame.locator('#detail-content .front-detail').count() == 1


def test_static_report_matches_audit_to_source_csv(tmp_path):
    category = load_category(CONFIGS / 'categories/fitness.example.toml')
    source = tmp_path / 'results.csv'
    source.write_text(f'账户名称,频道网址,预测结果,人工标注,频道概率\nExample,https://example.org/a,{category["negative_label"]},{category["positive_label"]},.1\n', encoding='utf-8')
    path, audit = audit_files(tmp_path, source, category)
    html, _ = generate(source)
    def payload():
        return json.loads(html.read_text(encoding='utf-8').split('<script id="report-data" type="application/json">')[1].split('</script>')[0])
    assert payload()['cover_audit']['criteria'] == audit['criteria']
    audit['source_sha256'] = 'different-source'
    path.write_text(json.dumps(audit), encoding='utf-8')
    generate(source)
    assert 'cover_audit' not in payload()
