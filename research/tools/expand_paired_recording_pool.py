"""Expand non-test recording inventory and render SD/raw pilots, never auto-accept."""
from collections import Counter, defaultdict
import csv
from fractions import Fraction
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).parent / '_sonar_audit_deps'))
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'DataSet/expanded_paired_recordings'
DATA = Path('D:/pby')
NATIVE = DATA / 'uxo-full/extracted/recordings'
CLASSES = {'100lbs_aircraft_bomb': '炸弹', 'mortar_shell': '迫击炮', 'incindiary_grenade': '燃烧弹'}
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p, x): p.write_text(json.dumps(x, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def run(args):
    r = subprocess.run(args, capture_output=True)
    if r.returncode: raise RuntimeError(r.stderr.decode(errors='replace')[-2000:])
    return r.stdout
def nominal(note):
    def number(k):
        m = re.search(r'\b'+k+r'\s*:\s*(-?\d+(?:\.\d+)?)', note, re.I)
        return m[1] if m else 'unknown'
    return dict(placement='floor' if '(floor)' in note.lower() else 'standard',
                trajectory='ellipse' if 'ellipse' in note.lower() else 'flyby' if 'flyby' in note.lower() else 'L_to_R' if 'l to r' in note.lower() else 'unknown',
                **{k:number(k) for k in ['z','tilt','roll','pan']})
def condition(r): return '|'.join(str(r[k]) for k in ['placement','trajectory','z','tilt','roll','pan'])
def csvout(p, rows):
    flat = [{k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rows]
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in flat for k in r)));w.writeheader();w.writerows(flat)

