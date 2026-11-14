"""Recheck saved correspondences; no new videos, registration or GT writes."""
from pathlib import Path
import sys, json, hashlib, csv
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
import cv2
from scipy.spatial.transform import Rotation
OUT = ROOT/'DataSet/sonar_view_consistency'
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def skew(t):
    x,y,z=t
    return np.array([[0,-z,y],[z,0,-x],[-y,x,0]])
def error(F,a,b):
    x=np.c_[a,np.ones(len(a))]; y=np.c_[b,np.ones(len(b))]
    fx=x@F.T; fy=y@F
    return np.abs(np.sum(y*fx,axis=1))/np.maximum(np.sqrt(np.sum(fx[:,:2]**2,axis=1)+np.sum(fy[:,:2]**2,axis=1)),1e-15)
def table(p):
    with p.open(encoding='utf-8',newline='') as f: return list(csv.DictReader(f))
paths=[OUT/'local-motion.json', OUT/'verification.json', ROOT/'DataSet/sonar_independent_registration/contours.json', ROOT/'DataSet/sonar_independent_registration/selection.json', ROOT/'DataSet/camera_temporal_all/manifest-resolved.json', ROOT/'DataSet/sonar_independent_registration/results.json',ROOT/'DataSet/sonar_model_registration_consistency/calibration-versions.json',OUT/'source-check.json',ROOT/'experiment/sonar-view-consistency-plan.md']
before={str(p):sha(p) for p in paths}
local=read(paths[0]); prior=read(paths[1]); contours=read(paths[2])['points']; rows=read(paths[3])['samples']
manifest={x['sample']:x for x in read(paths[4])['items'] if x.get('paired_role') in ['train','val','val_id']}
assert all(x['sample'] in manifest for x in rows)
K=np.array(read(paths[5])['K_sd']); ik=np.linalg.inv(K)
tf={k:np.array(v) for k,v in read(paths[6])['versions']['release_current']['parent_from_child_matrices'].items()}
matches_path=Path('D:/pby/data_processed/matches.csv');before[str(matches_path)]=sha(matches_path)
matches={Path(x['aris_file']).name:x for x in table(matches_path)}
cache={}
def pose(rec,index):
    if rec not in cache:
        match=matches[rec]; row=next(x for x in rows if x['recording']==rec)
        meta_path=Path('D:/pby/data_processed')/match['aris_file']/(rec+'_frames.csv'); gp=Path(row['gantry_source'])
        before[str(meta_path)]=sha(meta_path); before[str(gp)]=sha(gp)
        mm=table(meta_path); gg=table(gp); mt={int(x['FrameIndex']):int(x['FrameTime']) for x in mm}
        ts=np.array([int(x['FrameTime']) for x in mm]); gt=np.array([mt[int(x['aris_frame_idx'])] for x in gg])
        angles=np.unwrap(np.deg2rad([[float(x[k]) for k in ['SonarRoll','SonarTilt','SonarPan']] for x in mm]),axis=0)
        xyz=np.array([[float(x[k]) for k in 'xyz'] for x in gg])
        fps=next(x['video_fps'] for x in read(OUT/'source-check.json') if x['sample'].startswith(rec))
        cache[rec]=(match,ts,gt,angles,xyz,mt[int(match['aris_onset'])],fps)
    match,ts,gt,angles,xyz,onset,fps=cache[rec]
    stamp=onset+(index-int(match['gopro_offset'])+.5)/fps*1e6
    wa=np.eye(4);wa[:3,:3]=tf['setup/ar3'][:3,:3]@Rotation.from_euler('xyz',[np.interp(stamp,ts,angles[:,k]) for k in range(3)]).as_matrix()
    wa[:3,3]=tf['setup/ar3'][:3,3]+[np.interp(stamp,gt,xyz[:,k]) for k in range(3)]
    return wa@tf['setup/gopro_mounting_hole']@tf['setup/gopro_mounting_axis']@tf['setup/camera']
def fundamental(a,b):
    rel=np.linalg.solve(b,a)
    return ik.T@skew(rel[:3,3])@rel[:3,:3]@ik
