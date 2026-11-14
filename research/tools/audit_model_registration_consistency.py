"""Version-qualified calibration controls and non-metric OBJ diagnostics. No GT writes."""
from pathlib import Path
import sys, json, hashlib, subprocess, csv
from datetime import datetime, timezone
sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/_sonar_audit_deps'))
import numpy as np
import yaml
from scipy.spatial.transform import Rotation
from pytransform3d.transform_manager import TransformManager
from PIL import Image, ImageDraw

UP = ROOT / 'related_work/uxo-upstream-history'
SRC = ROOT / 'related_work/model-registration-sources'
OUT = ROOT / 'DataSet/sonar_model_registration_consistency'
ASSETS = ROOT / 'related_work/sonar-projection-audit-assets'
SRC.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def git(*args): return subprocess.check_output(['git', '-C', str(UP), *args])
def original_state():
    repo = str(ROOT.parent / '声呐目标检测/code/VSFusionDistill')
    return {k: subprocess.check_output(['git', '-C', repo, *args]).decode().strip()
            for k, args in [('head', ['rev-parse','HEAD']), ('status', ['status','--porcelain'])]}

before_repo = original_state()
previous_hashes = json.loads((ROOT/'DataSet/sonar_projection_chain_audit/physical-input-hashes.json').read_text(encoding='utf-8'))['sha256']
before_hashes = {p: sha(Path(p)) for p in previous_hashes}
assert before_hashes == previous_hashes
snapshots = [
    ('notebook-era-transforms.yaml', 'ffd60f8271038e3dc9f12e3dd218e3a1c9e9a4a9', 'scripts/common/tf_statics.yaml'),
    ('pre-pitch-change-transforms.yaml', '3aa12ec^', 'scripts/common/tf_statics.yaml'),
    ('current-transforms.yaml', 'HEAD', 'calibration/transforms.yaml'),
    ('historical-README.md', '60fd93f^', 'README.md'),
    ('pose-notebook-at-addition.ipynb', 'ffd60f8271038e3dc9f12e3dd218e3a1c9e9a4a9', 'scripts/snippet_for_pose_gt.ipynb'),
]
provenance = []
for name, ref, path in snapshots:
    commit = git('rev-parse', ref).decode().strip()
    blob = git('show', f'{commit}:{path}')
    local = SRC/name; local.write_bytes(blob)
    provenance.append(dict(commit=commit, repository='https://github.com/dfki-ric/uxo-dataset2024',
        repository_path=path, local_path=str(local), sha256=sha(local), bytes=len(blob)))
change = git('show','--format=fuller','3aa12ec','--','scripts/common/tf_statics.yaml')
(SRC/'camera-pitch-change.patch').write_bytes(change)
paths = sorted(set(p for p in git('log','--all','--pretty=format:','--name-only').decode().splitlines() if p))
(SRC/'all-public-history-paths.txt').write_text('\n'.join(paths)+'\n', encoding='utf-8')
notes_commits = git('log','--format=%H','--','object_notes.md').decode().splitlines()
for ref in notes_commits:
    if not git('ls-tree','--name-only',ref,'object_notes.md').strip(): continue
    blob = git('show',f'{ref}:object_notes.md')
    local = SRC/('object-notes-'+ref[:8]+'.md'); local.write_bytes(blob)
    provenance.append(dict(commit=ref, repository_path='object_notes.md', local_path=str(local), sha256=sha(local)))
save(SRC/'history-provenance.json',dict(head=git('rev-parse','HEAD').decode().strip(),
    captured_utc=datetime.now(timezone.utc).isoformat(), snapshots=provenance,
    model_asset_paths=[p for p in paths if p.lower().endswith(('.obj','.stl','.ply','.blend','.psx','.psz'))]))

def matrix(entry):
    result=np.eye(4)
    result[:3,:3]=Rotation.from_quat([entry['rotation'][k] for k in ['x','y','z','w']]).as_matrix()
    result[:3,3]=[entry['translation'][k] for k in 'xyz']
    return result

manifest=json.loads((ROOT/'DataSet/camera_temporal_all/manifest-resolved.json').read_text(encoding='utf-8'))
assert '2023-09-20_171105' in manifest['identity']['recordings']
rd=Path(next(i['original_label'] for i in manifest['items'] if i['recording']=='2023-09-20_171105')).parent.parent
with (rd/'aris_frame_meta.csv').open(encoding='utf-8',newline='') as f:
    meta=next(r for r in csv.DictReader(f) if int(r['FrameIndex'])==1211)
