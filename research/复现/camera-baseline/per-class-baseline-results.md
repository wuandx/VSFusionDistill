# 按用户指定表格汇总baseline指标

2026-11-13。用户澄清只采用图片中的指标/表格，不要求新增蒸馏实验。AP为COCO AP@[0.50:0.95]，AR为同IoU范围AR(maxDets=1)，全部为百分数；mAP/mAR为当前600张val的pooled COCO类别平均，不是逐录音平均。权重固定epoch200 actual raw，EMA不混入。这里是单模态baseline，不是CMHD表2的蒸馏学生结果，论文原始数字不填入本地结果。

| 实验 | bomb AP | bomb AR | mortar AP | mortar AR | grenade AP | grenade AR | mAP | mAR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Camera YOLOX-S 640×384 | 63.01 | 64.05 | 82.43 | 84.65 | 48.28 | 59.50 | 64.58 | 69.40 |
| Camera YOLOX-M 640×384 | 68.72 | 69.70 | 82.89 | 85.65 | 50.50 | 55.40 | 67.37 | 70.25 |

类别按来源100lbs_aircraft_bomb/mortar_shell/incindiary_grenade对应排列；论文图片中的具体武器型号/重量不作为当前实物型号认证。其余fixed640 camera S、sonar S结束并核对raw身份后按同口径追加。未使用test，后续test读数须单独标注，不与val拼接。

2026-11-13补充：[M实际raw结果](../../runs/camera_recording_m/train/val_actual_raw_epoch200/metrics.json)与[权重身份](../../runs/camera_recording_m/train/val_actual_raw_epoch200/weight-identity.json)已核验。M相对S pooled mAP增加2.79个百分点，但grenade AR1下降4.10个百分点，不能称所有指标都改善。S/M预训练来源不同，单seed结果不支持纯容量归因。旧M val_raw_epoch200实际EMA（mAP67.27%），保留另列，不混入主表。

[当前S原始结果](../../runs/camera_recording_baseline/train/val_actual_raw_epoch200/metrics.json)。本次只是已有读数汇总，不新增训练或模型选择。

## 相机S的test结果（与上方val分列）

| 模型/集合 | bomb AP | AR | mortar AP | AR | grenade AP | AR | mAP | mAR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Camera YOLOX-S640×384 / test | 58.62 | 59.10 | 78.32 | 79.75 | 99.00 | 99.25 | 78.65 | 79.37 |
