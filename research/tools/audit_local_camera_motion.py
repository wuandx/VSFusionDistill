"""Fixed nearby-frame image correspondences vs published camera trajectory."""
from pathlib import Path
import sys,csv,json,hashlib,itertools,subprocess
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np,cv2
from scipy.spatial.transform import Rotation
OUT=ROOT/'DataSet/sonar_view_consistency';PRIOR=ROOT/'DataSet/sonar_independent_registration';BASE=Path('D:/pby/data_processed')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def table(p):
    with Path(p).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
rows=read(PRIOR/'selection.json')['samples'];manifest={r['sample']:r for r in read(ROOT/'DataSet/camera_temporal_all/manifest-resolved.json')['items'] if r.get('paired_role') in ['train','val','val_id']}
assert all(r['sample'] in manifest for r in rows)
matches={Path(r['aris_file']).name:r for r in table(BASE/'matches.csv')}
v=read(ROOT/'DataSet/sonar_model_registration_consistency/calibration-versions.json')['versions']['release_current']
tf={k:np.array(x) for k,x in v['parent_from_child_matrices'].items()}
K=np.array(read(PRIOR/'results.json')['K_sd']);ik=np.linalg.inv(K)
def skew(t):
    x,y,z=t;return np.array([[0,-z,y],[z,0,-x],[-y,x,0]])
def err(F,a,b):
    x=np.c_[a,np.ones(len(a))];y=np.c_[b,np.ones(len(b))];fx=x@F.T;fy=y@F
    return np.abs(np.sum(y*fx,axis=1))/np.sqrt(np.maximum(np.sum(fx[:,:2]**2,axis=1)+np.sum(fy[:,:2]**2,axis=1),1e-20))
