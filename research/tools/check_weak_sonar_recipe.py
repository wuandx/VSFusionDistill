"""Read-only comparison with the prior sonar-S recipe before GPU work."""
from pathlib import Path
from types import SimpleNamespace
import json
import sys
from mmengine.config import Config

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parent/'声呐目标检测/code/VSFusionDistill'
sys.path.insert(0,str(REPO))
from run_weak_coverage_sonar_student import configure,BASE

args=SimpleNamespace(repo=REPO,checkpoint=ROOT/'assets/checkpoints/yolox_s_coco.pth',work_dir=BASE/'train')
new,_=configure(args)
old=Config.fromfile(str(ROOT/'runs/scene_sonar_s_baseline/train/resolved_config.py'),import_custom_modules=False)
def normalize(cfg):
    d=cfg.to_dict()
    for suffix in ['backbone','neck']:d['model']['sonar_'+suffix]['init_cfg']['checkpoint']='COCO-S-SHA4592a793'
    return d
n,o=normalize(new),normalize(old)
checks={k:n[k]==o[k] for k in ['model','optim_wrapper','param_scheduler','randomness','train_cfg']}
checks['pipeline']=new.train_dataloader.dataset.pipeline==old.train_dataloader.dataset.pipeline
checks['sampler']=new.train_dataloader.sampler==old.train_dataloader.sampler
checks['batch']=new.train_dataloader.batch_size==old.train_dataloader.batch_size==8
checks['fresh_coco']=new.load_from is None and not new.resume
checks['no_camera_or_distillation']=all(new.model[k] is None for k in ['camera_backbone','camera_neck','camera_head','fused_sonar_head']) and not new.model.get('distillation') and not new.model.get('cmold')
checks['no_test']=all(new[k] is None for k in ['test_dataloader','test_cfg','test_evaluator'])
assert all(checks.values()),checks
assert new.train_cfg.max_epochs==200
BASE.mkdir(parents=True,exist_ok=True)
result=dict(passed=True,checks=checks,optimizer=new.optim_wrapper.to_dict(),scheduler=[dict(x) for x in new.param_scheduler],test_cfg=new.model.test_cfg.to_dict())
(BASE/'recipe-comparison.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
