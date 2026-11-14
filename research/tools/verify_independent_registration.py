"""Independent homogeneous-matrix/library replay of saved local registration results."""
from pathlib import Path
import sys,json,csv,hashlib
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.optimize import least_squares
from pytransform3d.transform_manager import TransformManager
OUT=ROOT/'DataSet/sonar_independent_registration'
result=json.loads((OUT/'results.json').read_text(encoding='utf-8'))
selection=json.loads((OUT/'selection.json').read_text(encoding='utf-8'))['samples']
annotations=json.loads((OUT/'contours.json').read_text(encoding='utf-8'))['points']
versions=json.loads((ROOT/'DataSet/sonar_model_registration_consistency/calibration-versions.json').read_text(encoding='utf-8'))['versions']
K=np.array(result['K_sd']);a=np.arange(36)*np.pi/18;directions=np.column_stack([np.cos(a),np.sin(a)])
max_error=0;transform_error=0;checked=0;synthetic=[]
for output in result['outputs']:
    name=output['model'];version=output['version'];tf={k:np.array(v) for k,v in versions[version]['parent_from_child_matrices'].items()}
    model=ROOT/f'related_work/sonar-projection-audit-assets/data_export_3dmodels/3d_models/{name}.obj'
    v=np.array([[float(s) for s in line.split()[1:4]] for line in model.read_text().splitlines() if line.startswith('v ')])
    mesh=np.column_stack([v,np.ones(len(v))]);sim=np.array(output['best_start']['mesh_to_target_similarity'])
    target={'100lbs':'target/100lbs','incindiary':'target/incendiary','mortar_shell':'target/mortar_shell'}[name]
    projections=[]
    for control in output['controls']:
        row=next(r for r in selection if r['sample']==control['sample'])
        with Path(row['meta_source']).open(encoding='utf-8',newline='') as f:m=next(r for r in csv.DictReader(f) if int(r['FrameIndex'])==row['aris_frame'])
        with Path(row['gantry_source']).open(encoding='utf-8',newline='') as f:g=next(r for r in csv.DictReader(f) if int(r['aris_frame_idx'])==row['aris_frame'])
        world_ar3=np.eye(4);world_ar3[:3,3]=np.array([float(g[k]) for k in 'xyz'])+tf['setup/ar3'][:3,3]
        world_ar3[:3,:3]=tf['setup/ar3'][:3,:3]@Rotation.from_euler('xyz',[float(m[k]) for k in ['SonarRoll','SonarTilt','SonarPan']],degrees=True).as_matrix()
        tm=TransformManager()
        parents={'setup/aris':'setup/ar3','setup/sonar':'setup/aris','setup/gopro_mounting_hole':'setup/ar3',
                 'setup/gopro_mounting_axis':'setup/gopro_mounting_hole','setup/camera':'setup/gopro_mounting_axis'}
        for child,parent in parents.items():tm.add_transform(child,parent,tf[child])
        tm.add_transform('setup/ar3','world',world_ar3);tm.add_transform(target,'world',tf[target])
        camera_target=tm.get_transform(target,'setup/camera')
        explicit=np.linalg.inv(world_ar3@tf['setup/gopro_mounting_hole']@tf['setup/gopro_mounting_axis']@tf['setup/camera'])@tf[target]
        transform_error=max(transform_error,float(np.max(np.abs(explicit-camera_target))))
        projection=K@camera_target[:3,:];projections.append(projection)
        # Replay every vertex, independent of solver's PCA-centering and 3D convex-hull reduction.
        screen=(projection@sim@mesh.T).T;uv=screen[:,:2]/screen[:,2:3]
        if control['camera_available']:
            error=np.max(uv@directions.T,axis=0)-np.max(np.array(annotations[row['sample']])@directions.T,axis=0)
            replay=float(np.sqrt(np.mean(error**2)));max_error=max(max_error,abs(replay-control['support_rms_px']));checked+=1
    # Camera-ray triangulation sanity control, using an arbitrary known target-frame point.
    truth=np.array([.01,.02,.03,1.]);observed=[]
    for projection in projections[:2]:
        projected=projection@truth;observed.append(projected[:2]/projected[2])
    def residual(x):
        diffs=[]
        for projection,obs in zip(projections[:2],observed):
            p=projection@np.r_[x,1];diffs.extend(p[:2]/p[2]-obs)
        return diffs
    recovered=least_squares(residual,truth[:3]+[.02,-.02,.01],xtol=1e-12,ftol=1e-12,gtol=1e-12)
    err=float(np.linalg.norm(recovered.x-truth[:3]));synthetic.append(dict(model=name,version=version,triangulation_error_m=err))
assert max_error<1e-8 and transform_error<1e-10
assert all(s['triangulation_error_m']<1e-8 for s in synthetic)
summary=dict(replayed_camera_controls=checked,all_vertex_homogeneous_replay_max_rms_difference_px=max_error,
    pytransform3d_transform_max_difference=transform_error,synthetic_triangulation=synthetic,
    passed=True,note='Numerical implementation verification only; does not validate camera mode, calibration, contour semantics, or physical registration',
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(OUT/'independent-verification.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
