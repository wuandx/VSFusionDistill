"""Explicitly authorized test715 evaluation of fixed final raw weights; no training."""
import os
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import argparse
import copy
import csv
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from prepare_scene_baselines import CLASSES, dump, sha
SOURCE = ROOT / 'DataSet/scene_stratified_mortar_recovered_candidate'
TEST = ROOT / 'DataSet/scene_baseline_test715'


def prepare():
    import cv2
    import numpy as np
    TEST.mkdir(exist_ok=False)
    models = {}
    for side, scale in [('camera', 'm'), ('sonar', 's')]:
        run = ROOT / f'runs/scene_{side}_{scale}_baseline/after_pilot/train'
        status = json.loads((run / 'status.json').read_text())
        assert status['status'] == 'completed'
        models[side] = dict(run=str(run), epoch=200, kind='raw',
                            export_sha256=sha(run / 'raw_epoch_200.pth'),
                            parent_sha256=sha(run / 'epoch_200.pth'),
                            config_sha256=sha(run / 'resolved_config.py'))
        assert models[side]['parent_sha256'] == status['checkpoint_sha256']
    freeze = dict(user_authorized_current_test715=True, status='preparing', models=models,
                  evaluation=dict(score=.01, nms_iou=.65, maxDets=100, geometry='keep_ratio fixed640 right/bottom114',
                                  weights='epoch200 actual raw only', no_training=True),
                  input_sha256={name: sha(SOURCE / name) for name in
                                 ['camera/coco_test.json', 'sonar/coco_test.json', 'test-selected.txt',
                                  'recordings.csv', 'user-split-confirmation.json']})
    dump(TEST / 'freeze.json', freeze)
    recs = list(csv.DictReader((SOURCE / 'recordings.csv').open(encoding='utf-8-sig')))
    test_recs = {r['recording']: r for r in recs if r['role'] == 'test'}
    groups = {r['group_id'] for r in test_recs.values()}
    assert len(test_recs) == len(groups) == 7
    assert not groups & {r['group_id'] for r in recs if r['role'] in ['train', 'val']}
    members = set((SOURCE / 'test-selected.txt').read_text().splitlines()); assert len(members) == 715
    trainval = ROOT / 'DataSet/scene_expanded_baseline_trainval'
    old = json.loads((trainval / 'files-sha256.json').read_text())
    forbidden = {side: {digest for name, digest in old.items() if name.startswith(side + '/images/')} for side in ['camera', 'sonar']}
    files, identity = {}, None
    for side in ['camera', 'sonar']:
        coco = json.loads((SOURCE / side / 'coco_test.json').read_text())
        assert len(coco['images']) == len(coco['annotations']) == 715
        assert coco['categories'] == [dict(id=i + 1, name=n) for i, n in enumerate(CLASSES)]
        assert len({i['id'] for i in coco['images']}) == 715
        assert {i['sample'] for i in coco['images']} == members
        annotations = {a['image_id']: a for a in coco['annotations']}; assert len(annotations) == 715
        exported, rows, identities = copy.deepcopy(coco), [], {}
        for image in exported['images']:
            original = SOURCE / image['file_name']
            assert original.is_file()
            decoded = cv2.imread(str(original), cv2.IMREAD_UNCHANGED)
            assert decoded is not None and decoded.dtype == np.uint8
            assert decoded.shape[:2] == (image['height'], image['width'])
            if side == 'camera': assert decoded.shape == (360, 640, 3)
            else:
                assert decoded.ndim == 2 or (decoded.ndim == 3 and np.array_equal(decoded[..., 0], decoded[..., 1]) and np.array_equal(decoded[..., 1], decoded[..., 2]))
            digest = sha(original); assert digest not in forbidden[side], 'Test image duplicates train/val'
            rec = test_recs[image['recording']]; a = annotations[image['id']]
            assert CLASSES[a['category_id'] - 1] == rec['category']
            x, y, w, h = a['bbox']
            assert np.isfinite(a['bbox']).all() and 0 <= x < x + w <= image['width'] and 0 <= y < y + h <= image['height']
            relative = Path(side) / 'images' / (image['sample'] + original.suffix.lower())
            target = TEST / relative; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target); assert sha(target) == digest
            files[relative.as_posix()] = digest
            image.update(file_name=relative.as_posix(), group_id=rec['group_id'], scene_id=rec['scene_id'])
            identities[image['sample']] = dict(recording=image['recording'], group_id=rec['group_id'], scene_id=rec['scene_id'])
            row = dict(sample_id=image['sample'], recording=image['recording'], group_id=rec['group_id'],
                       scene_id=rec['scene_id'], role='test', width=image['width'], height=image['height'],
                       fp_camera=None, fp_sonar=None, boxes_camera=[], boxes_sonar=[], labels_camera=[], labels_sonar=[],
                       deg_level='d0', deg_seed=0)
            row.update({f'fp_{side}': relative.as_posix(), f'coco_{side}_image_id': image['id'],
                        f'boxes_{side}': [a['bbox']], f'labels_{side}': [a['category_id'] - 1]})
            rows.append(row)
        if identity is None: identity = identities
        else: assert identity == identities, 'Paired identities differ'
        for suffix, value in [('coco', exported), ('dataset', rows)]:
            name = f'{side}-test-{suffix}.json'; dump(TEST / name, value); files[name] = sha(TEST / name)
    dump(TEST / 'members.json', identity); files['members.json'] = sha(TEST / 'members.json')
    dump(TEST / 'files-sha256.json', files)
    dump(TEST / 'verification.json', dict(passed=True, images_per_modality=715, recordings=7, groups=7,
         all_images_decoded=True, all_hashes_match=True, bounds_valid=True, train_val_groups_disjoint=True,
         cross_role_image_duplicates=0, other_original_test_sources_read=False))
    freeze['status'] = 'prepared'; dump(TEST / 'freeze.json', freeze)
    print('Prepared authorized paired test715 package')


