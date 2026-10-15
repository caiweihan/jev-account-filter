import asyncio
import csv
import json
from pathlib import Path

import pytest

from account_filter import __main__ as cli
from account_filter.category import load_category
from account_filter.classifier import build_request, build_title_request
from account_filter.config import load_config
from task_helpers import API_PATH, API_CONFIG
from account_filter.report import generate

PROJECT = Path(__file__).resolve().parents[1]
FITNESS = PROJECT / 'configs/categories/fitness.example.toml'


def test_category_controls_both_stages_and_keeps_account_data_out_of_titles(tmp_path):
    task = load_category(FITNESS)
    channel = {'platform': 'douyin', 'name': 'ACCOUNT_MARKER', 'bio': 'BIO_MARKER',
               'url': 'https://www.douyin.com/user/a',
               'videos': [{'id': '1', 'title': '深蹲训练', 'url': 'https://www.douyin.com/video/1'}]}
    for api in ('decisions', 'chat'):
        title, _ = build_title_request(channel, model='test', api=api, category=task,
                                       context_budget=API_CONFIG['context_budget'])
        video, _ = build_request(channel, tmp_path, model='test', api=api, category=task,
            max_videos=5, image_side=API_CONFIG['image_side'], context_budget=API_CONFIG['context_budget'],
            image_tokens=API_CONFIG['image_token_estimate'])
        assert 'ACCOUNT_MARKER' not in json.dumps(title) and 'BIO_MARKER' not in json.dumps(title)
        assert 'ACCOUNT_MARKER' in json.dumps(video) and 'BIO_MARKER' in json.dumps(video)
        assert 'fitness' in json.dumps(title) and 'fitness' in json.dumps(video)
        assert 'natural signing' not in json.dumps(title) + json.dumps(video)


def test_custom_category_pipeline_returns_configured_label_and_mismatch(tmp_path, monkeypatch):
    source = tmp_path / 'channel.json'
    channel = {'platform': 'douyin', 'name': '训练记录', 'url': 'https://www.douyin.com/user/a',
               'videos': [{'id': '1', 'title': '深蹲训练', 'url': 'https://www.douyin.com/video/1'}]}
    source.write_text(json.dumps(channel), encoding='utf-8')
    args = cli.parser().parse_args(['analyze', str(source), '--category', str(FITNESS), '--config', str(API_PATH)])
    args.output = tmp_path / 'run'
    args.offline = True
    args.true_label = '不是健身账户'
    calls = []
    async def model(payload, api, **kwargs):
        calls.append(payload)
        if 'channel' not in payload['questions']:
            return {'answers': {'v001': {'type': 'noul', 'noul': .9}}}
        return {'answers': {
            'channel': {'type': 'choice', 'choice': 'yes', 'probabilities': {'yes': .6, 'no': .4}},
            'channel_probability': {'type': 'noul', 'noul': .1},
            'v001': {'type': 'noul', 'noul': .8},
            'best_video': {'type': 'choice', 'choice': 'v001', 'probabilities': {'v001': .8, 'none': .2}},
        }}
    monkeypatch.setattr(cli, 'call_model_api', model)
    outcome = asyncio.run(cli.process_channel(args))
    assert len(calls) == 2
    assert outcome['row']['预测结果'] == '健身账户'  # Independent choice, despite p=.1.
    assert outcome['row']['频道概率'] == .1
    path = args.output / 'results.csv'
    cli.write_results(path, [outcome['row']], category=args.category_spec)
    row = next(csv.DictReader(path.open(encoding='utf-8-sig', newline='')))
    assert row['预测与标注不符'] == '预测与标注不符'


def test_resume_restores_category_and_skips_success_without_inference(tmp_path, monkeypatch):
    task = load_category(FITNESS)
    (tmp_path / 'category.json').write_text(json.dumps(task), encoding='utf-8')
    (tmp_path / 'api-config.json').write_text(json.dumps(API_CONFIG), encoding='utf-8')
    (tmp_path / 'reclassify-settings.json').write_text('{"offline":true}', encoding='utf-8')
    record = {'url': 'https://www.douyin.com/user/a', 'name': '训练记录', 'true_label': '健身账户'}
    cli.write_results(tmp_path / 'results.csv', [cli.empty_row(record, '健身账户')], category=task)
    args = cli.parser().parse_args(['batch', '--resume', str(tmp_path)])
    assert args.category_spec == task
    records = cli.batch_inputs(args)
    assert records[0]['true_label'] == '健身账户'
    async def forbidden(*args, **kwargs):
        pytest.fail('成功项不应再分类')
    monkeypatch.setattr(cli, 'process_channel', forbidden)
    assert asyncio.run(cli.run_batch(args)) == 0
    other = cli.parser().parse_args(['batch', '--resume', str(tmp_path), '--category', 'sign-language'])
    with pytest.raises(ValueError, match='续跑不能更换'):
        cli.prepare_batch(other, records)


def test_custom_category_empty_account_does_not_call_model(tmp_path, monkeypatch):
    source = tmp_path / 'channel.json'
    source.write_text(json.dumps({'platform': 'douyin', 'name': '空账户',
        'url': 'https://www.douyin.com/user/a', 'videos': [], 'no_posts': True}), encoding='utf-8')
    args = cli.parser().parse_args(['analyze', str(source), '--category', str(FITNESS), '--config', str(API_PATH)])
    args.output = tmp_path / 'run'
    async def forbidden(*args, **kwargs):
        pytest.fail('空账户不应调用模型')
    monkeypatch.setattr(cli, 'call_model_api', forbidden)
    assert asyncio.run(cli.process_channel(args))['row']['预测结果'] == '不是健身账户'


def test_custom_report_uses_custom_labels(tmp_path):
    task = load_category(FITNESS)
    (tmp_path / 'category.json').write_text(json.dumps(task), encoding='utf-8')
    row = cli.empty_row({'url': 'https://www.douyin.com/user/a', 'true_label': '不是健身账户'}, '健身账户')
    row['频道概率'] = '.7'
    csv_path = tmp_path / 'results.csv'
    cli.write_results(csv_path, [row], category=task)
    html, summary = generate(csv_path)
    payload = json.loads(html.read_text(encoding='utf-8').split('<script id="report-data" type="application/json">')[1].split('</script>')[0])
    assert payload['labels'] == ['健身账户', '疑难', '不是健身账户']
    assert summary['mismatch'] == 1 and summary['comparable'] == 1


def test_loopback_chat_is_supported_without_a_provider_default(tmp_path):
    config = tmp_path / 'local.toml'
    config.write_text('model="test"\napi_key_env="TEST_KEY"\napi="chat"\nendpoint="http://127.0.0.1:8000/v1/chat/completions"\n')
    assert load_config(config)['endpoint'].startswith('http://127.0.0.1:8000/')
    config.write_text('model="test"\napi_key_env="TEST_KEY"\napi="chat"\nendpoint="http://remote.example/v1/chat/completions"\n')
    with pytest.raises(ValueError):
        load_config(config)
