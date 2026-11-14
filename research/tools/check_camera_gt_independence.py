import os
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import copy
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import run_camera_recording_baseline as common
import torch
from mmengine.config import Config
from mmengine.runner import Runner
from aodet.cuda_compat import install_nms_cpu_fallback

def main():
    work=ROOT/'runs/camera_recording_baseline/train'
    cfg=Config.fromfile(str(work/'resolved_config.py'));cfg.work_dir=str(work/'gt_independence_runtime')
    runner=Runner.from_cfg(cfg)
    saved=torch.load(work/'epoch_200.pth',map_location='cpu',weights_only=False)
    raw={k[7:]:v for k,v in saved['ema_state_dict'].items() if k.startswith('module.')}
    runner.model.load_state_dict(raw,strict=True);runner.model.eval();install_nms_cpu_fallback()
    outputs={}
    for split in ['train','val']:
        spec=copy.deepcopy(cfg.train_dataloader);spec.sampler.shuffle=False
        spec.dataset.ann_file=str(ROOT/f'DataSet/camera_recording_baseline/{split}-dataset.json')
        loader=Runner.build_dataloader(spec,seed=0)
        indices=list(range(0,len(loader.dataset),100))
        spec.dataset=loader.dataset.get_subset(indices)
        spec.batch_size=len(indices)
        batch=next(iter(Runner.build_dataloader(spec,seed=0)))
        clean=copy.deepcopy(batch)
        for sample in clean['data_samples_camera']:
            sample.gt_instances=sample.gt_instances[:0]
        with torch.no_grad():a=runner.model.test_step(batch)['camera'];b=runner.model.test_step(clean)['camera']
        for x,y in zip(a,b):
            assert torch.equal(x.pred_instances.labels,y.pred_instances.labels)
            torch.testing.assert_close(x.pred_instances.bboxes,y.pred_instances.bboxes,rtol=0,atol=0)
            torch.testing.assert_close(x.pred_instances.scores,y.pred_instances.scores,rtol=0,atol=0)
        outputs[split]=dict(images=len(a),empty_GT_predictions_identical=True)
    (work/'gt-independence.json').write_text(json.dumps(outputs,indent=2)+'\n');print(outputs)

if __name__=='__main__':main()
