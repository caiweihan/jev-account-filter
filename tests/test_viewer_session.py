"""Persist real serializable handles in IndexedDB; all files are fictional and offline."""
import base64
import io

import pytest
from PIL import Image
from playwright.sync_api import expect

from test_viewer import browser, data, ready, parent_click, sized
from task_helpers import TASK


def frame_asset_count(page):
    return page.frame_locator('#report').locator('body').evaluate('()=>viewerURLs.size')


@pytest.fixture
def viewer(tmp_path, browser):
    from account_filter.viewer import build
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    # OPFS is unavailable for file://. Fulfill a secure test origin entirely
    # in memory; no server, DNS, or external network is used.
    html = build(tmp_path / 'viewer.html').read_text(encoding='utf-8')
    page.route('**/*', lambda route: route.fulfill(body=html, content_type='text/html')
               if route.request.url == 'https://viewer.example/analysis.html' else route.abort())
    page.goto('https://viewer.example/analysis.html')
    page.locator('#advanced-settings').evaluate('el=>el.open=true')
    yield page, errors, []
    assert not errors
    page.close()


def prepare_handles(page):
    # OPFS supplies real browser handles without opening an OS dialog in headless tests.
    image = io.BytesIO()
    Image.new('RGB', (2, 2), '#123456').save(image, format='JPEG')
    page.evaluate("""async ({labels,image})=>{
      const root=await navigator.storage.getDirectory();
      async function write(dir,name,text){const h=await dir.getFileHandle(name,{create:true});const w=await h.createWritable();await w.write(text);await w.close();return h}
      await write(root,'results.csv',`账户名称,频道网址,预测结果,人工标注,频道概率,视频1分数,视频1链接\n虚构账户,https://example.com/a,${labels[0]},${labels[1]},.8,.7,https://example.com/video/1\n`);
      await write(root,'review.csv',`主页网址,审核结果\nhttps://example.com/a,${labels[0]}\n`);
      const cache=await root.getDirectoryHandle('cache',{create:true});
      await write(cache,'channel.json',JSON.stringify({url:'https://example.com/a',bio:'恢复的简介',videos:[{id:'1',url:'https://example.com/video/1',title:'恢复的标题'}]}));
      await write(cache,'1.jpg',Uint8Array.from(atob(image),c=>c.charCodeAt(0)));
    }""", {'labels': [TASK['positive_label'], TASK['negative_label']],
            'image': base64.b64encode(image.getvalue()).decode('ascii')})
    page.add_init_script("""
      window.showOpenFilePicker=async options=>[await (await navigator.storage.getDirectory()).getFileHandle(options.id==='results'?'results.csv':'review.csv')];
      window.showDirectoryPicker=async()=>await (await navigator.storage.getDirectory()).getDirectoryHandle('cache');
    """)
    page.reload()
    page.wait_for_function('()=>!document.querySelector("#pick-csv").disabled')
    page.locator('#advanced-settings').evaluate('el=>el.open=true')


