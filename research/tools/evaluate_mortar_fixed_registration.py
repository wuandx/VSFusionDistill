"""Evaluate frozen mortar candidates on the predeclared six development frames."""
from pathlib import Path
import csv
import hashlib
import json
import sys
import itertools
import html

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/_sonar_audit_deps'))
import numpy as np
import cv2
from PIL import Image, ImageDraw
from fit_mortar_fixed_registration import FitFrame, read_obj
from check_official_sonar_coordinates import load_beam_tables, beam_count

OUT = ROOT / 'DataSet/mortar_fixed_registration'


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(p, data):
    Path(p).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def iou(a, b):
    if a is None or b is None:
        return None
    a, b = np.array(a), np.array(b)
    s = np.maximum(0., np.minimum(a[2:], b[2:]) - np.maximum(a[:2], b[:2]))
    intersection = float(s.prod())
    return intersection / ((a[2:] - a[:2]).prod() + (b[2:] - b[:2]).prod() - intersection)


def draw_raw(raw, proj=None, box=None, points=None, title='', color=(0, 245, 110)):
    image = Image.fromarray(np.clip(raw.astype(float) * 3, 0, 255).astype('uint8')).convert('RGB').resize((512, raw.shape[0] * 2), Image.Resampling.NEAREST)
    draw = ImageDraw.Draw(image)
    if proj is not None:
        uv = proj['uv'][proj['visible']]
        if len(uv) >= 3:
            # Convex outline is display only, not the fitted support or bbox.
            hull = cv2.convexHull(uv.astype('float32')).reshape(-1, 2)
            verts = [(float(u * 4), float(v * 2)) for u, v in hull]
            draw.line(verts + [verts[0]], fill=color, width=2)
    if box is not None:
        draw.rectangle([box[0] * 4, box[1] * 2, box[2] * 4, box[3] * 2], outline=color, width=2)
    if points:
        for pt in points:
            u, v = pt['raw_uv_edge']; x, y = u * 4, v * 2
            draw.ellipse([x - 3, y - 3, x + 3, y + 3], outline=(255, 90, 225), width=2)
    panel = Image.new('RGB', (532, image.height + 54), 'white')
    panel.paste(image, (10, 44))
    d = ImageDraw.Draw(panel); d.text((10, 8), title, fill='black'); d.text((10, 24), 'raw gain=3; full range; x=beam, y=range bin', fill='#333333')
    return panel


