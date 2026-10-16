"""从结果 CSV 和本地快照生成可交互的离线 HTML；不采集、不调用 API。"""
import argparse
import csv
import hashlib
import importlib
import json
import math
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from .category import resolve_category, category_labels

COLLECTED_DATA = Path(__file__).resolve().parents[1] / 'data' / 'channels'


def score(value):
    if value is None or not str(value).strip():
        return None
    n = float(value)
    if not math.isfinite(n) or not 0 <= n <= 1:
        raise ValueError(f'无效概率：{value!r}')
    return n


def identity(url):
    parsed = urlsplit(url)
    return parsed.hostname, parsed.path.rstrip('/')


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return {}


def relative_file(path, root):
    """只引用实验目录或项目正式缓存中的本地文件，不使用远程封面地址。"""
    try:
        resolved = path.resolve()
        if not (resolved.is_relative_to(root.resolve()) or resolved.is_relative_to(COLLECTED_DATA.resolve())):
            return None
        return Path(os.path.relpath(resolved, root.resolve())).as_posix() if resolved.is_file() else None
    except (OSError, ValueError):
        return None


def load_rows(csv_path, labels=None):
    labels = labels or category_labels(resolve_category(csv_path.parent))
    root = csv_path.parent
    snapshots = {}
    for folder in sorted((root / 'intermediate').glob('*')):
        channel = read_json(folder / 'channel.json')
        if channel.get('url'):
            snapshots[identity(channel['url'])] = (folder, channel)
    with csv_path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        required = {'账户名称', '频道网址', '预测结果', '人工标注', '频道概率'}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError('CSV 缺少必要列：' + '、'.join(sorted(required - set(reader.fieldnames or []))))
        ranks = sorted(int(m[1]) for name in reader.fieldnames
                       if (m := re.fullmatch(r'视频(\d+)分数', name)))
        rows = []
        for index, raw in enumerate(reader, 1):
            try:
                p = score(raw['频道概率'])
                videos = [{'rank': rank, 'p': score(raw.get(f'视频{rank}分数')),
                           'url': raw.get(f'视频{rank}链接', '')} for rank in ranks]
            except ValueError as exc:
                raise ValueError(f'CSV 第 {index + 1} 行：{exc}') from exc
            videos = [v for v in videos if v['p'] is not None or v['url']]
            folder, channel = snapshots.get(identity(raw['频道网址']), (None, {}))
            by_url = {identity(v.get('url', '')): v for v in channel.get('videos', [])}
            ranking = read_json(folder / 'title-ranking.json') if folder else {}
            title_scores = {v['id']: v.get('title_probability') for v in ranking.get('videos', [])}
            for video in videos:
                cached = by_url.get(identity(video['url']), {})
                video['title'] = cached.get('title', '')
                video['title_p'] = title_scores.get(cached.get('id'))
                video['cover'] = None
                if folder:
                    for cover in [folder / (cached.get('cover_path') or '__missing__'),
                                  folder / 'covers' / f"{cached.get('id', '__missing__')}.jpg"]:
                        if local := relative_file(cover, root):
                            video['cover'] = local
                            break
            comparable = raw['人工标注'] in labels and raw['预测结果'] in labels
            values = [v['p'] for v in videos if v['p'] is not None]
            rows.append({'id': index, 'name': raw['账户名称'], 'url': raw['频道网址'],
                         'account_id': raw.get('账户id', ''), 'platform': raw.get('平台', ''),
                         'manual': raw['人工标注'], 'prediction': raw['预测结果'], 'p': p,
                         'comparable': comparable, 'wrong': comparable and raw['人工标注'] != raw['预测结果'],
                         'max': max(values) if values else None,
                         'mean': sum(values) / len(values) if values else None,
                         'gap': max(values) - p if values and p is not None else None,
                         'spread': values[0] - values[1] if len(values) > 1 else None,
                         'videos': videos, 'bio': channel.get('bio', ''),
                         'page_count': len(channel['videos']) if 'videos' in channel else None,
                         'no_posts': bool(channel.get('no_posts')),
                         'snapshot': relative_file(folder / 'channel.json', root) if folder else None})
    if not rows:
        raise ValueError('CSV 没有数据行。')
    return rows, ranks


