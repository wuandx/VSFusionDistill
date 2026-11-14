"""Independent read-only checks of both modalities and their shared identity."""
import collections
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
from PIL import Image
import numpy as np
OUT=ROOT/'DataSet/paired_paper_scale'
def read(p):return json.loads(p.read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    rows=read(OUT/'manifest.json');summary=read(OUT/'summary.json')
    camroot=ROOT/'DataSet/camera_temporal_all';sonroot=ROOT/'DataSet/sonar_visible_annotation/export'
    source={x['sample']:x for x in read(camroot/'manifest-resolved.json')['items']}
    son={x['sample']:x for x in read(sonroot/'manifest.json')}
    assert len(rows)==len({x['sample'] for x in rows})==len(son)==1120
    cs={k:read(OUT/k/'annotations.coco.json') for k in ('camera','sonar')}
    assert {x['id'] for x in cs['camera']['images']}=={x['id'] for x in cs['sonar']['images']}
    index={k:{Path(x['file_name']).stem:x for x in v['images']} for k,v in cs.items()}
    anns={k:collections.defaultdict(list) for k in cs}
    for k,v in cs.items():
        for x in v['annotations']:anns[k][x['image_id']].append(x)
    maxerr=0.;sdkeys=[]
    for r in rows:
        sid=r['sample'];m=source[sid];s=son[sid]
        assert m.get('paired_role') in (None,'train','val','val_id')
        assert r['recording']==m['recording']==s['recording'] and r['aris_frame']==m['aris_frame']==s['frame']
        assert r['category']==m['category']==s['category']
        assert r['sd_index']==m['sd_index'] and r['sd_pts']==m['sd_pts']
        assert r['camera_boxes_xyxy']==[[b[k] for k in ('x_min','y_min','x_max','y_max')] for b in ([read(camroot/m['label_copy'])] if isinstance(read(camroot/m['label_copy']),dict) else read(camroot/m['label_copy']))]
        assert sha(OUT/r['camera_image'])==sha(camroot/m['reference_sd'])==r['camera_image_sha256']
        assert sha(OUT/r['camera_label_original'])==sha(camroot/m['label_copy'])==m['original_label_sha256_before']==r['camera_label_sha256']
        assert sha(OUT/r['sonar_image'])==sha(sonroot/s['export_image'])==r['sonar_image_sha256']
        assert r['sonar_bbox_xyxy']==s['bbox_xyxy']
        assert r['training_split'] is None and not r['training_ready'] and not r['annotation_expert_verified']
        sdkeys.append((r['recording'],r['sd_index']))
        for kind,boxes in [('camera',r['camera_boxes_xyxy']),('sonar',[r['sonar_bbox_xyxy']])]:
            with Image.open(OUT/r[kind+'_image']) as im:
                im.load();w,h=im.size
            if kind=='camera':assert (w,h)==(640,360)
            else:assert [w,h]==r['sonar_size_wh']
            lp=OUT/kind/'labels'/f'{sid}.txt'
            if not r['format_valid_pair']:
                assert sid not in index[kind] and not lp.exists()
                continue
            record=index[kind][sid]
            assert [record['width'],record['height']]==[w,h]
            annotations=anns[kind][record['id']]
            lines=lp.read_text('utf-8').splitlines()
            assert len(lines)==len(boxes)==len(annotations)
            for line,b,ann in zip(lines,boxes,annotations):
                tokens=line.split();cl=int(tokens[0]);cx,cy,bw,bh=map(float,tokens[1:])
                assert 0<=b[0]<b[2]<=w and 0<=b[1]<b[3]<=h
                assert cl+1==ann['category_id'] and cs[kind]['categories'][cl]['name']==r['category']
                assert ann['bbox']==[b[0],b[1],b[2]-b[0],b[3]-b[1]]
                back=np.array([(cx-bw/2)*w,(cy-bh/2)*h,(cx+bw/2)*w,(cy+bh/2)*h])
                err=float(np.max(np.abs(back-b)));maxerr=max(maxerr,err);assert err<1e-6
        with Image.open(OUT/r['preview']) as im:im.verify()
    assert len(set(sdkeys))==len(sdkeys), 'Duplicate camera frame reused for multiple pairs'
    queue=read(OUT/'uniform-review-queue.json');assert len(queue)==len({x['sample'] for x in queue})==4000
    assert set(collections.Counter(x['recording'] for x in queue).values())=={100}
    assert all(x['sonar_bbox_xyxy'] is None and x['status']=='pending_visual_review' for x in queue)
    for p,digest in summary['source_hashes'].items():assert sha(ROOT/p)==digest
    inventory=read(OUT/'source-inventory.json');assert {x['sample'] for x in inventory}==set(source)
    report=dict(status='passed',linked_pairs=len(rows),unique_camera_frames=len(set(sdkeys)),
        source_bytes_and_original_labels_unchanged=True,shared_coco_identity_verified=True,
        coco_yolo_roundtrip_max_error_px=maxerr,uniform_queue_unique_pairs=len(queue),
        original_sonar_manifest_sha256=sha(sonroot/'manifest.json'),
        scope='Numerical, provenance and file verification only; not semantic or synchronization certification')
    (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
