"""采集资料的正式缓存：data/channels/<平台>/<频道ID>/，与每轮实验结果分离。"""
import argparse
import csv
import json
import shutil
from pathlib import Path

from .collector import profile_info, saved_channel, save_channel

DEFAULT_CACHE = Path(__file__).resolve().parents[1] / 'data' / 'channels'


def channel_dir(url):
    platform, channel_id = profile_info(url)
    return DEFAULT_CACHE / platform / channel_id


def copy_snapshot(source, output, url):
    """只复制采集JSON与封面，不复制模型答案、不移动或改写源文件。"""
    source, output = Path(source).resolve(), Path(output).resolve()
    channel = saved_channel(source, url)
    if channel is None:
        raise ValueError(f'频道缓存缺失或采集不完整：{source}；不会访问主页。')
    channel.setdefault('warnings', [])
    for video in channel.get('videos', []):
        filename = f"{video['id']}.jpg"
        if Path(filename).name != filename:
            raise ValueError('缓存作品ID包含非法路径字符。')
        cover = source / (video.get('cover_path') or f'covers/{filename}')
        destination = output / 'covers' / filename
        if cover.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            if cover.resolve() != destination.resolve() and (not destination.is_file() or
                    cover.stat().st_size != destination.stat().st_size or
                    cover.stat().st_mtime_ns != destination.stat().st_mtime_ns):
                shutil.copy2(cover, destination)
            video['cover_path'] = str(destination.relative_to(output))
        else:
            video.pop('cover_path', None)
    channel['cache_source'] = str(source)
    for name in ('first-page-posts.json', 'post-type-status.json'):
        path = source / name
        if path.is_file() and path.resolve() != (output / name).resolve():
            output.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, output / name)
    save_channel(channel, output)
    return channel


def remember(source, url):
    return copy_snapshot(source, channel_dir(url), url)


def reference_snapshot(url, output):
    """实验只保存小型资料快照，封面引用正式缓存，不为每轮复制图片。"""
    source = channel_dir(url)
    channel = saved_channel(source, url)
    if channel is None:
        raise ValueError(f'频道缓存缺失或采集不完整：{source}；不会访问主页。')
    for video in channel.get('videos', []):
        path = source / (video.get('cover_path') or f"covers/{video['id']}.jpg")
        if path.is_file():
            video['cover_path'] = str(path.resolve())
        else:
            video.pop('cover_path', None)
    channel['cache_source'] = str(source.resolve())
    save_channel(channel, output)


def import_experiment(source):
    from .__main__ import channel_folder
    source = Path(source).resolve()
    rows = list(csv.DictReader((source / 'results.csv').open(encoding='utf-8-sig')))
    success, failures, covers, missing = 0, [], 0, 0
    for index, row in enumerate(rows, 1):
        try:
            channel = remember(channel_folder(source, index, row['频道网址']), row['频道网址'])
            success += 1
            folder = channel_dir(row['频道网址'])
            for v in channel.get('videos', []):
                present = bool(v.get('cover_path') and (folder / v['cover_path']).is_file())
                covers += present; missing += not present
        except (OSError, ValueError) as exc:
            failures.append({'url': row['频道网址'], 'error': str(exc)})
        if index % 100 == 0:
            print(f'导入采集缓存：{index}/{len(rows)}', flush=True)
    summary = {'source': str(source), 'directory': str(DEFAULT_CACHE), 'channels': success,
               'covers': covers, 'missing_covers': missing, 'failures': failures}
    DEFAULT_CACHE.parent.mkdir(parents=True, exist_ok=True)
    (DEFAULT_CACHE.parent / 'cache-import.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='将旧实验采集资料复制到正式缓存，不访问平台或调用模型')
    parser.add_argument('experiment', type=Path)
    args = parser.parse_args()
    result = import_experiment(args.experiment)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(1 if result['failures'] else 0)
