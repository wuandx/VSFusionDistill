"""Recover both modalities for extra recording candidates; no automatic paired acceptance."""
from prepare_camera_more_recordings import ROOT,DATA,read,save,sha
from pathlib import Path
from collections import Counter
import csv
import sys
sys.path.insert(0,str(Path(__file__).parent/'_sonar_audit_deps'))
import cv2
import numpy as np
from PIL import Image,ImageDraw,ImageFont
OUT=ROOT/'DataSet/paired_more_recordings_review_verified'
CAM=ROOT/'DataSet/camera_more_recordings_candidate'
BLOCKED={'2023-09-20_173329','2023-09-21_100927','2023-09-21_101131','2023-09-21_120653','2023-09-21_120912'}
def main():
    OUT.mkdir(exist_ok=False)
    inv={r['recording']:r for r in read(ROOT/'DataSet/recording_expansion_94_audit/inventory.json')}
    rows=[];summaries=[];missing=[];font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',15)
    for rec in sorted({r['recording'] for r in read(CAM/'manifest.json')}):
        folder=OUT/rec;folder.mkdir()
        native=DATA/'uxo-full/extracted/recordings'/inv[rec]['category_dir']/rec
        items=read(CAM/rec/'manifest.json');assert len(items)==100
        missing.extend(dict(sample=r['sample'],reason='missing_same_frame_aris_raw') for r in items if not (native/'aris_raw'/f'{r["frame"]:04d}.pgm').is_file())
        items=[r for r in items if (native/'aris_raw'/f'{r["frame"]:04d}.pgm').is_file()]
        pilot=read(ROOT/'DataSet/expanded_paired_recordings/full-review'/rec/'spec.json') if (ROOT/'DataSet/expanded_paired_recordings/full-review'/rec/'spec.json').exists() else None
        prior={r['sample']:r for r in pilot['items']} if pilot else {}
        metadata=DATA/'data_processed/aris'/rec/(rec+'_frames.csv')
        md={int(r['FrameIndex']):r for r in csv.DictReader(metadata.open(encoding='utf-8-sig'))}
        sheets=[]
        for j,r in enumerate(items):
            raw=native/'aris_raw'/f'{r["frame"]:04d}.pgm';assert raw.is_file()
            arr=cv2.imdecode(np.frombuffer(raw.read_bytes(),np.uint8),cv2.IMREAD_UNCHANGED)
            assert arr.ndim==2 and arr.shape[1]==128
            camera=CAM/r['image'];assert sha(camera)==r['source_sha256']
            p=prior.get(r['sample'],{});box=p.get('proposal_xyxy')
            record=dict(sample=r['sample'],recording=rec,category=r['category'],role='train_candidate',group_id=r['group_id'],scene_id=r['scene_id'],frame=r['frame'],aris_time_us=int(md[r['frame']]['FrameTime']),sd_index=r['sd_index'],camera_source=str(camera),camera_sha256=sha(camera),camera_boxes_xyxy=[r['box']],camera_label_source=r['label_source'],camera_label_sha256=r['label_sha256'],camera_review='assistant_reviewed_corrected_SD',sonar_source=str(raw),sonar_sha256=sha(raw),sonar_size_wh=[arr.shape[1],arr.shape[0]],sonar_bbox_xyxy=None,prior_unaccepted_sonar_proposal=box,decision='blocked_prior_cross_modal_pairing' if rec in BLOCKED else 'pending_sonar_box_and_pair_review',precision_sync_certified=False,expert_verified=False,temporal_source=r['temporal_source'],nominal=r['nominal'])
            rows.append(record)
            # Render all 400 actionable frames; blocked sources retain full mapping but only a pilot sheet.
            show=rec not in BLOCKED or j in [round(i*99/11) for i in range(12)]
            if not show:continue
            ordinal=sum(x['recording']==rec for x in rows)-1
            display_idx=j if rec not in BLOCKED else [round(i*99/11) for i in range(12)].index(j)
            if display_idx%12==0:
                canvas=Image.new('RGB',(1800,2090),'#f4f6fa');draw=ImageDraw.Draw(canvas)
                draw.text((5,4),rec+' | corrected SD GT + full ARIS raw | NO ACCEPTED NEW SONAR GT',font=font,fill='black')
            x=(display_idx%12%3)*600;y=30+(display_idx%12//3)*510
            draw.text((x+3,y),f'{j}: ARIS {r["frame"]} / SD {r["sd_index"]}',font=font,fill='black')
            im=Image.open(camera).convert('RGB');ImageDraw.Draw(im).rectangle(r['box'],outline='#00ff40',width=2)
            canvas.paste(im.resize((596,335)),(x,y+22))
            sonar=Image.fromarray(np.clip(arr.astype(np.float32)*2.5,0,255).astype(np.uint8)).convert('RGB')
            canvas.paste(sonar.resize((128,145)),(x,y+360));canvas.paste(sonar.resize((460,145)),(x+132,y+360))
            if display_idx%12==11 or j==len(items)-1:
                path=folder/f'page-{display_idx//12:02d}.jpg';canvas.save(path,quality=94);sheets.append(dict(path=str(path.relative_to(OUT)),sha256=sha(path)))
        summaries.append(dict(recording=rec,candidates=len(items),prior_pairing_block=rec in BLOCKED,accepted_new_pairs=0,sheets=sheets,metadata_sha256=sha(metadata)))
    save(OUT/'manifest.json',rows);save(OUT/'recordings.json',summaries);save(OUT/'missing-aris.json',missing)
    save(OUT/'summary.json',dict(candidate_pairs=len(rows),missing_same_frame_aris=len(missing),actionable_sonar_review_candidates=sum(r['decision']=='pending_sonar_box_and_pair_review' for r in rows),blocked_prior_pairing=sum(r['decision']=='blocked_prior_cross_modal_pairing' for r in rows),accepted_new_pairs=0,training_started=False,current_4081_pairs_unchanged=True,camera_only_expansion_not_activated=True,states=dict(Counter(r['decision'] for r in rows))))
    cards=[]
    for r in summaries:cards.append(f'<h2>{r["recording"]} | '+('PRIOR PAIRING BLOCK RETAINED' if r['prior_pairing_block'] else 'PENDING SONAR BOX + PAIR REVIEW')+'</h2>'+''.join(f'<img loading="lazy" style="max-width:100%" src="{s["path"]}">' for s in r['sheets']))
    (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Paired recording expansion review</title><h1>Both modalities required; no newly accepted pairs yet</h1>'+''.join(cards),encoding='utf-8')
    print((OUT/'summary.json').read_text())
if __name__=='__main__':main()
