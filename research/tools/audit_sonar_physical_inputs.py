"""Inspect allowed-recording geometry inputs and verify the official pose demo."""
from pathlib import Path
import csv
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
sys.dont_write_bytecode=True
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'DataSet/sonar_projection_chain_audit'
ASSETS=ROOT/'related_work/sonar-projection-audit-assets'
sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
import yaml
from scipy.spatial.transform import Rotation
from pytransform3d.transform_manager import TransformManager

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def tf_from_yaml(row):
    t=np.array([row['translation'][k] for k in 'xyz'])
    q=np.array([row['rotation'][k] for k in ['x','y','z','w']])
    T=np.eye(4);T[:3,:3]=Rotation.from_quat(q).as_matrix();T[:3,3]=t
    return T

manifest=json.loads((ROOT/'DataSet/camera_temporal_all/manifest-resolved.json').read_text(encoding='utf-8'))
records={}
tracked=set()
for item in manifest['items']:
    records.setdefault(item['recording'],Path(item['original_label']).parent.parent)
inventory=[]
for rec,rd in sorted(records.items()):
    assert rec in manifest['identity']['recordings']
    with (rd/'aris_frame_meta.csv').open(encoding='utf-8',newline='') as f:meta=list(csv.DictReader(f))
    with (rd/'gantry.csv').open(encoding='utf-8',newline='') as f:gantry=list(csv.DictReader(f))
    filemeta=yaml.safe_load((rd/'aris_file_meta.yaml').read_text(encoding='utf-8'))
    notes=(rd/'notes.txt').read_text(encoding='utf-8')
    tracked.update(rd/p for p in ['aris_frame_meta.csv','gantry.csv','aris_file_meta.yaml','notes.txt'])
    row=dict(recording=rec,category=next(r['category'] for r in manifest['recordings'] if r['recording']==rec),
             metadata_rows=len(meta),gantry_rows=len(gantry),num_beams=filemeta['NumRawBeams'],
             samples_per_channel=filemeta['SamplesPerChannel'],ar3_csv_exists=(rd/'ar3.csv').exists(),
             orientation_columns_present=all(k in meta[0] for k in ['SonarPan','SonarTilt','SonarRoll']),
             notes=notes,explicit_motion_note=any(k in notes.lower() for k in ['moving','movable','rotating target','target moves']))
    for field in ['SonarPan','SonarTilt','SonarRoll','WindowStart','SamplePeriod','SoundSpeed','SamplesPerBeam']:
        values=np.array([float(m[field]) for m in meta])
        row[field+'_min_max']=[float(values.min()),float(values.max())]
        assert np.isfinite(values).all()
    assert {int(r['FrameIndex']) for r in meta}=={int(r['aris_frame_idx']) for r in gantry}
    inventory.append(row)

before={str(p):digest(p) for p in tracked}
tf_path=ASSETS/'data_export_calibration/calibration/transforms.yaml'
transforms=yaml.safe_load(tf_path.read_text(encoding='utf-8'))
git_tf=ASSETS/'calibration__transforms.yaml'
assert yaml.safe_load(git_tf.read_text(encoding='utf-8'))==transforms
setup={r['frame_id']:tf_from_yaml(r) for r in transforms['setup']}
target={r['frame_id']:tf_from_yaml(r) for r in transforms['targets']}

# Official notebook's fixed control: recording 171105, frame 1211.
rd=records['2023-09-20_171105']
with (rd/'aris_frame_meta.csv').open(encoding='utf-8',newline='') as f:m=next(r for r in csv.DictReader(f) if int(r['FrameIndex'])==1211)
with (rd/'gantry.csv').open(encoding='utf-8',newline='') as f:g=next(r for r in csv.DictReader(f) if int(r['aris_frame_idx'])==1211)
world_ar3=np.eye(4)
world_ar3[:3,3]=np.array([float(g[k]) for k in 'xyz'])+setup['setup/ar3'][:3,3]
world_ar3[:3,:3]=setup['setup/ar3'][:3,:3]@Rotation.from_euler('xyz',[float(m[k]) for k in ['SonarRoll','SonarTilt','SonarPan']],degrees=True).as_matrix()
# Notebook rounds ar3 pose to six decimals before reading it back.
position_rounded=np.round(world_ar3[:3,3],6)
quat_rounded=np.round(Rotation.from_matrix(world_ar3[:3,:3]).as_quat(),6)
world_ar3[:3,3]=position_rounded;world_ar3[:3,:3]=Rotation.from_quat(quat_rounded).as_matrix()
world_cam=world_ar3@setup['setup/gopro_mounting_hole']@setup['setup/gopro_mounting_axis']@setup['setup/camera']
cam_target=np.linalg.inv(world_cam)@target['target/100lbs']
notebook=json.loads((ASSETS/'demo__snippet_for_pose_gt.ipynb').read_text(encoding='utf-8'))
expected=np.array([[.75499007,.65573623,0,.178494],[.28745525,-.33096518,-.89879449,.03468642],[-.58937211,.67858091,-.43837024,1.02410471],[0,0,0,1]])
assert any('0.75499007' in str(c.get('outputs')) and '1.02410471' in str(c.get('outputs')) for c in notebook['cells'])
error=float(np.max(np.abs(cam_target-expected)))
# Independently repeat the transform composition with the upstream demo library.
manager=TransformManager()
for entry in transforms['setup']+transforms['targets']:
    manager.add_transform(entry['frame_id'],entry['parent_frame_id'],tf_from_yaml(entry))
