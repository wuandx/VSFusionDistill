"""Compare fixed full-geometry projection with the existing +/-7 degree rule."""
from pathlib import Path
import hashlib
import html
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/_sonar_audit_deps'))
import numpy as np
from PIL import Image, ImageDraw
from verify_sonar_registration_expanded import dense_obj, beam_tables, fingerprint

BASE = ROOT / 'DataSet/sonar_fixed_registration_refinement'
OUT = BASE / 'full_projection_diagnostic'
PLAN = ROOT / 'experiment/sonar-registration-full-projection-plan.md'
MODELS = ('100lbs', 'incindiary', 'mortar_shell')


def read(p):
    return json.loads(Path(p).read_text('utf-8-sig'))


def save(p, data):
    Path(p).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def box_projection(points, world_from_sonar, world_from_obj, g, table):
    ws = np.asarray(world_from_sonar)
    sw = np.eye(4)
    sw[:3, :3] = ws[:3, :3].T
    sw[:3, 3] = -ws[:3, :3].T @ ws[:3, 3]
    xyz = ((sw @ np.asarray(world_from_obj)) @ points.T)[:3].T
    ranges = np.sqrt(np.sum(xyz*xyz, axis=1))
    azimuth = -np.degrees(np.arctan2(xyz[:, 0], xyz[:, 2]))
    elevation = np.degrees(np.arctan2(xyz[:, 1], np.hypot(xyz[:, 0], xyz[:, 2])))
    height, width = g['raw_shape_hw']
    angles = np.empty(2*width+1)
    angles[:-1:2] = table[:, 1]
    angles[1::2] = table[:, 0]
    angles[-1] = table[-1, 2]
    common = (xyz[:, 2] > 0) & (ranges >= g['range_start_m']) & (ranges <= g['last_sample_end_m'])
    common &= (azimuth >= angles[0]) & (azimuth <= angles[-1])
    uv = np.empty((int(common.sum()), 2))
    a = azimuth[common]
    k = np.clip(np.searchsorted(angles, a, side='right')-1, 0, len(angles)-2)
    uv[:, 0] = (k+(a-angles[k])/(angles[k+1]-angles[k]))/2
    uv[:, 1] = (ranges[common]-g['range_start_m'])/g['sample_bin_m']
    eligible_elevations = elevation[common]
    narrow = np.abs(eligible_elevations) <= 7.

    def bounds(coords):
        if len(coords) == 0:
            return None
        lo = np.maximum(coords.min(axis=0), [0., 0.])
        hi = np.minimum(coords.max(axis=0), [width, height])
        return np.r_[lo, hi].tolist() if np.all(hi > lo) else None

    return ({'bbox_xyxy': bounds(uv[narrow]), 'visible_point_count': int(narrow.sum()), 'surface_count': len(points)},
            {'bbox_xyxy': bounds(uv), 'visible_point_count': len(uv), 'surface_count': len(points),
             'elevation_extent_deg': [float(eligible_elevations.min()), float(eligible_elevations.max())] if len(uv) else None})


def difference(clipped, full):
    b0, b1 = clipped['bbox_xyxy'], full['bbox_xyxy']
    result = {'empty_7deg': b0 is None, 'empty_full': b1 is None,
              'null_to_nonnull': b0 is None and b1 is not None,
              'added_surface_points': full['visible_point_count']-clipped['visible_point_count'],
              'area_7deg_raw_px2': None, 'area_full_raw_px2': None, 'area_ratio_full_over_7deg': None,
              'iou_between_definitions': None, 'bbox_max_abs_delta_px': None,
              'bbox_unchanged': b0 is None and b1 is None}
    if b0 is not None:
        result['area_7deg_raw_px2'] = (b0[2]-b0[0])*(b0[3]-b0[1])
    if b1 is not None:
        result['area_full_raw_px2'] = (b1[2]-b1[0])*(b1[3]-b1[1])
    if b0 is not None and b1 is not None:
        a0, a1 = result['area_7deg_raw_px2'], result['area_full_raw_px2']
        intersection = max(0., min(b0[2], b1[2])-max(b0[0], b1[0])) * max(0., min(b0[3], b1[3])-max(b0[1], b1[1]))
        result.update(area_ratio_full_over_7deg=a1/a0, iou_between_definitions=intersection/(a0+a1-intersection),
                      bbox_max_abs_delta_px=float(np.max(np.abs(np.asarray(b0)-b1))))
        result['bbox_unchanged'] = result['bbox_max_abs_delta_px'] <= 1e-8
        assert b1[0] <= b0[0]+1e-8 and b1[1] <= b0[1]+1e-8 and b1[2] >= b0[2]-1e-8 and b1[3] >= b0[3]-1e-8
    return result


