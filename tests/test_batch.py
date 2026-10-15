from task_helpers import TASK
from task_helpers import parse_task_args
import asyncio
import csv
import json
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager

import pytest

from account_filter import __main__ as cli


@pytest.fixture(autouse=True)
def local_browser(monkeypatch):
    sessions = []
    @asynccontextmanager
    async def session(*args, **kwargs):
        page = object()
        sessions.append(page)
        yield page
    monkeypatch.setattr(cli, 'browser_session', session)
    return sessions


def read_results(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


@pytest.mark.parametrize('command', ['run', 'collect', 'login', 'analyze'])
def test_repeated_single_runs_preserve_previous_outputs(tmp_path, monkeypatch, command):
    async def process(args):
        cli.write_json(args.output / 'request-preview.json', {'run': len(list(tmp_path.iterdir()))})
    monkeypatch.setattr(cli, 'process_channel', process)
    source = str(tmp_path / 'channel.json') if command == 'analyze' else 'https://www.kuaishou.com/profile/first'
    outputs = []
    for _ in range(2):
        args = parse_task_args(cli, [command, source, '--output', str(tmp_path)])
        assert asyncio.run(cli.main(args)) == 0
        outputs.append(args.output)
    assert outputs[0] != outputs[1]
    for index, folder in enumerate(outputs, 1):
        datetime.strptime(folder.name, '%Y%m%d-%H%M%S-%f')
        assert json.loads((folder / 'request-preview.json').read_text(encoding='utf-8')) == {'run': index}


def test_same_timestamp_keeps_existing_directory(tmp_path):
    started = datetime(2026, 10, 12, 14, 30, 0, tzinfo=timezone(timedelta(hours=8)))
    first = cli.create_run_dir(tmp_path, started)
    (first / 'result.json').write_text('previous result', encoding='utf-8')
    second = cli.create_run_dir(tmp_path, started)
    assert first.name == '20261012-143000-000000'
    assert second.name == first.name + '-1'
    assert (first / 'result.json').read_text(encoding='utf-8') == 'previous result'


def test_file_input_bom_comments_and_channel_dedup(tmp_path):
    path = tmp_path / 'channels.txt'
    path.write_text('# 注释\n\nhttps://www.kuaishou.com/profile/first?source=SEARCH\nhttps://www.kuaishou.com/profile/second\n', encoding='utf-8-sig')
    args = parse_task_args(cli, ['batch', 'https://www.kuaishou.com/profile/first', '--urls-file', str(path)])
    assert cli.batch_urls(args) == ['https://www.kuaishou.com/profile/first', 'https://www.kuaishou.com/profile/second']


def test_empty_input_and_invalid_global_setting(tmp_path, monkeypatch):
    args = parse_task_args(cli, ['batch', '--output', str(tmp_path)])
    with pytest.raises(ValueError, match='至少一个'):
        asyncio.run(cli.main(args))
    args = parse_task_args(cli, ['batch', 'https://www.kuaishou.com/profile/a', '--top-videos', '129'])
    with pytest.raises(ValueError, match='top-videos'):
        asyncio.run(cli.main(args))


def test_failed_channel_does_not_stop_batch_and_outputs_are_separate(tmp_path, monkeypatch, local_browser):
    calls = []
    async def process(args):
        calls.append(args)
        if len(calls) == 1:
            raise RuntimeError('频道登录已过期')
        cli.write_json(args.output / 'channel.json', {'name': '第二个频道'})
        return {'status': 'success', 'row': cli.empty_row({'name': '第二个频道', 'url': args.url}, '手语频道')}
    monkeypatch.setattr(cli, 'process_channel', process)
    args = parse_task_args(cli, ['batch', 'https://www.kuaishou.com/profile/first',
                                    'https://www.kuaishou.com/profile/second', '--output', str(tmp_path)])
    assert asyncio.run(cli.main(args)) == 1
    rows = read_results(next(tmp_path.glob('*/results.csv')))
    assert len(rows) == 2
    assert rows[0]['预测结果'] == '失败：RuntimeError: 频道登录已过期'
    assert rows[1]['预测结果'] == '手语频道'
    assert calls[0].output != calls[1].output
    assert calls[0].output.parent == calls[1].output.parent == next(tmp_path.iterdir()) / 'intermediate'
    assert calls[0].browser_dir == calls[1].browser_dir
    assert calls[0].command == calls[1].command == 'run'
    assert len(local_browser) == 1 and calls[0].page is calls[1].page
    assert not list(tmp_path.rglob('result.json')) and not list(tmp_path.rglob('summary.json'))
    assert (calls[1].output / 'channel.json').is_file()


def test_dry_run_batch_no_paid_api_and_invalid_url_recorded(tmp_path, monkeypatch):
    async def collect(url, output, browser_dir, **kwargs):
        cli.profile_id(url)
        return {'platform': 'kuaishou', 'name': '测试频道', 'bio': '', 'url': url,
                'videos': [{'id': 'sample', 'title': '手语', 'url': 'https://www.kuaishou.com/short-video/sample'}]}
    async def forbidden(*args, **kwargs):
        pytest.fail('dry-run 不应调用 API')
    monkeypatch.setattr(cli, 'collect', collect)
    monkeypatch.setattr(cli, 'call_model_api', forbidden)
    args = parse_task_args(cli, ['batch', 'https://example.com/profile/bad', 'https://www.kuaishou.com/profile/good',
                                    '--output', str(tmp_path), '--dry-run'])
    assert asyncio.run(cli.main(args)) == 1
    rows = read_results(next(tmp_path.glob('*/results.csv')))
    assert rows[0]['预测结果'].startswith('失败：ValueError:')
    assert rows[1]['预测结果'] == '未调用模型'
    assert next(tmp_path.glob('*/intermediate/002_good/title-request-preview.json')).is_file()


def test_cancelled_batch_keeps_csv(tmp_path, monkeypatch):
    async def cancelled(args):
        raise asyncio.CancelledError()
    monkeypatch.setattr(cli, 'process_channel', cancelled)
    args = parse_task_args(cli, ['batch', 'https://www.kuaishou.com/profile/first', '--output', str(tmp_path)])
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(cli.main(args))
    rows = read_results(next(tmp_path.glob('*/results.csv')))
    assert rows[0]['预测结果'] == '已中断'


def test_risk_control_stops_batch_and_preserves_completed_rows(tmp_path, monkeypatch):
    calls = []
    async def process(args):
        calls.append(args.url)
        if len(calls) == 2:
            raise cli.RiskControlError('作品区域仅显示“服务器异常，稍后重试”')
        return {'status': 'success', 'row': cli.empty_row({'name': '已完成频道', 'url': args.url}, '手语频道')}
    monkeypatch.setattr(cli, 'process_channel', process)
    urls = [f'https://www.kuaishou.com/profile/{n}' for n in ('first', 'second', 'third')]
    args = parse_task_args(cli, ['batch', *urls, '--output', str(tmp_path)])
    assert asyncio.run(cli.main(args)) == 1
    assert calls == urls[:2]
    rows = read_results(next(tmp_path.glob('*/results.csv')))
    assert rows[0]['预测结果'] == '手语频道'
    assert rows[1]['预测结果'].startswith('失败：RiskControlError:')
    assert rows[2]['预测结果'] == '未完成（快手风控）'


def test_csv_labels_and_direct_urls_dedup(tmp_path):
    source = tmp_path / 'input.csv'
    with source.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['平台', '账户昵称', '主页网址', '审核结果'])
        writer.writeheader()
        for platform, name, channel, label in [('快手', '名称,含逗号', 'first', '1'), ('快手', '疑难频道', 'second', '0'),
                                                ('快手', '普通频道', 'third', '-1'), ('YouTube', '其他平台', 'other', '1')]:
            writer.writerow(dict(zip(writer.fieldnames, [platform, name, f'https://www.kuaishou.com/profile/{channel}', label])))
    args = parse_task_args(cli, ['batch', 'https://www.kuaishou.com/profile/first?source=SEARCH', '--input-csv', str(source)])
    records = cli.batch_inputs(args)
    assert len(records) == 3
    assert records[0]['name'] == '名称,含逗号'
    assert [r['true_label'] for r in records] == ['手语频道', '疑难', '不是手语频道']
    source.write_text('主页网址,人工标注\nhttps://www.kuaishou.com/profile/first,手语频道\nhttps://www.kuaishou.com/profile/first,不是手语频道\n', encoding='utf-8-sig')
    with pytest.raises(ValueError, match='冲突'):
        cli.batch_inputs(args)


