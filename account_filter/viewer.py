"""Build a data-free browser viewer, reusing the existing offline report templates."""
import argparse
import json
from pathlib import Path

from .category import CONFIGS, load_category
from .report import assemble_html

ROOT = Path(__file__).resolve().parents[1]


def build(output=None):
    output = Path(output) if output else ROOT / 'analysis.html'
    if output.suffix.lower() != '.html':
        raise ValueError('查看器输出必须是 .html，不能覆盖 CSV 或缓存文件。')
    categories = []
    for path in sorted((CONFIGS / 'categories').glob('*.toml')):
        category = load_category(path)
        categories.append({key: category[key] for key in
                           ('id', 'name', 'positive_label', 'negative_label', 'report_extension')
                           if key in category})
    templates = {}
    extensions = {'', *(c.get('report_extension', '') for c in categories)}
    for extension in sorted(extensions):
        marker = 'VIEWER_PAYLOAD_PLACEHOLDER'
        html = assemble_html({'category': {'report_extension': extension}, 'viewer': marker})
        start = html.index('<script id="report-data" type="application/json">')
        start = html.index('>', start) + 1
        end = html.index('</script>', start)
        html = html[:start] + '__VIEWER_PAYLOAD__' + html[end:]
        html = html.replace('页面生成 ${D.generated}', '载入 ${D.generated}')
        html = html.replace('html{scroll-behavior:smooth}', 'html{scroll-behavior:auto}')
        html = html.replace('HTML 内含结果数据，可直接打开；保留实验目录结构才能显示本地封面。移动文件或修改 CSV 后，需要重新生成页面。',
                            '数据来自本次选择的 CSV；简介、标题和封面来自主动选择的缓存文件夹。修改 CSV 后重新选择即可，未选择的本地文件不会自动读取。')
        # Custom labels come from selected files too; escape them at every HTML insertion.
        html = html.replace("${l.replace('频道','')}", "${esc(l.replace('频道',''))}")
        html = html.replace("${L[i].replace('频道','')}", "${esc(L[i].replace('频道',''))}")
        html = html.replace('${L[i]}', '${esc(L[i])}').replace('${L[j]}', '${esc(L[j])}')
        html = html.replace('data-stratum="${l}"', 'data-stratum="${esc(l)}"')
        html = html.replace('${l}</button>', '${esc(l)}</button>')
        html = html.replace('${D.category.name}', '${esc(D.category.name)}')
        html = html.replace('${t}</div>', '${esc(t)}</div>')
        # Inline evidence keeps the full-page viewer in one scroll context.
        html = html.replace('<dialog id="detail"><div id="detail-content"></div></dialog>', '')
        html = html.replace('<section class="panel method">', '<section class="panel detail-panel" id="detail" hidden><div id="detail-content"></div></section><section class="panel method">')
        # Transfer only selected local assets into the sandbox. Blob URLs belong to
        # the document that creates them, so the report creates its own URLs.
        html = html.replace("init();initAnalysis();if(typeof initTaskReport==='function')initTaskReport();", """
window.addEventListener('message',function loadAssets(event){
 if(event.source!==parent||event.data?.type!=='viewer-files')return;
 window.removeEventListener('message',loadAssets);
 const files=new Map(event.data.assets.map(item=>[item.id,URL.createObjectURL(item.file)]));
 for(const row of D.rows){row.snapshot=files.get(row.snapshot)||null;for(const video of row.videos)video.cover=files.get(video.cover)||null}
 if(D.cover_audit){D.cover_audit.csv=files.get(D.cover_audit.csv)||'';for(const row of D.cover_audit.rows){row.response=files.get(row.response)||null;for(const video of row.videos)video.cover=files.get(video.cover)||null}}
 document.getElementById('report-data').textContent=JSON.stringify(D);
 const detail=document.getElementById('detail');let returnTo=null;
 detail.showModal=function(){returnTo=document.activeElement;this.hidden=false;this.open=true;requestAnimationFrame(()=>this.scrollIntoView({block:'start',behavior:'instant'}))};
 detail.close=function(){this.hidden=true;this.open=false;returnTo?.focus({preventScroll:true})};
 document.addEventListener('keydown',event=>{if(event.key==='Escape'&&detail.open)detail.close()});
 init();initAnalysis();if(typeof initTaskReport==='function')initTaskReport();
 const token=event.data.token;
 let sizing=false;
 function reportSize(){if(sizing)return;sizing=true;requestAnimationFrame(()=>{sizing=false;parent.postMessage({type:'viewer-height',token,height:Math.ceil(document.body.getBoundingClientRect().height)},'*')})}
 new ResizeObserver(reportSize).observe(document.body);reportSize();
 parent.postMessage({type:'viewer-ready',token:event.data.token},'*');
});
""")
        templates[extension] = html
    bundle = json.dumps({'categories': categories, 'templates': templates}, ensure_ascii=False)
    bundle = bundle.replace('<', '\\u003c').replace('&', '\\u0026')
    directory = Path(__file__).parent / 'templates'
    html = (directory / 'viewer.html').read_text(encoding='utf-8')
    html = html.replace('__VIEWER_BUNDLE__', bundle)
    script = '\n'.join((directory / name).read_text(encoding='utf-8')
                       for name in ('viewer.js', 'viewer-session.js'))
    html = html.replace('__VIEWER_SCRIPT__', script)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding='utf-8')
    return output


def main():
    parser = argparse.ArgumentParser(description='构建可直接选择 CSV 和缓存文件夹的离线分析页面，不读取实验数据')
    parser.add_argument('--output', type=Path, help='默认项目根目录 analysis.html')
    args = parser.parse_args()
    print(f'已构建：{build(args.output).resolve()}')


if __name__ == '__main__':
    main()
