"""Input account lists to a reusable dataset. No model dependencies."""
import csv
import os
from pathlib import Path
from .browser import browser_session, collect, archive_covers, profile_info, saved_channel, recover_post_type_failure
from .platforms.registry import PLATFORMS
from ..dataset import read_dataset, write_dataset
from ..errors import RiskControlError, UserNotFoundError
from ..experiments import create_experiment_dir
from ..progress import Progress

DEFAULT_BROWSER = 'msedge' if os.name == 'nt' and Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe').exists() else None


def input_records(args):
    rows = []
    if args.input_csv:
        with args.input_csv.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            if '主页网址' not in (reader.fieldnames or []):
                raise ValueError('输入 CSV 必须包含“主页网址”。')
            rows.extend(reader)
    rows.extend({'主页网址': url} for url in args.urls)
    records, seen = [], set()
    for row in rows:
        platform, account_id = profile_info(row['主页网址'].strip())
        if (platform, account_id) in seen:
            continue
        seen.add((platform, account_id))
        records.append({'platform': platform, 'account_id': account_id, 'url': row['主页网址'].strip(),
                        'name': row.get('账户昵称') or row.get('账户名称') or '',
                        'annotation': row.get('人工标注') or row.get('审核结果') or '',
                        'path': f'channels/{platform}/{account_id}/channel.json', 'status': 'pending', 'error': ''})
    if not records:
        raise ValueError('请指定 --input-csv 或账户主页链接。')
    return records


async def run(args):
    root = args.resume.resolve() if args.resume else create_experiment_dir(args.output).resolve()
    records = read_dataset(root) if args.resume else input_records(args)
    write_dataset(root, records)
    failed = 0
    async with Progress(len(records)) as progress:
        progress.start_at(sum(r['status'] in ('ready', 'private', 'user_not_found') for r in records))
        async with browser_session(args.browser_dir, headless=args.headless, browser_channel=args.browser_channel,
                                   cookies=args.cookies) as page:
            for index, record in enumerate(records, 1):
                if record['status'] in ('ready', 'private', 'user_not_found'):
                    continue
                folder = root / record['path']
                folder = folder.parent
                try:
                    if (folder / 'collection-status.json').is_file():
                        recover_post_type_failure(folder, record['url'])
                    channel = saved_channel(folder, record['url'])
                    if channel is None:
                        channel = await collect(record['url'], folder, args.browser_dir, page=page,
                                                timeout=args.timeout, login_timeout=args.login_timeout,
                                                headless=args.headless, on_status=progress.set_phase)
                    channel.setdefault('id', record['account_id'])
                    if not channel.get('user_not_found'):
                        await archive_covers(channel, folder, page, progress.set_phase)
                    record.update(name=channel['name'], status='private' if channel.get('is_private') else 'ready', error='')
                except UserNotFoundError as exc:
                    record.update(status='user_not_found', error=str(exc))
                except Exception as exc:
                    record.update(status='failed', error=f'{type(exc).__name__}: {exc}')
                    failed += 1
                    progress.message(f'[{index}/{len(records)}] 采集失败：{record["url"]}\n{record["error"]}', error=True)
                    if isinstance(exc, RiskControlError):
                        write_dataset(root, records)
                        progress.stopped = True
                        break
                write_dataset(root, records)
                progress.advance()
    print(f'采集数据：{root}')
    return 1 if failed else 0


async def login(args):
    platform, _ = profile_info(args.url)
    from .platforms.registry import adapter
    import asyncio
    async with browser_session(args.browser_dir, browser_channel=args.browser_channel) as page:
        site = 'https://' + PLATFORMS[platform]['hosts'][0]
        await page.goto(site, wait_until='domcontentloaded')
        await adapter(platform).begin_login(page)
        print('请在浏览器完成登录。')
        deadline = asyncio.get_running_loop().time() + args.login_timeout
        while not any(c['name'] in adapter(platform).LOGIN_COOKIES and c['value'] for c in await page.context.cookies(site)):
            adapter(platform).check_page({'videos': []}, await page.locator('body').inner_text())
            if asyncio.get_running_loop().time() >= deadline:
                raise ValueError('等待登录超时。')
            await asyncio.sleep(1)
    return 0
