import hashlib
import json
from pathlib import Path
import cv2
import numpy as np

root=Path('/root/wzl')
data=root/'dataset/paired_recording_trainval'
files=json.loads((data/'files-sha256.json').read_text())
for rel,expected in files.items():
    p=root/'dataset'/rel
    assert hashlib.sha256(p.read_bytes()).hexdigest()==expected,rel
source=root/'workflow_baselines'
for rel,expected in json.loads((source/'source-sha256.json').read_text()).items():
    assert hashlib.sha256((source/'source'/rel).read_bytes()).hexdigest()==expected,rel
rows=json.loads((data/'trainval-members.json').read_text())
assert len(rows)==2400 and len({r['sample'] for r in rows})==2400
assert len({r['recording'] for r in rows if r['role']=='train'})==18
assert len({r['recording'] for r in rows if r['role']=='val'})==6
assert not ({r['group_id'] for r in rows if r['role']=='train'} & {r['group_id'] for r in rows if r['role']=='val'})
decoded=0
for modality in ['camera','sonar']:
    for role,n in [('train',1800),('val',600)]:
        ds=json.loads((data/f'{modality}-{role}-dataset.json').read_text())
        assert len(ds)==n
        for x in ds:
            img=cv2.imread(x['fp_'+modality]);assert img is not None
            h,w=img.shape[:2];assert (w,h)==(x['width'],x['height'])
            boxes=x['boxes_'+modality]
            for a,b,c,d in boxes: assert 0<=a<a+c<=w and 0<=b<b+d<=h
            decoded+=1
report=dict(passed=True,files_verified=len(files),images_decoded=decoded,train=1800,val=600,test_present=False,source_snapshot_verified=True)
(source/'remote-data-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
