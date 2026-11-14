"""Tag-square image-only camera-model diagnostics with blocked held-out views."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import sys,json,re
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
import cv2
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix
from scipy.spatial.transform import Rotation
from prepare_sonar_tag_continuous import OUT,read,save,sha
OBJ=np.array([[-.5,.5,0],[.5,.5,0],[.5,-.5,0],[-.5,-.5,0]],float)
HIST_K=np.array([[397.77105952,0,323.01645778],[0,393.9965825,181.94773453],[0,0,1.]])*np.array([[3,3,3],[3,3,3],[1,1,1]])
HIST_D=np.array([.22602159,.34004099,-.39509882,.66812696])

def fixed_models():
    a=read(ROOT/'DataSet/sonar_rgb_pose_pilot/camera-assumptions.json');K=np.array(a['K_960x540']);K[:2]*=2
    return [dict(name='released_linear_pinhole',kind='pinhole',K=K.tolist(),D=[0]*4),dict(name='released_linear_fisheye_hypothesis',kind='fisheye',K=K.tolist(),D=a['raw_four_coefficients']),dict(name='historical_wide_fisheye',kind='fisheye',K=HIST_K.tolist(),D=HIST_D.tolist())]

def predict(x,model):
    # x is [rotvec, translation]; all distances in tag side units.
    K=np.array(model['K']);D=np.array(model['D']);rv=x[:3];tv=x[3:]
    if model['kind']=='fisheye':return cv2.fisheye.projectPoints(OBJ.reshape(-1,1,3),rv,tv,K,D.reshape(4,1))[0].reshape(4,2)
    return cv2.projectPoints(OBJ,rv,tv,K,D if model['kind']=='brown' else None)[0].reshape(4,2)

def pose_solutions(xy,model):
    K=np.array(model['K']);D=np.array(model['D']);points=xy
    if model['kind']=='fisheye':points=cv2.fisheye.undistortPoints(xy.reshape(-1,1,2),K,D.reshape(4,1),P=K).reshape(4,2)
    elif model['kind']=='brown':points=cv2.undistortPoints(xy.reshape(-1,1,2),K,D,P=K).reshape(4,2)
    _,rvs,tvs,_=cv2.solvePnPGeneric(OBJ,points,K,None,flags=cv2.SOLVEPNP_IPPE_SQUARE);out=[]
    for rv,tv in zip(rvs,tvs):
        x=np.r_[rv.ravel(),tv.ravel()]
        # Keep raw IPPE branches, no branch collapsing iterative optimization.
        pred=predict(x,model);R=cv2.Rodrigues(rv)[0]
        out.append(dict(parameters=x.tolist(),rotation_camera_from_tag=R.tolist(),reprojection_rms_px=float(np.sqrt(np.mean(np.sum((pred-xy)**2,axis=1)))),positive_depth=bool(((OBJ@R.T+tv.ravel())[:,2]>0).all())))
    return sorted(out,key=lambda x:x['reprojection_rms_px'])

def model_from_intrinsics(q,kind):
    K=[[float(np.exp(q[0])),0,float(q[2])],[0,float(np.exp(q[1])),float(q[3])],[0,0,1]]
    return dict(kind=kind,K=K,D=[float(q[4]),float(q[5]),0,0,0] if kind=='brown' else [0]*4)

def optimize(frames,kind,initial,max_nfev=180):
    n=len(frames);nq=6 if kind=='brown' else 4;q=np.r_[np.log([initial[0,0],initial[1,1]]),initial[:2,2],([0.,0.] if kind=='brown' else [])];model=model_from_intrinsics(q,kind)
    starts=np.array([pose_solutions(np.array(r['corners']),model)[0]['parameters'] for r in frames]);x=np.r_[q,starts.ravel()]
    lo=np.r_[np.log([400,400]),[480,270],([-2,-3] if kind=='brown' else []),np.tile([-10,-10,-10,-100,-100,.05],n)];hi=np.r_[np.log([4000,4000]),[1440,810],([2,3] if kind=='brown' else []),np.tile([10,10,10,100,100,1000],n)]
    x=np.clip(x,lo+1e-7,hi-1e-7);sparsity=lil_matrix((8*n,nq+6*n),dtype=int)
    for i in range(n):sparsity[8*i:8*i+8,:nq]=1;sparsity[8*i:8*i+8,nq+6*i:nq+6*i+6]=1
    def residual(v):
        model=model_from_intrinsics(v[:nq],kind);poses=v[nq:].reshape(n,6)
        return np.concatenate([(predict(p,model)-np.array(r['corners'])).ravel() for r,p in zip(frames,poses)])
    scale=np.r_[[.25,.25,300,200],([.4,.4] if kind=='brown' else []),np.tile([1,1,1,5,5,5],n)]
    r=least_squares(residual,x,bounds=(lo,hi),jac_sparsity=sparsity.tocsr(),x_scale=scale,max_nfev=max_nfev,ftol=1e-8,xtol=1e-8,gtol=1e-8)
    errors=np.linalg.norm(r.fun.reshape(n,4,2),axis=2);result=dict(kind=kind,initial_K=initial.tolist(),model=model_from_intrinsics(r.x[:nq],kind),intrinsic_parameters=r.x[:nq].tolist(),fit_median_corner_error_px=float(np.median(errors)),fit_rms_px=float(np.sqrt(np.mean(errors**2))),cost=float(r.cost),nfev=r.nfev,success=bool(r.success),message=r.message,near_intrinsic_bound=((r.x[:nq]-lo[:nq]<.001*(hi[:nq]-lo[:nq]))|(hi[:nq]-r.x[:nq]<.001*(hi[:nq]-lo[:nq]))).tolist(),fit_poses=r.x[nq:].reshape(n,6).tolist(),fit_sample_ids=[r['sample'] for r in frames])
    # Profile Jacobian: project each view's intrinsic sensitivity out of its six pose freedoms.
    profile=[];q=r.x[:nq]
    for i,row in enumerate(frames):
        pose=r.x[nq+6*i:nq+6*i+6];base=predict(pose,result['model']).ravel();A=[];B=[]
        for j in range(nq):
            step=1e-5 if j<2 or j>=4 else .01;qq=q.copy();qq[j]+=step;A.append((predict(pose,model_from_intrinsics(qq,kind)).ravel()-base)/step*scale[j])
        for j in range(6):
            step=1e-5;pp=pose.copy();pp[j]+=step;B.append((predict(pp,result['model']).ravel()-base)/step)
        A=np.array(A).T;B=np.array(B).T;profile.append(A-B@np.linalg.lstsq(B,A,rcond=1e-7)[0])
    ss=np.linalg.svd(np.vstack(profile),compute_uv=False);result['profile_intrinsic_singular_values_scaled']=ss.tolist();result['profile_condition_ratio']=float(ss[0]/max(ss[-1],1e-15));return result

def main():
    folder=OUT/'camera_models';assert not folder.exists();folder.mkdir();selected={r['sample']:r for r in read(OUT/'selection.json')['frames']};detections=read(OUT/'detections.json')['frames'];eligible=[]
    for row in detections:
        tags=[t for t in row['tags'] if t['id']==141 and t['minimum_edge_px']>=30 and t['border_clearance_px']>=5]
        if len(tags)==1:eligible.append(dict(sample=row['sample'],aris_frame=selected[row['sample']]['aris_frame'],corners=tags[0]['corners'],time_s=selected[row['sample']]['sd_pts']))
    first,last=eligible[0]['aris_frame'],eligible[-1]['aris_frame'];frozen=[];prev=-1000
    for r in eligible:
        if r['aris_frame']-prev<9 and r['aris_frame'] not in [392,788]:continue
        prev=r['aris_frame'];r=dict(r);block=min(5,int((r['aris_frame']-first)/(last-first)*6));fit=block%2==0 and all(abs(r['aris_frame']-a)>12 for a in [392,788]);r.update(block=block,role='fit' if fit else 'check');frozen.append(r)
    for anchor in [392,788]:
        if not any(r['aris_frame']==anchor for r in frozen):
            r=dict(next(r for r in eligible if r['aris_frame']==anchor));r.update(block=min(5,int((anchor-first)/(last-first)*6)),role='check');frozen.append(r)
    frozen.sort(key=lambda r:r['aris_frame']);save(folder/'selection-before-fit.json',dict(frames=frozen,all_eligible_count=len(eligible),rule='spacing>=9 ARIS; 6 time blocks; even fit, odd check; anchor+-12 prohibited fit; anchors check'))
    fit=[r for r in frozen if r['role']=='fit'];assert len(fit)>=20
    controls=fixed_models();models=list(controls);initials=[HIST_K,np.array(controls[0]['K']),np.array([[1500.,0,960],[0,1500.,540],[0,0,1.]])];candidates={};sensitivity={}
    for kind in ['pinhole','brown']:
        variants=[]
        for i,K in enumerate(initials):
            result=optimize(fit,kind,K);variants.append(result);save(folder/(f'{kind}-start-{i}.json'),result);print(kind,i,result['fit_rms_px'],result['nfev'],flush=True)
        best=min(variants,key=lambda r:r['cost']);best['name']='image_fit_'+kind;models.append(dict(name=best['name'],**best['model']));candidates[kind]=variants
        leave=[]
        for block in sorted({r['block'] for r in fit}):
            frames=[r for r in fit if r['block']!=block]
            if len(frames)<12:continue
            q=optimize(frames,kind,np.array(best['model']['K']),max_nfev=120);leave.append(dict(excluded_block=block,**q));print(kind,'omit',block,q['fit_rms_px'],q['nfev'],flush=True)
        sensitivity[kind]=leave;save(folder/(kind+'-fit.json'),dict(chosen=best,starts=variants,leave_time_block_out=leave))
    # Evaluate all detections (not just calibration selection); retain both IPPE branches.
    all_eval=[];poses={};anchor_ids=['2023-09-21_123500_0392','2023-09-21_123500_0788'];expected=np.array(selected[anchor_ids[1]]['world_from_camera'])[:3,:3].T@np.array(selected[anchor_ids[0]]['world_from_camera'])[:3,:3]
    for model in models:
        rr=[]
        for r in eligible:
            pp=pose_solutions(np.array(r['corners']),model);rr.append(dict(sample=r['sample'],aris_frame=r['aris_frame'],time_s=r['time_s'],solutions=pp))
        lookup={r['sample']:r for r in rr};p0=lookup[anchor_ids[0]]['solutions'];p1=lookup[anchor_ids[1]]['solutions'];combos=[]
        for i,a in enumerate(p0):
            for j,b in enumerate(p1):
                delta=np.array(b['rotation_camera_from_tag'])@np.array(a['rotation_camera_from_tag']).T@expected.T;combos.append(dict(first=i,second=j,difference_deg=float(Rotation.from_matrix(delta).magnitude()*180/np.pi)))
        errors={}
        for role in ['fit','check']:
            values=[lookup[r['sample']]['solutions'][0]['reprojection_rms_px'] for r in frozen if r['role']==role];errors[role]=dict(n=len(values),median_rms_px=float(np.median(values)),p90_rms_px=float(np.percentile(values,90)))
        # Image-only continuity: start from first frame's image-best, then lowest image+weak rotation transition cost.
        costs=[np.array([s['reprojection_rms_px']**2 for s in rr[0]['solutions']])];parents=[]
        for i in range(1,len(rr)):
            old=rr[i-1]['solutions'];new=rr[i]['solutions'];cost=np.zeros(len(new));parent=[]
            for j,n in enumerate(new):
                transitions=[costs[-1][k]+(float(Rotation.from_matrix(np.array(n['rotation_camera_from_tag'])@np.array(o['rotation_camera_from_tag']).T).magnitude()*180/np.pi)/10)**2 for k,o in enumerate(old)];k=int(np.argmin(transitions));cost[j]=transitions[k]+n['reprojection_rms_px']**2;parent.append(k)
            costs.append(cost);parents.append(parent)
        branch=[int(np.argmin(costs[-1]))]
        for i in range(len(rr)-2,-1,-1):branch.append(parents[i][branch[-1]])
        branch=branch[::-1]
        for r,b in zip(rr,branch):r['image_continuity_branch']=b
        b0=rr[[r['sample'] for r in rr].index(anchor_ids[0])]['image_continuity_branch'];b1=rr[[r['sample'] for r in rr].index(anchor_ids[1])]['image_continuity_branch'];cont=next(q for q in combos if q['first']==b0 and q['second']==b1)
        all_eval.append(dict(model=model,frames=rr,calibration_view_residuals=errors,anchor_all_branch_combinations=combos,anchor_image_best_difference_deg=combos[0]['difference_deg'],anchor_continuity_difference_deg=cont['difference_deg'],continuity_rule='image RMS^2 + (interframe rotation deg/10)^2; no release poses used',image_continuity_branch_switches=sum(b!=0 for b in branch)))
    save(folder/'evaluation.json',dict(models=all_eval,plan_sha256=sha(ROOT/'experiment/sonar-tag-continuous-camera-plan.md'),script_sha256=sha(__file__),data_sha256=sha(OUT/'detections.json'),selection_sha256=sha(folder/'selection-before-fit.json'),tag_motion_not_assumed_for_calibration=True,physical_calibration_approved=False))
    print([(m['model']['name'],m['anchor_image_best_difference_deg'],m['calibration_view_residuals']) for m in all_eval],flush=True)

if __name__=='__main__':main()
