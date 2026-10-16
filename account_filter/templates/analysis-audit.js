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
 $('front-count').textContent=`当前 ${rows.length} 个频道 · ${frontState.scope==='all'?'整组每张都符合':'至少一张符合'}口径 · 全量 ${audit.conflict_count||0} 条整组与逐张答案冲突，需复核。原分类分数未改变。`;
 $('front-table').innerHTML=rows.length?'<table class="case-table front-table"><thead><tr><th>CSV 行</th><th>账户</th><th>整组模型判断</th><th>符合概率</th><th>原候选封面 / 每张模型判断</th><th>详情</th></tr></thead><tbody>'+rows.slice(frontState.page*pageSize,(frontState.page+1)*pageSize).map(r=>{const a=frontState.scope==='all'?r.overall:r.any_front;return `<tr data-front-row="${r.id}"><td>${r.id}</td><td class="name"><b>${esc(r.name)}</b><div class="note">人工 ${esc(r.manual)} · 原预测 ${esc(r.prediction)}</div>${link(r.url,'打开频道 ↗')}</td><td class="${frontStatus(r)==='不符合'?'wrong':''}">${esc(frontStatus(r))}<div class="note">发送 ${r.sent_count??0}/${r.videos.length} 张</div>${r.conflict?`<div class="note wrong">${esc(r.conflict)}</div>`:''}</td><td>${fmt(a?.probabilities?.yes)}</td><td><div class="front-thumbs">${r.videos.map(v=>`<div class="front-thumb" title="${esc(v.title)}">${v.cover?`<img src="${esc(encodeURI(v.cover))}" alt="视频${v.rank}原封面" loading="lazy">`:'缺少本地封面'}<div>视频${v.rank} · 原分数 ${fmt(v.p)}</div><div class="${v.front?.choice==='no'?'bad':v.front?.choice==='yes'?'good':''}">${esc(v.front?.label||(!v.cover?'缺少封面':'待判断'))}</div><div class="note">符合概率 ${fmt(v.front?.probabilities?.yes)}</div></div>`).join('')}</div></td><td><button data-front-case="${r.id}">标题与封面</button></td></tr>`}).join('')+'</tbody></table>':'<div class="empty">当前条件没有频道。</div>';
 $('front-table').querySelectorAll('[data-front-case]').forEach(el=>el.onclick=()=>openCase(Number(el.dataset.frontCase)));
 $('front-table').querySelectorAll('img').forEach(img=>img.onerror=()=>{img.replaceWith('本地封面无法打开')});
 $('front-page-note').textContent=`${rows.length?frontState.page*pageSize+1:0}–${Math.min(rows.length,(frontState.page+1)*pageSize)} / ${rows.length} 个 · 第${frontState.page+1}/${pages}页`;
 $('front-previous').disabled=frontState.page===0;$('front-next').disabled=frontState.page>=pages-1;
}
function showFrontDetail(r){
 const audit=D.cover_audit?.rows.find(x=>x.id===r.id&&x.url===r.url);if(!audit)return;
 $('detail-content').querySelector('.bio').insertAdjacentHTML('beforebegin',`<div class="front-detail"><b>独立封面特征核验 · 模型整组答案</b><div>全部候选符合标准：<b>${esc(audit.status)}</b> · 符合概率 ${fmt(audit.overall?.probabilities?.yes)}</div><div>至少一张符合标准：${esc(audit.any_front?.label||'未获得答案')} · 发送 ${audit.sent_count??0}/${audit.videos.length} 张</div>${audit.response?`<a href="${esc(encodeURI(audit.response))}" target="_blank">查看独立模型原始响应</a>`:''}${audit.error?`<p class="wrong">${esc(audit.error)}</p>`:''}${audit.conflict?`<p class="wrong">模型答案冲突：${esc(audit.conflict)}。保留原模型判断，请人工复核。</p>`:''}</div>`);
 $('detail-content').querySelectorAll('.video').forEach((el,i)=>{const v=audit.videos.find(v=>v.rank===r.videos[i].rank),front=v?.front;el.querySelector('.body').insertAdjacentHTML('afterbegin',`<p class="${front?.choice==='no'?'wrong':'note'}">封面标准：${esc(front?.label||(!v?.cover?'缺少封面':'待判断'))} · ${fmt(front?.probabilities?.yes)}</p>`)});
}
function initCoverAudit(){
 const audit=D.cover_audit;if(!audit)return;$('front-audit').hidden=false;$('front-nav').hidden=false;
 $('front-title').textContent=audit.title||'候选封面特征核验';$('front-criteria').textContent=audit.criteria||'此核验文件未提供判据说明。';
 $('front-meta').textContent=`${audit.population||'核验账户'} · 本次 ${audit.rows.length}/${audit.manual_positive_total??audit.rows.length} 个 · 模型 ${audit.model} · 判据 ${audit.prompt_version} · ${audit.generated}`;
 $('front-csv').hidden=!audit.csv;if(audit.csv)$('front-csv').href=encodeURI(audit.csv);
 $('front-scope').onchange=()=>{frontState.scope=$('front-scope').value;frontState.page=0;frontReview()};$('front-status').onchange=()=>{frontState.status=$('front-status').value;frontState.page=0;frontReview()};
 $('front-conflicts').onchange=()=>{frontState.conflicts=$('front-conflicts').checked;frontState.page=0;frontReview()};
 let timer;$('front-search').oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>{frontState.search=$('front-search').value;frontState.page=0;frontReview()},150)};$('front-reset').onclick=()=>{clearTimeout(timer);$('front-search').value='';frontState.search='';frontState.page=0;frontReview()};
 $('front-previous').onclick=()=>{frontState.page--;frontReview()};$('front-next').onclick=()=>{frontState.page++;frontReview()};frontReview();
}

function showAuditDetail(r){showFrontDetail(r)}
