"""Bounded synthetic six-DOF solver controls; no image or real observation reads."""
from pathlib import Path
import csv
import hashlib
import json
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
import scipy
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
import fit_mortar_fixed_registration as legacy
from check_official_sonar_coordinates import Geometry, beam_count, load_beam_tables

OUT = ROOT/'DataSet/sonar_registration_solver_controls'
PLAN = ROOT/'experiment/sonar-registration-solver-controls-plan.md'
SCALE = np.array([.05,.05,.05,30.,15.,30.])
LOWER = np.array([-.35,-.35,-.20,-180.,-60.,-180.])
UPPER = -LOWER
TRUTH = np.array([.025,-.018,.012,12.,5.,20.])
STARTS = [np.array(v) for v in [[.035,-.018,.012,12.,5.,20.],
                               [.04,-.03,.022,16.,2.,25.], [0.,0.,0.,0.,0.,0.]]]
FIT_INDICES = [87,451,811]


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save(path,value): Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def matrix(x,origin): return legacy.matrix_from_parameters(np.asarray(x),origin,0.,0.)


def project(points,T,frame):
    combined=frame.sonar_from_world@T
    p=points@combined[:3,:3].T+combined[:3,3]
    ranges=np.linalg.norm(p,axis=1)
    beta=-np.degrees(np.arctan2(p[:,0],p[:,2]))
    return frame.geom.points_to_raw_edges(ranges,beta)


def central_jacobian(function,x,step=1e-5):
    columns=[]
    for i in range(len(x)):
        delta=np.zeros_like(x);delta[i]=step
        columns.append((function(x+delta)-function(x-delta))/(2*step))
    return np.column_stack(columns)


def spectrum(J):
    sv=np.linalg.svd(J,compute_uv=False)
    threshold=max(float(sv[0])*1e-8,1e-12)
    return dict(singular_values=sv.tolist(),rank=int(np.sum(sv>threshold)),threshold=threshold,
                condition_number=float(sv[0]/sv[-1]) if sv[-1]>0 else None)


class BudgetExceeded(RuntimeError): pass


def run_fit(name,start,fn,origin,frames,points,global_started,stable=True,max_nfev=160):
    run_started=time.perf_counter();calls=0;improvements=[];best_cost=float('inf');best_x=start.copy()
    call_limit=1500 if name.startswith('legacy_') else 2500
    time_limit=180 if name.startswith('legacy_') else 120
    def wrapped(argument):
        nonlocal calls,best_cost,best_x
        if calls>=call_limit or time.perf_counter()-run_started>time_limit or time.perf_counter()-global_started>600:
            raise BudgetExceeded('Preregistered residual/time budget reached')
        calls+=1;x=argument*SCALE if stable else argument
        value=fn(x);cost=float(value@value/2)
        if cost<best_cost:
            best_cost=cost;best_x=x.copy()
            improvements.append(dict(call=calls,objective=cost,parameters=x.tolist()))
        return value
    failure=None;fit=None
    initial=fn(start)
    try:
        if stable:
            fit=least_squares(wrapped,start/SCALE,jac=lambda q:central_jacobian(wrapped,q),
                              bounds=(LOWER/SCALE,UPPER/SCALE),x_scale=1.,max_nfev=max_nfev,
                              ftol=1e-10,xtol=1e-10,gtol=1e-10)
            final=fit.x*SCALE
        else:
            fit=least_squares(wrapped,start,bounds=(LOWER,UPPER),x_scale=SCALE,max_nfev=max_nfev,
                              diff_step=1e-4,ftol=1e-7,xtol=1e-7,gtol=1e-7)
            final=fit.x
    except Exception as exc:
        failure=repr(exc);final=best_x
    T=matrix(final,origin);truthT=matrix(TRUTH,origin)
    all_errors=[project(points,T,frame)-project(points,truthT,frame) for frame in frames]
    max_error=max(float(np.max(np.abs(value))) for value in all_errors)
    translation_error=float(np.linalg.norm(final[:3]-TRUTH[:3]))
    rotation_error=float(np.degrees(Rotation.from_matrix(T[:3,:3]@truthT[:3,:3].T).magnitude()))
    residual=fn(final)
    passed=translation_error<1e-5 and rotation_error<.01 and max_error<1e-3
    jac=central_jacobian(lambda q:fn(q*SCALE),final/SCALE)
    result=dict(name=name,initial_parameters=start.tolist(),final_parameters=final.tolist(),
                parameter_order=['dx_m','dy_m','dz_m','yaw_deg','pitch_deg','roll_deg'],
                initial_objective=float(initial@initial/2),final_objective=float(residual@residual/2),
                residual_max_abs=float(np.max(np.abs(residual))),translation_error_m=translation_error,
                rotation_error_deg=rotation_error,full_model_projection_max_abs_error_px=max_error,
                recovery_threshold_pass=passed,solver_success=bool(fit.success) if fit is not None else False,
                solver_status=int(fit.status) if fit is not None else None,message=str(fit.message) if fit is not None else failure,
                nfev=int(fit.nfev) if fit is not None else None,njev=int(fit.njev) if fit is not None else None,
                optimality=float(fit.optimality) if fit is not None else None,actual_residual_calls=calls,
                elapsed_seconds=time.perf_counter()-run_started,failure=failure,finite_difference_normalized_step=1e-5 if stable else None,
                jacobian_normalized_parameters=spectrum(jac),improvement_trace=improvements,
                max_nfev=max_nfev,residual_call_limit=call_limit,time_limit_seconds=time_limit,
                objective_note='Case-specific synthetic objective; objective magnitudes are not directly comparable across different constraint sets')
    save(OUT/(name+'.json'),result)
    print(name,'initial',result['initial_objective'],'final',result['final_objective'],
          'translation_m',translation_error,'rotation_deg',rotation_error,'recovery',passed,'calls',calls,flush=True)
    return result