# Synthetic independent homogeneous projection control, known world_from_camera.
rng=np.random.default_rng(51); xyz=rng.uniform([-1,-.7,3],[1,.7,7],size=(80,3))
wa=np.eye(4);wb=np.eye(4);wb[:3,:3]=Rotation.from_euler('xyz',[.02,.07,-.03]).as_matrix();wb[:3,3]=[.3,-.12,.08]
def project(wc):
    q=(np.linalg.inv(wc)@np.c_[xyz,np.ones(len(xyz))].T)[:3]; pix=K@q
    return (pix[:2]/pix[2]).T
pa,pb=project(wa),project(wb);synthetic=float(error(fundamental(wa,wb),pa,pb).max())
wrong=float(np.median(error(fundamental(wb,wa),pa,pb)))
assert synthetic<1e-9 and wrong>.01
output=[]
for o in local['outputs']:
    if o['status']!='diagnostic':
        output.append({k:o[k] for k in ['sample','recording','index_a','index_b','status']});continue
    a=np.array(o['points_a']); b=np.array(o['points_b']); keep=np.ones(len(a),dtype=bool)
    center=manifest[o['sample']]['sd_index'];poly=np.array(contours[o['sample']],np.float32)
    for index,points in [(o['index_a'],a),(o['index_b'],b)]:
        if index==center: keep &= np.array([cv2.pointPolygonTest(poly,tuple(p),True)<-10 for p in points])
    F=fundamental(pose(o['recording'],o['index_a']),pose(o['recording'],o['index_b']))
    source=error(F,a,b)
    assert abs(float(np.median(source))-o['source_time_quantization'][1]['median_sampson_px'])<1e-7
    entry={k:o[k] for k in ['sample','recording','index_a','index_b','ransac_inliers','image_F_median_sampson_px']}
    entry['all_source_median_px']=float(np.median(source));entry['subsets']={}
    for name,mask in [('all',np.ones(len(a),bool)),('outside_target',keep)]:
        x,y=a[mask],b[mask];s={'count':len(x)}
        if len(x)>=4:
            s['hull_fraction']=float(cv2.contourArea(cv2.convexHull(x.astype(np.float32)))/(640*360))
            cv2.setRNGSeed(0);H,hm=cv2.findHomography(x,y,cv2.RANSAC,1.5,maxIters=10000,confidence=.999)
            s['homography_support_fraction']=float(hm.mean()) if hm is not None else None
            s['source_median_px']=float(np.median(error(F,x,y)))
        if len(x)>=24:
            order=np.lexsort((x[:,1],x[:,0]));train=order[::2];check=order[1::2]
            ff,_=cv2.findFundamentalMat(x[train],y[train],cv2.FM_8POINT)
            if ff is not None and ff.shape==(3,3):
                s['split_F_check_median_px']=float(np.median(error(ff,x[check],y[check])))
                s['split_source_check_median_px']=float(np.median(error(F,x[check],y[check])))
        entry['subsets'][name]=s
    output.append(entry)
assert all(sha(Path(p))==h for p,h in before.items())
assert all(sha(Path(p))==h for p,h in local['input_hashes'].items())
prior_changes=[dict(path=p,old_sha256=h,current_sha256=sha(Path(p))) for p,h in prior['input_hashes'].items() if sha(Path(p))!=h]
assert all(Path(x['path']).resolve()==(ROOT/'experiment/sonar-view-consistency-plan.md').resolve() for x in prior_changes)
assert all(Path(p).stat().st_size==v['bytes'] and Path(p).stat().st_mtime_ns==v['mtime_ns'] for p,v in prior['video_stat_identity'].items())
result=dict(synthetic_max_error_px=synthetic,wrong_direction_median_px=wrong,inputs_unchanged_during_review=True,prior_changes=prior_changes,input_hashes=before,script_sha256=sha(Path(__file__)),outputs=output,new_image_access=0,note='Split F uses points previously filtered by all-point RANSAC; internal check only. Outside-target points are not guaranteed static background.')
(OUT/'motion-evidence-review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
for o in output:
    if 'subsets' in o: print(o['recording'],o['index_a'],o['index_b'],json.dumps(o['subsets']['outside_target']))
