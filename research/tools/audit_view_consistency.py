"""Mesh-independent source, intrinsic-sensitivity and image epipolar diagnostics."""
from pathlib import Path
import sys,json,csv,hashlib,re,subprocess,itertools
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
import cv2
from scipy.spatial.transform import Rotation
from scipy.optimize import least_squares
OUT=ROOT/'DataSet/sonar_view_consistency';OUT.mkdir(exist_ok=True)
PRIOR=ROOT/'DataSet/sonar_independent_registration';BASE=Path('D:/pby/data_processed')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def table(p,key):
    with Path(p).open(encoding='utf-8',newline='') as f:return {r[key]:r for r in csv.DictReader(f)}
rows=read(PRIOR/'selection.json')['samples'];land=read(PRIOR/'landmarks.json')['points']
manifest={i['sample']:i for i in read(ROOT/'DataSet/camera_temporal_all/manifest-resolved.json')['items'] if i.get('paired_role') in ['train','val','val_id']}
assert all(r['sample'] in manifest for r in rows)
tracked={Path(__file__),ROOT/'experiment/sonar-view-consistency-plan.md',PRIOR/'selection.json',PRIOR/'landmarks.json',BASE/'matches.csv',BASE/'gantry/gantry_metadata.csv'}
matches={Path(r['aris_file']).name:r for r in table(BASE/'matches.csv','aris_file').values()}
gm=table(BASE/'gantry/gantry_metadata.csv','file');data={};source=[]
for rec in sorted({r['recording'] for r in rows}):
    rr=[r for r in rows if r['recording']==rec];match=matches[rec]
    aris=BASE/match['aris_file']/(rec+'_frames.csv');gantry=BASE/match['gantry_file']
    tracked.update([aris,gantry,Path(rr[0]['meta_source']),Path(rr[0]['gantry_source'])])
    am={int(k):v for k,v in table(aris,'FrameIndex').items()};em={int(k):v for k,v in table(rr[0]['meta_source'],'FrameIndex').items()}
    eg={int(k):v for k,v in table(rr[0]['gantry_source'],'aris_frame_idx').items()}
    gd=np.genfromtxt(gantry,delimiter=',',names=True);gmeta=gm[gantry.name]
    onset=int(am[int(match['aris_onset'])]['FrameTime'])
    data[rec]=(em,eg)
    # Only selected camera video metadata is read, no other recording videos.
    video=BASE/match['gopro_file'];tracked.add(video)
    cap=cv2.VideoCapture(str(video));fps=cap.get(cv2.CAP_PROP_FPS);frames=cap.get(cv2.CAP_PROP_FRAME_COUNT);cap.release()
    for row in rr:
        m=am[row['aris_frame']];g=eg[row['aris_frame']]
        t=float(gmeta['start_us'])+float(match['gantry_offset'])+int(m['FrameTime'])-onset
        xyz=np.array([np.interp(t,gd['timestamp_us'],gd[k]) for k in 'xyz']);exported=np.array([float(g[k]) for k in 'xyz'])
        expected=int((int(m['FrameTime'])-onset)*fps/1e6)+int(match['gopro_offset'])
        item=manifest[row['sample']]
        entry=dict(sample=row['sample'],gantry_max_abs_error_m=float(np.max(np.abs(xyz-exported))),
            gantry_clamped=bool(t<gd['timestamp_us'].min() or t>gd['timestamp_us'].max()),
            frame_time_matches=int(m['FrameTime'])==int(em[row['aris_frame']]['FrameTime'])==item['aris_time_us'],
            orientation_matches=all(abs(float(m[k])-float(em[row['aris_frame']][k]))<1e-10 for k in ['SonarPan','SonarTilt','SonarRoll']),
            onset_matches=onset==item['aris_onset_time_us'],expected_sd_index=expected,manifest_sd_index=item['sd_index'],
            sd_index_matches=expected==item['sd_index'],sd_index_within_video=0<=expected<frames,
            video_fps=fps,video_frames=int(frames))
        if row.get('camera_copy'):
            tracked.update([Path(row['camera_source']),Path(row['camera_copy'])]);entry['sd_copy_hash_matches']=sha(row['camera_source'])==sha(row['camera_copy'])==row['camera_sha256']
        source.append(entry)
