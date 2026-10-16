from PIL import Image
import pytest
from account_filter.tasks.sign_language.cover_audit import build_request, normalize, answer
from task_helpers import API_CONFIG
from task_helpers import API_PATH
import asyncio
import json
from account_filter.tasks.sign_language import cover_audit
from account_filter.report import generate
from test_report import fixture_csv


def sample_answer(choice):
    return {'type':'choice','choice':choice,'probabilities':{key:1 if key==choice else 0 for key in ('yes','no','unclear')}}


def test_one_request_contains_five_images_without_channel_label(tmp_path):
    videos=[]
    for i in range(1,6):
        Image.new('RGB',(30,40),'white').save(tmp_path/f'{i}.jpg')
        videos.append({'rank':i,'cover':f'{i}.jpg'})
    row={'name':'DO_NOT_LEAK_NAME','manual':'DO_NOT_LEAK_LABEL','videos':videos}
    payload,sent=build_request(row,tmp_path,API_CONFIG)
    assert sent == [1,2,3,4,5]
    assert sum(isinstance(x,dict) for x in payload['state'])==5
    assert set(payload['questions'])=={'v001','v002','v003','v004','v005','all_front','any_front'}
    assert 'DO_NOT_LEAK' not in str(payload)


def test_group_judgment_comes_from_model_and_missing_does_not_prove_all():
    row={'videos':[{'rank':1},{'rank':2}]}
    raw={'answers':{'all_front':sample_answer('no'),'any_front':sample_answer('yes'),'v001':sample_answer('yes')}}
    result=normalize(row,raw,[1])
    assert result['status']=='不符合'  # 整组答案不由每张答案的聚合覆盖。
    assert result['videos'][1]['front'] is None
    raw['answers']['all_front']=sample_answer('yes')
    assert normalize(row,raw,[1])['status']=='无法验证（缺少封面）'
    raw['answers']['all_front']=sample_answer('unclear')
    raw['answers']['v002']=sample_answer('unclear')
    assert normalize(row,raw,[1,2])['status']=='无法判断'


def test_invalid_probability_distribution_is_an_error():
    raw={'answers':{'all_front':{'type':'choice','choice':'yes','probabilities':{'yes':.9,'no':.9,'unclear':0}}}}
    with pytest.raises(ValueError,match='概率之和'):
        answer(raw,'all_front')


def test_named_output_resume_and_report_update_without_task_extension(tmp_path, monkeypatch):
    source = fixture_csv(tmp_path)
    folder = tmp_path / 'intermediate/0001'
    (folder / 'covers').mkdir(parents=True)
    Image.new('RGB', (30, 40)).save(folder / 'covers/1.jpg')
    (folder / 'channel.json').write_text(json.dumps({
        'url': 'https://www.douyin.com/user/a', 'name': 'Example', 'bio': '',
        'videos': [{'id': '1', 'url': 'https://www.douyin.com/video/1', 'title': 'Example'}]}), encoding='utf-8')
    html, _ = generate(source)
    before_csv = source.read_bytes()
    before = json.loads(html.read_text(encoding='utf-8').split('<script id="report-data" type="application/json">')[1].split('</script>')[0])
    assert 'report_extension' not in before['category']
    calls = []
    async def model(*args, **kwargs):
        calls.append(args)
        return {'answers': {key: sample_answer('yes') for key in ('all_front', 'any_front', 'v001')}}
    monkeypatch.setattr(cover_audit, 'call_model_api', model)
    output = tmp_path / 'cover-audit/person-feature'
    command = cover_audit.parser()
    args = command.parse_args([str(source), '--config', str(API_PATH), '--limit', '1', '--output', str(output)])
    assert asyncio.run(cover_audit.run(args)) == 0
    assert (output / 'audit-results.json').is_file()
    assert len(calls) == 1
    after = json.loads(html.read_text(encoding='utf-8').split('<script id="report-data" type="application/json">')[1].split('</script>')[0])
    assert after['rows'] == before['rows'] and after['category'] == before['category']
    assert after['cover_audit']['criteria'] == cover_audit.CRITERIA
    assert source.read_bytes() == before_csv
    with pytest.raises(ValueError, match='非空'):
        asyncio.run(cover_audit.run(args))
    args = command.parse_args([str(source), '--config', str(API_PATH), '--limit', '1', '--resume', str(output)])
    assert asyncio.run(cover_audit.run(args)) == 0
    assert len(calls) == 1
    # Bounds of the selected population are part of a resumed experiment.
    args.limit = None
    with pytest.raises(ValueError, match='账户范围'):
        asyncio.run(cover_audit.run(args))


def test_default_output_has_name_and_mismatched_report_fails_before_api(tmp_path, monkeypatch):
    source = fixture_csv(tmp_path)
    html, _ = generate(source)
    command = cover_audit.parser()
    args = command.parse_args([str(source), '--config', str(API_PATH), '--limit', '1'])
    async def forbidden(*args, **kwargs):
        pytest.fail('No images or an inconsistent report must never call the API')
    monkeypatch.setattr(cover_audit, 'call_model_api', forbidden)
    assert asyncio.run(cover_audit.run(args)) == 0
    assert (tmp_path / 'cover-audit/sign-language/audit-results.json').is_file()
    source.write_bytes(source.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='尚未调用模型'):
        asyncio.run(cover_audit.run(args))
