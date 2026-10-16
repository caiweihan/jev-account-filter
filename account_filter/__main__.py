"""Dispatch independent collection and screening commands lazily."""
import argparse
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT = Path(__file__).resolve().parents[1]


def positive(value):
    n = int(value)
    if n <= 0:
        raise argparse.ArgumentTypeError('必须为正整数。')
    return n


def parser():
    p = argparse.ArgumentParser(description='账户筛选：input → collect → data → screen → results')
    sub = p.add_subparsers(dest='command', required=True)
    collect = sub.add_parser('collect', help='只采集账户数据，不调用模型')
    collect.add_argument('urls', nargs='*')
    collect.add_argument('--input-csv', type=Path)
    collect.add_argument('--output', type=Path)
    collect.add_argument('--resume', type=Path)
    collect.add_argument('--cookies', type=Path)
    collect.add_argument('--headless', action='store_true')
    collect.add_argument('--timeout', type=positive, default=45)
    login = sub.add_parser('login', help='只保存浏览器登录会话')
    login.add_argument('url')
    for cmd in (collect, login):
        cmd.add_argument('--browser-dir', type=Path, default=PROJECT / '.browser/profile')
        cmd.add_argument('--browser-channel', choices=('msedge', 'chrome'))
        cmd.add_argument('--login-timeout', type=positive, default=600)
    screen = sub.add_parser('screen', help='只读取采集数据并调用模型，不访问平台或下载封面')
    screen.add_argument('--data', type=Path)
    screen.add_argument('--output', type=Path)
    screen.add_argument('--resume', type=Path)
    screen.add_argument('--config', type=Path)
    screen.add_argument('--category')
    screen.add_argument('--top-videos', type=positive)
    screen.add_argument('--dry-run', action='store_true')
    validate = sub.add_parser('validate-data', help='验证自定义数据集，不访问网络')
    validate.add_argument('data', type=Path)
    return p


async def main(args):
    load_dotenv(PROJECT / '.env')
    if args.command in ('collect', 'login'):
        os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', str(PROJECT / '.cache/ms-playwright'))
        from .collection import runner
        args.browser_channel = args.browser_channel or runner.DEFAULT_BROWSER
        if args.command == 'login':
            return await runner.login(args)
        if not args.resume and not args.output:
            raise ValueError('采集请指定 --output data/<数据集名>。')
        if args.resume and (args.output or args.input_csv or args.urls):
            raise ValueError('采集续跑只指定 --resume，读取已有输入清单。')
        return await runner.run(args)
    if args.command == 'screen':
        if not args.resume and not all((args.data, args.output, args.config, args.category)):
            raise ValueError('筛选请指定 --data、--output、--config 和 --category。')
        if args.top_videos and args.top_videos > 128:
            raise ValueError('--top-videos 最大为 128。')
        from .screening.runner import run
        return await run(args)
    from .dataset import read_dataset, read_channel
    records = read_dataset(args.data)
    for record in records:
        read_channel(record, args.data)
    print(f'数据格式验证通过：{len(records)} 个账户。')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(asyncio.run(main(parser().parse_args())))
    except KeyboardInterrupt:
        raise SystemExit('已停止；可以在同一目录续跑。')
    except Exception as exc:
        raise SystemExit(f'{type(exc).__name__}: {exc}')
