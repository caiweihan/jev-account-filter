import csv
import json
from pathlib import Path
from .category import category_labels

RESULT_COLUMNS = ['账户名称', '频道网址', '预测结果', '频道概率', '人工标注', '预测与标注不符', '最可能的视频']


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


def create_experiment_dir(directory):
    directory = Path(directory)
    if directory.exists() and (not directory.is_dir() or any(directory.iterdir())):
        raise ValueError(f'输出目录已存在且非空：{directory}；请换一个实验名称，批量续跑请使用 --resume。')
    directory.mkdir(parents=True, exist_ok=True)
    return directory
