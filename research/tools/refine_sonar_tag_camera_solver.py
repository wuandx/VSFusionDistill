"""Dense exact trust-region refinement of frozen camera fitting candidates."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from fit_sonar_tag_camera_models import OUT,read,save,sha,model_from_intrinsics,predict,pose_solutions

def main():
    folder=OUT/'camera_solver_control';assert not folder.exists();folder.mkdir();rows=read(OUT/'camera_models/selection-before-fit.json')['frames'];fit=[r for r in rows if r['role']=='fit'];lookup={r['sample']:r for r in rows};sel={r['sample']:r for r in read(OUT/'selection.json')['frames']};anchors=['2023-09-21_123500_0392','2023-09-21_123500_0788'];expected=np.array(sel[anchors[1]]['world_from_camera'])[:3,:3].T@np.array(sel[anchors[0]]['world_from_camera'])[:3,:3];results=[]
    for kind in ['pinhole','brown']:
        original=read(OUT/'camera_models'/(kind+'-fit.json'));sources=[dict(run='full_fit',**original['chosen'])]+[dict(run='omit_'+str(r['excluded_block']),**r) for r in original['leave_time_block_out']];refined=[]
        for source in sources:
            rr=[lookup[s] for s in source['fit_sample_ids']];n=len(rr);nq=6 if kind=='brown' else 4;x=np.r_[source['intrinsic_parameters'],np.array(source['fit_poses']).ravel()]
            lo=np.r_[np.log([400,400]),[480,270],([-2,-3] if kind=='brown' else []),np.tile([-10,-10,-10,-100,-100,.05],n)];hi=np.r_[np.log([4000,4000]),[1440,810],([2,3] if kind=='brown' else []),np.tile([10,10,10,100,100,1000],n)]
            scale=np.r_[[.25,.25,300,200],([.4,.4] if kind=='brown' else []),np.tile([1,1,1,5,5,5],n)]
            def residual(v):return np.concatenate([(predict(p,model_from_intrinsics(v[:nq],kind))-np.array(r['corners'])).ravel() for r,p in zip(rr,v[nq:].reshape(n,6))])
            opt=least_squares(residual,x,bounds=(lo,hi),x_scale=scale,max_nfev=400,ftol=1e-9,xtol=1e-9,gtol=1e-9,tr_solver='exact');q=opt.x[:nq];model=model_from_intrinsics(q,kind);evaluated=[]
            for r in rows:
                pp=pose_solutions(np.array(r['corners']),model);evaluated.append(dict(sample=r['sample'],role=r['role'],rms_px=pp[0]['reprojection_rms_px'],solutions=pp))
            byid={r['sample']:r for r in evaluated};a=byid[anchors[0]]['solutions'][0];b=byid[anchors[1]]['solutions'][0];delta=np.array(b['rotation_camera_from_tag'])@np.array(a['rotation_camera_from_tag']).T@expected.T
            errors={role:dict(median_rms_px=float(np.median([r['rms_px'] for r in evaluated if r['role']==role])),p90_rms_px=float(np.percentile([r['rms_px'] for r in evaluated if r['role']==role],90))) for role in ['fit','check']}
            # Jacobian of normalized parameter perturbations, pose nuisance removed.
            profile=[];J=opt.jac
            for i in range(n):
                A=J[8*i:8*i+8,:nq]*scale[:nq];B=J[8*i:8*i+8,nq+6*i:nq+6*i+6];profile.append(A-B@np.linalg.lstsq(B,A,rcond=1e-7)[0])
            ss=np.linalg.svd(np.vstack(profile),compute_uv=False);out=dict(run=source['run'],kind=kind,model=model,cost=float(opt.cost),source_cost=source['cost'],fit_rms_px=float(np.sqrt(np.mean(np.linalg.norm(opt.fun.reshape(n,4,2),axis=2)**2))),nfev=opt.nfev,success=bool(opt.success),message=opt.message,optimality=float(opt.optimality),near_intrinsic_bound=((q-lo[:nq]<.001*(hi[:nq]-lo[:nq]))|(hi[:nq]-q<.001*(hi[:nq]-lo[:nq]))).tolist(),profile_intrinsic_singular_values_scaled=ss.tolist(),profile_condition_ratio=float(ss[0]/max(ss[-1],1e-15)),fit_sample_ids=source['fit_sample_ids'],evaluation=evaluated,view_residuals=errors,anchor_difference_deg=float(Rotation.from_matrix(delta).magnitude()*180/np.pi),fit_poses=opt.x[nq:].reshape(n,6).tolist(),intrinsic_parameters=q.tolist())
            refined.append(out);save(folder/(kind+'-'+source['run']+'.json'),out);print(kind,source['run'],out['fit_rms_px'],opt.nfev,opt.success,out['anchor_difference_deg'],flush=True)
        results.append(dict(kind=kind,refined=refined))
    save(folder/'results.json',dict(models=results,plan_sha256=sha(ROOT/'experiment/sonar-tag-camera-solver-control-plan.md'),script_sha256=sha(__file__),role_selection_sha256=sha(OUT/'camera_models/selection-before-fit.json'),physical_calibration_approved=False))

if __name__=='__main__':main()
