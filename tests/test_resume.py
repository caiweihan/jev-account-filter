from task_helpers import API_CONFIG
from task_helpers import TASK
from task_helpers import parse_task_args
import argparse
import asyncio
import csv
import json

import pytest

from account_filter import __main__ as cli
from account_filter import collector


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def test_disagreement_only_for_comparable_predictions(tmp_path):
    rows = [cli.empty_row({'url': str(i), 'true_label': label}, prediction) for i, (label, prediction) in
            enumerate([('手语频道', '不是手语频道'), ('疑难', '疑难'), ('', '手语频道'),
                       ('手语频道', '失败：超时'), ('手语频道', cli.PRIVATE_RESULT)])]
    path = tmp_path / 'results.csv'
    cli.write_results(path, rows, category=TASK)
    assert [r['预测与标注不符'] for r in read_csv(path)] == ['预测与标注不符', '', '', '', '']


def test_resume_preserves_success_and_retries_failed_in_same_directory(tmp_path, monkeypatch):
    records = [{'url': 'https://www.douyin.com/user/a', 'name': '甲', 'true_label': '手语频道'},
               {'url': 'https://www.douyin.com/user/b', 'name': '乙', 'true_label': '不是手语频道'}]
    previous = [cli.empty_row(records[0], '手语频道'), cli.empty_row(records[1], '失败：API超时')]
    previous[0]['频道概率'] = .99
    cli.write_results(tmp_path / 'results.csv', previous)
    first = cli.channel_folder(tmp_path, 1, records[0]['url'])
    collector.save_channel({'platform': 'douyin', 'url': records[0]['url'], 'name': '甲', 'videos': [], 'no_posts': True}, first)
    calls = []
    async def process(args):
        calls.append(args)
        assert args.reuse_cache
        return {'status': 'success', 'row': cli.empty_row(records[1], '不是手语频道')}
    async def archive(*args, **kwargs):
        return {'missing': []}
    monkeypatch.setattr(cli, 'process_channel', process)
    monkeypatch.setattr(cli, 'archive_covers', archive)
    args = parse_task_args(cli, ['batch', '--resume', str(tmp_path)])
    assert asyncio.run(cli.run_batch_in_session(args, cli.batch_inputs(args), object())) == 0
    assert len(calls) == 1 and calls[0].url == records[1]['url']
    assert calls[0].output == cli.channel_folder(tmp_path, 2, records[1]['url'])
    rows = read_csv(tmp_path / 'results.csv')
    assert rows[0]['频道概率'] == '0.99' and rows[1]['预测结果'] == '不是手语频道'
    assert not list(tmp_path.glob('20*'))
    with pytest.raises(ValueError, match='顺序或数量'):
        cli.prepare_batch(args, records[::-1])


def test_resume_skips_complete_cover_cache_without_archiving(tmp_path, monkeypatch):
    records = [{'url': f'https://www.douyin.com/user/{name}', 'name': name, 'true_label': ''}
               for name in ('done', 'retry')]
    cli.write_results(tmp_path / 'results.csv', [cli.empty_row(records[0], '手语频道'),
                                               cli.empty_row(records[1], '失败：API超时')])
    folder = cli.channel_folder(tmp_path, 1, records[0]['url'])
    collector.save_channel({'url': records[0]['url'], 'name': 'done', 'videos': [{'id': '1'}]}, folder)
    (folder / 'covers').mkdir()
    (folder / 'covers' / '1.jpg').write_bytes(b'cached')
    async def archive(*args, **kwargs):
        pytest.fail('完整封面缓存不应重新归档或显示下载进度')
    async def process(args):
        assert args.url == records[1]['url']
        return {'status': 'success', 'row': cli.empty_row(records[1], '不是手语频道')}
    monkeypatch.setattr(cli, 'archive_covers', archive)
    monkeypatch.setattr(cli, 'process_channel', process)
    args = parse_task_args(cli, ['batch', '--resume', str(tmp_path)])
    assert asyncio.run(cli.run_batch_in_session(args, records, object())) == 0
    assert read_csv(tmp_path / 'results.csv')[0]['预测结果'] == '手语频道'


