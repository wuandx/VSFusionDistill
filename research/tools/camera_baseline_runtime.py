"""Workflow-local data adapter, finite-loss guard and val COCO evaluation."""
import json
from pathlib import Path
import torch
from mmengine.dataset import BaseDataset
from mmengine.registry import DATASETS, HOOKS
from mmengine.hooks import Hook

@DATASETS.register_module()
class WorkflowCameraDataset(BaseDataset):
    def load_data_list(self):
        return json.loads(Path(self.ann_file).read_text())

@HOOKS.register_module()
class FiniteCameraLossHook(Hook):
    def after_train_iter(self, runner, batch_idx, data_batch=None, outputs=None):
        for k,v in (outputs or {}).items():
            if isinstance(v,(torch.Tensor,float,int)) and not torch.isfinite(torch.as_tensor(v)).all():
                raise RuntimeError(f'Nonfinite training output: {k}={v}')

def evaluate_val(model, dataloader, gt_path, output):
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval
    output=Path(output); output.mkdir(exist_ok=True)
    model.eval(); predictions=[]
    with torch.no_grad():
        for batch in dataloader:
            for ds in model.test_step(batch)['camera']:
                pred=ds.pred_instances.cpu()
                for b,s,l in zip(pred.bboxes.tolist(),pred.scores.tolist(),pred.labels.tolist()):
                    predictions.append(dict(image_id=ds.metainfo['coco_image_id'],category_id=l+1,bbox=[b[0],b[1],b[2]-b[0],b[3]-b[1]],score=s))
    (output/'predictions.json').write_text(json.dumps(predictions))
    gt=COCO(str(gt_path)); dt=gt.loadRes(predictions) if predictions else COCO()
    if not predictions:
        dt.dataset=dict(images=gt.dataset['images'],categories=gt.dataset['categories'],annotations=[]); dt.createIndex()
    def measure(ids=None,cats=None):
        e=COCOeval(gt,dt,'bbox')
        if ids is not None: e.params.imgIds=ids
        if cats is not None: e.params.catIds=cats
        e.evaluate(); e.accumulate(); e.summarize()
        return dict(zip(['mAP','AP50','AP75','APsmall','APmedium','APlarge','AR1','AR10','AR100','ARsmall','ARmedium','ARlarge'],map(float,e.stats)))
    result=dict(pooled=measure(),per_class={c['name']:measure(cats=[c['id']]) for c in gt.dataset['categories']},per_recording={})
    for rec in sorted({i['recording'] for i in gt.dataset['images']}):
        ids=[i['id'] for i in gt.dataset['images'] if i['recording']==rec]
        cats=sorted({a['category_id'] for a in gt.dataset['annotations'] if a['image_id'] in ids})
        result['per_recording'][rec]=dict(metrics=measure(ids,cats),images=len(ids),gt=sum(a['image_id'] in ids for a in gt.dataset['annotations']),predictions=sum(a['image_id'] in ids for a in predictions))
    result['counts']=dict(images=len(gt.dataset['images']),gt=len(gt.dataset['annotations']),predictions=len(predictions))
    (output/'metrics.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
