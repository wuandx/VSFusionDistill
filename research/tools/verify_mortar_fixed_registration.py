"""Independent replay for the authorized fixed-mortar registration pilot.

No optimizer or generator is imported. Geometry is reconstructed from public
YAML, selected source metadata and OBJ. Importing this file reads no data.
"""
from pathlib import Path
import ast
import argparse
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

FIT_IDS = ('2023-09-21_100927_0087', '2023-09-21_100927_0451', '2023-09-21_100927_0811')
CHECK_IDS = ('2023-09-21_101131_0103', '2023-09-21_101131_0509', '2023-09-21_101131_0909')
ALL_IDS = FIT_IDS + CHECK_IDS


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def quaternion_rotation(node):
    q = np.array([float(node[k]) for k in ('w', 'x', 'y', 'z')])
    q /= np.linalg.norm(q)
    w, x, y, z = q
    return np.array([
        [w*w+x*x-y*y-z*z, 2*(x*y-w*z), 2*(x*z+w*y)],
        [2*(x*y+w*z), w*w-x*x+y*y-z*z, 2*(y*z-w*x)],
        [2*(x*z-w*y), 2*(y*z+w*x), w*w-x*x-y*y+z*z],
    ])


def load_static_transforms(path):
    raw = yaml.safe_load(Path(path).read_text(encoding='utf-8'))
    transforms = {}
    for group in raw.values():
        for node in group:
            T = np.eye(4)
            T[:3, :3] = quaternion_rotation(node['rotation'])
            T[:3, 3] = [float(node['translation'][k]) for k in 'xyz']
            transforms[node['frame_id']] = T
    return transforms


def extrinsic_xyz(roll, tilt, pan):
    a, b, c = [float(v) * math.pi / 180 for v in (roll, tilt, pan)]
    ca, sa, cb, sb, cc, sc = math.cos(a), math.sin(a), math.cos(b), math.sin(b), math.cos(c), math.sin(c)
    # Expanded Rz(c) Ry(b) Rx(a), independent of scipy Rotation.
    return np.array([
        [cc*cb, cc*sb*sa-sc*ca, cc*sb*ca+sc*sa],
        [sc*cb, sc*sb*sa+cc*ca, sc*sb*ca-cc*sa],
        [-sb, cb*sa, cb*ca],
    ])


def sonar_transforms(metadata, gantry, statics):
    WA = np.eye(4)
    WA[:3, :3] = statics['setup/ar3'][:3, :3] @ extrinsic_xyz(
        metadata['SonarRoll'], metadata['SonarTilt'], metadata['SonarPan'])
    WA[:3, 3] = [float(gantry[k]) for k in 'xyz']
    WA[:3, 3] += statics['setup/ar3'][:3, 3]
    WS = WA @ statics['setup/aris'] @ statics['setup/sonar']
    SW = np.eye(4)
    SW[:3, :3] = WS[:3, :3].T
    SW[:3, 3] = -(SW[:3, :3] @ WS[:3, 3])
    return WA, WS, SW


def selected_csv_rows(path, index_key, indices):
    wanted = set(indices)
    with Path(path).open(encoding='utf-8', newline='') as stream:
        rows = {int(row[index_key]): row for row in csv.DictReader(stream)
                if int(row[index_key]) in wanted}
    assert set(rows) == wanted, (str(path), sorted(wanted-set(rows)))
    return rows


def load_obj(path):
    vertices, faces = [], []
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            fields = line.split()
            if not fields:
                continue
            if fields[0] == 'v':
                vertices.append([float(x) for x in fields[1:4]])
            elif fields[0] == 'f':
                ids = [int(x.split('/')[0]) for x in fields[1:]]
                ids = [i - 1 if i > 0 else len(vertices) + i for i in ids]
                faces.extend((ids[0], ids[j], ids[j+1]) for j in range(1, len(ids)-1))
    return np.asarray(vertices), np.asarray(faces, dtype=int)


def transform_points(points, matrix):
    homogeneous = np.column_stack((points, np.ones(len(points))))
    transformed = (np.asarray(matrix) @ homogeneous.T).T
    assert np.max(np.abs(transformed[:, 3] - 1)) < 1e-10
    return transformed[:, :3]


def surface_cloud(vertices, faces):
    tri = vertices[faces]
    # Deliberately distinct ordering from production; same documented surface set.
    return np.concatenate(((tri[:, 2]+tri[:, 0])/2, tri.mean(axis=1), vertices,
                           (tri[:, 0]+tri[:, 1])/2, (tri[:, 1]+tri[:, 2])/2))


