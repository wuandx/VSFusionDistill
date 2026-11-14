"""Independently replay the sign-only candidate while preserving the baseline."""
from pathlib import Path
import ast
import copy
import csv
import hashlib
import json
import math
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/_sonar_audit_deps'))
import numpy as np
import yaml

BASE = ROOT / 'DataSet/sonar_fixed_mesh'
OUT = ROOT / 'DataSet/sonar_fixed_mesh_beam_sign'
DEST = OUT / 'independent-verification.json'
if DEST.exists():
    raise RuntimeError('Preserve the completed report; do not silently overwrite')

# Reuse only pure, independently written algebra helpers. No generator code runs.
helper_path = ROOT / 'tools/verify_sonar_fixed_mesh.py'
names = {'read', 'sha', 'quat_matrix', 'yaml_transform', 'euler_xyz', 'load_obj', 'column_from_angle', 'box', 'difference'}
helper_ast = ast.parse(helper_path.read_text(encoding='utf-8'))
helper_functions = [node for node in helper_ast.body if isinstance(node, ast.FunctionDef) and node.name in names]
assert len(helper_functions) == len(names)
exec(compile(ast.fix_missing_locations(ast.Module(body=helper_functions, type_ignores=[])), str(helper_path), 'exec'))

base_result = read(BASE / 'results.json')
result = read(OUT / 'results.json')
assert (BASE / 'fixed-mesh-transforms.json').read_bytes() == (OUT / 'fixed-mesh-transforms.json').read_bytes()
assert result['fixed_transform_sha256'] == base_result['fixed_transform_sha256'] == sha(BASE / 'fixed-mesh-transforms.json')
assert result['beam_azimuth_formula'] == '-degrees(atan2(sonar_x,sonar_z))'
old_outputs = {x['sample']: x for x in base_result['outputs']}
new_outputs = {x['sample']: x for x in result['outputs']}
assert old_outputs.keys() == new_outputs.keys() and len(new_outputs) == 18

baseline_script = ROOT / 'tools/project_fixed_mesh_to_sonar.py'
candidate_script = ROOT / 'tools/project_fixed_mesh_beam_sign.py'
def frame_loop(path):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    return next(node for node in tree.body if isinstance(node, ast.For) and isinstance(node.target, ast.Name) and node.target.id == 'row')
old_loop, new_loop = frame_loop(baseline_script), copy.deepcopy(frame_loop(candidate_script))
az_assignment = next(node for node in new_loop.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'az' for target in node.targets))
assert isinstance(az_assignment.value, ast.UnaryOp) and isinstance(az_assignment.value.op, ast.USub)
az_assignment.value = az_assignment.value.operand
assert ast.dump(old_loop, include_attributes=False) == ast.dump(new_loop, include_attributes=False)

selection_path = ROOT / 'DataSet/sonar_independent_registration/selection.json'
manifest_path = ROOT / 'DataSet/camera_temporal_all/manifest-resolved.json'
yaml_path = ROOT / 'related_work/sonar-projection-audit-assets/calibration__transforms.yaml'
beam_path = ROOT / 'related_work/uxo-upstream-history/scripts/common/aris_definitions.py'
rows = read(selection_path)['samples']
assert {row['sample'] for row in rows} == old_outputs.keys()
allowed = {x['sample']: x for x in read(manifest_path)['items'] if x.get('paired_role') in ('train', 'val', 'val_id')}
assert all(row['sample'] in allowed for row in rows)
tracked = set(map(Path, read(OUT / 'inputs-before.json'))) | {
    helper_path, Path(__file__), yaml_path, baseline_script, candidate_script,
    BASE / 'results.json', BASE / 'fixed-mesh-transforms.json', BASE / 'independent-verification.json',
    OUT / 'results.json', OUT / 'fixed-mesh-transforms.json'}
for row in rows:
    tracked |= {directory / 'frames' / (row['sample']+'-'+suffix+'.png') for directory in (BASE, OUT) for suffix in ('raw', 'fan')}
before = {str(path): sha(path) for path in tracked}
assert all(sha(Path(path)) == value for path, value in read(OUT / 'inputs-before.json').items())
assert all(sha(Path(path)) == value for path, value in read(BASE / 'inputs-before.json').items())

raw_yaml = yaml.safe_load(yaml_path.read_text(encoding='utf-8'))
transforms = {node['frame_id']: yaml_transform(node) for group in raw_yaml.values() for node in group}
beam_tables = {}
for node in ast.parse(beam_path.read_text(encoding='utf-8')).body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in ('BeamWidthsAris3000_64', 'BeamWidthsAris3000_128'):
                beam_tables[int(target.id.rsplit('_', 1)[-1])] = np.array(ast.literal_eval(node.value))
