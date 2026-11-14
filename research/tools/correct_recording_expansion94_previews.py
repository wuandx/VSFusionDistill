"""Replace the QA basis with the already repaired SD time mapping; preserve bad previews."""
import hashlib
import html
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent/'_sonar_audit_deps'))
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'DataSet/recording_expansion_94_audit'
OUT=BASE/'corrected_sd_review'
CAM=ROOT/'DataSet/camera_temporal_all'
PILOTS=ROOT/'DataSet/expanded_paired_recordings'


def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    OUT.mkdir(exist_ok=False)
    previous=read(BASE/'proposals.json')
    manifest=read(CAM/'manifest-resolved.json'); corrected={r['sample']:r for r in manifest['items']}
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)
    rows=[];summaries=[]
    records=sorted({r['recording'] for r in previous if r['source_label']})
    for rec in records:
        source_rows=[r for r in previous if r['recording']==rec];assert len(source_rows)==12
        folder=OUT/rec;folder.mkdir()
        pilot_path=PILOTS/'pilots'/rec/'pilot.json'
        pilot={r['frame']:r for r in read(pilot_path)['items']} if pilot_path.exists() else {}
        canvas=Image.new('RGB',(1280,690),'#f4f6fa');d=ImageDraw.Draw(canvas)
        d.text((4,3),rec+' | CORRECTED SD mapping + unchanged original label | timing QA only',font=font,fill='black')
        mapped=missing=invalid=0
        for j,old in enumerate(source_rows):
            sample=f'{rec}_{old["native_frame"]:04d}';m=corrected.get(sample)
            path=None;sd_index=None;origin=None
            if m:
                sd_index=m['sd_index'];origin='camera_temporal_all/manifest-resolved.json:reference_sd'
                assert sha(CAM/m['label_copy'])==old['source_label_sha256']==m['original_label_sha256_before']
                if m.get('reference_sd'):path=CAM/m['reference_sd']
            elif old['native_frame'] in pilot:
                m=pilot[old['native_frame']];sd_index=m['sd_index'];origin='expanded_paired_recordings/pilots:published SD mapping'
                path=PILOTS/m['camera_image']
                assert sha(path)==m['camera_sha256'] and m['original_label_sha256']==old['source_label_sha256']
            label=read(old['source_label']);box=[label[k] for k in ['x_min','y_min','x_max','y_max']]
            assert box==old['boxes_xyxy_sd']
            bounds=0<=box[0]<box[2]<=640 and 0<=box[1]<box[3]<=360
            x=(j%4)*320;y=28+(j//4)*220
            if path:
                image=Image.open(path).convert('RGB');assert image.size==(640,360)
                ImageDraw.Draw(image).rectangle(box,outline='#00ff40' if bounds else '#ff3030',width=3)
                mapped+=1;invalid+=not bounds
                image.save(folder/f'{j:02d}.jpg',quality=94)
                canvas.paste(image.resize((320,180)),(x,y+19))
            else:
                missing+=1;d.rectangle((x,y+19,x+319,y+199),fill='#273142')
                d.text((x+8,y+85),'SD reference unavailable; do not substitute FHD',font=font,fill='white')
            d.text((x+3,y),f'{j} frame{old["native_frame"]} SD={sd_index} '+('IN-BOUNDS' if bounds else 'OUT-OF-BOUNDS'),font=font,fill='black')
            rows.append(dict(recording=rec,sample=sample,ordinal=j,sd_index=sd_index,temporal_source=origin,
                             corrected_sd_image=str(path) if path else None,corrected_sd_sha256=sha(path) if path else None,
                             original_label=old['source_label'],original_label_sha256=old['source_label_sha256'],
                             boxes_xyxy_sd=box,bbox_in_bounds=bounds,old_native_preview=old['preview'],
                             old_native_preview_not_valid_for_alignment_verdict=True,
                             status='corrected_sd_pending_visual_review' if path else 'missing_sd_reference',
                             precision_sync_certified=False))
        canvas.save(folder/'overview.jpg',quality=94)
        summaries.append(dict(recording=rec,samples=12,mapped=mapped,missing=missing,out_of_bounds=invalid,
                              sheet=str((folder/'overview.jpg').relative_to(OUT))))
    correction=dict(reason='User identified omitted previously repaired SD/FHD time mapping. Native JPG resized + SD GT was not a valid basis for new alignment rejection.',
        withdrawn_verdict='All image-box temporal-shift judgments based solely on initial native previews are withdrawn pending corrected SD review.',
        previous_preview_assets_preserved=True,labels_unchanged=True,new_boxes=0,training=False,
        corrected_manifest_sha256=sha(CAM/'manifest-resolved.json'),
        mapped=sum(r['mapped'] for r in summaries),missing_sd=sum(r['missing'] for r in summaries),
        source_records=summaries,scope='120 existing-label previews only; 48 unlabelled previews make no box-alignment claim')
    dump(OUT/'manifest.json',rows);dump(OUT/'summary.json',correction);dump(BASE/'correction.json',correction)
    sections=[]
    for r in summaries:sections.append(f'<h2>{r["recording"]}</h2><img style="max-width:100%" src="{r["sheet"]}">')
    (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Corrected SD timing review</title><h1>Corrected SD mapping + unchanged labels</h1><p>Previous native-frame alignment verdicts withdrawn. No new label fitting or training.</p>'+''.join(sections),encoding='utf-8')
    print(json.dumps(correction,ensure_ascii=True))


if __name__=='__main__':main()
