// Dataset composition and independent second-review analysis share the report's data.
const binaryLabel=label=>label===L[0]||label===L[2];
const verifyPct=value=>value==null?'—':(value*100).toFixed(2)+'%';
const hasSecond=row=>row.second_review?.status==='valid'&&L.includes(row.second_review.label);
const revisedLabel=row=>hasSecond(row)?row.second_review.label:row.manual;
function profileKey(url){try{const u=new URL(url);return u.hostname+u.pathname.replace(/\/+$/,'')}catch{return ''}}
function composition(node,values,total,onChoose){
 const palette=['#345bd3','#d8a83e','#178878','#9ca9bb','#b68dd9'],color=(entry,i)=>entry.color||palette[i%palette.length];let offset=0;
 const arcs=values.map((entry,i)=>{const length=total?entry.count/total*100:0,arc=`<circle cx="75" cy="75" r="56" fill="none" stroke="${color(entry,i)}" stroke-width="20" pathLength="100" stroke-dasharray="${length} ${100-length}" stroke-dashoffset="${-offset}" transform="rotate(-90 75 75)"/>`;offset+=length;return arc}).join('');
 $(node).innerHTML=`<svg viewBox="0 0 150 150" role="img" aria-label="类别占比"><circle cx="75" cy="75" r="56" fill="none" stroke="#edf1f6" stroke-width="20"/>${arcs}<text x="75" y="74" text-anchor="middle" font-size="23" font-weight="650" fill="#18253a">${nfmt(total)}</text><text x="75" y="96" text-anchor="middle" font-size="12" fill="#65738a">CSV 数据行</text></svg><div class="composition-legend">${values.map((entry,i)=>`<div class="composition-line"><span><i class="dot" style="background:${color(entry,i)}"></i>${onChoose&&L.includes(entry.label)?`<button data-composition="${i}">${esc(entry.label)}</button>`:esc(entry.label)}</span><span>${nfmt(entry.count)} · ${pct(total?entry.count/total:null)}</span></div>`).join('')}</div>`;
 if(onChoose)$(node).querySelectorAll('[data-composition]').forEach(button=>button.onclick=()=>onChoose(values[Number(button.dataset.composition)].label));
}
function labelCounts(rows,get,empty){const colors=['#345bd3','#d8a83e','#178878'];const values=L.map((label,i)=>({label,count:rows.filter(r=>get(r)===label).length,color:colors[i]}));values.push({label:empty,count:rows.filter(r=>!get(r)).length,color:'#9ca9bb'},{label:'其它标签 / 非类别结果',count:rows.filter(r=>get(r)&&!L.includes(get(r))).length,color:'#b68dd9'});return values.filter(v=>v.count)}
function secondOutcome(row){if(!hasSecond(row)||!L.includes(row.manual)||!L.includes(row.prediction))return 'other';const a=row.prediction===row.second_review.label,b=row.manual===row.second_review.label;return a?(b?'both':'model'):(b?'original':'neither')}
function secondStats(){
 const reviewed=D.rows.filter(hasSecond),paired=reviewed.filter(r=>L.includes(r.manual)&&L.includes(r.prediction)),disputed=D.rows.filter(r=>r.wrong),counts={model:0,original:0,both:0,neither:0};
 paired.forEach(r=>counts[secondOutcome(r)]++);
 const fixed=D.rows.filter(r=>binaryLabel(r.manual)&&binaryLabel(revisedLabel(r))&&L.includes(r.prediction));
 const updated=D.rows.filter(r=>binaryLabel(revisedLabel(r))&&L.includes(r.prediction));
 return{reviewed:reviewed.length,paired:paired.length,counts,model_matches:counts.model+counts.both,original_matches:counts.original+counts.both,disputed:disputed.length,reviewed_disputed:disputed.filter(hasSecond).length,
  fixed_total:fixed.length,fixed_original_matches:fixed.filter(r=>r.prediction===r.manual).length,fixed_updated_matches:fixed.filter(r=>r.prediction===revisedLabel(r)).length,
  updated_total:updated.length,updated_matches:updated.filter(r=>r.prediction===revisedLabel(r)).length};
}
