"""Rejoin existing sonar annotations to SD camera sources; never certifies sync."""
import collections
import hashlib
import html
import json
import math
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/_sonar_audit_deps'))
from PIL import Image, ImageDraw
import numpy as np

CAM = ROOT / 'DataSet/camera_temporal_all'
SON = ROOT / 'DataSet/sonar_visible_annotation/export'
OUT = ROOT / 'DataSet/paired_paper_scale'
CLASSES = ['100lbs_aircraft_bomb', 'mortar_shell', 'incindiary_grenade']


def read(p):
    return json.loads(Path(p).read_text('utf-8-sig'))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), 'utf-8')


def label(m):
    problems = []
    if not m.get('reference_sd') or not (CAM / m['reference_sd']).is_file():
        problems.append('missing_sd')
    if not m.get('label_copy') or not (CAM / m['label_copy']).is_file():
        return [], problems + ['missing_label']
    value = read(CAM / m['label_copy'])
    entries = value if isinstance(value, list) else [value]
    boxes = []
    if not entries:
        problems.append('empty_label')
    for b in entries:
        if b.get('class') != m['category']:
            problems.append('class_mismatch')
        xyxy = [b.get(k) for k in ('x_min', 'y_min', 'x_max', 'y_max')]
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in xyxy):
            problems.append('invalid_coordinates')
            continue
        boxes.append(xyxy)
        x0, y0, x1, y1 = xyxy
        if not 0 <= x0 < x1 <= 640 or not 0 <= y0 < y1 <= 360:
            problems.append('camera_bbox_out_of_bounds')
    return boxes, sorted(set(problems))


def sync_info(m, decisions):
    d = decisions.get(m['recording'])
    if d is None:
        return dict(status='not_independently_checked', eligible_for_review=True)
    if d.get('camera_aris_continuous_check') == 'passed_local_preregistered_check':
        t = (m['aris_time_us'] - m['aris_onset_time_us']) / 1e6
        lo, hi = d['scope_aris_time_s']
        return dict(status='supported_in_checked_window' if lo <= t <= hi else 'outside_checked_window',
                    eligible_for_review=True, aris_relative_time_s=t, checked_window_s=[lo, hi])
    return dict(status='prior_pairing_check_insufficient', eligible_for_review=False,
                original_decision=d)