sift=cv2.SIFT_create(nfeatures=3000);matcher=cv2.BFMatcher();outputs=[];tracked={};access=[]
for rec in sorted({r['recording'] for r in rows}):
    rr=[r for r in rows if r['recording']==rec];match=matches[rec]
    mpath=BASE/match['aris_file']/(rec+'_frames.csv');gpath=Path(rr[0]['gantry_source'])
    tracked[str(mpath)]=sha(mpath);tracked[str(gpath)]=sha(gpath)
    meta=table(mpath);gantry=table(gpath);times=np.array([int(x['FrameTime']) for x in meta]);onset=times[int(match['aris_onset'])]
    mt={int(x['FrameIndex']):int(x['FrameTime']) for x in meta};gt=np.array([mt[int(x['aris_frame_idx'])] for x in gantry])
    unwrapped={k:np.unwrap(np.deg2rad([float(x[k]) for x in meta])) for k in ['SonarRoll','SonarTilt','SonarPan']}
    video=BASE/match['gopro_file'];cap=cv2.VideoCapture(str(video));fps=cap.get(cv2.CAP_PROP_FPS);n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    def pose(index,offset=0.):
        stamp=onset+((index-int(match['gopro_offset'])+.5+offset)/fps)*1e6
        wa=np.eye(4);wa[:3,3]=[np.interp(stamp,gt,[float(x[k]) for x in gantry]) for k in 'xyz'];wa[:3,3]+=tf['setup/ar3'][:3,3]
        angles=[np.interp(stamp,times,unwrapped[k]) for k in ['SonarRoll','SonarTilt','SonarPan']]
        wa[:3,:3]=tf['setup/ar3'][:3,:3]@Rotation.from_euler('xyz',angles).as_matrix()
        return wa@tf['setup/gopro_mounting_hole']@tf['setup/gopro_mounting_axis']@tf['setup/camera']
    for row in rr:
        if not row.get('camera_copy'):continue
        center=manifest[row['sample']]['sd_index'];indices=[center-15,center,center+15];images={};features={}
        for index in indices:
            if not 0<=index<n:continue
            cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,img=cap.read()
            if not ok:continue
            gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY);images[index]=gray;features[index]=sift.detectAndCompute(gray,None)
            access.append(dict(recording=rec,source=str(video),sd_index=index,decoded_sha256=hashlib.sha256(img.tobytes()).hexdigest()))
        for a,b in [(center-15,center),(center,center+15)]:
            entry=dict(sample=row['sample'],recording=rec,index_a=a,index_b=b)
            if a not in images or b not in images:entry['status']='out_of_coverage';outputs.append(entry);continue
            ka,da=features[a];kb,db=features[b]
            ab=matcher.knnMatch(da,db,k=2);ba=matcher.knnMatch(db,da,k=2);back={m.queryIdx:m.trainIdx for m,z in ba if m.distance<.7*z.distance}
            good=[m for m,z in ab if m.distance<.7*z.distance and back.get(m.trainIdx)==m.queryIdx]
            entry['ratio_mutual_matches']=len(good)
            if len(good)<12:entry['status']='insufficient_matches';outputs.append(entry);continue
            pa=np.float32([ka[m.queryIdx].pt for m in good]);pb=np.float32([kb[m.trainIdx].pt for m in good]);cv2.setRNGSeed(0)
            F,mask=cv2.findFundamentalMat(pa,pb,cv2.FM_RANSAC,1.5,.999,10000)
            if F is None or F.shape!=(3,3):entry['status']='F_failed';outputs.append(entry);continue
            keep=mask.ravel().astype(bool);x,y=pa[keep],pb[keep]
            entry.update(status='diagnostic',ransac_inliers=int(len(x)),image_F_median_sampson_px=float(np.median(err(F,x,y))),
                image_a_hull_area_fraction=float(cv2.contourArea(cv2.convexHull(x))/(640*360)),image_b_hull_area_fraction=float(cv2.contourArea(cv2.convexHull(y))/(640*360)))
            entry['source_time_quantization']=[]
            for offset in [-1,0,1]:
                relative=np.linalg.inv(pose(b,offset))@pose(a,offset);pred=ik.T@skew(relative[:3,3])@relative[:3,:3]@ik
                e=err(pred,x,y);entry['source_time_quantization'].append(dict(offset_sd_frames=offset,median_sampson_px=float(np.median(e)),p90_sampson_px=float(np.percentile(e,90)),translation_norm_m=float(np.linalg.norm(relative[:3,3]))))
            entry['median_flow_px']=np.median(y-x,axis=0).tolist()
            entry['linear_focal_sweep']=[]
            relative=np.linalg.inv(pose(b))@pose(a)
            for factor in [.5,.75,1.,1.25,1.5,2.]:
                kk=K.copy();kk[0,0]*=factor;kk[1,1]*=factor;i=np.linalg.inv(kk);p=i.T@skew(relative[:3,3])@relative[:3,:3]@i
                entry['linear_focal_sweep'].append(dict(factor=factor,median_sampson_px=float(np.median(err(p,x,y)))))
            dest=OUT/'local-matches'/f'{rec}_{a:04d}_{b:04d}.jpg';dest.parent.mkdir(exist_ok=True)
            draw=cv2.drawMatches(images[a],ka,images[b],kb,[m for m,k in zip(good,keep) if k],None,flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
            dest.write_bytes(cv2.imencode('.jpg',draw)[1].tobytes())
            entry['points_a']=x.tolist();entry['points_b']=y.tolist();entry['image_F']=F.tolist()
            outputs.append(entry)
    cap.release()
assert all(sha(Path(p))==h for p,h in tracked.items())
(OUT/'local-motion.json').write_text(json.dumps(dict(outputs=outputs,access=access,input_hashes=tracked,input_hashes_unchanged=True,script_sha256=sha(Path(__file__))),indent=2),encoding='utf-8')
for o in outputs:
    if o.get('status')=='diagnostic':print(o['recording'],o['index_a'],o['index_b'],'N',o['ransac_inliers'],'coverage',round(o['image_a_hull_area_fraction'],2),'imageF',round(o['image_F_median_sampson_px'],2),'source',round(o['source_time_quantization'][1]['median_sampson_px'],2))
