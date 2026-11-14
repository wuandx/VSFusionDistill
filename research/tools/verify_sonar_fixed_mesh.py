"""Independent numeric review of the frozen sonar_fixed_mesh pilot.

Reads the original YAML, OBJ, and allowed 18 frame metadata.  Does not import
or execute the generator and never fits mesh parameters or opens test images.
Writes only independent-verification.json. Audit-note revisions must be explicit
and preserve the previous report checksum and revision log.
"""
from pathlib import Path
import ast
import csv
import hashlib
import json
import math
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/_sonar_audit_deps'))
import numpy as np
import cv2
import yaml

OUT = ROOT / 'DataSet/sonar_fixed_mesh'
DEST = OUT / 'independent-verification.json'
previous_verifier_report = None
if DEST.exists():
    previous_verifier_report = json.loads(DEST.read_text(encoding='utf-8'))
    if '--revise-audit-notes' not in sys.argv:
        raise RuntimeError('Preserve the previous verification; use a separately named run')

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def quat_matrix(q):
    x, y, z, w = (float(q[k]) for k in 'xyzw')
    norm = math.sqrt(x*x + y*y + z*z + w*w)
    x, y, z, w = x/norm, y/norm, z/norm, w/norm
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])

def yaml_transform(node):
    matrix = np.eye(4)
    matrix[:3, :3] = quat_matrix(node['rotation'])
    matrix[:3, 3] = [node['translation'][k] for k in 'xyz']
    return matrix

def euler_xyz(angles):
    # Extrinsic xyz: rightmost rotation acts first on a column vector.
    r, p, y = np.deg2rad(angles)
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    return rz @ ry @ rx

def load_obj(path):
    vertices, faces = [], []
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            fields = line.split()
            if not fields:
                continue
            if fields[0] == 'v':
                vertices.append(list(map(float, fields[1:4])))
            elif fields[0] == 'f':
                indices = [int(field.split('/')[0]) for field in fields[1:]]
                indices = [i-1 if i > 0 else len(vertices)+i for i in indices]
                faces.extend((indices[0], indices[j], indices[j+1]) for j in range(1, len(indices)-1))
    return np.asarray(vertices), np.asarray(faces, dtype=int)

def column_from_angle(angles, beams):
    # Independent interpolation, including linear extrapolation at the edges.
    knots = np.concatenate(([beams[0, 1]], beams[:, 0], [beams[-1, 2]]))
    columns = np.concatenate(([0.], np.arange(len(beams))+.5, [float(len(beams))]))
    positions = np.searchsorted(knots, angles, side='right') - 1
    positions = np.clip(positions, 0, len(knots)-2)
    return columns[positions] + (angles-knots[positions]) * (columns[positions+1]-columns[positions]) / (knots[positions+1]-knots[positions])

def box(points, width=None, height=None):
    if len(points) == 0:
        return None
    value = np.r_[points.min(axis=0)-1, points.max(axis=0)+1]
    if width is not None:
        value[:2] = np.maximum(value[:2], [0, 0])
        value[2:] = np.minimum(value[2:], [width, height])
        if np.any(value[2:] <= value[:2]):
            return None
    return value

def difference(actual, expected):
    if actual is None or expected is None:
        assert actual is None and expected is None
        return 0.
    return float(np.max(np.abs(np.asarray(actual)-np.asarray(expected))))

