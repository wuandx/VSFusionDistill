"""Named beam-sign candidate; consumes the original frozen mesh transforms."""
from pathlib import Path
import sys,json,csv,hashlib,importlib.util,subprocess,math
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np,cv2
from scipy.spatial.transform import Rotation
from scipy.interpolate import interp1d
from PIL import Image,ImageDraw
BASE=ROOT/'DataSet/sonar_fixed_mesh'
OUT=ROOT/'DataSet/sonar_fixed_mesh_beam_sign';OUT.mkdir(exist_ok=True)
PRIOR=ROOT/'DataSet/sonar_independent_registration'
ASSETS=ROOT/'related_work/sonar-projection-audit-assets/data_export_3dmodels/3d_models'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def table(p,key):
    with p.open(encoding='utf-8',newline='') as f:return {int(x[key]):x for x in csv.DictReader(f)}
def bbox(p,pad=0):
    if not len(p):return None
    return [float(p[:,0].min()-pad),float(p[:,1].min()-pad),float(p[:,0].max()+pad),float(p[:,1].max()+pad)]
def clip(box,w,h):
    if box is None:return None
    x0,y0,x1,y1=box;x0=max(0.,x0);y0=max(0.,y0);x1=min(float(w),x1);y1=min(float(h),y1)
    return [x0,y0,x1,y1] if x1>x0 and y1>y0 else None
if (OUT/'results.json').exists():raise RuntimeError('Preserve existing run; use a new name')
rows=read(PRIOR/'selection.json')['samples'];assert len(rows)==18
manifest_path=ROOT/'DataSet/camera_temporal_all/manifest-resolved.json'
allowed={x['sample']:x for x in read(manifest_path)['items'] if x.get('paired_role') in ['train','val','val_id']}
assert all(r['sample'] in allowed and allowed[r['sample']]['aris_frame']==r['aris_frame'] for r in rows)
cal_path=ROOT/'DataSet/sonar_model_registration_consistency/calibration-versions.json'
statics={k:np.array(v) for k,v in read(cal_path)['versions']['release_current']['parent_from_child_matrices'].items()}
beam_path=ROOT/'related_work/uxo-upstream-history/scripts/common/aris_definitions.py'
spec=importlib.util.spec_from_file_location('beam_table',beam_path);bm=importlib.util.module_from_spec(spec);spec.loader.exec_module(bm)
registry_path=ROOT/'DataSet/sonar_model_registration_consistency/mesh-registration.json'
reg=read(registry_path)['models']
paths={PRIOR/'selection.json',manifest_path,cal_path,beam_path,registry_path,ROOT/'experiment/sonar-fixed-mesh-beam-sign-plan.md',BASE/'qa-before-projection.json',BASE/'fixed-mesh-transforms.json',BASE/'results.json',Path(__file__),ROOT/'related_work/model-registration-sources/historical-README.md'}
paths.update(Path(r[k]) for r in rows for k in ['raw_sonar_source','gantry_source','meta_source'])
paths.update(Path(m['source']) for m in reg)
before={str(p):sha(p) for p in paths};save(OUT/'inputs-before.json',before)
frozen=read(BASE/'fixed-mesh-transforms.json')
models=frozen['models'];clouds={};worlds={}
for name,info in models.items():
    vs=[];faces=[]
    for line in Path(info['source']).read_text(encoding='utf-8').splitlines():
        s=line.split()
        if not s:continue
        if s[0]=='v':vs.append([float(x) for x in s[1:4]])
        elif s[0]=='f':
            ids=[int(x.split('/')[0]) for x in s[1:]];ids=[i-1 if i>0 else len(vs)+i for i in ids]
            faces.extend([[ids[0],ids[i],ids[i+1]] for i in range(1,len(ids)-1)])
    vs=np.array(vs);faces=np.array(faces,dtype=int)
    scale=info['scale_m_per_obj_unit'];R=np.array(info['rotation_target_from_mesh']);t=np.array(info['translation_target_from_mesh_m'])
    target=scale*(vs@R.T)+t
    tri=target[faces]
    dense=np.concatenate([target,tri.mean(axis=1),(tri[:,0]+tri[:,1])/2,(tri[:,1]+tri[:,2])/2,(tri[:,2]+tri[:,0])/2])
    wt=np.array(info['world_from_target'])
    clouds[name]=dense;worlds[name]=dense@wt[:3,:3].T+wt[:3,3]
