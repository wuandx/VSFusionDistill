"""Local silhouette-constrained similarity registration; diagnostic outputs only."""
from pathlib import Path
import sys,json,csv,hashlib,subprocess,math,html
sys.dont_write_bytecode=True
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
import cv2,yaml
from PIL import Image,ImageDraw
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation
from scipy.optimize import least_squares
OUT=ROOT/'DataSet/sonar_independent_registration'
ASSETS=ROOT/'related_work/sonar-projection-audit-assets/data_export_3dmodels/3d_models'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def repo_state():
    repo=str(ROOT.parent/'声呐目标检测/code/VSFusionDistill')
    return {k:subprocess.check_output(['git','-C',repo,*a]).decode().strip() for k,a in [('head',['rev-parse','HEAD']),('status',['status','--porcelain'])]}
def tf(entry):
    t=np.eye(4);t[:3,:3]=Rotation.from_quat([entry['rotation'][k] for k in ['x','y','z','w']]).as_matrix()
    t[:3,3]=[entry['translation'][k] for k in 'xyz'];return t

if (OUT/'results.json').exists():raise RuntimeError('Preserve previous result; use a new named run for changes')
before_repo=repo_state()
rows=json.loads((OUT/'selection.json').read_text(encoding='utf-8'))['samples']
contours=json.loads((OUT/'contours.json').read_text(encoding='utf-8'))['points']
manifest=json.loads((ROOT/'DataSet/camera_temporal_all/manifest-resolved.json').read_text(encoding='utf-8'))
allowed={r['sample']:r for r in manifest['items'] if r.get('paired_id') and r.get('paired_role') in ['train','val','val_id']}
for r in rows:assert r['sample'] in allowed
vjson=json.loads((ROOT/'DataSet/sonar_model_registration_consistency/calibration-versions.json').read_text(encoding='utf-8'))
tracked={OUT/'contours.json',OUT/'selection.json',Path(__file__),ROOT/'experiment/sonar-independent-registration-plan.md'}
for r in rows:
    tracked.update(Path(r[k]) for k in ['raw_sonar_source','gantry_source','meta_source'])
    if r.get('camera_copy'):
        tracked.update([Path(r['camera_source']),Path(r['camera_copy'])]);assert sha(r['camera_source'])==r['camera_sha256']==sha(r['camera_copy'])
for v in vjson['versions'].values():tracked.add(Path(v['source']))
for name in ['100lbs','incindiary','mortar_shell']:tracked.add(ASSETS/(name+'.obj'))
before={str(p):sha(p) for p in tracked}
save(OUT/'input-snapshot-before.json',dict(sha256=before,repo=before_repo))
K=np.array([[1473.04513/3,0,969.389055/3],[0,1478.33421/3,540.775107/3],[0,0,1]])
angles=np.arange(36)*2*np.pi/36;directions=np.stack([np.cos(angles),np.sin(angles)],axis=1)
rawmeta={}
for r in rows:
    if r['recording'] not in rawmeta:
        with Path(r['meta_source']).open(encoding='utf-8',newline='') as f:m={int(x['FrameIndex']):x for x in csv.DictReader(f)}
        with Path(r['gantry_source']).open(encoding='utf-8',newline='') as f:g={int(x['aris_frame_idx']):x for x in csv.DictReader(f)}
        rawmeta[r['recording']]=(m,g)
def chain(row,static):
    m,g=rawmeta[row['recording']];m=m[row['aris_frame']];g=g[row['aris_frame']]
    wa=np.eye(4);wa[:3,3]=[float(g[k]) for k in 'xyz'];wa[:3,3]+=static['setup/ar3'][:3,3]
    wa[:3,:3]=static['setup/ar3'][:3,:3]@Rotation.from_euler('xyz',[float(m[k]) for k in ['SonarRoll','SonarTilt','SonarPan']],degrees=True).as_matrix()
    wc=wa@static['setup/gopro_mounting_hole']@static['setup/gopro_mounting_axis']@static['setup/camera']
    ws=wa@static['setup/aris']@static['setup/sonar']
    return np.linalg.inv(wc),np.linalg.inv(ws),m
