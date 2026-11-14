"""Display-only gain1/gain3 views for frozen bomb QA; no fitting or reviews."""
from pathlib import Path
import sys,json,hashlib
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
from PIL import Image,ImageDraw

BASE=ROOT/'DataSet/sonar_fixed_registration_refinement/100lbs'
OUT=BASE/'independent-qa-displays'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def panel(a,title,b=None,color='white'):
    h,w=a.shape
    im=Image.new('RGB',(280,h+65),'white');im.paste(Image.fromarray(a).convert('RGB').resize((256,h),Image.Resampling.NEAREST),(16,40));d=ImageDraw.Draw(im);d.text((6,5),title,fill='black')
    if b:
        d.rectangle((16+b[0]*256/w,40+b[1],16+b[2]*256/w,40+b[3]),outline=color,width=2)
    return im
def main():
    assert not OUT.exists(),'Keep existing output'
    data=json.loads((BASE/'evaluation-results.json').read_text('utf-8-sig'))
    allowed={r['sample']:r for r in json.loads((ROOT/'DataSet/camera_temporal_all/manifest-resolved.json').read_text('utf-8'))['items']}
    frames=data['frames'];assert len(frames)==36
    OUT.mkdir();inputs={};summaries=[]
    for p in [BASE/'evaluation-results.json',BASE/'freeze-model.json',ROOT/'experiment/sonar-registration-refinement-visual-qa.md']:
        inputs[str(p)]=sha(p)
    for rec in sorted({f['recording'] for f in frames}):
        fs=[f for f in frames if f['recording']==rec];assert len(fs)==3
        rawtiles=[];boxtiles=[]
        for f in fs:
            sid=f['sample'];assert sid in allowed and allowed[sid].get('paired_role') in [None,'train','val','val_id']
            p=Path(f['provenance']['raw']['path']);assert sha(p)==f['provenance']['raw']['sha256'];inputs[str(p)]=sha(p)
            a=np.array(Image.open(p));assert list(a.shape)==f['geometry']['raw_shape_hw']
            g=np.clip(a.astype('uint16')*3,0,255).astype('uint8')
            p1=panel(a,sid+' gain1');p3=panel(g,sid+' gain3')
            tile=Image.new('RGB',(560,p1.height+195),'white');tile.paste(p1,(0,195));tile.paste(p3,(280,195));d=ImageDraw.Draw(tile);d.text((8,4),sid+' unboxed; full native rows',fill='black')
            cam=f['provenance']['camera']
            if cam:
                cp=Path(cam['path']);assert sha(cp)==cam['sha256'];inputs[str(cp)]=sha(cp)
                im=Image.open(cp).convert('RGB');im.thumbnail((320,180));tile.paste(im,(8,20))
            else:d.text((8,40),'SD unavailable',fill='black')
            rawtiles.append(tile)
            bt=Image.new('RGB',(560,p1.height),'white')
            for k,v,c in [(0,'old',(255,160,0)),(1,'new',(0,235,130))]:
                bt.paste(panel(a,sid+' '+v+' gain1',f[v]['bbox_xyxy'],c),(k*280,0))
            boxtiles.append(bt)
            summaries.append({'sample':sid,'raw_shape_hw':list(a.shape),'full_height_preserved':True,'camera_present':bool(cam),'floor_extrapolation':f['floor_extrapolation']})
        for kind,tiles in [('unboxed',rawtiles),('boxes-gain1',boxtiles)]:
            sheet=Image.new('RGB',(1680,max(p.height for p in tiles)),'white')
            for k,p in enumerate(tiles):sheet.paste(p,(k*560,0))
            sheet.save(OUT/(rec+'-'+kind+'.png'))
    assert all(sha(p)==h for p,h in inputs.items())
    save(OUT/'display-provenance.json',{'inputs_sha256':inputs,'inputs_unchanged':True,'frames':summaries,'display_only':True,'new_gt':0,'user_reviews_written':0,'coordinate_note':'Native raw xyxy edge coordinates; x displayed at 2x; y at 1x. No crop or pixel intensity changes in gain1.'})
    print(json.dumps({'frames':len(summaries),'recordings':12,'input_hashes':len(inputs),'full_height_preserved':True}))
if __name__=='__main__':main()
