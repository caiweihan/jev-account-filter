import asyncio
import json
from pathlib import Path

import httpx
import pytest
from PIL import Image

from account_filter.api import call_model_api
from task_helpers import build_request, normalize_result
from account_filter.collector import RiskControlError, check_risk_control, is_profile_response, parse_profile_payload, profile_id, import_cookies


@pytest.fixture
def channel(tmp_path):
    Image.new('RGB', (800, 400), 'white').save(tmp_path / 'cover.jpg')
    return {'platform': 'kuaishou', 'name': '虚构手语测试账号', 'bio': '用于测试的虚构简介', 'url': 'https://www.kuaishou.com/profile/abc',
            'videos': [{'id': 'a', 'title': '你好', 'url': 'https://www.kuaishou.com/short-video/a', 'cover_path': 'cover.jpg'},
                       {'id': 'b', 'title': '手语 谢谢', 'url': 'https://www.kuaishou.com/short-video/b'}]}


def result():
    return {'answers': {'channel': {'type': 'choice', 'choice': 'no', 'probabilities': {'yes': .4, 'no': .6}},
                        'channel_probability': {'type': 'noul', 'noul': .6}, 'v001': {'type': 'noul', 'noul': .3},
                        'v002': {'type': 'noul', 'noul': .9},
                        'best_video': {'type': 'choice', 'choice': 'v002', 'probabilities': {'v001': .1, 'v002': .85, 'none': .05}}}}


def test_profile_and_feed_shapes():
    name, videos = parse_profile_payload({'data': {'visionProfile': {'userProfile': {'profile': {'user_name': '测试', 'user_text': '简介'}}},
                                                   'visionProfilePhotoList': {'feeds': [{'photo': {'id': '3xx', 'caption': '标题', 'coverUrls': [{'url': 'https://x.kwimgs.com/c.jpg'}]}}]}}})
    assert name == {'name': '测试', 'bio': '简介'}
    assert videos[0]['id'] == '3xx' and videos[0]['title'] == '标题'
    assert videos[0]['cover_url'] == 'https://x.kwimgs.com/c.jpg'
    _, rest = parse_profile_payload({'result': 1, 'feeds': [{'photo': {'id': '3xy', 'caption': 'REST', 'cover_url': 'https://x.yximgs.com/c.jpg'}}]})
    assert rest[0]['title'] == 'REST'


def test_only_target_profile_responses():
    assert is_profile_response('https://www.kuaishou.com/rest/v/profile/feed?signature=x', {'user_id': 'abc'}, 'abc')
    assert not is_profile_response('https://www.kuaishou.com/rest/v/profile/feed', {'user_id': 'other'}, 'abc')
    assert not is_profile_response('https://www.kuaishou.com/graphql', {'operationName': 'visionSearchPhoto', 'variables': {'userId': 'abc'}}, 'abc')
    assert is_profile_response('https://www.kuaishou.com/graphql', {'operationName': 'visionProfile', 'variables': {'userId': 'abc'}}, 'abc')


def test_empty_works_server_error_reports_risk_instead_of_empty_channel():
    with pytest.raises(RiskControlError, match='服务器异常，稍后重试'):
        check_risk_control({'feed_error': True, 'videos': []}, '账号名称\n作品\n服务器异常，稍后重试')
    # 有作品时不把分页错误误判为“只有错误”；简介中引用文字也不是作品区错误。
    check_risk_control({'feed_error': True, 'videos': [{'id': 'a'}]}, '服务器异常，稍后重试')
    check_risk_control({'feed_error': False, 'videos': []}, '简介：服务器异常，稍后重试')
    with pytest.raises(RiskControlError, match='result:2'):
        check_risk_control({'feed_error': False, 'videos': []}, '{"result":2}')


@pytest.mark.parametrize('url', ['https://evil.com/profile/abc', 'https://www.kuaishou.com.evil.com/profile/abc', 'http://www.kuaishou.com/profile/abc', 'https://www.kuaishou.com/short-video/abc'])
def test_reject_non_profile_url(url):
    with pytest.raises(ValueError):
        profile_id(url)


def test_image_input_and_real_cover_budget(channel, tmp_path):
    request, selected = build_request(channel, tmp_path, model='openai/gpt-6-luna-decisions', image_side=128)
    images = [part for part in request['state'] if isinstance(part, dict)]
    assert len(images) == 1 and images[0]['image_url']['url'].startswith('data:image/jpeg;base64,')
    assert len(selected['videos']) == 2
    assert 'none' in request['questions']['best_video']['criteria']
    _, one = build_request(channel, tmp_path, model='test', max_videos=1)
    trimmed, limited = build_request(channel, tmp_path, model='test', context_budget=one['estimated_input_tokens'] + 100)
    assert len(limited['videos']) == 1
    assert set(trimmed['questions']) == {'channel', 'channel_probability', 'v001', 'best_video'}
    assert trimmed['questions']['channel']['type'] == 'choice'
    assert set(trimmed['questions']['channel']['criteria']) == {'yes', 'no'}
    assert set(trimmed['questions']['best_video']['criteria']) == {'v001', 'none'}
    with pytest.raises(ValueError):
        build_request(channel, tmp_path, model='test', context_budget=10)


