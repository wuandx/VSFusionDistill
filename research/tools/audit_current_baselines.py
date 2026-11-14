import contextlib
from collections import Counter
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from camera_baseline_runtime import evaluate_val
OUT=ROOT/'复现/camera-baseline/integrity-audit'

def main():
    OUT.mkdir(exist_ok=True)
    data=ROOT/'DataSet/workstation_baselines'
    roles=json.loads((data/'trainval-members.json').read_text())
    group_sets={r:{x['group_id'] for x in roles if x['role']==r} for r in ['train','val']}
    assert not group_sets['train']&group_sets['val']
    results=dict(group_disjoint=True,native_camera_equality=True,geometry_roundtrip_max_error=0.,size_counts={})
    count=0
    for role in ['train','val']:
        local=json.loads((ROOT/f'DataSet/camera_recording_baseline/{role}-coco.json').read_text())
        remote=json.loads((data/f'camera-{role}-coco.json').read_text())
        assert local==remote
        for modality in ['camera','sonar']:
            coco=json.loads((data/f'{modality}-{role}-coco.json').read_text())
            images={x['id']:x for x in coco['images']}
            if modality=='sonar':
                results['size_counts'][role]=dict(Counter(f"category{a['category_id']}:{images[a['image_id']]['width']}x{images[a['image_id']]['height']}" for a in coco['annotations']))
            for a in coco['annotations']:
                im=images[a['image_id']];w,h=im['width'],im['height']
                s=min(640/w,640/h); nw,nh=int(w*s+.5),int(h*s+.5)
                scale=np.array([nw/w,nh/h,nw/w,nh/h])
                xywh=np.asarray(a['bbox']);xyxy=np.r_[xywh[:2],xywh[:2]+xywh[2:]]
                scaled_xywh=xywh*scale
                packed=np.r_[scaled_xywh[:2],scaled_xywh[:2]+scaled_xywh[2:]]
                recovered=packed/scale
                err=float(np.max(np.abs(recovered-xyxy)))
                results['geometry_roundtrip_max_error']=max(results['geometry_roundtrip_max_error'],err)
                assert err<1e-9
                count+=1
    gt=json.loads((data/'camera-val-coco.json').read_text())
    class Model:
        def __init__(self,wrong):self.wrong=wrong
        def eval(self):pass
        def test_step(self,batch):
            arr=[]
            for a in gt['annotations']:
                x,y,w,h=a['bbox'];label=(a['category_id']-1+int(self.wrong))%3
                pred=SimpleNamespace(bboxes=torch.tensor([[x,y,x+w,y+h]]),scores=torch.tensor([.99]),labels=torch.tensor([label]))
                pred.cpu=lambda pred=pred:pred
                arr.append(SimpleNamespace(metainfo={'coco_image_id':a['image_id']},pred_instances=pred))
            return {'camera':arr}
    with (OUT/'metric-controls.log').open('w') as f,contextlib.redirect_stdout(f):
        perfect=evaluate_val(Model(False),[None],data/'camera-val-coco.json',OUT/'perfect')
        wrong=evaluate_val(Model(True),[None],data/'camera-val-coco.json',OUT/'wrong-class')
    assert perfect['pooled']['mAP']>.99999 and wrong['pooled']['mAP']==0
    assert all(x['metrics']['mAP']>.99999 for x in perfect['per_recording'].values())
    results.update(boxes_checked=count,perfect_AP=perfect['pooled']['mAP'],wrong_class_AP=wrong['pooled']['mAP'],test_content_read=False)
    checkpoints=list((ROOT/'runs/camera_recording_baseline/train').glob('epoch_*.pth'))
    checkpoint=min(checkpoints,key=lambda p:int(p.stem.split('_')[-1]))
    ck=torch.load(checkpoint,map_location='cpu',weights_only=False)
    raw={k[7:]:v for k,v in ck['ema_state_dict'].items() if k.startswith('module.')}
    assert set(raw)==set(ck['state_dict'])
    diffs=[k for k,v in raw.items() if k.startswith('camera_') and not torch.equal(v,ck['state_dict'][k])]
    assert diffs
    results['checkpoint_fields']=dict(path=str(checkpoint),matching_keysets=True,camera_raw_ema_different_tensors=len(diffs),ema_updates=int(ck['ema_state_dict']['steps']))
    (OUT/'checks.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
