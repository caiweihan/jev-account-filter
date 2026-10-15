import argparse
import asyncio
import csv
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_BROWSER = 'msedge' if os.name == 'nt' and Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe').exists() else None
load_dotenv(PROJECT / '.env')
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', str(PROJECT / '.cache' / 'ms-playwright'))

from .classifier import build_request, build_title_request, rank_titles, call_model_api, normalize_result
from .collector import (RiskControlError, UserNotFoundError, browser_session, collect, download_selected_covers,
                        profile_id, profile_info, save_channel, saved_channel, attach_saved_covers, archive_covers,
                        recover_post_type_failure)
from .progress import Progress
from .config import ConfigArgumentParser
from .category import saved_category, category_labels
from .cache import reference_snapshot, remember

RESULT_COLUMNS = ['账户名称', '频道网址', '预测结果', '频道概率', '人工标注', '预测与标注不符', '最可能的视频']
PRIVATE_RESULT = '无法判断（私密账号）'
NOT_FOUND_RESULT = '用户不存在'
CACHE_REFRESHED = '已更新缓存'
NON_CLASSIFICATION_RESULTS = (PRIVATE_RESULT, NOT_FOUND_RESULT, CACHE_REFRESHED)


def positive(value):
    n = int(value)
    if n <= 0:
        raise argparse.ArgumentTypeError('必须为正整数。')
    return n


def parser():
    p = ConfigArgumentParser(description='账户分类：平台采集 → 标题排序 → 资料与封面复判')
    sub = p.add_subparsers(dest='command', required=True)
    for command in ('login', 'collect', 'run', 'analyze', 'batch'):
        cmd = sub.add_parser(command)
        if command != 'analyze':
            if command == 'batch':
                cmd.add_argument('urls', nargs='*', help='多个频道链接，以空格分隔')
                cmd.add_argument('--urls-file', type=Path, help='UTF-8 文本文件，每行一个频道链接')
                cmd.add_argument('--input-csv', type=Path, help='输入 CSV，必需列：主页网址；可选列：账户昵称、人工标注（兼容审核结果）')
                cmd.add_argument('--resume', type=Path, help='继续已有时间目录，更新同一个results.csv；重试失败/未完成项，复用已保存资料')
                cmd.add_argument('--reclassify-from', type=Path, help='从已有实验的频道缓存重新两轮判断，输出新时间目录；不访问平台或下载封面')
                cmd.add_argument('--from-cache', action='store_true', help='只用data/channels中的正式采集缓存重新判断，不访问平台或下载封面')
                cmd.add_argument('--refresh-cache', action='store_true', help='重新采集全部频道资料并核实作品类型，复用已有视频封面；不调用模型')
                cmd.add_argument('--backfill-only', action='store_true', help='与--resume配合：只补已有频道的封面缓存，不访问作者主页或调用模型')
            else:
                cmd.add_argument('url')
            cmd.add_argument('--browser-dir', type=Path, default=PROJECT / '.browser' / 'profile')
            cmd.add_argument('--browser-channel', choices=('msedge', 'chrome'), default=DEFAULT_BROWSER, help='使用本机官方 Edge/Chrome；Windows 有 Edge 时默认使用 Edge')
            cmd.add_argument('--cookies', type=Path, help='Cookie 数组或 Playwright storage_state JSON')
            cmd.add_argument('--timeout', type=positive, default=45)
            cmd.add_argument('--login-timeout', type=positive, default=300)
            cmd.add_argument('--headless', action='store_true')
            cmd.add_argument('--platform', choices=('auto', 'kuaishou', 'douyin'), default='auto',
                             help='选择采集平台；默认按链接识别，可混合快手和抖音')
            if command in ('run', 'batch'):
                cmd.add_argument('--login', action='store_true')
        else:
            cmd.add_argument('channel_json', type=Path)
        cmd.add_argument('--output', type=Path, default=PROJECT / 'output' / 'batch' if command == 'batch' else PROJECT / 'output',
                         help='输出父目录；每次运行自动创建北京时间命名的子目录')
        cmd.add_argument('--top-videos', '--max-videos', dest='max_videos', type=positive, default=5,
                         help='标题排序后进入封面复判的候选数，默认 5；--max-videos 为兼容别名')
        if command in ('run', 'analyze', 'batch'):
            cmd.add_argument('--config', type=Path,
                             help='明确选择模型/API 配置 TOML；续跑可读取实验快照')
            cmd.add_argument('--category', help='明确选择分类配置名称或 TOML 路径；续跑可读取实验快照')
            cmd.add_argument('--dry-run', action='store_true', help='生成请求预算和脱敏预览，不调用付费 API')
    return p


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def write_results(path, rows, category=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    video_indices = sorted({int(key[2:-2]) for row in rows for key in row
                            if key.startswith('视频') and key.endswith(('分数', '链接')) and key[2:-2].isdigit()})
    video_columns = [f'视频{index}{suffix}' for index in video_indices for suffix in ('分数', '链接')]
    labels = category_labels(category) if category else ()
    for row in rows:
        if category:
            row['预测与标注不符'] = ('预测与标注不符' if row.get('预测结果') in labels and
                                  row.get('人工标注') in labels and row['预测结果'] != row['人工标注'] else '')
        else:
            row.setdefault('预测与标注不符', '')
    temporary = path.with_suffix('.csv.tmp')
    with temporary.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=RESULT_COLUMNS + video_columns)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def label_text(value, category=None):
    value = (value or '').strip()
    if not category:
        return value  # Collection-only tasks preserve annotations without interpreting a category.
    labels = {'yes': category['positive_label'], '1': category['positive_label'],
              'no': category['negative_label'], '-1': category['negative_label'],
              '0': '疑难', 'uncertain': '疑难'}
    if not value or value in labels.values():
        return value
    if value in labels:
        return labels[value]
    raise ValueError(f'未知人工标注：{value}；请使用 {category["positive_label"]} / 疑难 / {category["negative_label"]}。')


