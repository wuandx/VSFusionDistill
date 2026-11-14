"""Strict relocatable data and explicit live-model raw/EMA checkpoint identities."""
import json
from pathlib import Path
import numpy as np
import torch
from mmcv.transforms import BaseTransform
from mmengine.dataset import BaseDataset
from mmengine.hooks import Hook, EMAHook
from mmengine.registry import DATASETS, HOOKS, TRANSFORMS


@DATASETS.register_module()
class SceneSingleModalDataset(BaseDataset):
    def load_data_list(self):
        root = Path(self.ann_file).resolve().parent
        rows = json.loads(Path(self.ann_file).read_text(encoding='utf-8'))
        assert len({r['sample_id'] for r in rows}) == len(rows)
        for row in rows:
            active = [s for s in ['camera', 'sonar'] if row.get(f'fp_{s}')]
            assert len(active) == 1
            side = active[0]
            path = (root / row[f'fp_{side}']).resolve()
            assert path.is_relative_to(root) and path.is_file(), path
            row[f'fp_{side}'] = str(path)
            labels = row[f'labels_{side}']
            assert len(labels) == len(row[f'boxes_{side}']) == 1
            assert all(x in [0, 1, 2] for x in labels)
        return rows


@TRANSFORMS.register_module()
class SceneFixedCanvas(BaseTransform):
    def transform(self, results):
        active = []
        for side in ['camera', 'sonar']:
            key = f'img_{side}'
            arr = results.get(key)
            if arr is None:
                continue
            active.append(side)
            c, h, w = arr.shape
            assert c == 3 and 0 < h <= 640 and 0 < w <= 640
            canvas = np.full((3, 640, 640), 114, dtype=arr.dtype)
            canvas[:, :h, :w] = arr
            results[key] = canvas
        assert len(active) == 1, 'Missing image or unexpected second modality'
        return results


def model_state(mapping, field):
    if field == 'state_dict':
        return dict(mapping[field])
    assert field == 'ema_state_dict'
    return {k[7:]: v for k, v in mapping[field].items() if k.startswith('module.')}


def equal_state(a, b):
    return a.keys() == b.keys() and all(torch.equal(v.detach().cpu(), b[k].detach().cpu()) for k, v in a.items())


@HOOKS.register_module()
class SceneWeightIdentityHook(Hook):
    # Run after EMAHook (49). Verify semantics against the live raw model and live EMA.
    priority = 90

    def before_save_checkpoint(self, runner, checkpoint):
        ema = [h for h in runner.hooks if isinstance(h, EMAHook)]
        assert len(ema) == 1
        live = runner.model.module if hasattr(runner.model, 'module') else runner.model
        raw, averaged = live.state_dict(), ema[0].ema_model.module.state_dict()
        fields = ['state_dict', 'ema_state_dict']
        raw_matches = [f for f in fields if equal_state(model_state(checkpoint, f), raw)]
        ema_matches = [f for f in fields if equal_state(model_state(checkpoint, f), averaged)]
        assert raw_matches and ema_matches, 'Checkpoint weight identity mismatch'
        # Identical initial states are ambiguous; later independent export is still correct.
        raw_field = 'ema_state_dict' if 'ema_state_dict' in raw_matches else raw_matches[0]
        ema_field = next((f for f in ema_matches if f != raw_field), ema_matches[0])
        checkpoint['workflow_weight_identity'] = dict(raw_field=raw_field, ema_field=ema_field,
                                                     verified_against_live_models=True,
                                                     raw_equals_ema=equal_state(raw, averaged))


def identified_state(checkpoint, kind):
    identity = checkpoint['workflow_weight_identity']
    assert identity['verified_against_live_models'] and kind in ['raw', 'ema']
    return model_state(checkpoint, identity[f'{kind}_field'])


@HOOKS.register_module()
class ScenePeriodicValHook(Hook):
    """Monitor live raw weights offline; never select a checkpoint or run a test loader."""
    priority = 80

    def __init__(self, data_root, modality, interval=10):
        self.data_root = Path(data_root)
        self.modality = modality
        self.interval = interval
        self.loader = None

    def after_train_epoch(self, runner):
        epoch = runner.epoch + 1
        if epoch % self.interval:
            return
        from copy import deepcopy
        from mmengine.runner import Runner
        from camera_baseline_runtime import evaluate_val
        from aodet.cuda_compat import install_nms_cpu_fallback
        if self.loader is None:
            spec = deepcopy(runner.cfg.train_dataloader)
            spec['sampler'] = dict(type='DefaultSampler', shuffle=False)
            spec['dataset']['ann_file'] = str(self.data_root / f'{self.modality}-val-dataset.json')
            self.loader = Runner.build_dataloader(spec, seed=0)
            assert len(self.loader.dataset) == 894
        model = runner.model
        was_training = model.training
        branch = 'camera' if self.modality == 'camera' else 'sonar_uncoupled'
        class Adapter:
            def eval(self): model.eval()
            def test_step(self, batch): return {'camera': model.test_step(batch)[branch]}
        install_nms_cpu_fallback()
        try:
            evaluate_val(Adapter(), self.loader, self.data_root / f'{self.modality}-val-coco.json',
                         Path(runner.work_dir) / f'monitor_val_actual_raw_epoch{epoch:03d}')
        finally:
            model.train(was_training)