def test_backfill_only_never_collects_or_calls_model(tmp_path, monkeypatch):
    record = {'url': 'https://www.douyin.com/user/a', 'name': '甲', 'true_label': '疑难'}
    cli.write_results(tmp_path / 'results.csv', [cli.empty_row(record, '失败：API超时')])
    folder = cli.channel_folder(tmp_path, 1, record['url'])
    collector.save_channel({'url': record['url'], 'name': '甲', 'videos': [{'id': '1'}]}, folder)
    async def forbidden(*args, **kwargs):
        pytest.fail('补缓存不能调用推理或采集')
    async def archive(channel, root, page, on_status):
        assert root == folder
        return {'missing': []}
    monkeypatch.setattr(cli, 'process_channel', forbidden)
    monkeypatch.setattr(cli, 'call_model_api', forbidden)
    monkeypatch.setattr(cli, 'archive_covers', archive)
    args = parse_task_args(cli, ['batch', '--resume', str(tmp_path), '--backfill-only'])
    assert asyncio.run(cli.run_batch_in_session(args, [record], object())) == 0
    assert read_csv(tmp_path / 'results.csv')[0]['预测结果'] == '失败：API超时'


def test_resume_risk_stop_preserves_later_completed_rows(tmp_path, monkeypatch):
    records = [{'url': f'https://www.douyin.com/user/{name}', 'name': name, 'true_label': ''}
               for name in ('a', 'b', 'c', 'd')]
    predictions = ['失败：超时', '手语频道', cli.PRIVATE_RESULT, '待处理']
    cli.write_results(tmp_path / 'results.csv', [cli.empty_row(r, p) for r, p in zip(records, predictions)])
    async def risk(args):
        raise cli.RiskControlError('风控')
    monkeypatch.setattr(cli, 'process_channel', risk)
    args = parse_task_args(cli, ['batch', '--resume', str(tmp_path)])
    assert asyncio.run(cli.run_batch_in_session(args, records, object())) == 1
    rows = read_csv(tmp_path / 'results.csv')
    assert rows[1]['预测结果'] == '手语频道'
    assert rows[2]['预测结果'] == cli.PRIVATE_RESULT
    assert rows[3]['预测结果'] == '未完成（抖音风控）'


def test_matching_inference_is_reused_and_changed_evidence_is_not(tmp_path, monkeypatch):
    calls = []
    async def model(payload, api, **kwargs):
        calls.append(payload)
        return {'answers': {'v001': {'type': 'noul', 'noul': .9}}}
    monkeypatch.setattr(cli, 'call_model_api', model)
    args = argparse.Namespace(output=tmp_path, api='decisions', reuse_cache=True, endpoint=API_CONFIG['endpoint'], api_key_env=API_CONFIG['api_key_env'])
    payload = {'model': 'test', 'state': ['标题'], 'questions': {'v001': {}}}
    preview = {'model': 'test', 'api': 'decisions', 'state_text': ['标题'], 'questions': payload['questions']}
    async def check():
        original = await cli.cached_model_call(args, payload, preview, 'title')
        assert await cli.cached_model_call(args, payload, {**preview, 'videos': [{'cover_path': 'new-cache.jpg'}]}, 'title') == original
        changed = {**payload, 'state': ['新标题']}
        await cli.cached_model_call(args, changed, {**preview, 'state_text': ['新标题']}, 'title')
    asyncio.run(check())
    assert len(calls) == 2