models = read(BASE / 'fixed-mesh-transforms.json')['models']
clouds = {}
for name, model in models.items():
    vertices, faces = load_obj(Path(model['source']))
    sim = np.asarray(model['mesh_to_target_similarity'])
    target = (sim @ np.column_stack([vertices, np.ones(len(vertices))]).T).T[:, :3]
    triangle = target[faces]
    clouds[name] = np.concatenate([triangle.mean(axis=1), (triangle[:, 0]+triangle[:, 2])/2,
                                  target, (triangle[:, 0]+triangle[:, 1])/2, (triangle[:, 1]+triangle[:, 2])/2])
    assert len(clouds[name]) == model['sampled_surface_points']
targets = {'100lbs': 'target/100lbs', 'incindiary': 'target/incendiary', 'mortar_shell': 'target/mortar_shell'}
cache, checks = {}, []
invariant_keys = ['sample', 'recording', 'category', 'model', 'historical_role', 'prior_geometry_role',
    'raw_sonar_source', 'raw_shape_hw', 'gantry_xyz_m', 'aris_roll_tilt_pan_deg', 'frame_time_us',
    'world_from_ar3', 'world_from_sonar', 'sonar_from_world', 'range_bin_m', 'range_start_m',
    'window_start_field_m', 'range_start_field_difference_m', 'range_end_m', 'beam_azimuth_extent_deg',
    'mesh_range_m', 'mesh_elevation_deg', 'surface_sample_count', 'fan_geometry', 'approved_for_training_gt']
for row in rows:
    sample = row['sample']
    old, new = old_outputs[sample], new_outputs[sample]
    assert all(old[key] == new[key] for key in invariant_keys)
    assert new['mesh_azimuth_deg'] == [-old['mesh_azimuth_deg'][1], -old['mesh_azimuth_deg'][0]]
    assert old['full_surface_raw_bbox_padded_xyxy'][1::2] == new['full_surface_raw_bbox_padded_xyxy'][1::2]
    image_checks = {suffix: sha(BASE/'frames'/(sample+'-'+suffix+'.png')) == sha(OUT/'frames'/(sample+'-'+suffix+'.png')) for suffix in ('raw', 'fan')}
    assert all(image_checks.values())
    if row['recording'] not in cache:
        wanted = {r['aris_frame'] for r in rows if r['recording'] == row['recording']}
        tables = []
        for field, key in [('meta_source', 'FrameIndex'), ('gantry_source', 'aris_frame_idx')]:
            with Path(row[field]).open(encoding='utf-8', newline='') as stream:
                tables.append({int(x[key]): x for x in csv.DictReader(stream) if int(x[key]) in wanted})
        cache[row['recording']] = tables
    metadata, gantry = [table[row['aris_frame']] for table in cache[row['recording']]]
    assert row['aris_frame'] == allowed[sample]['aris_frame']
    assert int(metadata['FrameTime']) == new['frame_time_us'] == allowed[sample]['aris_time_us']
    world_ar3 = np.eye(4)
    world_ar3[:3, :3] = transforms['setup/ar3'][:3, :3] @ euler_xyz([float(metadata[k]) for k in ('SonarRoll', 'SonarTilt', 'SonarPan')])
    world_ar3[:3, 3] = np.array([float(gantry[k]) for k in 'xyz']) + transforms['setup/ar3'][:3, 3]
    world_sonar = world_ar3 @ transforms['setup/aris'] @ transforms['setup/sonar']
    sonar_world = np.eye(4)
    sonar_world[:3, :3] = world_sonar[:3, :3].T
    sonar_world[:3, 3] = -world_sonar[:3, :3].T @ world_sonar[:3, 3]
    sonar_target = sonar_world @ transforms[targets[new['model']]]
    cloud = clouds[new['model']]
    points = (sonar_target @ np.column_stack([cloud, np.ones(len(cloud))]).T).T[:, :3]
    ranges = np.sqrt(np.sum(points*points, axis=1))
    angles = -np.degrees(np.arctan2(points[:, 0], points[:, 2]))
    elevation = np.degrees(np.arcsin(np.clip(points[:, 1]/ranges, -1, 1)))
    height, width = new['raw_shape_hw']
    beams = beam_tables[width]
    dr = float(metadata['SoundSpeed'])*float(metadata['SamplePeriod'])/2_000_000
    r0 = float(metadata['SoundSpeed'])*float(metadata['SampleStartDelay'])/2_000_000
    r1 = r0+height*dr
    pixels = np.column_stack([column_from_angle(angles, beams), (ranges-r0)/dr])
    in_range = (points[:, 2] > 0) & (ranges >= r0) & (ranges <= r1)
    horizontal = in_range & (angles >= beams[0, 1]) & (angles <= beams[-1, 2])
    old_horizontal = in_range & (-angles >= beams[0, 1]) & (-angles <= beams[-1, 2])
    visible = horizontal & (abs(elevation) <= 7)
    old_visible = old_horizontal & (abs(elevation) <= 7)
    fw, fh = new['fan_geometry']['width'], new['fan_geometry']['height']
    fan = np.column_stack([fw/2-ranges*np.sin(np.radians(angles))*200, fh-ranges*np.cos(np.radians(angles))*200])
    recomputed = {
        'world_from_ar3': world_ar3, 'world_from_sonar': world_sonar, 'sonar_from_world': sonar_world,
        'range_start_m': r0, 'range_end_m': r1, 'range_bin_m': dr,
        'mesh_range_m': [ranges.min(), ranges.max()], 'mesh_azimuth_deg': [angles.min(), angles.max()],
        'mesh_elevation_deg': [elevation.min(), elevation.max()],
        'fraction_in_range_beam': horizontal.mean(), 'fraction_visible_assumed_7deg': visible.mean(),
        'fraction_visible_assumed_7_5deg': (horizontal & (abs(elevation) <= 7.5)).mean(),
        'full_surface_raw_bbox_padded_xyxy': box(pixels),
        'full_surface_raw_bbox_intersection_xyxy': box(pixels, width, height),
        'visible_raw_bbox_padded_clipped_xyxy': box(pixels[visible], width, height),
        'visible_fan_bbox_padded_clipped_xyxy': box(fan[visible], fw, fh)}
    errors = {key: difference(value, new[key]) for key, value in recomputed.items()}
    assert max(errors.values()) < 1e-8, (sample, errors)
    assert abs(old_horizontal.mean()-old['fraction_in_range_beam']) < 1e-12
    assert abs(old_visible.mean()-old['fraction_visible_assumed_7deg']) < 1e-12
    assert new['range_beam_truncated'] == bool(not horizontal.all())
    assert new['vertical_gate_removes_points'] == bool(np.any(horizontal & ~visible))
    assert new['status'] == ('candidate_visible' if visible.any() else 'no_visible_surface_under_assumptions')
    checks.append(dict(sample=sample,all_invariant_fields_equal=True,azimuth_bounds_exactly_negated=True,
        raw_and_fan_image_hashes_equal=image_checks,independent_numeric_errors=errors,
        horizontal_mask_changed_points=int(np.count_nonzero(horizontal != old_horizontal)),
        visible_mask_changed_points=int(np.count_nonzero(visible != old_visible)),
        visible_fraction_delta=float(visible.mean()-old_visible.mean()),
        fov_difference_reason='The table endpoints are asymmetric. Reversing beam angle changes admission near the outer beam edges; range and elevation tests are unchanged.'))