def test_restore_files_folders_review_and_settings_with_fresh_contents(viewer):
    page, _, _ = viewer
    prepare_handles(page)
    page.locator('#category').select_option(label=TASK['name'])
    page.locator('#pick-csv').click()
    ready(page, '已载入 1 个频道')
    page.locator('#pick-folder').click()
    ready(page, '数据匹配 1/1')
    page.locator('#pick-review').click()
    ready(page, '二次核验匹配 1 个频道')
    page.wait_for_function('()=>document.querySelector("#session-note").textContent.includes("已自动保存")')
    assert data(page)['second_review']['matched'] == 1
    assert data(page)['rows'][0]['bio'] == '恢复的简介'
    # Close the document and open the same HTML again in the same browser profile.
    url = page.url
    page.goto('about:blank')
    page.goto(url)
    ready(page, '已载入 1 个频道')
    assert data(page)['rows'][0]['videos'][0]['title'] == '恢复的标题'
    assert data(page)['second_review']['matched'] == 1
    assert '已自动载入' in page.locator('#session-note').inner_text()
    # Files are not snapshots stored in IndexedDB: edited data is read next time.
    page.evaluate("""async()=>{const root=await navigator.storage.getDirectory();const h=await root.getFileHandle('results.csv');const file=await h.getFile();const text=await file.text();const w=await h.createWritable();await w.write(text.replace('虚构账户','更新的账户'));await w.close()}""")
    page.reload()
    ready(page, '已载入 1 个频道')
    assert data(page)['rows'][0]['name'] == '更新的账户'
    page.locator('#clear-review').click()
    ready(page, '已载入 1 个频道')
    page.locator('#clear-cache').click()
    ready(page, '数据匹配 0/1')
    page.reload()
    ready(page, '已载入 1 个频道')
    assert 'second_review' not in data(page)
    assert data(page)['rows'][0]['bio'] == ''
    page.locator('#forget-session').click()
    page.wait_for_function('()=>document.querySelector("#session-note").textContent.includes("已忘记")')
    assert not page.locator('#report').is_hidden()
    page.reload()
    page.wait_for_function('()=>!document.querySelector("#pick-csv").disabled')
    assert page.locator('#report').is_hidden()
    assert page.locator('#category').input_value() == ''


def test_expired_permission_automatically_displays_cached_review_and_covers(viewer):
    page, _, _ = viewer
    prepare_handles(page)
    page.locator('#category').select_option(label=TASK['name'])
    page.locator('#pick-csv').click()
    ready(page, '已载入 1 个频道')
    page.locator('#pick-folder').click()
    ready(page, '数据匹配 1/1')
    page.locator('#pick-review').click()
    ready(page, '二次核验匹配 1 个频道')
    page.wait_for_function('()=>document.querySelector("#session-note").textContent.includes("已自动保存")')
    page.add_init_script("""
      window.permissionGranted=false;window.permissionPrompts=0;
      FileSystemFileHandle.prototype.queryPermission=async()=>window.permissionGranted?'granted':'prompt';
      FileSystemFileHandle.prototype.requestPermission=async()=>{window.permissionPrompts++;window.permissionGranted=true;return 'granted'};
      FileSystemDirectoryHandle.prototype.queryPermission=FileSystemFileHandle.prototype.queryPermission;
      FileSystemDirectoryHandle.prototype.requestPermission=FileSystemFileHandle.prototype.requestPermission;
    """)
    page.reload()
    page.wait_for_function('()=>document.querySelector("#session-note").textContent.includes("已自动显示上次分析副本")')
    assert page.evaluate('window.permissionPrompts') == 0
    assert page.locator('#restore-session').count() == 0
    assert data(page)['rows'][0]['name'] == '虚构账户'
    assert data(page)['rows'][0]['bio'] == '恢复的简介'
    assert data(page)['rows'][0]['videos'][0]['cover'].startswith('viewer-asset:')
    assert frame_asset_count(page) == 0
    assert data(page)['second_review']['matched'] == 1
    # The report is immediately interactive, including the cached thumbnail.
    frame = page.frame_locator('#report')
    frame.locator('#case-table [data-case]').first.click()
    frame.locator('#detail-content img').first.wait_for()
    frame.locator('#detail-content img').first.scroll_into_view_if_needed()
    frame.locator('#detail-content img').first.evaluate("img=>{img.loading='eager'}")
    expect(frame.locator('#detail-content img').first).to_have_js_property('naturalWidth', 2)
    frame.locator('#close-detail').click()
    sized(page)
    parent_click(page, '#refresh-files')
    ready(page, '已载入 1 个频道')
    assert page.evaluate('window.permissionPrompts') == 3
    page.evaluate("()=>{window.showOpenFilePicker=async()=>{throw new DOMException('cancelled','AbortError')}}")
    page.locator('#pick-csv').click()
    page.wait_for_function('()=>!document.querySelector("#pick-csv").disabled')
    assert data(page)['rows'][0]['name'] == '虚构账户'
    assert '已自动载入' in page.locator('#session-note').inner_text()


