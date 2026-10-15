// Remember choices by default, with a local analysis snapshot for no-click opens.
// Only explicit file refreshes may request read permission; snapshots stay local.
const session={db:null,csv:null,review:null,folders:[],saved:null,restoring:false};
// Use regular inputs for local HTML: exposing the picker API does not guarantee
// that native handles can be read in the file:// context.
const nativeSelection=location.protocol!=='file:'&&typeof window.showOpenFilePicker==='function'&&typeof window.showDirectoryPicker==='function';
function sessionText(text){$('session-note').textContent=text}
function ordinarySelection(){for(const id of ['csv-file','cache-folder','review-file'])$(id).parentElement.hidden=false}
function accessDenied(error){return ['NotAllowedError','SecurityError','NotSupportedError'].includes(error?.name)}
function fileError(error){return accessDenied(error)?'浏览器拒绝读取此文件或目录，请通过普通文件选择重新载入；已有分析缓存保留。':error?.name==='NotFoundError'?'文件已移动或删除，请重新选择。':error.message}
async function pickRemembered(picker){try{return await picker()}catch(error){if(accessDenied(error)){ordinarySelection();sessionText('当前浏览器拒绝读取文件，已显示普通文件选择；已有分析不受影响。');throw Error(fileError(error))}throw error}}
function sessionHandles(saved){return [saved.csv,saved.review,...saved.folders].filter(Boolean)}
function sessionNames(){return [session.csv?.name,session.review?.name,...session.folders.map(h=>h.name)].filter(Boolean).join('、')}
function sessionStore(value,snapshot){return new Promise((resolve,reject)=>{
 const tx=session.db.transaction('selection','readwrite');
 const store=tx.objectStore('selection');
 if(value)store.put(value,'last');else{store.delete('last');store.delete('view')}
 if(snapshot)store.put(snapshot,'view');
 tx.oncomplete=resolve;tx.onabort=tx.onerror=()=>reject(tx.error||Error('无法保存文件选择'));
})}
function snapshotView(){
 if(!model.lastView)return null;
 const payload=structuredClone(model.lastView.payload),refs=[];
 for(const row of payload.rows){refs.push([row,'snapshot']);for(const video of row.videos)refs.push([video,'cover'])}
 if(payload.cover_audit){refs.push([payload.cover_audit,'csv']);for(const row of payload.cover_audit.rows||[]){refs.push([row,'response']);for(const video of row.videos||[])refs.push([video,'cover'])}}
 const used=new Set(refs.map(([obj,key])=>obj[key]).filter(Boolean));
 const selected=model.lastView.assets.filter(item=>used.has(item.id));
 const remap=new Map(selected.map((item,i)=>[item.id,`viewer-asset:${i}`]));
 for(const [obj,key] of refs)if(obj[key])obj[key]=remap.get(obj[key])||null;
 return {date:new Date().toLocaleString('zh-CN'),inputs:model.lastInputs,view:{payload,assets:selected.map((item,i)=>({id:`viewer-asset:${i}`,file:item.file}))}};
}
async function rememberSession(quiet=false){
 if(!session.db||session.restoring)return;
 const saved={version:1,csv:session.csv,review:session.review,folders:session.folders,
  encoding:$('encoding').value,reviewEncoding:$('review-encoding').value,
  category:selectedCategory(),categoryAuto:model.categoryAuto,custom:$('category').value==='custom',positive:$('positive').value,negative:$('negative').value};
 try{const snapshot=model.lastView!==session.persistedView?snapshotView():null;await sessionStore(saved,snapshot);session.saved=saved;session.persistedView=model.lastView;$('forget-session').hidden=false;$('refresh-files').hidden=!nativeSelection||!sessionHandles(saved).length;
  if(!quiet)sessionText(snapshot||model.lastView?`已自动保存上次分析及所用封面，下次打开直接显示。当前选择：${sessionNames()||model.file?.name||''}。`:'文件选择、类别和编码会自动保存。');
 }catch{try{await sessionStore(saved);session.saved=saved;$('forget-session').hidden=false}catch{}sessionText('浏览器无法保存完整分析缓存（可能空间不足），当前分析仍可使用；下次可能需要重新授权读取文件。')}
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
 if(skipped.length&&!entries.length){ordinarySelection();throw Error('所选目录中的文件无法读取，请通过普通文件选择重新添加缓存目录。')}
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
 let index=available.findIndex(c=>c.id===saved.category.id&&c.positive_label===saved.category.positive_label&&c.negative_label===saved.category.negative_label&&(c.report_extension||'')===(saved.category.report_extension||''));
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
  for(const handle of session.folders){if(!allowed(handle))continue;try{say(`正在恢复缓存目录：${handle.name}…`);const skipped=await addRememberedFolder(handle);if(skipped)errors.push(`${handle.name}：已跳过 ${skipped} 个无法读取的文件或子目录`)}catch(error){if(accessDenied(error))ordinarySelection();errors.push(`${handle.name}：${fileError(error)}`)}}
  if(session.csv&&allowed(session.csv))try{await loadCSV(await pickRemembered(()=>session.csv.getFile()));if(saved.custom){$('positive').value=saved.positive;$('negative').value=saved.negative}}catch(error){errors.push(`${session.csv.name}：${fileError(error)}`)}
  if(session.review&&allowed(session.review))try{await loadReview(await pickRemembered(()=>session.review.getFile()))}catch(error){errors.push(`${session.review.name}：${fileError(error)}`)}
  model.restoring=false;await renderReport();
  const waiting=grants.some(value=>value!=='granted');$('refresh-files').hidden=!nativeSelection||!handles.length;
  const cached=Boolean(model.cachedView)&&(waiting||errors.length||!handles.length);
  sessionText(`${cached?`已自动显示上次分析缓存（${session.snapshot.date}）。`:waiting?'上次文件读取权限不可用。':handles.length?`已自动载入：${sessionNames()}。`:'已恢复上次的类别及编码。'}${waiting?(nativeSelection?'如需读取磁盘上的最新改动，可点击“更新本地文件”授权。':'本地 HTML 使用普通文件选择；如需读取磁盘上的新改动，请重新选择文件或目录。'):''}${errors.length?' 部分文件无法读取（可能权限受限、已移动或删除）：'+errors.join('；')+'。可重新选择替换。':''}`);
  if(!waiting&&!errors.length){session.restoring=false;await rememberSession(true)}
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
 for(const existing of session.folders)if(await existing.isSameEntry(handle)){sessionText('这个缓存目录已经记住，无需重复添加。');return}
 await addRememberedFolder(handle);session.folders.push(handle);await renderReport();
});
$('refresh-files').onclick=()=>action(async()=>{session.skipSave=true;await restoreSession(true)});
$('forget-session').onclick=()=>action(async()=>{
 // Suppress automatic saving for this action; current analysis remains open.
 session.skipSave=true;
 if(session.db)await sessionStore(null);session.saved=null;session.csv=null;session.review=null;session.folders=[];$('refresh-files').hidden=true;$('forget-session').hidden=true;sessionText('已忘记上次选择并删除浏览器中的分析缓存，当前分析保留。之后新选择的文件会重新记住。');
});
async function initSession(){
 busy(true);
 try{
  session.db=await new Promise((resolve,reject)=>{const request=indexedDB.open('jev-viewer:'+location.pathname,1);request.onupgradeneeded=()=>request.result.createObjectStore('selection');request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error)});
  session.saved=await new Promise((resolve,reject)=>{const request=session.db.transaction('selection').objectStore('selection').get('last');request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error)});
  session.snapshot=await new Promise((resolve,reject)=>{const request=session.db.transaction('selection').objectStore('selection').get('view');request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error)});
  for(const id of ['pick-csv','pick-folder','pick-review'])$(id).hidden=!nativeSelection;
  if(nativeSelection)for(const id of ['csv-file','cache-folder','review-file'])$(id).parentElement.hidden=true;
  $('forget-session').hidden=!session.saved;
  if(session.snapshot){Object.assign(model,session.snapshot.inputs);model.cachedView=session.snapshot.view;customOptions();updateSelection();$('cache-note').textContent='上次分析使用的简介、候选标题和封面已从浏览器本地缓存载入。';if(model.review)$('review-note').textContent=`已恢复二次核验：${model.review.file.name}`}
  if(session.saved)await restoreSession();
  else sessionText('选择后自动保存文件位置、分析结果、类别和编码；下次打开直接显示上次分析。');
 }catch{ordinarySelection();sessionText('此浏览器无法使用本地持久存储；仍可通过普通文件选择分析。')}
 finally{busy(false)}
}
initSession();
