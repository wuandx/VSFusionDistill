"""Render fixed train/val scene comparisons from completed pilot predictions."""
import json
from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'runs/scene_camera_m_pilot/train'
OUT = WORK / 'distribution_analysis'


def contact(kind, train_rec, val_rec):
    import cv2
    import numpy as np
    names = {1: 'bomb', 2: 'mortar', 3: 'grenade'}
    strips = []
    for role, recording in [('train', train_rec), ('val', val_rec)]:
        coco = json.loads((ROOT / f'DataSet/scene_expanded_baseline_trainval/camera-{role}-coco.json').read_text())
        gt = {a['image_id']: a for a in coco['annotations']}
        path = OUT / 'train_actual_raw_epoch10/predictions.json' if role == 'train' else WORK / 'monitor_val_actual_raw_epoch010/predictions.json'
        predictions = json.loads(path.read_text())
        images = sorted([i for i in coco['images'] if i['recording'] == recording], key=lambda i: i['sample'])
        panels = []
        for index in [0, len(images) // 2, len(images) - 1]:
            item = images[index]; a = gt[item['id']]
            image = cv2.imread(str(ROOT / 'DataSet/scene_expanded_baseline_trainval' / item['file_name']))
            canvas = cv2.copyMakeBorder(image, 40, 0, 0, 0, cv2.BORDER_CONSTANT, value=(25, 25, 25))
            cv2.putText(canvas, role + ' ' + item['sample'], (5, 16), cv2.FONT_HERSHEY_SIMPLEX, .46, (255, 255, 255), 1)
            cv2.putText(canvas, 'GT green; top-scored prediction orange (>=0.25)', (5, 33), cv2.FONT_HERSHEY_SIMPLEX, .43, (255, 255, 255), 1)
            candidates = [p for p in predictions if p['image_id'] == item['id'] and p['score'] >= .25]
            layers = [(a, (0, 255, 0), 'GT')]
            if candidates:
                top = max(candidates, key=lambda p: p['score']); layers.append((top, (0, 160, 255), f'{top["score"]:.2f}'))
            for p, color, label in layers:
                x, y, w, h = p['bbox']
                cv2.rectangle(canvas, (round(x), round(y) + 40), (round(x + w), round(y + h) + 40), color, 2)
                cv2.putText(canvas, names[p['category_id']] + ' ' + label, (max(0, round(x)), max(52, round(y) + 37)),
                            cv2.FONT_HERSHEY_SIMPLEX, .48, color, 1)
            panels.append(canvas)
        strips.append(np.hstack(panels))
    cv2.imwrite(str(OUT / f'{kind}-flyby-train-val.jpg'), np.vstack(strips))


def main():
    result = json.loads((OUT / 'results.json').read_text())
    contact('grenade', '2023-09-21_124915', '2023-09-21_125048')
    contact('mortar', '2023-09-21_110049', '2023-09-21_105856')
    rows = []
    for role, metrics in [('train', result['train_metrics']), ('val', result['val_metrics']['10'])]:
        for recording, entry in metrics['per_recording'].items():
            rows.append(dict(role=role, recording=recording, images=entry['images'], **entry['metrics']))
    with (OUT / 'recording-comparison.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    def pct(value): return f'{value * 100:.2f}'
    lines = ['# camera-only YOLOX-M 10轮分布诊断', '',
        '2026-11-14。同一epoch10实际raw权重、原2472train/894val及固定评价口径；新增train自评，无新增训练或test访问。', '',
        '## 结论', '',
        '目前支持两种flyby上的跨录音/条件泛化落差，不能概括为所有场景仍失败。普通左右运动及地面ellipse的train/val较接近。10epoch仍有高IoU定位拟合空间，val5→10 mAP上升，不能据此宣布最终收敛或唯一原因。', '',
        '## 总体与类别（百分数）', '',
        '| 分布 | train mAP | val mAP | train AP50 | val AP50 |', '|---|---:|---:|---:|---:|']
    train = result['train_metrics']; val = result['val_metrics']['10']
    pairs = [('总体', train['pooled'], val['pooled'])]
    pairs += [(name, m, val['per_class'][name]) for name, m in train['per_class'].items()]
    for name, a, b in pairs:
        lines.append(f'| {name} | {pct(a["mAP"])} | {pct(b["mAP"])} | {pct(a["AP50"])} | {pct(b["AP50"])} |')
    lines += ['', '## 八种场景（各自场景内pooled COCOeval，百分数）', '',
              '| 场景 | train帧/组 | val帧/组 | train mAP | val5 mAP | val10 mAP | val10 AP50/AP75 |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for scene, a in result['scenes']['train10'].items():
        b = result['scenes']['val10'].get(scene); old = result['scenes']['val5'].get(scene)
        tail = f'{b["images"]}/{b["groups"]} | {pct(a["metrics"]["mAP"])} | {pct(old["metrics"]["mAP"])} | {pct(b["metrics"]["mAP"])} | {pct(b["metrics"]["AP50"])}/{pct(b["metrics"]["AP75"])}' if b else f'0/0 | {pct(a["metrics"]["mAP"])} | N/A | N/A | N/A'
        display_scene = scene.replace('|', '\\|')
        lines.append(f'| {display_scene} | {a["images"]}/{a["groups"]} | {tail} |')
    lines += ['', '以上每场景均一个有GT类别，不是将各场景AP平均成总体AP。train-only两场景无独立val结论。', '',
              '## 逐录音（百分数）', '', '| role | recording | 帧数 | mAP | AP50 | AP75 |', '|---|---|---:|---:|---:|---:|']
    for row in rows:
        lines.append(f'| {row["role"]} | {row["recording"]} | {row["images"]} | {pct(row["mAP"])} | {pct(row["AP50"])} | {pct(row["AP75"])} |')
    lines += ['', '## 两个失败集中点', '',
        '- 燃烧弹flyby：train124915 108帧/一个来源组，val125048 100帧/一个来源组，mAP75.68→15.78。固定score≥.25诊断下，val100帧最高分预测均为bomb；100帧均有任意类别IoU≥.75候选，最高分框IoU中位数0.874，正确类别IoU≥.5候选仅7帧。这支持分类混淆而非找不到目标是该录音的主要失败表现。AP仍使用原score.01，不能把上述阈值统计冒充COCO指标。',
        '- 迫击炮flyby：train110049 16帧/一个来源组，val105856 20帧/一个来源组，mAP78.37→33.97。score≥.25下val20帧最高分均为mortar，20帧均有IoU≥.5候选，仅9帧有IoU≥.75候选，最高分框IoU中位数0.649；AP50为96.04而AP75仅17.32。结合固定图，支持定位/框质量与预测排序是主要表现，未证明全部源于模型或GT单方。',
        '- 原始recordings.csv中燃烧弹flyby train nominal tilt−60、val−90，存在记录条件差异，不能把该值直接当独立验证的物理/RGB姿态。迫击炮train与val nominal z/tilt/roll相同，声呐gain等设置不同；本模型只读相机，不能把声呐电子设置直接当相机错误原因。',
        '- 固定迫击炮train首/中/末3帧均可见较竖直、下边截断的目标，val对照3帧是较横向/斜向的目标，图像外观和可见部分有明显差异。这只描述所看固定帧，不能升级为全序列或精密姿态认证；仍提示同一flyby场景名称不保证视图充分覆盖。',
        '- 三类在其他val录音上均有正确预测，未见把全数据类别顺序全局交换的表现；这不是对每个原始标签的专家复审。', '',
        '## 训练充分性与下一步', '',
        'train总体mAP78.46/AP50约100/AP75约99.67，尚不是高IoU定位完全拟合；val mAP从5轮60.61升至10轮68.31，AP75从79.38升至87.92，仍在变化。飞过分类与定位落差已可见，但短跑不能证明继续训练必定无效，也不能确定无增广、姿态、外观或标注的唯一因果。', '',
        '建议保留当前划分与完整失败录音；下一步若继续，先仅camera-M按原计划延长一个预先固定的训练预算，再用相同train/val口径观察两条flyby，而非立即恢复双模型200轮或按val挑数据。继续训练尚未执行。', '',
        '本次实际查看9val录音首/中/末27张固定图、训练曲线，以及下列两组train/val固定对照；非全量逐帧专家复审。图上显示阈值.25只用于观察。', '',
        '![燃烧弹flyby train/val固定对照](../../runs/scene_camera_m_pilot/train/distribution_analysis/grenade-flyby-train-val.jpg)', '',
        '![迫击炮flyby train/val固定对照](../../runs/scene_camera_m_pilot/train/distribution_analysis/mortar-flyby-train-val.jpg)', '',
        '证据：[完整JSON](../../runs/scene_camera_m_pilot/train/distribution_analysis/results.json)、[场景CSV](../../runs/scene_camera_m_pilot/train/distribution_analysis/scene-comparison.csv)、[逐录音CSV](../../runs/scene_camera_m_pilot/train/distribution_analysis/recording-comparison.csv)、[权重身份](../../runs/scene_camera_m_pilot/train/distribution_analysis/weight-identity.json)。']
    target = ROOT / '复现/camera-baseline/camera-m-pilot-distribution.md'
    target.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(target)


if __name__ == '__main__': main()
