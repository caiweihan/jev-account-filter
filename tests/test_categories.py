import asyncio
import csv
import json
from pathlib import Path

import pytest

from account_filter import experiments as cli
from account_filter.category import load_category
from account_filter.screening.classifier import build_request, build_title_request
from account_filter.screening.config import load_config
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
