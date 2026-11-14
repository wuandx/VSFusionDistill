"""Image-only proposals for assistant visual curation; never auto-accepts labels."""
import sys, json, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
OUT=ROOT/'DataSet/sonar_visible_annotation'
SELECTED=[0,1,2,3,4,5,7,8,9,10,11,12,15,16,18,19,22,27,28,34]
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def arr(p):return cv2.imdecode(np.frombuffer(Path(p).read_bytes(),np.uint8),cv2.IMREAD_UNCHANGED)
def propose(a,idx,threshold_floor=12,mad_multiple=3):
    h,w=a.shape
    yl,yh=({18:(.43,.78),19:(.43,.78),22:(.43,.78),34:(.43,.8)}.get(idx,(.1,.52) if idx<=10 else (.23,.68)))
    y0,y1=int(h*yl),int(h*yh)
    sm=cv2.GaussianBlur(a.astype(np.float32),(3,7),0)
    roi=sm[y0:y1]; bg=float(np.median(roi)); mad=float(np.median(np.abs(roi-bg)))
    threshold=bg+max(threshold_floor,mad_multiple*mad)
    mask=(roi>threshold).astype(np.uint8)
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((9,3),np.uint8))
    n,lab,stats,cent=cv2.connectedComponentsWithStats(mask)
    if n<=1:return None,dict(bg=bg,mad=mad,threshold=threshold)
    scores=[float(np.maximum(roi[lab==k]-threshold,0).sum()) for k in range(1,n)]
    k=1+int(np.argmax(scores)); x,y,bw,bh,area=stats[k]
    if area<12:return None,dict(bg=bg,mad=mad,threshold=threshold)
    return [max(0,int(x)-2),max(0,int(y+y0)-5),min(w,int(x+bw)+2),min(h,int(y+y0+bh)+5)],dict(bg=bg,mad=mad,threshold=threshold,component_area=int(area))
def tile(row, box=None, size=(320,240), show_context=False):
    a=arr(row['source']); h,w=a.shape; b=row['proposal_xyxy'] if box is None else box
    if show_context: y0,y1=0,h
    else:
        if b: cy=(b[1]+b[3])/2; span=max(110,b[3]-b[1]+50)
        else: cy=h*.35; span=180
        y0=max(0,int(cy-span/2));y1=min(h,int(cy+span/2))
    tw,th=size; im=Image.fromarray(np.clip(a[y0:y1].astype(np.float32)*2.5,0,255).astype(np.uint8)).convert('RGB').resize((tw,th-35))
    canvas=Image.new('RGB',size,'white');canvas.paste(im,(0,35));d=ImageDraw.Draw(canvas)
    d.text((3,2),f"{row.get('ordinal','')} f={row['frame']} y={y0}:{y1}",fill='black')
    d.text((3,18),str(b),fill='black')
    if b:
        sx=tw/w;sy=(th-35)/(y1-y0)
        d.rectangle((b[0]*sx,35+(b[1]-y0)*sy,min(tw-1,b[2]*sx),35+(b[3]-y0)*sy),outline='#00ff60',width=2)
    return canvas
def main():
    overview=read(OUT/'overview/index.json'); manifest=read(ROOT/'DataSet/camera_temporal_all/manifest-resolved.json')
    assert len(overview)==40
    byrec={r['recording']:[] for r in overview}
    for r in manifest['items']:
        assert r['recording'] in byrec and r.get('paired_role') in (None,'train','val','val_id')
        byrec[r['recording']].append(r)
    proposals=[]
    out=OUT/'candidates';out.mkdir(exist_ok=True)
    for rec in overview:
        if rec['index'] not in SELECTED:continue
        members=sorted(byrec[rec['recording']],key=lambda x:x['aris_frame'])
        lo,hi=round((len(members)-1)*.2),round((len(members)-1)*.8)
        if hi-lo<99:
            lo=max(0,(len(members)-100)//2);hi=min(len(members)-1,lo+99)
        positions=np.linspace(lo,hi,min(100,len(members))).round().astype(int)
        assert len(set(positions))==100
        rows=[]
        for ordinal,pos in enumerate(positions):
            m=members[pos];p=Path(m['original_image']).parent.parent/'aris_raw'/f"{m['aris_frame']:04d}.pgm"
            a=arr(p); assert a.ndim==2 and a.shape[1]==128 and a.dtype==np.uint8
            b,diag=propose(a,rec['index'])
            r=dict(sample=m['sample'],recording=m['recording'],category=m['category'],overview_index=rec['index'],ordinal=ordinal,frame=m['aris_frame'],source=str(p),source_sha256=sha(p),shape_hw=list(a.shape),proposal_xyxy=b,diagnostics=diag,reference_sd=m.get('reference_sd'),paired_role=m.get('paired_role'),status='pending_visual_review')
            rows.append(r);proposals.append(r)
        for j in range(5):
            canvas=Image.new('RGB',(1600,960),'white')
            for k,r in enumerate(rows[j*20:(j+1)*20]):canvas.paste(tile(r),((k%5)*320,(k//5)*240))
            canvas.save(out/f"r{rec['index']:02d}_p{j}.jpg",quality=94)
    (out/'proposals.json').write_text(json.dumps(proposals,ensure_ascii=False,indent=2),'utf-8')
    # Three class pilots: full raw and corresponding close-up, same sample coordinates.
    for idx in [2,18,34]:
        rows=[r for r in proposals if r['overview_index']==idx][::11]
        canvas=Image.new('RGB',(1600,960),'white')
        for k,r in enumerate(rows):
            canvas.paste(tile(r,size=(320,240),show_context=True),((k%5)*320,(k//5)*480))
            canvas.paste(tile(r,size=(320,240)),((k%5)*320,(k//5)*480+240))
        canvas.save(out/f'pilot_r{idx:02d}.jpg',quality=95)
    print(json.dumps(dict(proposals=len(proposals),recordings=len(SELECTED),reviewed=0)))
if __name__=='__main__':main()