def comparison(raw, item, destination):
    height, width = raw.shape
    canvas = Image.new('RGB', (1230, height+110), '#eeeeee')
    cases = [('Raw / gain 1', None, None), ('Fixed model / +/-7 deg', item['clipped_7deg'], '#00dd88'),
             ('Full geometry / no elevation gate', item['full_projection'], '#ffb000')]
    for index, (title, result, color) in enumerate(cases):
        pic = Image.fromarray(raw).convert('RGB').resize((384, height), Image.Resampling.NEAREST)
        d = ImageDraw.Draw(pic)
        if result and result['bbox_xyxy']:
            x0, y0, x1, y1 = result['bbox_xyxy']
            d.rectangle((x0*384/width, y0, x1*384/width, y1), outline=color, width=2)
        canvas.paste(pic, (index*410+13, 39))
        d = ImageDraw.Draw(canvas)
        d.text((index*410+8, 8), title, fill='black')
        if result:
            suffix = 'EMPTY' if result['bbox_xyxy'] is None else f'{result["visible_point_count"]} surface points'
            d.text((index*410+8, height+47), suffix, fill='black')
    d.text((10, height+69), item['sample']+' | '+item['role']+' | target '+item['target_frame'], fill='black')
    d.text((10, height+89), 'Same frozen model. Full geometry is not an acoustic visibility claim. Padding 0; no fit or review write.', fill='black')
    canvas.save(destination, quality=94)


def summarize(items):
    diffs = [f['difference'] for f in items]
    ratios = [d['area_ratio_full_over_7deg'] for d in diffs if d['area_ratio_full_over_7deg'] is not None]
    return {'frames': len(items), 'empty_7deg': sum(d['empty_7deg'] for d in diffs),
            'empty_full': sum(d['empty_full'] for d in diffs), 'null_to_nonnull': sum(d['null_to_nonnull'] for d in diffs),
            'nonnull_to_null': sum(not d['empty_7deg'] and d['empty_full'] for d in diffs),
            'bbox_unchanged': sum(d['bbox_unchanged'] for d in diffs),
            'bbox_changed': sum(not d['bbox_unchanged'] for d in diffs),
            'area_ratio_ge_1_5_among_two_nonempty': sum(r >= 1.5 for r in ratios),
            'area_ratio_max_among_two_nonempty': max(ratios) if ratios else None,
            'additional_points_frames': sum(d['added_surface_points'] > 0 for d in diffs)}


def make_index(items, summary):
    cards = []
    for item in sorted(items, key=lambda v: v['sample']):
        d = item['difference']
        change = '空框变为非空' if d['null_to_nonnull'] else ('两者均为空' if d['empty_full'] else ('边界不变' if d['bbox_unchanged'] else '边界扩大'))
        ratio = d['area_ratio_full_over_7deg']
        extra = '' if ratio is None else f'；面积比 {ratio:.3f}；两定义框 IoU {d["iou_between_definitions"]:.3f}'
        cards.append(f'<article data-model="{item["model_name"]}" data-recording="{item["recording"]}"><h3>{item["sample"]} · {item["role"]}</h3><p>{change}{extra}。这不是 GT IoU 或通过率。</p><a href="{item["comparison_image"]}"><img loading="lazy" src="{item["comparison_image"]}"></a></article>')
    options = ''.join(f'<option value="{rec}">{rec}</option>' for rec in sorted({f['recording'] for f in items}))
    totals = html.escape(json.dumps(summary, ensure_ascii=False, indent=2))
    page = '''<!doctype html><html lang="zh"><meta charset="utf-8"><title>完整几何投影与 ±7° 裁剪对照</title><style>body{font:16px system-ui;background:#f1f5f9;color:#1e293b;margin:24px}article{background:white;padding:16px;margin:20px 0;border-radius:10px}img{width:100%;max-width:1230px}select{padding:8px;margin:8px}pre{white-space:pre-wrap}</style><h1>完整几何投影与 ±7° 裁剪对照</h1><p>固定三类模型、全部120身份、beam/range/像素约定与padding=0。仅比较是否按elevation裁剪。原图gain=1。</p><p>取消elevation条件得到完整目标几何外包框，不代表真实垂直FOV无限、全部表面可见或论文采用此规则。未改默认、未拟合、未写正式审阅或GT。</p><p>每图左：原图；中：±7°；右：无elevation门限。颜色只区分两种定义。</p><details><summary>数值统计</summary><pre>'''+totals+'''</pre></details><select id="model" onchange="filter()"><option value="">全部类别</option><option value="100lbs">bomb</option><option value="incindiary">grenade</option><option value="mortar_shell">mortar</option></select><select id="rec" onchange="filter()"><option value="">全部录音</option>'''+options+'</select>'+''.join(cards)+'''<script>function filter(){const m=document.getElementById('model').value,r=document.getElementById('rec').value;document.querySelectorAll('article').forEach(a=>a.hidden=(!!m&&a.dataset.model!==m)||(!!r&&a.dataset.recording!==r));}</script></html>'''
    (OUT/'index.html').write_text(page, encoding='utf-8')


