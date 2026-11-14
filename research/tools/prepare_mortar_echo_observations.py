"""Render only three preregistered unboxed development sonar frames for observation."""
from pathlib import Path
import json, sys, hashlib
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
from PIL import Image, ImageDraw

IDS = ['2023-09-21_100927_0087','2023-09-21_100927_0451','2023-09-21_100927_0811']
OUT = ROOT/'DataSet/mortar_fixed_registration/observations'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    plan=ROOT/'experiment/mortar-fixed-registration-plan.md'
    assert plan.exists(), 'Preregistration must exist before rendering'
    selection=ROOT/'DataSet/sonar_independent_registration/selection.json'
    byid={r['sample']:r for r in json.loads(selection.read_text(encoding='utf-8'))['samples']}
    OUT.mkdir(parents=True,exist_ok=True)
    output=OUT/'display-provenance.json'
    if output.exists():raise RuntimeError('Do not overwrite completed observation preparation')
    records=[]
    inputs={str(plan):sha(plan),str(selection):sha(selection),str(Path(__file__)):sha(Path(__file__))}
    for sid in IDS:
        row=byid[sid]
        assert row['recording']=='2023-09-21_100927'
        assert row['historical_role'] in ['train','val','val_id']
        src=Path(row['raw_sonar_source'])
        polar=ROOT/'DataSet/sonar_registration_methods/coordinates'/f'{sid}-official-polar2.png'
        inputs[str(src)]=sha(src);inputs[str(polar)]=sha(polar)
        arr=np.asarray(Image.open(src));assert arr.ndim==2 and arr.dtype==np.uint8
        h,w=arr.shape
        sx,sy=4,2
        marginx,marginy=45,55
        pw=w*sx+marginx+15
        canvas=Image.new('RGB',(pw*2,h*sy+90),'white');d=ImageDraw.Draw(canvas)
        for col,gain in enumerate([1,3]):
            x0=col*pw+marginx;y0=marginy
            image=Image.fromarray(np.minimum(arr.astype(np.uint16)*gain,255).astype(np.uint8)).convert('RGB').resize((w*sx,h*sy),Image.Resampling.NEAREST)
            canvas.paste(image,(x0,y0));d.text((col*pw+5,5),f'{sid} | fixed gain={gain} | raw {w}x{h}',fill='black')
            d.text((col*pw+5,23),'Grid uses pixel-edge coordinates, no crop / box / model',fill='black')
            for x in range(0,w+1,8):
                xp=x0+x*sx;d.line((xp,y0,xp,y0+h*sy),fill=(70,85,90),width=1);d.text((xp-6,y0-17),str(x),fill='black')
            for y in range(0,h+1,20):
                yp=y0+y*sy;d.line((x0,yp,x0+w*sx,yp),fill=(70,85,90),width=1);d.text((x0-32,yp-5),str(y),fill='black')
        canvas.save(OUT/f'{sid}-raw-review.png')
        # Copy image pixels for a dedicated observation artifact; original polar retained.
        Image.open(polar).save(OUT/f'{sid}-official-polar2.png')
        records.append(dict(sample=sid,raw_source=str(src),polar_source=str(polar),shape_hw=[h,w],gain=[1,3],display_scale_xy=[sx,sy],
                            observation_coordinate_convention='raw pixel edge; pixel (column,row) center = (column+0.5,row+0.5)',
                            raw_source_sha256=inputs[str(src)],polar_source_sha256=inputs[str(polar)]))
    assert inputs=={p:sha(Path(p)) for p in inputs},'Input changed'
    output.write_text(json.dumps(dict(records=records,inputs_sha256=inputs,unchanged=True,model_or_box_inputs_read=False),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(records,indent=2))

if __name__=='__main__':main()
