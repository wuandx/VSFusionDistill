"""Display-only gain=1 contact sheets from already evaluated native raw copies."""
from pathlib import Path
import json,sys
sys.dont_write_bytecode=True
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]/'DataSet/sonar_fixed_registration_refinement'
for model in ('incindiary','mortar_shell','100lbs'):
    base=ROOT/model;path=base/'evaluation-results.json'
    if not path.exists():continue
    data=json.loads(path.read_text('utf-8'));dest=base/'review-gain1';dest.mkdir(exist_ok=True)
    for rec in sorted({x['recording'] for x in data['frames']}):
        tiles=[]
        for f in data['frames']:
            if f['recording']!=rec:continue
            raw=Image.open(base/'evaluation'/(f['sample']+'-raw.png')).convert('RGB');w,h=raw.size
            row=Image.new('RGB',(1200,h+36),'white')
            for j,key in enumerate((None,'old','new')):
                im=raw.resize((384,h),Image.Resampling.NEAREST);dr=ImageDraw.Draw(im)
                if key:
                    result=f[key];c=(255,155,0) if key=='old' else (0,240,130)
                    b=result['bbox_xyxy']
                    if b:dr.rectangle([b[0]*384/w,b[1],b[2]*384/w,b[3]],outline=c,width=2)
                row.paste(im,(400*j+8,30));ImageDraw.Draw(row).text((400*j+8,8),f['sample']+' / '+(key or 'raw')+' gain=1',fill='black')
            tiles.append(row)
        out=Image.new('RGB',(1200,sum(x.height for x in tiles)),'white');y=0
        for tile in tiles:out.paste(tile,(0,y));y+=tile.height
        out.save(dest/(rec+'.jpg'),quality=96)
    print(model,len(data['frames']),flush=True)
