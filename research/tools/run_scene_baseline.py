"""New-data camera-M / sonar-S only. Requires an explicit mode; never reads test."""
import os
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from prepare_scene_baselines import CLASSES, COUNTS, dump, sha


def configure(args):
    from mmengine.config import Config
    repo, data = args.repo.resolve(), args.data.resolve()
    verification = json.loads((data / 'verification.json').read_text(encoding='utf-8'))
    assert verification['passed'] and verification['classes'] == CLASSES
    recorded = json.loads((data / 'files-sha256.json').read_text(encoding='utf-8'))
    for side in ['camera', 'sonar']:
        for role, count in COUNTS.items():
            for suffix in ['dataset', 'coco']:
                name = f'{side}-{role}-{suffix}.json'
                assert sha(data / name) == recorded[name], f'Changed prepared annotation: {name}'
            assert verification['counts'][f'{side}-{role}']['images'] == count
    assert sha(data / 'trainval-members.json') == recorded['trainval-members.json']
    cfg = Config.fromfile(str(repo / 'configs/repro_cmold/teachers/t_camera_s_yoloxs.py'))
    side = args.modality
    if side == 'camera':
        for key in ['camera_backbone']:
            cfg.model[key].update(deepen_factor=.67, widen_factor=.75)
        cfg.model.camera_neck.update(in_channels=[192, 384, 768], out_channels=192, num_csp_blocks=2)
        cfg.model.camera_head.update(in_channels=192, feat_channels=192)
    else:
        cfg.model.sonar_backbone.init_cfg = cfg.model.camera_backbone.init_cfg.copy()
        cfg.model.sonar_neck.init_cfg = cfg.model.camera_neck.init_cfg.copy()
        cfg.model.uncoupled_sonar_head = cfg.model.camera_head.copy()
        cfg.model.camera_backbone = None
        cfg.model.camera_neck = None
        cfg.model.camera_head = None
        cfg.model.loss_weights = dict(camera=0., fused_sonar=0., uncoupled_sonar=1.)
    ckpt = args.checkpoint.resolve()
    assert ckpt.is_file(), ckpt
    for suffix in ['backbone', 'neck']:
        cfg.model[f'{side}_{suffix}'].init_cfg.checkpoint = str(ckpt)
    cfg.model.data_preprocessor.update(mean=None, std=None, bgr_to_rgb=False, pad_value=114.)
    cfg.model.fused_sonar_head = None
    cfg.model.fusion = dict(type='NoneFusion')
    pipeline = [dict(type='AOLoadPaired'),
                dict(type='AOPairedResize', **{f'{side}_size': (640, 640)}, keep_ratio=True),
                dict(type='AOPackPairedInputs'), dict(type='SceneFixedCanvas')]
    def loader(role, shuffle):
        return dict(batch_size=8, num_workers=args.workers, persistent_workers=args.workers > 0,
                    sampler=dict(type='DefaultSampler', shuffle=shuffle), collate_fn=dict(type='pseudo_collate'),
                    dataset=dict(type='SceneSingleModalDataset', ann_file=str(data / f'{side}-{role}-dataset.json'),
                                 pipeline=pipeline, serialize_data=False))
    cfg.train_dataloader = loader('train', True)
    cfg.val_dataloader = cfg.val_evaluator = cfg.val_cfg = None
    cfg.test_dataloader = cfg.test_evaluator = cfg.test_cfg = None
    cfg.randomness = dict(seed=0, deterministic=False)
    cfg.load_from = None
    cfg.resume = False
    cfg.custom_hooks = list(cfg.custom_hooks) + [dict(type='FiniteCameraLossHook'), dict(type='SceneWeightIdentityHook'),
        dict(type='ScenePeriodicValHook', data_root=str(data), modality=side, interval=10)]
    cfg.default_hooks.checkpoint = dict(type='CheckpointHook', interval=10, max_keep_ckpts=2, save_last=True)
    cfg.custom_imports = dict(imports=['aodet.datasets', 'aodet.models', 'aodet.engine',
                                     'camera_baseline_runtime', 'scene_baseline_runtime'], allow_failed_imports=False)
    cfg.experiment_name = f'scene_{side}_{"m" if side == "camera" else "s"}_baseline'
    cfg.known_deviations = dict(data='4081-pair accepted split: train/val only',
                                classes=CLASSES, geometry='keep_ratio fixed640 right/bottom114',
                                initialization='COCO backbone/neck; random 3-class head',
                                primary_weights='epoch200 raw verified against live model at save')
    cfg.work_dir = str(args.work_dir.resolve())
    return cfg, loader


def stratified_batch(dataset):
    from torch.utils.data import DataLoader, Subset
    from mmengine.dataset import pseudo_collate
    selected, seen = [], set()
    for i in range(len(dataset)):
        row = dataset.get_data_info(i)
        key = (tuple(row.get('labels_camera') or row.get('labels_sonar')), row['width'], row['height'])
        if key not in seen:
            seen.add(key); selected.append(i)
    assert len(selected) <= 8, 'Increase explicit preflight coverage if data changes'
    selected += [i for i in range(len(dataset)) if i not in selected][:8 - len(selected)]
    return next(iter(DataLoader(Subset(dataset, selected), batch_size=8, collate_fn=pseudo_collate))), sorted(seen)


