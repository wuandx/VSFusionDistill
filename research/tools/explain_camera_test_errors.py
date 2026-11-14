"""Describe stored camera predictions at fixed thresholds; no inference or tuning."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'runs/scene_baselines_test715_review/camera_explanation'


def main():
    import cv2
    import numpy as np
    result = json.loads((ROOT / 'runs/scene_baselines_test715_review/results.json').read_text())
    diagnostics = result['models']['camera']['diagnostics']
    rows = [r for d in diagnostics.values() for r in d['samples']]
    summary = dict(images=len(rows), score_threshold=.25,
        no_prediction=sum(r['top_category'] is None for r in rows),
        top_wrong_class=sum(r['top_category'] is not None and r['top_category'] != r['gt_category'] for r in rows),
        coverage={str(t): dict(any_class=sum(r['any_class_best_iou'] >= t for r in rows),
                              correct_class=sum(r['correct_class_best_iou'] >= t for r in rows)) for t in [.5, .75, .9, .95]},
        no_new_inference=True, no_training=True)
    summary['per_recording'] = {}
    for rec, entry in diagnostics.items():
        samples = entry['samples']
        summary['per_recording'][rec] = dict(images=len(samples), top_wrong_class=entry['top_wrong_class'],
            correct_class_coverage={str(t): sum(r['correct_class_best_iou'] >= t for r in samples) for t in [.5,.75,.9,.95]})
    OUT.mkdir(exist_ok=False)
    (OUT / 'counts.json').write_text(json.dumps(summary, indent=2) + '\n')
    strips = []
    for role, rec in [('train', '2023-09-21_121124'), ('train', '2023-09-21_122855'), ('test', '2023-09-21_121539')]:
        data = ROOT / ('DataSet/scene_expanded_baseline_trainval' if role == 'train' else 'DataSet/scene_baseline_test715')
        coco = json.loads((data / f'camera-{role}-coco.json').read_text())
        gt = {a['image_id']: a for a in coco['annotations']}
        work = ROOT / 'runs/scene_camera_m_baseline/after_pilot/train'
        preds = json.loads((work / f'{role}_actual_raw_epoch200/predictions.json').read_text())
        images = sorted([i for i in coco['images'] if i['recording'] == rec], key=lambda i: i['sample'])
        panels = []
        for index in [0, len(images)//2, len(images)-1]:
            item = images[index]; image = cv2.imread(str(data / item['file_name']))
            canvas = cv2.copyMakeBorder(image, 42, 0, 0, 0, cv2.BORDER_CONSTANT, value=(25,25,25))
            cv2.putText(canvas, role + ' ' + item['sample'], (5,16), cv2.FONT_HERSHEY_SIMPLEX,.44,(255,255,255),1)
            cv2.putText(canvas, 'GT green; top prediction orange >=.25', (5,33), cv2.FONT_HERSHEY_SIMPLEX,.44,(255,255,255),1)
            candidates = [p for p in preds if p['image_id']==item['id'] and p['score']>=.25]
            layers=[(gt[item['id']],(0,255,0),'GT')]
            if candidates:
                top=max(candidates,key=lambda p:p['score']);layers.append((top,(0,160,255),f'{top["score"]:.2f}'))
            for p,color,label in layers:
                x,y,w,h=p['bbox'];cv2.rectangle(canvas,(round(x),round(y)+42),(round(x+w),round(y+h)+42),color,2)
                name={1:'bomb',2:'mortar',3:'grenade'}[p['category_id']]
                cv2.putText(canvas,name+' '+label,(max(0,round(x)),max(54,round(y)+39)),cv2.FONT_HERSHEY_SIMPLEX,.45,color,1)
            panels.append(canvas)
        strips.append(np.hstack(panels))
    cv2.imwrite(str(OUT / 'grenade-training-test-fixed-examples.jpg'),np.vstack(strips))
    print(json.dumps(summary))


if __name__ == '__main__': main()