selection_path = ROOT / 'DataSet/sonar_independent_registration/selection.json'
manifest_path = ROOT / 'DataSet/camera_temporal_all/manifest-resolved.json'
yaml_path = ROOT / 'related_work/sonar-projection-audit-assets/calibration__transforms.yaml'
beam_path = ROOT / 'related_work/uxo-upstream-history/scripts/common/aris_definitions.py'
polar_path = ROOT / 'related_work/uxo-upstream-history/scripts/prep_2_aris_to_polar.py'
release_path = ROOT / 'related_work/uxo-upstream-history/scripts/release_1_export.py'
viewer_path = ROOT / 'related_work/uxo-upstream-history/scripts/view_recording.py'
selection = read(selection_path)['samples']
allowed = {x['sample']: x for x in read(manifest_path)['items'] if x.get('paired_role') in ('train', 'val', 'val_id')}
result = read(OUT / 'results.json')
models = read(OUT / 'fixed-mesh-transforms.json')['models']
assert len(selection) == len(result['outputs']) == 18
assert set(x['sample'] for x in selection) == set(x['sample'] for x in result['outputs'])
assert len(set(x['recording'] for x in selection)) == 6
assert all(x['sample'] in allowed for x in selection)
assert result['fixed_transform_sha256'] == sha(OUT / 'fixed-mesh-transforms.json')
generation_inputs = read(OUT / 'inputs-before.json')
generation_input_mismatches = [p for p, value in generation_inputs.items() if sha(Path(p)) != value]
assert not generation_input_mismatches, generation_input_mismatches
tracked = set(map(Path, generation_inputs)) | {yaml_path, polar_path, release_path, viewer_path, OUT / 'fixed-mesh-transforms.json', OUT / 'results.json', Path(__file__)}
before = {str(p): sha(p) for p in tracked}
raw_yaml = yaml.safe_load(yaml_path.read_text(encoding='utf-8'))
transforms = {node['frame_id']: yaml_transform(node) for group in raw_yaml.values() for node in group}
beam_tables = {}
for node in ast.parse(beam_path.read_text(encoding='utf-8')).body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in ('BeamWidthsAris3000_64', 'BeamWidthsAris3000_128'):
                beam_tables[int(target.id.rsplit('_', 1)[-1])] = np.array(ast.literal_eval(node.value))

clouds, model_checks = {}, []
for name, saved in models.items():
    vertices, faces = load_obj(Path(saved['source']))
    # Eigenvectors of the covariance independently recover the frozen SVD axes.
    centered = vertices - vertices.mean(axis=0)
    values, eigenvectors = np.linalg.eigh(centered.T @ centered)
    rotation = eigenvectors[:, np.argsort(values)[::-1]].T
    for i in (0, 1):
        if rotation[i, i] < 0:
            rotation[i] *= -1
    rotation[2] = np.cross(rotation[0], rotation[1])
    local = vertices @ rotation.T
    scale = saved['nominal_length_m'] / np.ptp(local[:, 0])
    translation = -scale * (local.min(axis=0)+local.max(axis=0))/2
    expected = np.eye(4)
    expected[:3, :3] = scale*rotation
    expected[:3, 3] = translation
    sim = np.asarray(saved['mesh_to_target_similarity'])
    target = (sim @ np.column_stack([vertices, np.ones(len(vertices))]).T).T[:, :3]
    triangles = target[faces]
    # The same explicit surface set, in a distinct concatenation order.
    cloud = np.concatenate([triangles.mean(axis=1), (triangles[:, 1]+triangles[:, 2])/2,
                            (triangles[:, 2]+triangles[:, 0])/2, target, (triangles[:, 0]+triangles[:, 1])/2])
    clouds[name] = cloud
    model_checks.append(dict(model=name,similarity_rederived_max_abs_error=difference(expected, sim),
        rotation_orthogonality_error=difference(rotation@rotation.T, np.eye(3)), determinant=float(np.linalg.det(rotation)),
        length_error_m=abs(float(np.ptp(target[:, 0]))-saved['nominal_length_m']),
        extent_error_m=difference(np.ptp(target, axis=0), saved['target_mesh_extent_m']),
        midpoint_error_m=float(np.max(np.abs((target.min(axis=0)+target.max(axis=0))/2))),
        sampled_points=len(cloud),source_sha256_matches=sha(Path(saved['source'])) == saved['source_sha256'],
        eigenvalues_descending=values[::-1].tolist()))
    assert model_checks[-1]['similarity_rederived_max_abs_error'] < 1e-10
    assert model_checks[-1]['source_sha256_matches'] and len(cloud) == saved['sampled_surface_points']