assert all(sha(Path(path)) == value for path, value in before.items())
report = dict(run='sonar_fixed_mesh_beam_sign_independent_verification',passed=True,
    scope='One sign-only implementation revision and software replay; not physical registration or GT certification',
    identities=18,recordings=6,models=3,
    fixed_mesh_json_byte_identical=True,fixed_transform_sha256=result['fixed_transform_sha256'],
    per_frame_loop_ast_identical_after_removing_single_azimuth_minus=True,
    invariant_output_fields=invariant_keys,
    input_hashes=before,baseline_and_candidate_inputs_unchanged=True,
    raw_and_fan_images_byte_identical_across_versions=True,
    maximum_independent_numeric_difference=max(max(x['independent_numeric_errors'].values()) for x in checks),
    maximum_absolute_visible_fraction_delta=max(abs(x['visible_fraction_delta']) for x in checks),
    points_3d_invariance_evidence='Frozen mesh file is byte-identical, pose outputs match exactly, and per-frame loop AST before the angle calculation is identical. The independently rebuilt point cloud and homogeneous pose projection are common to both versions.',
    frame_checks=checks,
    axis_evidence_source=str(BASE/'independent-verification.json'),
    limitations=['Beam sign revision is consistent with the public right-to-left beam order if the supplied sonar frame shares the standard optical camera convention. No measured point-to-beam control certifies that interpretation.',
                 'Both versions use the same unverified target origin, long-axis/roll assumptions, nominal dimensions, static target pose and elevation gate. Numerical agreement cannot establish echo identity.',
                 'Visibility fractions count sampled points, not surface area. Boxes approximate the sampled surface and are not acoustic scattering masks.',
                 'Local fan coordinates differ from the public polygon rasterizer coordinates and cannot be transplanted directly.'],
    parameter_fits=0,new_training_labels=0,test_images_read=0)
DEST.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
print(json.dumps(dict(passed=True,identities=18,fixed_mesh_json_byte_identical=True,
    per_frame_loop_ast_only_azimuth_minus=True,
    maximum_numeric_difference=report['maximum_independent_numeric_difference'],
    maximum_absolute_visible_fraction_delta=report['maximum_absolute_visible_fraction_delta']),indent=2))