def main():
    if OUT.exists():
        raise RuntimeError('Preserve existing diagnostic directory')
    assert PLAN.is_file()
    selection_path = BASE/'evaluation-selection.json'
    beam_path = ROOT/'related_work/uxo-upstream-history/scripts/common/aris_definitions.py'
    selection = read(selection_path)
    expected = {x['sample']: x for x in selection['samples']}
    assert len(expected) == 120
    evals = {m: read(BASE/m/'evaluation-results.json') for m in MODELS}
    freezes = {m: read(BASE/m/'freeze-model.json') for m in MODELS}
    sources = {PLAN, Path(__file__), ROOT/'tools/verify_sonar_registration_expanded.py', selection_path, beam_path,
               BASE/'expanded-numeric-verification.json', BASE/'delivery-verification.json',
               ROOT/'DataSet/sonar_manual_curation/reviews.jsonl', ROOT/'tools/sonar_manual_curation_server.py'}
    for model in MODELS:
        sources.update((BASE/model/'evaluation-results.json', BASE/model/'freeze-model.json', Path(freezes[model]['model']['obj_path'])))
        sources.update(BASE/model/'evaluation'/(f['sample']+'-raw.png') for f in evals[model]['frames'])
    before = {str(p): fingerprint(p) for p in sorted(sources)}
    for model in MODELS:
        assert before[str(BASE/model/'freeze-model.json')]['sha256'] == evals[model]['freeze_sha256']
        assert before[str(selection_path)]['sha256'] == evals[model]['selection_sha256']
        assert before[str(Path(freezes[model]['model']['obj_path']))]['sha256'] == freezes[model]['model']['obj_sha256']
    assert read(BASE/'expanded-numeric-verification.json')['status'] == 'pass'
    OUT.mkdir()
    (OUT/'comparisons').mkdir()
    save(OUT/'inputs-before.json', before)
    (OUT/'plan-before-run.md').write_bytes(PLAN.read_bytes())
    (OUT/'implementation-before-run.py').write_bytes(Path(__file__).read_bytes())
    tables = beam_tables(beam_path)
    results = []
    try:
        for model in MODELS:
            cloud, _, _ = dense_obj(freezes[model]['model']['obj_path'])
            for f in evals[model]['frames']:
                sid = f['sample']
                assert all(f[k] == v for k, v in expected[sid].items())
                clipped, full = box_projection(cloud, f['world_from_sonar'], f['new_world_from_obj'], f['geometry'], tables[f['geometry']['raw_shape_hw'][1]])
                original = f['new']
                assert (original['bbox_xyxy'] is None) == (clipped['bbox_xyxy'] is None)
                error = 0. if clipped['bbox_xyxy'] is None else float(np.max(np.abs(np.asarray(clipped['bbox_xyxy'])-original['bbox_xyxy'])))
                assert error <= 1e-8 and clipped['visible_point_count'] == original['visible_point_count'] and clipped['surface_count'] == original['surface_count']
                assert full['visible_point_count'] >= clipped['visible_point_count']
                rawpath = BASE/model/'evaluation'/(sid+'-raw.png')
                with Image.open(rawpath) as im:
                    assert im.mode == 'L'
                    raw = np.array(im)
                assert list(raw.shape) == f['geometry']['raw_shape_hw']
                item = {k: f[k] for k in ('sample', 'recording', 'aris_frame', 'category', 'model_name', 'role', 'historical_paired_role', 'target_frame', 'floor_extrapolation', 'candidate_id')}
                item.update(clipped_7deg=clipped, full_projection=full, difference=difference(clipped, full),
                            existing_7deg_bbox_max_abs_error_px=error, world_from_sonar=f['world_from_sonar'], world_from_obj=f['new_world_from_obj'],
                            raw_copy={'path': str(rawpath), **before[str(rawpath)]}, freeze_sha256=evals[model]['freeze_sha256'],
                            comparison_image='comparisons/'+sid+'.jpg')
                comparison(raw, item, OUT/item['comparison_image'])
                results.append(item)
                if len(results) % 12 == 0: print(f'Compared {len(results)}/120', flush=True)
        assert len(results) == 120 and {f['sample'] for f in results} == set(expected)
        after = {p: fingerprint(p) for p in before}
        save(OUT/'inputs-after.json', after)
        assert before == after
        summary = summarize(results)
        model_summaries = {model: summarize([f for f in results if f['model_name'] == model]) for model in MODELS}
        recording_summaries = {rec: summarize([f for f in results if f['recording'] == rec]) for rec in sorted({f['recording'] for f in results})}
        journal = str(ROOT/'DataSet/sonar_manual_curation/reviews.jsonl')
        data = {'status': 'complete', 'created_utc': datetime.now(timezone.utc).isoformat(),
                'plan_sha256': before[str(PLAN)]['sha256'], 'script_sha256': before[str(Path(__file__))]['sha256'],
                'selection_sha256': before[str(selection_path)]['sha256'],
                'semantics': {'clipped_7deg': 'Geometric surface support inside forward/range/beam and absolute elevation <=7 degrees.',
                              'full_projection': 'Full geometric surface support inside forward/range/beam only; not acoustic visibility or infinite vertical FOV.',
                              'both': 'Same fixed model, sensor pose, target mapping, beta=-atan2(x,z), actual beam edges/centres, raw pixel-edge coordinates and zero padding.',
                              'paper': 'No assertion that CMHD used no elevation gate.'},
                'summary': summary, 'by_model': model_summaries, 'by_recording': recording_summaries, 'frames': results,
                'verification': {'all_120_existing_7deg_controls_match': True,
                                 'max_7deg_bbox_error_px': max(f['existing_7deg_bbox_max_abs_error_px'] for f in results),
                                 'input_file_count': len(before), 'all_inputs_unchanged': before == after,
                                 'raw_copy_decodes': 120, 'new_original_image_reads': 0, 'fit_calls': 0,
                                 'user_reviews_before': before[journal], 'user_reviews_after': after[journal],
                                 'default_service_changed': False, 'formal_gt_written': 0}}
        save(OUT/'results.json', data)
        make_index(results, summary)
        report = ['# 完整几何投影与 ±7° 裁剪对照', '',
                  '固定三类注册与全部120身份，仅取消第二种框定义的elevation门限。无门限框不表示实际声呐垂直FOV无限、全部表面可见或论文采用此规则。所有图均为已有raw副本、gain=1；未改默认或正式审阅。', '',
                  '| 范围 | 帧数 | ±7°空框 | 完整几何空框 | 空→非空 | 边界不变 | 面积比≥1.5（两者非空） |',
                  '|---|---:|---:|---:|---:|---:|---:|']
        for name, s in [('全部', summary), *model_summaries.items()]:
            report.append(f'| {name} | {s["frames"]} | {s["empty_7deg"]} | {s["empty_full"]} | {s["null_to_nonnull"]} | {s["bbox_unchanged"]} | {s["area_ratio_ge_1_5_among_two_nonempty"]} |')
        report += ['', '两定义框IoU、面积比和数量只描述裁剪规则的影响，不是真值精度或质量通过率。全部逐帧框、点数、变换与来源见results.json；index.html可按录音筛选。', '',
                   f'现有±7°对照120/120一致，可见点数完全相同，最大框差{data["verification"]["max_7deg_bbox_error_px"]:.4g}px。{len(before)}项输入前后hash/存在状态不变；新增源图读取0、已有raw副本解码120、拟合0、正式GT0。', '',
                   '自动统计尚不判断几何框是否贴合实际目标。完整几何仍错位、含非发声表面或被range/beam截断的情形均须保留，由后续明确标记的目视诊断解释。']
        (OUT/'report.md').write_text('\n'.join(report)+'\n', encoding='utf-8')
        print(json.dumps({'summary': summary, 'by_model': model_summaries, 'verification': data['verification']}, ensure_ascii=False))
    except Exception as exc:
        save(OUT/'failure.json', {'error': repr(exc), 'completed_frames': len(results), 'frames': results})
        raise


if __name__ == '__main__':
    main()