cache, checks = {}, []
targets = {'100lbs': 'target/100lbs', 'incindiary': 'target/incendiary', 'mortar_shell': 'target/mortar_shell'}
for stored in result['outputs']:
    row = next(x for x in selection if x['sample'] == stored['sample'])
    if row['recording'] not in cache:
        # Read only frame rows belonging to the frozen allowed selection.
        wanted = {x['aris_frame'] for x in selection if x['recording'] == row['recording']}
        tables = []
        for field, key in [('meta_source', 'FrameIndex'), ('gantry_source', 'aris_frame_idx')]:
            with Path(row[field]).open(encoding='utf-8', newline='') as stream:
                tables.append({int(x[key]): x for x in csv.DictReader(stream) if int(x[key]) in wanted})
        cache[row['recording']] = tables
    metadata, gantry = [table[row['aris_frame']] for table in cache[row['recording']]]
    assert allowed[row['sample']]['aris_frame'] == row['aris_frame']
    assert int(metadata['FrameTime']) == stored['frame_time_us'] == allowed[row['sample']]['aris_time_us']
    world_ar3 = np.eye(4)
    world_ar3[:3, :3] = transforms['setup/ar3'][:3, :3] @ euler_xyz([float(metadata[k]) for k in ('SonarRoll', 'SonarTilt', 'SonarPan')])
    world_ar3[:3, 3] = [float(gantry[k]) for k in 'xyz']
    world_ar3[:3, 3] += transforms['setup/ar3'][:3, 3]
    world_sonar = world_ar3 @ transforms['setup/aris'] @ transforms['setup/sonar']
    # Analytic rigid inverse instead of generic matrix inversion.
    sonar_world = np.eye(4)
    sonar_world[:3, :3] = world_sonar[:3, :3].T
    sonar_world[:3, 3] = -world_sonar[:3, :3].T @ world_sonar[:3, 3]
    sonar_target = sonar_world @ transforms[targets[stored['model']]]
    cloud = clouds[stored['model']]
    points = (sonar_target @ np.column_stack([cloud, np.ones(len(cloud))]).T).T[:, :3]
    distances = np.sqrt(np.sum(points*points, axis=1))
    angles = np.degrees(np.arctan2(points[:, 0], points[:, 2]))
    elevation = np.degrees(np.arcsin(np.clip(points[:, 1]/distances, -1, 1)))
    height, width = stored['raw_shape_hw']
    assert height == int(metadata['SamplesPerBeam'])
    mode = int(metadata['PingMode'])
    official_beam_count = 48 if mode in (1, 2) else 96 if mode in (3, 4, 5) else 64 if mode in (6, 7, 8) else 128 if mode in (9, 10, 11, 12) else 0
    assert width == official_beam_count
    beams = beam_tables[width]
    interval = float(metadata['SoundSpeed']) * float(metadata['SamplePeriod']) / 2_000_000
    start = float(metadata['SoundSpeed']) * float(metadata['SampleStartDelay']) / 2_000_000
    end = start + height*interval
    pixels = np.column_stack([column_from_angle(angles, beams), (distances-start)/interval])
    horizontal = (points[:, 2] > 0) & (angles >= beams[0, 1]) & (angles <= beams[-1, 2]) & (distances >= start) & (distances <= end)
    visible = horizontal & (abs(elevation) <= 7)
    fw, fh = stored['fan_geometry']['width'], stored['fan_geometry']['height']
    fan = np.column_stack([fw/2-distances*np.sin(np.radians(angles))*200, fh-distances*np.cos(np.radians(angles))*200])
    boxes = {
        'full_surface_raw_bbox_padded_xyxy': box(pixels),
        'full_surface_raw_bbox_intersection_xyxy': box(pixels, width, height),
        'visible_raw_bbox_padded_clipped_xyxy': box(pixels[visible], width, height),
        'visible_fan_bbox_padded_clipped_xyxy': box(fan[visible], fw, fh)}
    numeric = {
        'world_from_ar3': world_ar3, 'world_from_sonar': world_sonar, 'sonar_from_world': sonar_world,
        'range_start_m': start, 'range_end_m': end, 'range_bin_m': interval,
        'mesh_range_m': [distances.min(), distances.max()],
        'mesh_azimuth_deg': [angles.min(), angles.max()],
        'mesh_elevation_deg': [elevation.min(), elevation.max()],
        'fraction_in_range_beam': horizontal.mean(), 'fraction_visible_assumed_7deg': visible.mean(),
        'fraction_visible_assumed_7_5deg': (horizontal & (abs(elevation) <= 7.5)).mean()}
    errors = {key: difference(value, stored[key]) for key, value in {**numeric, **boxes}.items()}
    assert max(errors.values()) < 1e-8, (row['sample'], errors)
    assert len(points) == stored['surface_sample_count']
    official_end = start + (height+1)*interval
    official_width = math.ceil(2*official_end*np.tan(np.radians((beams[-1, 2]-beams[0, 1])/2))*200)
    checks.append(dict(sample=row['sample'],errors=errors,all_numeric_comparisons_passed=True,
        canvas_local_wh=[fw, fh],canvas_official_polar2_wh_at_200px_per_m=[official_width, math.ceil(official_end*200)],
        official_canvas_extra_range_m=interval,window_start_field_difference_m=start-float(metadata['WindowStart']),
        visible_fraction_7deg=float(visible.mean()),visible_fraction_7_5deg=float((horizontal & (abs(elevation)<=7.5)).mean())))

