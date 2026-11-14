"""Independent numerical replay of the frozen 120-frame development evaluation.

No evaluator, DatasetSource, Geometry, optimizer or image decoder is imported.
The official YAML and literal upstream beam tables are the owning inputs.
"""
from pathlib import Path
import ast
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/_sonar_audit_deps'))
import numpy as np
import yaml

OUT = ROOT / 'DataSet/sonar_fixed_registration_refinement'
MODELS = ('100lbs', 'incindiary', 'mortar_shell')
CATEGORY_MODEL = {'100lbs_aircraft_bomb': '100lbs',
                  'incindiary_grenade': 'incindiary', 'mortar_shell': 'mortar_shell'}
MODEL_TARGET = {'100lbs': 'target/100lbs', 'incindiary': 'target/incendiary',
                'mortar_shell': 'target/mortar_shell'}
FITS = {'2023-09-20_171105': [622, 981, 1336],
        '2023-09-21_100927': [87, 451, 811],
        '2023-09-21_120653': [163, 551, 933]}
REPLAY_CHECK_RECORDINGS = {'2023-09-20_173329', '2023-09-21_160551',
                           '2023-09-21_101131', '2023-09-21_110411',
                           '2023-09-21_120912', '2023-09-21_125048'}
MATRIX_TOL = 1e-11
BBOX_TOL = 1e-8


def read(path):
    return json.loads(Path(path).read_text('utf-8-sig'))


def fingerprint(path):
    p = Path(path)
    if not p.exists():
        return {'exists': False, 'bytes': 0, 'sha256': None}
    blob = p.read_bytes()
    return {'exists': True, 'bytes': len(blob),
            'sha256': hashlib.sha256(blob).hexdigest()}


def maxerr(a, b):
    return float(np.max(np.abs(np.asarray(a) - np.asarray(b))))


def xyz_rotation(roll, pitch, yaw):
    r, p, y = map(math.radians, (roll, pitch, yaw))
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    rx = np.array([[1., 0., 0.], [0., cr, -sr], [0., sr, cr]])
    ry = np.array([[cp, 0., sp], [0., 1., 0.], [-sp, 0., cp]])
    rz = np.array([[cy, -sy, 0.], [sy, cy, 0.], [0., 0., 1.]])
    return rz @ ry @ rx


