import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / 'DataSet/paired_assistant_truncated_review/export'
OUT = ROOT / 'DataSet/camera_recording_baseline'
CLASSES = ['100lbs_aircraft_bomb', 'incindiary_grenade', 'mortar_shell']

def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--test-only',action='store_true');args=parser.parse_args()
    import cv2
    import numpy as np
    roles = json.loads((ROOT/'DataSet/paired_recording_split/manifest.json').read_text(encoding='utf-8'))
    OUT.mkdir(exist_ok=True)
    report = {}
    previews = []
    roles_to_prepare=[('test',600)] if args.test_only else [('train',1800),('val',600)]
    for role, expected in roles_to_prepare:
        rows = [x for x in roles if x['role']==role and x['membership']=='selected']
        assert len(rows)==expected
        coco = dict(info={}, images=[], annotations=[], categories=[dict(id=i+1,name=n) for i,n in enumerate(CLASSES)])
        ds = []
        pictured = set()
        for i, x in enumerate(sorted(rows,key=lambda a:a['sample']),1):
            path = EXPORT/x['camera_image']
            assert hashlib.sha256(path.read_bytes()).hexdigest()==x['camera_image_sha256']
            img = cv2.imread(str(path)); assert img.shape==(360,640,3)
            label_path = EXPORT/'camera/original_labels'/f"{x['sample']}.json"
            label = json.loads(label_path.read_text())
            assert label['class']==x['category']
            b = [label[k] for k in ['x_min','y_min','x_max','y_max']]
            assert np.isfinite(b).all() and 0<=b[0]<b[2]<=640 and 0<=b[1]<b[3]<=360, (x['sample'],b)
            box = [b[0],b[1],b[2]-b[0],b[3]-b[1]]
            cat = CLASSES.index(x['category'])
            coco['images'].append(dict(id=i,file_name=x['camera_image'],width=640,height=360,sample=x['sample'],recording=x['recording']))
            coco['annotations'].append(dict(id=i,image_id=i,category_id=cat+1,bbox=box,area=box[2]*box[3],iscrowd=0))
            ds.append(dict(sample_id=x['sample'],fp_camera=str(path),fp_sonar=None,coco_camera_image_id=i,boxes_camera=[box],labels_camera=[cat],boxes_sonar=[],labels_sonar=[],deg_level='d0',deg_seed=0,recording=x['recording'],label_sha256=hashlib.sha256(label_path.read_bytes()).hexdigest()))
            if cat not in pictured:
                pictured.add(cat)
                canvas=cv2.copyMakeBorder(img,0,24,0,0,cv2.BORDER_CONSTANT,value=(114,114,114))
                cv2.rectangle(canvas,(int(b[0]),int(b[1])),(int(b[2]),int(b[3])),(0,255,0),2)
                cv2.putText(canvas,role+' '+x['sample'],(4,18),cv2.FONT_HERSHEY_SIMPLEX,.45,(0,0,255),1)
                previews.append(canvas)
        for name,data in [('coco',coco),('dataset',ds)]:
            (OUT/f'{role}-{name}.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        report[role]=dict(images=len(rows),classes=dict(Counter(x['category'] for x in rows)),all_images_decoded=True,all_image_hashes_match=True,boxes_in_native_sd_bounds=True)
    if args.test_only:
        cv2.imwrite(str(OUT/'test-geometry-preview.jpg'),np.hstack(previews))
    else:
        cv2.imwrite(str(OUT/'geometry-preview.jpg'),np.vstack([np.hstack(previews[:3]),np.hstack(previews[3:])]))
    (OUT/('test-verification.json' if args.test_only else 'verification.json')).write_text(json.dumps(dict(passed=True,summary=report,test_content_read=args.test_only,coordinate_scale=1,clip=False),indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__': main()