# Execute just the public rasterizer on synthetic data, not release images.
polar_ast = ast.parse(polar_path.read_text(encoding='utf-8'))
polar_func = next(node for node in polar_ast.body if isinstance(node, ast.FunctionDef) and node.name == 'aris_frame_to_polar2')
scope = dict(np=np, cv2=cv2, BeamWidthsAris3000_64=beam_tables[64], BeamWidthsAris3000_128=beam_tables[128], get_beamcount_from_pingmode=lambda mode: 128)
exec(compile(ast.fix_missing_locations(ast.Module(body=[polar_func], type_ignores=[])), str(polar_path), 'exec'), scope)
class Metadata:
    def __init__(self, row):
        self.row = row
        self.iloc = self
    def __getitem__(self, index):
        return self.row

synthetic = np.zeros((3, 128), dtype=np.uint8)
synthetic[1, 0] = 79
synthetic[1, 127] = 183
rendered = scope['aris_frame_to_polar2'](synthetic, 0, Metadata(dict(PingMode=9, SamplesPerBeam=3, SoundSpeed=1500, SampleStartDelay=1000, SamplePeriod=20)), frame_res=1000)
negative_centroid = float(np.nonzero(rendered == 79)[1].mean())
positive_centroid = float(np.nonzero(rendered == 183)[1].mean())
assert positive_centroid < rendered.shape[1]/2 < negative_centroid
boundary_errors = {}
for width, beams in beam_tables.items():
    assert np.all(np.diff(beams[:, 0]) > 0)
    assert np.allclose(column_from_angle(beams[:, 0], beams), np.arange(width)+.5)
    boundary_errors[str(width)] = float(np.max(abs(column_from_angle(beams[:-1, 2], beams)-np.arange(1, width))))

assert all(sha(Path(path)) == value for path, value in before.items())
camera_relative_ar3 = transforms['setup/gopro_mounting_hole'] @ transforms['setup/gopro_mounting_axis'] @ transforms['setup/camera']
sonar_relative_ar3 = transforms['setup/aris'] @ transforms['setup/sonar']
revision_history = previous_verifier_report.get('verifier_revision_history', []) if previous_verifier_report else []
if previous_verifier_report:
    revision_history = revision_history + [dict(reason='Clarify that official raw-to-fan direction does not establish the physical sonar +x to beam-angle sign; no geometry parameters or generated results changed.',
        previous_report_sha256=sha(DEST), previous_maximum_numeric_difference=previous_verifier_report['maximum_saved_numeric_difference'])]
