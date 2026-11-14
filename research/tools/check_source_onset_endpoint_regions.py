from pathlib import Path
import sys,json
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
from scipy.optimize import differential_evolution
from check_official_sonar_coordinates import load_beam_tables,linear_extrapolate
def main():
    out=ROOT/'DataSet/sonar_source_onset_control';data=json.loads((out/'results.json').read_text('utf-8'));frames={f['sample']:f for f in data['frames']};ids=['2023-09-20_171105_0622','2023-09-20_171105_1336'];regions=[[[8,24],[245,295],[96,116],[132,175]],[[0,14],[90,130],[88,104],[200,265]]];t=load_beam_tables()[128];knots=np.r_[np.column_stack([t[:,1],t[:,0]]).ravel(),t[-1,2]]
    def point(q,f):
        u,v,e=q;e=np.deg2rad(e);a=-np.deg2rad(linear_extrapolate(u,np.arange(257)/2,knots));r=f['range_start_m']+v*f['range_bin_m'];p=r*np.array([np.cos(e)*np.sin(a),np.sin(e),np.cos(e)*np.cos(a)]);ws=np.array(f['world_from_sonar']);return ws[:3,:3]@p+ws[:3,3]
    results=[]
    for end in [0,1]:
        bounds=[*regions[0][2*end:2*end+2],[-7,7],*regions[1][2*end:2*end+2],[-7,7]];cs=[]
        for seed in [17,31]:
            r=differential_evolution(lambda q:np.linalg.norm(point(q[:3],frames[ids[0]])-point(q[3:],frames[ids[1]])),bounds,seed=seed,popsize=12,maxiter=200,tol=1e-9,polish=True);cs.append(dict(seed=seed,distance_m=float(r.fun),parameters=r.x.tolist(),success=bool(r.success)))
        results.append(dict(endpoint='AB'[end],candidates=cs))
    (out/'endpoint-region-consistency.json').write_text(json.dumps(dict(results=results,not_correspondence_certification=True),indent=2),encoding='utf-8');print(results)
if __name__=='__main__':main()