save(OUT/'source-check.json',source)
assert all(s['gantry_max_abs_error_m']<1e-7 and s['frame_time_matches'] and s['orientation_matches'] and s['onset_matches'] and s['sd_index_matches'] for s in source)
# Hash small inputs and record video identity cheaply; prior work already checked official archive CRC.
small={str(p):sha(p) for p in tracked if p.suffix.lower()!='.mp4'}
video_identity={str(p):dict(bytes=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns) for p in tracked if p.suffix.lower()=='.mp4'}
versions=read(ROOT/'DataSet/sonar_model_registration_consistency/calibration-versions.json')['versions']
static={k:np.array(v) for k,v in versions['release_current']['parent_from_child_matrices'].items()}
def pose(row,version='release_current'):
    tf={k:np.array(v) for k,v in versions[version]['parent_from_child_matrices'].items()}
    mm,gg=data[row['recording']];m=mm[row['aris_frame']];g=gg[row['aris_frame']]
    wa=np.eye(4);wa[:3,3]=np.array([float(g[k]) for k in 'xyz'])+tf['setup/ar3'][:3,3]
    wa[:3,:3]=tf['setup/ar3'][:3,:3]@Rotation.from_euler('xyz',[float(m[k]) for k in ['SonarRoll','SonarTilt','SonarPan']],degrees=True).as_matrix()
    return wa@tf['setup/gopro_mounting_hole']@tf['setup/gopro_mounting_axis']@tf['setup/camera']