def main():
    assert not (OUT/'summary.json').exists(), 'Preserve completed named audit'
    OUT.mkdir(exist_ok=True); (OUT/'pilots').mkdir(exist_ok=True)
    paths = [ROOT/'DataSet/paired_paper_scale/source-inventory.json', ROOT/'DataSet/paired_assistant_truncated_review/export/manifest.json',
             ROOT/'DataSet/paired_assistant_full_review/export/all-recording-coverage.json', DATA/'uxo-full/split_manifest.json', DATA/'uxo-full/inventory.json',
             DATA/'data_processed/matches.csv', ROOT/'DataSet/paired_recording_condition_coverage_candidate/protocol.json']
    fixed = {str(p):sha(p) for p in paths}
    src, delivered, review, legacy, inventory = map(read, paths[:5])
    byrec=defaultdict(list)
    for r in src: byrec[r['recording']].append(r)
    oldrecs={r['recording'] for r in delivered}; assert len(oldrecs)==30 and len(byrec)==40
    coverage={r['recording']:r for r in review}
    matches={Path(x['aris_file']).name:x for x in csv.DictReader(paths[5].open(encoding='utf-8-sig'))}
    extra=[]
    for rec, row in legacy['recordings'].items():
        if rec not in byrec and row['split']!='test' and row.get('category') in CLASSES and inventory['recordings'][rec].get('annotated_with_gopro_and_aris',0)>0:
            extra.append(rec)
    assert len(extra)==7, extra
    if (OUT/'inventory.json').exists():
        rows=read(OUT/'inventory.json')
        for r in rows:
            if not r['pilot_sheet']: continue
            folder=OUT/'pilots'/r['recording'];pilot=read(folder/'pilot.json')
            assert sha(folder/'pilot.jpg')==pilot['sheet_sha256']
            for p in pilot['items']:
                assert sha(OUT/p['camera_image'])==p['camera_sha256'] and sha(p['original_label'])==p['original_label_sha256'] and sha(p['sonar_source'])==p['sonar_sha256']
            root=Path(r['source_root']);rec=r['recording']
            for p in [Path(pilot['source_clip']),DATA/'data_processed/aris'/rec/(rec+'_frames.csv'),root/'notes.txt',root/'aris_frame_meta.csv']:
                fixed[str(p)]=sha(p)
        finalize(rows,fixed,oldrecs,extra)
        return
    rows=[]
    for rec in sorted(set(byrec)|set(extra)):
        legacyrow=legacy['recordings'][rec]; assert legacyrow['split']!='test'
        match=matches[rec]; roots=[g/rec for g in NATIVE.iterdir() if (g/rec).is_dir()]; assert len(roots)==1
        root=roots[0]; note=(root/'notes.txt').read_text(encoding='utf-8-sig'); assert note.strip()==match['notes'].strip()
        cat=legacyrow['category']; n=nominal(note)
        rr=byrec.get(rec,[]); accepted=sum(x['recording']==rec for x in delivered)
        issues=dict(Counter(i for x in rr for i in x['camera_issues'])); pairing=dict(Counter(x['pairing']['status'] for x in rr))
        if rec in oldrecs: state='existing_reviewed_recording'; reason='沿用当前接受包；不重新认证同步或专家GT'
        elif pairing.get('prior_pairing_check_insufficient'): state='pairing_failed_retained';reason='历史配对检查未通过；不自动恢复，不为扩量改时间'
        elif issues.get('camera_bbox_out_of_bounds')==len(rr) and rr: state='camera_labels_pending';reason='全序列原相机框越界，需核查原坐标与可见部分；未改框'
        elif rec in byrec: state='sonar_review_pending';reason='旧双端审核0接受；含截断与回波边界疑点，需新审阅，不能作负样本'
        else: state='new_non_test_pilot';reason='旧excluded基于投影残差；本轮新建SD/raw直接审阅试点，尚未验收'
        row=dict(recording=rec,category=cat,**n,primary_condition=condition(n),legacy_role=legacyrow['split'],legacy_exclude_reason=legacyrow['exclude_reason'],
                 status=state,reason=reason,old_delivered=accepted,source_count=len(rr) if rr else inventory['recordings'][rec]['annotated_with_gopro_and_aris'],
                 source_sd_count=sum(bool(x['reference_sd']) for x in rr) if rr else None,camera_issues=issues,pairing_status=pairing,
                 previous_review=coverage.get(rec,{}),notes=note,source_root=str(root),pilot_count=0,pilot_sheet=None)
        rows.append(row)
    save(OUT/'inventory-before-pilots.json', rows)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
    for row in rows:
        if row['recording'] not in extra: continue
        rec=row['recording']; root=Path(row['source_root']); folder=OUT/'pilots'/rec; folder.mkdir()
        match=matches[rec]; clip=DATA/'data_processed/gopro/clips_sd'/Path(match['gopro_file']).name
        meta=DATA/'data_processed/aris'/rec/(rec+'_frames.csv')
        for p in [clip,meta,root/'notes.txt',root/'aris_frame_meta.csv']: fixed[str(p)]=sha(p)
        probe=json.loads(run(['ffprobe','-v','error','-select_streams','v:0','-show_streams','-show_entries','stream=width,height,avg_frame_rate,nb_frames,start_time','-of','json',str(clip)]))['streams'][0]
        assert (probe['width'],probe['height'])==(640,360)
        fps=float(Fraction(probe['avg_frame_rate'])); count=int(probe['nb_frames'])
        frames={int(x['FrameIndex']):x for x in csv.DictReader(meta.open(encoding='utf-8-sig'))}; onset=int(frames[int(match['aris_onset'])]['FrameTime'])
        labels=sorted((root/'labels').glob('*.json'),key=lambda p:int(p.stem)); available=[]
        for lab in labels:
            frame=int(lab.stem); assert frame in frames
            si=int((int(frames[frame]['FrameTime'])-onset)/1e6*fps)+int(match['gopro_offset'])
            raw=root/'aris_raw'/f'{frame:04d}.pgm'
            if not raw.is_file(): raw=root/'aris_raw'/(lab.stem+'.pgm')
            if 0<=si<count and raw.is_file(): available.append((lab,raw,frame,si))
        assert len(available)>=12
        take=[available[round(j*(len(available)-1)/11)] for j in range(12)]
        sd=folder/'sd';sd.mkdir(); expr='+'.join(f'eq(n\\,{x})' for x in sorted({a[3] for a in take}))
        run(['ffmpeg','-hide_banner','-loglevel','error','-threads','2','-i',str(clip),'-vf','select='+expr,'-fps_mode','passthrough','-q:v','2',str(sd/'%03d.jpg')])
        extracted=sorted(sd.glob('*.jpg'));indices=sorted({a[3] for a in take});assert len(extracted)==len(indices)
        decoded=dict(zip(indices,extracted)); pilot=[]
        canvas=Image.new('RGB',(1800,2300),'#f4f6f8');draw=ImageDraw.Draw(canvas)
        draw.text((8,6),f'{rec} | SD original GT + SONAR raw; no sonar GT yet. Display gain=2.5. Not accepted.',font=font,fill='black')
        for j,(lab,raw,frame,si) in enumerate(take):
            label=read(lab); assert label['class']==row['category']; b=[label[k] for k in ['x_min','y_min','x_max','y_max']]
            srcbytes=np.frombuffer(raw.read_bytes(),np.uint8);a=cv2.imdecode(srcbytes,cv2.IMREAD_UNCHANGED); assert a.ndim==2 and a.shape[1]==128
            im=Image.open(decoded[si]).convert('RGB');assert im.size==(640,360); ImageDraw.Draw(im).rectangle(b,outline='#00ff60',width=2)
            ox=(j%3)*600;oy=35+(j//3)*565
            draw.text((ox+3,oy),f'{j}: frame {frame} / SD {si} / GT {b}',font=font,fill='black');canvas.paste(im.resize((596,335)),(ox,oy+24))
            son=Image.fromarray(np.clip(a.astype(float)*2.5,0,255).astype(np.uint8)).convert('RGB')
            canvas.paste(son.resize((128,190)),(ox,oy+365));canvas.paste(son.resize((460,190)),(ox+132,oy+365))
            item=dict(ordinal=j,sample=f'{rec}_{frame:04d}',recording=rec,category=row['category'],frame=frame,sd_index=si,camera_boxes_xyxy=[b],
                      camera_bbox_in_bounds=0<=b[0]<b[2]<=640 and 0<=b[1]<b[3]<=360,
                      camera_image=str(decoded[si].relative_to(OUT)),camera_sha256=sha(decoded[si]),original_label=str(lab),original_label_sha256=sha(lab),
                      sonar_source=str(raw),sonar_sha256=sha(raw),sonar_shape=list(a.shape),sonar_bbox_xyxy=None,decision='unreviewed',
                      precision_sync_certified=False,expert_verified=False,metadata=frames[frame])
            pilot.append(item)
        sheet=folder/'pilot.jpg';canvas.save(sheet,quality=95);save(folder/'pilot.json',dict(sheet_sha256=sha(sheet),items=pilot,source_clip=str(clip),probe=probe,available_native_sd_pairs=len(available)))
        row.update(pilot_count=len(pilot),pilot_sheet=str(sheet.relative_to(OUT)),source_sd_count=len(available),pilot_in_bounds=sum(x['camera_bbox_in_bounds'] for x in pilot))
        print(json.dumps(dict(recording=rec,available=len(available),pilot=len(pilot)),ensure_ascii=False),flush=True)
    save(OUT/'inventory.json',rows)
    finalize(rows,fixed,oldrecs,extra)

def finalize(rows,fixed,oldrecs,extra):
    csvout(OUT/'recordings.csv',rows)
    summary=dict(recordings=len(rows),old_reviewed_recordings=len(oldrecs),additional_existing_development=10,new_non_test_sources=len(extra),
                 by_category=dict(Counter(x['category'] for x in rows)),by_status=dict(Counter(x['status'] for x in rows)),
                 new_pilot_pairs=sum(x['pilot_count'] for x in rows),new_pilot_accepted=0,source_hash_unchanged=all(sha(Path(p))==s for p,s in fixed.items()),
                 original_test_images_opened=0,model_inference=False,training=False,old_split_changed=False)
    assert summary['source_hash_unchanged'];save(OUT/'summary.json',summary);save(OUT/'inputs-sha256.json',fixed)
    cards=[]
    for r in rows:
        image=f'<a href="{r["pilot_sheet"]}"><img src="{r["pilot_sheet"]}" loading="lazy"></a>' if r['pilot_sheet'] else ''
        cards.append(f'<article id="{r["recording"]}"><h3>{r["recording"]} · {CLASSES[r["category"]]} · {r["status"]}</h3><p>{html.escape(r["primary_condition"])}；原角色 {r["legacy_role"]}；原接受 {r["old_delivered"]}；库存 {r["source_count"]}；SD可对应 {r["source_sd_count"]}</p><p>{html.escape(r["reason"])}</p><p>旧排除理由：{html.escape(r["legacy_exclude_reason"])}</p>{image}<details><summary>原始notes</summary><pre>{html.escape(r["notes"])}</pre></details></article>')
    (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>扩充配对录音</title><style>body{font:16px/1.6 sans-serif;max-width:1400px;margin:25px auto;padding:12px}article{border:1px solid #bbb;margin:16px 0;padding:15px}img{max-width:100%;width:1200px}pre{white-space:pre-wrap}</style><h1>扩充相机—声呐共用录音</h1><p>47条来源审计：原40条 + 7条非test新来源。新增84对仅试点，未审/未验收，不能当作已扩成37条训练数据。旧划分不变、无训练、不读原test样本；新来源曾因投影残差排除，本轮重新检查直接标注可用性。</p><p><a href="recordings.csv">47条录音表</a> · <a href="summary.json">数量核验</a></p>'+''.join(cards),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
