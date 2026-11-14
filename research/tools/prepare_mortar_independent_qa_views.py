"""Make raw-only viewing sheets for independent QA; no candidate box rendering."""
from pathlib import Path
from collections import defaultdict
import hashlib, json, sys
sys.dont_write_bytecode = True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
from PIL import Image,ImageDraw,ImageFont
OUT=ROOT/'DataSet/sonar_fixed_registration_refinement/mortar_shell'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')


def main():
    target=OUT/'independent-qa-views'
    assert not (target/'inputs-before.json').exists(),'Preserve QA input capture'
    target.mkdir(exist_ok=True)
    evaluation=OUT/'evaluation-results.json';report=json.loads(evaluation.read_text(encoding='utf-8'))
    manifest=ROOT/'DataSet/camera_temporal_all/manifest-resolved.json'
    allowed={r['sample']:r for r in json.loads(manifest.read_text(encoding='utf-8'))['items']}
    assert report['model_name']=='mortar_shell' and len(report['frames'])==48
    assert sha(report['freeze_path'])==report['freeze_sha256']
    grouped=defaultdict(list)
    paths={evaluation,Path(report['freeze_path']),manifest,Path(__file__),ROOT/'experiment/sonar-registration-refinement-visual-qa.md'}
    for r in report['frames']:
        sid=r['sample']; row=allowed[sid]
        assert row['category']=='mortar_shell' and row['recording']==r['recording'] and int(row['aris_frame'])==r['aris_frame']
        assert row.get('paired_role') in (None,'train','val','val_id')
        raw=OUT/'evaluation'/f'{sid}-raw.png'
        paths.add(raw);paths.add(OUT/'evaluation'/f'{sid}-comparison.jpg')
        camera=r['provenance'].get('camera')
        if camera:
            cp=Path(camera['path']);assert cp.resolve()==(manifest.parent/row['reference_sd']).resolve()
            assert sha(cp)==camera['sha256'];paths.add(cp)
        grouped[r['recording']].append(r)
    assert len(grouped)==16 and all(len(rs)==3 for rs in grouped.values())
    for rec in grouped:paths.add(OUT/'evaluation'/f'{rec}-contact.jpg')
    hashes={str(p):sha(p) for p in sorted(paths)}
    save(target/'inputs-before.json',dict(hashes=hashes,frames=48,recordings=16,rule='reviewable/needs_revision/misaligned/uncertain',
        model_parameters_not_inspected=True,scope_verified=True))
    ff=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
    fs=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',13)
    for rec, rows in grouped.items():
        canvas=Image.new('RGB',(1320,1180),'white');d=ImageDraw.Draw(canvas)
        d.text((7,5),f'{rec} | independent raw-first review | fixed gain3 | no candidates',font=ff,fill='black')
        for k,r in enumerate(rows):
            x=k*440;sid=r['sample']
            raw=np.asarray(Image.open(OUT/'evaluation'/f'{sid}-raw.png'))
            h,w=raw.shape;assert (h,w)==(441,128)
            d.text((x+7,35),sid,font=ff,fill='black')
            image=Image.fromarray(np.minimum(raw.astype(np.uint16)*3,255).astype(np.uint8)).convert('RGB').resize((384,882),Image.Resampling.NEAREST)
            canvas.paste(image,(x+43,75))
            for u in range(0,129,16):d.text((x+40+3*u,56),str(u),font=fs,fill='black')
            for v in range(0,441,50):d.text((x+4,69+2*v),str(v),font=fs,fill='black')
            camera=r['provenance'].get('camera')
            if camera:
                im=Image.open(camera['path']).convert('RGB');assert im.size==(640,360)
                im.thumbnail((420,200));canvas.paste(im,(x+(440-im.width)//2,973))
            else:d.text((x+12,990),'SD unavailable; no replacement',font=ff,fill='black')
        canvas.save(target/f'{rec}-raw-first.png')
    assert all(sha(p)==h for p,h in hashes.items()),'QA source changed'
    print(json.dumps(dict(output=str(target),raw_first_sheets=16,frames=48)))


if __name__=='__main__':main()
