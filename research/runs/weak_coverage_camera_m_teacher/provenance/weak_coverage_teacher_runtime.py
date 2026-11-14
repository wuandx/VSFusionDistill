"""Configurable raw-val monitor for the frozen camera-only teacher run."""
from pathlib import Path
from copy import deepcopy
from mmengine.hooks import Hook
from mmengine.registry import HOOKS


@HOOKS.register_module()
class WeakCoverageTeacherValHook(Hook):
    priority=80

    def __init__(self,data_root,expected_count=573,interval=10):
        self.data_root=Path(data_root);self.expected_count=expected_count;self.interval=interval;self.loader=None

    def after_train_epoch(self,runner):
        epoch=runner.epoch+1
        if epoch%self.interval:return
        from mmengine.runner import Runner
        from camera_baseline_runtime import evaluate_val
        from aodet.cuda_compat import install_nms_cpu_fallback
        if self.loader is None:
            spec=deepcopy(runner.cfg.train_dataloader)
            spec['sampler']=dict(type='DefaultSampler',shuffle=False)
            spec['dataset']['ann_file']=str(self.data_root/'camera-val-dataset.json')
            self.loader=Runner.build_dataloader(spec,seed=0)
            assert len(self.loader.dataset)==self.expected_count
        model=runner.model;was_training=model.training
        class Adapter:
            def eval(self):model.eval()
            def test_step(self,batch):return {'camera':model.test_step(batch)['camera']}
        install_nms_cpu_fallback()
        try:
            evaluate_val(Adapter(),self.loader,self.data_root/'camera-val-coco.json',
                         Path(runner.work_dir)/f'monitor_val_actual_raw_epoch{epoch:03d}')
        finally:model.train(was_training)