def evaluate(side):
    import torch
    torch.set_num_threads(8)
    freeze = json.loads((TEST / 'freeze.json').read_text())
    assert freeze['status'] == 'prepared'
    proof = freeze['models'][side]; run = Path(proof['run'])
    status = json.loads((run / 'status.json').read_text())
    sys.path.insert(0, status['source_repo'])
    from mmengine.config import Config
    from mmengine.runner import Runner
    import aodet.datasets, aodet.models, aodet.engine
    import camera_baseline_runtime, scene_baseline_runtime
    from aodet.torch_load_compat import trusted_torch_load
    from aodet.cuda_compat import install_nms_cpu_fallback
    assert sha(run / 'resolved_config.py') == proof['config_sha256']
    assert sha(run / 'raw_epoch_200.pth') == proof['export_sha256']
    assert sha(run / 'epoch_200.pth') == proof['parent_sha256'] == status['checkpoint_sha256']
    for name, digest in status['source_sha256'].items(): assert sha(Path(status['source_repo']) / name) == digest
    ledger = json.loads((TEST / 'files-sha256.json').read_text())
    for name in [f'{side}-test-dataset.json', f'{side}-test-coco.json']: assert sha(TEST / name) == ledger[name]
    output = run / 'test_actual_raw_epoch200'; assert not output.exists()
    cfg = Config.fromfile(str(run / 'resolved_config.py')); cfg.work_dir = str(run / 'test_raw_evaluation_runtime')
    runner = Runner.from_cfg(cfg)
    with trusted_torch_load():
        exported = torch.load(run / 'raw_epoch_200.pth', map_location='cpu', weights_only=False)
        identity = exported['workflow_weight_identity']
        assert identity['kind'] == 'raw' and identity['epoch'] == 200 and identity['verified_against_live_models']
        assert identity['parent_sha256'] == proof['parent_sha256']
        runner.model.load_state_dict(exported['state_dict'], strict=True)
        spec = copy.deepcopy(cfg.train_dataloader)
        spec['sampler'] = dict(type='DefaultSampler', shuffle=False)
        spec['dataset']['ann_file'] = str(TEST / f'{side}-test-dataset.json')
        loader = Runner.build_dataloader(spec, seed=0); assert len(loader.dataset) == 715
        install_nms_cpu_fallback()
        expected_ids = {i['id'] for i in json.loads((TEST / f'{side}-test-coco.json').read_text())['images']}
        seen_ids = set()
        class Adapter:
            def eval(self): runner.model.eval()
            def test_step(self, batch):
                branch = 'camera' if side == 'camera' else 'sonar_uncoupled'
                samples = runner.model.test_step(batch)[branch]
                for sample in samples:
                    image_id = sample.metainfo['coco_image_id']
                    assert image_id in expected_ids and image_id not in seen_ids
                    seen_ids.add(image_id)
                    assert torch.isfinite(sample.pred_instances.bboxes).all()
                    assert torch.isfinite(sample.pred_instances.scores).all()
                    assert ((sample.pred_instances.labels >= 0) & (sample.pred_instances.labels < 3)).all()
                return {'camera': samples}
        metrics = camera_baseline_runtime.evaluate_val(Adapter(), loader, TEST / f'{side}-test-coco.json', output)
        assert seen_ids == expected_ids
    dump(output / 'weight-identity.json', dict(**identity, export_sha256=proof['export_sha256'],
         authorized_test_images=715, test_used_for_model_evaluation=True, freeze_sha256=sha(TEST / 'freeze.json')))
    print(json.dumps(dict(modality=side, pooled=metrics['pooled'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--modality', choices=['camera', 'sonar'])
    args = parser.parse_args(); assert args.prepare != bool(args.modality)
    if args.prepare: prepare()
    else: evaluate(args.modality)
