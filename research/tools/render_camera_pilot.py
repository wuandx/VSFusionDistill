"""Deterministic val examples and loss/LR plots for the camera-only short pilot."""
import json
from pathlib import Path


def render(work, data, epochs):
    import cv2
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    work, data = Path(work), Path(data)
    out = work / 'review'
    out.mkdir(exist_ok=True)
    coco = json.loads((data / 'camera-val-coco.json').read_text(encoding='utf-8'))
    prediction_file = work / f'monitor_val_actual_raw_epoch{epochs:03d}/predictions.json'
    predictions = json.loads(prediction_file.read_text(encoding='utf-8'))
    gt, predicted, recordings = {}, {}, {}
    for a in coco['annotations']: gt.setdefault(a['image_id'], []).append(a)
    for a in predictions: predicted.setdefault(a['image_id'], []).append(a)
    for item in coco['images']: recordings.setdefault(item['recording'], []).append(item)
    names = {1: 'bomb', 2: 'mortar', 3: 'grenade'}
    selected = []
    for recording, images in sorted(recordings.items()):
        images = sorted(images, key=lambda i: i['sample'])
        indices = sorted({0, len(images) // 2, len(images) - 1})
        panels = []
        for index in indices:
            item = images[index]
            img = cv2.imread(str(data / item['file_name']))
            assert img is not None
            canvas = cv2.copyMakeBorder(img, 38, 0, 0, 0, cv2.BORDER_CONSTANT, value=(30, 30, 30))
            cv2.putText(canvas, item['sample'], (5, 16), cv2.FONT_HERSHEY_SIMPLEX, .43, (255, 255, 255), 1)
            cv2.putText(canvas, 'GT green; prediction orange (score >= 0.25)', (5, 32), cv2.FONT_HERSHEY_SIMPLEX, .43, (255, 255, 255), 1)
            layers = [(a, (0, 255, 0), 'GT') for a in gt[item['id']]]
            layers += [(a, (0, 160, 255), f'{a["score"]:.2f}') for a in
                       sorted(predicted.get(item['id'], []), key=lambda a: -a['score'])[:5] if a['score'] >= .25]
            for a, color, tag in layers:
                x, y, w, h = a['bbox']
                cv2.rectangle(canvas, (round(x), round(y) + 38), (round(x + w), round(y + h) + 38), color, 2)
                cv2.putText(canvas, f'{names[a["category_id"]]} {tag}', (max(0, round(x)), max(48, round(y) + 35)),
                            cv2.FONT_HERSHEY_SIMPLEX, .45, color, 1)
            panels.append(canvas)
            selected.append(dict(recording=recording, sample=item['sample'], image_id=item['id']))
        cv2.imwrite(str(out / f'{recording}.jpg'), np.hstack(panels))
    scalar_rows = []
    for path in work.rglob('scalars.json'):
        scalar_rows.extend(json.loads(line) for line in path.read_text().splitlines() if line.strip())
    scalar_rows = sorted([r for r in scalar_rows if 'loss' in r], key=lambda r: r['iter'])
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for key in ['loss', 'camera/loss_obj', 'camera/loss_bbox', 'camera/loss_cls']:
        axes[0].plot([r['iter'] for r in scalar_rows], [r[key] for r in scalar_rows], label=key)
    axes[0].set(xlabel='Iteration', ylabel='Loss', title='Training losses'); axes[0].legend(fontsize=7)
    axes[1].plot([r['iter'] for r in scalar_rows], [r['lr'] for r in scalar_rows])
    axes[1].set(xlabel='Iteration', ylabel='Learning rate', title='Original 200-epoch LR schedule prefix')
    measured = []
    for path in sorted(work.glob('monitor_val_actual_raw_epoch*/metrics.json')):
        epoch = int(path.parent.name.rsplit('epoch', 1)[1])
        measured.append((epoch, json.loads(path.read_text())))
    for key in ['mAP', 'AP50', 'AP75']:
        axes[2].plot([e for e, _ in measured], [100 * d['pooled'][key] for _, d in measured], marker='o', label=key)
    axes[2].set(xlabel='Epoch', ylabel='AP (%)', title='Raw val metrics'); axes[2].legend()
    fig.tight_layout(); fig.savefig(out / 'training-curves.png', dpi=140); plt.close(fig)
    report = dict(epochs=epochs, fixed_examples=selected, display_score_threshold=.25,
                  evaluation_score_threshold=.01, metrics={str(e): d for e, d in measured}, test_content_read=False)
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# Camera-only YOLOX-M short pilot', '', f'{epochs} epochs; raw weights; fixed COCO initialization; val only.', '',
             '| Epoch | mAP@[.5:.95] | AP50 | AP75 |', '|---|---:|---:|---:|']
    for e, d in measured:
        lines.append(f'| {e} | {d["pooled"]["mAP"]*100:.2f} | {d["pooled"]["AP50"]*100:.2f} | {d["pooled"]["AP75"]*100:.2f} |')
    lines += ['', '![Training curves](training-curves.png)', '', 'Fixed first/middle/last sample from every val recording; no test.']
    for rec in sorted(recordings): lines += ['', f'![{rec}]({rec}.jpg)']
    (out / 'README.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return dict(review_directory=str(out), val_pooled=measured[-1][1]['pooled'], fixed_examples=len(selected))