def test_binary_prediction_and_choice_mapping(channel, tmp_path):
    _, selected = build_request(channel, tmp_path, model='test')
    normalized = normalize_result(result(), selected, channel)
    assert normalized['channel_label'] == 'no'
    assert normalized['most_likely_video']['id'] == 'b'
    raw = result()
    raw['answers']['best_video']['choice'] = 'none'
    assert normalize_result(raw, selected, channel)['most_likely_video'] is None


@pytest.mark.parametrize('choice,channel_p,video_p', [('yes', .01, .01), ('no', .99, .99)])
def test_channel_choice_is_independent_of_all_probabilities(channel, tmp_path, choice, channel_p, video_p):
    _, selected = build_request(channel, tmp_path, model='test')
    raw = result()
    raw['answers']['channel']['choice'] = choice
    # Deliberately make the choice distribution favor the opposite answer as well.
    raw['answers']['channel']['probabilities'] = {choice: .1, 'no' if choice == 'yes' else 'yes': .9}
    raw['answers']['channel_probability']['noul'] = channel_p
    for key in ('v001', 'v002'):
        raw['answers'][key]['noul'] = video_p
    normalized = normalize_result(raw, selected, channel)
    assert normalized['channel_label'] == choice
    assert normalized['channel_probability'] == channel_p
    assert 'threshold' not in normalized


@pytest.mark.parametrize('answer', [
    {'type': 'noul', 'noul': .9},
    {'type': 'choice', 'choice': 'uncertain', 'probabilities': {'yes': .5, 'no': .5}},
    {'type': 'choice', 'choice': 'yes', 'probabilities': {'yes': 1}},
    {'type': 'choice', 'choice': 'yes', 'probabilities': {'yes': .9, 'no': .9}},
])
def test_invalid_channel_decision_is_rejected(channel, tmp_path, answer):
    _, selected = build_request(channel, tmp_path, model='test')
    raw = result()
    raw['answers']['channel'] = answer
    with pytest.raises(ValueError, match='channel'):
        normalize_result(raw, selected, channel)


@pytest.mark.parametrize('bad', [float('nan'), 1.2, -1, True, '0.5'])
def test_malformed_probability_rejected(channel, tmp_path, bad):
    _, selected = build_request(channel, tmp_path, model='test')
    raw = result()
    raw['answers']['channel_probability']['noul'] = bad
    with pytest.raises(ValueError):
        normalize_result(raw, selected, channel)


def test_cookie_import_filters_unrelated_domains(tmp_path):
    path = tmp_path / 'cookies.json'
    path.write_text(json.dumps([{'name': 'test', 'value': 'secret', 'domain': '.kuaishou.com'},
                               {'name': 'other', 'value': 'private', 'domain': '.example.com'}]))
    assert len(import_cookies(path)) == 1


def test_wire_format_and_http_errors(channel, tmp_path, monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')
    payload, _ = build_request(channel, tmp_path, model='openai/gpt-6-luna-decisions')
    def handler(request):
        assert str(request.url) == 'https://openrouter.ai/api/alpha/decisions'
        assert request.headers['authorization'] == 'Bearer test-key'
        assert json.loads(request.content)['model'] == 'openai/gpt-6-luna-decisions'
        return httpx.Response(200, json=result())
    assert asyncio.run(call_model_api(payload, 'decisions', endpoint='https://openrouter.ai/api/alpha/decisions', api_key_env='OPENROUTER_API_KEY', transport=httpx.MockTransport(handler))) == result()
    with pytest.raises(ValueError, match='HTTP 401'):
        asyncio.run(call_model_api(payload, 'decisions', endpoint='https://openrouter.ai/api/alpha/decisions', api_key_env='OPENROUTER_API_KEY', transport=httpx.MockTransport(lambda r: httpx.Response(401))))
    with pytest.raises(ValueError, match='HTTP 429: 请求太频繁') as error:
        asyncio.run(call_model_api(payload, 'decisions', endpoint='https://openrouter.ai/api/alpha/decisions', api_key_env='OPENROUTER_API_KEY', transport=httpx.MockTransport(
            lambda r: httpx.Response(429, json={'error': {'message': '请求太频繁 test-key'}}))))
    assert 'test-key' not in str(error.value)


@pytest.mark.parametrize('api', ['decisions', 'chat'])
def test_original_text_and_cover_association_survive_missing_image(channel, tmp_path, api):
    channel['videos'][0].pop('cover_path')
    channel['videos'][1]['cover_path'] = 'cover.jpg'
    request, selection = build_request(channel, tmp_path, model='test', api=api)
    parts = request['state'] if api == 'decisions' else request['messages'][-1]['content']
    image_index = next(i for i, part in enumerate(parts) if isinstance(part, dict) and part.get('type') == 'image_url')
    prior_text = parts[image_index - 1]
    record = json.loads(prior_text if isinstance(prior_text, str) else prior_text['text'])
    assert record['key'] == 'v002' and record['title'] == '手语 谢谢'
    assert not selection['videos'][0]['has_cover']
    assert selection['videos'][1]['has_cover']
    assert Path(selection['videos'][1]['cover_path']).is_file()
    # An analyze output folder may differ from the original collection directory.
    assert Path(selection['videos'][1]['cover_path']).is_absolute()
