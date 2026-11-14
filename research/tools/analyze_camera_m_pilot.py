"""Same epoch10 raw train self-evaluation and scene/recording diagnostics; no test."""
import os
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import argparse
from collections import defaultdict
import contextlib
import csv
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from prepare_scene_baselines import dump, sha


def iou(a, b):
    ax, ay, aw, ah = a; bx, by, bw, bh = b
    intersect = max(0., min(ax + aw, bx + bw) - max(ax, bx)) * max(0., min(ay + ah, by + bh) - max(ay, by))
    return intersect / (aw * ah + bw * bh - intersect) if intersect else 0.


def grouped(annotation, prediction_file):
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval
    gt = COCO(str(annotation)); predictions = json.loads(prediction_file.read_text())
    dt = gt.loadRes(predictions)
    scenes = defaultdict(list)
    for image in gt.dataset['images']: scenes[image['scene_id']].append(image)
    result = {}
    for scene, images in sorted(scenes.items()):
        ids = {i['id'] for i in images}
        cats = sorted({a['category_id'] for a in gt.dataset['annotations'] if a['image_id'] in ids})
        evaluation = COCOeval(gt, dt, 'bbox')
        evaluation.params.imgIds = sorted(ids); evaluation.params.catIds = cats
        evaluation.evaluate(); evaluation.accumulate(); evaluation.summarize()
        result[scene] = dict(images=len(ids), recordings=len({i['recording'] for i in images}),
                             groups=len({i['group_id'] for i in images}), categories=cats,
                             metrics=dict(zip(['mAP', 'AP50', 'AP75', 'APsmall', 'APmedium', 'APlarge',
                                               'AR1', 'AR10', 'AR100', 'ARsmall', 'ARmedium', 'ARlarge'],
                                              map(float, evaluation.stats))))
    by_image = defaultdict(list)
    for prediction in predictions: by_image[prediction['image_id']].append(prediction)
    annotations = {a['image_id']: a for a in gt.dataset['annotations']}
    records = defaultdict(list)
    for image in gt.dataset['images']:
        a = annotations[image['id']]
        candidates = [p for p in by_image[image['id']] if p['score'] >= .25]
        top = max(candidates, key=lambda p: p['score']) if candidates else None
        best = max((iou(a['bbox'], p['bbox']) for p in candidates), default=0.)
        best_correct = max((iou(a['bbox'], p['bbox']) for p in candidates if p['category_id'] == a['category_id']), default=0.)
        records[image['recording']].append(dict(sample=image['sample'], gt_category=a['category_id'],
             top_category=top['category_id'] if top else None, top_score=top['score'] if top else None,
             top_iou=iou(a['bbox'], top['bbox']) if top else 0., any_class_best_iou=best,
             correct_class_best_iou=best_correct, predictions_ge025=len(candidates)))
    diagnostic = {}
    for recording, rows in sorted(records.items()):
        diagnostic[recording] = dict(images=len(rows), no_prediction_ge025=sum(r['top_category'] is None for r in rows),
            top_wrong_class=sum(r['top_category'] is not None and r['top_category'] != r['gt_category'] for r in rows),
            any_class_iou50=sum(r['any_class_best_iou'] >= .5 for r in rows),
            any_class_iou75=sum(r['any_class_best_iou'] >= .75 for r in rows),
            correct_class_iou50=sum(r['correct_class_best_iou'] >= .5 for r in rows),
            correct_class_iou75=sum(r['correct_class_best_iou'] >= .75 for r in rows),
            median_any_class_best_iou=statistics.median(r['any_class_best_iou'] for r in rows),
            median_top_iou=statistics.median(r['top_iou'] for r in rows), samples=rows)
    return result, diagnostic


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--repo', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo.resolve()))
    import torch
    torch.set_num_threads(8)
    from mmengine.config import Config
    from mmengine.runner import Runner
    import aodet.datasets, aodet.models, aodet.engine
    import camera_baseline_runtime, scene_baseline_runtime
    from aodet.torch_load_compat import trusted_torch_load
    from aodet.cuda_compat import install_nms_cpu_fallback
    work = ROOT / 'runs/scene_camera_m_pilot/train'
    out = work / 'distribution_analysis'
    out.mkdir(exist_ok=False)
    data = ROOT / 'DataSet/scene_expanded_baseline_trainval'
    status = json.loads((work / 'status.json').read_text())
    assert status['status'] == 'completed'
    assert sha(data / 'files-sha256.json') == status['dataset_sha256']
    ledger = json.loads((data / 'files-sha256.json').read_text())
    for role in ['train', 'val']:
        for suffix in ['dataset', 'coco']:
            name = f'camera-{role}-{suffix}.json'; assert sha(data / name) == ledger[name]
    for name, digest in status['source_sha256'].items(): assert sha(args.repo / name) == digest
    cfg = Config.fromfile(str(work / 'resolved_config.py'))
    cfg.work_dir = str(out / 'evaluation_runtime')
    runner = Runner.from_cfg(cfg)
    checkpoint = work / 'raw_epoch_10.pth'
    with trusted_torch_load():
        saved = torch.load(checkpoint, map_location='cpu', weights_only=False)
        identity = saved['workflow_weight_identity']
        assert identity['kind'] == 'raw' and identity['epoch'] == 10 and identity['verified_against_live_models']
        assert identity['parent_sha256'] == status['checkpoint_sha256'] == sha(work / 'epoch_10.pth')
        runner.model.load_state_dict(saved['state_dict'], strict=True)
        loader_spec = dict(cfg.train_dataloader)
        loader_spec['sampler'] = dict(type='DefaultSampler', shuffle=False)
        loader = Runner.build_dataloader(loader_spec, seed=0)
        assert len(loader.dataset) == 2472
        install_nms_cpu_fallback()
        train_metrics = camera_baseline_runtime.evaluate_val(runner.model, loader,
                        data / 'camera-train-coco.json', out / 'train_actual_raw_epoch10')
    dump(out / 'weight-identity.json', dict(**identity, checkpoint_sha256=sha(checkpoint), test_content_read=False))
    result = dict(epoch=10, weight='actual_raw', train_metrics=train_metrics, val_metrics={}, scenes={}, diagnostics={})
    with (out / 'grouped-evaluation.log').open('w') as log, contextlib.redirect_stdout(log):
        scene, diagnostic = grouped(data / 'camera-train-coco.json', out / 'train_actual_raw_epoch10/predictions.json')
        result['scenes']['train10'] = scene; result['diagnostics']['train10'] = diagnostic
        for epoch in [5, 10]:
            folder = work / f'monitor_val_actual_raw_epoch{epoch:03d}'
            result['val_metrics'][str(epoch)] = json.loads((folder / 'metrics.json').read_text())
            scene, diagnostic = grouped(data / 'camera-val-coco.json', folder / 'predictions.json')
            result['scenes'][f'val{epoch}'] = scene; result['diagnostics'][f'val{epoch}'] = diagnostic
    dump(out / 'results.json', result)
    with (out / 'scene-comparison.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['scene', 'train_n', 'train_groups', 'train_mAP', 'train_AP50', 'val_n', 'val_groups', 'val5_mAP', 'val10_mAP', 'val10_AP50', 'val10_AP75'])
        for scene, train in result['scenes']['train10'].items():
            val = result['scenes']['val10'].get(scene); old = result['scenes']['val5'].get(scene)
            writer.writerow([scene, train['images'], train['groups'], train['metrics']['mAP'], train['metrics']['AP50'],
                val['images'] if val else 0, val['groups'] if val else 0,
                old['metrics']['mAP'] if old else 'N/A', val['metrics']['mAP'] if val else 'N/A',
                val['metrics']['AP50'] if val else 'N/A', val['metrics']['AP75'] if val else 'N/A'])
    print(json.dumps(dict(train=train_metrics['pooled'], val10=result['val_metrics']['10']['pooled'],
                         scenes=result['scenes']), ensure_ascii=False))


if __name__ == '__main__': main()
