"""Scale-free tag relative rotation control, no metric pose or mesh fitting."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
import cv2
from scipy.spatial.transform import Rotation
from prepare_sonar_rgb_pose_pilot import OUT,read,save,sha
from sonar_manual_curation_server import DatasetSource
from fit_box_guided_sonar_registration import CAL

OBJ=np.array([[-.5,.5,0],[.5,.5,0],[.5,-.5,0],[-.5,-.5,0]],np.float64)
def poses(xy,K,D,kind):
    pts=xy if kind=='pinhole' else cv2.fisheye.undistortPoints(xy.reshape(-1,1,2),K,D.reshape(4,1),P=K).reshape(-1,2)
    n,rv,tv,_=cv2.solvePnPGeneric(OBJ,pts,K,None,flags=cv2.SOLVEPNP_IPPE_SQUARE);result=[]
    for r,t in zip(rv,tv):
        R=cv2.Rodrigues(r)[0]
        pred=(cv2.projectPoints(OBJ,r,t,K,None)[0] if kind=='pinhole' else cv2.fisheye.projectPoints(OBJ.reshape(-1,1,3),r,t,K,D.reshape(4,1))[0]).reshape(-1,2)
        result.append(dict(rotation_camera_from_tag=R.tolist(),reprojection_rms_fhd_px=float(np.sqrt(np.mean(np.sum((pred-xy)**2,axis=1)))),positive_depth=bool(((OBJ@R.T+t.ravel())[:,2]>0).all())))
    return sorted(result,key=lambda r:r['reprojection_rms_fhd_px'])
def angle(R):return float(Rotation.from_matrix(R).magnitude()*180/np.pi)

def main():
    path=OUT/'tag-rotation.json';assert not path.exists();ids=['2023-09-21_123500_0392','2023-09-21_123500_0788'];tags={r['sample']:r for r in read(OUT/'pooled/tag-detections.json')['frames']};xy=[np.array(tags[s]['corners_fhd'][tags[s]['ids'].index(141)]) for s in ids];a=read(OUT/'camera-assumptions.json');K=np.array(a['K_960x540']);K[:2]*=2;D=np.array(a['raw_four_coefficients']);ds=DatasetSource();statics={k:np.array(v) for k,v in read(CAL)['versions']['release_current']['parent_from_child_matrices'].items()};world=[]
    for sid in ids:
        r=ds.require(sid);mm,gg,*_=ds.recording_metadata(r['recording']);m=mm[r['aris_frame']];wa=statics['setup/ar3'][:3,:3]@Rotation.from_euler('xyz',[float(m[k]) for k in ['SonarRoll','SonarTilt','SonarPan']],degrees=True).as_matrix();wc=wa
        for k in ['setup/gopro_mounting_hole','setup/gopro_mounting_axis','setup/camera']:wc=wc@statics[k][:3,:3]
        world.append(wc)
    expected=world[1].T@world[0];variants=[]
    for kind in ['pinhole','fisheye']:
        pp=[poses(p,K,D,kind) for p in xy];combinations=[]
        for i,u in enumerate(pp[0]):
            for j,v in enumerate(pp[1]):
                rel=np.array(v['rotation_camera_from_tag'])@np.array(u['rotation_camera_from_tag']).T
                combinations.append(dict(first_solution=i,second_solution=j,relative_rotation_deg=angle(rel),difference_from_released_pose_deg=angle(rel@expected.T)))
        rng=np.random.default_rng(20261113);errors=[]
        for i in range(100):
            q=[poses(p+rng.normal(0,.5,p.shape),K,D,kind)[0] for p in xy];rel=np.array(q[1]['rotation_camera_from_tag'])@np.array(q[0]['rotation_camera_from_tag']).T;errors.append(angle(rel@expected.T))
        variants.append(dict(camera_model=kind,solutions=pp,all_solution_combinations=combinations,selected_by_image_reprojection=combinations[0],corner_noise_sigma_fhd_px=.5,corner_noise_repeats=100,difference_percentiles_5_50_95_deg=np.percentile(errors,[5,50,95]).tolist()))
    save(path,dict(samples=ids,tag_id=141,corners_fhd=[p.tolist() for p in xy],tag_assumed_static=True,static_assumption_independently_verified=False,physical_side_length_known=False,metric_translations_not_reported=True,released_camera_rotation_change_deg=angle(expected),released_camera_relative_rotation=expected.tolist(),variants=variants,plan_sha256=sha(ROOT/'experiment/sonar-rgb-tag-rotation-plan.md'),script_sha256=sha(__file__),source_detection_sha256=sha(OUT/'pooled/tag-detections.json'),calibration_sha256=sha(CAL),physical_sync_certified=False))
    print([(r['camera_model'],r['selected_by_image_reprojection'],r['difference_percentiles_5_50_95_deg']) for r in variants])

if __name__=='__main__':main()
