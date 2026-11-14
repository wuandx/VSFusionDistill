"""Freeze image-only ridge observations and audit five development metadata chains."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import sys,json,csv,hashlib
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np,cv2
from PIL import Image,ImageDraw
from sonar_manual_curation_server import DatasetSource
OUT=ROOT/'DataSet/sonar_projection_root_cause'
BASE=ROOT/'DataSet/sonar_box_guided_full_trajectory'
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),'utf-8')
def ridge(a,b):
    sm=cv2.GaussianBlur(a.astype('float32'),(3,5),0);x0,y0,x1,y1=map(int,b)
    span=max(x1-x0,1);us=np.unique(np.round(np.linspace(x0+.12*span,x1-.12*span,18)).astype(int));pts=[]
    bg=np.median(sm);mad=np.median(abs(sm-bg))
    for u in us:
        if not 0<=u<a.shape[1]:continue
        signal=sm[y0:y1,u];k=int(np.argmax(signal));v=y0+k
        if float(signal[k])-bg<max(6,2*mad) or v<=y0+2 or v>=y1-3:continue
        pts.append([u+.5,v+.5])
    # Reject isolated branch jumps; no model-derived locations used.
    if len(pts)>=5:
        p=np.array(pts);keep=np.ones(len(p),bool)
        for i in range(1,len(p)-1):
            predict=np.interp(p[i,0],p[[i-1,i+1],0],p[[i-1,i+1],1]);keep[i]=abs(p[i,1]-predict)<=max(10,.18*(y1-y0))
        p=p[keep]
    else:p=np.array(pts).reshape(-1,2)
    return p.tolist()
def main():
    assert not OUT.exists();OUT.mkdir();(OUT/'observations').mkdir()
    (OUT/'plan-before-observation.md').write_bytes((ROOT/'experiment/sonar-projection-root-cause-plan.md').read_bytes())
    ds=DatasetSource();rows=read(BASE/'results.json')['frames'];observations={};panels={};hashes={str(BASE/'results.json'):sha(BASE/'results.json'),str(__file__):sha(__file__)}
    for r in rows:
        sid=r['sample'];ds.require(sid);source=Path(r['provenance']['raw']['path']);assert sha(source)==r['provenance']['raw']['sha256']
        a=np.array(Image.open(source));pts=ridge(a,r['reference_bbox']);obs=dict(sample=sid,recording=r['recording'],model=r['model'],role=r['role'],reference_bbox=r['reference_bbox'],points_raw_uv=pts,source_sha256=sha(source),source=str(source),semantics='assistant-derived intensity-peak proxies; not physical correspondences',usable=len(pts)>=6)
        observations[sid]=obs
    chosen=[]
    for group in sorted({(r['recording'],r['role']) for r in rows}):
        rr=sorted([r for r in rows if (r['recording'],r['role'])==group],key=lambda r:r['sample'])
        take=rr if group[1]=='fit' else [rr[i] for i in sorted({0,len(rr)//2,len(rr)-1})]
        tiles=[]
        for r in take:
            ob=observations[r['sample']];a=np.array(Image.open(ob['source']));b=ob['reference_bbox'];lo=max(0,int(b[1])-25);hi=min(len(a),int(b[3])+25)
            tile=Image.new('RGB',(480,340),'white');im=Image.fromarray(np.minimum(a.astype(float)*2.5,255).astype('uint8')).convert('RGB').crop((0,lo,a.shape[1],hi)).resize((480,305));d=ImageDraw.Draw(im)
            d.rectangle((b[0]*480/a.shape[1],(b[1]-lo)*305/(hi-lo),b[2]*480/a.shape[1],(b[3]-lo)*305/(hi-lo)),outline='lime',width=2)
            for u,v in ob['points_raw_uv']:
                x=u*480/a.shape[1];y=(v-lo)*305/(hi-lo);d.ellipse((x-3,y-3,x+3,y+3),fill='cyan')
            tile.paste(im,(0,35));ImageDraw.Draw(tile).text((5,5),r['sample']+' '+r['role'],fill='black');tiles.append(tile);chosen.append(r['sample'])
        canvas=Image.new('RGB',(1440,340*((len(tiles)+2)//3)),'white')
        for i,t in enumerate(tiles):canvas.paste(t,((i%3)*480,(i//3)*340))
        name=group[0]+'-'+group[1]+'.jpg';canvas.save(OUT/'observations'/name,quality=96);panels[name]=[r['sample'] for r in take]
    save(OUT/'observations.json',dict(frames=observations,algorithm='frozen strongest smoothed return within existing box; interior beams; MAD gate; isolated jump rejection',review_panels=panels))
    base=Path('D:/pby/data_processed');matches=list(csv.DictReader((base/'matches.csv').open(encoding='utf-8-sig')));hashes[str(base/'matches.csv')]=sha(base/'matches.csv');audits=[]
    for rec in sorted({r['recording'] for r in rows}):
        mm,gg,mp,gp=ds.recording_metadata(rec);indices=sorted(mm);m=[mm[i] for i in indices];a=np.array([[float(x[k]) for k in ['FrameTime','SonarPan','SonarTilt','SonarRoll','PanAbsPosition','TiltAbsPosition','RollAbsPosition','sonarTimeStamp']] for x in m]);diff=(a[:,4:7]-a[:,1:4]+180)%360-180
        match=next(r for r in matches if Path(r['aris_file']).name==rec);rawg=base/match['gantry_file'];gm=list(csv.DictReader(rawg.open(encoding='utf-8-sig')));g=np.array([[float(x[k]) for k in ['timestamp_us','x','y','z']] for x in gm]);amp=base/match['aris_file']/(rec+'_frames.csv');am=list(csv.DictReader(amp.open(encoding='utf-8-sig')));onset=next(int(x['FrameTime']) for x in am if int(x['FrameIndex'])==int(match['aris_onset']));target=g[0,0]+float(match['gantry_offset'])+(a[:,0]-onset)
        reconstructed=np.column_stack([np.interp(target,g[:,0],g[:,j]) for j in [1,2,3]]);released=np.array([[float(gg[i][k]) for k in 'xyz'] for i in indices]);err=abs(reconstructed-released)
        for p in [rawg,amp,ds.rec_dirs[rec]/'notes.txt',Path(mp['path']),Path(gp['path'])]:hashes[str(p)]=sha(p)
        audits.append(dict(recording=rec,metadata_frames=len(m),match=match,notes=(ds.rec_dirs[rec]/'notes.txt').read_text('utf-8',errors='replace'),encoder_minus_sonar_angles_deg_percentiles=np.percentile(diff,[0,5,50,95,100],axis=0).tolist(),frametime_minus_sonar_timestamp_seconds_percentiles=np.percentile((a[:,0]-a[:,7])/1e6,[0,50,100]).tolist(),gantry_replay_max_abs_m=float(err.max()),gantry_clock_clamped_frames=int(((target<g[0,0])|(target>g[-1,0])).sum()),gantry_source_first_motion_gap_s=float(np.diff(g[:,0]).max()/1e6),image_sync_certified=False))
    assert all(sha(p)==s for p,s in hashes.items());save(OUT/'source-audit.json',dict(records=audits,input_hashes=hashes,inputs_unchanged=True,official_pose_formula='R_setup_ar3 @ Euler_xyz(SonarRoll,SonarTilt,SonarPan); translation gantry+offset; matches release_1_export.py',new_sync_certification=False))
    print(json.dumps(dict(frames=len(rows),fit=sum(x['role']=='fit' for x in observations.values()),unusable=sum(not x['usable'] for x in observations.values()),records=[dict(recording=r['recording'],gantry_replay_max_abs_m=r['gantry_replay_max_abs_m'],encoder_deg=r['encoder_minus_sonar_angles_deg_percentiles']) for r in audits]),indent=2),flush=True)
if __name__=='__main__':main()