def empty_row(record, prediction='待处理'):
    return dict(zip(RESULT_COLUMNS, [record.get('name') or record['url'], record['url'], prediction,
                                    '', record.get('true_label', ''), '', '']))


def result_row(result, true_label='', *, category):
    best = result['most_likely_video']
    labels = {'yes': category['positive_label'], 'no': category['negative_label']}
    row = dict(zip(RESULT_COLUMNS, [result['channel_name'], result['channel_url'], labels[result['channel_label']],
                                   result['channel_probability'], true_label, '', best['url'] if best else '无候选']))
    videos = sorted(result['videos'], key=lambda video: video['relevance_probability'], reverse=True)
    for index, video in enumerate(videos, 1):
        row[f'视频{index}分数'] = video['relevance_probability']
        row[f'视频{index}链接'] = video['url']
    return row


def create_run_dir(parent, started=None):
    started = started or datetime.now(timezone(timedelta(hours=8)))
    stamp = started.strftime('%Y%m%d-%H%M%S-%f')
    suffix = 0
    while True:
        folder = parent / (stamp if suffix == 0 else f'{stamp}-{suffix}')
        try:
            folder.mkdir(parents=True, exist_ok=False)
            return folder
        except FileExistsError:
            suffix += 1


def set_phase(args, phase):
    if getattr(args, 'progress', None):
        args.progress.set_phase(phase)


