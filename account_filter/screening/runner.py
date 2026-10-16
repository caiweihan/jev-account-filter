"""Read a dataset and call the model; never import a browser or collector."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from .classifier import build_request, build_title_request, rank_titles, call_model_api, normalize_result
from ..category import load_category, saved_category
from .config import load_config, saved_config
from ..dataset import read_dataset, read_channel
from ..experiments import write_json, write_results, empty_row, result_row, create_experiment_dir, label_text
from ..progress import Progress


def set_phase(args, phase):
    if getattr(args, 'progress', None):
        args.progress.set_phase(phase)


async def model_call(args, payload, preview, stem):
    """续跑只复用相同问题和证据的已保存响应，失败的API请求没有成功响应可复用。"""
    preview_path = args.output / f'{stem}-request-preview.json' if stem == 'title' else args.output / 'request-preview.json'
    response_path = args.output / f'{stem}-model-response.json' if stem == 'title' else args.output / 'model-response.json'
    hash_path = response_path.with_suffix('.sha256')
    endpoint = args.endpoint
    preview = {**preview, 'endpoint': endpoint}
    signature = hashlib.sha256(json.dumps({'endpoint': endpoint, 'payload': payload}, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
    cached = None
    if getattr(args, 'resume', False) and response_path.is_file():
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
    # 保留旧原始响应供检查，但新请求成功前将已保存响应标为未完成，避免失败后误用旧结果。
    hash_path.write_text('pending:' + signature, encoding='ascii')
    raw = await call_model_api(payload, args.api, endpoint=endpoint,
        api_key_env=args.api_key_env,
        timeout=getattr(args, 'timeout_seconds', 120))
    write_json(response_path, raw)
    hash_path.write_text(signature, encoding='ascii')
    return raw


async def process_channel(args):
    category = args.category_spec
    channel, root = read_channel(args.record, args.dataset_root)
    if channel.get('user_not_found') or channel.get('is_private'):
        prediction = '用户不存在' if channel.get('user_not_found') else '无法判断（私密账号）'
    elif not channel['videos']:
        prediction = category['negative_label']
    else:
        prediction = None
    if prediction is not None:
        write_json(args.output / 'classification-status.json', {'model_called': False, 'reason': prediction})
        return {'status': 'success', 'row': empty_row({'url': channel['url'], 'name': channel['name'], 'true_label': args.true_label}, prediction)}
    for video in channel['videos']:
        if video.get('cover_path'):
            video['cover_path'] = str((root / video['cover_path']).resolve())
    write_json(args.output / 'channel.json', channel)
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
    title_raw = await model_call(args, title_payload, title_preview, 'title')
    ranked = rank_titles(title_raw, title_selection)
    selected = ranked[:args.max_videos]
    write_json(args.output / 'title-ranking.json', {'videos': ranked, 'selected_ids': [v['id'] for v in selected]})
    set_phase(args, '读取候选封面')
    for video in selected:
        cover = root / (video.get('cover_path') or '__missing__')
        if cover.is_file():
            video['cover_path'] = str(cover.resolve())
        else:
            video.pop('cover_path', None)
            channel['warnings'].append(f"候选 {video['id']} 缺少已采集封面，仅使用标题。")
    write_json(args.output / 'selected-videos.json', {'videos': selected, 'warnings': channel['warnings']})
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
    raw = await model_call(args, payload, preview, 'video')
    result = normalize_result(raw, selection, channel, category=category)
    row = result_row(result, getattr(args, 'true_label', ''), category=category)
    return {'status': 'success', 'row': row}



async def run(args):
    resume = args.resume
    output = resume.resolve() if resume else create_experiment_dir(args.output).resolve()
    source = output / 'dataset-source.json'
    dataset_root = args.data.resolve() if args.data else Path(json.loads(source.read_text(encoding='utf-8'))['directory'])
    records = read_dataset(dataset_root)
    category = load_category(args.category) if args.category else saved_category(output)
    config = load_config(args.config) if args.config else saved_config(output)
    if not category or not config:
        raise ValueError('筛选必须明确提供 --config 和 --category；续跑可读取实验配置。')
    top = args.top_videos
    if resume:
        old = json.loads(source.read_text(encoding='utf-8'))
        if [[r['platform'], r['account_id']] for r in records] != old['identities']:
            raise ValueError('续跑数据集的账户或顺序已改变，请建立新实验。')
        previous = saved_category(output)
        if previous != category or saved_config(output) != config:
            raise ValueError('续跑不能更换模型或类别配置，请建立新实验。')
        if top is not None and top != old['top_videos']:
            raise ValueError('续跑不能改变候选数量。')
        top = old['top_videos']
    top = top or 5
    write_json(source, {'directory': str(dataset_root), 'top_videos': top,
                        'identities': [[r['platform'], r['account_id']] for r in records]})
    write_json(output / 'category.json', category)
    write_json(output / 'api-config.json', config)
    result_path = output / 'results.csv'
    if resume:
        with result_path.open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) != len(records) or any(row['频道网址'] != r['url'] for row,r in zip(rows,records)):
            raise ValueError('结果与数据集账户不匹配。')
    else:
        rows = [empty_row({'url': r['url'], 'name': r['name'], 'true_label': label_text(r['annotation'],category)}) for r in records]
    write_results(result_path, rows, category)
    terminal = (category['positive_label'], category['negative_label'], '用户不存在', '无法判断（私密账号）')
    failed = 0
    async with Progress(len(records)) as progress:
        progress.start_at(sum(row['预测结果'] in terminal for row in rows))
        for index, record in enumerate(records):
            if resume and rows[index]['预测结果'] in terminal:
                continue
            folder = output / 'intermediate' / f'{index+1:04d}'
            call = argparse.Namespace(**{**config, 'category_spec': category, 'record': record,
                'dataset_root': dataset_root, 'true_label': label_text(record['annotation'],category),
                'max_videos': top, 'output': folder, 'dry_run': args.dry_run, 'resume': bool(resume), 'progress': progress})
            try:
                outcome = await process_channel(call)
                rows[index] = outcome['row']
            except Exception as exc:
                rows[index]['预测结果'] = f'失败：{type(exc).__name__}: {exc}'
                failed += 1
                progress.message(f'[{index+1}/{len(records)}] {rows[index]["预测结果"]}', error=True)
            write_results(result_path, rows, category)
            progress.advance()
    print(f'结果 CSV：{result_path}')
    return 1 if failed else 0