def draw_polar(polar, geom, projection, box):
    im = Image.fromarray(np.clip(polar.astype(float) * 3, 0, 255).astype('uint8')).convert('RGB')
    dr = ImageDraw.Draw(im)
    if box is not None:
        dr.rectangle(box, outline=(0, 245, 110), width=4)
    vis = projection['visible']
    p = geom.points_to_polar_index(projection['ranges'][vis], projection['beta'][vis]) + .5
    if len(p) >= 3:
        h = cv2.convexHull(p.astype('float32')).reshape(-1, 2)
        line = [tuple(map(float, z)) for z in h]
        dr.line(line + [line[0]], fill=(0, 245, 110), width=3)
    im.thumbnail((512, 882))
    panel = Image.new('RGB', (532, 936), 'white'); panel.paste(im, ((532 - im.width) // 2, 44))
    dr = ImageDraw.Draw(panel); dr.text((10, 8), 'Official polar2 / frozen best', fill='black'); dr.text((10, 24), 'aspect preserved; gain=3; outline is display only', fill='#333333')
    return panel


def main():
    frozen_path = OUT / 'freeze-model.json'
    check_path = OUT / 'observations/check-observations.json'
    assert frozen_path.exists() and check_path.exists(), 'Freeze model before check observations'
    if (OUT / 'evaluation-results.json').exists():
        raise RuntimeError('Preserve evaluation')
    frozen = read(frozen_path)
    assert sha(frozen_path) == read(OUT / 'freeze-model.sha256.json')['sha256']
    assert sha(OUT / 'fit-results.json') == frozen['fit_results_sha256']
    assert sha(ROOT / 'tools/fit_mortar_fixed_registration.py') == frozen['solver_sha256']
    assert sha(OUT / 'observations/fit-observations.json') == frozen['observation_sha256']
    observations = {f['sample']: f for p in [OUT / 'observations/fit-observations.json', check_path] for f in read(p)['frames']}
    ids = frozen['fit_samples'] + frozen['check_samples_not_used']
    assert set(observations) == set(ids)
    assert all(observations[s]['role'] == ('fit' if s in frozen['fit_samples'] else 'check') for s in ids)
    select_path = ROOT / 'DataSet/sonar_independent_registration/selection.json'
    selection = {r['sample']: r for r in read(select_path)['samples'] if r['sample'] in ids}
    manifest_path = ROOT / 'DataSet/camera_temporal_all/manifest-resolved.json'
    allowed = {r['sample']: r for r in read(manifest_path)['items'] if r.get('paired_role') in ['train', 'val', 'val_id'] and r['sample'] in ids}
    assert set(allowed) == set(ids)
    pose_path = ROOT / 'DataSet/sonar_fixed_mesh/results.json'
    poses = {r['sample']: r for r in read(pose_path)['outputs'] if r['sample'] in ids}
    old_path = ROOT / 'DataSet/sonar_fixed_mesh/fixed-mesh-transforms.json'
    old = read(old_path)['models']['mortar_shell']
    vs, faces = read_obj(frozen['model']['obj_path']); tri = vs[faces]
    original_dense = np.concatenate([vs, tri.mean(1), (tri[:, 0] + tri[:, 1]) / 2, (tri[:, 1] + tri[:, 2]) / 2, (tri[:, 2] + tri[:, 0]) / 2])
    S = np.array(frozen['model']['raw_obj_to_model_similarity'])
    dense = original_dense @ S[:3, :3].T + S[:3, 3]
    old_matrix = np.array(old['world_from_target']) @ np.array(old['mesh_to_target_similarity'])
    old_world = original_dense @ old_matrix[:3, :3].T + old_matrix[:3, 3]
    candidates = {c['id']: c for c in frozen['candidates']}
    best = frozen['best_display_candidate_id']; eligible = frozen['eligible_candidate_ids']
    tables = load_beam_tables()
    paths = {Path(__file__), frozen_path, check_path, OUT / 'fit-results.json', OUT / 'observations/fit-observations.json', select_path, manifest_path, pose_path, old_path, Path(frozen['model']['obj_path']), ROOT / 'tools/fit_mortar_fixed_registration.py', ROOT / 'tools/check_official_sonar_coordinates.py'}
    for row in selection.values():
        paths.update([Path(row['raw_sonar_source']), Path(row['meta_source'])])
        paths.add(ROOT / 'DataSet/sonar_registration_methods/coordinates' / (row['sample'] + '-official-polar2.png'))
    before = {str(p): sha(p) for p in paths}; save(OUT / 'evaluation-inputs-before.json', before)
    eval_rows = []; media = OUT / 'review'; media.mkdir(exist_ok=True)
    for sid in ids:
        row = selection[sid]
        with Path(row['meta_source']).open(encoding='utf-8', newline='') as f:
            meta = next(r for r in csv.DictReader(f) if int(r['FrameIndex']) == row['aris_frame'])
        assert int(meta['FrameTime']) == allowed[sid]['aris_time_us']
        obs = observations[sid]
        no_observations = not obs['points']
        # FitFrame needs at least three points. Dummy points are never reported
        # as evidence and serve only to reuse projection/bbox code for unknown.
        input_obs = obs if not no_observations else dict(obs, points=[dict(raw_uv_edge=[64., 200.], tolerance_uv=[1., 2.])] * 3)
        frame = FitFrame(input_obs, poses[sid], meta, tables[beam_count(meta['PingMode'])])
        metrics = {}; projections = {}
        for cid in list(dict.fromkeys([best] + eligible)):
            proj = frame.project(dense, np.array(candidates[cid]['world_from_model']))
            m = frame.summarize(proj)
            if no_observations:
                for key in ['point_residuals', 'point_huber_mean', 'objective', 'point_gap_median', 'point_gap_p95', 'point_gap_max', 'fraction_inside_original_observation_band']:
                    m[key] = None
                m['point_count'] = 0
            metrics[cid] = m
            if cid == best:
                projections[cid] = proj
        old_proj = frame.project(old_world, np.eye(4)); old_metrics = frame.summarize(old_proj)
        if no_observations:
            for key in ['point_residuals', 'point_huber_mean', 'objective', 'point_gap_median', 'point_gap_p95', 'point_gap_max', 'fraction_inside_original_observation_band']:
                old_metrics[key] = None
            old_metrics['point_count'] = 0
        bxs = [metrics[c]['visible_raw_bbox_7deg'] for c in eligible]
        pair_ious = [iou(a, b) for a, b in itertools.combinations(bxs, 2)]
        valid = [b for b in bxs if b is not None]
        spans = (np.ptp(np.array(valid), axis=0).tolist() if valid else None)
        stable = bool(len(bxs) >= 2 and len(valid) == len(bxs) and min(pair_ious) >= .9 and np.all(np.array(spans) <= [1, 2, 1, 2]))
        stability = dict(eligible_count=len(eligible),nonempty_boxes=len(valid),minimum_pairwise_iou=min(pair_ious) if pair_ious and all(p is not None for p in pair_ious) else None,edge_spans_raw_uv=spans,stable_by_draft_rule=stable)
        raw = cv2.imdecode(np.frombuffer(Path(row['raw_sonar_source']).read_bytes(), np.uint8), cv2.IMREAD_GRAYSCALE)
        assert raw.shape == (frame.geom.h, frame.geom.w)
        polar_path = ROOT / 'DataSet/sonar_registration_methods/coordinates' / (sid + '-official-polar2.png')
        polar = cv2.imdecode(np.frombuffer(polar_path.read_bytes(), np.uint8), cv2.IMREAD_GRAYSCALE)
        panels = [draw_raw(raw, points=obs['points'], title='Unboxed / independent observations'),
                  draw_raw(raw, old_proj, old_metrics['visible_raw_bbox_7deg'], title='Prior fixed PCA / same imaging', color=(255, 165, 0)),
                  draw_raw(raw, projections[best], metrics[best]['visible_raw_bbox_7deg'], title='Frozen best ' + best, color=(0, 245, 110)),
                  draw_polar(polar, frame.geom, projections[best], metrics[best]['visible_polar_bbox_7deg'])]
        canvas = Image.new('RGB', (sum(p.width for p in panels), max(p.height for p in panels) + 42), 'white')
        dr = ImageDraw.Draw(canvas); dr.text((12, 8), sid + ' | ' + obs['role'] + ' | all poses frozen; green=best, orange=prior; not training GT', fill='black')
        off = 0
        for p in panels:
            canvas.paste(p, (off, 36)); off += p.width
        review_path = media / (sid + '.jpg'); canvas.save(review_path, quality=94)
        eval_rows.append(dict(sample=sid,role=obs['role'],observation_count=len(obs['points']),no_reliable_observation=no_observations,candidate_metrics=metrics,prior_fixed_mesh_metrics=old_metrics,candidate_box_stability=stability,review_image=str(review_path.relative_to(OUT))))
        print(sid, 'bestp95', metrics[best]['point_gap_p95'], 'priorp95', old_metrics['point_gap_p95'], 'minIoU', stability['minimum_pairwise_iou'], flush=True)
    assert before == {str(p): sha(p) for p in paths}
    save(OUT / 'evaluation-results.json', dict(run='mortar_fixed_registration',freeze_sha256=sha(frozen_path),check_observations_sha256=sha(check_path),model_changed_for_check=False,best_display_candidate_id=best,eligible_candidate_ids=eligible,frames=eval_rows,inputs_unchanged=True,source_hashes=before,test_access=False,training_gt=False,note='Convex outline in review images is display only; fitting and numeric support use dense sampled surface. Unknown frame uses no observation metric. Prior baseline recomputed with same coordinate API and zero padding.'))
    page=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>mortar固定注册实测</title><style>body{font:16px/1.6 system-ui;max-width:1800px;margin:28px auto;padding:20px;color:#18344c}img{max-width:100%}article{border-top:1px solid #ccc;margin-top:30px}a{color:#0762a6}table{border-collapse:collapse}td,th{padding:7px;border-bottom:1px solid #ddd}</style><h1>mortar固定注册：拟合与跨轨迹检查</h1><p>只用100927三帧19个支持点拟合；101131三帧在模型冻结后检查。全部为已观察开发数据，非专家真值或训练GT。</p><p>橙色：旧固定PCA假设；绿色：首轨迹fit代价最低的冻结解；粉色：本轮独立回波观察。线框为显示用凸包轮廓，数字支持集仍为采样表面。</p><p><a href="fit-results.json">24组拟合完整记录</a> · <a href="freeze-model.json">冻结模型与候选</a> · <a href="evaluation-results.json">逐帧误差与框稳定性</a> · <a href="../../复现/camera-baseline/mortar-fixed-registration.md">结果报告</a></p>']
    for r in eval_rows:
        m=r['candidate_metrics'][best]; st=r['candidate_box_stability']
        page.append(f'<article><h2>{r["sample"]} · {r["role"]}</h2><p>观察点 {r["observation_count"]}；最佳解带外p95 {m["point_gap_p95"]}；候选框最小IoU {st["minimum_pairwise_iou"]}；框稳定 {st["stable_by_draft_rule"]}</p><a href="{r["review_image"]}"><img src="{r["review_image"]}" loading="lazy"></a></article>')
    (OUT/'index.html').write_text('\n'.join(page)+'</html>',encoding='utf-8')


if __name__ == '__main__':
    main()