def load_beam_tables(path):
    tables = {}
    for node in ast.parse(Path(path).read_text(encoding='utf-8')).body:
        if not isinstance(node, ast.Assign):
            continue
        for name in node.targets:
            if isinstance(name, ast.Name) and name.id in ('BeamWidthsAris3000_64', 'BeamWidthsAris3000_128'):
                tables[int(name.id.rsplit('_', 1)[1])] = np.array(ast.literal_eval(node.value), dtype=float)
    assert set(tables) == {64, 128}
    return tables


def raw_columns(angles, table):
    # Actual boundaries map to integers, official centers to half-integers.
    k = np.empty(2*len(table)+1)
    k[0:-1:2], k[1::2], k[-1] = table[:, 1], table[:, 0], table[-1, 2]
    assert np.all(np.diff(k) > 0)
    positions = np.clip(np.searchsorted(k, angles, side='right')-1, 0, len(k)-2)
    return positions/2 + .5*(angles-k[positions])/(k[positions+1]-k[positions])


def bbox(points, pad=1., width=None, height=None):
    if len(points) == 0:
        return None
    lo, hi = np.min(points, axis=0)-pad, np.max(points, axis=0)+pad
    if width is not None:
        lo = np.maximum(lo, [0., 0.])
        hi = np.minimum(hi, [float(width), float(height)])
    if np.any(hi <= lo):
        return None
    return np.r_[lo, hi]


def replay_projection(world_points, metadata, gantry, statics, tables, resolution=1000., elevation_limit=7., padding=0.):
    WA, WS, SW = sonar_transforms(metadata, gantry, statics)
    points = transform_points(world_points, SW)
    ranges = np.sqrt(np.einsum('ij,ij->i', points, points))
    beta = -np.arctan2(points[:, 0], points[:, 2]) * 180 / np.pi
    elevation = np.arcsin(np.clip(points[:, 1]/ranges, -1, 1)) * 180 / np.pi
    mode = int(metadata['PingMode'])
    width = 64 if mode in (6, 7, 8) else 128 if mode in (9, 10, 11, 12) else None
    assert width is not None, mode
    height = int(metadata['SamplesPerBeam'])
    table = tables[width]
    speed = float(metadata['SoundSpeed'])
    dr = float(metadata['SamplePeriod']) * speed / 2_000_000
    start = float(metadata['SampleStartDelay']) * speed / 2_000_000
    end = start + height*dr
    horizontal = ((points[:, 2] > 0) & (ranges >= start) & (ranges <= end)
                  & (beta >= table[0, 1]) & (beta <= table[-1, 2]))
    visible = horizontal & (np.abs(elevation) <= elevation_limit)
    uv_raw = np.column_stack((raw_columns(beta, table), (ranges-start)/dr))
    canvas_range = start + float(metadata['SamplePeriod'])*(height+1)*1e-6*speed/2
    H = math.ceil(canvas_range*resolution)
    W = math.ceil(2*canvas_range*math.tan((table[-1, 2]-table[0, 1])*math.pi/360)*resolution)
    theta = beta*math.pi/180
    uv_polar = np.column_stack((W/2-.5-ranges*np.sin(theta)*resolution, H+.5-ranges*np.cos(theta)*resolution))
    return dict(
        world_from_ar3=WA, world_from_sonar=WS, sonar_from_world=SW,
        raw_shape_hw=[height, width], polar_shape_hw=[H, W],
        range_start_m=start, range_end_m=end, range_bin_m=dr,
        mesh_range_m=[ranges.min(), ranges.max()],
        mesh_azimuth_deg=[beta.min(), beta.max()], mesh_elevation_deg=[elevation.min(), elevation.max()],
        surface_sample_count=len(points), fraction_in_range_beam=horizontal.mean(),
        fraction_visible_assumed_7deg=(horizontal & (np.abs(elevation)<=7)).mean(),
        fraction_visible_assumed_7_5deg=(horizontal & (np.abs(elevation)<=7.5)).mean(),
        full_surface_raw_bbox_padded_xyxy=bbox(uv_raw, padding),
        full_surface_raw_bbox_intersection_xyxy=bbox(uv_raw, padding, width, height),
        horizontal_raw_bbox=bbox(uv_raw[horizontal], padding, width, height),
        visible_raw_bbox_padded_clipped_xyxy=bbox(uv_raw[visible], padding, width, height),
        visible_raw_bbox_7_5deg=bbox(uv_raw[horizontal & (np.abs(elevation)<=7.5)], padding, width, height),
        visible_polar_bbox_padded_clipped_xyxy=bbox(uv_polar[visible], padding, W, H),
        horizontal_polar_bbox_padded_clipped_xyxy=bbox(uv_polar[horizontal], padding, W, H),
        _sonar_points=points, _raw_pixels=uv_raw, _polar_pixels=uv_polar,
        _horizontal_mask=horizontal, _visible_mask=visible,
    )