def official_matrices(path):
    data = yaml.safe_load(Path(path).read_text('utf-8'))
    result = {}
    for group in data.values():
        for frame in group:
            q = frame['rotation']
            x, y, z, w = [float(q[k]) for k in 'xyzw']
            assert abs(x*x+y*y+z*z+w*w-1) < 1e-12
            t = np.eye(4)
            t[:3, :3] = [[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                         [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                         [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]
            t[:3, 3] = [float(frame['translation'][k]) for k in 'xyz']
            result[frame['frame_id']] = t
    return result


def beam_tables(path):
    tree = ast.parse(Path(path).read_text('utf-8-sig'))
    result = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('BeamWidthsAris3000_64', 'BeamWidthsAris3000_128'):
                    result[int(target.id.rsplit('_', 1)[1])] = np.asarray(ast.literal_eval(node.value))
    assert set(result) == {64, 128}
    return result


def geometry(meta, tables):
    mode = int(meta['PingMode'])
    assert mode in (6, 7, 8, 9, 10, 11, 12)
    w = 64 if mode in (6, 7, 8) else 128
    h = int(meta['SamplesPerBeam'])
    speed = float(meta['SoundSpeed'])
    r0 = float(meta['SampleStartDelay']) * 1e-6 * speed / 2
    dr = float(meta['SamplePeriod']) * 1e-6 * speed / 2
    table = tables[w]
    # Knots alternate lower boundary and beam centre, with the final upper boundary.
    angles = np.empty(2*w+1)
    angles[:-1:2] = table[:, 1]
    angles[1::2] = table[:, 0]
    angles[-1] = table[-1, 2]
    assert np.all(np.diff(angles) > 0)
    return {'w': w, 'h': h, 'r0': r0, 'dr': dr, 'rmax': r0+h*dr, 'angles': angles}


def dense_obj(path):
    vertices, faces = [], []
    for line in Path(path).read_text('utf-8').splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0] == 'v':
            vertices.append([float(v) for v in fields[1:4]])
        elif fields[0] == 'f':
            indices = [int(v.split('/')[0]) for v in fields[1:]]
            indices = [v-1 if v > 0 else len(vertices)+v for v in indices]
            faces.extend((indices[0], indices[i], indices[i+1]) for i in range(1, len(indices)-1))
    v = np.asarray(vertices)
    tri = v[np.asarray(faces)]
    pts = np.concatenate((v, tri.sum(axis=1)/3, (tri[:, 0]+tri[:, 1])/2,
                          (tri[:, 1]+tri[:, 2])/2, (tri[:, 2]+tri[:, 0])/2))
    return np.c_[pts, np.ones(len(pts))], len(v), len(faces)


def raw_projection(homogeneous_points, sonar_from_obj, g):
    # One homogeneous composition rather than the evaluator's staged point transforms.
    p = (sonar_from_obj @ homogeneous_points.T)[:3].T
    r = np.sqrt(np.sum(p*p, axis=1))
    angle = -np.arctan2(p[:, 0], p[:, 2]) * (180/math.pi)
    elevation = np.arctan2(p[:, 1], np.sqrt(p[:, 0]**2+p[:, 2]**2)) * (180/math.pi)
    keep = (p[:, 2] > 0) & (r >= g['r0']) & (r <= g['rmax'])
    keep &= (angle >= g['angles'][0]) & (angle <= g['angles'][-1]) & (np.abs(elevation) <= 7.)
    if not keep.any():
        return {'bbox_xyxy': None, 'visible_point_count': 0, 'surface_count': len(p)}
    a = angle[keep]
    k = np.clip(np.searchsorted(g['angles'], a, side='right')-1, 0, len(g['angles'])-2)
    u = (k+(a-g['angles'][k])/(g['angles'][k+1]-g['angles'][k]))/2
    v = (r[keep]-g['r0'])/g['dr']
    bounds = [max(0., float(u.min())), max(0., float(v.min())),
              min(float(g['w']), float(u.max())), min(float(g['h']), float(v.max()))]
    box = bounds if bounds[2] > bounds[0] and bounds[3] > bounds[1] else None
    return {'bbox_xyxy': box, 'visible_point_count': int(keep.sum()), 'surface_count': len(p)}


def main():
    output = OUT / 'expanded-numeric-verification.json'
    if output.exists():
        raise RuntimeError('Preserve existing verification; choose a separate revision instead')
    selection_path = OUT / 'evaluation-selection.json'
    selection = read(selection_path)
    manifest_path = ROOT / 'DataSet/camera_temporal_all/manifest-resolved.json'
    manifest = read(manifest_path)
    old_path = ROOT / 'DataSet/sonar_fixed_mesh/fixed-mesh-transforms.json'
    old_models = read(old_path)['models']
    yaml_path = ROOT / 'related_work/model-registration-sources/current-transforms.yaml'
    beam_path = ROOT / 'related_work/uxo-upstream-history/scripts/common/aris_definitions.py'
    official = official_matrices(yaml_path)
    tables = beam_tables(beam_path)
    protected = {old_path, manifest_path, yaml_path, beam_path, selection_path,
                 OUT / 'delivery-verification.json', Path(__file__),
                 ROOT / 'tools/evaluate_sonar_registration_refinement.py',
                 ROOT / 'tools/sonar_manual_curation_server.py',
                 ROOT / 'DataSet/mortar_fixed_registration/freeze-model.json',
                 ROOT / 'DataSet/mortar_fixed_registration/fit-results.json',
                 ROOT / 'DataSet/mortar_fixed_registration/numerical-controls.json',
                 ROOT / 'DataSet/sonar_initial_candidate_audit/floor-target-fix-verification.json',
                 ROOT / 'DataSet/sonar_manual_curation/reviews.jsonl'}
    protected.update((ROOT / 'DataSet/sonar_fixed_mesh').glob('*.json'))
    evaluations, freezes = {}, {}
    source_expectations = {}

    def expect(path, sha, size=None):
        path = Path(path).resolve()
        prior = source_expectations.get(path)
        if prior:
            assert prior['sha256'] == sha
            assert size is None or prior['bytes'] is None or prior['bytes'] == size
        source_expectations[path] = {'sha256': sha, 'bytes': size if size is not None else (prior or {}).get('bytes')}
        protected.add(path)

    expect(manifest_path, selection['manifest']['sha256'])
    expect(yaml_path, 'db99ddb4153a71011b6c2563da706bd7b6f6626681dd861641c4aecb5fd7a560')
    for model in MODELS:
        ep = OUT / model / 'evaluation-results.json'
        fp = OUT / model / 'freeze-model.json'
        evaluations[model], freezes[model] = read(ep), read(fp)
        protected.update((ep, fp))
        ev = evaluations[model]
        expect(fp, ev['freeze_sha256'])
        expect(selection_path, ev['selection_sha256'])
        expect(ROOT / 'tools/evaluate_sonar_registration_refinement.py', ev['script_sha256'])
        expect(old_models[model]['source'], old_models[model]['source_sha256'])
        for path, sha in freezes[model]['source_hashes'].items():
            expect(path, sha)
        for frame in ev['frames']:
            for p in frame['provenance'].values():
                if p:
                    expect(p['path'], p['sha256'], p['bytes'])
    before = {str(p): fingerprint(p) for p in sorted(protected)}
    issues = []

    def check(condition, description):
        if not condition:
            issues.append(description)

    for path, expected in source_expectations.items():
        actual = before[str(path)]
        check(actual['exists'] and actual['sha256'] == expected['sha256'], f'Source hash: {path}')
        check(expected['bytes'] is None or actual['bytes'] == expected['bytes'], f'Source size: {path}')
    if issues:
        raise RuntimeError('Source verification failed before projection: '+repr(issues))

    rows = {r['sample']: r for r in manifest['items']}
    recordings = defaultdict(list)
    for row in rows.values():
        assert row.get('paired_role') in (None, 'train', 'val', 'val_id')
        recordings[row['recording']].append(row)
    assert len(rows) == len(manifest['items']) == 26761
    assert len(recordings) == 40
    assert set(recordings) == set(manifest['identity']['recordings'])
    selected = {s['sample']: s for s in selection['samples']}
    expected_ids = set()
    for rec, members in recordings.items():
        members.sort(key=lambda r: int(r['aris_frame']))
        indices = FITS[rec] if rec in FITS else [members[0]['aris_frame'], members[len(members)//2]['aris_frame'], members[-1]['aris_frame']]
        expected_ids.update(f'{rec}_{i:04d}' for i in indices)
    check(len(selected) == 120 and set(selected) == expected_ids, '120-frame preregistered selection')
    frames = [f for ev in evaluations.values() for f in ev['frames']]
    check(len(frames) == 120 and {f['sample'] for f in frames} == expected_ids, 'Evaluation exact membership')
    check(Counter(f['role'] for f in frames) == {'fit': 9, 'development_check': 111}, 'Role counts')
    check(all(v == 3 for v in Counter(f['recording'] for f in frames).values()), 'Three frames per recording')
    for model, ev in evaluations.items():
        check(ev['frame_count'] == len(ev['frames']), f'{model} frame count')
        check(ev['old_bbox_padding'] == ev['new_bbox_padding'] == 0, f'{model} zero padding')
        check(ev['new_formal_gt'] == ev['user_reviews_written'] == 0, f'{model} no GT/review writes')

    class_checks = []
    for model, frozen in freezes.items():
        sim = np.asarray(frozen['raw_obj_to_model_similarity'])
        old = old_models[model]
        check(np.array_equal(sim, np.asarray(old['mesh_to_target_similarity'])), f'{model} fixed similarity')
        check(maxerr(old['world_from_target'], official[MODEL_TARGET[model]]) < MATRIX_TOL, f'{model} original target')
        check(frozen['fixed_imaging'] == {'beta': '-degrees(atan2(x,z))', 'main_elevation_limit_deg': 7.0,
                                        'raw_bbox_padding': 0.0, 'polar_bbox_padding': 0.0}, f'{model} imaging convention')
        errors = []
        for candidate in frozen['candidates']:
            dx, dy, dz, yaw, pitch, roll = candidate['parameters']
            rigid = np.eye(4)
            rigid[:3, :3] = xyz_rotation(roll, pitch, yaw)
            rigid[:3, 3] = official[MODEL_TARGET[model]][:3, 3] + [dx, dy, dz]
            err = max(maxerr(rigid, candidate['world_from_model']), maxerr(rigid@sim, candidate['world_from_obj_similarity']))
            errors.append(err)
            check(err < MATRIX_TOL, f'{model} {candidate["id"]} rigid composition')
        best = min(frozen['candidates'], key=lambda c: c['fit_objective'])
        check(best['id'] == frozen['candidate_id'] and frozen['check_used_for_selection'] is False, f'{model} fit-only selection')
        check(maxerr(np.asarray(frozen['world_from_model'])@sim, frozen['world_from_obj_similarity']) < MATRIX_TOL, f'{model} frozen composition')
        class_checks.append({'model_name': model, 'candidate_count': len(errors), 'max_rigid_composition_error': max(errors),
                             'similarity_unchanged': True, 'candidate_id': frozen['candidate_id']})

    frame_checks, replays = [], []
    metadata_cache, dense_cache = {}, {}
    floor_shift = official['target/100lbs_floor'][:3, 3]-official['target/100lbs'][:3, 3]
    for f in frames:
        sid = f['sample']; row = rows[sid]; rec = row['recording']; idx = int(row['aris_frame']); model = CATEGORY_MODEL[row['category']]
        for key in ('recording', 'aris_frame', 'category'):
            check(f[key] == row[key], f'{sid} identity {key}')
        check(f['model_name'] == model and f['historical_paired_role'] == row.get('paired_role'), f'{sid} class/role')
        check(all(f[k] == v for k, v in selected[sid].items()), f'{sid} selected metadata')
        recdir = Path(row['original_image']).parent.parent
        check(recdir.name == rec and Path(row['original_image']).stem == f'{idx:04d}', f'{sid} source identity')
        tf = 'target/100lbs_floor' if rec == '2023-09-21_160551' else MODEL_TARGET[model]
        is_floor = tf.endswith('_floor')
        check(f['target_frame'] == tf and f['floor_extrapolation'] == is_floor, f'{sid} target mapping')
        check((recdir.parent.name == '100lbs_bomb_(floor)') == is_floor, f'{sid} floor directory mapping')
        if rec not in metadata_cache:
            wanted = {int(s['aris_frame']) for s in selection['samples'] if s['recording'] == rec}
            mp = recdir / 'aris_frame_meta.csv'; gp = recdir / 'gantry.csv'
            with mp.open(encoding='utf-8-sig', newline='') as stream:
                mm = {int(r['FrameIndex']): r for r in csv.DictReader(stream) if int(r['FrameIndex']) in wanted}
            with gp.open(encoding='utf-8-sig', newline='') as stream:
                gg = {int(r['aris_frame_idx']): r for r in csv.DictReader(stream) if int(r['aris_frame_idx']) in wanted}
            metadata_cache[rec] = mm, gg
        meta = metadata_cache[rec][0][idx]; gantry = metadata_cache[rec][1][idx]
        check(int(meta['FrameTime']) == int(row['aris_time_us']), f'{sid} timestamp')
        expected_paths = {'raw': recdir / 'aris_raw' / f'{idx:04d}.pgm', 'metadata': recdir/'aris_frame_meta.csv', 'gantry': recdir/'gantry.csv'}
        if row.get('reference_sd'):
            cp = manifest_path.parent / row['reference_sd']
            if cp.is_file(): expected_paths['camera'] = cp
        for kind in ('raw', 'metadata', 'gantry', 'camera'):
            got = f['provenance'][kind]
            check((got is None and kind not in expected_paths) or (got is not None and kind in expected_paths and Path(got['path']).resolve() == expected_paths[kind].resolve()), f'{sid} {kind} provenance path')
        wa = np.eye(4)
        wa[:3, :3] = official['setup/ar3'][:3, :3] @ xyz_rotation(*(float(meta[k]) for k in ('SonarRoll', 'SonarTilt', 'SonarPan')))
        wa[:3, 3] = np.array([float(gantry[k]) for k in 'xyz']) + official['setup/ar3'][:3, 3]
        ws = wa @ official['setup/aris'] @ official['setup/sonar']
        sw = np.eye(4); sw[:3, :3] = ws[:3, :3].T; sw[:3, 3] = -ws[:3, :3].T @ ws[:3, 3]
        sim = np.asarray(freezes[model]['raw_obj_to_model_similarity'])
        oldmatrix = official[tf] @ sim
        newmatrix = np.asarray(freezes[model]['world_from_model']) @ sim
        # All official target rotations are identity; apply only the known relative translation.
        if is_floor: newmatrix[:3, 3] += floor_shift
        matrix_error = max(maxerr(ws, f['world_from_sonar']), maxerr(newmatrix, f['new_world_from_obj']))
        check(matrix_error < MATRIX_TOL, f'{sid} sensor/object chain')
        g = geometry(meta, tables)
        geom_error = max(abs(g['r0']-f['geometry']['range_start_m']), abs(g['dr']-f['geometry']['sample_bin_m']), abs(g['rmax']-f['geometry']['last_sample_end_m']))
        check(geom_error < 1e-12 and [g['h'], g['w']] == f['geometry']['raw_shape_hw'], f'{sid} raw geometry')
        check(maxerr([g['angles'][0], g['angles'][-1]], f['geometry']['beam_angle_endpoints_deg']) < 1e-12, f'{sid} beam boundaries')
        check(f['candidate_id'] == freezes[model]['candidate_id'], f'{sid} frozen candidate identity')
        frame_checks.append({'sample': sid, 'target_frame': tf, 'matrix_max_abs_error': matrix_error,
                             'range_geometry_max_abs_error_m': geom_error, 'floor_extrapolation': is_floor})
        rec_frames = [s for s in selection['samples'] if s['recording'] == rec]
        do_replay = f['role'] == 'fit' or (rec in REPLAY_CHECK_RECORDINGS and sid in (rec_frames[0]['sample'], rec_frames[-1]['sample']))
        if do_replay:
            if model not in dense_cache:
                dense_cache[model] = dense_obj(old_models[model]['source'])
            cloud, nverts, nfaces = dense_cache[model]
            check(nverts == old_models[model]['vertices'] and nfaces == old_models[model]['triangles'], f'{model} mesh topology')
            for variant, matrix in [('old', oldmatrix), ('new', newmatrix)]:
                result = raw_projection(cloud, sw@matrix, g)
                original = f[variant]
                null_match = (result['bbox_xyxy'] is None) == (original['bbox_xyxy'] is None)
                err = maxerr(result['bbox_xyxy'], original['bbox_xyxy']) if null_match and result['bbox_xyxy'] is not None else (0. if null_match else None)
                count_match = result['visible_point_count'] == original['visible_point_count'] and result['surface_count'] == original['surface_count']
                check(null_match and err is not None and err <= BBOX_TOL and count_match, f'{sid} {variant} dense projection')
                replays.append({'sample': sid, 'variant': variant, **result, 'bbox_max_abs_error_px': err, 'visible_and_surface_counts_match': count_match})
            print('Replayed '+sid, flush=True)
    check(len(replays) == 42, '21 frames / 42 old+new dense replays')
    floor_notes = Path(rows['2023-09-21_160551_0066']['original_image']).parent.parent / 'notes.txt'
    floor_text = floor_notes.read_text('utf-8-sig')
    check(floor_text.splitlines()[0].strip() == '- target: 100lbs_bomb (floor)', 'Official floor recording notes')
    after = {path: fingerprint(path) for path in before}
    check(before == after, 'Protected input/artifact bytes unchanged during independent verification')
    journal = str(ROOT / 'DataSet/sonar_manual_curation/reviews.jsonl')
    report = {'status': 'pass' if not issues else 'fail', 'created_utc': datetime.now(timezone.utc).isoformat(),
              'method': 'Independent official YAML quaternion/Euler construction, homogeneous OBJ transforms, AST literal beam tables, manual piecewise interpolation; no main evaluator/projection imports',
              'scope': {'frames_metadata_and_chains': len(frames), 'recordings': len(recordings), 'fit_frames': 9, 'development_check_frames': 111,
                        'dense_replay_frames': len(replays)//2, 'dense_replay_boxes': len(replays), 'new_image_decodes': 0, 'fitting_calls': 0, 'formal_gt_written': 0, 'user_reviews_written': 0},
              'tolerances': {'matrix_max_abs': MATRIX_TOL, 'bbox_max_abs_px': BBOX_TOL, 'visible_count': 'exact'},
              'class_counts': dict(Counter(f['model_name'] for f in frames)),
              'historical_paired_roles': dict(Counter(str(f['historical_paired_role']) for f in frames)),
              'selection_rule_verified': 'All 40 allowed native recordings, first/middle/last except 9 frozen fit centers; paired_role null retained',
              'source_references_verified': len(source_expectations), 'source_expectations': {str(k): v for k, v in source_expectations.items()},
              'class_checks': class_checks, 'frame_checks': frame_checks, 'dense_replays': replays,
              'max_matrix_error': max(v['matrix_max_abs_error'] for v in frame_checks),
              'max_bbox_error_px': max((v['bbox_max_abs_error_px'] or 0.) for v in replays),
              'floor': {'recording': '2023-09-21_160551', 'official_target': 'target/100lbs_floor', 'relative_translation_m': floor_shift.tolist(),
                        'new_chain': 'frozen_world_from_obj + official floor-minus-normal target translation, applied exactly once',
                        'additional_beam_sign_change': False, 'unvalidated_extrapolation': True, 'notes_sha256': fingerprint(floor_notes)['sha256']},
              'protected_artifacts_before': before, 'protected_artifacts_after': after, 'protected_unchanged': before == after,
              'production_reviews_before': before[journal], 'production_reviews_after': after[journal],
              'limitations': ['Software arithmetic and input provenance verification only; no physical registration, echo correctness or GT acceptance is certified.',
                             '21 of 120 frames received full dense old/new bbox replay; all 120 received identity, target, geometry and matrix checks.',
                             'Only listed protected files are covered by before/after checks; no claim about the whole original repository is made.'],
              'issues': issues}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'sources': len(source_expectations), 'matrices': len(frames), 'replays': len(replays),
                      'max_matrix_error': report['max_matrix_error'], 'max_bbox_error_px': report['max_bbox_error_px'], 'issues': issues}))
    if issues: raise SystemExit(1)


if __name__ == '__main__':
    main()