manager.add_transform('setup/ar3','world',world_ar3)
library_result=manager.get_transform('target/100lbs','setup/camera')
library_error=float(np.max(np.abs(cam_target-library_result)))
assert library_error<1e-10
angle_difference=float(Rotation.from_matrix(cam_target[:3,:3]@expected[:3,:3].T).magnitude()*180/np.pi)
translation_difference=float(np.linalg.norm(cam_target[:3,3]-expected[:3,3]))
ar3_expected_position=np.array([1.848146,.627722,-1.088])
ar3_expected_quat=np.array([.407265,.893156,-.079164,.173612])
assert np.array_equal(position_rounded,ar3_expected_position) and np.array_equal(quat_rounded,ar3_expected_quat)
save(OUT/'official-pose-control.json',dict(recording='2023-09-20_171105',frame=1211,
     source='official notebook saved numeric output, non-test source metadata',world_ar3_position=position_rounded.tolist(),
     world_ar3_quaternion_xyzw=quat_rounded.tolist(),camera_from_target=cam_target.tolist(),
     notebook_expected=expected.tolist(),max_abs_error=error,passed=error<1e-7,
     ar3_pose_matches_notebook=True,independent_transform_library_max_error=library_error,
     camera_rotation_difference_deg=angle_difference,camera_translation_difference_m=translation_difference,
     note='Public AR3 pose reproduced; current public calibration does not reproduce saved camera transform output. Cause unresolved; no correction fitted.'))
print('POSE CONTROL',json.dumps(dict(actual=cam_target.tolist(),expected=expected.tolist(),error=error)))

models=[]
for path in sorted((ASSETS/'data_export_3dmodels/3d_models').glob('*.obj')):
    points=np.array([[float(x) for x in line.split()[1:4]] for line in path.read_text().splitlines() if line.startswith('v ')])
    models.append(dict(path=str(path),sha256=digest(path),vertices=len(points),minimum=points.min(0).tolist(),
                       maximum=points.max(0).tolist(),extent_obj_units=np.ptp(points,axis=0).tolist()))
summary=dict(allowed_recordings=len(inventory),orientation_columns_present=sum(r['orientation_columns_present'] for r in inventory),
             ar3_csv_exists=sum(r['ar3_csv_exists'] for r in inventory),
             raw_shapes=sorted({(r['samples_per_channel'],r['num_beams']) for r in inventory}),
             archive_git_calibration_semantically_equal=True,official_pose_demo_reproduced=error<1e-7,
             normalized_stl_from_official_demo_present=False,
             obj_to_target_scale_rotation_translation_documented=False,
             status='HOLD for physical mesh GT: model-to-target registration and per-recording validity not established')
save(OUT/'physical-input-inventory.json',dict(summary=summary,recordings=inventory,models=models))
after={str(p):digest(p) for p in tracked}
assert before==after
save(OUT/'physical-input-hashes.json',dict(files=len(before),sha256=before,unchanged=True))

# Record the two additional public notebooks already fetched during the investigation.
log_path=ASSETS/'acquisition-log.json';log=json.loads(log_path.read_text(encoding='utf-8'))
for name in ['camera_tilt.ipynb','transforms_nb.ipynb']:
    path=ASSETS/('demo__'+name)
    if path.exists() and not any(x.get('local_path')==str(path) for x in log):
        log.append(dict(url='https://raw.githubusercontent.com/dfki-ric/uxo-dataset2024/main/demo/'+name,
                        local_path=str(path),bytes=path.stat().st_size,sha256=digest(path),status=200,
                        note='Retrieved during audit; retrieval UTC time not captured, record creation time only',
                        recorded_at_utc=datetime.now(timezone.utc).isoformat()))
save(log_path,log)
print(json.dumps(summary,ensure_ascii=False,indent=2))
print('official pose maximum absolute error',error)
