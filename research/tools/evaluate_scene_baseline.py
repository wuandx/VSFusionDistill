"""Evaluate only train/val using explicitly identified exported raw or EMA weights."""
import os
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from prepare_scene_baselines import sha, dump, COUNTS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--split', choices=['train', 'val'], default='val')
    parser.add_argument('--kind', choices=['raw', 'ema'], required=True)
    args = parser.parse_args()
    run = args.run_dir.resolve()
    meta = json.loads((run / 'status.json').read_text())
    assert meta['status'] == 'completed'
    sys.path.insert(0, meta['source_repo'])
    import torch
    from mmengine.config import Config
    from mmengine.runner import Runner
    import aodet.datasets, aodet.models, aodet.engine
    import camera_baseline_runtime, scene_baseline_runtime
    from aodet.torch_load_compat import trusted_torch_load
    from aodet.cuda_compat import install_nms_cpu_fallback
    cfg = Config.fromfile(str(run / 'resolved_config.py'))
    side = 'camera' if meta['name'] == 'scene_camera_m_baseline' else 'sonar'
    data = Path(cfg.train_dataloader.dataset.ann_file).parent
    assert sha(data / 'files-sha256.json') == meta['dataset_sha256']
    files = json.loads((data / 'files-sha256.json').read_text())
    ann = data / f'{side}-{args.split}-coco.json'
    rows = data / f'{side}-{args.split}-dataset.json'
    assert sha(ann) == files[ann.name] and sha(rows) == files[rows.name]
    target = run / f'{args.split}_actual_{args.kind}_epoch200'
    assert not target.exists(), f'Refusing to overwrite evaluation: {target}'
    cfg.work_dir = str(run / f'{args.split}_{args.kind}_evaluation_runtime')
    runner = Runner.from_cfg(cfg)
    checkpoint = run / f'{args.kind}_epoch_200.pth'
    with trusted_torch_load():
        exported = torch.load(checkpoint, map_location='cpu', weights_only=False)
        identity = exported['workflow_weight_identity']
        assert identity['kind'] == args.kind and identity['epoch'] == 200
        assert identity['verified_against_live_models']
        assert identity['parent_sha256'] == meta['checkpoint_sha256'] == sha(run / 'epoch_200.pth')
        runner.model.load_state_dict(exported['state_dict'], strict=True)
        spec = dict(cfg.train_dataloader)
        spec['sampler'] = dict(type='DefaultSampler', shuffle=False)
        spec['dataset'] = dict(cfg.train_dataloader.dataset)
        spec['dataset']['ann_file'] = str(rows)
        loader = Runner.build_dataloader(spec, seed=0)
        assert len(loader.dataset) == COUNTS[args.split]
        install_nms_cpu_fallback()
        class Adapter:
            def eval(self): runner.model.eval()
            def test_step(self, batch):
                branch = 'camera' if side == 'camera' else 'sonar_uncoupled'
                return {'camera': runner.model.test_step(batch)[branch]}
        metrics = camera_baseline_runtime.evaluate_val(Adapter(), loader, ann, target)
    dump(target / 'weight-identity.json', dict(**identity, export_sha256=sha(checkpoint), split=args.split,
                                             images=COUNTS[args.split], test_content_read=False))
    print(json.dumps(metrics['pooled']))


if __name__ == '__main__':
    main()
