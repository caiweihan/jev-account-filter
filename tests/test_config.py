import argparse
import asyncio
import json
import httpx
import pytest

from account_filter.screening import runner as cli
from account_filter.screening.api import call_model_api
from account_filter.screening.config import load_config
from task_helpers import parse_task_args

BASE = {'model': 'test-vision', 'api': 'chat', 'endpoint': 'https://provider.example/v1/chat/completions', 'api_key_env': 'TEST_API_KEY'}


def config_file(path, **overrides):
    path.write_text('\n'.join(f'{k} = {json.dumps(v)}' for k, v in {**BASE, **overrides}.items()), encoding='utf-8')
    return path


@pytest.mark.parametrize('field', ['model', 'api', 'endpoint', 'api_key_env'])
def test_missing_service_identity_never_gets_a_provider_default(tmp_path, field):
    values = {k: v for k, v in BASE.items() if k != field}
    path = tmp_path / 'missing.toml'
    path.write_text('\n'.join(f'{k} = {json.dumps(v)}' for k, v in values.items()))
    with pytest.raises(ValueError, match=field):
        load_config(path)


@pytest.mark.parametrize('overrides', [{'api': 'other'}, {'context_budget': 0}, {'image_side': 32},
    {'image_token_estimate': True}, {'timeout_seconds': -1}, {'endpoint': 'http://example.com/api'},
    {'model': ''}, {'endpoint': ''}, {'context_buget': 1000}])
def test_invalid_config_fails_before_network(tmp_path, overrides):
    with pytest.raises(ValueError):
        load_config(config_file(tmp_path / 'invalid.toml', **overrides))


def test_explicit_config_changes_request_and_secret_source(tmp_path, monkeypatch):
    path = config_file(tmp_path / 'other.toml', model='other-vision-model', timeout_seconds=30,
                       context_budget=12000, image_side=1024, image_token_estimate=2000)
    args = argparse.Namespace(**load_config(path))
    monkeypatch.setenv('TEST_API_KEY', 'other-test-key')
    def handler(request):
        assert str(request.url) == BASE['endpoint']
        assert request.headers['authorization'] == 'Bearer other-test-key'
        assert 'x-title' not in request.headers
        assert json.loads(request.content)['model'] == 'other-vision-model'
        assert request.extensions['timeout']['read'] == 30
        return httpx.Response(200, json={'choices': [{'message': {'content': '{"answers":{}}'}}]})
    result = asyncio.run(call_model_api({'model': args.model}, args.api,
        transport=httpx.MockTransport(handler), endpoint=args.endpoint,
        api_key_env=args.api_key_env, timeout=args.timeout_seconds))
    assert result['answers'] == {}
    assert args.context_budget == 12000 and args.image_side == 1024


def test_changed_endpoint_and_failed_request_never_reuse_old_response(tmp_path, monkeypatch):
    calls = []
    async def model(payload, api, **kwargs):
        calls.append(kwargs['endpoint'])
        if len(calls) == 2:
            raise RuntimeError('new service failed')
        return {'answers': {'v001': {'type': 'noul', 'noul': .9}}}
    monkeypatch.setattr(cli, 'call_model_api', model)
    args = argparse.Namespace(output=tmp_path, api='decisions', resume=True,
                              endpoint='https://provider.example/decisions', api_key_env='TEST_API_KEY')
    payload = {'model': 'test', 'state': ['title'], 'questions': {'v001': {}}}
    preview = {'model': 'test', 'api': 'decisions', 'state_text': ['title'], 'questions': payload['questions']}
    async def check():
        await cli.model_call(args, payload, preview, 'title')
        args.endpoint = 'https://other.example/decisions'
        with pytest.raises(RuntimeError):
            await cli.model_call(args, payload, preview, 'title')
        await cli.model_call(args, payload, preview, 'title')
        await cli.model_call(args, payload, preview, 'title')
    asyncio.run(check())
    assert len(calls) == 3


def test_matching_explicit_endpoint_reuses_response(tmp_path, monkeypatch):
    import hashlib
    endpoint = 'https://provider.example/decisions'
    payload = {'model': 'test', 'state': ['title'], 'questions': {}}
    preview = {'model': 'test', 'api': 'decisions', 'state_text': ['title'], 'questions': {}, 'endpoint': endpoint}
    cli.write_json(tmp_path / 'title-request-preview.json', preview)
    cli.write_json(tmp_path / 'title-model-response.json', {'answers': {}})
    signature = hashlib.sha256(json.dumps({'endpoint': endpoint, 'payload': payload}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    (tmp_path / 'title-model-response.sha256').write_text(signature)
    async def forbidden(*args, **kwargs):
        pytest.fail('Matching requests must reuse their existing response.')
    monkeypatch.setattr(cli, 'call_model_api', forbidden)
    args = argparse.Namespace(output=tmp_path, api='decisions', resume=True, endpoint=endpoint)
    assert asyncio.run(cli.model_call(args, payload, preview, 'title')) == {'answers': {}}
