function evidence(){const fp=D.rows.filter(r=>r.manual===L[2]&&r.prediction===L[0]&&r.p>=.95).sort((a,b)=>b.p-a.p),fn=D.rows.filter(r=>r.manual===L[0]&&r.prediction===L[2]&&r.p!=null).sort((a,b)=>a.p-b.p);const samples=[{r:fp.find(r=>r.name.includes('手语')&&r.videos.some(v=>v.title.includes('手语'))),text:'当前标题与简介有手语线索，但人工标为非手语。需要核查标注与当前目标是否一致。'},{r:fp.find(r=>r.videos.some(v=>v.title.includes('手语新闻'))),text:'综合账号也可能包含手语内容。“有手语视频”与“专门发布手语的账号”是不同口径。'},{r:fn[0],text:'人工标为手语，本轮候选却得到低分。需要核查是否有更早的手语视频未被第一页覆盖。'}].filter(s=>s.r);$('evidence').innerHTML=samples.map(({r,text})=>`<article class="insight"><h3>${esc(r.name)}</h3><div class="note">人工 ${esc(r.manual)} · 预测 ${esc(r.prediction)} · 频道 ${fmt(r.p)}</div><p>${esc(text)}</p><p>候选标题：“${esc(Array.from(r.videos.find(v=>v.title.includes('手语新闻'))?.title||r.videos[0]?.title||'无标题').slice(0,90).join(''))}”</p><p><button data-evidence="${r.id}">查看标题与封面</button></p></article>`).join('')||'<p class="note">当前数据没有对应场景样例，可从频道明细选择复核对象。</p>';$('evidence').querySelectorAll('[data-evidence]').forEach(el=>el.onclick=()=>openCase(Number(el.dataset.evidence)))}
const countState={mode:'single-low',group:'fixed',includeAmbiguous:false,search:'',page:0};
function countSelected(p){return p!=null&&(countState.mode==='single-low'?p>.1:p>=.8)}
function countBoundary(){return countState.mode==='single-low'?'>0.1':'≥0.8'}
function countComparison(r){
 const valid=r.videos.filter(v=>v.p!=null),count=valid.filter(v=>countSelected(v.p)).length;
 const eligible=r.comparable&&(countState.includeAmbiguous||r.manual!==L[1])&&(valid.length>0||r.no_posts);
 const predicted=countState.mode==='single-low'?(r.prediction===L[1]?(count>=2?L[0]:L[2]):r.prediction===L[0]&&count===1?L[2]:r.prediction):countState.mode==='binary'?(count>=2?L[0]:L[2]):(r.prediction===L[0]&&count<2?L[2]:r.prediction);
 const before=r.prediction===r.manual,after=predicted===r.manual,changed=r.prediction!==predicted;
 return{count,predicted,eligible,changed,kind:!eligible?'excluded':!changed?'unchanged':!before&&after?'fixed':before&&!after?'harmed':'other',before,after};
}
function countBadge(c){const text=c.kind==='unchanged'&&c.eligible&&!c.after?'仍不符（未改判）':{fixed:'变对',harmed:'变错',other:'改判后仍不符',unchanged:'预测未改',excluded:'不参与本口径对照'}[c.kind];return `<span class="badge ${c.kind==='fixed'?'green':c.eligible&&!c.after?'red':''}">${text}</span>`}
function countScoreStrip(r){return `<div class="score-strip">${D.ranks.slice(0,5).map(k=>{const p=r.videos.find(v=>v.rank===k)?.p??null;return `<span title="视频${k}：${fmt(p)}${countSelected(p)?' · 计入数量':''}" style="background:${p==null?'#f2f4f7':countSelected(p)?'#cdece2':'#eef1f6'}">${p==null?'—':p.toFixed(2)}</span>`}).join('')}</div>`}
function countMetrics(evaluated){
 const explicit=evaluated.filter(x=>x.r.manual===L[0]||x.r.manual===L[2]);
 const stats=useNew=>{let tp=0,fp=0,fn=0;for(const {r,c} of explicit){const prediction=useNew?c.predicted:r.prediction;if(prediction===L[0]){if(r.manual===L[0])tp++;else fp++}else if(r.manual===L[0])fn++}return{precision:tp+fp?tp/(tp+fp):null,recall:tp+fn?tp/(tp+fn):null,f1:2*tp+fp+fn?2*tp/(2*tp+fp+fn):null,tp,fp,fn}};
 const old=stats(false),next=stats(true),acc=useNew=>evaluated.length?evaluated.filter(x=>useNew?x.c.after:x.c.before).length/evaluated.length:null;
 const percent=p=>p==null?'—':(p*100).toFixed(2)+'%',diff=(a,b)=>a==null||b==null?'—':((b-a)*100>=0?'+':'')+((b-a)*100).toFixed(2)+' 个百分点';
 $('count-metrics').innerHTML='<table class="stat-table"><thead><tr><th>指标</th><th>原预测</th><th>模拟预测</th><th>变化</th></tr></thead><tbody>'+[['与原标注一致率',acc(false),acc(true)],['手语精确率',old.precision,next.precision],['手语召回率',old.recall,next.recall],['手语 F1',old.f1,next.f1]].map(([name,a,b])=>`<tr><td>${name}</td><td>${percent(a)}</td><td>${percent(b)}</td><td>${diff(a,b)}</td></tr>`).join('')+`</tbody></table><p class="note">本模拟沿用原人工标注计算一致率，不随上方评估参考切换；精确率、召回率和 F1 仅在人工明确正负类中计算，模型“疑难”不算正类命中。误判为手语 ${old.fp} → ${next.fp} 条；人工手语未判为手语 ${old.fn} → ${next.fn} 条（包括模型疑难）。</p>`;
}
function countReview(){
 const evaluated=D.rows.map(r=>({r,c:countComparison(r)})),eligible=evaluated.filter(x=>x.c.eligible),changed=eligible.filter(x=>x.c.changed);
 const fixed=changed.filter(x=>x.c.kind==='fixed'),harmed=changed.filter(x=>x.c.kind==='harmed'),other=changed.filter(x=>x.c.kind==='other');
 $('count-fixed').textContent=nfmt(fixed.length);$('count-harmed').textContent=nfmt(harmed.length);
 const remaining=eligible.filter(x=>!x.c.after);$('count-remaining').textContent=nfmt(remaining.length);
 const single=countState.mode==='single-low';
 $('count-heading').textContent=single?'候选数量规则的敏感性分析':'候选数量规则的分类结果变化';
 $('count-caption').textContent=single?'原手语恰好1条 >0.1 时改非手语；原疑难至少2条 >0.1 时判手语，否则非手语。':'以 CSV 原预测为基准，只数候选中分数 ≥0.8 的视频。原结果和人工标注保持不变。';
 $('count-rule-note').textContent=single?'当前规则：原预测手语且恰好 1 个分数 >0.1 的候选时改非手语；原预测疑难有至少 2 个分数 >0.1 的候选时改手语，否则非手语。原预测非手语不改；原手语有0个或至少2个不改。严格大于0.1，等于0.1不计数。':countState.mode==='binary'?'当前规则：至少 2 个分数 ≥0.8 的候选判手语，否则判非手语；原模型疑难也会重新划分。':'当前规则：仅将原预测手语且不足 2 个高分候选的频道改为非手语；其它原标签，包括模型疑难，保持不变。';
 countMetrics(eligible);
 const before=eligible.filter(x=>x.c.before).length,after=eligible.filter(x=>x.c.after).length;
 $('count-summary').textContent=`全量可对照 ${eligible.length} 条 · ${countState.includeAmbiguous?'包括人工疑难':'排除人工疑难及无法对照项'} · 改判 ${changed.length} 条，其中 ${other.length} 条改判后仍不符。准确率 ${pct(eligible.length?before/eligible.length:null)} → ${pct(eligible.length?after/eligible.length:null)}。绿色视频分数格表示计入数量。`;
 if(single){const resolved=eligible.filter(x=>x.r.prediction===L[1]);$('count-summary').textContent+=` 原模型疑难 ${resolved.length} 条分流：${resolved.filter(x=>x.c.predicted===L[0]).length} 条手语、${resolved.filter(x=>x.c.predicted===L[2]).length} 条非手语，${resolved.filter(x=>x.c.after).length} 条符合人工标注。`}
 const query=countState.search.trim().toLowerCase(),pool=countState.group==='remaining'?remaining:changed,rows=pool.filter(x=>(countState.group==='all'||countState.group==='remaining'||x.c.kind===countState.group)&&(!query||`${x.r.name} ${x.r.bio}`.toLowerCase().includes(query))).sort((a,b)=>a.r.id-b.r.id);
 const pages=Math.max(1,Math.ceil(rows.length/pageSize));countState.page=Math.min(countState.page,pages-1);
 const visible=rows.slice(countState.page*pageSize,(countState.page+1)*pageSize);
 $('count-list-title').textContent=({fixed:'新增一致账户',harmed:'新增不一致账户',all:'全部改判账户',remaining:'模拟后仍与原标注不一致的账户'}[countState.group])+`（当前 ${rows.length} 条）`;
 $('count-table').innerHTML=rows.length?'<table class="case-table count-table"><thead><tr><th>CSV 行</th><th>账户</th><th>人工标注</th><th>原预测</th><th>模拟预测</th><th>改判结果</th><th>分数 '+countBoundary()+' 的视频数</th><th>原频道概率</th><th>原视频分数（降序）</th><th>封面预览</th><th>复核</th></tr></thead><tbody>'+visible.map(({r,c})=>`<tr data-count-row="${r.id}"><td class="muted">${r.id}</td><td class="name">${esc(r.name)}<div class="small">${link(r.url,'打开频道 ↗')}</div></td><td>${esc(r.manual)}</td><td>${esc(r.prediction)}</td><td><b>${esc(c.predicted)}</b></td><td>${countBadge(c)}</td><td class="num">${c.count} / ${r.videos.filter(v=>v.p!=null).length}</td><td class="num">${fmt(r.p)}</td><td>${countScoreStrip(r)}</td><td><div class="mini-covers">${r.videos.filter(v=>v.cover).slice(0,2).map(v=>`<img src="${esc(encodeURI(v.cover))}" alt="视频${v.rank}封面" loading="lazy">`).join('')||'<span class="note">无本地封面</span>'}</div></td><td><button data-count-case="${r.id}">标题与封面</button></td></tr>`).join('')+'</tbody></table>':'<div class="empty">这组频道在当前条件下为空。</div>';
 $('count-table').querySelectorAll('[data-count-case]').forEach(el=>el.onclick=()=>openCase(Number(el.dataset.countCase)));
 $('count-table').querySelectorAll('img').forEach(img=>img.onerror=()=>{img.remove()});
 $('count-page-note').textContent=`${rows.length?countState.page*pageSize+1:0}–${Math.min(rows.length,(countState.page+1)*pageSize)} / ${rows.length} 条 · 第 ${countState.page+1}/${pages} 页`;
 $('count-previous').disabled=countState.page===0;$('count-next').disabled=countState.page>=pages-1;
 document.querySelectorAll('[data-count-group]').forEach(el=>el.classList.toggle('active',el.dataset.countGroup===countState.group));$('count-all').classList.toggle('active',countState.group==='all');
}
function showCountDetail(r){
 const c=countComparison(r),single=countState.mode==='single-low',note=single?'原手语恰好1条 >0.1 时改非手语；原疑难至少2条 >0.1 时判手语，否则非手语':countState.mode==='binary'?'至少2条 ≥0.8 的数量直接二分类':'仅对原预测手语项增加至少2条 ≥0.8 门槛';
 $('detail-content').querySelector('.bio').insertAdjacentHTML('beforebegin',`<div class="count-detail"><b>规则模拟 · ${note}</b><div>原预测 ${esc(r.prediction)} → 模拟预测 <b>${esc(c.predicted)}</b> · ${countBadge(c)}</div><div class="note">分数 ${countBoundary()} 的视频 ${c.count} / ${r.videos.filter(v=>v.p!=null).length}；${countState.includeAmbiguous?'包括':'排除'}人工疑难。仅改变模拟标签，原概率和原结果不变。</div></div>`);
 $('detail-content').querySelectorAll('.video').forEach((el,i)=>{const p=r.videos[i].p,counted=countSelected(p);el.querySelector('.body').insertAdjacentHTML('afterbegin',`<div class="count-flag ${counted?'yes':'no'}">${p==null?'分数缺失，不计数':counted?countBoundary()+'：计入数量':(single?'≤0.1':'<0.8')+'：不计入数量'}</div>`)});
}
function initCountReview(){
 document.querySelectorAll('[data-count-group]').forEach(el=>el.onclick=()=>{countState.group=el.dataset.countGroup;countState.page=0;countReview()});
 $('count-all').onclick=()=>{countState.group='all';countState.page=0;countReview()};
 $('count-mode').onchange=()=>{countState.mode=$('count-mode').value;countState.page=0;countReview()};
 $('count-ambiguous').onchange=()=>{countState.includeAmbiguous=$('count-ambiguous').checked;countState.page=0;countReview()};
 let timer;$('count-search').oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>{countState.search=$('count-search').value;countState.page=0;countReview()},150)};
 $('count-reset').onclick=()=>{clearTimeout(timer);$('count-search').value='';countState.search='';countState.page=0;countReview()};
 $('count-previous').onclick=()=>{countState.page--;countReview()};$('count-next').onclick=()=>{countState.page++;countReview()};countReview();
}
const frontState={scope:'all',status:'不符合',search:'',page:0,conflicts:false};
function frontStatus(r){if(frontState.scope==='all')return r.status;if(!r.any_front)return r.status;return r.missing_count&&r.any_front.choice==='no'?'无法验证（缺少封面）':r.any_front.label}
function frontGroup(status){return status.startsWith('无法')?'无法判断':status}
function frontReview(){
 const audit=D.cover_audit;if(!audit)return;
 const groupCounts={};for(const r of audit.rows){const key=frontGroup(frontStatus(r));groupCounts[key]=(groupCounts[key]||0)+1}
 $('front-summary').innerHTML=['符合','不符合','无法判断','调用失败','待处理'].map(key=>`<button data-front-status="${key}" class="${frontState.status===key?'active':''}">${key}<b class="${key==='不符合'?'wrong':key==='符合'?'agree':''}">${groupCounts[key]||0}</b></button>`).join('');
 $('front-summary').querySelectorAll('button').forEach(el=>el.onclick=()=>{frontState.status=el.dataset.frontStatus;$('front-status').value=frontState.status;frontState.page=0;frontReview()});
 const query=frontState.search.trim().toLowerCase(),rows=audit.rows.filter(r=>(!frontState.status||frontGroup(frontStatus(r))===frontState.status)&&(!frontState.conflicts||r.conflict)&&(!query||`${r.name} ${r.videos.map(v=>v.title).join(' ')}`.toLowerCase().includes(query)));
 const pages=Math.max(1,Math.ceil(rows.length/pageSize));frontState.page=Math.min(frontState.page,pages-1);
 $('front-count').textContent=`当前 ${rows.length} 个频道 · ${frontState.scope==='all'?'整组每张都符合':'至少一张符合'}口径 · 全量 ${audit.conflict_count||0} 条整组与逐张答案冲突，需复核。原手语分数未改变。`;
 $('front-table').innerHTML=rows.length?'<table class="case-table front-table"><thead><tr><th>CSV 行</th><th>账户</th><th>整组模型判断</th><th>符合概率</th><th>原候选封面 / 每张模型判断</th><th>详情</th></tr></thead><tbody>'+rows.slice(frontState.page*pageSize,(frontState.page+1)*pageSize).map(r=>{const a=frontState.scope==='all'?r.overall:r.any_front;return `<tr data-front-row="${r.id}"><td>${r.id}</td><td class="name"><b>${esc(r.name)}</b><div class="note">人工 ${esc(r.manual)} · 原预测 ${esc(r.prediction)}</div>${link(r.url,'打开频道 ↗')}</td><td class="${frontStatus(r)==='不符合'?'wrong':''}">${esc(frontStatus(r))}<div class="note">发送 ${r.sent_count??0}/${r.videos.length} 张</div>${r.conflict?`<div class="note wrong">${esc(r.conflict)}</div>`:''}</td><td>${fmt(a?.probabilities?.yes)}</td><td><div class="front-thumbs">${r.videos.map(v=>`<div class="front-thumb" title="${esc(v.title)}">${v.cover?`<img src="${esc(encodeURI(v.cover))}" alt="视频${v.rank}原封面" loading="lazy">`:'缺少本地封面'}<div>视频${v.rank} · 原分数 ${fmt(v.p)}</div><div class="${v.front?.choice==='no'?'bad':v.front?.choice==='yes'?'good':''}">${esc(v.front?.label||(!v.cover?'缺少封面':'待判断'))}</div><div class="note">符合概率 ${fmt(v.front?.probabilities?.yes)}</div></div>`).join('')}</div></td><td><button data-front-case="${r.id}">标题与封面</button></td></tr>`}).join('')+'</tbody></table>':'<div class="empty">当前条件没有频道。</div>';
 $('front-table').querySelectorAll('[data-front-case]').forEach(el=>el.onclick=()=>openCase(Number(el.dataset.frontCase)));
 $('front-table').querySelectorAll('img').forEach(img=>img.onerror=()=>{img.replaceWith('本地封面无法打开')});
 $('front-page-note').textContent=`${rows.length?frontState.page*pageSize+1:0}–${Math.min(rows.length,(frontState.page+1)*pageSize)} / ${rows.length} 个 · 第${frontState.page+1}/${pages}页`;
 $('front-previous').disabled=frontState.page===0;$('front-next').disabled=frontState.page>=pages-1;
}
function showFrontDetail(r){
 const audit=D.cover_audit?.rows.find(x=>x.id===r.id&&x.url===r.url);if(!audit)return;
 $('detail-content').querySelector('.bio').insertAdjacentHTML('beforebegin',`<div class="front-detail"><b>独立封面猜想验证 · 模型整组答案</b><div>全部候选符合标准：<b>${esc(audit.status)}</b> · 符合概率 ${fmt(audit.overall?.probabilities?.yes)}</div><div>至少一张符合标准：${esc(audit.any_front?.label||'未获得答案')} · 发送 ${audit.sent_count??0}/${audit.videos.length} 张</div>${audit.response?`<a href="${esc(encodeURI(audit.response))}" target="_blank">查看独立模型原始响应</a>`:''}${audit.error?`<p class="wrong">${esc(audit.error)}</p>`:''}${audit.conflict?`<p class="wrong">模型答案冲突：${esc(audit.conflict)}。保留原模型判断，请人工复核。</p>`:''}</div>`);
 $('detail-content').querySelectorAll('.video').forEach((el,i)=>{const v=audit.videos.find(v=>v.rank===r.videos[i].rank),front=v?.front;el.querySelector('.body').insertAdjacentHTML('afterbegin',`<p class="${front?.choice==='no'?'wrong':'note'}">封面标准：${esc(front?.label||(!v?.cover?'缺少封面':'待判断'))} · ${fmt(front?.probabilities?.yes)}</p>`)});
}
function initCoverAudit(){
 const audit=D.cover_audit;if(!audit)return;$('front-audit').hidden=false;$('front-nav').hidden=false;
 $('front-meta').textContent=`人工标注为手语的频道 · 本次 ${audit.rows.length}/${audit.manual_positive_total??audit.rows.length} 个 · 模型 ${audit.model} · 判据 ${audit.prompt_version} · ${audit.generated}`;
 $('front-csv').href=encodeURI(audit.csv);
 $('front-scope').onchange=()=>{frontState.scope=$('front-scope').value;frontState.page=0;frontReview()};$('front-status').onchange=()=>{frontState.status=$('front-status').value;frontState.page=0;frontReview()};
 $('front-conflicts').onchange=()=>{frontState.conflicts=$('front-conflicts').checked;frontState.page=0;frontReview()};
 let timer;$('front-search').oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>{frontState.search=$('front-search').value;frontState.page=0;frontReview()},150)};$('front-reset').onclick=()=>{clearTimeout(timer);$('front-search').value='';frontState.search='';frontState.page=0;frontReview()};
 $('front-previous').onclick=()=>{frontState.page--;frontReview()};$('front-next').onclick=()=>{frontState.page++;frontReview()};frontReview();
}

function showTaskDetail(r){showCountDetail(r);showFrontDetail(r)}
function initTaskReport(){evidence();initCountReview();initCoverAudit()}
