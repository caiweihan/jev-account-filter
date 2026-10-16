"""The source-neutral, versioned boundary between collection and screening."""
import csv
import json
from pathlib import Path
from .experiments import write_json

FIELDS = ('platform', 'account_id', 'url', 'name', 'annotation', 'path', 'status', 'error')


def local_path(root, value):
    root = Path(root).resolve()
    value = Path(value)
    target = (root / value).resolve()
    if value.is_absolute() or not target.is_relative_to(root):
        raise ValueError(f'数据路径必须位于数据集目录内：{value}')
    return target


def read_dataset(root):
    root = Path(root).resolve()
    metadata = json.loads((root / 'dataset.json').read_text(encoding='utf-8-sig'))
    if metadata.get('schema_version') != 1:
        raise ValueError('不支持的数据格式；schema_version 必须为 1。')
    manifest = local_path(root, metadata.get('manifest', 'manifest.csv'))
    with manifest.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if not set(FIELDS).issubset(reader.fieldnames or []):
            raise ValueError('manifest.csv 缺少字段：' + ', '.join(FIELDS))
        records = list(reader)
    if not records:
        raise ValueError('数据集没有账户。')
    seen = set()
    for row in records:
        key = row['platform'], row['account_id']
        if not all(key) or key in seen:
            raise ValueError(f'账户身份为空或重复：{key}')
        seen.add(key)
        local_path(root, row['path'])
    return records


def read_channel(record, root):
    if record['status'] not in ('ready', 'user_not_found', 'private'):
        raise ValueError('该账户采集未完成：' + (record.get('error') or record['status']))
    path = local_path(root, record['path'])
    channel = json.loads(path.read_text(encoding='utf-8-sig'))
    for key in ('platform', 'id', 'url', 'name', 'bio', 'videos'):
        if key not in channel:
            raise ValueError(f'{path.name} 缺少字段 {key}')
    if (str(channel['platform']), str(channel['id']), channel['url']) != (record['platform'], record['account_id'], record['url']):
        raise ValueError('账户 JSON 与 manifest 身份不一致。')
    if not isinstance(channel['videos'], list):
        raise ValueError('videos 必须为数组。')
    if any(not isinstance(channel[k], str) for k in ('platform', 'id', 'url', 'name', 'bio')):
        raise ValueError('账户文本字段必须为字符串。')
    ids = set()
    for video in channel['videos']:
        if not all(isinstance(video.get(k), str) for k in ('id', 'title', 'url')) or not video['id'] or video['id'] in ids:
            raise ValueError('视频必须有唯一 id、title 和 url。')
        ids.add(video['id'])
        if video.get('content_type', 'video') != 'video':
            raise ValueError('videos 中只能包含视频，图文请放入 excluded_posts。')
        if video.get('cover_path'):
            local_path(path.parent, video['cover_path'])
    channel.setdefault('warnings', [])
    return channel, path.parent


def write_dataset(root, records):
    root = Path(root)
    write_json(root / 'dataset.json', {'schema_version': 1, 'manifest': 'manifest.csv'})
    temporary = root / 'manifest.csv.tmp'
    with temporary.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)
    temporary.replace(root / 'manifest.csv')
