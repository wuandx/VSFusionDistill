"""Source-motion-derived time control; no fitted time, angle or mesh."""
from pathlib import Path
import sys,json,csv,hashlib
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np,cv2
from scipy.optimize import least_squares
from PIL import Image,ImageDraw
from fit_mortar_fixed_registration import read_obj
from fit_sonar_endpoint_registration import uv_project,transform
OUT=ROOT/'DataSet/sonar_source_onset_control';BASE=Path('D:/pby/data_processed');hashes={}
def read(p):
    hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text('utf-8'))
def table(p):
    hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
    with p.open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def main():
    OUT.mkdir(exist_ok=True);assert not (OUT/'results.json').exists()
    audit=read(ROOT/'DataSet/sonar_motion_timing/results.json')['records'];byrec={r['recording']:r for r in audit};old=read(ROOT/'DataSet/sonar_fixed_mesh/results.json')['outputs'];models=read(ROOT/'DataSet/sonar_fixed_mesh/fixed-mesh-transforms.json')['models'];new=[];cache={}
    for f in old:
        rec=f['recording'];a=byrec[rec];m=a['match']
        if rec not in cache:
            g=table(BASE/m['gantry_file']);g=np.array([[float(r[k]) for k in ['timestamp_us','x','y','z']] for r in g]);ar=table(BASE/m['aris_file']/(rec+'_frames.csv'));onset=next(int(r['FrameTime']) for r in ar if int(r['FrameIndex'])==int(m['aris_onset']));cache[rec]=(g,onset)
        g,onset=cache[rec];time=g[0,0]+a['gantry_vector_onset_offset_us']+f['frame_time_us']-onset;xyz=np.array([np.interp(time,g[:,0],g[:,k]) for k in [1,2,3]]);delta=xyz-np.array(f['gantry_xyz_m']);nf=dict(f)
        for k in ['world_from_sonar','world_from_ar3']:
            mat=np.array(f[k]);mat[:3,3]+=delta;nf[k]=mat.tolist()
        nf.update(gantry_xyz_m=xyz.tolist(),source_onset_position_shift_m=delta.tolist(),source_onset_time_us=float(time),source_onset_clamped=bool(time<g[0,0] or time>g[-1,0]));new.append(nf)
    lookup={f['sample']:f for f in new};cards=[];support=[]
    info=models['100lbs'];v,faces=read_obj(info['source']);S=np.array(info['world_from_target'])@np.array(info['mesh_to_target_similarity']);world=transform(v,S)
    observations=read(ROOT/'DataSet/sonar_fixed_registration_refinement/100lbs/adapted-fit-observations.json');ob={f['sample']:f for f in observations['frames']}
    for f in old:
        if f['model']!='100lbs':continue
        sid=f['sample'];nf=lookup[sid];rawpath=ROOT/'DataSet/sonar_fixed_mesh/frames'/f'{sid}-raw.png';hashes[str(rawpath)]=hashlib.sha256(rawpath.read_bytes()).hexdigest();raw=np.array(Image.open(rawpath).convert('L'));h,w=raw.shape;canvas=Image.new('RGB',(1050,h+80),'white');d=ImageDraw.Draw(canvas);d.text((10,8),sid+' | old timing / source motion onset; same frozen PCA mesh',fill='black');counts={}
        for i,(name,ff) in enumerate([('old',f),('source_onset',nf)]):
            pic=Image.fromarray(np.minimum(raw.astype('uint16')*3,255).astype('uint8')).convert('RGB').resize((512,h));canvas.paste(pic,(525*i,35));uv,e,z=uv_project(world,ff);horizontal=(z>0)&(uv[:,0]>=0)&(uv[:,0]<=w)&(uv[:,1]>=0)&(uv[:,1]<=h)
            for key,mask,color in [('full',horizontal,'cyan'),('gate7',horizontal&(abs(e)<=7),'lime')]:
                if mask.sum()<3:continue
                hull=cv2.convexHull(uv[mask].astype('float32')).reshape(-1,2);xy=[(525*i+u*4,v+35) for u,v in hull];d.line(xy+[xy[0]],fill=color,width=2)
                if sid in ob:
                    ds=[cv2.pointPolygonTest((hull/[2,5]).astype('float32'),tuple(np.array(p['witness_raw_uv_edge'])/[2,5]),True) for p in ob[sid]['points']];counts[name+'_'+key]=float(np.mean(np.array(ds)>=-1))
        canvas.save(OUT/f'{sid}.png');cards.append(f'<h3>{sid}</h3><img src="{sid}.png">');support.append(dict(sample=sid,support=counts,position_shift_m=nf['source_onset_position_shift_m']))
    # Fixed optical observations, same fit/check identities in both timing arms.
    landmarks=read(ROOT/'DataSet/sonar_independent_registration/landmarks.json')['points'];selection=read(ROOT/'DataSet/sonar_independent_registration/selection.json')['samples'];K=np.array(read(ROOT/'DataSet/sonar_independent_registration/results.json')['K_sd']);tf={k:np.array(v) for k,v in read(ROOT/'DataSet/sonar_model_registration_consistency/calibration-versions.json')['versions']['release_current']['parent_from_child_matrices'].items()};camera=[]
    for category in sorted({r['category'] for r in selection}):
        rr=[r for r in selection if r['category']==category and r['sample'] in landmarks and r.get('camera_copy')];rec=rr[0]['recording'];fr=[r for r in rr if r['recording']==rec];fitids={fr[0]['sample'],fr[-1]['sample']}
        for name,allframes in [('old',old),('source_onset',new)]:
            frames={f['sample']:f for f in allframes};poses={r['sample']:np.array(frames[r['sample']]['world_from_ar3'])@tf['setup/gopro_mounting_hole']@tf['setup/gopro_mounting_axis']@tf['setup/camera'] for r in rr};ends=[]
            for j in [0,1]:
                A=[];b=[]
                for sid in fitids:
                    pose=poses[sid];direction=pose[:3,:3]@np.linalg.inv(K)@np.r_[landmarks[sid][j],1];direction/=np.linalg.norm(direction);M=np.eye(3)-np.outer(direction,direction);A.append(M);b.append(M@pose[:3,3])
                p0=np.linalg.lstsq(np.concatenate(A),np.concatenate(b),rcond=None)[0]
                def project(p,sid):
                    pc=np.linalg.solve(poses[sid],np.r_[p,1]);q=K@pc[:3];return q[:2]/q[2]
                sol=least_squares(lambda p:np.concatenate([project(p,sid)-landmarks[sid][j] for sid in fitids]),p0)
                ends.append(dict(point_world=sol.x.tolist(),errors=[dict(sample=r['sample'],fit=r['sample'] in fitids,error_px=float(np.linalg.norm(project(sol.x,r['sample'])-landmarks[r['sample']][j]))) for r in rr]))
            fit=[v['error_px'] for e in ends for v in e['errors'] if v['fit']];check=[v['error_px'] for e in ends for v in e['errors'] if not v['fit']];row=dict(category=category,arm=name,fit_ids=sorted(fitids),endpoints=ends,fit_median_px=float(np.median(fit)),check_median_px=float(np.median(check)),check_max_px=float(max(check)),endpoint_distance_m=float(np.linalg.norm(np.array(ends[0]['point_world'])-ends[1]['point_world'])));camera.append(row);print(category,name,row['fit_median_px'],row['check_median_px'],row['endpoint_distance_m'])
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    result=dict(frames=new,sonar_support=support,camera=camera,input_hashes=hashes,inputs_unchanged=True,not_deployed=True,new_gt=0)
    (OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');(OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><h1>源运动起点对照：仅改变gantry时间对应</h1><p>左右使用同一旧PCA模型；青色完整投影，绿色±7°；不是GT。</p>'+''.join(cards),encoding='utf-8');print('sonar',support)
if __name__=='__main__':main()