report = dict(
    run='sonar_fixed_mesh_independent_numeric_verification', passed=True,
    verifier_revision='physical beam sign remains unverified',verifier_revision_history=revision_history,
    scope='Software and saved-hypothesis replay; does not certify physical calibration, model registration, echo identity, or training labels',
    identities=18,recordings=6,models=3,test_images_read=0,parameter_fits=0,
    independent_methods=['YAML quaternion algebra','manual Rz Ry Rx extrinsic Euler matrix','analytic rigid inverse','homogeneous point projection','covariance eigendecomposition instead of SVD','arcsin elevation','piecewise scalar interpolation','original polar2 synthetic rasterizer'],
    fixed_transform_sha256=result['fixed_transform_sha256'],
    inputs_unchanged=True,generation_inputs_still_match=True,input_hashes=before,
    model_checks=model_checks,frame_checks=checks,
    maximum_saved_numeric_difference=max(max(x['errors'].values()) for x in checks),
    synthetic_controls=dict(official_polar2_direction_passed=True,negative_angle_image_column_centroid=negative_centroid,
        positive_angle_image_column_centroid=positive_centroid,synthetic_image_width=rendered.shape[1],
        range_bin_center_convention='range r0+(j+0.5)*dr maps to raw edge-coordinate row j+0.5',
        beam_center_convention='table center i maps to raw edge-coordinate column i+0.5',
        actual_internal_beam_boundary_vs_center_interpolation_max_error_columns=boundary_errors),
    physical_axis_review=dict(
        sonar_xyz_to_beam_physical_sign_validated=False,
        target_long_axis_x_is_officially_registered=False,
        camera_and_sonar_rotation_difference_current_yaml_max_abs=difference(camera_relative_ar3[:3, :3], sonar_relative_ar3[:3, :3]),
        public_fact='Official viewer states raw beams are ordered right to left; polar2 places increasing beam-table angle to the left.',
        inference='Current public calibration gives the sonar and camera identical rotation. If sonar +x is interpreted as standard camera-right, the beam-table angle should be -atan2(x,z), not the current +atan2(x,z). This is an unresolved coordinate-convention inconsistency, not a certified correction.',
        missing_control='An authoritative sonar-frame axis definition tied to beam index, or independent known 3D point and measured raw-beam correspondence.',
        action='Keep the current hypothesis and failures; do not claim that numerical replay ruled out a physical left-right sign error or attribute all visual mismatch to mesh registration.'),
    source_evidence=[
        dict(path=str(release_path),lines='19-35',finding='Gantry translation plus setup/ar3 offset; static rotation multiplied by extrinsic xyz Euler'),
        dict(path=str(polar_path),lines='156-171',finding='Range start uses delay; official display canvas extends to h+1 bins'),
        dict(path=str(polar_path),lines='174-207',finding='Angles negated before cos(angle+90), then horizontal flip; net positive angle is left'),
        dict(path=str(viewer_path),lines='178-180',finding='Official comment: In ARIS frames, beams are ordered right to left; viewer flips raw images'),
        dict(path=str(beam_path),lines='250-452',finding='Nonuniform center/left/right beam angle table')],
    limitations=[
        'The synthetic rasterizer control validates beam-index-to-display direction only. It does not validate mapping sonar xyz coordinates to physical beam angle. The current +atan2(x,z) sign remains unverified and may be inconsistent with the public camera/sonar axis alignment.',
        'Local fan is a display reconstruction, not the released polar2 image coordinate frame: h instead of h+1 outer canvas, max absolute angle instead of half full span, nearest-neighbor versus polygon fill.',
        'Ignoring raster rounding, official flip on pixel indices gives u=W/2-1-r*sin(az)*res. Local continuous edge convention uses u=W/2-r*sin(az)*res. Positive-angle-left direction agrees; a local fan box must not be transplanted to an official raster without coordinate conversion.',
        'Raw beam position is interpolated through beam centers. Actual internal table boundaries differ slightly from integer columns; the exact maximum is recorded. This is smaller than the candidate one-column pad, not a substitute for exact polygon clipping.',
        'Surface sampling plus one-bin/one-beam padding is not a proof of exact clipped mesh bounds. No analytic mesh-frustum intersection or acoustic scattering/occlusion/shadow model is used.',
        'Fractions count nonuniformly sampled mesh points; they are not surface-area visibility fractions or echo probabilities.',
        'Plus/minus 7 degree elevation, nominal intact length, PCA orientation/roll, midpoint origin, and one static target pose across recordings remain explicit hypotheses.'
    ])
DEST.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
print(json.dumps(dict(passed=report['passed'],identities=18,maximum_saved_numeric_difference=report['maximum_saved_numeric_difference'],model_checks=model_checks,synthetic_controls=report['synthetic_controls'],report=str(DEST)),ensure_ascii=False,indent=2))
