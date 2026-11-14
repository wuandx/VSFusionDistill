"""Summarize completed final raw runs, grouped metrics and fixed val examples."""
import contextlib
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'runs/scene_baselines_after_pilot_review'
DATA = ROOT / 'DataSet/scene_expanded_baseline_trainval'


def examples(side, work):
    import cv2
    import numpy as np
    names = {1: 'bomb', 2: 'mortar', 3: 'grenade'}
    coco = json.loads((DATA / f'{side}-val-coco.json').read_text())
    predictions = json.loads((work / 'val_actual_raw_epoch200/predictions.json').read_text())
    gt = {a['image_id']: a for a in coco['annotations']}
    images = {}
    for image in coco['images']: images.setdefault(image['recording'], []).append(image)
    selected = []
    for recording, group in sorted(images.items()):
        group = sorted(group, key=lambda i: i['sample']); panels = []
        for index in [0, len(group) // 2, len(group) - 1]:
            item = group[index]
            image = cv2.imread(str(DATA / item['file_name']))
            assert image is not None
            h, w = image.shape[:2]
            # Sonar is expanded horizontally for viewing only. Original pixels/metrics remain unchanged.
            tw, th = (640, 360) if side == 'camera' else (384, 480)
            view = cv2.resize(image, (tw, th)); sx, sy = tw / w, th / h
            canvas = cv2.copyMakeBorder(view, 42, 0, 0, 0, cv2.BORDER_CONSTANT, value=(25, 25, 25))
            cv2.putText(canvas, item['sample'], (4, 15), cv2.FONT_HERSHEY_SIMPLEX, .4, (255, 255, 255), 1)
            caption = 'GT green; pred orange >=.25' + ('; display resized' if side == 'sonar' else '')
            cv2.putText(canvas, caption, (4, 32), cv2.FONT_HERSHEY_SIMPLEX, .37, (255, 255, 255), 1)
            candidates = sorted([p for p in predictions if p['image_id'] == item['id'] and p['score'] >= .25], key=lambda p: -p['score'])[:5]
            layers = [(gt[item['id']], (0, 255, 0), 'GT')] + [(p, (0, 160, 255), f'{p["score"]:.2f}') for p in candidates]
            for p, color, tag in layers:
                x, y, bw, bh = p['bbox']
                a, b, c, d = round(x * sx), round(y * sy) + 42, round((x + bw) * sx), round((y + bh) * sy) + 42
                cv2.rectangle(canvas, (a, b), (c, d), color, 2)
                cv2.putText(canvas, names[p['category_id']] + ' ' + tag, (max(0, a), max(55, b - 3)), cv2.FONT_HERSHEY_SIMPLEX, .42, color, 1)
            panels.append(canvas); selected.append(dict(recording=recording, sample=item['sample']))
        cv2.imwrite(str(OUT / f'{side}-{recording}.jpg'), np.hstack(panels))
    return selected


def main():
    from analyze_camera_m_pilot import grouped
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    OUT.mkdir(exist_ok=False)
    result = dict(epoch=200, weights='actual_raw', seed=0, test_content_read=False, runs={})
    records = []
    for side, scale in [('camera', 'm'), ('sonar', 's')]:
        work = ROOT / f'runs/scene_{side}_{scale}_baseline/after_pilot/train'
        status = json.loads((work / 'status.json').read_text())
        assert status['status'] == 'completed'
        val = json.loads((work / 'val_actual_raw_epoch200/metrics.json').read_text())
        train = json.loads((work / 'train_actual_raw_epoch200/metrics.json').read_text())
        entry = dict(status=status, train=train, val=val, scenes={}, diagnostics={}, trend=[])
        with (OUT / f'{side}-grouped-evaluation.log').open('w') as log, contextlib.redirect_stdout(log):
            for role in ['train', 'val']:
                scenes, diagnostics = grouped(DATA / f'{side}-{role}-coco.json', work / f'{role}_actual_raw_epoch200/predictions.json')
                entry['scenes'][role] = scenes; entry['diagnostics'][role] = diagnostics
        for role, metric in [('train', train), ('val', val)]:
            for recording, value in metric['per_recording'].items():
                records.append(dict(modality=side, role=role, recording=recording, images=value['images'], **value['metrics']))
        for file in sorted(work.glob('monitor_val_actual_raw_epoch*/metrics.json')):
            metric = json.loads(file.read_text())
            entry['trend'].append(dict(epoch=int(file.parent.name.rsplit('epoch', 1)[1]), **metric['pooled']))
        entry['fixed_examples'] = examples(side, work)
        result['runs'][side] = entry
    (OUT / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with (OUT / 'per-recording.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0])); writer.writeheader(); writer.writerows(records)
    with (OUT / 'per-scene.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f); writer.writerow(['modality', 'role', 'scene', 'images', 'groups', 'mAP', 'AP50', 'AP75'])
        for side, run in result['runs'].items():
            for role, scenes in run['scenes'].items():
                for scene, value in scenes.items():
                    writer.writerow([side, role, scene, value['images'], value['groups'], *[value['metrics'][k] for k in ['mAP', 'AP50', 'AP75']]])
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for ax, (side, run) in zip(axes, result['runs'].items()):
        for key in ['mAP', 'AP50', 'AP75']:
            ax.plot([r['epoch'] for r in run['trend']], [r[key] * 100 for r in run['trend']], label=key)
        ax.set(title=side + ': raw val, fixed epoch200 primary', xlabel='Epoch', ylabel='AP (%)', ylim=(0, 105))
        ax.grid(alpha=.2); ax.legend()
    fig.tight_layout(); fig.savefig(OUT / 'val-curves.png', dpi=150); plt.close(fig)
    print(json.dumps({side: {'train': r['train']['pooled'], 'val': r['val']['pooled'], 'scenes': r['scenes']}
                      for side, r in result['runs'].items()}, ensure_ascii=False))


if __name__ == '__main__': main()
