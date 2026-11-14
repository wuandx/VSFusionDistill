"""Verify frozen endpoint controls independently of projection helper."""
from pathlib import Path
import json,sys,hashlib
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
from scipy.spatial.transform import Rotation
from PIL import Image
from check_official_sonar_coordinates import load_beam_tables

def read(p):return json.loads(p.read_text('utf-8'))
def main():
    frames={f['sample']:f for f in read(ROOT/'DataSet/sonar_fixed_mesh/results.json')['outputs']};table=load_beam_tables()[128]
    aa=np.r_[np.column_stack([table[:,1],table[:,0]]).ravel(),table[-1,2]];xx=np.arange(257)/2
    results=[]
    for folder in ['sonar_endpoint_registration','sonar_endpoint_pan_control']:
        base=ROOT/'DataSet'/folder;freeze=read(base/'freeze-model.json');ann=read(base/'observations-before-fit.json');ev=read(base/'evaluation.json');T=np.array(freeze['selected']['world_from_model']);anchors=np.array(ann['model_anchors_local_m']);deltas=[]
        assert abs(np.linalg.det(T[:3,:3])-1)<1e-12
        assert freeze['observations_sha256']==hashlib.sha256((base/'observations-before-fit.json').read_bytes()).hexdigest()
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in ev['input_hashes'].items())
        for f in ev['frames']:
            original=frames[f['sample']];ws=np.array(original['world_from_sonar'])
            delta=freeze['selected'].get('pan_delta_deg',0)
            if delta:
                oldwa=np.array(original['world_from_ar3']);ws_static=np.linalg.solve(oldwa,ws);wa=oldwa.copy();roll,tilt,pan=original['aris_roll_tilt_pan_deg']
                # Independent elementary matrices in published xyz convention.
                rx=Rotation.from_euler('x',roll,degrees=True).as_matrix();ry=Rotation.from_euler('y',tilt,degrees=True).as_matrix();rz=Rotation.from_euler('z',pan+delta,degrees=True).as_matrix()
                wa[:3,:3]=np.diag([-1,1,-1])@rz@ry@rx;ws=wa@ws_static
            world=np.c_[anchors,np.ones(2)]@T.T;sonar=np.linalg.solve(ws,world.T).T[:,:3];r=np.sqrt((sonar*sonar).sum(1));angle=-np.degrees(np.arctan2(sonar[:,0],sonar[:,2]));u=[]
            for a in angle:
                k=int(np.clip(np.searchsorted(aa,a)-1,0,len(aa)-2));u.append(xx[k]+(a-aa[k])/(aa[k+1]-aa[k])*(xx[k+1]-xx[k]))
            uv=np.c_[u,(r-original['range_start_m'])/original['range_bin_m']];deltas.append(float(np.abs(uv-np.array(f['endpoints_raw_uv'])).max()))
            with Image.open(base/(f['sample']+'-projection.png')) as im:im.load()
        assert max(deltas)<1e-9
        row=dict(run=folder,frames=6,candidates=len(freeze['candidates']),max_endpoint_replay_difference_px=max(deltas),source_hashes_unchanged=True,all_images_decode=True,fit_passed=freeze['fit_passed'],approved_for_training_gt=False);results.append(row)
    out=ROOT/'DataSet/sonar_endpoint_pan_control/verification.json';out.write_text(json.dumps(dict(results=results,passed=True),indent=2),encoding='utf-8');print(results)
if __name__=='__main__':main()
