"""Fixed bomb registration from frozen semantic endpoint-region hypotheses."""
from pathlib import Path
import sys,json,hashlib
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np,cv2
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from PIL import Image,ImageDraw
from fit_mortar_fixed_registration import read_obj
from check_official_sonar_coordinates import load_beam_tables,linear_extrapolate

OUT=ROOT/'DataSet/sonar_endpoint_pan_control';tracked={}
def read(p):
    p=Path(p);tracked[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text('utf-8-sig'))
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def corrected_frame(frame,delta):
    f=dict(frame);wa=np.array(frame['world_from_ar3']);roll,tilt,pan=frame['aris_roll_tilt_pan_deg']
    parent=np.diag([-1.,1.,-1.]);wa[:3,:3]=parent@Rotation.from_euler('xyz',[roll,tilt,pan+delta],degrees=True).as_matrix()
    original_wa=np.array(frame['world_from_ar3']);static=np.linalg.inv(original_wa)@np.array(frame['world_from_sonar']);f['world_from_sonar']=(wa@static).tolist();return f

def matrix(q):
    T=np.eye(4);T[:3,:3]=Rotation.from_rotvec(q[3:6]).as_matrix();T[:3,3]=q[:3];return T
def transform(p,T):return p@T[:3,:3].T+T[:3,3]
def uv_project(p,frame):
    p=transform(p,np.linalg.inv(np.array(frame['world_from_sonar'])))
    r=np.linalg.norm(p,axis=1);a=-np.degrees(np.arctan2(p[:,0],p[:,2]));e=np.degrees(np.arctan2(p[:,1],np.hypot(p[:,0],p[:,2])))
    table=load_beam_tables()[frame['raw_shape_hw'][1]]
    knots=np.r_[np.column_stack([table[:,1],table[:,0]]).ravel(),table[-1,2]]
    u=linear_extrapolate(a,knots,np.arange(2*len(table)+1)/2);v=(r-frame['range_start_m'])/frame['range_bin_m']
    return np.c_[u,v],e,p[:,2]
