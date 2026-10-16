from task_helpers import parse_task_args
import asyncio
import csv
import json

import pytest

from account_filter.collection import runner as cli
from account_filter.collection import browser as collector




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