@pytest.mark.parametrize('private', [False, True])
def test_no_posts_and_private_cached_profiles_do_not_use_api(tmp_path, monkeypatch, private):
    url = 'https://www.douyin.com/user/a'
    collector.save_channel({'platform': 'douyin', 'url': url, 'name': '甲', 'videos': [],
                            'no_posts': not private, 'is_private': private}, tmp_path)
    async def forbidden(*args, **kwargs):
        pytest.fail('明确空频道/私密账号不应调用采集或模型')
    monkeypatch.setattr(cli, 'collect', forbidden)
    monkeypatch.setattr(cli, 'call_model_api', forbidden)
    args = parse_task_args(cli, ['run', url, '--output', str(tmp_path)])
    args.page, args.reuse_cache = object(), True
    row = asyncio.run(cli.process_channel(args))['row']
    assert row['预测结果'] == (cli.PRIVATE_RESULT if private else '不是手语频道')
    assert row['频道概率'] == ''


def test_archive_downloads_only_missing_and_persists_all_paths(tmp_path, monkeypatch):
    folder = tmp_path / 'covers'
    folder.mkdir()
    (folder / '1.jpg').write_bytes(b'existing')
    channel = {'name': '甲', 'videos': [{'id': '1', 'cover_url': 'old'}, {'id': '2', 'cover_url': 'new'}]}
    calls = []
    async def download(context, url, destination):
        calls.append(url)
        destination.write_bytes(b'new')
    monkeypatch.setattr(collector, 'download_cover', download)
    phases = []
    status = asyncio.run(collector.archive_covers(channel, tmp_path, argparse.Namespace(context=object()), phases.append))
    assert calls == ['new'] and status['complete']
    assert phases == ['缓存封面 2/2']
    saved = json.loads((tmp_path / 'channel.json').read_text(encoding='utf-8'))
    assert all((tmp_path / v['cover_path']).is_file() for v in saved['videos'])


def test_partial_failed_snapshot_is_not_reused(tmp_path):
    collector.save_channel({'url': 'https://www.douyin.com/user/a', 'name': '甲',
                            'collection_state': 'failed', 'videos': [{'id': '1'}]}, tmp_path)
    assert collector.saved_channel(tmp_path, 'https://www.douyin.com/user/a') is None


def test_csv_row_removal_reuses_original_folder_by_channel_url(tmp_path):
    url = 'https://www.douyin.com/user/retained'
    original = cli.channel_folder(tmp_path, 9, url)
    collector.save_channel({'url': url, 'name': '缓存', 'videos': [{'id': '1'}]}, original)
    assert cli.channel_folder(tmp_path, 8, url + '?source=search') == original
    assert cli.channel_folder(tmp_path, 8, 'https://www.douyin.com/user/new') != original


def test_failed_snapshot_folder_is_reused_after_csv_row_removal(tmp_path):
    url = 'https://www.douyin.com/user/failed'
    original = cli.channel_folder(tmp_path, 12, url)
    original.mkdir(parents=True)
    cli.write_json(original / 'collection-status.json', {'channel_url': url, 'status': 'collection_failed'})
    assert cli.channel_folder(tmp_path, 10, url) == original


def test_title_api_error_still_archives_the_collected_page(tmp_path, monkeypatch):
    record = {'url': 'https://www.douyin.com/user/a', 'name': '甲', 'true_label': '手语频道'}
    archived = []
    async def collect(url, output, browser_dir, **kwargs):
        channel = {'platform': 'douyin', 'url': url, 'name': '甲', 'bio': '',
                   'videos': [{'id': '1', 'title': '标题', 'url': 'https://www.douyin.com/video/1'}]}
        collector.save_channel(channel, output)
        return channel
    async def model(*args, **kwargs):
        raise RuntimeError('API失败')
    async def archive(channel, root, page, on_status):
        archived.append(root)
        return {'missing': []}
    monkeypatch.setattr(cli, 'collect', collect)
    monkeypatch.setattr(cli, 'call_model_api', model)
    monkeypatch.setattr(cli, 'archive_covers', archive)
    args = parse_task_args(cli, ['batch', '--output', str(tmp_path)])
    assert asyncio.run(cli.run_batch_in_session(args, [record], object())) == 1
    assert len(archived) == 1
    assert read_csv(next(tmp_path.glob('*/results.csv')))[0]['预测结果'] == '失败：RuntimeError: API失败'