def test_unavailable_storage_falls_back_to_regular_file_controls(tmp_path, browser):
    from account_filter.viewer import build
    page = browser.new_page()
    page.add_init_script("Object.defineProperty(window,'indexedDB',{get(){throw new Error('blocked')}})")
    page.goto(build(tmp_path / 'viewer.html').as_uri())
    page.wait_for_function('()=>!document.querySelector("#csv-file").disabled')
    assert page.locator('#choose-csv').is_visible()
    assert '无法使用本地持久存储' in page.locator('#session-note').inner_text()
    page.close()


def test_asset_cache_is_separate_and_idle_restore_does_not_rewrite_it(viewer):
    page, _, _ = viewer
    prepare_handles(page)
    page.locator('#pick-csv').click()
    ready(page, '已载入 1 个频道')
    page.locator('#pick-folder').click()
    ready(page, '数据匹配 1/1')
    assert frame_asset_count(page) == 0
    saved = page.evaluate("""async()=>{
      const tx=session.db.transaction(['selection','assets']);
      const read=r=>new Promise((yes,no)=>{r.onsuccess=()=>yes(r.result);r.onerror=()=>no(r.error)});
      const view=await read(tx.objectStore('selection').get('view-v2'));
      return {date:view.date,assets:view.view.assets,stored:await read(session.db.transaction('assets').objectStore('assets').count())};
    }""")
    assert saved['stored'] == 2
    assert all('file' not in item for item in saved['assets'])
    page.add_init_script("""window.assetWrites=0;const put=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(...args){if(this.name==='assets')window.assetWrites++;return put.apply(this,args)};FileSystemFileHandle.prototype.queryPermission=async()=>'prompt';FileSystemDirectoryHandle.prototype.queryPermission=async()=>'prompt'""")
    page.reload()
    page.wait_for_function('()=>!model.busy&&model.lastView?.assets.length===2')
    assert page.evaluate('window.assetWrites') == 0
    assert frame_asset_count(page) == 0
    frame = page.frame_locator('#report')
    frame.locator('#case-table [data-case]').first.click()
    expect(frame.locator('#detail-content img')).to_have_js_property('naturalWidth', 2)
    assert frame_asset_count(page) <= 2
    page.wait_for_function('()=>assetBroker.active===0&&assetBroker.queue.length===0')


def test_legacy_bulk_snapshot_is_not_read_during_upgrade(viewer):
    page, _, _ = viewer
    page.wait_for_function('()=>!model.busy')
    page.evaluate("""async()=>{
      session.db.close();
      const name='jev-viewer:'+location.pathname;
      await new Promise((yes,no)=>{const r=indexedDB.deleteDatabase(name);r.onsuccess=yes;r.onerror=no});
      const db=await new Promise((yes,no)=>{const r=indexedDB.open(name,1);r.onupgradeneeded=()=>r.result.createObjectStore('selection');r.onsuccess=()=>yes(r.result);r.onerror=no});
      await new Promise((yes,no)=>{const tx=db.transaction('selection','readwrite');tx.objectStore('selection').put({csv:null,folders:[],review:null,encoding:'auto'},'last');tx.objectStore('selection').put({old:true},'view');tx.oncomplete=yes;tx.onerror=no});db.close();
    }""")
    page.add_init_script("""
      for(const method of ['get','delete']){const original=IDBObjectStore.prototype[method];IDBObjectStore.prototype[method]=function(key){if(this.name==='selection'&&key==='view')throw Error('Legacy bulk value must not be read or deleted');return original.call(this,key)}}
      const clear=IDBObjectStore.prototype.clear;IDBObjectStore.prototype.clear=function(){if(this.name==='selection')throw Error('Clearing selection would touch the legacy bulk value');return clear.call(this)};
    """)
    page.reload()
    page.wait_for_function('()=>!model.busy&&session.legacy')
    assert '重新选择' in page.locator('#session-note').inner_text()
    assert page.locator('#choose-csv').is_visible() or page.locator('#pick-csv').is_visible()
    assert page.locator('#report').is_hidden()
    # Loading a new CSV automatically saves, then forgetting and reopening must
    # also avoid the legacy value. Deleting it caused a real browser-process OOM.
    page.locator('#advanced-settings').evaluate('el=>el.open=true')
    page.locator('#category').select_option(label=TASK['name'])
    text = ('账户名称,频道网址,预测结果,人工标注,频道概率\n'
            f'虚构账户,https://example.com/a,{TASK["positive_label"]},{TASK["positive_label"]},.8\n')
    page.locator('#csv-file').set_input_files({
        'name': 'results.csv', 'mimeType': 'text/csv', 'buffer': text.encode('utf-8')})
    ready(page, '已载入 1 个频道')
    assert '已自动保存' in page.locator('#session-note').inner_text()
    page.reload()
    ready(page, '已载入 1 个频道')
    page.locator('#forget-session').click()
    page.wait_for_function('()=>!model.busy')
    assert '已忘记' in page.locator('#session-note').inner_text()
    page.reload()
    page.wait_for_function('()=>!model.busy')
    assert page.locator('#report').is_hidden()


