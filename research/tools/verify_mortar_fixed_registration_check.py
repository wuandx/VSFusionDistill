"""Independent six-frame replay of frozen mortar development evaluation.

Only the independently authored verifier geometry is imported. No producer,
optimizer, image decoder or display code runs here.
"""
from pathlib import Path
import itertools
import json
import sys
sys.dont_write_bytecode = True
from verify_mortar_fixed_registration import (
    ROOT, FIT_IDS, CHECK_IDS, ALL_IDS, np, read_json, digest, load_obj,
    transform_points, surface_cloud, selected_csv_rows, load_static_transforms,
    load_beam_tables, replay_projection, assert_metric_replay, independent_gaps,
    max_difference,
)


def iou(a, b):
    if a is None or b is None:
        return None
    a, b = np.asarray(a), np.asarray(b)
    low = np.maximum(a[:2], b[:2])
    high = np.minimum(a[2:], b[2:])
    overlap = np.prod(np.maximum(high-low, 0.))
    union = np.prod(a[2:]-a[:2])+np.prod(b[2:]-b[:2])-overlap
    return float(overlap/union)


def main():
    out = ROOT/'DataSet/mortar_fixed_registration'
    destination = out/'independent-check-verification.json'
    if destination.exists():
        raise RuntimeError('Preserve previous independent check verification')
    frozen_path = out/'freeze-model.json'
    frozen = read_json(frozen_path)
    evaluation_path = out/'evaluation-results.json'
    evaluation = read_json(evaluation_path)
    assert digest(frozen_path) == evaluation['freeze_sha256'] == read_json(out/'freeze-model.sha256.json')['sha256']
    assert evaluation['model_changed_for_check'] is False
    assert evaluation['test_access'] is False and evaluation['training_gt'] is False
    assert digest(ROOT/'tools/fit_mortar_fixed_registration.py') == frozen['solver_sha256']
    assert digest(out/'observations/fit-observations.json') == frozen['observation_sha256']
    assert digest(out/'observations/check-observations.json') == evaluation['check_observations_sha256']
    rows = {r['sample']: r for r in evaluation['frames']}
    assert set(rows) == set(ALL_IDS)
    obs = {}
    for file in ('fit-observations.json', 'check-observations.json'):
        for row in read_json(out/'observations'/file)['frames']:
            assert row['sample'] not in obs
            obs[row['sample']] = row
    assert set(obs) == set(ALL_IDS)
    assert all(obs[s]['role'] == ('fit' if s in FIT_IDS else 'check') for s in ALL_IDS)
    candidates = {c['id']: c for c in frozen['candidates']}
    best = frozen['best_display_candidate_id']
    eligible = frozen['eligible_candidate_ids']
    assert evaluation['best_display_candidate_id'] == best
    assert evaluation['eligible_candidate_ids'] == eligible
    candidate_ids = list(dict.fromkeys([best]+eligible))
    selection_path = ROOT/'DataSet/sonar_independent_registration/selection.json'
    selection = {r['sample']: r for r in read_json(selection_path)['samples'] if r['sample'] in ALL_IDS}
    manifest_path = ROOT/'DataSet/camera_temporal_all/manifest-resolved.json'
    allowed = {r['sample']: r for r in read_json(manifest_path)['items'] if r['sample'] in ALL_IDS and r.get('paired_role') in ('train', 'val', 'val_id')}
    assert set(selection) == set(allowed) == set(ALL_IDS)
    statics_path = ROOT/'related_work/sonar-projection-audit-assets/calibration__transforms.yaml'
    beam_path = ROOT/'related_work/uxo-upstream-history/scripts/common/aris_definitions.py'
    statics = load_static_transforms(statics_path)
    tables = load_beam_tables(beam_path)
    old_path = ROOT/'DataSet/sonar_fixed_mesh/fixed-mesh-transforms.json'
    old = read_json(old_path)['models']['mortar_shell']
    vertices, faces = load_obj(frozen['model']['obj_path'])
    raw_cloud = surface_cloud(vertices, faces)
    model_cloud = transform_points(raw_cloud, frozen['model']['raw_obj_to_model_similarity'])
    old_world = transform_points(raw_cloud, np.asarray(old['world_from_target'])@np.asarray(old['mesh_to_target_similarity']))
    tracked = set(map(Path, evaluation['source_hashes'])) | {Path(__file__), ROOT/'tools/verify_mortar_fixed_registration.py',
                evaluation_path, statics_path, beam_path, out/'freeze-model.sha256.json'}
    tracked |= {Path(selection[s][k]) for s in ALL_IDS for k in ('meta_source', 'gantry_source')}
    stale = {p: h for p, h in evaluation['source_hashes'].items() if digest(p) != h}
    assert not stale, stale
    before = {str(p): digest(p) for p in tracked}
    checks = []
    for sid in ALL_IDS:
        row = selection[sid]
        meta = selected_csv_rows(row['meta_source'], 'FrameIndex', [row['aris_frame']])[row['aris_frame']]
        gantry = selected_csv_rows(row['gantry_source'], 'aris_frame_idx', [row['aris_frame']])[row['aris_frame']]
        assert int(meta['FrameTime']) == allowed[sid]['aris_time_us']
        assert row['aris_frame'] == allowed[sid]['aris_frame']
        assert set(rows[sid]['candidate_metrics']) == set(candidate_ids)
        observation = obs[sid]
        candidate_checks = []
        boxes = {}
        metrics_iter = [(cid, rows[sid]['candidate_metrics'][cid]) for cid in candidate_ids]
        metrics_iter.append(('prior_fixed_mesh', rows[sid]['prior_fixed_mesh_metrics']))
        for cid, saved in metrics_iter:
            world = old_world if cid == 'prior_fixed_mesh' else transform_points(model_cloud, candidates[cid]['world_from_model'])
            replay = replay_projection(world, meta, gantry, statics, tables)
            errors = assert_metric_replay(replay, saved)
            if cid in eligible:
                boxes[cid] = replay['visible_raw_bbox_padded_clipped_xyxy']
            gap_error = None
            if observation['points']:
                gaps = independent_gaps(replay, observation)
                gap_error = max_difference(gaps, [p['normalized_gap'] for p in saved['point_residuals']])
                assert gap_error < 1e-7, (sid, cid, gap_error)
                huber_mean = float(np.mean(np.where(gaps <= 1., .5*gaps*gaps, gaps-.5)))
                assert abs(huber_mean-saved['point_huber_mean']) < 1e-7
                assert abs(float(np.quantile(gaps, .95))-saved['point_gap_p95']) < 1e-7
                assert abs(float(np.max(gaps))-saved['point_gap_max']) < 1e-7
            else:
                assert saved['point_count'] == 0
                assert all(saved[key] is None for key in ('point_residuals', 'point_huber_mean', 'objective', 'point_gap_p95', 'point_gap_max'))
                assert rows[sid]['no_reliable_observation'] is True
            candidate_checks.append(dict(candidate_id=cid, numeric_errors=errors, brute_force_gap_error=gap_error))
        values = [boxes[c] for c in eligible]
        pairs = [iou(a, b) for a, b in itertools.combinations(values, 2)]
        valid = [b for b in values if b is not None]
        min_iou = min(pairs) if pairs and all(p is not None for p in pairs) else None
        spans = np.ptp(np.array(valid), axis=0) if valid else None
        stable = bool(len(values) >= 2 and len(valid) == len(values) and min_iou >= .9 and np.all(spans <= [1, 2, 1, 2]))
        saved_stability = rows[sid]['candidate_box_stability']
        assert max_difference(min_iou, saved_stability['minimum_pairwise_iou']) < 1e-7
        assert max_difference(spans, saved_stability['edge_spans_raw_uv']) < 1e-7
        assert stable == saved_stability['stable_by_draft_rule']
        checks.append(dict(sample=sid, role=rows[sid]['role'], observation_count=len(observation['points']),
                           candidate_checks=candidate_checks, minimum_pairwise_iou=min_iou, stable=stable))
    assert before == {p: digest(p) for p in before}
    report = dict(run='mortar_fixed_registration_independent_check_verification',passed=True,
                  source_hashes=before,inputs_unchanged=True,freeze_sha256=digest(frozen_path),
                  evaluation_sha256=digest(evaluation_path),frames=checks,
                  best_display_candidate_id=best,eligible_candidate_ids=eligible,
                  fits_run=0,new_images_decoded=0,test_access=False,training_gt=False,
                  scope='Independent numeric replay of six predeclared development frames; not physical calibration or expert truth',
                  methods=['original YAML and selected raw metadata pose reconstruction','independent OBJ homogeneous projection',
                           'actual beam-edge/center interpolation','brute-force rectangle support gap','independent box IoU'])
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(passed=True,frames=6,candidates=len(candidate_ids),report=str(destination)),ensure_ascii=False))


if __name__ == '__main__':
    main()
