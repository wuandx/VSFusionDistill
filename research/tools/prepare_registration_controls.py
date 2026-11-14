"""Fixed independent registration development controls; no old boxes copied."""
from pathlib import Path
import json,hashlib,shutil
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'DataSet/sonar_independent_registration'
OUT.mkdir(exist_ok=True);(OUT/'camera').mkdir(exist_ok=True)
manifest=json.loads((ROOT/'DataSet/camera_temporal_all/manifest-resolved.json').read_text(encoding='utf-8'))
rows=[]
for cat in sorted({r['category'] for r in manifest['recordings']}):
    recs=sorted(r['recording'] for r in manifest['recordings'] if r['category']==cat)[:2]
    for ri,rec in enumerate(recs):
        candidates=sorted([x for x in manifest['items'] if x['recording']==rec and x.get('paired_id')],key=lambda x:x['aris_frame'])
        for fi,index in enumerate([0,len(candidates)//2,len(candidates)-1]):
            item=candidates[index];assert item['paired_role'] in ['train','val','val_id']
            frame=item['aris_frame'];sd=ROOT/'DataSet/camera_temporal_all'/item['reference_sd'] if item.get('reference_sd') else None
            rd=Path(item['original_label']).parent.parent
            row=dict(sample=item['sample'],category=cat,recording=rec,aris_frame=frame,
                role='registration_fit' if ri==0 and fi<2 else 'registration_holdout',
                historical_role=item['paired_role'],camera_source=str(sd) if sd else None,
                raw_sonar_source=str(rd/'aris_raw'/f'{frame:04d}.pgm'),
                gantry_source=str(rd/'gantry.csv'),meta_source=str(rd/'aris_frame_meta.csv'))
            if sd:
                assert Image.open(sd).size==(640,360)
                dest=OUT/'camera'/f"{item['sample']}.jpg";shutil.copyfile(sd,dest)
                row['camera_copy']=str(dest);row['camera_sha256']=hashlib.sha256(sd.read_bytes()).hexdigest()
            rows.append(row)
for role in ['registration_fit','registration_holdout']:
    rr=[r for r in rows if r['role']==role];canvas=Image.new('RGB',(1280,400*((len(rr)+1)//2)),(235,235,235));d=ImageDraw.Draw(canvas)
    for i,row in enumerate(rr):
        x=(i%2)*640;y=(i//2)*400
        if row.get('camera_copy'):canvas.paste(Image.open(row['camera_copy']),(x,y+35))
        else:d.text((x+20,y+70),'SD MISSING - retained identity',fill='black')
        d.text((x+3,y+3),row['sample']+' | '+role,fill='black')
        for xx in range(0,640,40):
            d.line((x+xx,y+35,x+xx,y+395),fill=(50,90,90),width=1);d.text((x+xx,y+20),str(xx),fill='black')
        for yy in range(0,360,40):
            d.line((x,y+35+yy,x+639,y+35+yy),fill=(50,90,90),width=1);d.text((x,y+35+yy),str(yy),fill=(255,255,0))
    canvas.save(OUT/(role+'-grid.jpg'),quality=96)
(OUT/'selection.json').write_text(json.dumps(dict(rule='preregistered first/second recording per category, first/middle/last paired identities',samples=rows),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps([{k:r[k] for k in ['sample','role','camera_source']} for r in rows],ensure_ascii=False,indent=2))
