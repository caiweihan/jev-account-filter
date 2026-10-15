'use strict';
const bundle=JSON.parse(document.getElementById('viewer-bundle').textContent);
const $=id=>document.getElementById(id);
const model={file:null,records:null,ranks:[],hash:'',groups:[],channels:new Map(),categories:[],review:null,busy:false,categoryAuto:true,folderNames:[]};
const available=bundle.categories.map(c=>({...c}));
function say(text,error=false){$('status').textContent=text;$('status').className=error?'error':'ok'}
function busy(value){model.busy=value;document.querySelectorAll('input,select,button').forEach(el=>el.disabled=value);$('clear-cache').disabled=value||(!model.groups.length&&!model.cachedView);$('clear-review').disabled=value||!model.review;$('progress').hidden=!value}
function identity(value){try{const u=new URL(value);return u.hostname+u.pathname.replace(/\/+$/,'')}catch{return ''}}
function normalize(value){const parts=[];for(const p of String(value).replaceAll('\\','/').split('/')){if(!p||p==='.')continue;if(p==='..')parts.pop();else parts.push(p)}return parts.join('/')}
const dirname=path=>path.slice(0,path.lastIndexOf('/'));
const basename=path=>String(path).replaceAll('\\','/').split('/').at(-1);
const imageName=name=>/\.(?:jpe?g|png|webp|gif|avif|bmp|heic|heif)$/i.test(name);
const jsonEscape=value=>JSON.stringify(value).replaceAll('<','\\u003c').replaceAll('&','\\u0026');
function asset(file,assets){const id=`viewer-asset:${assets.length}`;assets.push({id,file});return id}
async function sha256(bytes){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),n=>n.toString(16).padStart(2,'0')).join('')}
function probability(value,line,column){if(value==null||!String(value).trim())return null;const text=String(value).trim();const n=Number(text);if(!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(text)||!Number.isFinite(n)||n<0||n>1)throw Error(`CSV 数据行 ${line}，${column}：无效概率 ${text}`);return n}
function csvTable(text){
 text=text.replace(/^\uFEFF/,'');const records=[];let row=[],field='',quoted=false,closed=false;
 function cell(){row.push(field);field='';closed=false}
 function end(){cell();if(row.some(v=>v!==''))records.push(row);row=[]}
 for(let i=0;i<text.length;i++){
  const c=text[i];if(quoted){if(c==='"'){if(text[i+1]==='"'){field+='"';i++}else{quoted=false;closed=true}}else field+=c;continue}
  if(c==='"'){if(field||closed)throw Error('CSV 引号格式错误。');quoted=true}
  else if(c===',')cell();else if(c==='\n'||c==='\r'){if(c==='\r'&&text[i+1]==='\n')i++;end()}
  else{if(closed)throw Error('CSV 结束引号后存在多余内容。');field+=c}
 }
 if(quoted)throw Error('CSV 存在未闭合的引号。');if(field||row.length||closed)end();
 if(records.length<2)throw Error('CSV 没有数据行。');const headers=records.shift().map(s=>s.trim());
 if(new Set(headers).size!==headers.length)throw Error('CSV 有重复列名。');
 const rows=records.map((fields,index)=>{if(fields.length!==headers.length)throw Error(`CSV 数据行 ${index+1}：列数与表头不符。`);return Object.fromEntries(headers.map((h,i)=>[h,fields[i]]))});
 return{headers,rows};
}
function parseCSV(text){
 const {headers,rows:records}=csvTable(text);
 const required=['账户名称','频道网址','预测结果','人工标注','频道概率'];const missing=required.filter(h=>!headers.includes(h));if(missing.length)throw Error('CSV 缺少必要列：'+missing.join('、'));
 const ranks=headers.map(h=>/^视频(\d+)分数$/.exec(h)).filter(Boolean).map(m=>Number(m[1])).sort((a,b)=>a-b);
 const rows=records.map((raw,index)=>{
  const videos=ranks.map(rank=>({rank,p:probability(raw[`视频${rank}分数`],index+1,`视频${rank}分数`),url:raw[`视频${rank}链接`]?.trim()||''})).filter(v=>v.p!==null||v.url);
  return{id:index+1,name:raw['账户名称'],url:raw['频道网址'].trim(),account_id:raw['账户id']?.trim()||'',platform:raw['平台']?.trim()||'',manual:raw['人工标注'].trim(),prediction:raw['预测结果'].trim(),p:probability(raw['频道概率'],index+1,'频道概率'),videos};
 });return{rows,ranks};
}
function parseReview(text){
 const {headers,rows}=csvTable(text),urlField=['主页网址','频道网址'].find(k=>headers.includes(k)),idField=headers.includes('账户id')?'账户id':null,labelField=['二次标注','审核结果','人工标注'].find(k=>headers.includes(k));
 if((!urlField&&!idField)||!labelField)throw Error('核验 CSV 需要“主页网址”或“账户id”，以及“审核结果”（也支持“二次标注”“人工标注”）。');
 return rows.map((row,i)=>({line:i+1,url:row[urlField]?.trim()||'',account_id:row[idField]?.trim()||'',label:row[labelField].trim(),name:row['账户昵称']||row['账户名称']||'',platform:row['平台']?.trim()||''}));
}
function attachReview(rows,labels){
 if(!model.review)return null;
 const groups=new Map(),byURL=new Map(),byID=new Map(),issues=[],assignments=new Map();
 const add=(map,key,value)=>{if(!key)return;const list=map.get(key)||[];list.push(value);map.set(key,list)};
 for(const row of rows){add(byURL,identity(row.url),row);add(byID,row.account_id,row)}
 for(const raw of model.review.rows){const url=identity(raw.url),key=url?'url:'+url:raw.account_id?'id:'+raw.account_id:'';
  if(!key){issues.push({...raw,reason:'缺少有效主页网址和账户id'});continue}add(groups,key,raw);
 }
 for(const entries of groups.values()){
  const raw=entries[0],hasURL=Boolean(identity(raw.url));
  const targets=(hasURL?byURL.get(identity(raw.url)):byID.get(raw.account_id))||[];
  if(targets.length!==1){entries.forEach(r=>issues.push({...r,reason:targets.length?'结果中匹配到多个频道，未合并':'未匹配到结果频道；仅ID核验需要结果CSV也有账户id列'}));continue}
  const row=targets[0];for(const entry of entries){if(entry.account_id&&row.account_id&&entry.account_id!==row.account_id){issues.push({...entry,reason:'主页网址匹配，但账户id与结果不一致'});continue}add(assignments,row.id,entry)}
 }
 let duplicates=0,matched=0,conflicts=0,unknown=0;
 const normalizeLabel=value=>value==='1'?labels[0]:value==='0'?labels[1]:value==='-1'?labels[2]:value;
 for(const [id,entries] of assignments){
  const row=rows.find(r=>r.id===id),raw=entries[0],choices=new Set(entries.map(r=>normalizeLabel(r.label)));
  const label=[...choices][0],status=choices.size>1?'conflict':labels.includes(label)?'valid':'unknown';
  row.second_review={status,label:status==='valid'?label:null,raw_label:entries.map(r=>r.label).join(' / '),account_id:raw.account_id,lines:entries.map(r=>r.line)};
  if(status==='conflict'){conflicts++;entries.forEach(r=>issues.push({...r,reason:'重复频道的二次标签冲突，未计入统计'}))}
  else if(status==='unknown'){unknown++;entries.forEach(r=>issues.push({...r,reason:'二次标签为空或不属于当前类别'}))}
  else{matched++;duplicates+=entries.length-1}
 }
 return{source:model.review.file.name,total:model.review.rows.length,matched,duplicates,conflicts,unknown,issues};
}
function categoryOption(category){const option=document.createElement('option');option.value=String(available.length);option.textContent=category.name;available.push(category);$('category').append(option);return option.value}
// The compiler supplies category choices; the shared viewer has no task/provider default.
bundle.categories.forEach((c,i)=>$('category').append(new Option(c.name,String(i))));
function validCategory(c){return c&&['name','positive_label','negative_label'].every(k=>typeof c[k]==='string'&&c[k].trim()&&c[k].length<200)&&c.positive_label!==c.negative_label&&!['疑难'].some(v=>v===c.positive_label||v===c.negative_label)}
function selectedCategory(){if($('category').value==='custom'){const p=$('positive').value,n=$('negative').value;if(!p||!n)return null;if(p===n)throw Error('正类与负类标签必须不同。');return{id:'custom',name:p,positive_label:p,negative_label:n}}return available[Number($('category').value)]&&$('category').value!==''?available[Number($('category').value)]:null}
function customOptions(){const values=[...new Set(model.records.flatMap(r=>[r.manual,r.prediction]))].filter(v=>v&&v!=='疑难');for(const id of ['positive','negative']){const previous=$(id).value;$(id).replaceChildren(new Option('请选择',''),...values.map(v=>new Option(v,v)));if(values.includes(previous))$(id).value=previous}}
function inferCategory(){
 if(!model.categoryAuto)return;
 const labels=new Set(model.records.flatMap(row=>[row.manual,row.prediction]).filter(Boolean));
 const candidates=available.map((category,index)=>({category,index})).filter(({category})=>[category.positive_label,category.negative_label].some(label=>labels.has(label))&&!model.records.some(row=>row.p!=null&&![category.positive_label,category.negative_label,'疑难'].includes(row.prediction)));
 const unique=[...new Map(candidates.map(item=>[JSON.stringify([item.category.positive_label,item.category.negative_label,item.category.report_extension||'']),item])).values()];
 $('category').value=unique.length===1?String(unique[0].index):'';
}
function updateSelection(){
 $('csv-selected').textContent=model.file?.name||'尚未选择';$('review-selected').textContent=model.review?.file.name||'尚未选择';$('folder-selected').textContent=model.folderNames.length?model.folderNames.join('；'):'尚未添加';
 const category=selectedCategory();$('selection-summary').textContent=`分析类别：${category?.name||'尚未确定'}${model.categoryAuto?'（自动）':''} · 结果编码：${model.encodingDetected||'自动识别'}${model.review?' · 核验编码：'+(model.reviewEncodingDetected||'自动识别'):''}。`;
}
function decodeCSV(bytes,choice,kind){
 const array=new Uint8Array(bytes),automatic=choice==='auto',encodings=automatic?(array[0]===255&&array[1]===254?['utf-16le']:array[0]===254&&array[1]===255?['utf-16be']:['utf-8','gb18030']):[choice];
 for(const encoding of encodings)try{return{text:new TextDecoder(encoding,{fatal:true}).decode(bytes),encoding}}catch{}
 $('advanced-settings').open=true;throw Error(`${kind} 编码无法解码，请在分析设置中指定 UTF-8 / GB18030。`);
}
function useCacheCategory(roots){
 if(!model.records||($('category').value&&!model.categoryAuto))return false;
 const entries=model.categories.filter(x=>roots.some(root=>x.group===root.group&&x.folder===root.folder));
 const candidates=[...new Map(entries.filter(x=>validCategory(x.value)).map(x=>[JSON.stringify([x.value.name,x.value.positive_label,x.value.negative_label,x.value.report_extension||'']),x.value])).values()];
 if(candidates.length!==1)return false;const c=candidates[0];let i=available.findIndex(x=>x.positive_label===c.positive_label&&x.negative_label===c.negative_label&&(x.report_extension||'')===(c.report_extension||''));
 if(i<0)i=Number(categoryOption(c));$('category').value=String(i);return true;
}
async function matchingRoots(){
 const roots=[];if(!model.file)return roots;
 for(const group of model.groups)for(const entry of group.csv){if(entry.file.name===model.file.name){entry.hash??=await sha256(await entry.file.arrayBuffer());if(entry.hash===model.hash)roots.push({group:group.id,folder:dirname(entry.path)})}}
 return roots;
}
async function pool(items,action){let next=0,done=0;await Promise.all(Array.from({length:Math.min(8,items.length)},async()=>{while(next<items.length){await action(items[next++]);done++;if(done%25===0||done===items.length){$('progress').value=done;$('progress').max=Math.max(1,items.length);say(`索引频道缓存 ${done}/${items.length}…`);await new Promise(resolve=>setTimeout(resolve,0))}}}))}
async function addFolder(files){
 if(!files.length)return;const group={id:model.groups.length,files:new Map(),names:new Map(),csv:[]},metadata=[];
 for(const item of files){const file=item.file||item,path=normalize(item.path||file.webkitRelativePath||file.name),entry={group:group.id,path,file};group.files.set(path,entry);const names=group.names.get(file.name)||[];names.push(entry);group.names.set(file.name,names);if(file.name.endsWith('.csv'))group.csv.push(entry);if(['channel.json','category.json'].includes(file.name))metadata.push(entry)}
 let invalid=0;await pool(metadata,async entry=>{try{const value=JSON.parse((await entry.file.text()).replace(/^\uFEFF/,''));if(entry.file.name==='category.json'){model.categories.push({group:group.id,folder:dirname(entry.path),value});return}const key=identity(value.url);if(!key)return;const records=model.channels.get(key)||[];records.push({...entry,folder:dirname(entry.path),value});model.channels.set(key,records)}catch{invalid++}});
 group.name=normalize(files[0].path||files[0].webkitRelativePath||files[0].file?.name||files[0].name).split('/')[0];model.folderNames=[...new Set([...model.folderNames,group.name])];model.groups.push(group);updateSelection();$('cache-note').textContent=`已添加：${model.folderNames.join('；')}。共 ${model.channels.size} 个频道的快照${invalid?`；${invalid} 个 JSON 无法读取，已跳过`:''}。可继续添加实验目录或封面所在目录。`;
}
function findCover(record,cached){
 const group=model.groups[record.group],name=basename(cached.cover_path||`${cached.id}.jpg`);
 if(!imageName(name))return null;
 const direct=group.files.get(normalize(record.folder+'/'+(cached.cover_path||'covers/'+name)));if(direct&&imageName(direct.file.name))return direct;
 const fallback=group.files.get(normalize(record.folder+'/covers/'+`${cached.id}.jpg`));if(fallback)return fallback;
 const candidates=model.groups.flatMap(g=>g.names.get(name)||[]);if(candidates.length===1)return candidates[0];
 const target=normalize(cached.cover_path||record.folder+'/covers/'+name).split('/');let best=null,score=1,tie=false;
 for(const entry of candidates){const parts=entry.path.split('/');let n=0;while(n<Math.min(parts.length,target.length)&&parts.at(-1-n)===target.at(-1-n))n++;if(n>score){score=n;best=entry;tie=false}else if(n===score)tie=true}
 return best&&!tie?best:null;
}
async function enrich(rows,roots,assets){
 const savedRows=new Map((model.cachedView?.payload.rows||[]).map(row=>[identity(row.url),row]));
 let matched=0,covers=0,titles=0;for(let i=0;i<rows.length;i++){
  const row=rows[i],candidates=(model.channels.get(identity(row.url))||[]).map(record=>{const match=roots.some(r=>r.group===record.group&&record.folder.startsWith(r.folder+'/intermediate/'));const ids=new Set((record.value.videos||[]).map(v=>identity(v.url)).filter(Boolean));return{record,score:(match?100000:0)+row.videos.filter(v=>ids.has(identity(v.url))).length}}).sort((a,b)=>b.score-a.score);
  const record=candidates[0]?.record;row.bio='';row.page_count=null;row.no_posts=false;row.snapshot=null;
  for(const video of row.videos){video.title='';video.title_p=null;video.cover=null}
  if(record){matched++;row.bio=typeof record.value.bio==='string'?record.value.bio:'';row.no_posts=Boolean(record.value.no_posts);row.page_count=Array.isArray(record.value.videos)?record.value.videos.length:null;row.snapshot=asset(new Blob([JSON.stringify(record.value,null,2)],{type:'application/json'}),assets);
   const byURL=new Map((record.value.videos||[]).filter(v=>identity(v.url)).map(v=>[identity(v.url),v]));
   const rankingFile=model.groups[record.group].files.get(record.folder+'/title-ranking.json');let ranking={};if(rankingFile){try{rankingFile.value??=JSON.parse(await rankingFile.file.text());ranking=Object.fromEntries((rankingFile.value.videos||[]).map(v=>[v.id,v.title_probability]))}catch{}}
   for(const video of row.videos){const cached=byURL.get(identity(video.url));if(!cached)continue;video.title=typeof cached.title==='string'?cached.title:'';titles+=Boolean(video.title);const p=ranking[cached.id];video.title_p=typeof p==='number'&&Number.isFinite(p)&&p>=0&&p<=1?p:null;const cover=findCover(record,cached);if(cover){video.cover=asset(cover.file,assets);covers++}}
  }else if(savedRows.has(identity(row.url))){
   const saved=savedRows.get(identity(row.url));row.bio=saved.bio;row.page_count=saved.page_count;row.no_posts=saved.no_posts;row.snapshot=saved.snapshot;if(saved.snapshot)matched++;
   const videos=new Map(saved.videos.map(video=>[identity(video.url),video]));for(const video of row.videos){const cached=videos.get(identity(video.url));if(!cached)continue;for(const key of ['title','title_p','cover'])video[key]=cached[key];titles+=Boolean(video.title);covers+=Boolean(video.cover)}
  }
  if(i%100===0){$('progress').max=rows.length;$('progress').value=i;say(`匹配 CSV 与缓存 ${i+1}/${rows.length}…`);await new Promise(resolve=>setTimeout(resolve,0))}
 }return{matched,covers,titles};
}
function summarize(rows,labels){
 const comparable=rows.filter(r=>r.comparable),wrong=comparable.filter(r=>r.wrong),matrix=labels.map(a=>labels.map(b=>comparable.filter(r=>r.manual===a&&r.prediction===b).length));
 const predicted=comparable.filter(r=>r.prediction===labels[0]&&r.manual!==labels[1]).length,positive=comparable.filter(r=>r.manual===labels[0]).length;
 const counts=list=>Object.fromEntries(labels.map(l=>[l,list.filter(r=>r.manual===l).length]).filter(([,n])=>n));
 return{total:rows.length,comparable:comparable.length,matched:comparable.length-wrong.length,mismatch:wrong.length,matrix,accuracy:comparable.length?(comparable.length-wrong.length)/comparable.length:null,precision:predicted?matrix[0][0]/predicted:null,recall:positive?matrix[0][0]/positive:null,missing_p:rows.filter(r=>r.p===null).length,no_posts:rows.filter(r=>r.no_posts).length,missing_cover:rows.reduce((n,r)=>n+r.videos.filter(v=>!v.cover).length,0),high_confidence_mismatch:wrong.filter(r=>r.p!==null&&(r.p>=.95||r.p<=.05)).length,manual_counts:counts(comparable),wrong_manual_counts:counts(wrong)};
}
async function auditData(roots,assets){
 for(const root of roots){const group=model.groups[root.group],pointer=group.files.get(root.folder+'/cover-audit/latest.json');if(!pointer)continue;
  try{const latest=JSON.parse(await pointer.file.text()),entry=group.files.get(normalize(root.folder+'/'+latest.path));if(!entry)continue;const audit=JSON.parse(await entry.file.text());if(audit.source_sha256!==model.hash)continue;
   for(const row of audit.rows||[])for(const video of row.videos||[]){const record={group:root.group,folder:root.folder};const file=video.cover&&findCover(record,{id:video.id,cover_path:video.cover});video.cover=file?asset(file.file,assets):null}
   for(const row of audit.rows||[]){const entry=row.response&&group.files.get(normalize(root.folder+'/'+row.response));row.response=entry?asset(new Blob([await entry.file.text()],{type:'application/json'}),assets):null}
   const csv=group.files.get(normalize(root.folder+'/'+audit.csv));audit.csv=csv?asset(csv.file,assets):'';return audit;
  }catch{}
 }return null;
}
async function renderReport(){
 if(model.restoring)return;
 if(!model.records){updateSelection();say('请选择结果 CSV。已添加的缓存及二次核验会在载入后匹配。');return}const roots=await matchingRoots();if(!useCacheCategory(roots))inferCategory();const category=selectedCategory();updateSelection();if(!category){$('advanced-settings').open=true;say('CSV 已读取。无法唯一识别类别，请选择分析类别，或指定自定义正类、负类标签。');return}
 const assets=model.cachedView?[...model.cachedView.assets]:[];
  const rows=structuredClone(model.records),labels=[category.positive_label,'疑难',category.negative_label];
  for(const row of rows){row.comparable=labels.includes(row.manual)&&labels.includes(row.prediction);row.wrong=row.comparable&&row.manual!==row.prediction;const values=row.videos.map(v=>v.p).filter(v=>v!==null);row.max=values.length?Math.max(...values):null;row.mean=values.length?values.reduce((a,b)=>a+b,0)/values.length:null;row.gap=values.length&&row.p!==null?row.max-row.p:null;row.spread=values.length>1?values[0]-values[1]:null}
  const metadata=await enrich(rows,roots,assets),extension=category.report_extension||'',supported=Object.hasOwn(bundle.templates,extension),template=supported?bundle.templates[extension]:bundle.templates[''];
  const payload={rows,ranks:model.ranks,labels,summary:summarize(rows,labels),category:{id:category.id||'custom',name:category.name,report_extension:extension},source:model.file.name,sha256:model.hash,generated:new Date().toLocaleString('zh-CN')};
  const review=attachReview(rows,labels);if(review)payload.second_review=review;
  if(extension&&supported){const audit=await auditData(roots,assets)||(model.cachedView?.payload.sha256===model.hash?model.cachedView.payload.cover_audit:null);if(audit)payload.cover_audit=audit}
  await showReport(payload,assets);
  if(review)$('review-note').textContent=`${review.source}：${review.total} 条核验，匹配 ${review.matched} 个频道；一致重复 ${review.duplicates} 条、冲突 ${review.conflicts} 组、未知标签 ${review.unknown} 组。已合并至分类性能与错误分析；匹配问题见数据质量说明。`;
  say(`已载入 ${rows.length} 个频道；可对照 ${payload.summary.comparable}，不符 ${payload.summary.mismatch}。缓存匹配 ${metadata.matched}/${rows.length} 个频道，标题 ${metadata.titles} 条，封面 ${metadata.covers} 张。${review?`二次核验匹配 ${review.matched} 个频道。`:''}${extension&&!supported?'此页面未打包该类别扩展，使用通用分析。':''}`);
}
async function showReport(payload,assets){
 const extension=payload.category.report_extension||'',template=bundle.templates[extension]||bundle.templates[''];
 const html=template.replace('__VIEWER_PAYLOAD__',()=>jsonEscape(payload)),token=crypto.randomUUID();
 model.reportToken=token;
 await new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>{window.removeEventListener('message',ready);reject(Error('分析页面载入超时，请重新打开页面。'))},15000);
  function ready(event){if(event.source!==$('report').contentWindow||event.data?.type!=='viewer-ready'||event.data.token!==token)return;clearTimeout(timer);window.removeEventListener('message',ready);resolve()}
  window.addEventListener('message',ready);
  $('report').onload=()=>$('report').contentWindow.postMessage({type:'viewer-files',token,assets},'*');$('report').srcdoc=html;$('report').hidden=false;$('empty').hidden=true;
 });
 model.lastView={payload,assets};
 model.lastInputs={file:model.file,records:model.records,ranks:model.ranks,hash:model.hash,review:model.review,folderNames:model.folderNames,encodingDetected:model.encodingDetected,reviewEncodingDetected:model.reviewEncodingDetected};
}
window.addEventListener('message',event=>{if(event.source!==$('report').contentWindow||event.data?.token!==model.reportToken||event.data.type!=='viewer-height')return;const height=event.data.height;if(Number.isFinite(height)&&height>=300&&height<=1000000&&Math.abs($('report').getBoundingClientRect().height-height)>1)$('report').style.height=height+'px'});
async function loadCSV(file){const bytes=await file.arrayBuffer(),decoded=decodeCSV(bytes,$('encoding').value,'结果 CSV'),parsed=parseCSV(decoded.text);model.encodingDetected=decoded.encoding;model.file=file;model.records=parsed.rows;model.ranks=parsed.ranks;model.hash=await sha256(bytes);customOptions();updateSelection();await renderReport()}
async function action(work){if(model.busy)return false;busy(true);try{await work();return true}catch(error){if(error.name!=='AbortError')say(`${error.message}${!$('report').hidden?'\n新数据未载入，分析区仍显示上一次成功载入的结果。':''}`,true);return false}finally{busy(false)}}
async function loadReview(file){const bytes=await file.arrayBuffer(),decoded=decodeCSV(bytes,$('review-encoding').value,'核验 CSV'),rows=parseReview(decoded.text);model.reviewEncodingDetected=decoded.encoding;model.review={file,rows};updateSelection();$('review-note').textContent=`已读取 ${file.name}，${rows.length} 条，等待与结果匹配。`;await renderReport()}
$('csv-file').onchange=()=>{const file=$('csv-file').files[0];if(file)action(()=>loadCSV(file))};
$('cache-folder').onchange=()=>{const files=Array.from($('cache-folder').files);if(files.length)action(async()=>{await addFolder(files);$('cache-folder').value='';await renderReport()})};
$('category').onchange=()=>{model.categoryAuto=$('category').value==='';$('custom-labels').hidden=$('category').value!=='custom';action(renderReport)};
for(const id of ['positive','negative'])$(id).onchange=()=>action(renderReport);
$('encoding').onchange=()=>{const file=$('csv-file').files[0]||model.file;action(async()=>{if(file)await loadCSV(file)})};
$('clear-cache').onclick=()=>action(async()=>{model.groups=[];model.folderNames=[];model.channels.clear();model.categories=[];model.cachedView=null;updateSelection();$('cache-note').textContent='已清除缓存选择。仅使用 CSV 分析，简介、标题和封面暂缺。';await renderReport()});
$('review-file').onchange=()=>{const file=$('review-file').files[0];if(file)action(()=>loadReview(file))};
$('review-encoding').onchange=()=>{const file=$('review-file').files[0]||model.review?.file;action(async()=>{if(file)await loadReview(file)})};
$('clear-review').onclick=()=>action(async()=>{model.review=null;$('review-file').value='';updateSelection();$('review-note').textContent='已清除二次核验，原人工标注保持不变。';await renderReport()});
for(const [button,input] of [['choose-csv','csv-file'],['choose-folder','cache-folder'],['choose-review','review-file']])$(button).onclick=()=>$(input).click();