def copy_checked(source, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    digest = sha(source)
    assert sha(dest) == digest
    return digest


def coco_add(coco, ident, rel, size, boxes, category):
    w, h = size
    coco['images'].append(dict(id=ident, file_name=rel, width=w, height=h))
    for x0, y0, x1, y1 in boxes:
        coco['annotations'].append(dict(id=len(coco['annotations']) + 1, image_id=ident,
            category_id=CLASSES.index(category) + 1, bbox=[x0, y0, x1-x0, y1-y0],
            area=(x1-x0)*(y1-y0), iscrowd=0))


def yolo(path, boxes, size, category):
    w, h = size
    lines = [f'{CLASSES.index(category)} {(a+c)/2/w:.10f} {(b+d)/2/h:.10f} {(c-a)/w:.10f} {(d-b)/h:.10f}'
             for a, b, c, d in boxes]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', 'utf-8')


def preview(row):
    camera = Image.open(OUT / row['camera_image']).convert('RGB')
    a = np.array(Image.open(OUT / row['sonar_image']))
    h, w = a.shape
    son = Image.fromarray(np.clip(a.astype(float)*2.5, 0, 255).astype(np.uint8)).convert('RGB')
    canvas = Image.new('RGB', (1040, 485), '#eef2f5')
    canvas.paste(camera, (0, 55))
    canvas.paste(son.resize((384, 360)), (650, 55))
    d = ImageDraw.Draw(canvas)
    d.text((8, 5), row['sample'] + ' / ' + row['category'], fill='black')
    d.text((8, 23), 'CAMERA SD: original boxes     |     SONAR: raw, no flip; display gain 2.5', fill='black')
    for b in row['camera_boxes_xyxy']:
        # Out-of-bounds coordinates remain unchanged in JSON; preview clips only to its panel.
        cc = camera.copy()
        ImageDraw.Draw(cc).rectangle(tuple(b), outline='#ff6633' if row['camera_issues'] else '#00ff60', width=2)
        canvas.paste(cc, (0, 55))
    b = row['sonar_bbox_xyxy']
    d.rectangle((650+b[0]*384/w, 55+b[1]*360/h, min(1033,650+b[2]*384/w), min(414,55+b[3]*360/h)), outline='#00ff60', width=2)
    d.text((8, 425), row['pairing']['status'], fill='black')
    d.text((8, 445), 'Camera issues: ' + ', '.join(row['camera_issues']), fill='#b02010')
    d.text((8, 465), 'Candidate only: no new synchronization or expert-GT certification.', fill='black')
    path = OUT / 'previews' / (row['sample'] + '.jpg')
    path.parent.mkdir(exist_ok=True)
    canvas.save(path, quality=92)
    return path.relative_to(OUT).as_posix()


def main():
    assert not OUT.exists(), 'Refuse to overwrite this named run'
    mpath = CAM / 'manifest-resolved.json'
    spath = SON / 'manifest.json'
    manifest, sonar = read(mpath), read(spath)
    allowed = set(manifest['identity']['recordings'])
    assert len(allowed) == 40
    members = manifest['items']
    assert all(x['recording'] in allowed and x.get('paired_role') in (None, 'train', 'val', 'val_id') for x in members)
    lookup = {x['sample']: x for x in members}
    assert len(lookup) == len(members)
    decision_paths = [ROOT/'DataSet/sonar_camera_continuous_timing/recording-decisions.json',
                      ROOT/'DataSet/sonar_four_recording_timing/decisions.json']
    decisions = {x['recording']: x for p in decision_paths for x in read(p)['records']}
    OUT.mkdir()
    source_hashes = {str(p.relative_to(ROOT)): sha(p) for p in [mpath, spath, *decision_paths]}
    inventory = []
    for m in members:
        boxes, issues = label(m)
        inventory.append(dict(sample=m['sample'], recording=m['recording'], category=m['category'],
            aris_frame=m['aris_frame'], camera_boxes_xyxy=boxes, camera_issues=issues,
            pairing=sync_info(m, decisions), reference_sd=m.get('reference_sd'), label_copy=m.get('label_copy')))
    inv = {x['sample']: x for x in inventory}
    save(OUT/'source-inventory.json', inventory)
    paired = []
    cats = [dict(id=i+1, name=c) for i,c in enumerate(CLASSES)]
    coco = {k:dict(images=[], annotations=[], categories=cats, info=dict(description='Format-valid paired candidates; not frozen training GT')) for k in ['camera','sonar']}
    for i,s in enumerate(sonar, 1):
        m = lookup[s['sample']]
        assert s['recording'] == m['recording'] and s['frame'] == m['aris_frame'] and s['category'] == m['category']
        assert s['reference_sd'] == m['reference_sd']
        assert sha(SON/s['export_image']) == s['export_image_sha256']
        assert sha(CAM/m['label_copy']) == m['original_label_sha256_before']
        sample = s['sample']
        cr = f'camera/images/{sample}.jpg'
        sr = f'sonar/images/{sample}.png'
        lr = f'camera/labels_original/{sample}.json'
        ch = copy_checked(CAM/m['reference_sd'], OUT/cr)
        sh = copy_checked(SON/s['export_image'], OUT/sr)
        lh = copy_checked(CAM/m['label_copy'], OUT/lr)
        with Image.open(OUT/cr) as image:
            assert image.size == (640,360)
        with Image.open(OUT/sr) as image:
            sw,shh = image.size
            assert [shh,sw] == s['shape_hw']
        info = inv[sample]
        r = dict(sample=sample, recording=m['recording'], category=m['category'],
            aris_frame=m['aris_frame'], aris_time_us=m['aris_time_us'], sd_index=m['sd_index'], sd_pts=m['sd_pts'],
            camera_image=cr, camera_image_sha256=ch, camera_label_original=lr, camera_label_sha256=lh,
            camera_boxes_xyxy=info['camera_boxes_xyxy'], camera_issues=info['camera_issues'],
            sonar_image=sr, sonar_image_sha256=sh, sonar_bbox_xyxy=s['bbox_xyxy'], sonar_size_wh=[sw,shh],
            sonar_annotation_author=s['annotation_author'], sonar_source_manifest=str(spath.relative_to(ROOT)),
            camera_source_manifest=str(mpath.relative_to(ROOT)), source_reference_sd=m['reference_sd'],
            source_label_copy=m['label_copy'], pairing=info['pairing'], original_paired_role=m.get('paired_role'),
            annotation_expert_verified=False, training_split=None, training_ready=False,
            format_valid_pair=not info['camera_issues'],
            eligible_for_pairing_review=not info['camera_issues'] and info['pairing']['eligible_for_review'])
        # Do not export a training-style camera/sonar pair for invalid camera coordinates.
        if r['format_valid_pair']:
            for kind, rel, size, boxes in [('camera',cr,(640,360),r['camera_boxes_xyxy']), ('sonar',sr,(sw,shh),[s['bbox_xyxy']])]:
                coco_add(coco[kind], i, rel, size, boxes, m['category'])
                yolo(OUT/kind/'labels'/f'{sample}.txt', boxes, size, m['category'])
        r['preview'] = preview(r)
        paired.append(r)
    save(OUT/'manifest.json', paired)
    for kind, c in coco.items():
        save(OUT/kind/'annotations.coco.json', c)
    (OUT/'classes.txt').write_text('\n'.join(CLASSES)+'\n','utf-8')
    byrec = collections.defaultdict(list)
    for x in inventory:
        byrec[x['recording']].append(x)
    queue, coverage = [], []
    for rec in manifest['recordings']:
        rr = sorted(byrec[rec['recording']], key=lambda x:x['aris_frame'])
        # Deterministic whole-sequence uniform queue, unlike the old central-60% subset.
        positions = [round(i*(len(rr)-1)/99) for i in range(100)]
        assert len(set(positions)) == 100
        for j in positions:
            x = dict(rr[j]); x['sonar_bbox_xyxy'] = None; x['status'] = 'pending_visual_review'
            x['already_in_sonar_export'] = x['sample'] in {s['sample'] for s in sonar}
            queue.append(x)
        pp = [x for x in paired if x['recording'] == rec['recording']]
        available = sum(not x['camera_issues'] and x['pairing']['eligible_for_review'] for x in rr)
        count = sum(x['eligible_for_pairing_review'] for x in pp)
        coverage.append(dict(recording=rec['recording'],category=rec['category'],allowed_native=len(rr),
            camera_format_valid=sum(not x['camera_issues'] for x in rr),
            available_before_new_sonar_review=available,existing_sonar_labels=len(pp),
            linked_format_valid=sum(x['format_valid_pair'] for x in pp),
            eligible_for_pairing_review=count,missing_to_100=max(0,100-count),
            pairing=sync_info(lookup[rr[len(rr)//2]['sample']],decisions)['status']))
    save(OUT/'uniform-review-queue.json',queue)
    save(OUT/'recording-coverage.json',coverage)
    summary = dict(name='paired_paper_scale',status='incomplete_candidate_only',
        target_pairs=3000,target_recordings_per_class=10,target_pairs_per_recording=100,
        allowed_recordings=40,allowed_identities=len(members),linked_pairs=len(paired),
        format_valid_pairs=sum(x['format_valid_pair'] for x in paired),
        eligible_for_pairing_review=sum(x['eligible_for_pairing_review'] for x in paired),
        prior_pairing_check_insufficient=sum(not x['pairing']['eligible_for_review'] for x in paired),
        supported_in_checked_window=sum(x['pairing']['status']=='supported_in_checked_window' and x['format_valid_pair'] for x in paired),
        training_ready=0,uniform_pending_review=len(queue),source_hashes=source_hashes,
        per_class={})
    for cat in CLASSES:
        pp=[x for x in paired if x['category']==cat]
        cc=[x for x in coverage if x['category']==cat]
        eligible=sum(x['eligible_for_pairing_review'] for x in pp)
        summary['per_class'][cat]=dict(linked=len(pp),format_valid=sum(x['format_valid_pair'] for x in pp),
            eligible_for_pairing_review=eligible,missing_to_1000=1000-eligible,
            recordings_with_100_review_candidates=sum(x['eligible_for_pairing_review']>=100 for x in cc),
            recordings_with_at_least_100_source_candidates=sum(x['available_before_new_sonar_review']>=100 for x in cc))
    save(OUT/'summary.json',summary)
    # Self-contained gallery data; works with file:// without fetching JSON.
    gallery=[{k:r[k] for k in ('sample','category','recording','preview','format_valid_pair','eligible_for_pairing_review','pairing')} for r in paired]
    page='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>声呐—相机配对候选</title>
<style>body{font:16px system-ui;background:#eef2f5;color:#172c3c;margin:28px}select,input{padding:8px;margin:5px}article{background:white;padding:12px;margin:14px 0;border-radius:10px;max-width:1040px}img{width:100%;height:auto}small{color:#654}h1{font-size:26px}</style>
<h1>声呐—相机配对候选 · 尚未达到论文规模</h1>
<p>CMHD：3000 对，3 类 × 10 轨迹 × 100 对；1800/600/600 按轨迹划分。CMOLD：约 4700 对用于训练和验证。</p>
<p>本页保留已有声呐框与原相机框。格式通过≠同步通过≠正式训练集。相机 640×360；声呐 raw 未翻转，显示时调整比例和亮度。</p>
<p id="stats"></p><label>类别 <select id="cat"><option value="">全部</option></select></label>
<label>录音 <select id="rec"><option value="">全部</option></select></label>
<label><input type="checkbox" id="issues">包含越界框／此前配对检查不足项</label><p id="count"></p><main id="list"></main>
<script>const rows=DATA;const summary=SUMMARY;
stats.textContent=`关联 ${summary.linked_pairs} 对；框格式有效 ${summary.format_valid_pairs} 对；排除既有配对疑点后待核 ${summary.eligible_for_pairing_review} 对；正式准入 0。`;
for(const v of [...new Set(rows.map(r=>r.category))])cat.add(new Option(v,v));for(const v of [...new Set(rows.map(r=>r.recording))])rec.add(new Option(v,v));
function render(){const selected=rows.filter(r=>(!cat.value||r.category===cat.value)&&(!rec.value||r.recording===rec.value)&&(issues.checked||r.eligible_for_pairing_review));count.textContent=selected.length+' 对';list.replaceChildren();for(const r of selected){const a=document.createElement('article');const h=document.createElement('div');h.textContent=r.sample+' | '+r.pairing.status;const im=document.createElement('img');im.src=r.preview;im.loading='lazy';im.alt=r.sample+' 相机与声呐';a.append(h,im);list.append(a)}}cat.onchange=rec.onchange=issues.onchange=render;render();</script></html>'''
    page=page.replace('DATA',json.dumps(gallery,ensure_ascii=False)).replace('SUMMARY',json.dumps(summary,ensure_ascii=False))
    (OUT/'index.html').write_text(page,'utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
