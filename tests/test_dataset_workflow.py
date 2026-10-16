import argparse
import asyncio
import csv
import hashlib
import json
from pathlib import Path
from contextlib import asynccontextmanager

import pytest
from PIL import Image
from account_filter import __main__ as cli
from account_filter.dataset import read_channel, read_dataset, write_dataset
from account_filter.experiments import write_json, create_experiment_dir
from account_filter.screening import runner
from task_helpers import API_PATH, TASK


@pytest.fixture
def dataset(tmp_path):
    root = tmp_path / 'data'
    folder = root / 'accounts/a'
    folder.mkdir(parents=True)
    Image.new('RGB', (12, 12)).save(folder / 'cover.jpg')
    channel = {'platform': 'custom-source', 'id': 'a', 'url': 'https://example.org/account/a',
               'name': 'Example', 'bio': 'Example biography', 'videos': [
                   {'id': 'v', 'title': 'Example title', 'url': 'https://example.org/v',
                    'content_type': 'video', 'cover_path': 'cover.jpg'}]}
    write_json(folder / 'channel.json', channel)
    records = [{'platform': channel['platform'], 'account_id': 'a', 'url': channel['url'],
                'name': channel['name'], 'annotation': TASK['negative_label'],
                'path': 'accounts/a/channel.json', 'status': 'ready', 'error': ''}]
    write_dataset(root, records)
    return root, records


def model_reply(payload):
    if 'channel' not in payload['questions']:
        return {'answers': {'v001': {'type': 'noul', 'noul': .9}}}
    return {'answers': {
        'channel': {'type': 'choice', 'choice': 'yes', 'probabilities': {'yes': .9, 'no': .1}},
        'channel_probability': {'type': 'noul', 'noul': .8},
        'v001': {'type': 'noul', 'noul': .85},
        'best_video': {'type': 'choice', 'choice': 'v001', 'probabilities': {'v001': .9, 'none': .1}}}}


def test_custom_dataset_screening_and_resume_are_read_only(dataset, tmp_path, monkeypatch):
    root, _ = dataset
    original = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
    calls = []
    async def model(payload, *args, **kwargs):
        calls.append(payload)
        assert TASK['negative_label'] not in json.dumps(payload, ensure_ascii=False)
        return model_reply(payload)
    monkeypatch.setattr(runner, 'call_model_api', model)
    output = tmp_path / 'results/experiment'
    args = cli.parser().parse_args(['screen', '--data', str(root), '--output', str(output),
                                    '--config', str(API_PATH), '--category', 'sign-language'])
    assert asyncio.run(cli.main(args)) == 0
    assert len(calls) == 2
    rows = list(csv.DictReader((output / 'results.csv').open(encoding='utf-8-sig')))
    assert rows[0]['预测结果'] == TASK['positive_label']
    assert rows[0]['预测与标注不符'] == '预测与标注不符'
    assert (output / 'intermediate/0001/title-ranking.json').is_file()
    assert asyncio.run(cli.main(cli.parser().parse_args(['screen', '--resume', str(output)]))) == 0
    assert len(calls) == 2
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == h for p,h in original.items())
    with pytest.raises(ValueError, match='非空'):
        create_experiment_dir(output)


def test_inference_failure_is_retried_without_repeating_successful_title_call(dataset, tmp_path, monkeypatch):
    root, _ = dataset
    calls = []
    async def model(payload, *args, **kwargs):
        calls.append(payload)
        if len(calls) == 2:
            raise ValueError('HTTP 503')
        return model_reply(payload)
    monkeypatch.setattr(runner, 'call_model_api', model)
    output = tmp_path / 'experiment'
    args = cli.parser().parse_args(['screen', '--data', str(root), '--output', str(output),
                                    '--config', str(API_PATH), '--category', 'sign-language'])
    assert asyncio.run(cli.main(args)) == 1
    assert asyncio.run(cli.main(cli.parser().parse_args(['screen', '--resume', str(output)]))) == 0
    assert len(calls) == 3


def test_dataset_rejects_identity_path_and_nonvideo_errors(dataset):
    root, records = dataset
    assert read_channel(read_dataset(root)[0], root)[0]['id'] == 'a'
    path = root / records[0]['path']
    channel = json.loads(path.read_text(encoding='utf-8'))
    channel['videos'][0]['cover_path'] = '../../../outside.jpg'
    write_json(path, channel)
    with pytest.raises(ValueError, match='路径'):
        read_channel(records[0], root)
    channel['videos'][0].pop('cover_path')
    channel['videos'][0]['content_type'] = 'image'
    write_json(path, channel)
    with pytest.raises(ValueError, match='只能包含视频'):
        read_channel(records[0], root)


def test_collection_resume_only_retries_failed_rows(tmp_path, monkeypatch):
    from account_filter.collection import runner as collection
    root = tmp_path / 'collected'
    source = tmp_path / 'input.csv'
    source.write_text('主页网址\nhttps://www.douyin.com/user/fictional-a\nhttps://www.douyin.com/user/fictional-b\n', encoding='utf-8')
    calls = []
    @asynccontextmanager
    async def session(*args, **kwargs): yield object()
    async def collect(url, output, *args, **kwargs):
        calls.append(url)
        if len(calls) == 2: raise ValueError('temporary failure')
        c = {'platform': 'douyin', 'id': url.rsplit('/',1)[-1], 'url': url,
             'name': 'Example', 'bio': '', 'videos': [], 'no_posts': True}
        write_json(output / 'channel.json', c)
        return c
    async def archive(*args, **kwargs): return {'missing': []}
    monkeypatch.setattr(collection, 'browser_session', session)
    monkeypatch.setattr(collection, 'collect', collect)
    monkeypatch.setattr(collection, 'archive_covers', archive)
    args = cli.parser().parse_args(['collect', '--input-csv', str(source), '--output', str(root)])
    assert asyncio.run(cli.main(args)) == 1
    assert asyncio.run(cli.main(cli.parser().parse_args(['collect', '--resume', str(root)]))) == 0
    assert len(calls) == 3 and calls[0] != calls[-1]
    assert all(r['status'] == 'ready' for r in read_dataset(root))
