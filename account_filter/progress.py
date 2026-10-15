"""命令行进度；中间数据只写入文件。"""
import asyncio
import sys
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from time import monotonic
from unicodedata import east_asian_width


def duration(seconds):
    seconds = int(seconds)
    return f'{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}'


class Progress:
    def __init__(self, total):
        self.total = total
        self.completed = 0
        self.initial_completed = 0
        self.phase = '准备'
        self.started = monotonic()
        self.interactive = sys.stdout.isatty()
        self.width = 0
        self.timer = None
        self.stopped = False

    def render(self):
        elapsed = monotonic() - self.started
        processed = self.completed - self.initial_completed
        remaining = duration(elapsed / processed * (self.total - self.completed)) if processed > 0 and not self.stopped else '--:--:--'
        filled = int(10 * self.completed / self.total)
        clock = datetime.now(timezone(timedelta(hours=8))).strftime('%H:%M:%S')
        text = (f'[{clock}] [{"#" * filled}{"-" * (10 - filled)}] '
                f'{self.completed}/{self.total} {self.completed * 100 // self.total}% '
                f'已用 {duration(elapsed)} 剩余约 {remaining} | {self.phase}')
        if self.interactive:
            width = sum(2 if east_asian_width(char) in ('W', 'F') else 1 for char in text)
            sys.stdout.write('\r' + text + ' ' * max(0, self.width - width))
            sys.stdout.flush()
            self.width = width
        else:
            print(text, flush=True)

    def set_phase(self, phase):
        self.phase = phase
        self.render()

    def advance(self, phase='完成'):
        self.completed += 1
        self.set_phase(phase)

    def start_at(self, completed):
        self.initial_completed = self.completed = completed
        self.render()

    def message(self, text, *, error=False):
        if self.interactive:
            sys.stdout.write('\r' + ' ' * self.width + '\r')
            sys.stdout.flush()
            self.width = 0
        print(text, file=sys.stderr if error else sys.stdout, flush=True)
        if self.interactive:
            self.render()

    async def tick(self):
        while True:
            await asyncio.sleep(1)
            self.render()

    async def __aenter__(self):
        self.render()
        if self.interactive:
            self.timer = asyncio.create_task(self.tick())
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        if self.timer:
            self.timer.cancel()
            with suppress(asyncio.CancelledError):
                await self.timer
        if exc_type:
            self.stopped = True
            self.phase = '已中断' if exc_type in (KeyboardInterrupt, asyncio.CancelledError) else '失败'
        if self.interactive:
            self.render()
            print(flush=True)
        elif exc_type:
            self.render()