(OUT/'fixed-mesh-transforms.json').write_bytes((BASE/'fixed-mesh-transforms.json').read_bytes())
frozen_sha=sha(OUT/'fixed-mesh-transforms.json')
assert frozen_sha=='31e18b860fbbb6ac489156d9d2f4f3ffa57953301e95ab35f1e9fa0bcc8722c7'
cache={};outputs=[]
catmap={'100lbs_aircraft_bomb':'100lbs','incindiary_grenade':'incindiary','mortar_shell':'mortar_shell'}
for row in rows:
    rec=row['recording'];model=catmap[row['category']]
    if rec not in cache:cache[rec]=(table(Path(row['meta_source']),'FrameIndex'),table(Path(row['gantry_source']),'aris_frame_idx'))
    mm,gg=cache[rec];m=mm[row['aris_frame']];g=gg[row['aris_frame']]
    assert int(m['FrameTime'])==allowed[row['sample']]['aris_time_us']
    wa=np.eye(4);wa[:3,:3]=statics['setup/ar3'][:3,:3]@Rotation.from_euler('xyz',[float(m[k]) for k in ['SonarRoll','SonarTilt','SonarPan']],degrees=True).as_matrix()
    wa[:3,3]=np.array([float(g[k]) for k in 'xyz'])+statics['setup/ar3'][:3,3]
    ws=wa@statics['setup/aris']@statics['setup/sonar'];sw=np.linalg.inv(ws)
    p=worlds[model]@sw[:3,:3].T+sw[:3,3]
    rng=np.linalg.norm(p,axis=1);az=-np.rad2deg(np.arctan2(p[:,0],p[:,2]));el=np.rad2deg(np.arctan2(p[:,1],np.hypot(p[:,0],p[:,2])))
    assert np.isfinite(p).all()
    raw=cv2.imdecode(np.frombuffer(Path(row['raw_sonar_source']).read_bytes(),np.uint8),cv2.IMREAD_UNCHANGED);h,w=raw.shape
    assert h==int(m['SamplesPerBeam']) and w==bm.get_beamcount_from_pingmode(int(m['PingMode']))
    beams=np.array(bm.BeamWidthsAris3000_128 if w==128 else bm.BeamWidthsAris3000_64)
    angleknots=np.r_[beams[0,1],beams[:,0],beams[-1,2]];colknots=np.r_[0.,np.arange(w)+.5,float(w)]
    azcol=interp1d(angleknots,colknots,bounds_error=False,fill_value='extrapolate')
    dr=float(m['SamplePeriod'])*1e-6*float(m['SoundSpeed'])/2
    r0=float(m['SampleStartDelay'])*1e-6*float(m['SoundSpeed'])/2;r1=r0+h*dr
    pixel=np.c_[azcol(az),(rng-r0)/dr]
    horizontal=(p[:,2]>0)&(az>=beams[0,1])&(az<=beams[-1,2])&(rng>=r0)&(rng<=r1)
    visible=horizontal&(np.abs(el)<=7)
    fullbox=bbox(pixel,1);intersect=clip(fullbox,w,h)
    visbox=clip(bbox(pixel[visible],1),w,h)
    res=200.;H=math.ceil(r1*res);W=math.ceil(2*r1*np.tan(np.deg2rad(max(abs(beams[0,1]),abs(beams[-1,2]))))*res)
    # Same sign as public polar2 final horizontal flip: increasing beam angle lies left.
    yy,xx=np.mgrid[:H,:W];xx=(W/2-xx-.5)/res;zz=(H-yy-.5)/res
    rr=np.hypot(xx,zz);aa=np.rad2deg(np.arctan2(xx,zz))
    mapx=(azcol(aa)-.5).astype(np.float32);mapy=((rr-r0)/dr-.5).astype(np.float32)
    fan=cv2.remap(raw,mapx,mapy,cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT)
    valid=(rr>=r0)&(rr<=r1)&(aa>=beams[0,1])&(aa<=beams[-1,2]);fan[~valid]=0
    fanpoints=np.c_[W/2-rng*np.sin(np.deg2rad(az))*res,H-rng*np.cos(np.deg2rad(az))*res]
    fanvis=clip(bbox(fanpoints[visible],1),W,H)
    rawrgb=cv2.cvtColor(raw,cv2.COLOR_GRAY2RGB);fanrgb=cv2.cvtColor(fan,cv2.COLOR_GRAY2RGB)
    def drawpanel(base,pts,box,allbox):
        a=base.copy()
        # All no-elevation-gate geometry in amber, assumed visible samples green.
        ids=np.nonzero(horizontal)[0][::max(1,int(horizontal.sum()/10000))]
        for i in ids:
            u,v=pts[i]
            if 0<=u<a.shape[1] and 0<=v<a.shape[0]:a[int(v),int(u)]=[255,160,0]
        ids=np.nonzero(visible)[0][::max(1,int(visible.sum()/10000))]
        for i in ids:
            u,v=pts[i]
            if 0<=u<a.shape[1] and 0<=v<a.shape[0]:a[int(v),int(u)]=[0,255,120]
        if allbox:
            x0,y0,x1,y1=allbox;cv2.rectangle(a,(int(x0),int(y0)),(min(a.shape[1]-1,int(x1)),min(a.shape[0]-1,int(y1))),(255,160,0),1)
        if box:
            x0,y0,x1,y1=box;cv2.rectangle(a,(int(x0),int(y0)),(min(a.shape[1]-1,int(x1)),min(a.shape[0]-1,int(y1))),(0,255,120),1)
        return a
    overlay=drawpanel(rawrgb,pixel,visbox,intersect)
    foverlay=drawpanel(fanrgb,fanpoints,fanvis,clip(bbox(fanpoints[horizontal],1),W,H))
    dest=OUT/'frames';dest.mkdir(exist_ok=True)
    for suffix,im in [('raw',rawrgb),('raw-overlay',overlay),('fan',fanrgb),('fan-overlay',foverlay)]:
        Image.fromarray(im).save(dest/(row['sample']+'-'+suffix+'.png'))
    # Full raw height retained; display-only scaling explicit in viewer.
    canvas=Image.new('RGB',(1300,740),'white');draw=ImageDraw.Draw(canvas)
    draw.text((8,7),row['sample']+' | FIXED MESH HYPOTHESIS, NOT GT',fill='black')
    panels=[(rawrgb,0,384),(overlay,400,384),(foverlay,800,490)]
    for im,x,width in panels:
        pic=Image.fromarray(im).resize((width,650));canvas.paste(pic,(x,40))
    draw.text((5,24),'original range x beam',fill='black');draw.text((405,24),'raw overlay; range increases down',fill='black');draw.text((805,24),'fan overlay; range increases up',fill='black')
    draw.text((8,698),'orange: no elevation gate; green: assumed +/-7deg. All panels full extent; display scale differs.',fill='black')
    canvas.save(dest/(row['sample']+'-comparison.jpg'),quality=96)
    out=dict(sample=row['sample'],recording=rec,category=row['category'],model=model,historical_role=allowed[row['sample']]['paired_role'],prior_geometry_role=row['role'],raw_sonar_source=row['raw_sonar_source'],raw_shape_hw=[h,w],gantry_xyz_m=[float(g[k]) for k in 'xyz'],aris_roll_tilt_pan_deg=[float(m[k]) for k in ['SonarRoll','SonarTilt','SonarPan']],frame_time_us=int(m['FrameTime']),world_from_ar3=wa.tolist(),world_from_sonar=ws.tolist(),sonar_from_world=sw.tolist(),range_bin_m=dr,range_start_m=r0,window_start_field_m=float(m['WindowStart']),range_start_field_difference_m=r0-float(m['WindowStart']),range_end_m=r1,beam_azimuth_extent_deg=[float(beams[0,1]),float(beams[-1,2])],mesh_range_m=[float(rng.min()),float(rng.max())],mesh_azimuth_deg=[float(az.min()),float(az.max())],mesh_elevation_deg=[float(el.min()),float(el.max())],surface_sample_count=len(p),fraction_in_range_beam=float(horizontal.mean()),fraction_visible_assumed_7deg=float(visible.mean()),fraction_visible_assumed_7_5deg=float((horizontal&(np.abs(el)<=7.5)).mean()),full_surface_raw_bbox_padded_xyxy=fullbox,full_surface_raw_bbox_intersection_xyxy=intersect,visible_raw_bbox_padded_clipped_xyxy=visbox,visible_fan_bbox_padded_clipped_xyxy=fanvis,range_beam_truncated=bool(not horizontal.all()),vertical_gate_removes_points=bool(np.any(horizontal&~visible)),status='candidate_visible' if visible.any() else 'no_visible_surface_under_assumptions',fan_geometry=dict(width=W,height=H,pixels_per_m=res,u_formula='W/2 - range*sin(azimuth)*200',v_formula='H - range*cos(azimuth)*200',interpolation='nearest, using source bin centers; display only, not byte-identical public polygon rasterizer'),approved_for_training_gt=False)
    outputs.append(out)
    print(row['sample'],out['status'],'visible',round(visible.mean(),3),'bbox',visbox,flush=True)
assert sha(OUT/'fixed-mesh-transforms.json')==frozen_sha
assert all(sha(Path(p))==h for p,h in before.items())
save(OUT/'results.json',dict(run='sonar_fixed_mesh_beam_sign',beam_azimuth_formula='-degrees(atan2(sonar_x,sonar_z))',revision_of='sonar_fixed_mesh',status='single beam-sign candidate; awaiting visual QA; not training GT',fixed_transform_sha256=frozen_sha,outputs=outputs))
save(OUT/'generation-verification.json',dict(input_hashes=before,inputs_unchanged=True,fixed_transforms_unchanged=True,identities=len(outputs),models=3,echo_fit_runs=0,camera_parameters_used=False,new_training_gt=0,test_access=False,training_runs=0))