def preflight(runner, loader_spec, args, checkpoint, out):
    import torch
    from mmengine.runner import Runner
    from scene_baseline_runtime import identified_state, equal_state
    from aodet.cuda_compat import install_nms_cpu_fallback
    runner.model.init_weights()
    pretrained = torch.load(checkpoint, map_location='cpu', weights_only=False)['state_dict']
    for suffix in ['backbone', 'neck']:
        state = getattr(runner.model, f'{args.modality}_{suffix}').state_dict()
        assert all(f'{suffix}.{k}' in pretrained and torch.equal(v.cpu(), pretrained[f'{suffix}.{k}'])
                   for k, v in state.items()), f'COCO {suffix} load mismatch'
    runner.call_hook('before_run')
    branch = 'camera' if args.modality == 'camera' else 'sonar_uncoupled'
    covers, geometry_error = {}, 0.
    for role in ['train', 'val']:
        spec = loader_spec(role, False)
        spec['num_workers'] = 0; spec['persistent_workers'] = False
        loader = Runner.build_dataloader(spec, seed=0)
        assert len(loader.dataset) == COUNTS[role]
        batch, covers[role] = stratified_batch(loader.dataset)
        processed = runner.model.data_preprocessor(batch, training=role == 'train')
        assert tuple(processed['inputs'][args.modality].shape) == (8, 3, 640, 640)
        assert processed['inputs']['sonar' if args.modality == 'camera' else 'camera'] is None
        rows = {r['sample_id']: r for r in json.loads((args.data / f'{args.modality}-{role}-dataset.json').read_text())}
        for ds in processed['data_samples'][args.modality]:
            row = rows[ds.metainfo['sample_id']]
            b = torch.tensor(row[f'boxes_{args.modality}'], dtype=torch.float32, device=ds.gt_instances.bboxes.device)
            b[:, 2:] += b[:, :2]
            sx, sy = ds.metainfo['scale_factor']
            restored = ds.gt_instances.bboxes / ds.gt_instances.bboxes.new_tensor([sx, sy, sx, sy])
            geometry_error = max(geometry_error, float((restored - b).abs().max()))
            assert torch.allclose(restored, b, atol=1e-3, rtol=1e-5)
            assert ds.gt_instances.labels.tolist() == row[f'labels_{args.modality}']
            if args.modality == 'camera':
                assert (sx, sy) == (1., 1.)
        if role == 'train':
            runner.model.train()
            loss, _ = runner.model.parse_losses(runner.model(**processed, mode='loss'))
            assert torch.isfinite(loss)
            loss.backward()
            active = getattr(runner.model, f'{args.modality}_backbone')
            assert any(p.grad is not None and torch.isfinite(p.grad).all() for p in active.parameters())
            if args.modality == 'camera':
                assert all(p.grad is None for p in runner.model.sonar_backbone.parameters())
            runner.model.zero_grad(set_to_none=True)
            loss_value = float(loss.detach())
        else:
            runner.model.eval()
            install_nms_cpu_fallback()
            with torch.no_grad():
                predictions = runner.model.test_step(batch)[branch]
            assert len(predictions) == 8
            for ds in predictions:
                assert torch.isfinite(ds.pred_instances.bboxes).all()
                assert torch.isfinite(ds.pred_instances.scores).all()
    # Make raw/EMA distinct in this disposable preflight model, then exercise actual save hooks.
    with torch.no_grad():
        next(getattr(runner.model, f'{args.modality}_backbone').parameters()).add_(.001)
    runner.save_checkpoint(str(out), 'preflight_identity.pth', save_optimizer=False, save_param_scheduler=False)
    saved = torch.load(out / 'preflight_identity.pth', map_location='cpu', weights_only=False)
    assert equal_state(identified_state(saved, 'raw'), runner.model.state_dict())
    assert not equal_state(identified_state(saved, 'raw'), identified_state(saved, 'ema'))
    return dict(initialization_strict_match=True, input_shape=[8, 3, 640, 640], coverage=covers,
                loss=loss_value, geometry_max_abs_error=geometry_error, inference_passed=True,
                checkpoint_roundtrip=saved['workflow_weight_identity'], formal_training=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modality', choices=['camera', 'sonar'], required=True)
    parser.add_argument('--repo', type=Path, required=True, help='Read-only owning source or its snapshot')
    parser.add_argument('--checkpoint', type=Path, required=True, help='M converted COCO or S MMDetection COCO')
    parser.add_argument('--data', type=Path, default=ROOT / 'DataSet/scene_expanded_baseline_trainval')
    parser.add_argument('--work-dir', type=Path)
    parser.add_argument('--workers', type=int, default=2)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--config-only', action='store_true')
    mode.add_argument('--preflight', action='store_true')
    mode.add_argument('--train', action='store_true')
    args = parser.parse_args()
    args.data = args.data.resolve()
    run_name = f'scene_{args.modality}_{"m" if args.modality == "camera" else "s"}_baseline'
    if args.work_dir is None:
        args.work_dir = ROOT / 'runs' / run_name / ('preflight' if args.preflight else 'train' if args.train else 'configuration')
    out = args.work_dir.resolve()
    assert not out.exists(), f'Refusing to overwrite an existing run: {out}'
    sys.path.insert(0, str(args.repo.resolve()))
    import torch
    torch.set_num_threads(8)
    from mmengine.runner import Runner
    import aodet.datasets, aodet.models, aodet.engine
    import camera_baseline_runtime
    import scene_baseline_runtime
    from aodet.torch_load_compat import trusted_torch_load
    cfg, loader = configure(args)
    out.mkdir(parents=True)
    cfg.dump(str(out / 'resolved_config.py'))
    train_images = len(json.loads(Path(cfg.train_dataloader.dataset.ann_file).read_text()))
    batch_size = cfg.train_dataloader.batch_size
    steps = math.ceil(train_images / batch_size)
    epochs = cfg.train_cfg.max_epochs
    meta = dict(name=run_name, status='configured', classes=CLASSES, epochs=epochs, batch=batch_size, seed=0,
                train_images=train_images, val_images=COUNTS['val'], steps_per_epoch=steps, total_updates=steps * epochs,
                initialization_sha256=sha(args.checkpoint), dataset_sha256=sha(args.data / 'files-sha256.json'),
                checkpoint_selection='epoch200 explicit verified raw; EMA separate', test_content_read=False,
                torch=torch.__version__, source_repo=str(args.repo.resolve()),
                implementation_sha256={p: sha(ROOT / 'tools' / p) for p in
                                       ['run_scene_baseline.py', 'scene_baseline_runtime.py', 'prepare_scene_baselines.py',
                                        'evaluate_scene_baseline.py', 'camera_baseline_runtime.py']})
    meta['source_sha256'] = {p.relative_to(args.repo).as_posix(): sha(p)
                            for folder in ['aodet', 'configs'] for p in sorted((args.repo / folder).rglob('*.py'))}
    dump(out / 'status.json', meta)
    if args.config_only:
        print(json.dumps(meta)); return
    assert torch.cuda.is_available(), 'GPU required; no automatic device/batch change'
    meta['gpu'] = torch.cuda.get_device_name(0)
    (out / 'pip-freeze.txt').write_text(subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True))
    runner = Runner.from_cfg(cfg)
    assert len(runner.train_dataloader) == meta['steps_per_epoch'] == 309
    assert len(runner.train_dataloader.dataset) == meta['train_images'] == 2472
    try:
        with trusted_torch_load():
            if args.preflight:
                meta.update(preflight(runner, loader, args, args.checkpoint, out))
                meta['status'] = 'preflight_passed'
            else:
                # Formal training is possible only with a matching completed preflight.
                proof = out.parent / 'preflight/status.json'
                passed = json.loads(proof.read_text())
                assert passed['status'] == 'preflight_passed'
                for k in ['dataset_sha256', 'initialization_sha256', 'implementation_sha256', 'source_sha256']:
                    assert passed[k] == meta[k], f'Preflight changed: {k}'
                meta['status'] = 'training'; dump(out / 'status.json', meta)
                runner.train()
                final = out / 'epoch_200.pth'
                saved = torch.load(final, map_location='cpu', weights_only=False)
                assert saved['meta']['epoch'] == epochs and saved['meta']['iter'] == meta['total_updates']
                for kind in ['raw', 'ema']:
                    state = scene_baseline_runtime.identified_state(saved, kind)
                    target = out / f'{kind}_epoch_200.pth'
                    torch.save(dict(state_dict=state, workflow_weight_identity=dict(kind=kind, epoch=200,
                               parent_sha256=sha(final), verified_against_live_models=True)), target)
                runner.model.load_state_dict(scene_baseline_runtime.identified_state(saved, 'raw'), strict=True)
                from aodet.cuda_compat import install_nms_cpu_fallback
                install_nms_cpu_fallback()
                class Adapter:
                    def eval(self): runner.model.eval()
                    def test_step(self, batch):
                        branch = 'camera' if args.modality == 'camera' else 'sonar_uncoupled'
                        return {'camera': runner.model.test_step(batch)[branch]}
                val = Runner.build_dataloader(loader('val', False), seed=0)
                metrics = camera_baseline_runtime.evaluate_val(Adapter(), val,
                          args.data / f'{args.modality}-val-coco.json', out / 'val_actual_raw_epoch200')
                meta.update(status='completed', val_pooled=metrics['pooled'], checkpoint_sha256=sha(final))
    except BaseException as exc:
        meta.update(status='failed', error=repr(exc))
        raise
    finally:
        dump(out / 'status.json', meta)
    print(json.dumps(meta))


if __name__ == '__main__':
    main()
