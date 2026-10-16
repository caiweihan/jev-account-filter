"""Load user-granted files without ever invoking a native chooser."""
import base64
import io

from PIL import Image
from playwright.sync_api import expect

from test_viewer import browser, viewer, data, ready, report_click

CSV = '账户名称,频道网址,预测结果,人工标注,频道概率,视频1分数,视频1链接\n拖入账户,https://example.com/a,手语频道,不是手语频道,.8,.9,https://example.com/video/1\n'


def drop_csv(page, kind, text, name='results.csv'):
    transfer=page.evaluate_handle("""({name,text})=>{const transfer=new DataTransfer();transfer.items.add(new File([text],name,{type:'text/csv'}));return transfer}""", {'name':name,'text':text})
    page.locator(f'[data-drop-kind="{kind}"]').dispatch_event('drop', {'dataTransfer':transfer})
    transfer.dispose()


def test_dropped_results_reviews_and_reopen_do_not_open_a_chooser(viewer):
    page, _, _ = viewer
    choosers=[]
    page.on('filechooser', lambda chooser:choosers.append(chooser))
    drop_csv(page,'csv',CSV)
    ready(page,'已载入 1 个频道')
    assert page.locator('#csv-selected').inner_text()=='results.csv'
    drop_csv(page,'review','主页网址,审核结果\nhttps://example.com/a,手语频道\n','review.csv')
    ready(page,'二次核验匹配 1')
    assert data(page)['second_review']['matched']==1
    assert page.frame_locator('#report').locator('body').evaluate('()=>evaluationBasis()')=='combined'
    page.reload()
    page.wait_for_function('()=>!model.busy&&model.lastView?.payload.second_review?.matched===1')
    assert data(page)['rows'][0]['name']=='拖入账户'
    assert not choosers


def test_directory_drop_reads_all_entry_batches_and_keeps_cover_alignment(viewer):
    page, _, _ = viewer
    drop_csv(page,'csv',CSV)
    ready(page,'已载入 1 个频道')
    image=io.BytesIO();Image.new('RGB',(3,4),'blue').save(image,format='JPEG')
    page.evaluate("""async image=>{
      const file=(path,value,type)=>({name:path.split('/').at(-1),fullPath:path,isFile:true,isDirectory:false,file:yes=>queueMicrotask(()=>yes(new File([value],path.split('/').at(-1),{type})))});
      const metadata=file('/cache/account/channel.json',JSON.stringify({url:'https://example.com/a',bio:'拖入的简介',videos:[{id:'1',url:'https://example.com/video/1',title:'拖入的标题',cover_path:'covers/1.jpg'}]}),'application/json');
      const cover=file('/cache/account/covers/1.jpg',Uint8Array.from(atob(image),c=>c.charCodeAt(0)),'image/jpeg');
      const ignored=file('/cache/ignored.txt','do not read','text/plain');ignored.file=()=>{throw Error('Unrelated file read')};
      const entry={isDirectory:true,createReader(){let n=0;return{readEntries(yes){queueMicrotask(()=>yes(n++===0?[metadata]:n===2?[cover,ignored]:[]))}}}};
      await acceptDroppedFiles('folder',[],[entry]);
    }""", base64.b64encode(image.getvalue()).decode('ascii'))
    ready(page,'数据匹配 1/1')
    assert data(page)['rows'][0]['bio']=='拖入的简介'
    assert data(page)['rows'][0]['videos'][0]['title']=='拖入的标题'
    report_click(page,'#case-table [data-case]')
    frame=page.frame_locator('#report')
    image=frame.locator('#detail-content img')
    image.scroll_into_view_if_needed()
    expect(image).to_have_js_property('naturalWidth',3)


def test_wrong_drop_reports_an_error_and_preserves_the_last_report(viewer):
    page, _, _ = viewer
    drop_csv(page,'csv',CSV)
    ready(page,'已载入 1 个频道')
    drop_csv(page,'folder',CSV)
    ready(page,'请将采集数据目录拖到这一行')
    assert data(page)['rows'][0]['name']=='拖入账户'
    drop_csv(page,'csv','not csv','invalid.txt')
    ready(page,'请在这一行拖入一个 CSV')
    assert data(page)['rows'][0]['name']=='拖入账户'