async def cached_model_call(args, payload, preview, stem):
    """续跑只复用相同问题和证据的已保存响应，失败的API请求没有成功响应可复用。"""
    preview_path = args.output / f'{stem}-request-preview.json' if stem == 'title' else args.output / 'request-preview.json'
    response_path = args.output / f'{stem}-model-response.json' if stem == 'title' else args.output / 'model-response.json'
    hash_path = response_path.with_suffix('.sha256')
    endpoint = args.endpoint
    preview = {**preview, 'endpoint': endpoint}
    signature = hashlib.sha256(json.dumps({'endpoint': endpoint, 'payload': payload}, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
    cached = None
    if getattr(args, 'reuse_cache', False) and response_path.is_file():
        try:
            old = json.loads(preview_path.read_text(encoding='utf-8-sig'))
            keys = ('model', 'api', 'prompt_version', 'questions', 'state_text', 'messages')
            matches = all(old.get(key) == preview.get(key) for key in keys)
            matches = matches and old.get('endpoint') == endpoint
            if stem != 'title':
                matches = matches and old.get('image_count') == preview.get('image_count') and old.get('budget') == preview.get('budget')
                matches = matches and [(v['id'], v.get('has_cover')) for v in old['videos']] == [(v['id'], v.get('has_cover')) for v in preview['videos']]
            valid_hashes = {signature}
            if matches and (not hash_path.is_file() or hash_path.read_text().strip() in valid_hashes):
                cached = json.loads(response_path.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError, KeyError):
            pass
    write_json(preview_path, preview)
    if cached is not None:
        hash_path.write_text(signature, encoding='ascii')
        return cached
    # 保留旧原始响应供检查，但新请求成功前将缓存标为未完成，避免失败后误用旧结果。
    hash_path.write_text('pending:' + signature, encoding='ascii')
    raw = await call_model_api(payload, args.api, endpoint=endpoint,
        api_key_env=args.api_key_env,
        timeout=getattr(args, 'timeout_seconds', 120))
    write_json(response_path, raw)
    hash_path.write_text(signature, encoding='ascii')
    return raw


async def process_channel(args):
    category = getattr(args, 'category_spec', None)
    negative_label = category['negative_label'] if category else None
    if args.command != 'analyze' and getattr(args, 'page', None) is None:
        platform, _ = profile_info(args.url)
        selected_platform = getattr(args, 'platform', 'auto')
        if selected_platform != 'auto' and selected_platform != platform:
            raise ValueError('频道链接与 --platform 选择的平台不符。')
        async with browser_session(args.browser_dir, headless=args.headless,
                                   browser_channel=args.browser_channel, cookies=args.cookies) as page:
            try:
                return await process_channel(argparse.Namespace(**{**vars(args), 'page': page}))
            except Exception:
                cached = saved_channel(args.output, args.url)
                if cached:
                    await archive_covers(cached, args.output.resolve(), page, lambda phase: set_phase(args, phase))
                raise
    channel = saved_channel(args.output, args.url) if getattr(args, 'reuse_cache', False) else None
    if channel is not None:
        set_phase(args, '读取频道缓存')
        root = args.output.resolve()
    elif args.command == 'analyze':
        set_phase(args, '读取已保存资料')
        channel = json.loads(args.channel_json.read_text(encoding='utf-8-sig'))
        root = args.channel_json.resolve().parent
    else:
        set_phase(args, '采集频道')
        channel = await collect(args.url, args.output, args.browser_dir,
            max_videos=args.max_videos, headless=args.headless,
            login=args.command == 'login' or getattr(args, 'login', False),
            timeout=args.timeout, login_timeout=args.login_timeout,
            browser_channel=args.browser_channel, page=args.page,
            on_status=lambda phase: set_phase(args, phase),
            require_video_types=True)
        root = args.output.resolve()
    attach_saved_covers(channel, root)
    from .platforms.douyin import filter_image_posts
    channel = filter_image_posts(channel)
    if channel.get('user_not_found'):
        write_json(args.output / 'classification-status.json', {'status': 'user_not_found',
            'model_called': False, 'reason': channel.get('unavailable_reason', '主页明确显示用户不存在。')})
        return {'status': 'not_found', 'row': empty_row({'name': channel.get('name') or channel.get('input_name'), 'url': channel['url'],
            'true_label': getattr(args, 'true_label', '')}, NOT_FOUND_RESULT)}
    if args.command in ('collect', 'login'):
        await archive_covers(channel, root, args.page, lambda phase: set_phase(args, phase))
        return
    if getattr(args, 'refresh_cache', False):
        await archive_covers(channel, root, args.page, lambda phase: set_phase(args, phase))
        return {'status': 'success', 'row': empty_row({'name': channel['name'], 'url': channel['url'],
            'true_label': getattr(args, 'true_label', '')}, CACHE_REFRESHED)}
    if channel.get('is_private'):
        return {'status': 'private', 'row': empty_row({'name': channel['name'], 'url': channel['url'],
                'true_label': getattr(args, 'true_label', '')}, PRIVATE_RESULT)}
    if category is None:
        raise ValueError('分类任务缺少明确的类别配置。')
    if channel.get('no_video_posts'):
        write_json(args.output / 'classification-status.json', {'status': 'no_video_posts',
            'reason': f'本次采集的第一页只有图文/图集或文字文章，已排除；没有可判断的{category["name"]}视频候选。',
            'excluded_count': len(channel.get('excluded_posts', [])), 'model_called': False})
        return {'status': 'success', 'row': empty_row({'name': channel['name'], 'url': channel['url'],
            'true_label': getattr(args, 'true_label', '')}, negative_label)}
    if channel.get('no_posts') and not channel['videos']:
        row = empty_row({'name': channel['name'], 'url': channel['url'], 'true_label': getattr(args, 'true_label', '')}, negative_label)
        row['最可能的视频'] = '无候选'
        write_json(args.output / 'classification-status.json', {'status': 'no_posts',
                   'reason': channel.get('empty_reason', '主页明确未投稿'), 'model_called': False})
        return {'status': 'success', 'row': row}
    channel.setdefault('warnings', [])
    title_payload, title_selection = build_title_request(channel, model=args.model, api=args.api,
                                                        context_budget=args.context_budget, category=category)
    title_preview = {'model': args.model, 'api': args.api, 'prompt_version': title_selection['prompt_version'],
                     'video_count': len(title_selection['videos']), 'estimated_input_tokens': title_selection['estimated_input_tokens'],
                     'videos': title_selection['videos'], 'questions': title_payload.get('questions'),
                     'state_text': title_payload.get('state'), 'messages': title_payload.get('messages')}
    if args.dry_run:
        write_json(args.output / 'title-request-preview.json', title_preview)
        set_phase(args, '已保存预览')
        return {'status': 'dry_run', 'row': empty_row({'name': channel['name'], 'url': channel['url'],
                'true_label': getattr(args, 'true_label', '')}, '未调用模型')}
    set_phase(args, '标题排序')
    title_raw = await cached_model_call(args, title_payload, title_preview, 'title')
    ranked = rank_titles(title_raw, title_selection)
    selected = ranked[:args.max_videos]
    write_json(args.output / 'title-ranking.json', {'videos': ranked, 'selected_ids': [v['id'] for v in selected]})
    set_phase(args, '下载候选封面')
    if getattr(args, 'offline', False):
        for video in selected:
            cover = root / (video.get('cover_path') or '__missing__')
            if cover.is_file():
                video['cover_path'] = str(cover.resolve())
            else:
                video.pop('cover_path', None)
                channel['warnings'].append(f"候选 {video['id']} 本地封面缺失，离线重判仅使用标题，不下载或访问平台。")
    elif args.command == 'analyze' and any(v.get('cover_url') and not (root / (v.get('cover_path') or '__missing__')).is_file() for v in selected):
        async with browser_session(PROJECT / '.browser' / 'profile', browser_channel=DEFAULT_BROWSER) as page:
            await download_selected_covers(channel, selected, root, args.output, page)
    else:
        await download_selected_covers(channel, selected, root, args.output, getattr(args, 'page', None))
    write_json(args.output / 'selected-videos.json', {'videos': selected, 'warnings': channel['warnings']})
    # 先完成候选选择与封面下载；其余封面用于以后离线复用，不加入第二轮模型输入。
    if args.command != 'analyze' or getattr(args, 'page', None):
        await archive_covers(channel, root, getattr(args, 'page', None), lambda phase: set_phase(args, phase))
    else:
        attach_saved_covers(channel, root)
    candidates = {**channel, 'videos': selected}
    payload, selection = build_request(candidates, root, model=args.model, api=args.api,
        max_videos=args.max_videos, image_side=args.image_side, context_budget=args.context_budget,
        image_tokens=args.image_token_estimate, require_all=True, category=category)
    preview = {'model': args.model, 'api': args.api,
               'prompt_version': selection['prompt_version'],
               'channel': {'name': channel['name'][:1000], 'bio': channel.get('bio', '')[:4000]},
               'video_count': len(selection['videos']), 'image_count': sum(v['has_cover'] for v in selection['videos']),
               'budget': {k: v for k, v in selection.items() if k not in ('videos', 'warnings')},
               'videos': selection['videos'], 'warnings': selection['warnings'],
               'questions': payload.get('questions'),
               'state_text': [part for part in payload.get('state', []) if isinstance(part, str)]}
    set_phase(args, '封面复判')
    raw = await cached_model_call(args, payload, preview, 'video')
    result = normalize_result(raw, selection, channel, category=category)
    row = result_row(result, getattr(args, 'true_label', ''), category=category)
    return {'status': 'success', 'row': row}


def batch_inputs(args):
    records = []
    source = getattr(args, 'resume', None) or getattr(args, 'reclassify_from', None)
    if source and not (args.input_csv or args.urls or args.urls_file):
        with (source / 'results.csv').open(encoding='utf-8-sig', newline='') as stream:
            return [{'url': row['频道网址'], 'name': row['账户名称'],
                     'true_label': label_text(row.get('人工标注') or row.get('真实标签'), getattr(args, 'category_spec', None))} for row in csv.DictReader(stream)]
    if args.input_csv:
        with args.input_csv.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or '主页网址' not in reader.fieldnames:
                raise ValueError('输入 CSV 缺少“主页网址”列。')
            skipped = 0
            for index, row in enumerate(reader, 2):
                if row.get('平台', '').strip() not in ('', '快手', '抖音'):
                    skipped += 1
                    continue
                url = (row.get('主页网址') or '').strip()
                if not url:
                    raise ValueError(f'输入 CSV 第 {index} 行的主页网址为空。')
                records.append({'url': url, 'name': (row.get('账户昵称') or row.get('账户名称') or '').strip(),
                                'true_label': label_text(row.get('人工标注') or row.get('审核结果') or row.get('真实标签'), getattr(args, 'category_spec', None))})
            if skipped:
                print(f'跳过 {skipped} 条其他平台数据；当前支持快手和抖音。', flush=True)
    urls = list(args.urls)
    if args.urls_file:
        urls.extend(line.strip() for line in args.urls_file.read_text(encoding='utf-8-sig').splitlines()
                    if line.strip() and not line.lstrip().startswith('#'))
    records.extend({'url': url, 'name': '', 'true_label': ''} for url in urls)
    unique, seen = [], {}
    for record in records:
        url = record['url'].strip()
        if not url:
            continue
        try:
            platform, user_id = profile_info(url)
            key = platform + ':' + user_id
        except ValueError:
            key = url
        if key in seen:
            previous = seen[key]
            if previous['true_label'] and record['true_label'] and previous['true_label'] != record['true_label']:
                raise ValueError(f'同一频道存在冲突的人工标注：{url}')
            previous['true_label'] = previous['true_label'] or record['true_label']
            previous['name'] = previous['name'] or record['name']
        else:
            record['url'] = url
            unique.append(record)
            seen[key] = record
    if not unique:
        raise ValueError('请提供至少一个频道链接，或用 --input-csv / --urls-file 指定输入文件。')
    return unique


def batch_urls(args):
    return [record['url'] for record in batch_inputs(args)]


async def run_batch(args):
    refresh_resume = bool(getattr(args, 'resume', None) and (args.resume / 'refresh-settings.json').is_file())
    args.refresh_cache = bool(getattr(args, 'refresh_cache', False) or refresh_resume)
    if getattr(args, 'resume', None) and getattr(args, 'reclassify_from', None):
        raise ValueError('--resume 与 --reclassify-from 不能同时使用；新判据请用后者创建新实验。')
    if getattr(args, 'from_cache', False) and getattr(args, 'reclassify_from', None):
        raise ValueError('--from-cache 与 --reclassify-from 只能选择一个缓存来源。')
    args.offline = bool(getattr(args, 'from_cache', False) or getattr(args, 'reclassify_from', None) or
                        (getattr(args, 'resume', None) and (args.resume / 'reclassify-settings.json').is_file()))
    if args.refresh_cache and (args.offline or getattr(args, 'backfill_only', False) or args.dry_run):
        raise ValueError('--refresh-cache 不能与离线重判、--backfill-only 或 --dry-run 同时使用。')
    if args.refresh_cache and getattr(args, 'resume', None) and not refresh_resume:
        raise ValueError('请新建缓存更新任务；--refresh-cache 不能续跑并覆盖旧分类实验。')
    if args.offline and getattr(args, 'backfill_only', False):
        raise ValueError('离线重判不下载封面，不能同时使用 --backfill-only。')
    records = batch_inputs(args)
    selected_platform = getattr(args, 'platform', 'auto')
    if selected_platform != 'auto':
        records = [record for record in records if profile_info(record['url'])[0] == selected_platform]
        if not records:
            raise ValueError('输入中没有所选平台的频道。')
    state = prepare_batch(args, records)
    async with Progress(len(records)) as progress:
        if args.offline:
            progress.set_phase('读取本地缓存，重新两轮判断')
            return await run_batch_in_session(args, records, None, progress, state)
        progress.set_phase('启动浏览器')
        async with browser_session(args.browser_dir, headless=args.headless,
                                   browser_channel=args.browser_channel, cookies=args.cookies) as page:
            return await run_batch_in_session(args, records, page, progress, state)


def channel_folder(batch_dir, index, url):
    try:
        platform, channel_id = profile_info(url)
        if platform == 'douyin':
            channel_id = 'douyin_' + channel_id[-16:]
    except ValueError:
        channel_id = 'invalid-url'
    expected = batch_dir / 'intermediate' / f'{index:03d}_{channel_id}'
    if expected.is_dir():
        return expected
    # CSV 删行后编号会变化，按频道身份复用原目录，避免重采集或移动原封面文件。
    for folder in sorted((batch_dir / 'intermediate').glob(f'*_{channel_id}')):
        for filename, field in (('channel.json', 'url'), ('collection-status.json', 'channel_url')):
            try:
                cached_url = json.loads((folder / filename).read_text(encoding='utf-8-sig'))[field]
                if profile_info(cached_url) == profile_info(url):
                    return folder
            except (OSError, ValueError, KeyError):
                continue
    return expected


def prepare_batch(args, records):
    if getattr(args, 'backfill_only', False) and not getattr(args, 'resume', None):
        raise ValueError('--backfill-only 必须与 --resume 已有时间目录配合。')
    if getattr(args, 'resume', None):
        batch_dir = args.resume.resolve()
        task = getattr(args, 'category_spec', None)
        previous_task = saved_category(batch_dir)
        if task and previous_task and any(task[key] != previous_task[key] for key in ('id', 'positive_label', 'negative_label')):
            raise ValueError('续跑不能更换分类任务或标签；请创建新实验。')
        results_path = batch_dir / 'results.csv'
        with results_path.open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) != len(records) or any(profile_info(row['频道网址']) != profile_info(record['url'])
                                          for row, record in zip(rows, records)):
            raise ValueError('续跑的频道顺序或数量与已有结果不同；请使用原输入CSV，或仅指定 --resume。')
        for row, record in zip(rows, records):
            row['人工标注'] = record['true_label']
            row.pop('真实标签', None)
            row.setdefault('频道概率', '')
    else:
        batch_dir = create_run_dir(args.output)
        results_path = batch_dir / 'results.csv'
        rows = [empty_row(record) for record in records]
        if getattr(args, 'reclassify_from', None) or getattr(args, 'from_cache', False):
            write_json(batch_dir / 'reclassify-settings.json', {'offline': True,
                'cache_source': str(args.reclassify_from.resolve()) if getattr(args, 'reclassify_from', None) else 'data/channels',
                'prompt_version': args.category_spec['version']})
        if getattr(args, 'refresh_cache', False):
            write_json(batch_dir / 'refresh-settings.json', {'refresh_cache': True,
                'cache_directory': 'data/channels', 'model_called': False})
    write_results(results_path, rows, category=getattr(args, 'category_spec', None))
    if getattr(args, 'category_spec', None):
        write_json(batch_dir / 'category.json', args.category_spec)
    if getattr(args, 'api_config', None):
        write_json(batch_dir / 'api-config.json', args.api_config)
    return batch_dir, results_path, rows


async def run_batch_in_session(args, records, page, progress=None, state=None):
    if progress is None:
        async with Progress(len(records)) as progress:
            return await run_batch_in_session(args, records, page, progress, state)
    batch_dir, results_path, rows = state or prepare_batch(args, records)
    resuming = bool(getattr(args, 'resume', None))
    backfill_only = bool(getattr(args, 'backfill_only', False))
    task = getattr(args, 'category_spec', None)
    predictions = (task['positive_label'], task['negative_label']) if task else ()
    terminal_results = (*predictions, '疑难', *NON_CLASSIFICATION_RESULTS)
    if backfill_only:
        progress.total = sum(saved_channel(channel_folder(batch_dir, i, r['url']), r['url']) is not None
                             for i, r in enumerate(records, 1)) or 1
    elif resuming:
        progress.start_at(sum(row['预测结果'] in terminal_results for row in rows))
        progress.set_phase('检查本地缓存；仅重试失败或未完成频道')
    succeeded = failed = unavailable = 0
    archived_missing = 0
    for index, record in enumerate(records, 1):
        url = record['url']
        folder = channel_folder(batch_dir, index, url)
        completed = rows[index - 1]['预测结果'] in terminal_results
        if resuming and getattr(args, 'refresh_cache', False) and not completed:
            recover_post_type_failure(folder, url)
        cached = saved_channel(folder, url) if resuming else None
        if backfill_only or (resuming and completed):
            if cached:
                attach_saved_covers(cached, folder)
                needs_covers = any(not v.get('cover_path') or not (folder / v['cover_path']).is_file()
                                  for v in cached['videos'])
                # 完整缓存直接跳过；普通续跑不逐个刷新已有封面，也不重写快照。
                if (backfill_only or needs_covers) and not getattr(args, 'offline', False):
                    def archive_phase(phase):
                        progress.set_phase(f'补齐频道 {index}/{len(records)} 缓存 | {phase}')
                    status = await archive_covers(cached, folder, page, archive_phase)
                    archived_missing += len(status['missing'])
            elif completed:
                progress.message(f'缓存缺失：第{index}个频道没有完整channel.json，请检查该频道目录。', error=True)
            if backfill_only and cached:
                progress.advance('补齐缓存')
            continue
        progress.set_phase(f'处理频道 {index}/{len(records)}：{record.get("name") or url}')
        channel_args = argparse.Namespace(**{**vars(args), 'command': 'run', 'url': url, 'output': folder,
                                              'true_label': record['true_label'], 'page': page, 'progress': progress,
                                              'reuse_cache': resuming})
        try:
            if getattr(args, 'offline', False):
                if getattr(args, 'reclassify_from', None):
                    progress.set_phase(f'复制频道 {index}/{len(records)} 本地缓存')
                    source = channel_folder(args.reclassify_from.resolve(), index, url)
                    remember(source, url)
                    reference_snapshot(url, folder)
                elif getattr(args, 'from_cache', False) and not resuming:
                    progress.set_phase(f'读取正式缓存 {index}/{len(records)}')
                    reference_snapshot(url, folder)
                if saved_channel(folder, url) is None:
                    raise ValueError('当前频道没有完整采集缓存；离线重判不会访问主页。')
                channel_args.command = 'analyze'
                channel_args.channel_json = folder / 'channel.json'
            # Sequential processing permits all channels to reuse one browser session.
            outcome = await process_channel(channel_args)
            rows[index - 1] = outcome['row']
            if outcome['status'] in ('private', 'not_found'):
                unavailable += 1
            else:
                succeeded += 1
        except (KeyboardInterrupt, asyncio.CancelledError):
            rows[index - 1]['预测结果'] = '已中断'
            write_results(results_path, rows, category=getattr(args, 'category_spec', None))
            raise
        except UserNotFoundError as exc:
            rows[index - 1] = empty_row(record, NOT_FOUND_RESULT)
            unavailable += 1
            write_json(folder / 'classification-status.json', {'status': 'user_not_found',
                'model_called': False, 'reason': str(exc)})
            progress.message(f'[{index}/{len(records)}] 用户不存在：{url}\nUserNotFoundError: {exc}', error=True)
        except RiskControlError as exc:
            rows[index - 1]['预测结果'] = f'失败：{type(exc).__name__}: {exc}'
            platform_name = '抖音' if 'douyin.com' in url else '快手'
            for remaining in rows[index:]:
                if remaining['预测结果'] not in terminal_results:
                    remaining['预测结果'] = f'未完成（{platform_name}风控）'
            write_results(results_path, rows, category=getattr(args, 'category_spec', None))
            progress.stopped = True
            progress.advance('风控停止')
            progress.message(f'{platform_name}风控，批量任务已停止：{url}\n{exc}\n结果 CSV：{results_path}', error=True)
            return 1
        except Exception as exc:
            rows[index - 1]['预测结果'] = f'失败：{type(exc).__name__}: {exc}'
            failed += 1
            progress.message(f"[{index}/{len(records)}] 失败：{url}\n{type(exc).__name__}: {exc}", error=True)
            # 即使标题排序/模型调用失败，也保存已成功采集的第一页全部封面。
            cached = saved_channel(folder, url)
            if cached and not getattr(args, 'offline', False):
                await archive_covers(cached, folder, page, progress.set_phase)
        write_results(results_path, rows, category=getattr(args, 'category_spec', None))
        progress.advance('完成' if index == len(records) else '准备下一频道')
    description = '缓存更新完成' if args.refresh_cache else '缓存补齐完成' if backfill_only else '批量处理完成'
    progress.set_phase('完成')
    progress.message(f"{description}：本轮成功 {succeeded}，失败 {failed}，账号不可判断 {unavailable}（私密或用户不存在）。\n结果 CSV：{results_path}")
    if archived_missing:
        progress.message(f'{archived_missing}张封面仍缺失，具体原因保存在各频道archive-status.json；没有为此重访作者主页。', error=True)
    evaluated = [row for row in rows if row['人工标注'] in predictions and row['预测结果'] in predictions]
    if evaluated:
        matches = sum(row['预测结果'] == row['人工标注'] for row in evaluated)
        progress.message(f'有明确人工标注且预测成功的频道：{len(evaluated)}；二类标签一致：{matches}/{len(evaluated)}。')
    return 1 if failed else 0


async def main(args):
    if args.max_videos > 128:
        raise ValueError('--top-videos 最大为128。')
    if hasattr(args, 'image_side'):
        if not 64 <= args.image_side <= 2048:
            raise ValueError('API 配置 image_side 需为 64..2048。')
    if args.command == 'batch':
        return await run_batch(args)
    args.output = create_run_dir(args.output)
    if getattr(args, 'category_spec', None):
        write_json(args.output / 'category.json', args.category_spec)
    if getattr(args, 'api_config', None):
        write_json(args.output / 'api-config.json', args.api_config)
    async with Progress(1) as progress:
        args.progress = progress
        try:
            outcome = await process_channel(args)
        except Exception as exc:
            if args.command in ('run', 'analyze'):
                url = getattr(args, 'url', str(getattr(args, 'channel_json', '')))
                prediction = NOT_FOUND_RESULT if isinstance(exc, UserNotFoundError) else f'失败：{type(exc).__name__}: {exc}'
                write_results(args.output / 'results.csv', [empty_row({'url': url}, prediction)], category=getattr(args, 'category_spec', None))
            raise
        if outcome:
            results_path = args.output / 'results.csv'
            write_results(results_path, [outcome['row']], category=getattr(args, 'category_spec', None))
        progress.advance()
    if outcome:
        print(f'结果 CSV：{results_path.resolve()}', flush=True)
    else:
        print(f'采集目录：{args.output.resolve()}', flush=True)
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    args = parser().parse_args()
    try:
        sys.exit(asyncio.run(main(args)))
    except KeyboardInterrupt:
        print('已停止；浏览器会话保留在项目内。', file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        sys.exit(1)
