"""Independently verify every exported paired image, box, identity and format."""
import collections
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
from PIL import Image
OUT=ROOT/'DataSet/paired_visible_reviewed/export'
CAM=ROOT/'DataSet/camera_temporal_all'
def read(p):return json.loads(p.read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    rows=read(OUT/'manifest.json');temporal=read(CAM/'manifest-resolved.json')
    source={r['sample']:r for r in temporal['items']};allowed=set(temporal['identity']['recordings'])
    ids=set();sd_ids=set();pixels={'camera':collections.defaultdict(list),'sonar':collections.defaultdict(list)}
    cat=['100lbs_aircraft_bomb','mortar_shell','incindiary_grenade'];checks=0
    cocos={m:read(OUT/f'{m}/coco_all_reviewed.json') for m in pixels}
    for modal,coco in cocos.items():
        assert len(coco['images'])==len(rows)
        assert len({x['id'] for x in coco['images']})==len(rows)
    for r in rows:
        sample=r['sample'];assert sample not in ids;ids.add(sample)
        m=source[sample];assert r['recording'] in allowed
        assert m.get('paired_role') in (None,'train','val','val_id')
        assert r['aris_frame']==m['aris_frame'] and r['sd_index']==m['sd_index'] and r['sd_pts']==m['sd_pts']
        identity=(r['recording'],r['sd_index']);assert identity not in sd_ids;sd_ids.add(identity)
        assert r['review']['decision']=='accepted' and r['review']['camera_box_reviewed']
        sheet=ROOT/'DataSet'/r['review']['review_root']/r['review']['sheet']
        assert sha(sheet)==r['review']['sheet_sha256']
        assert sha(Path(r['source']))==r['review']['source_sha256']
        assert (OUT/r['camera_image']).read_bytes()==(CAM/m['reference_sd']).read_bytes()
        assert (OUT/r['camera_original_label']).read_bytes()==(CAM/m['label_copy']).read_bytes()
        assert sha(CAM/m['label_copy'])==m['original_label_sha256_before']
        raw=np.array(Image.open(r['source']));son=np.array(Image.open(OUT/r['sonar_image']))
        assert raw.dtype==son.dtype and np.array_equal(raw,son)
        native=read(CAM/m['label_copy']);native=native if isinstance(native,list) else [native]
        assert r['camera_boxes_xyxy']==[[v[k] for k in ['x_min','y_min','x_max','y_max']] for v in native]
        for modal in pixels:
            p=OUT/r[modal+'_image'];assert sha(p)==r[modal+'_image_sha256']
            im=Image.open(p);w,h=im.size
            pixels[modal][hashlib.sha256(im.tobytes()).hexdigest()].append(sample)
            expected=r['camera_boxes_xyxy'] if modal=='camera' else [r['sonar_bbox_xyxy']]
            vals=[list(map(float,line.split())) for line in (OUT/f'{modal}/labels_yolo/{sample}.txt').read_text().splitlines()]
            assert len(vals)==len(expected)
            coco=cocos[modal];entry=next(x for x in coco['images'] if x['file_name']==r[modal+'_image'])
            assert (entry['width'],entry['height'])==(w,h)
            anns=[x for x in coco['annotations'] if x['image_id']==entry['id']]
            assert len(anns)==len(expected)
            for box,yolo,ann in zip(expected,vals,anns):
                x0,y0,x1,y1=box;assert 0<=x0<x1<=w and 0<=y0<y1<=h
                c,cx,cy,bw,bh=yolo;assert c==cat.index(r['category'])
                restored=[(cx-bw/2)*w,(cy-bh/2)*h,(cx+bw/2)*w,(cy+bh/2)*h]
                assert max(abs(a-b) for a,b in zip(box,restored))<1e-5
                assert ann['bbox']==[x0,y0,x1-x0,y1-y0] and ann['category_id']==c+1
                checks+=1
    duplicates={modal:[v for v in hashes.values() if len(v)>1] for modal,hashes in pixels.items()}
    assert not any(duplicates.values()),duplicates
    selected={r['sample'] for r in rows if r['selected_for_100_per_recording']}
    for modal in pixels:
        coco=read(OUT/f'{modal}/coco_selected.json')
        assert {Path(i['file_name']).stem for i in coco['images']}==selected
        assert {a['image_id'] for a in coco['annotations']}=={i['id'] for i in coco['images']}
    result=dict(status='passed',pairs=len(rows),selected_pairs=len(selected),modality_box_roundtrips=checks,
        unique_camera_frames=len(sd_ids),duplicate_pixel_groups=duplicates,manifest_sha256=sha(OUT/'manifest.json'),
        raw_pixels_exact=True,camera_bytes_exact=True,camera_labels_exact=True,all_sheet_hashes_passed=True,
        quality_claim='Integrity only; visual decisions are recorded separately; no expert GT or precision sync certification')
    (OUT/'verification.json').write_text(json.dumps(result,indent=2),'utf-8')
    print(json.dumps(result))
if __name__=='__main__':main()