def project(points,cam):
    p=points@cam[:3,:3].T+cam[:3,3]
    uv=p@K.T
    return uv[:,:2]/np.maximum(uv[:,2:3],.05),p[:,2]
def support(points):return np.max(points@directions.T,axis=0)
def hull(points):
    points=np.asarray(points,dtype=np.float32)
    return cv2.convexHull(points).reshape(-1,2)
def iou(a,b):
    ha,hb=hull(a),hull(b)
    inter,_=cv2.intersectConvexConvex(ha,hb)
    return float(inter/max(cv2.contourArea(ha)+cv2.contourArea(hb)-inter,1e-9))
models={'100lbs_aircraft_bomb':('100lbs','target/100lbs',.737),
        'incindiary_grenade':('incindiary','target/incendiary',.442),
        'mortar_shell':('mortar_shell','target/mortar_shell',.580)}
outputs=[];overlays=[]
for category,(model,target,length) in models.items():
    vertices=np.array([[float(x) for x in line.split()[1:4]] for line in (ASSETS/(model+'.obj')).read_text(encoding='utf-8').splitlines() if line.startswith('v ')])
    mean=vertices.mean(0);_,_,axes=np.linalg.svd(vertices-mean,full_matrices=False)
    if np.linalg.det(axes)<0:axes[2]*=-1
    local=vertices-mean;sample=local[ConvexHull(local).vertices]
    nominal_scale=length/np.ptp(local@axes[0])
    rr=[r for r in rows if r['category']==category]
    for version in ['release_current','notebook_20240723']:
        static={k:np.array(v) for k,v in vjson['versions'][version]['parent_from_child_matrices'].items()}
        target_world=static[target]
        assert np.allclose(target_world[:3,:3],np.eye(3))
        pose={r['sample']:chain(r,static) for r in rr}
        fit=[r for r in rr if r['role']=='registration_fit' and r.get('camera_copy')]
        fixed_support=[support(np.array(contours[r['sample']])) for r in fit]
        def points(x,base):
            rot=Rotation.from_rotvec(x[1:4]).as_matrix()@base
            return (sample@rot.T)*(nominal_scale*np.exp(x[0]))+target_world[:3,3]+x[4:7]
        def residual(x,base):
            p=points(x,base);errors=[]
            for r,truth in zip(fit,fixed_support):
                uv,z=project(p,pose[r['sample']][0]);errors.extend(support(uv)-truth)
                # Fixed extra term prohibits invalid depth without changing residual dimension.
                errors.append(min(float(z.min())-.05,0)*1000)
            return np.array(errors)
        starts=[];solutions=[]
        for flip in [0,1]:
            for roll in [0,90,180,270]:
                base=Rotation.from_euler('z',180*flip,degrees=True).as_matrix()@Rotation.from_euler('x',roll,degrees=True).as_matrix()@axes
                low=np.array([-np.log(2),-np.pi,-np.pi,-np.pi,-.5,-.5,-.5]);high=-low
                fit_result=least_squares(residual,np.zeros(7),args=(base,),bounds=(low,high),max_nfev=400,ftol=1e-9,xtol=1e-9,gtol=1e-8)
                x=fit_result.x;rot=Rotation.from_rotvec(x[1:4]).as_matrix()@base
                scale=nominal_scale*np.exp(x[0]);local_t=x[4:7]-scale*rot@mean
                sim=np.eye(4);sim[:3,:3]=scale*rot;sim[:3,3]=local_t
                rms=float(np.sqrt(np.mean(fit_result.fun**2)))
                singular=np.linalg.svd(fit_result.jac,compute_uv=False)
                start=dict(flip=flip,roll_init_deg=roll,rms_with_depth_penalty_px=rms,nfev=int(fit_result.nfev),
                    converged=bool(fit_result.success),message=fit_result.message,scale_m_per_obj_unit=float(scale),
                    rotation_target_from_mesh=rot.tolist(),translation_target_from_mesh_m=local_t.tolist(),
                    mesh_to_target_similarity=sim.tolist(),center_offset_from_target_m=x[4:7].tolist(),
                    parameter_bounds_hit=bool(np.any(np.minimum(x-low,high-x)<1e-4)),
                    jacobian_singular_values=singular.tolist(),jacobian_condition_number=float(singular[0]/max(singular[-1],1e-15)))
                starts.append(start);solutions.append((fit_result,base))
        best_index=int(np.argmin([s['rms_with_depth_penalty_px'] for s in starts]));best=starts[best_index]
        result,base=solutions[best_index];p=points(result.x,base)
        near=[]
        bestrot=np.array(best['rotation_target_from_mesh'])
        for s in starts:
            if s['rms_with_depth_penalty_px']<=best['rms_with_depth_penalty_px']+max(.5,.1*best['rms_with_depth_penalty_px']):
                angle=float(np.rad2deg(Rotation.from_matrix(np.array(s['rotation_target_from_mesh'])@bestrot.T).magnitude()))
                near.append(dict(flip=s['flip'],roll_init_deg=s['roll_init_deg'],rotation_difference_deg=angle,rms_px=s['rms_with_depth_penalty_px']))
        controls=[]
        for row in rr:
            cam,sonar,meta=pose[row['sample']]
            uv,z=project(p,cam)
            control=dict(sample=row['sample'],role=row['role'],camera_available=bool(row.get('camera_copy')))
            if row.get('camera_copy'):
                truth=np.array(contours[row['sample']]);error=support(uv)-support(truth)
                control.update(support_rms_px=float(np.sqrt(np.mean(error**2))),convex_hull_iou=iou(uv,truth),minimum_depth_m=float(z.min()))
            # setup/sonar uses optical-style axes after the static cyclic permutation.
            sp=p@sonar[:3,:3].T+sonar[:3,3]
            rng=np.linalg.norm(sp,axis=1);bearing=np.rad2deg(np.arctan2(sp[:,0],sp[:,2]));elevation=np.rad2deg(np.arctan2(sp[:,1],np.hypot(sp[:,0],sp[:,2])))
            dr=float(meta['SamplePeriod'])*1e-6*float(meta['SoundSpeed'])/2
            pixel_row=(rng-float(meta['WindowStart']))/dr
            control['sonar']=dict(range_m_min_max=[float(rng.min()),float(rng.max())],bearing_deg_min_max=[float(bearing.min()),float(bearing.max())],
                elevation_deg_min_max=[float(elevation.min()),float(elevation.max())],assumed_vertical_aperture_deg=14,
                fraction_points_within_assumed_vertical_aperture=float(np.mean(np.abs(elevation)<=7)),raw_height=int(meta['SamplesPerBeam']),
                predicted_row_min_max=[float(pixel_row.min()),float(pixel_row.max())])
            controls.append(control)
            if version=='release_current':
                img=Image.new('RGB',(1152,420),'white');draw=ImageDraw.Draw(img)
                draw.text((5,5),row['sample']+' | '+row['role']+' | local candidate, NOT GT',fill='black')
                if row.get('camera_copy'):
                    img.paste(Image.open(row['camera_copy']),(0,35))
                    a=[tuple(x) for x in np.array(contours[row['sample']])+[0,35]];b=[tuple(x) for x in hull(uv)+[0,35]]
                    draw.line(a+[a[0]],fill=(255,65,100),width=2);draw.line(b+[b[0]],fill=(0,255,150),width=2)
                    draw.text((5,400),f"camera support RMS {control['support_rms_px']:.2f}px | hull IoU {control['convex_hull_iou']:.3f}",fill='black')
                else:draw.text((10,100),'SD MISSING - deferred camera control',fill='black')
                raw=np.array(Image.open(row['raw_sonar_source']))
                h,w=raw.shape
                # Display raw first 300 range bins with fixed 4x horizontal, 1x vertical scale.
                # Full source remains untouched; crop and row-origin are explicit.
                disp=Image.fromarray(raw[:min(h,360)]).convert('RGB').resize((512,min(h,360)))
                img.paste(disp,(640,35))
                beam_module=ROOT/'related_work/uxo-upstream-history/scripts/common/aris_definitions.py'
                import importlib.util
                spec=importlib.util.spec_from_file_location('upstream_aris_table',beam_module);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
                tracked.add(beam_module)
                centers=np.array(module.BeamWidthsAris3000_128)[:,0]
                cols=np.interp(bearing,centers,np.arange(128))
                inside=(bearing>=centers.min())&(bearing<=centers.max())&(pixel_row>=0)&(pixel_row<min(h,360))
                # sign remains diagnostic: positive bearing +x uses ascending source beam table.
                for i in np.nonzero(inside)[0]:
                    color=(0,255,150) if abs(elevation[i])<=7 else (255,180,0)
                    draw.point((640+int(cols[i]*4),35+int(pixel_row[i])),fill=color)
                draw.text((645,400),'raw sonar rows 0:360 | green within assumed +/-7deg; orange outside',fill='black')
                dest=OUT/'overlays'/f"{row['sample']}.jpg";dest.parent.mkdir(exist_ok=True);img.save(dest,quality=96)
                overlays.append(dest)
        hold=[c for c in controls if c['role']=='registration_holdout' and c['camera_available']]
        rmsfit=[c['support_rms_px'] for c in controls if c['role']=='registration_fit' and c['camera_available']]
        fit_pass=max(rmsfit)<=4
        hold_pass=all(c['support_rms_px']<=8 and c['convex_hull_iou']>=.75 for c in hold) and bool(hold)
        ambiguous=any(n['rotation_difference_deg']>10 for n in near)
        output=dict(category=category,model=model,version=version,method='local assistant-annotated SD silhouette similarity registration',
            intrinsic_assumption='public linear K/3, zero distortion; unresolved imaging model',
            nominal_scale_initialization=nominal_scale,best_start=best,all_starts=starts,near_optimal_starts=near,
            fit_threshold_passed=fit_pass,camera_holdout_threshold_passed=hold_pass,
            rotation_multisolution=ambiguous,local_camera_candidate_passed=bool(fit_pass and hold_pass and not ambiguous and not best['parameter_bounds_hit'] and best['converged']),
            approved_for_sonar_gt=False,controls=controls)
        outputs.append(output)
        save(OUT/(model+'-'+version+'.json'),output)
        print(json.dumps(dict(category=category,version=version,fit_rms=rmsfit,holdout=[(c['sample'],c['support_rms_px'],c['convex_hull_iou']) for c in hold],ambiguous=ambiguous,bound=best['parameter_bounds_hit']),ensure_ascii=False),flush=True)
