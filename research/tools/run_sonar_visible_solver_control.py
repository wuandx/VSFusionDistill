"""Registered follow-up: only truth-visible synthetic fixed correspondences."""
import csv
import json
from pathlib import Path
import sys
import time

sys.dont_write_bytecode=True
import run_sonar_registration_solver_controls as control
import numpy as np
from scipy.spatial.transform import Rotation

ROOT=control.ROOT;OUT=control.OUT


def independent_projection(points,parameters,origin,frame):
    roll,pitch,yaw=np.deg2rad([parameters[5],parameters[4],parameters[3]])
    Rx=np.array([[1,0,0],[0,np.cos(roll),-np.sin(roll)],[0,np.sin(roll),np.cos(roll)]])
    Ry=np.array([[np.cos(pitch),0,np.sin(pitch)],[0,1,0],[-np.sin(pitch),0,np.cos(pitch)]])
    Rz=np.array([[np.cos(yaw),-np.sin(yaw),0],[np.sin(yaw),np.cos(yaw),0],[0,0,1]])
    transform=np.eye(4);transform[:3,:3]=Rz@Ry@Rx;transform[:3,3]=origin+parameters[:3]
    homogeneous=(np.linalg.inv(frame.world_from_sonar)@transform@np.column_stack([points,np.ones(len(points))]).T).T
    p=homogeneous[:,:3];ranges=np.sqrt(np.sum(p*p,axis=1));angle=-np.arctan2(p[:,0],p[:,2])*180/np.pi
    knots=frame.geom.angle_knots;index=np.searchsorted(knots,angle,side='right')-1;index=np.clip(index,0,len(knots)-2)
    column=(index+(angle-knots[index])/(knots[index+1]-knots[index]))/2
    row=(ranges-frame.geom.r0)/frame.geom.dr
    return np.column_stack([column,row])


def main():
    if (OUT/'visible-correspondence-results.json').exists(): raise RuntimeError('Do not overwrite completed supplemental control')
    started=time.perf_counter()
    fixture=control.read(OUT/'synthetic-fixture.json');origin=np.array(fixture['origin_world_m'])
    points_path=ROOT/'DataSet/mortar_fixed_registration/sampled-model-points.npy';points=np.load(points_path,allow_pickle=False)
    meta_path=Path('D:/pby/uxo-full/extracted/recordings/15cm_mortar/2023-09-21_100927/aris_frame_meta.csv')
    metadata={int(r['FrameIndex']):r for r in csv.DictReader(meta_path.open(encoding='utf-8-sig',newline='')) if int(r['FrameIndex']) in control.FIT_INDICES}
    paths=[Path(__file__),Path(control.__file__),control.PLAN,OUT/'synthetic-fixture.json',points_path,meta_path]
    before={str(path):control.sha(path) for path in paths}
    frames=[];indices=[];observations=[];selection=[];tables=control.load_beam_tables()
    truth=control.matrix(control.TRUTH,origin)
    for row in fixture['frames']:
        m=metadata[row['metadata_frame_index']]
        dummy=dict(sample=row['sample'],points=[dict(raw_uv_edge=uv,tolerance_uv=[.1,.2]) for uv in row['legacy_uv']])
        frame=control.legacy.FitFrame(dummy,dict(world_from_sonar=row['world_from_sonar']),m,tables[control.beam_count(m['PingMode'])])
        frames.append(frame)
        original=np.asarray(row['fixed_correspondence_indices'])
        visible=frame.project(points,truth)['visible'];retained=original[visible[original]];indices.append(retained)
        observations.append(independent_projection(points[retained],control.TRUTH,origin,frame))
        selection.append(dict(sample=row['sample'],original_count=len(original),retained_count=len(retained),
                              excluded_point_indices=original[~visible[original]].tolist(),retained_point_indices=retained.tolist()))
    def residual(parameters):
        T=control.matrix(parameters,origin)
        return np.concatenate([((control.project(points[ix],T,frame)-observed)/[.1,.2]/np.sqrt(len(ix))).ravel()
                               for frame,ix,observed in zip(frames,indices,observations)])
    results=[];verification=[]
    for i,start in enumerate(control.STARTS):
        result=control.run_fit(f'fixed_visible_correspondence_start{i}',start,residual,origin,frames,points,started)
        results.append(result);final=np.array(result['final_parameters']);T=control.matrix(final,origin)
        errors=[];implementation_errors=[];visible_counts=[]
        for frame,ix in zip(frames,indices):
            actual=independent_projection(points,final,origin,frame)
            expected=independent_projection(points,control.TRUTH,origin,frame)
            errors.append(float(np.max(np.abs(actual-expected))))
            implementation_errors.append(float(np.max(np.abs(actual-control.project(points,T,frame)))))
            visible_counts.append(int(frame.project(points,T)['visible'][ix].sum()))
        assert max(implementation_errors)<1e-9
        verification.append(dict(name=result['name'],independent_full_model_max_error_px=max(errors),
                                 independent_implementation_max_error_px=max(implementation_errors),
                                 final_visible_correspondences=visible_counts,retained_counts=[len(ix) for ix in indices]))
    after={str(path):control.sha(path) for path in paths};assert before==after
    summary=dict(run='fixed_visible_correspondence',status='completed',selection=selection,
                 results=[{k:v for k,v in r.items() if k!='improvement_trace'} for r in results],independent_verification=verification,
                 all_recovery_thresholds_pass=all(r['recovery_threshold_pass'] for r in results),
                 input_hashes=before,input_hashes_unchanged=True,image_reads=0,real_observation_reads=0,real_check_reads=0,
                 elapsed_seconds=time.perf_counter()-started,note='Synthetic known surface correspondences only; no real registration claim')
    control.save(OUT/'visible-correspondence-results.json',summary)
    print('VISIBLE CONTROL',summary['all_recovery_thresholds_pass'],'independent max error',max(v['independent_full_model_max_error_px'] for v in verification),flush=True)


if __name__=='__main__':main()
