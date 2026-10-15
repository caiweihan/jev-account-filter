// Descriptive clustering only: predictions and experiment files are never changed.
let clusterResult=null;
const clusterColors=['#345bd3','#178878','#d89b3d','#9460bf','#d25353','#279bb5','#a87453','#68758b'];
function clusterAccounts(rows,requested){
 const ranks=[1,2,3,4,5],eligible=[];let missing=0,invalid=0;
 for(const row of rows){const scores=ranks.map(rank=>row.videos.find(v=>v.rank===rank)?.p);
  if(!L.includes(row.prediction)){invalid++;continue}
  if(scores.some(p=>p==null||!Number.isFinite(p))){missing++;continue}
  eligible.push({row,scores,vector:[...scores,...L.map(label=>row.prediction===label?Math.SQRT1_2:0)]});
 }
 eligible.sort((a,b)=>{for(let i=0;i<a.vector.length;i++)if(a.vector[i]!==b.vector[i])return a.vector[i]-b.vector[i];return a.row.id-b.row.id});
 const distance=(a,b)=>a.reduce((sum,x,i)=>sum+(x-b[i])**2,0),unique=[...new Map(eligible.map(item=>[JSON.stringify(item.vector),item.vector])).values()];
 const k=Math.min(Math.max(1,Number(requested)||5),unique.length),centers=k?[unique[0].slice()]:[];
 while(centers.length<k){let best=null,far=-1;for(const point of unique){const d=Math.min(...centers.map(c=>distance(point,c)));if(d>far){far=d;best=point}}centers.push(best.slice())}
 let assignments=[];
 for(let iteration=0;iteration<60&&k;iteration++){
  const next=eligible.map(item=>{let best=0;for(let j=1;j<k;j++)if(distance(item.vector,centers[j])<distance(item.vector,centers[best]))best=j;return best});
  const stable=next.length===assignments.length&&next.every((v,i)=>v===assignments[i]);assignments=next;
  for(let j=0;j<k;j++){const members=eligible.filter((_,i)=>assignments[i]===j);if(members.length)centers[j]=centers[j].map((_,d)=>members.reduce((sum,item)=>sum+item.vector[d],0)/members.length)}
  if(stable)break;
 }
 const groups=centers.map((center,j)=>({center,members:eligible.filter((_,i)=>assignments[i]===j)})).filter(g=>g.members.length);
 groups.sort((a,b)=>b.center.slice(0,5).reduce((x,y)=>x+y,0)-a.center.slice(0,5).reduce((x,y)=>x+y,0)||b.center[5]-a.center[5]);
 const byId=new Map();groups.forEach((group,index)=>{group.id=index;group.members.forEach(item=>byId.set(item.row.id,index))});
 const dimensions=eligible[0]?.vector.length||0,mean=Array.from({length:dimensions},(_,d)=>eligible.reduce((sum,item)=>sum+item.vector[d],0)/eligible.length);
 const centered=eligible.map(item=>item.vector.map((x,d)=>x-mean[d]));
 const covariance=mean.map((_,i)=>mean.map((_,j)=>centered.reduce((sum,v)=>sum+v[i]*v[j],0)/Math.max(1,centered.length-1)));
 const vectors=[],eigenvalues=[];
 for(let axis=0;axis<2;axis++){
  let v=mean.map((_,i)=>1/(i+axis+1));
  for(let step=0;step<120;step++){
   let next=covariance.map(row=>row.reduce((sum,x,i)=>sum+x*v[i],0));
   for(const previous of vectors){const dot=next.reduce((sum,x,i)=>sum+x*previous[i],0);next=next.map((x,i)=>x-dot*previous[i])}
   const norm=Math.hypot(...next);if(norm<1e-12){v=mean.map(()=>0);break}next=next.map(x=>x/norm);v=next;
  }
  const sign=v.reduce((best,x,i)=>Math.abs(x)>Math.abs(v[best])?i:best,0);if(v[sign]<0)v=v.map(x=>-x);
  vectors.push(v);eigenvalues.push(v.reduce((sum,x,i)=>sum+x*covariance[i].reduce((s,c,j)=>s+c*v[j],0),0));
 }
 const variance=covariance.reduce((sum,row,i)=>sum+row[i],0),points=eligible.map((item,index)=>({...item,cluster:byId.get(item.row.id),x:centered[index].reduce((sum,x,i)=>sum+x*vectors[0][i],0),y:centered[index].reduce((sum,x,i)=>sum+x*vectors[1][i],0)}));
 return {eligible,groups,byId,points,missing,invalid,variance:variance?eigenvalues.map(value=>Math.max(0,value)/variance):[0,0],sse:eligible.reduce((sum,item)=>sum+distance(item.vector,groups[byId.get(item.row.id)].center),0)};
}
function selectCluster(id){state.cluster=id;state.page=0;sync();render();$('review').scrollIntoView({behavior:'smooth'})}
function renderClusters(){
 if(!clusterResult)return;
 const result=clusterResult,reviewed=new Map(analysisRows().map(row=>[row.id,row])),mode=$('cluster-color').value;
 const w=800,h=365,left=55,right=770,top=25,bottom=325;
 const xs=result.points.map(p=>p.x),ys=result.points.map(p=>p.y),xmin=xs.length?Math.min(...xs):0,xmax=xs.length?Math.max(...xs):0,ymin=ys.length?Math.min(...ys):0,ymax=ys.length?Math.max(...ys):0;
 const x=value=>left+(value-xmin)/(xmax-xmin||1)*(right-left),y=value=>bottom-(value-ymin)/(ymax-ymin||1)*(bottom-top);
 const errorColor=row=>!row||!row.humanEvaluable||!hasSecond(row)?'#aeb8c6':row.human_wrong?(row.wrong?'#9460bf':'#d89b3d'):(row.wrong?'#d25353':'#178878');
 let body=`<line x1="${left}" x2="${right}" y1="${bottom}" y2="${bottom}" class="axis"/><line x1="${left}" x2="${left}" y1="${top}" y2="${bottom}" class="axis"/><text x="${(left+right)/2}" y="358" text-anchor="middle">第一主成分 · ${pct(result.variance[0])}</text><text x="12" y="18">第二主成分 · ${pct(result.variance[1])}</text>`;
 body+=result.points.map(point=>{const row=point.row,color=mode==='errors'?errorColor(reviewed.get(row.id)):clusterColors[point.cluster];return `<circle class="cluster-point" data-point="${row.id}" cx="${x(point.x).toFixed(2)}" cy="${y(point.y).toFixed(2)}" r="3.5" fill="${color}" opacity="${state.cluster!==''&&state.cluster!==point.cluster?.24:.7}"><title>${esc(row.name)} · 聚类 ${point.cluster+1}\n预测：${esc(row.prediction)}\n五条分数：${point.scores.map(p=>p.toFixed(3)).join(' / ')}</title></circle>`}).join('');
 $('cluster-scatter').innerHTML=result.points.length?svg(w,h,body):'<p class="empty">没有同时具备有效预测和五条完整分数的频道，无法聚类。</p>';
 $('cluster-scatter').querySelectorAll('[data-point]').forEach(point=>point.onclick=()=>openCase(Number(point.dataset.point)));
 $('cluster-legend').innerHTML=mode==='errors'?[['仅人工标注错误','#d89b3d'],['仅模型预测错误','#d25353'],['两者均错误','#9460bf'],['两者均正确','#178878'],['未纳入独立核验','#aeb8c6']].map(([label,color])=>`<span><i class="dot" style="background:${color}"></i>${label}</span>`).join(''):result.groups.map(g=>`<button data-cluster="${g.id}" class="${state.cluster===g.id?'active':''}"><i class="dot" style="background:${clusterColors[g.id]}"></i>聚类 ${g.id+1} · ${g.members.length}</button>`).join('');
 $('cluster-legend').querySelectorAll('[data-cluster]').forEach(button=>button.onclick=()=>selectCluster(Number(button.dataset.cluster)));
 $('cluster-profiles').innerHTML='<table class="stat-table"><thead><tr><th>聚类</th><th>频道数</th>'+[1,2,3,4,5].map(i=>`<th>视频${i}均分</th>`).join('')+'<th>目标类预测占比</th><th>评估样本</th><th>人工错误率</th><th>模型错误率</th></tr></thead><tbody>'+result.groups.map(group=>{const scoped=group.members.map(item=>reviewed.get(item.row.id)).filter(Boolean),independent=scoped.filter(r=>r.humanEvaluable);return `<tr><td><button data-cluster="${group.id}">聚类 ${group.id+1}</button></td><td>${group.members.length}</td>${group.center.slice(0,5).map(value=>`<td style="background:rgba(52,91,211,${.04+.25*value})">${value.toFixed(3)}</td>`).join('')}<td>${pct(group.members.filter(item=>item.row.prediction===L[0]).length/group.members.length)}</td><td>${scoped.length}</td><td>${verifyPct(independent.length?independent.filter(r=>r.human_wrong).length/independent.length:null)}</td><td>${verifyPct(scoped.length?scoped.filter(r=>r.wrong).length/scoped.length:null)}</td></tr>`}).join('')+'</tbody></table>';
 $('cluster-profiles').querySelectorAll('[data-cluster]').forEach(button=>button.onclick=()=>selectCluster(Number(button.dataset.cluster)));
 $('cluster-note').textContent=`纳入 ${result.eligible.length}/${D.rows.length} 个频道，实际形成 ${result.groups.length} 组；缺少完整五条分数 ${result.missing} 个，预测无效 ${result.invalid} 个，均未补零。聚类使用五个 0–1 分数及预测类别独热编码（类别变化的平方距离为 1），确定性 K-means；散点仅用 PCA 投影展示，前两维解释 ${pct(result.variance.reduce((a,b)=>a+b,0))} 的特征方差。重叠点可能遮挡，可通过聚类表筛选全部成员。聚类概况使用全量数据；错误率随评估参考切换，不随账户筛选变化。人工错误率在原标注对照模式下不估计。`;
}
function initClusters(){
 const rebuild=()=>{clusterResult=clusterAccounts(D.rows,Number($('cluster-k').value));state.cluster='';render()};
 $('cluster-k').onchange=rebuild;$('cluster-color').onchange=renderClusters;$('clear-cluster').onclick=()=>{state.cluster='';render()};rebuild();
}
