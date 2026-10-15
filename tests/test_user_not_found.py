from task_helpers import parse_task_args
import asyncio
import csv
import json

import pytest

from account_filter import __main__ as cli
from account_filter import collector


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def test_collect_saves_terminal_missing_user_snapshot_and_specific_error(tmp_path):
    class Page:
        context = object()
        def on(self, *args):
            pass
        def remove_listener(self, *args):
            pass
        async def goto(self, *args, **kwargs):
            pass
        async def evaluate(self, script):
            return {'name': '', 'bio': '', 'videos': [], 'user_not_found': True}
        def locator(self, selector):
            return self
        async def inner_text(self):
            return '用户不存在'
        async def screenshot(self, **kwargs):
            pass
    url = 'https://www.douyin.com/user/missing'
    with pytest.raises(collector.UserNotFoundError, match='主页明确显示“用户不存在”'):
        asyncio.run(collector.collect(url, tmp_path, tmp_path / 'browser', page=Page()))
    cached = collector.saved_channel(tmp_path, url)
    assert cached['user_not_found'] and not cached['videos'] and not cached['name']
    status = json.loads((tmp_path / 'collection-status.json').read_text(encoding='utf-8'))
    assert status['status'] == 'user_not_found' and status['error_type'] == 'UserNotFoundError'


def test_batch_records_missing_user_and_resume_skips_without_inference(tmp_path, monkeypatch):
    record = {'url': 'https://www.douyin.com/user/missing', 'name': '输入昵称', 'true_label': '手语频道'}
    async def missing(args):
        raise collector.UserNotFoundError('抖音主页明确显示“用户不存在”。')
    monkeypatch.setattr(cli, 'process_channel', missing)
    args = parse_task_args(cli, ['batch', '--output', str(tmp_path)])
    assert asyncio.run(cli.run_batch_in_session(args, [record], object())) == 0
    folder = next(tmp_path.glob('*/results.csv')).parent
    row = read_csv(folder / 'results.csv')[0]
    assert row['预测结果'] == cli.NOT_FOUND_RESULT
    assert not row['频道概率'] and not row['预测与标注不符']
    async def forbidden(*args, **kwargs):
        pytest.fail('用户不存在的已处理行不应再采集/调用模型')
    monkeypatch.setattr(cli, 'process_channel', forbidden)
    args = parse_task_args(cli, ['batch', '--resume', str(folder)])
    assert asyncio.run(cli.run_batch_in_session(args, [record], object())) == 0


def test_analyze_cached_missing_user_never_calls_model(tmp_path, monkeypatch):
    channel = {'url': 'https://www.douyin.com/user/missing', 'platform': 'douyin', 'name': '',
               'input_name': '输入昵称', 'videos': [], 'user_not_found': True, 'collection_state': 'user_not_found'}
    collector.save_channel(channel, tmp_path)
    async def forbidden(*args, **kwargs):
        pytest.fail('用户不存在不能调用模型')
    monkeypatch.setattr(cli, 'call_model_api', forbidden)
    args = parse_task_args(cli, ['analyze', str(tmp_path / 'channel.json'), '--output', str(tmp_path / 'new')])
    assert asyncio.run(cli.main(args)) == 0
    assert read_csv(args.output / 'results.csv')[0]['账户名称'] == '输入昵称'
