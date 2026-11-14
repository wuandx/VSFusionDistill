"""Functional controls for the new label/evaluator and fail-closed loading contracts."""
import os
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import argparse
import contextlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from prepare_scene_baselines import dump


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--data', type=Path, default=ROOT / 'DataSet/scene_expanded_baseline_trainval')
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo))
    import torch
    from mmengine.structures import InstanceData
    from mmdet.structures import DetDataSample
    from camera_baseline_runtime import evaluate_val
    from scene_baseline_runtime import SceneSingleModalDataset, identified_state
    out = ROOT / 'runs/scene_expanded_baseline_controls'
    out.mkdir(exist_ok=False)
    report = {}
    for side in ['camera', 'sonar']:
        annotation = args.data / f'{side}-val-coco.json'
        coco = json.loads(annotation.read_text())
        image_ids = [i['id'] for i in coco['images']]
        by_image = {a['image_id']: a for a in coco['annotations']}
        for wrong in [False, True]:
            class Predictor:
                def eval(self): pass
                def test_step(self, ids):
                    output = []
                    for image_id in ids:
                        a = by_image[image_id]
                        x, y, w, h = a['bbox']
                        ds = DetDataSample(metainfo={'coco_image_id': image_id})
                        label = a['category_id'] - 1
                        if wrong: label = (label + 1) % 3
                        ds.pred_instances = InstanceData(bboxes=torch.tensor([[x, y, x + w, y + h]]),
                                                        scores=torch.tensor([.99]), labels=torch.tensor([label]))
                        output.append(ds)
                    return {'camera': output}
            name = f'{side}_{"wrong_category" if wrong else "perfect_gt"}'
            with (out / f'{name}.log').open('w') as log, contextlib.redirect_stdout(log):
                result = evaluate_val(Predictor(), [image_ids[i:i + 8] for i in range(0, len(image_ids), 8)],
                                      annotation, out / name)
            assert abs(result['pooled']['mAP'] - (0. if wrong else 1.)) < 1e-6
            report[name] = dict(mAP=result['pooled']['mAP'], images=result['counts']['images'])
    # A missing file must fail at dataset construction rather than silently disappear.
    broken = json.loads((args.data / 'camera-val-dataset.json').read_text())[:1]
    broken[0]['fp_camera'] = 'missing.jpg'
    dump(out / 'missing-image-dataset.json', broken)
    try:
        SceneSingleModalDataset(ann_file=str(out / 'missing-image-dataset.json'), pipeline=[], serialize_data=False)
    except AssertionError:
        report['missing_image_rejected'] = True
    else:
        raise AssertionError('Missing image was silently accepted')
    try:
        identified_state({'state_dict': {}}, 'raw')
    except KeyError:
        report['unidentified_weights_rejected'] = True
    else:
        raise AssertionError('Unidentified weights were silently treated as raw')
    dump(out / 'checks.json', dict(passed=True, checks=report, formal_training=False, test_content_read=False))
    print(json.dumps(report))


if __name__ == '__main__':
    main()
