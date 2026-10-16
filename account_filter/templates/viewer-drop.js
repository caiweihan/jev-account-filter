// Dragging files grants read access without opening the native file chooser.
async function droppedDirectoryFiles(entries){
 const files=[];
 const readFile=entry=>new Promise((resolve,reject)=>entry.file(resolve,reject));
 const readEntries=reader=>new Promise((resolve,reject)=>reader.readEntries(resolve,reject));
 async function walk(entry){
  if(entry.isDirectory){const reader=entry.createReader();let batch;while((batch=await readEntries(reader)).length)for(const child of batch)await walk(child)}
  else if(entry.isFile&&(imageName(entry.name)||/\.(json|csv)$/i.test(entry.name))){files.push({file:await readFile(entry),path:normalize(entry.fullPath||entry.name)});if(files.length%100===0){say(`正在读取拖入的采集数据目录：${files.length} 个文件…`);await new Promise(resolve=>setTimeout(resolve,0))}}
 }
 for(const entry of entries)await walk(entry);return files;
}
function acceptDroppedFiles(kind,files,entries){return action(async()=>{
 if(kind==='folder'){
  if(!entries.length||entries.some(entry=>!entry?.isDirectory))throw Error('请将采集数据目录拖到这一行；结果 CSV 和核验 CSV 请拖到各自对应行。');
  const selected=await droppedDirectoryFiles(entries);if(!selected.length)throw Error('拖入的目录没有可用的 JSON、CSV 或图片文件。');
  session.folders=[];await addFolder(selected);await renderReport();return;
 }
 if(files.length!==1||!files[0].name.toLowerCase().endsWith('.csv'))throw Error('请在这一行拖入一个 CSV 文件。');
 if(kind==='csv'){session.csv=null;$('csv-file').value='';await loadCSV(files[0])}
 else{session.review=null;$('review-file').value='';await loadReview(files[0])}
})}
for(const row of document.querySelectorAll('[data-drop-kind]')){
 row.addEventListener('dragover',event=>{event.preventDefault();if(model.busy)return;event.dataTransfer.dropEffect='copy';row.classList.add('drag-over')});
 row.addEventListener('dragleave',event=>{if(!row.contains(event.relatedTarget))row.classList.remove('drag-over')});
 row.addEventListener('drop',event=>{
  event.preventDefault();row.classList.remove('drag-over');if(model.busy)return;
  // Capture access grants during the drop event, before the first async step.
  const files=Array.from(event.dataTransfer.files),entries=Array.from(event.dataTransfer.items||[]).filter(item=>item.kind==='file').map(item=>item.webkitGetAsEntry?.()).filter(Boolean);
  acceptDroppedFiles(row.dataset.dropKind,files,entries);
 });
}
document.addEventListener('dragover',event=>event.preventDefault());
document.addEventListener('drop',event=>{event.preventDefault();if(!event.target.closest('[data-drop-kind]'))say('请将 CSV 或采集数据目录拖到上方对应的文件行。')});
