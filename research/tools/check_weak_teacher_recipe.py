from pathlib import Path
import json
from mmengine.config import Config
ROOT=Path(__file__).resolve().parents[1]
new=Config.fromfile(str(ROOT/'runs/weak_coverage_camera_m_teacher/preflight/resolved_config.py'),import_custom_modules=False)
old=Config.fromfile(str(ROOT/'runs/scene_camera_m_baseline/after_pilot/train/resolved_config.py'),import_custom_modules=False)
checks={k:new[k]==old[k] for k in ['model','optim_wrapper','param_scheduler','randomness','train_cfg']}
assert all(checks.values()),checks
assert new.load_from is None and not new.resume
assert all(new[k] is None for k in ['test_dataloader','test_cfg','test_evaluator'])
assert new.train_dataloader.batch_size==8
assert new.train_dataloader.dataset.pipeline==old.train_dataloader.dataset.pipeline
assert new.train_dataloader.sampler==old.train_dataloader.sampler
checks.update(fresh_coco=True,old_optimizer_and_epoch_schedule_identical=True,old_model_and_preprocessing_identical=True,no_test_loader=True,old_sampler_recipe_identical=True)
(ROOT/'runs/weak_coverage_camera_m_teacher/recipe-comparison.json').write_text(json.dumps(checks,indent=2)+'\n')
print(checks)
