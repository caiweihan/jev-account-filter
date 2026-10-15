// Reference labels are derived for presentation; D.rows retains original results.
function analysisRows(){
 const basis=$('comparison-basis').value;
 return D.rows.flatMap(row=>{
  if(basis==='reviewed'&&!hasSecond(row))return [];
  const reference=basis==='original'?row.manual:revisedLabel(row),comparable=L.includes(reference)&&L.includes(row.prediction)&&L.includes(row.manual);
  return [{...row,original_manual:row.manual,original_disputed:row.comparable&&row.wrong,manual:reference,humanEvaluable:basis!=='original',comparable,wrong:comparable&&row.prediction!==reference,human_wrong:comparable&&row.manual!==reference}];
 });
}
function datasetOverview(){
 const rows=D.rows,keys=rows.map(r=>profileKey(r.url)),unique=new Set(keys.filter(Boolean)).size,duplicates=keys.filter(Boolean).length-unique,missingURL=keys.filter(k=>!k).length;
 const items=[['账户记录数',rows.length,'全量 CSV 数据行'],['唯一账户网址',unique,`重复网址 ${duplicates} · 无效网址 ${missingURL}`],['原人工明确二类',rows.filter(r=>binaryLabel(r.manual)).length,`未标注 ${rows.filter(r=>!r.manual).length} · 疑难 ${rows.filter(r=>r.manual===L[1]).length}`],['无效或未完成预测',rows.filter(r=>!L.includes(r.prediction)).length,'失败及空值单独统计']];
 $('dataset-kpis').innerHTML=items.map(([title,value,note])=>`<div class="mini-kpi"><span class="note">${esc(title)}</span><b>${nfmt(value)}</b><span class="note">${esc(note)}</span></div>`).join('');
 const choose=(field,label)=>{Object.assign(state,{manual:'',prediction:'',agreement:'',scenario:'',bin:null,page:0,cluster:'',errorSource:''});state[field]=label;sync();render();$('review').scrollIntoView({behavior:'smooth'})};
 composition('manual-composition',labelCounts(rows,r=>r.manual,'未标注'),rows.length,label=>{if($('comparison-basis').value!=='original'){$('comparison-basis').value='original';refreshReferenceControls()}choose('manual',label)});
 composition('prediction-composition',labelCounts(rows,r=>r.prediction,'无预测'),rows.length,label=>choose('prediction',label));
 $('dataset-note').textContent=`类别分布以全量记录为分母；点击类别可筛选账户明细。${duplicates?'重复网址不自动合并，核验匹配需唯一。':''}`;
}
function evaluationCounts(rows){const eligible=rows.filter(r=>r.comparable);return{n:eligible.length,human:eligible.filter(r=>!r.human_wrong).length,model:eligible.filter(r=>!r.wrong).length,canEvaluateHuman:$('comparison-basis').value!=='original'}}
function performanceKpis(rows){
 const result=evaluationCounts(rows),independent=result.canEvaluateHuman,basis=$('comparison-basis').value,ratio=n=>verifyPct(result.n?n/result.n:null),delta=result.n?(result.model-result.human)/result.n*100:null;
 const cards=[['有效评估账户',nfmt(result.n),`当前范围 ${rows.length} · 不可对照 ${rows.length-result.n}`],['人工标注准确率'+(basis==='combined'?'（条件估计）':''),independent?ratio(result.human):'—',independent?`${result.human}/${result.n} · 对照当前参考标签`:'无独立参考，不能用标注自身评估准确率'],[basis==='original'?'模型与原标注一致率':'模型预测准确率'+(basis==='combined'?'（条件估计）':''),ratio(result.model),`${result.model}/${result.n} · 同一评估样本`],['模型与人工准确率差',independent&&delta!=null?(delta>=0?'+':'')+delta.toFixed(2)+' pp':'—',independent?'百分点差；正值表示模型更高':'仅在有二次参考标签时计算']];
 $('eval-summary').innerHTML=cards.map(([title,value,note])=>`<div class="kpi"><div class="title">${esc(title)}</div><div class="value">${esc(value)}</div><div class="note">${esc(note)}</div></div>`).join('');
 const reviewed=D.rows.filter(hasSecond).length,basisText=basis==='reviewed'?'仅已有效复核样本':basis==='combined'?'全量：有效二次标签覆盖原标注':'全量原人工标注';
 $('evaluation-source').textContent=`${basisText} · 原标注、二次标注和模型预测均保留；当前筛选作用于性能与错误分析。`;
 $('evaluation-note').textContent=basis==='reviewed'?'以二次人工核验作为参考，原标注与二次标注一致的比例为人工标注准确率，模型预测与二次标注一致的比例为模型准确率。若只复核原来的分歧项，这两项准确率只代表已复核子集，不能外推到全量账户。':basis==='combined'?'全量条件估计：已复核账户使用二次标注，其余沿用原标注，因此假设所有未复核的原标注正确。此处的人工与模型准确率是这一假设下的估计，不是独立复核过的全量准确率。':'当前以原人工标注作参考，只能评估模型与标注的一致性。载入二次核验后，可在同一套图表与明细中比较人工和模型的准确率及错误类型。';
 const originalWrong=D.rows.filter(r=>r.wrong).length,covered=D.rows.filter(r=>r.wrong&&hasSecond(r)).length;
 $('evaluation-coverage').textContent=`全量 ${D.rows.length} 个账户 · 有效复核 ${reviewed} 个 · 原分歧项复核 ${covered}/${originalWrong}。计算分母要求参考标签、原标注、预测均属于当前类别标签；缺失、冲突和未知标签不作为正确性证据。`;
}
function evaluationTable(rows){
 rows=rows.filter(matchesReview);const pages=Math.max(1,Math.ceil(rows.length/pageSize));state.page=Math.min(state.page,pages-1);
 $('case-table').innerHTML=rows.length?'<table class="case-table"><thead><tr><th>CSV 行</th><th>账户</th><th>原人工标注</th><th>二次核验</th><th>当前参考</th><th>模型预测</th><th>人工判定</th><th>模型判定</th><th>频道概率</th><th>视频分数</th><th>聚类</th><th>证据</th></tr></thead><tbody>'+rows.slice(state.page*pageSize,(state.page+1)*pageSize).map(row=>`<tr><td>${row.id}</td><td class="name">${esc(row.name)}<div class="note">${esc(row.account_id||row.second_review?.account_id||'')}</div>${link(row.url,'账户主页 ↗')}</td><td>${esc(row.original_manual||'未标注')}</td><td>${esc(hasSecond(row)?row.second_review.label:row.second_review?.status==='conflict'?'标签冲突':row.second_review?.status==='unknown'?'未知标签':'未复核')}</td><td>${esc(row.manual||'未标注')}</td><td>${esc(row.prediction)}</td><td>${row.humanEvaluable&&row.comparable?`<span class="badge ${row.human_wrong?'red':'green'}">${row.human_wrong?'错误':'正确'}</span>`:'—'}</td><td>${row.comparable?`<span class="badge ${row.wrong?'red':'green'}">${row.wrong?'错误':'正确'}</span>`:'不可对照'}</td><td>${fmt(row.p)}</td><td><div class="score-strip">${[1,2,3,4,5].map(rank=>{const score=row.videos.find(v=>v.rank===rank)?.p;return `<span title="视频${rank}" style="background:rgba(52,91,211,${score==null?.03:.05+.25*score})">${score==null?'—':score.toFixed(2)}</span>`}).join('')}</div></td><td>${clusterResult?.byId.has(row.id)?'聚类 '+(clusterResult.byId.get(row.id)+1):'未参与'}</td><td><button data-case="${row.id}">详情</button></td></tr>`).join('')+'</tbody></table>':'<div class="empty">当前筛选无匹配账户。</div>';
 $('case-table').querySelectorAll('[data-case]').forEach(button=>button.onclick=()=>openCase(Number(button.dataset.case)));
 $('page-note').textContent=`${rows.length?state.page*pageSize+1:0}–${Math.min(rows.length,(state.page+1)*pageSize)} / ${rows.length} 条 · 第 ${state.page+1}/${pages} 页`;
 $('previous').disabled=state.page===0;$('next').disabled=state.page>=pages-1;
 $('case-note').textContent=`筛选后 ${rows.length} 个账户，按原 CSV 顺序展示。${state.cluster!==''?'当前限定聚类 '+(state.cluster+1)+'。':''} 原标注和二次标注并列保留，详情提供标题、封面及原始证据。`;
}
function renderErrorAnalysis(){
 const rows=current.filter(r=>r.comparable),mode=$('error-group').value,groups=new Map();
 for(const row of rows){const key=mode==='cluster'?(clusterResult?.byId.has(row.id)?'聚类 '+(clusterResult.byId.get(row.id)+1):'未参与聚类'):mode==='score'?(row.max==null?'分数缺失':row.max<.2?'[0, 0.2)':row.max<.5?'[0.2, 0.5)':row.max<.8?'[0.5, 0.8)':'[0.8, 1]'):row.manual;const values=groups.get(key)||[];values.push(row);groups.set(key,values)}
 $('error-profile').innerHTML='<table class="stat-table"><thead><tr><th>分组</th><th>有效样本</th><th>人工错误 / 错误率</th><th>模型错误 / 错误率</th><th>组内错误率对照</th></tr></thead><tbody>'+[...groups].map(([key,items])=>{const independent=items.filter(r=>r.humanEvaluable),human=independent.filter(r=>r.human_wrong).length,model=items.filter(r=>r.wrong).length;return `<tr><td>${esc(key)}</td><td>${items.length}</td><td>${independent.length?human+' / '+verifyPct(human/independent.length):'—'}</td><td>${model} / ${verifyPct(model/items.length)}</td><td><div class="error-bars">${independent.length?`<div class="error-track"><span style="background:#d89b3d;width:${100*human/independent.length}%"></span>人工</div>`:''}<div class="error-track"><span style="background:#d25353;width:${100*model/items.length}%"></span>模型</div></div></td></tr>`}).join('')+'</tbody></table>';
 $('error-profile-note').textContent=`当前按${mode==='reference'?'参考类别':mode==='cluster'?'预测与五条视频分数的聚类':'最高视频分数区间'}比较组内错误率。两者都可能出错，因此两类错误样本可以重叠。小样本分组只用于定位复核对象，不解释为稳定的群体差异。`;
}
function refreshReferenceControls(){
 const original=$('comparison-basis').value==='original';$('distribution-group').querySelector('[value="sources"]').disabled=original;if(original)$('distribution-group').value='correctness';
 for(const id of ['manual','prediction']){const key=id==='manual'?'manual':'prediction',previous=$(id).value,values=[...new Set(analysisRows().map(r=>r[key]))].filter(Boolean);$(id).replaceChildren(new Option('全部类别',''),...values.map(value=>new Option(value,value)));if(values.includes(previous))$(id).value=previous;else state[key]=''}
}
function reviewDiagnostics(){
 if(!D.second_review)return;$('review-diagnostics').hidden=false;const review=D.second_review;
 $('second-source').textContent=`${review.source} · ${review.total} 条输入 · 唯一有效匹配 ${review.matched} · 一致重复 ${review.duplicates} · 冲突 ${review.conflicts} 组 · 未知标签 ${review.unknown} 组。`;
 $('second-issues').innerHTML=review.issues.length?'<table class="stat-table"><thead><tr><th>核验行</th><th>账户id / 网址</th><th>标签</th><th>未纳入原因</th></tr></thead><tbody>'+review.issues.map(row=>`<tr><td>${row.line}</td><td>${esc(row.account_id||row.url)}</td><td>${esc(row.label)}</td><td>${esc(row.reason)}</td></tr>`).join('')+'</tbody></table>':'<p class="note">所有有效核验均已唯一匹配，未发现输入冲突。</p>';
}
const renderBase=render;
render=function(){renderBase();renderClusters();renderErrorAnalysis()};
const openCaseBase=openCase;
openCase=function(id){openCaseBase(id);const row=analysisRows().find(r=>r.id===id);if(!row)return;const banner=document.createElement('div');banner.className='verify-detail';banner.innerHTML=`<b>分类评估依据</b><div>原人工标注：${esc(row.original_manual||'未标注')} · 二次人工核验：${esc(hasSecond(row)?row.second_review.label:'未有效核验')} · 当前参考：${esc(row.manual||'未标注')}</div><div>${row.humanEvaluable&&row.comparable?'人工标注：'+(row.human_wrong?'错误':'正确')+'；':''}模型预测：${row.comparable?(row.wrong?'错误':'正确'):'不可对照'}。${$('comparison-basis').value==='combined'?'未复核项沿用原标注，本模式为条件估计。':''}</div>`;$('detail-content').querySelector('.bio').before(banner)};
function initAnalysis(){
 datasetOverview();reviewDiagnostics();
 if(D.rows.some(hasSecond)){for(const value of ['reviewed','combined'])$('comparison-basis').querySelector(`[value="${value}"]`).disabled=false;$('comparison-basis').value='reviewed';$('distribution-group').value='sources'}
 const change=()=>{Object.assign(state,{manual:'',prediction:'',agreement:'',scenario:'',review:'',bin:null,page:0,errorSource:''});refreshReferenceControls();sync();render()};
 $('comparison-basis').onchange=change;$('distribution-group').onchange=()=>{state.errorSource='';state.agreement='';state.bin=null;render()};$('error-group').onchange=renderErrorAnalysis;
 refreshReferenceControls();initClusters();
}
