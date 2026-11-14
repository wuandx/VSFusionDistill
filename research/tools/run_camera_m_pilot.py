"""Run only the first 10 epochs of the verified camera-M recipe, then stop."""
import os
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import argparse
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from prepare_scene_baselines import sha, dump


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo.resolve()))
    import torch
    torch.set_num_threads(8)
    from mmengine.runner import Runner
    import aodet.datasets, aodet.models, aodet.engine
    import camera_baseline_runtime, scene_baseline_runtime
    from aodet.torch_load_compat import trusted_torch_load
    from run_scene_baseline import configure
    from render_camera_pilot import render
    out = ROOT / 'runs/scene_camera_m_pilot/train'
    assert not out.exists(), out
    data = ROOT / 'DataSet/scene_expanded_baseline_trainval'
    checkpoint = ROOT / 'assets/checkpoints/yolox_m_coco_backbone_neck.pth'
    proof = json.loads((ROOT / 'runs/scene_camera_m_baseline/preflight/status.json').read_text())
    assert proof['status'] == 'preflight_passed'
    assert sha(checkpoint) == proof['initialization_sha256']
    assert sha(data / 'files-sha256.json') == proof['dataset_sha256']
    for file, digest in proof['implementation_sha256'].items(): assert sha(ROOT / 'tools' / file) == digest, file
    for file, digest in proof['source_sha256'].items(): assert sha(args.repo / file) == digest, file
    config_args = SimpleNamespace(repo=args.repo, data=data, modality='camera', checkpoint=checkpoint,
                                  workers=2, work_dir=out)
    cfg, _ = configure(config_args)
    cfg.train_cfg.max_epochs = 10
    # Explicit scheduler boundaries remain those of the verified 200-epoch recipe.
    assert cfg.param_scheduler[1].T_max == 185 and cfg.param_scheduler[1].end == 185
    for hook in cfg.custom_hooks:
        if hook['type'] == 'ScenePeriodicValHook': hook['interval'] = 5
    cfg.default_hooks.checkpoint.update(interval=5, max_keep_ckpts=2, save_last=True)
    cfg.experiment_name = 'scene_camera_m_pilot'
    cfg.known_deviations['budget'] = '10 epochs of original 200-epoch LR schedule; val/checkpoint every5; diagnostic only'
    out.mkdir(parents=True)
    cfg.dump(str(out / 'resolved_config.py'))
    meta = dict(name='scene_camera_m_pilot', status='configured', epochs=10, batch=8, seed=0,
                train_images=2472, val_images=894, steps_per_epoch=309, total_updates=3090,
                lr_schedule='first10 epochs of original200; warmup5 and T_max185 unchanged',
                initialized_from='COCO M backbone/neck; random three-class head',
                initialization_sha256=sha(checkpoint), dataset_sha256=proof['dataset_sha256'],
                baseline_implementation_sha256=proof['implementation_sha256'], source_sha256=proof['source_sha256'],
                pilot_implementation_sha256={f: sha(ROOT / 'tools' / f) for f in ['run_camera_m_pilot.py', 'render_camera_pilot.py']},
                test_content_read=False, checkpoint_selection='epoch10 actual raw; EMA separate',
                resume_from_interrupted_long_run=False, formal_200_epoch_result=False)
    dump(out / 'status.json', meta)
    (out / 'pip-freeze.txt').write_text(subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True))
    runner = Runner.from_cfg(cfg)
    assert len(runner.train_dataloader) == 309
    try:
        with trusted_torch_load():
            meta['status'] = 'training'; dump(out / 'status.json', meta)
            runner.train()
            final = out / 'epoch_10.pth'
            saved = torch.load(final, map_location='cpu', weights_only=False)
            assert saved['meta']['epoch'] == 10 and saved['meta']['iter'] == 3090
            assert scene_baseline_runtime.equal_state(scene_baseline_runtime.identified_state(saved, 'raw'), runner.model.state_dict())
            parent_hash = sha(final)
            for kind in ['raw', 'ema']:
                torch.save(dict(state_dict=scene_baseline_runtime.identified_state(saved, kind),
                                workflow_weight_identity=dict(kind=kind, epoch=10, parent_sha256=parent_hash,
                                                              verified_against_live_models=True)), out / f'{kind}_epoch_10.pth')
            meta.update(status='training_completed', checkpoint_sha256=parent_hash)
            dump(out / 'status.json', meta)
            meta.update(render(out, data, 10), status='completed')
    except BaseException as exc:
        meta.update(status='failed', error=repr(exc)); raise
    finally:
        dump(out / 'status.json', meta)
    print(json.dumps({k: v for k, v in meta.items() if not k.endswith('sha256')}))


if __name__ == '__main__':
    main()