with (rd/'gantry.csv').open(encoding='utf-8',newline='') as f:
    gantry=next(r for r in csv.DictReader(f) if int(r['aris_frame_idx'])==1211)
control=json.loads((ROOT/'DataSet/sonar_projection_chain_audit/official-pose-control.json').read_text(encoding='utf-8'))
expected=np.array(control['notebook_expected'])
notebook=json.loads((SRC/'pose-notebook-at-addition.ipynb').read_text(encoding='utf-8'))
assert any('0.75499007' in str(c.get('outputs')) and '1.02410471' in str(c.get('outputs')) for c in notebook['cells'])
versions={}
for version, filename in [('notebook_20240723','notebook-era-transforms.yaml'),('release_current','current-transforms.yaml')]:
    source=SRC/filename
    data=yaml.safe_load(source.read_text(encoding='utf-8'))
    rows={e['frame_id']:e for e in data['setup']+data['targets']}
    tf={k:matrix(v) for k,v in rows.items()}
    world_ar3=np.eye(4)
    world_ar3[:3,3]=np.array([float(gantry[k]) for k in 'xyz'])+tf['setup/ar3'][:3,3]
    world_ar3[:3,:3]=tf['setup/ar3'][:3,:3]@Rotation.from_euler('xyz',[float(meta[k]) for k in ['SonarRoll','SonarTilt','SonarPan']],degrees=True).as_matrix()
    # Match the demo's stored six-decimal AR3 CSV, without fitting transforms.
    world_ar3[:3,3]=np.round(world_ar3[:3,3],6)
    world_ar3[:3,:3]=Rotation.from_quat(np.round(Rotation.from_matrix(world_ar3[:3,:3]).as_quat(),6)).as_matrix()
    ar3_camera=tf['setup/gopro_mounting_hole']@tf['setup/gopro_mounting_axis']@tf['setup/camera']
    camera_target=np.linalg.inv(world_ar3@ar3_camera)@tf['target/100lbs']
    manager=TransformManager()
    for k,v in rows.items(): manager.add_transform(k,v['parent_frame_id'],tf[k])
    manager.add_transform('setup/ar3','world',world_ar3)
    independent=manager.get_transform('target/100lbs','setup/camera')
    assert np.max(np.abs(camera_target-independent))<1e-10
    sonar_camera=np.linalg.inv(tf['setup/sonar'])@ar3_camera
    versions[version]=dict(source=str(source),sha256=sha(source),
        camera_from_target=camera_target.tolist(),sonar_from_camera=sonar_camera.tolist(),
        world_from_ar3=world_ar3.tolist(),
        notebook_max_abs_error=float(np.max(np.abs(camera_target-expected))),
        notebook_translation_error_m=float(np.linalg.norm(camera_target[:3,3]-expected[:3,3])),
        notebook_rotation_error_deg=float(np.rad2deg(Rotation.from_matrix(camera_target[:3,:3]@expected[:3,:3].T).magnitude())),
        independent_library_max_abs_error=float(np.max(np.abs(camera_target-independent))),
        notebook_within_2e_6=bool(np.max(np.abs(camera_target-expected))<2e-6),
        parent_from_child_matrices={k:v.tolist() for k,v in tf.items()})
assert versions['notebook_20240723']['notebook_within_2e_6']
assert not versions['release_current']['notebook_within_2e_6']
historical=yaml.safe_load((SRC/'notebook-era-transforms.yaml').read_text(encoding='utf-8'))
current=yaml.safe_load((SRC/'current-transforms.yaml').read_text(encoding='utf-8'))
changed=[]
for group in ['setup','targets']:
    for a,b in zip(historical[group],current[group]):
        assert a['frame_id']==b['frame_id']
        if a!=b:changed.append(a['frame_id'])
assert changed==['setup/gopro_mounting_axis']
assert versions['notebook_20240723']['parent_from_child_matrices']['setup/sonar']==versions['release_current']['parent_from_child_matrices']['setup/sonar']
assert current==yaml.safe_load((ASSETS/'data_export_calibration/calibration/transforms.yaml').read_text(encoding='utf-8'))
save(OUT/'calibration-versions.json',dict(matrix_convention='column vectors; A_from_B maps B to A; translations in m',
    control=dict(recording='2023-09-20_171105',frame=1211,ar3_rounding_decimals=6,notebook_comparison_tolerance=2e-6),
    changed_frames=changed,default_for_release_diagnostics='release_current',
    physical_accuracy_validated=False,versions=versions))

