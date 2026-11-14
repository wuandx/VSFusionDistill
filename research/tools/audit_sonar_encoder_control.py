"""Replace only pose telemetry fields while keeping each frozen model fixed."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import sys,json
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
from scipy.spatial.transform import Rotation
from fit_box_guided_sonar_registration import Frame,read,save,sha,metrics,REG,CAL
from fit_sonar_fixed_registration_refinement import prepare_model
from sonar_manual_curation_server import DatasetSource
BASE=ROOT/'DataSet/sonar_box_guided_full_trajectory';OUT=ROOT/'DataSet/sonar_projection_root_cause/encoder_control'
def main():
    assert not OUT.exists();OUT.mkdir();ds=DatasetSource();rows=read(BASE/'results.json')['frames'];statics={k:np.array(v) for k,v in read(CAL)['versions']['release_current']['parent_from_child_matrices'].items()};registry=read(REG)['models'];cache={};out=[]
    for r in rows:
        model=r['model'];sid=r['sample']
        if model not in cache:cache[model]=(prepare_model(registry[model])[1],np.array(read(BASE/model/'freeze-model.json')['chosen']['world_from_model']))
        points,T=cache[model];f=Frame(ds,sid,statics);mm,gg,*_=ds.recording_metadata(r['recording']);m=mm[f.row['aris_frame']];g=gg[f.row['aris_frame']]
        wa=np.eye(4);wa[:3,:3]=statics['setup/ar3'][:3,:3]@Rotation.from_euler('xyz',[float(m[k]) for k in ['RollAbsPosition','TiltAbsPosition','PanAbsPosition']],degrees=True).as_matrix();wa[:3,3]=np.array([float(g[k]) for k in 'xyz'])+statics['setup/ar3'][:3,3]
        f.ws=wa@statics['setup/aris']@statics['setup/sonar'];f.sw=np.linalg.inv(f.ws);new=f.box(points,T,details=True);new['agreement']=metrics(new,np.array(r['reference_bbox']))
        out.append(dict(sample=sid,recording=r['recording'],role=r['role'],model=model,old=r['predictions']['box_guided'],new=new,world_from_sonar=f.ws.tolist(),reference_bbox=r['reference_bbox'],provenance=r['provenance'],geometry=f.geom.description()))
    summary=[]
    for rec in sorted({r['recording'] for r in out}):
        rr=[r for r in out if r['recording']==rec and r['role']!='fit'];summary.append(dict(recording=rec,n=len(rr),old_median_iou=float(np.median([r['old']['agreement']['iou'] for r in rr])),encoder_median_iou=float(np.median([r['new']['agreement']['iou'] for r in rr]))))
    save(OUT/'results.json',dict(frames=out,summary=summary,plan_sha256=sha(ROOT/'experiment/sonar-encoder-field-control-plan.md'),frozen_models_unchanged=True,physical_accuracy_validated=False));print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