def test_missing_files_and_picker_rejection_keep_recovery_controls(viewer):
    page, _, _ = viewer
    prepare_handles(page)
    page.locator('#category').select_option(label=TASK['name'])
    page.locator('#pick-csv').click()
    ready(page, '已载入 1 个频道')
    page.wait_for_function('()=>document.querySelector("#session-note").textContent.includes("已自动保存")')
    page.evaluate("async()=>{await (await navigator.storage.getDirectory()).removeEntry('results.csv')}")
    page.reload()
    page.wait_for_function('()=>document.querySelector("#session-note").textContent.includes("部分文件无法读取")')
    assert page.locator('#refresh-files').is_visible()
    assert data(page)['rows'][0]['name'] == '虚构账户'
    assert page.locator('#forget-session').is_visible()
    page.evaluate("()=>{window.showOpenFilePicker=async()=>{throw new DOMException('blocked','SecurityError')}}")
    page.locator('#pick-csv').click()
    page.wait_for_function('()=>!document.querySelector("#csv-file").disabled')
    assert page.locator('#choose-csv').is_visible()
    assert '普通文件选择' in page.locator('#session-note').inner_text()


def test_category_and_encoding_are_saved_without_files_on_file_url(tmp_path, browser):
    from account_filter.viewer import build
    page = browser.new_page()
    page.goto(build(tmp_path / 'viewer.html').as_uri())
    page.locator('#advanced-settings').evaluate('el=>el.open=true')
    page.locator('#category').select_option(label=TASK['name'])
    page.locator('#encoding').select_option('gb18030')
    page.wait_for_function('()=>document.querySelector("#session-note").textContent.includes("自动保存")')
    page.reload()
    page.wait_for_function('()=>!document.querySelector("#encoding").disabled')
    assert page.locator('#category option:checked').text_content() == TASK['name']
    assert page.locator('#encoding').input_value() == 'gb18030'
    assert page.locator('#report').is_hidden()
    page.close()


