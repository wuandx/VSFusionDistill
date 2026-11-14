"""Independent sampled-sector and saved-candidate feasibility controls."""
from diagnose_sonar_origin_intervals import ROOT,BASE,OUT,read,distance
from check_official_sonar_coordinates import load_beam_tables,linear_extrapolate
import numpy as np,json,hashlib

def main():
    saved=read(OUT/'interval-control.json');tables=load_beam_tables();errors=[];feas=[]
    for model,result in saved['results'].items():
        frames={f['sample']:f for f in read(BASE/model/'evaluation-results.json')['frames']}
        origin=np.array(result['official_origin_world_m']);records=[]
        for f in read(BASE/model/'adapted-fit-observations.json')['frames']:
            frame=frames[f['sample']];g=frame['geometry'];ws=np.array(frame['world_from_sonar']);w=g['raw_shape_hw'][1];table=tables[w]
            knots=np.r_[np.column_stack([table[:,1],table[:,0]]).ravel(),table[-1,2]]
            for p in f['points']:
                b=linear_extrapolate(p['beam_window'],np.arange(2*w+1)/2,knots);rs=g['range_start_m']+np.array(p['range_interval'])*g['sample_bin_m']
                record=(ws,-np.deg2rad(b[1]),-np.deg2rad(b[0]),*rs);records.append(record)
                # Independent exhaustive angle grid, with analytic radial clamp only.
                a,e=np.meshgrid(np.linspace(record[1],record[2],101),np.deg2rad(np.linspace(-7,7,301)))
                directions=np.stack([np.cos(e)*np.sin(a),np.sin(e),np.cos(e)*np.cos(a)],-1).reshape(-1,3)
                q=(np.linalg.inv(ws)@np.r_[origin,1])[:3]
                radii=np.clip(directions@q,rs[0],rs[1]);ps=directions*radii[:,None]
                brute=np.linalg.norm(ps-q,axis=1).min();exact=distance(origin,record,np.deg2rad(7))
                errors.append(float(abs(brute-exact)));assert abs(brute-exact)<.0001
        for c in result['sphere_candidates']:
            ds=[distance(np.array(c['center_world_m']),r,np.deg2rad(7)) for r in records]
            violation=max(ds)-c['radius_m'];assert violation<1e-7;feas.append(float(violation))
    assert all(hashlib.sha256(__import__('pathlib').Path(p).read_bytes()).hexdigest()==h for p,h in saved['input_hashes'].items())
    output=dict(intervals_checked=len(errors),grid_max_error_m=max(errors),sphere_candidates_checked=len(feas),max_sphere_constraint_violation_m=max(feas),source_hashes_unchanged=True,passed=True)
    (OUT/'interval-verification.json').write_text(json.dumps(output,indent=2),encoding='utf-8');print(output)
if __name__=='__main__':main()