def violation(x,lo,hi):return np.maximum(lo-x,0)+np.minimum(hi-x,0)
def main():
    if (OUT/'freeze-model.json').exists():raise RuntimeError('Preserve frozen run')
    OUT.mkdir(exist_ok=True)
    source=read(ROOT/'DataSet/sonar_fixed_mesh/results.json');frames={f['sample']:f for f in source['outputs'] if f['model']=='100lbs'}
    info=read(ROOT/'DataSet/sonar_fixed_mesh/fixed-mesh-transforms.json')['models']['100lbs']
    pts,faces=read_obj(info['source']);tracked[info['source']]=hashlib.sha256(Path(info['source']).read_bytes()).hexdigest()
    S=np.array(info['mesh_to_target_similarity']);p=transform(pts,S);lo,hi=p[:,0].min(),p[:,0].max();span=hi-lo
    ends=[]
    for mask,x in [(p[:,0]>=hi-.01*span,hi),(p[:,0]<=lo+.01*span,lo)]:
        section=p[mask];ends.append([x,*((section[:,1:].min(0)+section[:,1:].max(0))/2)])
    ends=np.array(ends) # A round nose +x; B neck -x, visually checked on OBJ previews.
    annotations={'2023-09-20_171105_0622':[[8,245,24,295],[96,132,116,175]],'2023-09-20_171105_1336':[[-10000,90,14,130],[88,200,104,265]]}
    ann=dict(author='assistant; tentative semantic echo endpoints, not expert GT',fit_regions_raw_xyxy=annotations,model_anchor_order=['A rounded nose','B rear neck'],model_anchors_local_m=ends.tolist(),scale_source='unchanged nominal length 0.737m; not independent measurement',censoring='1336 A left bound unobserved; 0981 both endpoints FOV-censored, excluded from fit')
    save(OUT/'observations-before-fit.json',ann)
    def residual(q,frames_in=frames,anns=annotations,anchors=ends):
        world=transform(anchors,matrix(q));rr=[]
        for sid,regions in anns.items():
            uv,e,z=uv_project(world,corrected_frame(frames_in[sid],q[6]) if len(q)==7 else frames_in[sid])
            for i,b in enumerate(regions):rr.extend(violation(uv[i],np.array(b[:2]),np.array(b[2:]))/np.array([2.,5.]))
            rr.extend(violation(e,-7,7)/2);rr.extend(np.maximum(.05-z,0)*100)
        return np.array(rr)
    # Synthetic control uses three known sensor translations and exact endpoint pixels.
    fake={};fa={};truth=np.array([0.,0.,2.,.1,.05,.3])
    for i,x in enumerate([-.08,0,.08]):
        f=dict(raw_shape_hw=[1000,128],range_start_m=.5,range_bin_m=.003,world_from_sonar=np.eye(4).tolist());f['world_from_sonar'][0][3]=x;sid=str(i);fake[sid]=f
        uv,_,_=uv_project(transform(ends,matrix(truth)),f);fa[sid]=[np.r_[u-1e-6,u+1e-6].tolist() for u in uv]
    control=least_squares(lambda q:residual(q,fake,fa),truth+np.array([.03,.02,.02,.02,.01,.02]),diff_step=1e-4,max_nfev=1500,xtol=1e-12,ftol=1e-12,gtol=1e-12)
    assert np.max(np.abs(control.fun))<1e-3
    origin=np.array(info['world_from_target'])[:3,3]
    prior=read(ROOT/'DataSet/sonar_origin_envelope/interval-control.json')['results']['100lbs']['sphere_candidates'][0]['center_world_m']
    candidates=[]
    for i in range(12):
        yaw=-np.pi+2*np.pi*(i%6)/6;rv=Rotation.from_euler('xyz',[0 if i<6 else np.pi/2,0,yaw]).as_rotvec();q0=np.r_[origin if i<6 else prior,rv,0.]
        result=least_squares(residual,q0,bounds=(np.r_[origin-.5,[-6.3]*3,-20.],np.r_[origin+.5,[6.3]*3,20.]),diff_step=1e-4,max_nfev=1800,xtol=1e-11,ftol=1e-11,gtol=1e-11)
        rr=residual(result.x);c=dict(id=f'endpoint-start-{i:02d}',parameters=result.x.tolist(),pan_delta_deg=float(result.x[6]),world_from_model=matrix(result.x).tolist(),cost=float(rr@rr),max_normalized_residual=float(np.abs(rr).max()),center_shift_m=float(np.linalg.norm(result.x[:3]-origin)),success=bool(result.success),message=result.message,nfev=int(result.nfev));candidates.append(c)
    viable=[c for c in candidates if c['max_normalized_residual']<=1]
    chosen=min(viable,key=lambda c:c['center_shift_m']) if viable else min(candidates,key=lambda c:c['cost'])
    freeze=dict(selected=chosen,selection_rule='fit max residual <=1 then smallest center shift; else lowest fit cost marked failed',fit_passed=bool(viable),raw_obj_to_model_similarity=S.tolist(),observations_sha256=hashlib.sha256((OUT/'observations-before-fit.json').read_bytes()).hexdigest(),candidates=candidates,synthetic_max_normalized_error=float(abs(control.fun).max()),approved_for_training_gt=False,pan_delta_is_diagnostic_only=True)
    save(OUT/'freeze-model.json',freeze)
    # Freeze before any evaluation; check observations never enter objective.
    obs=read(ROOT/'DataSet/sonar_fixed_registration_refinement/100lbs/adapted-fit-observations.json');ob={f['sample']:f for f in obs['frames']}
    dense=np.r_[p,transform(pts[faces].mean(1),S)]
    wt=np.array(chosen['world_from_model']);world=transform(dense,wt);evaluations=[];cards=[]
    for sid,f in frames.items():
        f=corrected_frame(f,chosen['parameters'][6])
        uv,e,z=uv_project(world,f);h,w=f['raw_shape_hw'];horizontal=(z>0)&(uv[:,0]>=0)&(uv[:,0]<=w)&(uv[:,1]>=0)&(uv[:,1]<=h);visible=horizontal&(abs(e)<=7)
        hulls={}
        for key,mask in [('full',horizontal),('gate7',visible)]:
            hulls[key]=cv2.convexHull(uv[mask].astype('float32')).reshape(-1,2) if mask.sum()>=3 else np.empty((0,2))
        projected_ends,ee,_=uv_project(transform(ends,wt),f)
        stats={}
        for key,hull in hulls.items():
            if sid in ob and len(hull):
                witnesses=np.array([p['witness_raw_uv_edge'] for p in ob[sid]['points']]);normalized=(hull/[2,5]).astype('float32');ds=[cv2.pointPolygonTest(normalized,tuple(map(float,q/[2,5])),True) for q in witnesses]
                stats[key]=dict(witness_count=len(ds),fraction_within_one_tolerance=float(np.mean(np.array(ds)>=-1)),max_outside_normalized=float(max(0,-min(ds))))
        rawpath=ROOT/'DataSet/sonar_fixed_mesh/frames'/f'{sid}-raw.png';tracked[str(rawpath)]=hashlib.sha256(rawpath.read_bytes()).hexdigest();a=np.array(Image.open(rawpath).convert('L'));raw=Image.fromarray(np.minimum(a.astype('uint16')*3,255).astype('uint8')).convert('RGB').resize((512,h))
        canvas=Image.new('RGB',(1152,h+70),'white');canvas.paste(raw,(0,35));d=ImageDraw.Draw(canvas);d.text((8,7),sid+' | fixed endpoint hypothesis, NOT GT',fill='black')
        for key,color in [('full','cyan'),('gate7','lime')]:
            hull=hulls[key]
            if len(hull):xy=[(float(u*4),float(v+35)) for u,v in hull];d.line(xy+[xy[0]],fill=color,width=2)
        for i,(u,v) in enumerate(projected_ends):
            if -10<u<138 and -10<v<h+10:d.ellipse((u*4-4,v+31,u*4+4,v+39),fill='magenta');d.text((u*4+6,v+35),'AB'[i],fill='magenta')
        if sid in annotations:
            for b in annotations[sid]:d.rectangle((max(0,b[0])*4,b[1]+35,min(128,b[2])*4,b[3]+35),outline='yellow',width=2)
        cam=ROOT/'DataSet/sonar_independent_registration/camera'/f'{sid}.jpg'
        if cam.exists():canvas.paste(Image.open(cam),(512,35));tracked[str(cam)]=hashlib.sha256(cam.read_bytes()).hexdigest()
        lines=['cyan: complete mesh projection','green: +/-7deg clipped mesh','magenta: fixed A/B anchors','yellow: frozen fit regions',f'fit: {sid in annotations}',f'full hull support: {stats.get("full",{})}',f'gate7 support: {stats.get("gate7",{})}']
        for i,line in enumerate(lines):d.text((525,420+i*24),line,fill='black')
        canvas.save(OUT/f'{sid}-projection.png');cards.append(f'<h3>{sid}</h3><img src="{sid}-projection.png">')
        evaluations.append(dict(sample=sid,role='fit' if sid in annotations else 'same_recording_check' if '171105' in sid else 'cross_recording_check',endpoints_raw_uv=projected_ends.tolist(),endpoints_elevation_deg=ee.tolist(),support=stats,hulls={k:v.tolist() for k,v in hulls.items()},uncertain=sid.endswith('173329_0456')))
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==s for p,s in tracked.items())
    save(OUT/'evaluation.json',dict(frames=evaluations,inputs_unchanged=True,input_hashes=tracked,new_training_gt=0,test_access=False))
    (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Endpoint registration</title><h1>固定端部区域注册假设：未验收</h1><p>两帧fit，一帧同录音检查，另三帧跨录音检查。原点与尺度/对应仍有假设，不是GT。</p>'+''.join(cards),encoding='utf-8')
    print(json.dumps(dict(chosen=chosen,viable=len(viable),control=freeze['synthetic_max_normalized_error'],checks=[dict(sample=f['sample'],support=f['support']) for f in evaluations]),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
