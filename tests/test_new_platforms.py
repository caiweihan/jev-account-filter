import asyncio
from types import SimpleNamespace

import pytest

from account_filter.collection.browser import profile_info, import_cookies
from account_filter.collection.platforms import youtube, bilibili
from account_filter.errors import CollectionError, RiskControlError


@pytest.mark.parametrize('url,expected', [
    ('https://www.youtube.com/@example/videos', ('youtube', '@example')),
    ('https://youtube.com/@example', ('youtube', '@example')),
    ('https://www.youtube.com/channel/UCexample/videos', ('youtube', 'UCexample')),
    ('https://www.youtube.com/@%E6%B5%8B%E8%AF%95/videos', ('youtube', '@测试')),
    ('https://space.bilibili.com/123/upload/video', ('bilibili', '123')),
    ('https://space.bilibili.com/123/video', ('bilibili', '123')),
    ('https://space.bilibili.com/123', ('bilibili', '123')),
    ('https://www.douyin.com/user/example?source=SEARCH', ('douyin', 'example')),
])
def test_profile_routes(url, expected):
    assert profile_info(url) == expected


@pytest.mark.parametrize('url', [
    'https://youtube.com.evil.test/@example/videos', 'http://youtube.com/@example/videos',
    'https://www.youtube.com/watch?v=abcdefghijk', 'https://www.youtube.com/@a%2fb/videos',
    'https://space.bilibili.com/../123/upload/video', 'https://www.youtube.com/@bad%5Cname/videos',
])
def test_nonprofile_urls_rejected(url):
    with pytest.raises(ValueError):
        profile_info(url)


def yt_video(identity, title):
    return {'videoRenderer': {'videoId': identity, 'title': {'runs': [{'text': title}]},
                              'thumbnail': {'thumbnails': [{'url': identity+'.jpg', 'width': 360}]}}}


def test_youtube_selected_tab_keeps_title_thumbnail_alignment_and_ignores_other_tabs():
    contents = [yt_video('abcdefghijk', 'First'), {'lockupViewModel': {
        'contentId': 'lmnopqrstuv', 'contentType': 'LOCKUP_CONTENT_TYPE_VIDEO',
        'metadata': {'lockupMetadataViewModel': {'title': {'content': 'Second'}}},
        'contentImage': {'thumbnailViewModel': {'image': {'sources': [{'url':'second.jpg','width':720}]}}}}}]
    data = {'metadata': {'channelMetadataRenderer': {'title':'Test', 'description':'Full bio',
             'ownerUrls':['https://www.youtube.com/@example'], 'externalId':'UCexample'}},
            'contents': {'tabs': [
                {'tabRenderer': {'selected':False, 'content':yt_video('xxxxxxxxxxx','Recommended')}},
                {'tabRenderer': {'selected':True, 'endpoint': {'commandMetadata': {'webCommandMetadata': {'url':'/@example/videos'}}},
                                 'content': contents}}]}}
    result = youtube.parse_initial_data(data, '@example')
    assert result['bio'] == 'Full bio'
    assert [(v['title'],v['cover_url']) for v in result['videos']] == [('First','abcdefghijk.jpg'),('Second','second.jpg')]
    assert not youtube.parse_initial_data(data, '@another')['name']
    assert not youtube.parse_initial_data(data, 'UCother')['videos']
    data['metadata']['channelMetadataRenderer']['ownerUrls']=['https://www.youtube.com/@%E6%B5%8B%E8%AF%95']
    assert len(youtube.parse_initial_data(data,'@测试')['videos'])==2
    data['metadata']['channelMetadataRenderer']['ownerUrls']=['https://www.youtube.com/@example']
    data['contents']['tabs'][1]['tabRenderer']['endpoint']['commandMetadata']['webCommandMetadata']['url']='/@example/shorts'
    assert not youtube.parse_initial_data(data,'@example')['videos']


def response(url, payload):
    async def read(): return payload
    return SimpleNamespace(url=url,json=read,request=SimpleNamespace(method='GET'))


def test_bilibili_first_author_feed_only_and_video_metadata():
    payload={'code':0,'data':{'list':{'vlist':[
        {'mid':123,'bvid':'BV1234567890','title':'A &amp; B','pic':'//i0.hdslb.com/a.jpg'},
        {'mid':999,'bvid':'BVabcdefghij','title':'Other author','pic':'https://i0.hdslb.com/b.jpg'}]}}}
    url='https://api.bilibili.com/x/space/wbi/arc/search?mid=123&pn=1'
    profile,videos,feed=asyncio.run(bilibili.parse_response(response(url,payload),'123'))
    assert feed and len(videos)==1
    assert videos[0]['title']=='A & B'
    assert videos[0]['cover_url']=='https://i0.hdslb.com/a.jpg'
    for bad_url in (url.replace('pn=1','pn=2'),url.replace('mid=123','mid=999'),url+'&keyword=search',url+'&tid=4'):
        assert asyncio.run(bilibili.parse_response(response(bad_url,payload),'123')) is None
    with pytest.raises(RiskControlError,match='-352'):
        asyncio.run(bilibili.parse_response(response(url,{'code':-352,'message':'验证'}),'123'))
    limited=response(url,{})
    limited.status=412
    with pytest.raises(RiskControlError,match='HTTP 412'):
        asyncio.run(bilibili.parse_response(limited,'123'))


def test_bilibili_nonempty_account_cannot_be_saved_as_empty():
    with pytest.raises(CollectionError,match='105'):
        bilibili.finalize({'videos':[]},{'video_count':105},None,[],False,True)


def test_bilibili_parent_domain_session_cookie_import(tmp_path):
    source=tmp_path/'cookies.json'
    source.write_text('[{"name":"SESSDATA","value":"test","domain":".bilibili.com"}]')
    assert import_cookies(source)[0]['name']=='SESSDATA'