def test_predictions_csv_keeps_labels_out_of_request_and_quotes_titles(tmp_path, monkeypatch):
    source = tmp_path / 'input.csv'
    source.write_text('账户昵称,主页网址,审核结果\n输入名称,https://www.kuaishou.com/profile/good,不是手语频道\n', encoding='utf-8-sig')
    async def collect(url, output, browser_dir, **kwargs):
        return {'platform': 'kuaishou', 'name': '账号,带逗号\n和换行', 'bio': '', 'url': url,
                'videos': [{'id': 'sample', 'title': '你好', 'url': 'https://www.kuaishou.com/short-video/sample'}]}
    async def model(payload, api, **kwargs):
        assert '不是手语频道' not in json.dumps(payload, ensure_ascii=False)
        return {'answers': {'channel': {'type': 'choice', 'choice': 'yes', 'probabilities': {'yes': .9, 'no': .1}},
                'channel_probability': {'type': 'noul', 'noul': .9}, 'v001': {'type': 'noul', 'noul': .87},
                'best_video': {'type': 'choice', 'choice': 'v001', 'probabilities': {'v001': .9, 'none': .1}}}}
    monkeypatch.setattr(cli, 'collect', collect)
    monkeypatch.setattr(cli, 'call_model_api', model)
    args = parse_task_args(cli, ['batch', '--input-csv', str(source), '--output', str(tmp_path / 'outputs')])
    assert asyncio.run(cli.main(args)) == 0
    path = next((tmp_path / 'outputs').glob('*/results.csv'))
    rows = read_results(path)
    assert list(rows[0]) == cli.RESULT_COLUMNS + ['视频1分数', '视频1链接']
    assert rows[0]['账户名称'] == '账号,带逗号\n和换行'
    assert rows[0]['预测结果'] == '手语频道' and rows[0]['人工标注'] == '不是手语频道'
    assert rows[0]['频道概率'] == '0.9'
    assert rows[0]['最可能的视频'].endswith('/sample')
    assert rows[0]['频道网址'] == 'https://www.kuaishou.com/profile/good'
    assert rows[0]['视频1分数'] == '0.87'
    assert rows[0]['视频1链接'] == 'https://www.kuaishou.com/short-video/sample'
    assert not list((tmp_path / 'outputs').rglob('result.json'))


