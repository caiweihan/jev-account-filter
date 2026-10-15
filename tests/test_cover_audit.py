from PIL import Image
import pytest
from account_filter.tasks.sign_language.cover_audit import build_request, normalize, answer
from task_helpers import API_CONFIG


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
