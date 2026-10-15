from task_helpers import parse_task_args
import asyncio
import csv
import json
from pathlib import Path

from PIL import Image
import pytest
from account_filter import __main__ as cli
from account_filter.collector import save_channel


def test_reclassification_creates_new_results_without_browser_or_recollecting(tmp_path, monkeypatch):
    source = tmp_path / 'previous'
    url = 'https://www.douyin.com/user/abc'
    record = {'url': url, 'name': '本地个人账号', 'true_label': '手语频道'}
    cli.write_results(source / 'results.csv', [cli.empty_row(record, '不是手语频道')])
    before = (source / 'results.csv').read_bytes()
    folder = cli.channel_folder(source, 1, url)
    save_channel({'platform': 'douyin', 'url': url, 'name': record['name'], 'bio': '练习手语',
                  'videos': [{'id': '1', 'title': '你好手语', 'url': 'https://www.douyin.com/video/1',
                              'cover_url': 'https://unavailable.douyinpic.com/1.jpg', 'cover_path': 'covers/1.jpg'}]}, folder)
    (folder / 'covers').mkdir()
    Image.new('RGB', (20, 30)).save(folder / 'covers/1.jpg')
    snapshot_before = (folder / 'channel.json').read_bytes()
    stages = []
    def forbidden(*args, **kwargs):
        pytest.fail('离线重判不能打开浏览器、采集或下载封面')
    async def model(payload, api, **kwargs):
        if 'channel' not in payload['questions']:
            stages.append('title')
            assert record['name'] not in str(payload)
            return {'answers': {'v001': {'type': 'noul', 'noul': .9}}}
        stages.append('cover')
        assert record['name'] in str(payload)
        assert sum(isinstance(p, dict) for p in payload['state']) == 1
        return {'answers': {'channel': {'type': 'choice', 'choice': 'yes', 'probabilities': {'yes': .9, 'no': .1}},
                'channel_probability': {'type': 'noul', 'noul': .9}, 'v001': {'type': 'noul', 'noul': .95},
                'best_video': {'type': 'choice', 'choice': 'v001', 'probabilities': {'v001': .9, 'none': .1}}}}
    monkeypatch.setattr(cli, 'browser_session', forbidden)
    monkeypatch.setattr(cli, 'collect', forbidden)
    monkeypatch.setattr(cli, 'download_selected_covers', forbidden)
    monkeypatch.setattr(cli, 'archive_covers', forbidden)
    monkeypatch.setattr(cli, 'call_model_api', model)
    args = parse_task_args(cli, ['batch', '--reclassify-from', str(source), '--output', str(tmp_path / 'new')])
    assert asyncio.run(cli.main(args)) == 0
    assert stages == ['title', 'cover']
    assert (source / 'results.csv').read_bytes() == before
    assert (folder / 'channel.json').read_bytes() == snapshot_before
    result_file = next((tmp_path / 'new').glob('*/results.csv'))
    rows = list(csv.DictReader(result_file.open(encoding='utf-8-sig')))
    assert rows[0]['预测结果'] == '手语频道'
    copied = next(result_file.parent.glob('intermediate/*/channel.json'))
    cached_cover = Path(json.loads(copied.read_text(encoding='utf-8'))['videos'][0]['cover_path'])
    assert cached_cover.read_bytes() == (folder / 'covers/1.jpg').read_bytes()
    assert not (copied.parent / 'covers').exists()
    # 中断续跑也保持离线，并跳过已成功的新判断。
    args = parse_task_args(cli, ['batch', '--resume', str(result_file.parent)])
    assert asyncio.run(cli.main(args)) == 0
    assert stages == ['title', 'cover']


def test_missing_snapshot_is_reported_without_platform_access(tmp_path, monkeypatch):
    source = tmp_path / 'old'
    cli.write_results(source / 'results.csv', [cli.empty_row({'url': 'https://www.douyin.com/user/abc'})])
    def forbidden(*args, **kwargs):
        pytest.fail('缺失缓存不能回退到访问网站')
    monkeypatch.setattr(cli, 'browser_session', forbidden)
    monkeypatch.setattr(cli, 'collect', forbidden)
    args = parse_task_args(cli, ['batch', '--reclassify-from', str(source), '--output', str(tmp_path / 'new')])
    assert asyncio.run(cli.main(args)) == 1
    rows = list(csv.DictReader(next((tmp_path / 'new').glob('*/results.csv')).open(encoding='utf-8-sig')))
    assert '缓存缺失' in rows[0]['预测结果']


def test_from_formal_cache_is_offline_and_preserves_manual_labels(tmp_path, monkeypatch):
    from account_filter import cache
    url = 'https://www.douyin.com/user/abc'
    folder = cache.channel_dir(url)
    save_channel({'platform': 'douyin', 'url': url, 'name': '无作品', 'videos': [], 'no_posts': True}, folder)
    def forbidden(*args, **kwargs):
        pytest.fail('读取正式缓存不能访问平台或调用模型')
    monkeypatch.setattr(cli, 'browser_session', forbidden)
    monkeypatch.setattr(cli, 'call_model_api', forbidden)
    source = tmp_path / 'input.csv'
    source.write_text(f'主页网址,人工标注\n{url},不是手语频道\n', encoding='utf-8-sig')
    args = parse_task_args(cli, ['batch', '--from-cache', '--input-csv', str(source), '--output', str(tmp_path / 'new')])
    assert asyncio.run(cli.main(args)) == 0
    rows = list(csv.DictReader(next((tmp_path / 'new').glob('*/results.csv')).open(encoding='utf-8-sig')))
    assert rows[0]['人工标注'] == rows[0]['预测结果'] == '不是手语频道'