def test_regular_file_selection_also_restores_analysis_without_handles(tmp_path, browser):
    from account_filter.viewer import build
    from test_viewer import pick_csv
    page = browser.new_page()
    page.goto(build(tmp_path / 'viewer.html').as_uri())
    assert page.locator('#choose-csv').is_visible()
    assert page.locator('#pick-csv').is_hidden()
    page.locator('#advanced-settings').evaluate('el=>el.open=true')
    page.locator('#category').select_option(label=TASK['name'])
    pick_csv(page, '账户名称,频道网址,预测结果,人工标注,频道概率\n普通选择,https://example.com/local,手语频道,不是手语频道,.8\n')
    ready(page, '已载入 1 个频道')
    page.wait_for_function('()=>document.querySelector("#session-note").textContent.includes("已自动保存")')
    page.reload()
    page.wait_for_function('()=>document.querySelector("#session-note").textContent.includes("已自动显示上次分析副本")')
    assert data(page)['rows'][0]['name'] == '普通选择'
    assert page.locator('#refresh-files').is_hidden()
    assert page.locator('#restore-session').count() == 0
    # The saved CSV bytes remain usable without a file-system handle.
    page.locator('#advanced-settings').evaluate('el=>el.open=true')
    page.locator('#encoding').select_option('utf-8')
    ready(page, '已载入 1 个频道')
    assert data(page)['summary']['mismatch'] == 1
    # An older release may have persisted unusable native handles. file:// must
    # ignore them rather than calling queryPermission/getFile on startup.
    page.evaluate("async()=>{await sessionStore({...session.saved,csv:{name:'old.csv'},folders:[{name:'old-cache'}]})}")
    page.reload()
    page.wait_for_function('()=>document.querySelector("#session-note").textContent.includes("已自动显示上次分析副本")')
    assert data(page)['rows'][0]['name'] == '普通选择'
    assert page.locator('#choose-csv').is_visible()
    assert page.locator('#refresh-files').is_hidden()
    page.close()


def test_get_file_denial_after_picker_and_on_reopen_preserves_analysis(viewer):
    page, _, _ = viewer
    prepare_handles(page)
    page.locator('#category').select_option(label=TASK['name'])
    page.locator('#pick-csv').click()
    ready(page, '已载入 1 个频道')
    page.wait_for_function('()=>document.querySelector("#session-note").textContent.includes("已自动保存")')
    script = """
      FileSystemFileHandle.prototype.getFile=async()=>{throw new DOMException("Failed to execute 'getFile' on 'FileSystemFileHandle': The request is not allowed by the user agent or the platform in the current context.",'NotAllowedError')};
    """
    page.evaluate('()=>{' + script + '}')
    page.locator('#pick-review').click()
    ready(page, '浏览器拒绝读取')
    assert page.locator('#choose-review').is_visible()
    assert 'Failed to execute' not in page.locator('#status').inner_text()
    assert data(page)['rows'][0]['name'] == '虚构账户'
    page.add_init_script(script)
    page.reload()
    page.wait_for_function('()=>document.querySelector("#session-note").textContent.includes("已自动显示上次分析副本")')
    assert data(page)['rows'][0]['name'] == '虚构账户'
    assert page.locator('#choose-csv').is_visible()
    assert '浏览器拒绝读取' in page.locator('#session-note').inner_text()
    assert 'Failed to execute' not in page.locator('#session-note').inner_text()


def test_unreadable_cache_entry_is_skipped_without_unhandled_rejection(viewer):
    page, _, _ = viewer
    prepare_handles(page)
    page.locator('#category').select_option(label=TASK['name'])
    page.locator('#pick-csv').click()
    ready(page, '已载入 1 个频道')
    page.evaluate("""async()=>{
      const cache=await (await navigator.storage.getDirectory()).getDirectoryHandle('cache');
      await cache.getFileHandle('unused.exe',{create:true});
      const original=FileSystemFileHandle.prototype.getFile;
      window.unusedRead=false;
      FileSystemFileHandle.prototype.getFile=async function(){
        if(this.name==='unused.exe'){window.unusedRead=true;throw new Error('unrelated file should never be read')}
        if(this.name==='1.jpg')throw new DOMException('blocked image','NotAllowedError');
        return original.call(this);
      };
    }""")
    page.locator('#pick-folder').click()
    ready(page, '数据匹配 1/1')
    assert data(page)['rows'][0]['bio'] == '恢复的简介'
    assert data(page)['rows'][0]['videos'][0]['title'] == '恢复的标题'
    assert data(page)['rows'][0]['videos'][0]['cover'] is None
    assert '已跳过 1 个无法读取' in page.locator('#cache-note').inner_text()
    assert page.evaluate('window.unusedRead') is False