def test_video_columns_are_sorted_and_shorter_rows_stay_blank(tmp_path):
    result = {'channel_name': '测试', 'channel_url': 'https://www.kuaishou.com/profile/test',
              'channel_label': 'yes', 'channel_probability': .95, 'most_likely_video': {'url': 'https://example.com/b'},
              'videos': [{'url': 'https://example.com/a', 'relevance_probability': .1},
                         {'url': 'https://example.com/b', 'relevance_probability': .9},
                         {'url': 'https://example.com/c', 'relevance_probability': .5}]}
    path = tmp_path / 'results.csv'
    cli.write_results(path, [cli.result_row(result, category=TASK), cli.empty_row({'url': 'https://www.kuaishou.com/profile/other'})])
    rows = read_results(path)
    assert list(rows[0]) == cli.RESULT_COLUMNS + [f'视频{i}{suffix}' for i in range(1, 4) for suffix in ('分数', '链接')]
    assert [rows[0][f'视频{i}分数'] for i in range(1, 4)] == ['0.9', '0.5', '0.1']
    assert [rows[0][f'视频{i}链接'] for i in range(1, 4)] == [
        'https://example.com/b', 'https://example.com/c', 'https://example.com/a']
    assert rows[1]['频道网址'].endswith('/other')
    assert rows[1]['频道概率'] == ''
    assert all(rows[1][f'视频{i}{suffix}'] == '' for i in range(1, 4) for suffix in ('分数', '链接'))
