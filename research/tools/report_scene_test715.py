"""Report the one fixed authorized test evaluation without selecting weights or epochs."""
import contextlib
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    from analyze_camera_m_pilot import grouped
    out = ROOT / 'runs/scene_baselines_test715_review'
    out.mkdir(exist_ok=False)
    data = ROOT / 'DataSet/scene_baseline_test715'
    freeze = json.loads((data / 'freeze.json').read_text())
    result = dict(frozen_protocol=freeze, images=715, recordings=7, source_groups=7, models={})
    for side, spec in freeze['models'].items():
        run = Path(spec['run']); folder = run / 'test_actual_raw_epoch200'
        identity = json.loads((folder / 'weight-identity.json').read_text())
        assert identity['test_used_for_model_evaluation'] and identity['authorized_test_images'] == 715
        metric = json.loads((folder / 'metrics.json').read_text())
        val = json.loads((run / 'val_actual_raw_epoch200/metrics.json').read_text())
        with (out / f'{side}-grouped-evaluation.log').open('w') as log, contextlib.redirect_stdout(log):
            scenes, diagnostics = grouped(data / f'{side}-test-coco.json', folder / 'predictions.json')
        result['models'][side] = dict(test=metric, val=val, scenes=scenes, diagnostics=diagnostics, weight_identity=identity)
    (out / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with (out / 'per-scene.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f); writer.writerow(['modality', 'scene', 'images', 'groups', 'mAP', 'AP50', 'AP75'])
        for side, entry in result['models'].items():
            for scene, value in entry['scenes'].items():
                writer.writerow([side, scene, value['images'], value['groups'], *[value['metrics'][k] for k in ['mAP', 'AP50', 'AP75']]])
    pct = lambda v: f'{v * 100:.2f}'
    lines = ['# 冻结epoch200 raw的715对test评价', '',
        '2026-11-14。用户明确授权当前715对test。模型、数据角色与阈值在评价前冻结；camera-M/sonar-S均使用after_pilot epoch200 actual raw，不比较或选择EMA/其他epoch，不训练、不重分、不修框。', '',
        '## 总体（百分数）', '', '| 模型 | val mAP | test mAP | test AP50 | test AP75 | test AR@1 | test AR@10/100 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for side, entry in result['models'].items():
        m = entry['test']['pooled']
        lines.append(f'| {side} | {pct(entry["val"]["pooled"]["mAP"])} | {pct(m["mAP"])} | {pct(m["AP50"])} | {pct(m["AP75"])} | {pct(m["AR1"])} | {pct(m["AR10"])}/{pct(m["AR100"])} |')
    lines += ['', '## 逐类test（百分数）', '', '| 类别 | 帧数 | camera mAP/AP50/AP75 | sonar mAP/AP50/AP75 |', '|---|---:|---:|---:|']
    sizes = {'100lbs_aircraft_bomb': 308, 'mortar_shell': 246, 'incindiary_grenade': 161}
    for name, count in sizes.items():
        values = ['/'.join(pct(result['models'][side]['test']['per_class'][name][k]) for k in ['mAP', 'AP50', 'AP75']) for side in ['camera', 'sonar']]
        lines.append(f'| {name} | {count} | {values[0]} | {values[1]} |')
    lines += ['', '## 逐场景test（各自场景内pooled，百分数）', '', '| 场景 | 帧数/组数 | camera mAP | sonar mAP |', '|---|---:|---:|---:|']
    for scene, value in result['models']['camera']['scenes'].items():
        other = result['models']['sonar']['scenes'][scene]
        lines.append(f'| {scene.replace("|", " / ")} | {value["images"]}/{value["groups"]} | {pct(value["metrics"]["mAP"])} | {pct(other["metrics"]["mAP"])} |')
    lines += ['', '普通bomb flyby、地面bomb flyby、mortar flyby无test，记N/A；本次无法独立检验此前最差的mortar flyby。当前test五场景不能称覆盖全部八场景。', '',
              '## 七条录音（百分数）', '', '| recording | 帧数 | camera mAP | sonar mAP |', '|---|---:|---:|---:|']
    for rec, value in result['models']['camera']['test']['per_recording'].items():
        other = result['models']['sonar']['test']['per_recording'][rec]
        lines.append(f'| {rec} | {value["images"]} | {pct(value["metrics"]["mAP"])} | {pct(other["metrics"]["mAP"])} |')
    lines += ['', '## 协议与边界', '',
        '- 每模型完整715身份推理，各715图/715GT；检查输出身份无重复/遗漏、预测有限且类别在0/1/2。7录音/7来源组与train/val互斥，图像hash跨角色重复0。独立副本1430图全部解码并核对复制hash、坐标和类别。',
        '- 输入与val完全相同：各模态原图/各自GT，keep_ratio fixed640右底pad114、BGR0–255、无增广，score.01/NMS.65/maxDets100。各模型父checkpoint、raw导出和resolved config hash预先冻结并核验。',
        '- 原test候选已有数据建设/开发审阅历史，因此不能称整个研究完全未触碰的外部盲测；本次后明确登记模型评价使用，不能据此调参后仍宣称保持独立。未访问另外的原研究test来源。',
        '- 这是seed0结果，val/test录音与场景组成不同，二者差值不能单独归因于过拟合强弱或数据难度。两个模态输入/GT不同，AP差不是方法增益或蒸馏收益。',
        '- 助手接受可见回波框、尺寸—类别/采集设置关联、正样本筛选分布与缺少纯背景验证的边界保持。没有进行test逐框专家复审，也未因本轮结果改标注。', '',
        '证据：[完整JSON](../../runs/scene_baselines_test715_review/results.json)、[场景CSV](../../runs/scene_baselines_test715_review/per-scene.csv)、[冻结协议](../../DataSet/scene_baseline_test715/freeze.json)、[副本核验](../../DataSet/scene_baseline_test715/verification.json)。原始metrics/predictions/weight-identity分别位于两个after_pilot/train/test_actual_raw_epoch200目录。']
    (ROOT / '复现/camera-baseline/scene-baselines-test715-results.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({side: entry['test']['pooled'] for side, entry in result['models'].items()}))


if __name__ == '__main__': main()
