"""Build a portable gallery from frozen projections and recorded visual QA."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'DataSet/sonar_fixed_registration_refinement'
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def main():
    rows=[];qa={}
    for model in ['100lbs','incindiary','mortar_shell']:
        folder=OUT/model
        for name in ('visual-qa.json','independent-visual-qa.json'):
            p=folder/name
            if p.exists():
                doc=read(p)
                for f in doc.get('frames',doc.get('reviews',[])):qa[f['sample']]=f
        for f in read(folder/'evaluation-results.json')['frames']:
            g=f['geometry'];shape=g['raw_shape_hw'];q=qa.get(f['sample'],{})
            # Keep observer schemas visible; normalize only display field names.
            old=q.get('old_status',q.get('old',{}));new=q.get('new_status',q.get('new',{}))
            if isinstance(old,dict):old=old.get('status',old.get('classification','pending'))
            if isinstance(new,dict):new=new.get('status',new.get('classification','pending'))
            reason=q.get('reason',q.get('notes'))
            if reason is None and isinstance(q.get('old'),dict):
                reason='原图：'+q.get('observation','')+' 旧框：'+q['old'].get('reason','')+' 新框：'+q.get('new',{}).get('reason','')
            rows.append(dict(sample=f['sample'],recording=f['recording'],model=model,role=f['role'],width=shape[1],height=shape[0],
                             raw=f'{model}/evaluation/{f["sample"]}-raw.png',comparison=f'{model}/evaluation/{f["sample"]}-comparison.jpg',
                             old=f['old']['bbox_xyxy'],new=f['new']['bbox_xyxy'],old_status=old or 'pending',new_status=new or 'pending',
                             reason=reason or '等待逐帧复核记录',floor=f['floor_extrapolation']))
    full=read(OUT/'full_projection_diagnostic/results.json')
    byid={x['sample']:x for x in full['frames']}
    for f in rows:f['full']=byid[f['sample']]['full_projection']['bbox_xyxy']
    assert len(rows)==120 and len({x['sample'] for x in rows})==120
    source=json.dumps(rows,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
    template=Path(__file__).with_name('sonar_refinement_gallery_template.html').read_text('utf-8')
    (OUT/'index.html').write_text(template.replace('__FRAME_DATA__',source),encoding='utf-8')
    (OUT/'gallery-data.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'frames':len(rows),'reviewed':sum(f['new_status']!='pending' for f in rows)}))
if __name__=='__main__':main()
