"""Inventory94 metadata and allowed extra camera review; no original-test content reads."""
import csv
from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent / '_sonar_audit_deps'))
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DATA = Path('D:/pby')
OUT = ROOT / 'DataSet/recording_expansion_94_audit'
CLASSES = {'100lbs_bomb': '100lbs_aircraft_bomb', '100lbs_bomb_(floor)': '100lbs_aircraft_bomb',
           '15cm_mortar': 'mortar_shell', '20lbs_incendiary': 'incindiary_grenade'}


def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p, value): Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    OUT.mkdir(exist_ok=False)
    paths = [DATA/'uxo-full/inventory.json', DATA/'uxo-full/split_manifest.json', DATA/'data_processed/matches.csv',
             ROOT/'DataSet/scene_stratified_mortar_recovered_candidate/recordings.csv',
             ROOT/'DataSet/expanded_paired_recordings/inventory.json']
    fixed = {str(p): sha(p) for p in paths}
    inventory = read(paths[0])['recordings']; legacy = read(paths[1])['recordings']
    matches = {Path(r['aris_file']).name: r for r in csv.DictReader(paths[2].open(encoding='utf-8-sig'))}
    current = {r['recording']: r for r in csv.DictReader(paths[3].open(encoding='utf-8-sig'))}
    old_review = {r['recording']: r for r in read(paths[4])}
    assert len(inventory) == len(matches) == len(legacy) == 94
    rows, proposals = [], []
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 14)
    for rec, meta in sorted(inventory.items()):
        match = matches[rec]
        category = CLASSES.get(meta['category_dir'])
        clip = DATA / 'data_processed' / match['gopro_file'] if match['gopro_file'] else None
        if category is None: state = 'other_target_test_cylinder'
        elif legacy[rec]['split'] == 'test': state = 'original_test_closed'
        elif rec in current: state = 'current_' + current[rec]['role']
        elif clip is None or not clip.is_file(): state = 'no_matched_camera_clip'
        elif rec in old_review: state = 'extra_existing_labels_camera_review'
        else: state = 'extra_camera_needs_annotation'
        shared = []
        if state.startswith('extra_'):
            for held, info in current.items():
                if info['role'] not in ['val','test']: continue
                for key in ['gantry_file','gopro_file']:
                    if match[key] and match[key] == matches[held][key]: shared.append(dict(recording=held, role=info['role'], field=key))
        row = dict(recording=rec, category=category, category_dir=meta['category_dir'], state=state,
                   original_role=legacy[rec]['split'], current_role=current.get(rec,{}).get('role'),
                   current_group=current.get(rec,{}).get('group_id'), source_gopro_image_count=meta['n_gopro'],
                   source_annotated_count=meta['n_annotated'], source_paired_count=meta['annotated_with_gopro_and_aris'],
                   matched_sd_clip_exists=bool(clip and clip.is_file()), matched_sd_clip=str(clip) if clip else None,
                   original_exclude_reason=legacy[rec].get('exclude_reason'), prior_review=old_review.get(rec,{}).get('status'),
                   shared_heldout_source=shared, notes=match['notes'], preview=None)
        rows.append(row)
        if not state.startswith('extra_'): continue
        assert legacy[rec]['split'] != 'test' and rec not in current and not shared
        native = DATA/'uxo-full/extracted/recordings'/meta['category_dir']/rec
        images = sorted((native/'gopro').glob('*.jpg'), key=lambda p:int(p.stem))
        assert images
        labels = {int(p.stem):p for p in (native/'labels').glob('*.json')}
        available = [p for p in images if int(p.stem) in labels] if state=='extra_existing_labels_camera_review' else images
        assert len(available) >= 12
        selected = [available[round(i*(len(available)-1)/11)] for i in range(12)]
        folder = OUT / rec; folder.mkdir(); items = []
        canvas = Image.new('RGB',(1280,690),'#f4f6fa'); draw=ImageDraw.Draw(canvas)
        draw.text((4,3), rec+' | CAMERA-ONLY native image + existing SD label | proposed, not accepted',font=font,fill='black')
        for j, path in enumerate(selected):
            image=Image.open(path).convert('RGB'); native_size=image.size
            assert native_size == (1920,1080)
            image=image.resize((640,360),Image.Resampling.BILINEAR)
            lab=labels.get(int(path.stem)); boxes=[]; in_bounds=None
            if lab:
                a=read(lab); assert a['class']==category
                boxes=[a[k] for k in ['x_min','y_min','x_max','y_max']]
                in_bounds=0<=boxes[0]<boxes[2]<=640 and 0<=boxes[1]<boxes[3]<=360
                ImageDraw.Draw(image).rectangle(boxes,outline='#00ff40' if in_bounds else '#ff3030',width=3)
            dest=folder/f'{j:02d}.jpg'; image.save(dest,quality=92)
            x=(j%4)*320; y=28+(j//4)*220
            draw.text((x+3,y),f'{j} frame{path.stem} '+('GT in-bounds' if in_bounds else 'GT OUT-OF-BOUNDS' if lab else 'NO GT'),font=font,fill='black')
            canvas.paste(image.resize((320,180)),(x,y+19))
            items.append(dict(recording=rec, category=category, ordinal=j, native_frame=int(path.stem),
                 source=str(path),source_sha256=sha(path),native_size=list(native_size),
                 preview=str(dest.relative_to(OUT)),preview_sha256=sha(dest),
                 source_label=str(lab) if lab else None,source_label_sha256=sha(lab) if lab else None,
                 boxes_xyxy_sd=boxes,bbox_in_bounds=in_bounds,decision='unreviewed',precision_sync_certified=False))
        sheet=folder/'overview.jpg';canvas.save(sheet,quality=94)
        row['preview']=str(sheet.relative_to(OUT)); row['native_camera_label_intersection']=len([p for p in images if int(p.stem) in labels])
        dump(folder/'proposals.json',items);proposals.extend(items)
    counts=dict(Counter(r['state'] for r in rows));assert counts==dict(other_target_test_cylinder=22,original_test_closed=10,current_train=21,current_val=9,current_test=7,no_matched_camera_clip=11,extra_existing_labels_camera_review=10,extra_camera_needs_annotation=4)
    summary=dict(total_recordings=94,target_class_recordings=72,other_target_recordings=22,
                 target_non_original_test=62,target_non_original_test_with_camera=51,current_pairs_recordings=37,
                 state_counts=counts,extra_camera_recordings=14,preview_proposals=len(proposals),
                 all_extra_shared_heldout_sources=0,original_test_content_read=False,training=False,
                 note='n_gopro counts camera image availability, not camera GT. Preview resize1920x1080 to640x360; bounds are not acceptance.')
    dump(OUT/'inventory.json',rows);dump(OUT/'proposals.json',proposals);dump(OUT/'summary.json',summary);dump(OUT/'input-sha256.json',fixed)
    with (OUT/'inventory.csv').open('w',encoding='utf-8-sig',newline='') as f:
        keys=list(dict.fromkeys(k for r in rows for k in r));writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader()
        writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rows)
    sections=[]
    for r in rows:
        if r['preview']: sections.append(f'<section><h2>{r["recording"]} — {html.escape(r["state"])}</h2><p>{html.escape(r["notes"])}</p><img style="max-width:100%" src="{r["preview"]}"></section>')
    (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>94 recording expansion audit</title><h1>14 extra camera-source proposals</h1><p>Preview only; no acceptance or training. Current train/val/test unchanged.</p>'+''.join(sections),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=True))


if __name__=='__main__':main()