# Intrinsic file has no explicit resolution/model metadata. Preserve it without guessing its interpretation.
intrinsic=UP/'calibration/camera_parameters/camera_parameter_linear.txt'
(SRC/'camera_parameter_linear.txt').write_bytes(intrinsic.read_bytes())
v1=json.loads((SRC/'zenodo-v1.json').read_text(encoding='utf-8'))
checks={x['key']:x['checksum'] for x in v1['files'] if any(k in x['key'] for k in ['3d','calib'])}
assert checks['data_export_3dmodels.7z']=='md5:4ed8820771bbb39819eacf66b50ff509'
assert checks['data_export_calibration.7z']=='md5:bb7641890899bf424e3eeb242509f261'

dimensions={'100lbs':(.737,.208),'incindiary':(.442,.127),'mortar_shell':(.580,.120)}
registry=[]
canvas=Image.new('RGB',(1230,1000),'white');draw=ImageDraw.Draw(canvas)
draw.text((15,10),'Public OBJ geometry: raw vertex units; PCA axes, NOT registered target axes',fill='black')
for idx,(name,(length,diameter)) in enumerate(dimensions.items()):
    mesh=ASSETS/f'data_export_3dmodels/3d_models/{name}.obj'
    vertices=np.array([[float(x) for x in line.split()[1:4]] for line in mesh.read_text(encoding='utf-8').splitlines() if line.startswith('v ')])
    center=vertices.mean(0); _,_,vh=np.linalg.svd(vertices-center,full_matrices=False)
    local=(vertices-center)@vh.T
    extents=np.ptp(local,axis=0)
    s=length/extents[0]
    registry.append(dict(model=name,source=str(mesh),sha256=sha(mesh),vertices=len(vertices),
        raw_aabb_extent_obj_units=np.ptp(vertices,axis=0).tolist(),pca_extent_obj_units=extents.tolist(),
        nominal_length_m=length,nominal_diameter_m=diameter,
        dimension_source=str(SRC/'historical-README.md'),
        length_only_candidate_scale_m_per_unit=float(s),
        length_only_scaled_pca_extent_m=(extents*s).tolist(),
        candidate_scale_status='diagnostic only: nominal dimensions do not establish scan extremum, rotation, origin, or damaged-object size',
        mesh_to_target=None,approved_for_gt=False,
        required=['metric scale or measured scan landmarks','longitudinal direction and transverse orientation','target origin corresponding to scan landmarks','independent per-recording pose and image controls']))
    draw.text((15,45+idx*315),f'{name} | nominal length {length:.3f} m | PCA extents {extents.round(3)} raw units',fill='black')
    step=max(1,len(local)//15000)
    for col,(ax,ay) in enumerate([(0,1),(0,2),(1,2)]):
        p=local[::step,[ax,ay]]; p-=p.min(0)
        zoom=min(365/max(np.ptp(p[:,0]),1e-9),245/max(np.ptp(p[:,1]),1e-9))
        for x,y in p*zoom:draw.point((int(20+col*405+x),int(95+idx*315+y)),fill=(35,85,135))
        draw.text((20+col*405,78+idx*315),f'PCA {ax+1}/{ay+1} (sign arbitrary)',fill='black')
canvas.save(OUT/'mesh-geometry.png')
save(OUT/'mesh-registration.json',dict(status='HOLD: source-backed mesh_to_target unavailable',
    public_history_model_asset_paths=[],zenodo_v1_asset_checksums=checks,models=registry))
after_hashes={p:sha(Path(p)) for p in previous_hashes}
after_repo=original_state()
assert before_hashes==after_hashes and before_repo==after_repo
save(OUT/'verification.json',dict(input_files=len(previous_hashes),input_hashes_unchanged=True,
    matches_previous_audit_hashes=True,original_repo_before=before_repo,original_repo_after=after_repo,
    historical_notebook_reproduced=True,independent_library_passed=True,
    only_changed_frame=changed,public_release_calibration_matches_archive=True,
    sonar_static_chain_unchanged=True,notebook_expected_values_present_in_historical_source=True,
    model_registration_approved=False,training_runs=0,new_gt_files=0,new_splits=0,
    test_sample_access=False,script_sha256=sha(Path(__file__))))
print(json.dumps(dict(versions={k:{x:v[x] for x in ['notebook_max_abs_error','notebook_rotation_error_deg','notebook_translation_error_m']} for k,v in versions.items()},
    models=[{k:v[k] for k in ['model','pca_extent_obj_units','length_only_candidate_scale_m_per_unit','length_only_scaled_pca_extent_m']} for v in registry]),indent=2))