def support_signature(frames,points,parameters,origin):
    signatures=[]
    for frame in frames:
        p=frame.project(points,matrix(parameters,origin));d=frame.distances(p)
        original_indices=np.flatnonzero(p['visible'])
        lookup={tuple(uv):int(index) for uv,index in zip(p['uv'][p['visible']],original_indices)}
        nearest=[lookup.get(tuple(uv),-1) for uv in d['closest']]
        signatures.append((p['visible'],np.array(nearest)))
    return signatures


def main():
    started=time.perf_counter()
    if (OUT/'run-state.json').exists(): raise RuntimeError('Preserve existing named control; do not overwrite')
    OUT.mkdir(parents=True,exist_ok=True)
    save(OUT/'run-state.json',dict(status='started',run='sonar_registration_solver_controls',observations='synthetic only'))
    model_path=ROOT/'DataSet/mortar_fixed_registration/model-definition.json'
    points_path=ROOT/'DataSet/mortar_fixed_registration/sampled-model-points.npy'
    old_control_path=ROOT/'DataSet/mortar_fixed_registration/numerical-controls.json'
    cal_path=ROOT/'DataSet/sonar_model_registration_consistency/calibration-versions.json'
    meta_path=Path('D:/pby/uxo-full/extracted/recordings/15cm_mortar/2023-09-21_100927/aris_frame_meta.csv')
    gantry_path=meta_path.parent/'gantry.csv'
    paths=[PLAN,Path(__file__),Path(legacy.__file__),ROOT/'tools/check_official_sonar_coordinates.py',
           ROOT/'related_work/uxo-upstream-history/scripts/common/aris_definitions.py',model_path,points_path,
           old_control_path,cal_path,meta_path,gantry_path]
    before={str(path):sha(path) for path in paths}
    save(OUT/'inputs-before.json',before)
    info=read(model_path);points=np.load(points_path,allow_pickle=False)
    assert legacy.arrsha(points)==info['sampling']['sampled_model_points_sha256']
    statics={k:np.asarray(v) for k,v in read(cal_path)['versions']['release_current']['parent_from_child_matrices'].items()}
    origin=statics['target/mortar_shell'][:3,3]
    metadata={int(r['FrameIndex']):r for r in csv.DictReader(meta_path.open(encoding='utf-8-sig',newline='')) if int(r['FrameIndex']) in FIT_INDICES}
    gantry={int(r['aris_frame_idx']):r for r in csv.DictReader(gantry_path.open(encoding='utf-8-sig',newline='')) if int(r['aris_frame_idx']) in FIT_INDICES}
    tables=load_beam_tables();frames=[];truthT=matrix(TRUTH,origin)
    correspondence_indices=[];observations=[];boundaries=[];fixture=[]
    for index in FIT_INDICES:
        m=metadata[index];g=gantry[index]
        wa=np.eye(4);wa[:3,:3]=statics['setup/ar3'][:3,:3]@Rotation.from_euler('xyz',[float(m[k]) for k in ['SonarRoll','SonarTilt','SonarPan']],degrees=True).as_matrix()
        wa[:3,3]=np.array([float(g[k]) for k in 'xyz'])+statics['setup/ar3'][:3,3]
        pose=wa@statics['setup/aris']@statics['setup/sonar']
        sample=f'synthetic-view-{index:04d}'
        dummy=dict(sample=sample,points=[dict(raw_uv_edge=[64.,200.],tolerance_uv=[.1,.2]) for _ in range(3)])
        frame=legacy.FitFrame(dummy,dict(world_from_sonar=pose),m,tables[beam_count(m['PingMode'])])
        projected=frame.project(points,truthT);visible_indices=np.flatnonzero(projected['visible'])
        indices=visible_indices[np.linspace(0,len(visible_indices)-1,12,dtype=int)]
        legacy_uv=projected['uv'][indices]
        synthetic=dict(sample=sample,points=[dict(raw_uv_edge=uv.tolist(),tolerance_uv=[.1,.2]) for uv in legacy_uv],boundary_intervals={})
        frame=legacy.FitFrame(synthetic,dict(world_from_sonar=pose),m,tables[beam_count(m['PingMode'])]);frames.append(frame)
        ends=np.array([int(np.argmin(points[:,0])),int(np.argmax(points[:,0]))])
        fixed_indices=np.unique(np.r_[indices,ends]);correspondence_indices.append(fixed_indices)
        all_uv=project(points,truthT,frame);observations.append(all_uv[fixed_indices]);boundaries.append(np.r_[all_uv.min(0),all_uv.max(0)])
        fixture.append(dict(sample=sample,metadata_frame_index=index,world_from_sonar=pose.tolist(),
                            geometry=frame.geom.description(),legacy_point_indices=indices.tolist(),legacy_uv=legacy_uv.tolist(),
                            fixed_correspondence_indices=fixed_indices.tolist(),fixed_correspondence_uv=all_uv[fixed_indices].tolist(),
                            endpoint_indices=ends.tolist(),endpoint_truth_visible=projected['visible'][ends].tolist(),
                            complete_surface_bounds=boundaries[-1].tolist()))
    save(OUT/'synthetic-fixture.json',dict(truth_parameters=TRUTH.tolist(),origin_world_m=origin.tolist(),
                                        truth_world_from_model=truthT.tolist(),frames=fixture,points_sha256=legacy.arrsha(points),
                                        real_observation_reads=0,image_reads=0,check_reads=0))
    legacy_fn=lambda x:legacy.raw_loss(frames,points,matrix(x,origin))
    old_record=read(old_control_path)
    initial=legacy_fn(STARTS[0]);initial_cost=float(initial@initial/2)
    assert abs(initial_cost-old_record['recovery_initial_objective'])<1e-9,(initial_cost,old_record)
    assert np.max(np.abs(legacy_fn(TRUTH)))<1e-10
    results=[]
    results.append(run_fit('legacy_interval_replay',STARTS[0],legacy_fn,origin,frames,points,started,stable=False,max_nfev=60))
    xfinal=np.array(results[0]['final_parameters'])
    interpolation=[]
    for fraction in np.linspace(0,1,11):
        x=xfinal*(1-fraction)+TRUTH*fraction;r=legacy_fn(x)
        interpolation.append(dict(fraction_to_truth=float(fraction),objective=float(r@r/2)))
    base_signature=support_signature(frames,points,xfinal,origin);changes=[]
    for axis in range(6):
        for sign in [-1,1]:
            displaced=xfinal.copy();displaced[axis]+=sign*1e-5*SCALE[axis]
            sig=support_signature(frames,points,displaced,origin)
            changes.append(dict(axis=axis,sign=sign,physical_step=float(sign*1e-5*SCALE[axis]),
                                visible_membership_changes=sum(int(np.sum(a[0]!=b[0])) for a,b in zip(base_signature,sig)),
                                nearest_witness_changes=sum(int(np.sum(a[1]!=b[1])) for a,b in zip(base_signature,sig))))
    jacobians=[central_jacobian(lambda q:legacy_fn(q*SCALE),xfinal/SCALE,step=h) for h in [1e-6,1e-5,1e-4]]
    diagnostic=dict(replay_matches_previous_final=abs(results[0]['final_objective']-old_record['recovery_final_objective'])<1e-7,
                    interpolation_to_known_truth=interpolation,support_changes_at_stable_step=changes,
                    difference_step_diagnostics=[dict(step=h,**spectrum(J)) for h,J in zip([1e-6,1e-5,1e-4],jacobians)],
                    jacobian_relative_change_1e6_to_1e5=float(np.linalg.norm(jacobians[0]-jacobians[1])/max(np.linalg.norm(jacobians[1]),1e-12)),
                    jacobian_relative_change_1e4_to_1e5=float(np.linalg.norm(jacobians[2]-jacobians[1])/max(np.linalg.norm(jacobians[1]),1e-12)))
    save(OUT/'legacy-diagnostics.json',diagnostic)
    results.append(run_fit('legacy_interval_stable_difference',STARTS[0],legacy_fn,origin,frames,points,started,stable=True,max_nfev=60))
    def corresponding(x):
        T=matrix(x,origin)
        return np.concatenate([((project(points[ix],T,frame)-observed)/[.1,.2]/np.sqrt(len(ix))).ravel()
                               for frame,ix,observed in zip(frames,correspondence_indices,observations)])
    def complete_bounds(x):
        T=matrix(x,origin);res=[]
        for frame,observed in zip(frames,boundaries):
            uv=project(points,T,frame);predicted=np.r_[uv.min(0),uv.max(0)]
            res.append((predicted-observed)/[.1,.2,.1,.2]/2)
        return np.concatenate(res)
    for case,fn in [('fixed_surface_correspondence',corresponding),('complete_surface_boundaries',complete_bounds)]:
        for i,start in enumerate(STARTS):
            results.append(run_fit(case+f'_start{i}',start,fn,origin,frames,points,started))
    after={str(path):sha(path) for path in paths}
    assert before==after
    save(OUT/'inputs-after.json',after)
    summary=dict(run='sonar_registration_solver_controls',status='completed',elapsed_seconds=time.perf_counter()-started,
                 synthetic_only=True,image_reads=0,real_observation_reads=0,real_check_reads=0,test_reads=0,training_runs=0,
                 numpy_version=np.__version__,scipy_version=scipy.__version__,input_hashes_unchanged=True,
                 primary_correspondence_recovery_pass=all(r['recovery_threshold_pass'] for r in results if r['name'].startswith('fixed_surface_')),
                 results=[{k:v for k,v in r.items() if k!='improvement_trace'} for r in results],
                 legacy_diagnostics=diagnostic,limitations=['Known correspondences and complete synthetic boundaries are supplied by construction.',
                 'Synthetic endpoint constraints may include points outside the hard elevation gate; truth visibility is recorded.',
                 'No result certifies real echo association, physical calibration, real registration, or automatic annotation quality.'])
    save(OUT/'results.json',summary)
    save(OUT/'run-state.json',dict(status='completed',run=summary['run'],elapsed_seconds=summary['elapsed_seconds'],
                                 primary_correspondence_recovery_pass=summary['primary_correspondence_recovery_pass']))


if __name__=='__main__':
    try: main()
    except Exception as exc:
        if OUT.exists(): save(OUT/'failure.json',dict(status='failed',error=repr(exc)))
        raise