save(OUT/'results.json',dict(status='diagnostic registration candidates; not official transforms or approved GT',
    K_sd=K.tolist(),annotation_sha256=sha(OUT/'contours.json'),outputs=outputs))
beam_module=ROOT/'related_work/uxo-upstream-history/scripts/common/aris_definitions.py'
after={p:sha(Path(p)) for p in before};assert before==after
assert before_repo==repo_state()
save(OUT/'verification.json',dict(unchanged_input_files=len(before),sha256_before=before,input_hashes_unchanged=True,
    original_repo_before=before_repo,original_repo_after=repo_state(),fixed_identities=len(rows),camera_images=17,
    registration_fit_images=6,registration_holdout_camera_images=11,missing_sd_retained=1,
    test_access=False,new_training_gt=0,training_runs=0,new_teacher_splits=0,
    beam_table_sha256=sha(beam_module),script_sha256=sha(Path(__file__))))
body=''.join('<p>'+html.escape(p.stem)+'</p><img loading="lazy" src="overlays/'+p.name+'">' for p in overlays)
(OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Independent registration diagnostics</title><style>body{font:16px sans-serif;background:#eee}img{max-width:100%}</style><h1>我方独立注册诊断（未准入GT）</h1><p>粉红：独立目视轮廓；绿：拟合模型凸包。每类首录音前两帧拟合；其余为开发检查。SD原坐标。Sonar只显示前360行，未拟合回波。主版本为当前标定。</p>'+body,encoding='utf-8')