def summarize(rows, labels):
    comparable = [r for r in rows if r['comparable']]
    scored = [r for r in comparable if r['p'] is not None]
    wrong = [r for r in comparable if r['wrong']]
    matrix = [[sum(r['manual'] == a and r['prediction'] == b for r in comparable)
               for b in labels] for a in labels]
    tp = matrix[0][0]
    # 明确正负标注的二元指标中排除人工“疑难”；三类一致率仍包括它。
    predicted_positive = sum(r['prediction'] == labels[0] for r in comparable if r['manual'] != labels[1])
    actual_positive = sum(r['manual'] == labels[0] for r in comparable)
    return {'total': len(rows), 'comparable': len(comparable), 'matched': len(comparable)-len(wrong),
            'mismatch': len(wrong), 'matrix': matrix,
            'accuracy': (len(comparable)-len(wrong))/len(comparable) if comparable else None,
            'precision': tp/predicted_positive if predicted_positive else None,
            'recall': tp/actual_positive if actual_positive else None,
            'missing_p': sum(r['p'] is None for r in rows),
            'no_posts': sum(r['no_posts'] for r in rows),
            'missing_cover': sum(not v['cover'] for r in rows for v in r['videos']),
            'high_confidence_mismatch': sum(r['wrong'] and (r['p'] >= .95 or r['p'] <= .05) for r in scored),
            'manual_counts': dict(Counter(r['manual'] for r in comparable)),
            'wrong_manual_counts': dict(Counter(r['manual'] for r in wrong))}


def generate(csv_path, output=None, *, category=None):
    csv_path = Path(csv_path).resolve()
    output = Path(output).resolve() if output else csv_path.with_name('analysis.html')
    if output == csv_path:
        raise ValueError('HTML 不能覆盖输入 CSV。')
    category = resolve_category(csv_path.parent, category)
    labels = category_labels(category)
    rows, ranks = load_rows(csv_path, labels)
    # HTML 可以放到其它目录，本地封面/快照链接相对输出位置重新计算。
    if output.parent != csv_path.parent:
        import os
        for row in rows:
            for target in [row, *row['videos']]:
                field = 'snapshot' if target is row else 'cover'
                if target.get(field):
                    target[field] = Path(os.path.relpath(csv_path.parent / target[field], output.parent)).as_posix()
    payload = {'rows': rows, 'ranks': ranks, 'labels': labels, 'summary': summarize(rows, labels),
               'source': csv_path.parent.name + '/' + csv_path.name,
               'sha256': hashlib.sha256(csv_path.read_bytes()).hexdigest(),
               'generated': datetime.now().astimezone().isoformat(timespec='seconds')}
    payload['category'] = {key: category[key] for key in ('id', 'name', 'report_extension') if key in category}
    extension = report_extension(payload)
    if extension:
        extension.augment_payload(payload, csv_path, output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(assemble_html(payload), encoding='utf-8')
    return output, payload['summary']


def report_extension(payload):
    module = payload.get('category', {}).get('report_extension')
    if not module:
        return None
    if not module.startswith('account_filter.tasks.'):
        raise ValueError('报告扩展必须位于 account_filter.tasks 下。')
    return importlib.import_module(module)


def assemble_html(payload):
    template = (Path(__file__).parent / 'templates/analysis.html').read_text(encoding='utf-8')
    scripts = '\n'.join((Path(__file__).parent / 'templates' / name).read_text(encoding='utf-8')
                        for name in ('analysis-extra.js', 'analysis-cluster.js', 'analysis-evaluation.js'))
    template = template.replace('__ANALYSIS_SCRIPTS__', scripts)
    extension = report_extension(payload)
    components = extension.components() if extension else {}
    for slot in ('top', 'bottom', 'evidence', 'scripts', 'nav', 'style'):
        template = template.replace(f'__TASK_{slot.upper()}__', components.get(slot, ''))
    # Escaping keeps supplied CSV text inside the JSON data block, never executable markup.
    data = json.dumps(payload, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c').replace('&', '\\u0026')
    return template.replace('__REPORT_DATA__', data)


def main():
    parser = argparse.ArgumentParser(description='从结果 CSV 生成离线交互分析 HTML，不访问平台或 API')
    parser.add_argument('results_csv', type=Path)
    parser.add_argument('--output', type=Path, help='默认保存在 CSV 同目录的 analysis.html')
    parser.add_argument('--category', help='分类配置名称或 TOML；没有实验分类快照时必须指定')
    args = parser.parse_args()
    try:
        output, summary = generate(args.results_csv, args.output, category=args.category)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'{type(exc).__name__}: {exc}\n')
    print(f"已生成：{output}\n频道 {summary['total']}；可对照 {summary['comparable']}；不符 {summary['mismatch']}。")


if __name__ == '__main__':
    main()