def max_difference(a, b):
    if a is None or b is None:
        assert a is None and b is None, (a, b)
        return 0.
    aa, bb = np.asarray(a), np.asarray(b)
    assert aa.shape == bb.shape, (aa.shape, bb.shape)
    return float(np.max(np.abs(aa-bb))) if aa.size else 0.


def independent_gaps(replay, observation):
    supports = replay['_raw_pixels'][replay['_visible_mask']]
    gaps = []
    for point in observation['points']:
        uv = np.asarray(point['raw_uv_edge'])
        tolerance = np.asarray(point.get('tolerance_uv', [1., 2.]))
        if len(supports) == 0:
            gaps.append(math.sqrt(2)*100.)
            continue
        # Brute-force minimum over every support; no producer KD tree.
        violations = np.maximum(np.abs((supports-uv)/tolerance)-1., 0.)
        gaps.append(float(np.sqrt(np.min(np.sum(violations*violations, axis=1)))))
    return np.array(gaps)


def assert_metric_replay(replay, saved):
    mapping = {
        'world_from_sonar': 'world_from_sonar',
        'mesh_range_m': 'range_m', 'mesh_azimuth_deg': 'beam_angle_deg',
        'mesh_elevation_deg': 'elevation_deg',
        'full_surface_raw_bbox_padded_xyxy': 'full_raw_bbox',
        'horizontal_raw_bbox': 'horizontal_raw_bbox',
        'visible_raw_bbox_padded_clipped_xyxy': 'visible_raw_bbox_7deg',
        'visible_raw_bbox_7_5deg': 'visible_raw_bbox_7_5deg',
        'visible_polar_bbox_padded_clipped_xyxy': 'visible_polar_bbox_7deg',
        'horizontal_polar_bbox_padded_clipped_xyxy': 'no_elevation_polar_bbox',
        'fraction_visible_assumed_7deg': 'visible_fraction',
    }
    errors = {actual: max_difference(replay[actual], saved[expected])
              for actual, expected in mapping.items()}
    errors['support_count'] = abs(int(replay['_visible_mask'].sum())-int(saved['support_count']))
    errors['horizontal_support_count'] = abs(int(replay['_horizontal_mask'].sum())-int(saved['horizontal_support_count']))
    geom = saved['geometry']
    for a, b in [('raw_shape_hw', 'raw_shape_hw'), ('polar_shape_hw', 'polar_shape_hw'),
                 ('range_start_m', 'range_start_m'), ('range_bin_m', 'sample_bin_m'),
                 ('range_end_m', 'last_sample_end_m')]:
        errors[a] = max_difference(replay[a], geom[b])
    assert max(errors.values()) < 1e-7, errors
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', type=Path, default=ROOT/'DataSet/mortar_fixed_registration')
    args = parser.parse_args()
    out = args.run_dir
    destination = out/'independent-fit-verification.json'
    if destination.exists():
        raise RuntimeError('Preserve the previous independent verification')
    frozen_path = out/'freeze-model.json'
    frozen = read_json(frozen_path)
    result_path = out/'fit-results.json'
    result = read_json(result_path)
    assert frozen['fit_results_sha256'] == digest(result_path)
    assert frozen['fit_samples'] == list(FIT_IDS) == result['fit_samples']
    assert frozen['check_samples_not_used'] == list(CHECK_IDS)
    assert result['check_observations_loaded'] is False
    assert result['check_images_loaded'] is False
    assert result['check_projections_generated'] is False
    assert frozen['check_used_for_selection'] is False
    assert result['test_access'] is False and result['new_formal_gt'] == 0 and result['training_runs'] == 0
    assert frozen['solver_sha256'] == digest(ROOT/'tools/fit_mortar_fixed_registration.py')
    observations_path = out/'observations/fit-observations.json'
    assert frozen['observation_sha256'] == digest(observations_path)
    observations = {f['sample']: f for f in read_json(observations_path)['frames']}
    assert set(observations) == set(FIT_IDS)
    assert all(observations[s]['role'] == 'fit' for s in FIT_IDS)
    assert len(frozen['candidates']) == len(result['candidates']) == 24
    selection_path = ROOT/'DataSet/sonar_independent_registration/selection.json'
    selection = {r['sample']: r for r in read_json(selection_path)['samples'] if r['sample'] in FIT_IDS}
    manifest_path = ROOT/'DataSet/camera_temporal_all/manifest-resolved.json'
    allowed = {r['sample']: r for r in read_json(manifest_path)['items']
               if r['sample'] in FIT_IDS and r.get('paired_role') in ('train', 'val', 'val_id')}
    assert set(allowed) == set(selection) == set(FIT_IDS)
    statics_path = ROOT/'related_work/sonar-projection-audit-assets/calibration__transforms.yaml'
    beam_path = ROOT/'related_work/uxo-upstream-history/scripts/common/aris_definitions.py'
    model = frozen['model']
    source_paths = {Path(p) for p in frozen['source_hashes']}
    source_paths |= {frozen_path, result_path, statics_path, beam_path, Path(__file__), out/'sampled-model-points.npy'}
    source_paths |= {Path(selection[s][f]) for s in FIT_IDS for f in ('gantry_source', 'meta_source')}
    historical_hash_errors = {p: dict(expected=h, actual=digest(p)) for p, h in frozen['source_hashes'].items() if digest(p) != h}
    assert not historical_hash_errors, historical_hash_errors
    before = {str(p): digest(p) for p in source_paths}
    statics = load_static_transforms(statics_path)
    tables = load_beam_tables(beam_path)
    vertices, faces = load_obj(model['obj_path'])
    assert digest(model['obj_path']) == model['obj_sha256']
    similarity = np.asarray(model['raw_obj_to_model_similarity'])
    local = transform_points(vertices, similarity)
    dense = surface_cloud(local, faces)
    sampled = np.load(out/'sampled-model-points.npy', allow_pickle=False)
    sample_bytes_hash = hashlib.sha256(np.ascontiguousarray(sampled, dtype='<f8').tobytes()).hexdigest()
    assert sample_bytes_hash == model['sampling']['sampled_model_points_sha256']
    assert len(sampled) == model['sampling']['sampled_point_count']
    assert len(dense) == model['sampling']['dense_point_count']
    scale = float(model['scale_m_per_obj_unit'])
    axes = similarity[:3, :3]/scale
    assert max_difference(axes@axes.T, np.eye(3)) < 1e-10
    assert abs(np.linalg.det(axes)-1) < 1e-10
    assert abs(np.ptp(local[:, 0])-.580) < 1e-10
    assert max_difference([local.min(0), local.max(0)], model['bounds_model_m']) < 1e-10
    assert max_difference(statics['target/mortar_shell'], frozen['official_world_from_target']) < 1e-10
    target_world = statics['target/mortar_shell']
    metadata = {}; gantry = {}
    for s in FIT_IDS:
        row = selection[s]
        metadata[s] = selected_csv_rows(row['meta_source'], 'FrameIndex', [row['aris_frame']])[row['aris_frame']]
        gantry[s] = selected_csv_rows(row['gantry_source'], 'aris_frame_idx', [row['aris_frame']])[row['aris_frame']]
        assert int(metadata[s]['FrameTime']) == allowed[s]['aris_time_us']
        assert row['aris_frame'] == allowed[s]['aris_frame']
    candidate_checks = []
    for candidate in frozen['candidates']:
        T = np.asarray(candidate['world_from_model'])
        p = candidate['final_parameters']
        initial_yaw, _, initial_roll = candidate['initial_yaw_pitch_roll_deg']
        rederived = np.eye(4)
        rederived[:3, :3] = extrinsic_xyz(initial_roll+p[5], p[4], initial_yaw+p[3])
        rederived[:3, 3] = target_world[:3, 3] + p[:3]
        matrix_errors = {
            'parameters_to_world_model': max_difference(T, rederived),
            'target_chain': max_difference(target_world@np.asarray(candidate['target_from_model']), T),
            'obj_chain': max_difference(T@similarity, candidate['world_from_obj_similarity']),
        }
        assert max(matrix_errors.values()) < 1e-10
        physical_bounds = [(0, -.35, .35), (1, -.35, .35), (2, -.20, .20), (4, -60., 60.)]
        bound_hit = any(min(abs(p[i]-lo), abs(hi-p[i])) < 1e-4 for i, lo, hi in physical_bounds)
        assert bound_hit == candidate['bound_hit']
        dense_saved = {x['sample']: x for x in candidate['fit_metrics_dense']}
        coarse_saved = {x['sample']: x for x in candidate['fit_metrics_coarse']}
        assert set(dense_saved) == set(coarse_saved) == set(FIT_IDS)
        world_dense = transform_points(dense, T)
        world_coarse = transform_points(sampled, T)
        checks = []
        for s in FIT_IDS:
            replay = replay_projection(world_dense, metadata[s], gantry[s], statics, tables)
            errors = assert_metric_replay(replay, dense_saved[s])
            coarse_replay = replay_projection(world_coarse, metadata[s], gantry[s], statics, tables)
            coarse_errors = assert_metric_replay(coarse_replay, coarse_saved[s])
            gaps = independent_gaps(coarse_replay, observations[s])
            gap_error = max_difference(gaps, [x['normalized_gap'] for x in coarse_saved[s]['point_residuals']])
            assert gap_error < 1e-7, (candidate['id'], s, gap_error)
            dense_gaps = independent_gaps(replay, observations[s])
            dense_gap_error = max_difference(dense_gaps, [x['normalized_gap'] for x in dense_saved[s]['point_residuals']])
            assert dense_gap_error < 1e-7, (candidate['id'], s, dense_gap_error)
            for values, saved in ((gaps, coarse_saved[s]), (dense_gaps, dense_saved[s])):
                loss_mean = np.mean(np.where(values <= 1., .5*values*values, values-.5))
                assert abs(loss_mean-saved['point_huber_mean']) < 1e-7
                assert abs(float(np.quantile(values, .95))-saved['point_gap_p95']) < 1e-7
                assert abs(float(values.max())-saved['point_gap_max']) < 1e-7
            checks.append(dict(sample=s, dense_errors=errors, coarse_errors=coarse_errors,
                               brute_force_coarse_gap_error=gap_error, brute_force_dense_gap_error=dense_gap_error))
        coarse_mean = float(np.mean([m['objective'] for m in coarse_saved.values()]))
        dense_mean = float(np.mean([m['objective'] for m in dense_saved.values()]))
        assert abs(coarse_mean-candidate['fit_objective']) < 1e-7
        assert abs(dense_mean-candidate['dense_fit_objective']) < 1e-7
        feasible = candidate['solver_success'] and not bound_hit and all(
            m['point_gap_p95'] <= 1. and m['point_gap_max'] <= 2. and
            all(abs(b['normalized_violation']) <= 1. for b in m['boundary_intervals'])
            for m in dense_saved.values())
        assert feasible == candidate['feasible_before_near_optimal_filter']
        candidate_checks.append(dict(id=candidate['id'], matrix_errors=matrix_errors, frame_checks=checks))
    best = min(frozen['candidates'], key=lambda c: c['fit_objective'])
    assert best['id'] == frozen['best_display_candidate_id']
    feasible = [c for c in frozen['candidates'] if c['feasible_before_near_optimal_filter']]
    best_feasible = min((c['fit_objective'] for c in feasible), default=None)
    expected_eligible = [c['id'] for c in feasible if c['fit_objective'] <= best_feasible+.25] if feasible else []
    assert expected_eligible == frozen['eligible_candidate_ids']
    assert before == {p: digest(p) for p in before}
    report = dict(
        run='mortar_fixed_registration_independent_fit_verification', passed=True,
        scope='Independent replay of frozen fit outputs, not physical calibration or GT certification',
        fit_samples=list(FIT_IDS), fit_candidate_count=len(candidate_checks), check_images_read=0,
        check_projections_recomputed=0, test_access=False, optimizer_runs=0,
        freeze_model_sha256=digest(frozen_path), fit_results_sha256=digest(result_path),
        inputs_unchanged=True, generation_inputs_still_match=True, input_hashes=before,
        model_checks=dict(fixed_length_m=.580, rigid_axes_verified=True, sampled_points_hash_matches=True,
                          dense_surface_point_count=len(dense), source_obj_hash_matches=True),
        candidate_checks=candidate_checks, eligible_candidate_ids=expected_eligible,
        best_display_candidate_id=best['id'],
        independent_methods=['raw YAML quaternion expansion', 'expanded extrinsic XYZ matrix',
                             'analytic rigid inverse', 'homogeneous point projection',
                             'arcsin elevation', 'actual beam-edge and center interpolation',
                             'brute-force anisotropic rectangle support gaps without KD tree'],
        limitations=['Replay validates saved computation, not real target identity or unique registration.',
                     'Surface samples approximate continuous geometry and elevation limits are assumptions.',
                     'Source metadata and frozen model were checked; no independent physical calibration was introduced.'])
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(passed=True, candidates=len(candidate_checks), frames=3, report=str(destination)), ensure_ascii=False))


if __name__ == '__main__':
    main()
