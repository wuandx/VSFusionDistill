"""Single-loss-change control: fixed 3D registration with visually frozen ridge proxies."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import sys,json,time
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation
from PIL import Image,ImageDraw
from fit_box_guided_sonar_registration import Frame,read,save,sha,matrix,params,metrics,aggregate,MODELS,CAL,REG
from fit_sonar_fixed_registration_refinement import prepare_model
from sonar_manual_curation_server import DatasetSource
BASE=ROOT/'DataSet/sonar_box_guided_full_trajectory';ROOTOUT=ROOT/'DataSet/sonar_projection_root_cause';OUT=ROOTOUT/'curve_control'
def front_values(uv,obs):
    # Smooth near-surface proxy within angular neighbors; no per-frame parameters.
    distances=abs(obs[:,None,0]-uv[None,:,0]);ids=np.argpartition(distances,min(63,len(uv)-1),axis=1)[:,:min(64,len(uv))]
    du=np.take_along_axis(distances,ids,axis=1);vv=uv[ids,1];weights=np.exp(-np.minimum(du**2/4.5,650))
    low=vv.min(axis=1);soft=low-3*np.log(np.maximum((weights*np.exp(-(vv-low[:,None])/3)).sum(axis=1),1e-290)/np.maximum(weights.sum(axis=1),1e-290))
    gap=np.maximum(distances.min(axis=1)-1.5,0)
    return soft,gap
def curve_stats(uv,points):
    obs=np.array(points)
    if not len(obs):return None
    v,gap=front_values(uv,obs);error=abs(v-obs[:,1]);valid=gap<=1.5
    return dict(point_count=len(obs),supported_fraction=float(valid.mean()),median_abs_range_bins=float(np.median(error)),p90_abs_range_bins=float(np.percentile(error,90)),median_beam_gap=float(np.median(gap)))
def main():
    assert not OUT.exists();OUT.mkdir();(OUT/'frames').mkdir()
    ds=DatasetSource();data=read(BASE/'results.json');specs=read(BASE/'selection.json')['samples'];ob=read(ROOTOUT/'observations.json')['frames'];review=read(ROOTOUT/'fit-observation-review.json');registry=read(REG)['models'];statics={k:np.array(v) for k,v in read(CAL)['versions']['release_current']['parent_from_child_matrices'].items()}
    tracked={str(p):sha(p) for p in [BASE/'results.json',BASE/'selection.json',ROOTOUT/'observations.json',ROOTOUT/'fit-observation-review.json',Path(__file__),ROOT/'experiment/sonar-projection-root-cause-plan.md']};save(OUT/'inputs-before.json',tracked)
    results=[];summaries={}
    for model,(rec,target) in MODELS.items():
        folder=OUT/model;folder.mkdir();info=registry[model];sampled,dense,definition=prepare_model(info);hull=ConvexHull(sampled);points=np.r_[sampled[::8],sampled[hull.vertices]]
        rows=[r for r in data['frames'] if r['model']==model];frames={r['sample']:Frame(ds,r['sample'],statics) for r in rows};fits=[r for r in rows if r['role']=='fit']
        fitobs={}
        for r in fits:
            sid=r['sample'];o=np.array(ob[sid]['points_raw_uv']);remove=review['removed_point_indices'].get(sid,[]);o=np.array([p for i,p in enumerate(o) if i not in remove]).reshape(-1,2)
            if sid in review['excluded_curve_frames']:o=np.empty((0,2))
            fitobs[sid]=o
        save(folder/'fit-observations.json',{s:o.tolist() for s,o in fitobs.items()})
        def residual(q):
            T=matrix(q);rr=[]
            for r in fits:
                f=frames[r['sample']];ref=np.array(r['reference_bbox']);uv,p=f.project(points,T);b=np.r_[uv.min(0),uv.max(0)];wh=np.maximum(ref[2:]-ref[:2],1)
                if ref[0]<=1:b[0]=max(0,b[0])
                if ref[1]<=1:b[1]=max(0,b[1])
                if ref[2]>=f.geom.w-1:b[2]=min(f.geom.w,b[2])
                if ref[3]>=f.geom.h-1:b[3]=min(f.geom.h,b[3])
                rr.extend((b-ref)/np.tile(wh,2));rr.append(max(0,.05-p[:,2].min())*10)
                obs=fitobs[r['sample']]
                if len(obs):
                    pred,gap=front_values(uv,obs);delta=pred-obs[:,1];gaprange=np.sign(delta)*np.maximum(abs(delta)-3,0)
                    # Total curve weight per frame equals four box-edge residuals.
                    weight=np.sqrt(4/len(obs));rr.extend(gaprange/wh[1]*weight);rr.extend(gap/wh[0]*weight)
            return np.array(rr)
        origin=statics[target][:3,3];lower=np.r_[origin-.5,[-6.3]*3];upper=np.r_[origin+.5,[6.3]*3];starts=[]
        for i in range(12):starts.append(np.r_[origin,Rotation.from_euler('xyz',[0 if i<6 else np.pi/2,0,-np.pi+2*np.pi*(i%6)/6]).as_rotvec()])
        starts += [params(np.array(info['world_from_target'])),params(np.array(read(ROOT/f'DataSet/sonar_fixed_registration_refinement/{model}/freeze-model.json')['world_from_model']))]
        candidates=[]
        for i,q in enumerate(starts):
            result=least_squares(residual,np.clip(q,lower+1e-8,upper-1e-8),bounds=(lower,upper),loss='soft_l1',f_scale=.1,diff_step=1e-4,max_nfev=250,ftol=1e-7,xtol=1e-7,gtol=1e-7,x_scale=np.r_[[.1]*3,[1.]*3])
            candidates.append(dict(id=f'start-{i:02d}',parameters=result.x.tolist(),world_from_model=matrix(result.x).tolist(),fit_cost=float(result.cost),nfev=result.nfev,success=bool(result.success),message=result.message));print(model,i,round(result.cost,5),result.nfev,flush=True)
        best=min(candidates,key=lambda x:x['fit_cost']);T=np.array(best['world_from_model']);old=np.array(read(BASE/model/'freeze-model.json')['chosen']['world_from_model']);save(folder/'freeze-model.json',dict(chosen=best,candidates=candidates,raw_obj_to_model_similarity=info['mesh_to_target_similarity'],world_from_obj_similarity=(T@np.array(info['mesh_to_target_similarity'])).tolist(),fit_sample_ids=[r['sample'] for r in fits],check_used_for_selection=False,physical_registration_validated=False,approved_for_training_gt=False,inputs=tracked));print(model,'FROZEN',flush=True)
        rr=[]
        for r in rows:
            sid=r['sample'];f=frames[sid];new=f.box(dense,T,details=True);new['agreement']=metrics(new,np.array(r['reference_bbox']))
            # Curves measured on same deterministic surface sample for all variants.
            curve={}
            for key,pose in [('box_only',old),('box_plus_curve',T)]:
                uv,_=f.project(sampled,pose);curve[key]=curve_stats(uv,ob[sid]['points_raw_uv'])
            rr.append(dict(sample=sid,recording=r['recording'],model=model,role=r['role'],reference_bbox=r['reference_bbox'],old=r['predictions']['box_guided'],new=new,curve=curve,world_from_sonar=f.ws.tolist(),geometry=f.geom.description(),provenance=r['provenance']))
            if len(rr)%60==0:print(model,'evaluated',len(rr),flush=True)
        save(folder/'evaluation.json',dict(frames=rr));results+=rr
    save(OUT/'results.json',dict(frames=results,run='box_plus_curve',inputs=tracked,checks_not_blind=True))
    assert all(sha(p)==v for p,v in tracked.items());print('COMPLETE',len(results),flush=True)
if __name__=='__main__':main()
