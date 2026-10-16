// Remember choices by default, with a local analysis snapshot for no-click opens.
// Only explicit file refreshes may request read permission; snapshots stay local.
const session={db:null,csv:null,review:null,folders:[],saved:null,restoring:false,persistedKeys:new Set()};
// Use regular inputs for local HTML: exposing the picker API does not guarantee
// that native handles can be read in the file:// context.
const nativeSelection=location.protocol!=='file:'&&typeof window.showOpenFilePicker==='function'&&typeof window.showDirectoryPicker==='function';
function sessionText(text){$('session-note').textContent=text}
function ordinarySelection(){for(const id of ['csv-file','cache-folder','review-file'])$(id).parentElement.hidden=false}
function accessDenied(error){return ['NotAllowedError','SecurityError','NotSupportedError'].includes(error?.name)}
function fileError(error){return accessDenied(error)?'浏览器拒绝读取此文件或目录，请通过普通文件选择重新载入；已有分析副本保留。':error?.name==='NotFoundError'?'文件已移动或删除，请重新选择。':error.message}
async function pickRemembered(picker){try{return await picker()}catch(error){if(accessDenied(error)){ordinarySelection();sessionText('当前浏览器拒绝读取文件，已显示普通文件选择；已有分析不受影响。');throw Error(fileError(error))}throw error}}
function sessionHandles(saved){return [saved.csv,saved.review,...saved.folders].filter(Boolean)}
function sessionNames(){return [session.csv?.name,session.review?.name,...session.folders.map(h=>h.name)].filter(Boolean).join('、')}
function sessionTransaction(names,write){return new Promise((resolve,reject)=>{const tx=session.db.transaction(names,'readwrite');tx.oncomplete=resolve;tx.onabort=tx.onerror=()=>reject(tx.error||Error('无法保存文件选择'));try{write(tx)}catch(error){tx.abort();reject(error)}})}
async function sessionStore(value,snapshot){
 // Never read or delete the legacy bulk value: Chromium may exhaust browser
 // process memory while materializing its thousands of Blob references, even
 // for deletion. Forget only keys owned by the current snapshot format.
 if(!value){await sessionTransaction(['selection','assets'],tx=>{const store=tx.objectStore('selection');store.delete('last');store.delete('view-v2');tx.objectStore('assets').clear()});session.persistedKeys.clear();return}
 if(snapshot){
  // Small transactions avoid cloning thousands of Blob handles in one value.
  let batch=[],bytes=0;
  const flush=async()=>{if(!batch.length)return;const items=batch;batch=[];bytes=0;await sessionTransaction(['assets'],tx=>{const store=tx.objectStore('assets');for(const item of items)store.put(item.file.slice(0,item.file.size,item.file.type),item.key)});await new Promise(resolve=>setTimeout(resolve,0))};
  for(const item of snapshot.view.assets){if(!item.file||session.persistedKeys.has(item.key))continue;if(batch.length&&(batch.length>=16||bytes+item.file.size>4*1024*1024))await flush();batch.push(item);bytes+=item.file.size}
  await flush();
 }
 const metadata=snapshot?{...snapshot,version:2,view:{payload:snapshot.view.payload,assets:snapshot.view.assets.map(({id,key,file,size})=>({id,key,size:file?.size??size}))}}:null;
 await sessionTransaction(['selection'],tx=>{const store=tx.objectStore('selection');store.put(value,'last');if(metadata)store.put(metadata,'view-v2')});
 if(metadata){const keep=new Set(metadata.view.assets.map(item=>item.key)),obsolete=[...session.persistedKeys].filter(key=>!keep.has(key));for(let i=0;i<obsolete.length;i+=32)await sessionTransaction(['assets'],tx=>{for(const key of obsolete.slice(i,i+32))tx.objectStore('assets').delete(key)});session.persistedKeys=keep;session.legacy=false}
}
function snapshotView(){
 if(!model.lastView)return null;
 const payload=structuredClone(model.lastView.payload),refs=assetReferences(payload);
 const used=new Set(refs.map(([obj,key])=>obj[key]).filter(Boolean));
 const selected=model.lastView.assets.filter(item=>used.has(item.id));
 const remap=new Map(selected.map((item,i)=>[item.id,`viewer-asset:${i}`]));
 for(const [obj,key] of refs)if(obj[key])obj[key]=remap.get(obj[key])||null;
 return {date:new Date().toLocaleString('zh-CN'),inputs:model.lastInputs,view:{payload,assets:selected.map((item,i)=>({...item,id:`viewer-asset:${i}`,key:item.key||(item.file?assetKey(item.file):null)}))}};
}
async function rememberSession(quiet=false){
 if(!session.db||session.restoring)return;
 const saved={version:1,csv:session.csv,review:session.review,folders:session.folders,
  encoding:$('encoding').value,reviewEncoding:$('review-encoding').value,
  category:selectedCategory(),categoryAuto:model.categoryAuto,custom:$('category').value==='custom',positive:$('positive').value,negative:$('negative').value};
 try{const snapshot=model.lastView!==session.persistedView?snapshotView():null;await sessionStore(saved,snapshot);session.saved=saved;session.persistedView=model.lastView;$('forget-session').hidden=false;$('refresh-files').hidden=!nativeSelection||!sessionHandles(saved).length;
  if(!quiet)sessionText(snapshot||model.lastView?`已自动保存上次分析及所用封面，下次打开直接显示。当前选择：${sessionNames()||model.file?.name||''}。`:'文件选择、类别和编码会自动保存。');
 }catch{try{await sessionStore(saved);session.saved=saved;$('forget-session').hidden=false}catch{}sessionText('浏览器无法保存完整分析副本（可能空间不足），当前分析仍可使用；下次可能需要重新授权读取文件。')}
}
const runViewerAction=action;
action=async work=>{const ok=await runViewerAction(work);if(ok&&!session.skipSave){busy(true);try{await rememberSession()}finally{busy(false)}}session.skipSave=false;return ok};

