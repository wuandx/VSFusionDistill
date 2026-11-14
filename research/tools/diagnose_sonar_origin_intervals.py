"""Interval-aware necessary geometry constraints, not a new registration."""
import sys,json,hashlib
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
from scipy.optimize import minimize
from check_official_sonar_coordinates import load_beam_tables,linear_extrapolate
BASE=ROOT/'DataSet/sonar_fixed_registration_refinement';OUT=ROOT/'DataSet/sonar_origin_envelope'
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def distance(c,record,lim):
    ws,lo,hi,rlo,rhi=record
    q=ws[:3,:3].T@(c-ws[:3,3])
    az=np.clip(np.arctan2(q[0],q[2]),lo,hi)
    A=q[0]*np.sin(az)+q[2]*np.cos(az)
    assert A>0, 'analytic projection assumes front-facing sector'
    e=np.clip(np.arctan2(q[1],A),-lim,lim)
    direction=np.array([np.cos(e)*np.sin(az),np.sin(e),np.cos(e)*np.cos(az)])
    r=np.clip(q@direction,rlo,rhi)
    return float(np.linalg.norm(q-r*direction))
def main():
    dest=OUT/'interval-control.json'
    if dest.exists():raise RuntimeError('Preserve control')
    prior=read(OUT/'results.json');tables=load_beam_tables();results={}
    inputs={}
    for model in ('100lbs','incindiary','mortar_shell'):
        ep=BASE/model/'evaluation-results.json';op=BASE/model/'adapted-fit-observations.json'
        for p in (ep,op):inputs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
        fs={f['sample']:f for f in read(ep)['frames']};obs=read(op)['frames'];records=[];samples=[]
        for f in obs:
            frame=fs[f['sample']];g=frame['geometry'];ws=np.array(frame['world_from_sonar']);w=g['raw_shape_hw'][1];table=tables[w]
            knots=np.r_[np.column_stack([table[:,1],table[:,0]]).ravel(),table[-1,2]]
            for p in f['points']:
                beta=linear_extrapolate(p['beam_window'],np.arange(2*w+1)/2,knots)
                rr=g['range_start_m']+np.array(p['range_interval'])*g['sample_bin_m']
                records.append((ws,-np.deg2rad(beta[1]),-np.deg2rad(beta[0]),*rr));samples.append(f['sample'])
        first=next(f for f in prior['frames'] if f['model']==model);f0=fs[first['sample']];ws=np.array(f0['world_from_sonar'])
        origin=ws[:3,:3]@np.array(first['origin_sonar_xyz_m'])+ws[:3,3];radius=first['orientation_independent_mesh_bound_radius_m']
        checks={}
        for name,lim in [('unrestricted',np.pi/2),('gate7',np.deg2rad(7))]:
            ds=np.array([distance(origin,r,lim) for r in records])
            checks[name]=dict(outside=int((ds>radius).sum()),max_distance_m=float(ds.max()),exceedance_max_m=float(max(0,ds.max()-radius)),by_sample=[dict(sample=s,distance_m=float(d),outside=bool(d>radius)) for s,d in zip(samples,ds)])
        candidates=[];lim=np.deg2rad(7)
        for offset in ([0,0,0],[.15,0,0],[0,.15,0],[0,0,.15]):
            c=origin+offset;rad=max(distance(c,r,lim) for r in records)+.01
            def constraints(x):return np.array([x[3]-distance(x[:3],r,lim) for r in records])
            res=minimize(lambda x:x[3],np.r_[c,rad],method='SLSQP',bounds=[(v-.4,v+.4) for v in origin]+[(0,1.5)],constraints=[dict(type='ineq',fun=constraints)],options=dict(maxiter=300,ftol=1e-10))
            candidates.append(dict(success=bool(res.success),message=str(res.message),center_world_m=res.x[:3].tolist(),center_shift_m=float(np.linalg.norm(res.x[:3]-origin)),radius_m=float(res.x[3]),minimum_constraint_m=float(constraints(res.x).min()),iterations=int(res.nit)))
        results[model]=dict(witnesses=len(records),old_bound_radius_m=radius,official_origin_world_m=origin.tolist(),interval_checks=checks,sphere_candidates=candidates)
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==s for p,s in inputs.items())
    dest.write_text(json.dumps(dict(results=results,input_hashes=inputs,inputs_unchanged=True,not_gt=True),ensure_ascii=False,indent=2),encoding='utf-8')
    for m,r in results.items():print(m,'interval outside',[(k,v['outside'],v['max_distance_m']) for k,v in r['interval_checks'].items()],'sphere',[(c['success'],c['radius_m'],c['center_shift_m']) for c in r['sphere_candidates']])
if __name__=='__main__':main()