Ks={}
for mode in ['linear','wide','narrow','superview']:
    path=ROOT/f'related_work/sonar-projection-audit-assets/data_export_calibration/calibration/camera_parameters/camera_parameter_{mode}.txt'
    text=path.read_text();numbers=[float(x) for x in re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?',text.split('distortion')[0])]
    K=np.array(numbers).reshape(3,3);K[:2]/=3;Ks[mode]=K
    small[str(path)]=sha(path)
def endpoint_control(rr,K,version='release_current'):
    fit=[r for r in rr if r['role']=='registration_fit'];fit=fit[:2]
    errors=[];points=[]
    for ix in [0,1]:
        Ps=[K@np.linalg.inv(pose(r,version))[:3] for r in fit]
        A=[]
        for P,r in zip(Ps,fit):
            x,y=land[r['sample']][ix];A.extend([x*P[2]-P[0],y*P[2]-P[1]])
        _,_,vh=np.linalg.svd(A);p0=vh[-1,:3]/vh[-1,3]
        def project(p,r):
            q=K@(np.linalg.inv(pose(r,version))@np.r_[p,1])[:3];return q[:2]/q[2]
        result=least_squares(lambda p:np.concatenate([project(p,r)-land[r['sample']][ix] for r in fit]),p0,max_nfev=150)
        points.append(result.x)
        for r in rr:
            if not r.get('camera_copy'):continue
            error=np.linalg.norm(project(result.x,r)-land[r['sample']][ix])
            errors.append(dict(sample=r['sample'],endpoint='AB'[ix],role=r['role'],error_px=float(error)))
    f=[e['error_px']**2 for e in errors if e['role']=='registration_fit'];h=[e['error_px']**2 for e in errors if e['role']=='registration_holdout']
    return dict(fit_euclidean_rms_px=float(np.sqrt(np.mean(f))),holdout_euclidean_rms_px=float(np.sqrt(np.mean(h))),
        endpoint_distance_m=float(np.linalg.norm(points[0]-points[1])),controls=errors)
scan=[]
for cat in sorted({r['category'] for r in rows}):
    rr=[r for r in rows if r['category']==cat]
    for mode,K in Ks.items():scan.append(dict(category=cat,mode=mode,focal_multiplier=1.,**endpoint_control(rr,K)))
    for factor in np.linspace(.4,2,33):
        K=Ks['linear'].copy();K[0,0]*=factor;K[1,1]*=factor
        scan.append(dict(category=cat,mode='linear_focal_sweep',focal_multiplier=float(factor),**endpoint_control(rr,K)))
save(OUT/'intrinsic-sensitivity.json',scan)
def skew(t):
    x,y,z=t;return np.array([[0,-z,y],[z,0,-x],[-y,x,0]])
def fundamental(a,b,K):
    relative=np.linalg.inv(pose(b))@pose(a);ik=np.linalg.inv(K)
    return ik.T@skew(relative[:3,3])@relative[:3,:3]@ik
def sampson(F,a,b):
    ah=np.column_stack([a,np.ones(len(a))]);bh=np.column_stack([b,np.ones(len(b))]);fa=ah@F.T;fb=bh@F
    return np.abs(np.sum(bh*fa,axis=1))/np.sqrt(np.maximum(np.sum(fa[:,:2]**2,axis=1)+np.sum(fb[:,:2]**2,axis=1),1e-20))
sift=cv2.SIFT_create(nfeatures=2500);matcher=cv2.BFMatcher();features={};pairs=[]
for r in rows:
    if r.get('camera_copy'):
        image=cv2.imdecode(np.frombuffer(Path(r['camera_copy']).read_bytes(),dtype=np.uint8),cv2.IMREAD_GRAYSCALE);features[r['sample']]=(*sift.detectAndCompute(image,None),image)
for rec in sorted({r['recording'] for r in rows}):
    rr=[r for r in rows if r['recording']==rec and r.get('camera_copy')]
    for a,b in itertools.combinations(rr,2):
        ka,da,ia=features[a['sample']];kb,db,ib=features[b['sample']]
        ab=matcher.knnMatch(da,db,k=2);ba=matcher.knnMatch(db,da,k=2)
        back={m.queryIdx:m.trainIdx for m,n in ba if m.distance<.7*n.distance}
        good=[m for m,n in ab if m.distance<.7*n.distance and back.get(m.trainIdx)==m.queryIdx]
        pa=np.float32([ka[m.queryIdx].pt for m in good]);pb=np.float32([kb[m.trainIdx].pt for m in good])
        entry=dict(recording=rec,sample_a=a['sample'],sample_b=b['sample'],ratio_mutual_matches=len(good))
        if len(good)<12:pairs.append(entry);continue
        cv2.setRNGSeed(0);F,mask=cv2.findFundamentalMat(pa,pb,cv2.FM_RANSAC,1.5,.999,10000)
        if F is None or F.shape!=(3,3):pairs.append(entry);continue
        keep=mask.ravel().astype(bool);x,y=pa[keep],pb[keep];entry['ransac_inliers']=int(keep.sum())
        if len(x)<8:pairs.append(entry);continue
        # Convex hull coverage flags concentrated or near-planar feature support.
        entry['image_a_hull_area_fraction']=float(cv2.contourArea(cv2.convexHull(x))/(640*360))
        entry['image_b_hull_area_fraction']=float(cv2.contourArea(cv2.convexHull(y))/(640*360))
        estimated=sampson(F,x,y);entry['image_F_median_sampson_px']=float(np.median(estimated))
        entry['source_pose_modes']={mode:dict(median_sampson_px=float(np.median(sampson(fundamental(a,b,K),x,y))),p90_sampson_px=float(np.percentile(sampson(fundamental(a,b,K),x,y),90))) for mode,K in Ks.items()}
        entry['linear_focal_sweep']=[dict(factor=float(f),median_sampson_px=float(np.median(sampson(fundamental(a,b,np.array([[Ks['linear'][0,0]*f,0,Ks['linear'][0,2]],[0,Ks['linear'][1,1]*f,Ks['linear'][1,2]],[0,0,1]])),x,y)))) for f in np.linspace(.4,2,33)]
        good_kept=[m for m,k in zip(good,keep) if k]
        vis=cv2.drawMatches(ia,ka,ib,kb,good_kept,None,flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
        dest=OUT/'matches'/f"{a['sample']}__{b['sample']}.jpg";dest.parent.mkdir(exist_ok=True)
        dest.write_bytes(cv2.imencode('.jpg',vis)[1].tobytes())
        entry['matched_points_a']=x.tolist();entry['matched_points_b']=y.tolist();entry['image_F']=F.tolist()
        pairs.append(entry)
save(OUT/'epipolar-controls.json',pairs)
assert all(sha(Path(p))==h for p,h in small.items())
assert all(Path(p).stat().st_size==x['bytes'] and Path(p).stat().st_mtime_ns==x['mtime_ns'] for p,x in video_identity.items())
save(OUT/'verification.json',dict(input_hashes=small,input_hashes_unchanged=True,video_stat_identity=video_identity,video_stat_unchanged=True,
    source_samples=len(source),test_access=False,training_runs=0,new_gt=0,script_sha256=sha(Path(__file__))))
for cat in sorted({r['category'] for r in rows}):
    ss=[s for s in scan if s['category']==cat and s['mode']=='linear_focal_sweep'];base=next(s for s in scan if s['category']==cat and s['mode']=='linear')
    best=min(ss,key=lambda x:x['fit_euclidean_rms_px'])
    print(cat,'baseline',base['fit_euclidean_rms_px'],base['holdout_euclidean_rms_px'],'fit-min factor',best['focal_multiplier'],best['fit_euclidean_rms_px'],best['holdout_euclidean_rms_px'])
for p in pairs:
    if 'source_pose_modes' in p:print(p['sample_a'],p['sample_b'],'matches',p['ransac_inliers'],'imageF',round(p['image_F_median_sampson_px'],2),'source',round(p['source_pose_modes']['linear']['median_sampson_px'],2),'bestf',min(p['linear_focal_sweep'],key=lambda x:x['median_sampson_px']))