// Enumerate fresh File objects on each open, so edits on disk are reflected.
async function folderFiles(handle){
 const entries=[],skipped=[];let pending=[];
 async function flush(){entries.push(...(await Promise.all(pending)).filter(Boolean));pending=[];await new Promise(resolve=>setTimeout(resolve,0))}
 async function walk(directory,path){try{for await(const [name,child] of directory.entries()){
  const relative=path+'/'+name;
  if(child.kind==='directory')await walk(child,relative);
  else if(imageName(name)||/\.(json|csv)$/i.test(name)){pending.push(child.getFile().then(file=>({file,path:relative}),error=>{skipped.push({path:relative,reason:fileError(error)});return null}));if(pending.length>=32)await flush()}
 }}catch(error){skipped.push({path,reason:fileError(error)})}}
 await walk(handle,handle.name);if(pending.length)await flush();
 if(skipped.length&&!entries.length){ordinarySelection();throw Error('所选目录中的文件无法读取，请通过普通文件选择重新添加采集数据目录。')}
 entries.skipped=skipped;return entries;
}
async function addRememberedFolder(handle){
 const files=await pickRemembered(()=>folderFiles(handle));await addFolder(files);
 if(files.skipped.length){ordinarySelection();$('cache-note').textContent+=` 已跳过 ${files.skipped.length} 个无法读取的文件或子目录；相关标题或封面可能缺失。首项：${files.skipped[0].path}。可通过普通文件选择重新添加目录。`}
 return files.skipped.length;
}
function applySessionCategory(saved){
 model.categoryAuto=saved.categoryAuto??false;
 if(saved.custom){$('category').value='custom';$('custom-labels').hidden=false;return}
 if(!validCategory(saved.category))return;
 let index=available.findIndex(c=>c.id===saved.category.id&&c.positive_label===saved.category.positive_label&&c.negative_label===saved.category.negative_label);
 if(index<0)index=Number(categoryOption(saved.category));$('category').value=String(index);$('custom-labels').hidden=true;
}
async function restoreSession(prompt=false){
 const saved=session.saved;if(!saved)return;
 session.restoring=true;
 try{
  const handles=sessionHandles(saved),errors=[];
  // Issue permission requests directly from the button's user gesture.
  if(prompt&&nativeSelection)await Promise.all(handles.map(h=>h.requestPermission({mode:'read'}).catch(()=> 'denied')));
  const grants=nativeSelection?await Promise.all(handles.map(h=>h.queryPermission({mode:'read'}).catch(()=> 'denied'))):handles.map(()=> 'prompt');
  const allowed=h=>grants[handles.indexOf(h)]==='granted';
  session.csv=saved.csv;session.review=saved.review;session.folders=[...saved.folders];
  $('encoding').value=saved.encoding||'auto';$('review-encoding').value=saved.reviewEncoding||'auto';applySessionCategory(saved);
  model.restoring=true;
  model.groups=[];model.channels.clear();model.categories=[];
  for(const handle of session.folders){if(!allowed(handle))continue;try{say(`正在恢复采集数据目录：${handle.name}…`);const skipped=await addRememberedFolder(handle);if(skipped)errors.push(`${handle.name}：已跳过 ${skipped} 个无法读取的文件或子目录`)}catch(error){if(accessDenied(error))ordinarySelection();errors.push(`${handle.name}：${fileError(error)}`)}}
  if(session.csv&&allowed(session.csv))try{await loadCSV(await pickRemembered(()=>session.csv.getFile()));if(saved.custom){$('positive').value=saved.positive;$('negative').value=saved.negative}}catch(error){errors.push(`${session.csv.name}：${fileError(error)}`)}
  if(session.review&&allowed(session.review))try{await loadReview(await pickRemembered(()=>session.review.getFile()))}catch(error){errors.push(`${session.review.name}：${fileError(error)}`)}
  model.restoring=false;await renderReport();
  const waiting=grants.some(value=>value!=='granted');$('refresh-files').hidden=!nativeSelection||!handles.length;
  const cached=Boolean(model.cachedView)&&(waiting||errors.length||!handles.length);
  sessionText(`${cached?`已自动显示上次分析副本（${session.snapshot.date}）。`:waiting?'上次文件读取权限不可用。':handles.length?`已自动载入：${sessionNames()}。`:'已恢复上次的类别及编码。'}${waiting?(nativeSelection?'如需读取磁盘上的最新改动，可点击“更新本地文件”授权。':'本地 HTML 使用普通文件选择；如需读取磁盘上的新改动，请重新选择文件或目录。'):''}${errors.length?' 部分文件无法读取（可能权限受限、已移动或删除）：'+errors.join('；')+'。可重新选择替换。':''}`);
  if(!waiting&&!errors.length&&handles.length){session.restoring=false;await rememberSession(true)}else session.persistedView=model.lastView;
  if(session.legacy)sessionText('已升级分析副本读取方式，旧版整批文件副本不再自动载入。请重新选择结果 CSV、核验 CSV 和采集数据目录一次；无需重新采集或调用模型，之后继续自动恢复。');
 }finally{model.restoring=false;session.restoring=false}
}
function clearSavedHandle(id,work){const original=$(id).onchange;$(id).onchange=event=>{work();original(event)}}
clearSavedHandle('csv-file',()=>{session.csv=null});
clearSavedHandle('review-file',()=>{session.review=null});
for(const [id,key] of [['clear-cache','folders'],['clear-review','review']]){
 const original=$(id).onclick;$(id).onclick=event=>{session[key]=key==='folders'?[]:null;original(event)};
}
for(const [id,key] of [['pick-csv','csv'],['pick-review','review']])$(id).onclick=()=>action(async()=>{
 const [handle]=await pickRemembered(()=>window.showOpenFilePicker({id:key==='csv'?'results':'second-review',multiple:false,types:[{description:'CSV',accept:{'text/csv':['.csv']}}]}));
 const file=await pickRemembered(()=>handle.getFile());
 if(key==='csv'){await loadCSV(file);$('csv-file').value=''}else{await loadReview(file);$('review-file').value=''}
 session[key]=handle;
});
$('pick-folder').onclick=()=>action(async()=>{
 const handle=await pickRemembered(()=>window.showDirectoryPicker({id:'channel-cache',mode:'read'}));
 for(const existing of session.folders)if(await existing.isSameEntry(handle)){sessionText('这个采集数据目录已经记住，无需重复添加。');return}
 await addRememberedFolder(handle);session.folders.push(handle);await renderReport();
});
$('refresh-files').onclick=()=>action(async()=>{session.skipSave=true;await restoreSession(true)});
$('forget-session').onclick=()=>action(async()=>{
 // Suppress automatic saving for this action; current analysis remains open.
 session.skipSave=true;
 if(session.db)await sessionStore(null);session.saved=null;session.csv=null;session.review=null;session.folders=[];$('refresh-files').hidden=true;$('forget-session').hidden=true;sessionText('已忘记上次选择并删除浏览器中的分析副本，当前分析保留。之后新选择的文件会重新记住。');
});
async function initSession(){
 busy(true);
 try{
  session.db=await new Promise((resolve,reject)=>{const request=indexedDB.open('jev-viewer:'+location.pathname,2);request.onupgradeneeded=()=>{for(const name of ['selection','assets'])if(!request.result.objectStoreNames.contains(name))request.result.createObjectStore(name)};request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);request.onblocked=()=>sessionText('请关闭旧版分析页面，再重新打开此页面完成存储升级。')});
  session.saved=await new Promise((resolve,reject)=>{const request=session.db.transaction('selection').objectStore('selection').get('last');request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error)});
  session.snapshot=await new Promise((resolve,reject)=>{const request=session.db.transaction('selection').objectStore('selection').get('view-v2');request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error)});
  session.legacy=!session.snapshot&&await new Promise((resolve,reject)=>{const request=session.db.transaction('selection').objectStore('selection').getKey('view');request.onsuccess=()=>resolve(request.result!==undefined);request.onerror=()=>reject(request.error)});
  for(const id of ['pick-csv','pick-folder','pick-review'])$(id).hidden=!nativeSelection;
  if(nativeSelection)for(const id of ['csv-file','cache-folder','review-file'])$(id).parentElement.hidden=true;
  $('forget-session').hidden=!session.saved;
  if(session.snapshot){session.persistedKeys=new Set(session.snapshot.view.assets.map(item=>item.key));Object.assign(model,session.snapshot.inputs);model.cachedView=session.snapshot.view;customOptions();updateSelection();$('cache-note').textContent='已恢复上次分析的简介和候选标题；封面在查看时按需读取。'}
  if(session.saved)await restoreSession();
  else sessionText('选择后自动保存文件位置、分析结果、类别和编码；下次打开直接显示上次分析。');
 }catch{ordinarySelection();sessionText('此浏览器无法使用本地持久存储；仍可通过普通文件选择分析。')}
 finally{busy(false)}
}
async function loadDemo(){
 if(!bundle.demo||model.lastView||session.saved)return;
 const demo=bundle.demo;
 await action(async()=>{
  const files=demo.files.map(item=>({path:item.path,file:new File([Uint8Array.from(atob(item.base64),c=>c.charCodeAt(0))],item.name)}));
  await addFolder(files);
  await loadCSV(new File([demo.csv],'demo-results.csv',{type:'text/csv'}));
  if(demo.review)await loadReview(new File([demo.review],'demo-second-review.csv',{type:'text/csv'}));
  sessionText('正在展示 6 个真实公开样例及原始模型结果；这是演示子集，不代表全量实验表现。选择自己的文件即可替换。');
 });
}
initSession().then(loadDemo);
