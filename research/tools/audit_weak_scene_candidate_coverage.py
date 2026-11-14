"""Compare candidate metadata with fixed val failures; no model/test reads or new GT."""
import csv
import json
import hashlib
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).parent/'_sonar_audit_deps'))
from PIL import Image,ImageDraw,ImageFont
import cv2
import numpy as np
OUT=ROOT/'DataSet/paired_weak_scene_coverage_audit'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dump(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    OUT.mkdir(exist_ok=False)
    current=list(csv.DictReader((ROOT/'DataSet/scene_stratified_mortar_recovered_candidate/recordings.csv').open(encoding='utf-8-sig')))
    inventory=read(ROOT/'DataSet/recording_expansion_94_audit/inventory.json')
    candidates=read(ROOT/'DataSet/paired_more_recordings_review_verified/manifest.json')
    proposed=read(ROOT/'DataSet/camera_more_recordings_candidate/recordings.json')
    extras={r['recording']:r for r in proposed}
    frozen={r['recording']:r for r in current}
    rows=[]
    specifications=[
      ('mortar_flyby','2023-09-21_105856',47.15,.59,['2023-09-21_110229','2023-09-21_110411'],'partial_tilt_mismatch_and_unreviewed_echo', 'New candidates tilt -90 vs val -60; 110411 matches Max/5dB; 110229 Min/15dB. Neither has accepted new sonar GT.'),
      ('mortar_L_to_R','2023-09-21_101416',89.05,9.36,['2023-09-21_100927','2023-09-21_101131'],'nominal_pose_match_pairing_blocked','z750/tilt-22/roll0 matches; both Min/15dB vs val Max/5dB. Resolve historical pairing evidence before admission.'),
      ('grenade_flyby','2023-09-21_125048',68.85,51.84,[],'no_current_extra_paired_source','No new available extra recording in this scene. 122115 has no matched camera clip; 125236 is original test and stays closed.'),
      ('grenade_L_to_R','2023-09-21_123841',100.,45.66,['2023-09-21_124241','2023-09-21_124440'],'partial_roll_mismatch_needs_both_annotations','Both z250/tilt-42 match, roll90 vs val roll0; 124241 Max/0dB matches acquisition note. No original camera labels.'),
      ('grenade_L_to_R','2023-09-21_124039',95.32,40.68,['2023-09-21_124241','2023-09-21_124440'],'partial_roll_mismatch_needs_both_annotations','Same as 123841. Existing train123500 already nominal z250/tilt-42/roll0; label-boundary consistency and localization controls are also needed.')]
    for scene,rec,cam,son,refs,status,note in specifications:
        r=frozen[rec]
        rows.append(dict(weak_scene=scene,val_recording=rec,camera_val_mAP=cam,sonar_val_mAP=son,val_condition={k:r[k] for k in ['z','tilt','roll','notes','settings']},candidate_recordings=refs,candidate_counts={c:sum(x['recording']==c for x in candidates) for c in refs},status=status,interpretation=note,candidates=[next(x for x in inventory if x['recording']==c) for c in refs]))
    dump(OUT/'coverage.json',rows)
    dump(OUT/'summary.json',dict(actionable_candidates=397,mortar_flyby_candidates=200,bomb_candidates=197,accepted_new_pairs=0,original_test_content_read=False,model_inference=False,training=False,metadata_not_physical_pose_certification=True))
    # Full-height echo inspection for 2 candidates and matched train/val references.
    manifest=read(ROOT/'DataSet/scene_stratified_mortar_recovered_candidate/manifest.json')
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16)
    visuals=[]
    for rec in ['2023-09-21_110049','2023-09-21_105856','2023-09-21_110229','2023-09-21_110411']:
        rr=[r for r in candidates if r['recording']==rec]
        is_new=bool(rr)
        if not rr:rr=[r for r in manifest if r['recording']==rec]
        rr=sorted(rr,key=lambda r:int(r.get('frame',r.get('aris_frame',r['sample'].rsplit('_',1)[1]))))
        samples=[rr[i] for i in [0,len(rr)//2,len(rr)-1]]
        canvas=Image.new('RGB',(1200,760),'#edf1f6');draw=ImageDraw.Draw(canvas)
        draw.text((6,3),rec+' | fixed first/middle/last | '+('candidate; NO accepted sonar box' if is_new else 'existing train/val labels'),font=font,fill='black')
        for j,r in enumerate(samples):
            if is_new:
                cp=Path(r['camera_source']);sp=Path(r['sonar_source']);cb=r['camera_boxes_xyxy'][0];sb=None
            else:
                base=ROOT/'DataSet/scene_stratified_mortar_recovered_candidate';cp=base/r['camera_image'];sp=base/r['sonar_image'];cb=r['camera_boxes_xyxy'][0];sb=r['sonar_bbox_xyxy']
            ci=Image.open(cp).convert('RGB');ImageDraw.Draw(ci).rectangle(cb,outline='#00ff40',width=2)
            x=j*400;canvas.paste(ci.resize((396,223)),(x,45));draw.text((x+3,25),r['sample'].rsplit('_',1)[-1],font=font,fill='black')
            a=cv2.imdecode(np.frombuffer(sp.read_bytes(),np.uint8),cv2.IMREAD_UNCHANGED)
            assert a.ndim==2
            for k,gain in enumerate([1.,2.5]):
                im=Image.fromarray(np.clip(a.astype(float)*gain,0,255).astype(np.uint8)).convert('RGB')
                if sb:ImageDraw.Draw(im).rectangle(sb,outline='#00ff40',width=2)
                im=im.resize((190,441));canvas.paste(im,(x+k*200,296));draw.text((x+k*200+3,273),f'display gain{gain}',font=font,fill='black')
            visuals.append(dict(recording=rec,sample=r['sample'],camera_sha256=sha(cp),sonar_sha256=sha(sp),source_wh=[a.shape[1],a.shape[0]],new_pair_accepted=False if is_new else None))
        canvas.save(OUT/(rec+'.jpg'),quality=95)
    dump(OUT/'fixed-visual-inputs.json',visuals)
    print(json.dumps(dict(weak_recordings=len(rows),fixed_visuals=len(visuals),accepted_new_pairs=0)))
if __name__=='__main__':main()
