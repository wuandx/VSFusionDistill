# 历史模型baseline结果

2026-11-14整理。数值直接读取既有结果JSON，没有重新运行模型或COCOeval。全部指标为百分数，mAP为pooled COCO AP@[.5:.95]，AR@1与AR@100分列。每一行链接到原结果，数据版本见[数据集索引](DATASETS.md)；另提供[CSV](baselines.csv)与[完整精度JSON](baselines.json)。

不同划分、几何、GT与权重身份的结果分别列出，不合成模型排名。val、train自评、已使用test分开；train自评不能代替泛化证据。

早期原代码表沿用历史评测器加载的epoch200 checkpoint，不冒称本次补评的actual raw；后两表采用已经单独核验的epoch200 actual raw。旧目录`val_raw_epoch200`实际可能为EMA，主表只引用`val_actual_raw_epoch200`。

## 早期原代码：同录音val

| 模型 / 条件 | 集合 | 图像数 | mAP | AP50 | AP75 | AR@1 | AR@100 | 原始结果 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| camera YOLOX-S | val | 830 | 90.25 | 98.97 | 95.75 | N/A | 93.17 | [JSON](legacy_code_results/repro_cmold/t_camera_s/eval_val/ap_summary.json) |
| camera YOLOX-S，train/eval stretch（诊断） | val | 830 | 87.44 | 96.03 | 92.88 | N/A | 89.96 | [JSON](legacy_code_results/repro_cmold/t_camera_s_stretch/eval_val/ap_summary.json) |
| camera YOLOX-S，仅评测stretch（诊断） | val | 830 | 27.12 | 72.16 | 16.25 | N/A | 36.69 | [JSON](legacy_code_results/repro_cmold/t_camera_s/eval_val_stretch/ap_summary.json) |

## 3000对recording-level split

| 模型 / 条件 | 集合 | 图像数 | mAP | AP50 | AP75 | AR@1 | AR@100 | 原始结果 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| camera YOLOX-S 640x384 | train | 1800 | 100.00 | 100.00 | 100.00 | 100.00 | 100.00 | [JSON](runs/camera_recording_baseline/train/train_actual_raw_epoch200/metrics.json) |
| camera YOLOX-S 640x384 | val | 600 | 64.58 | 80.41 | 75.67 | 69.40 | 69.43 | [JSON](runs/camera_recording_baseline/train/val_actual_raw_epoch200/metrics.json) |
| camera YOLOX-S 640x384 | test | 600 | 78.65 | 89.27 | 84.69 | 79.37 | 79.48 | [JSON](runs/camera_recording_baseline/train/test_actual_raw_epoch200/metrics.json) |
| camera YOLOX-M 640x384 | val | 600 | 67.37 | 86.85 | 79.51 | 70.25 | 70.25 | [JSON](runs/camera_recording_m/train/val_actual_raw_epoch200/metrics.json) |

## 4081对scene扩充版

| 模型 / 条件 | 集合 | 图像数 | mAP | AP50 | AP75 | AR@1 | AR@100 | 原始结果 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| camera YOLOX-M fixed640 | train | 2472 | 100.00 | 100.00 | 100.00 | 100.00 | 100.00 | [JSON](runs/scene_camera_m_baseline/after_pilot/train/train_actual_raw_epoch200/metrics.json) |
| camera YOLOX-M fixed640 | val | 894 | 89.37 | 97.35 | 95.68 | 91.17 | 91.17 | [JSON](runs/scene_camera_m_baseline/after_pilot/train/val_actual_raw_epoch200/metrics.json) |
| camera YOLOX-M fixed640 | test | 715 | 85.54 | 98.68 | 97.63 | 87.94 | 87.97 | [JSON](runs/scene_camera_m_baseline/after_pilot/train/test_actual_raw_epoch200/metrics.json) |
| sonar YOLOX-S fixed640 | train | 2472 | 100.00 | 100.00 | 100.00 | 100.00 | 100.00 | [JSON](runs/scene_sonar_s_baseline/after_pilot/train/train_actual_raw_epoch200/metrics.json) |
| sonar YOLOX-S fixed640 | val | 894 | 51.38 | 84.30 | 48.27 | 58.30 | 59.06 | [JSON](runs/scene_sonar_s_baseline/after_pilot/train/val_actual_raw_epoch200/metrics.json) |
| sonar YOLOX-S fixed640 | test | 715 | 67.73 | 90.74 | 76.65 | 74.22 | 74.60 | [JSON](runs/scene_sonar_s_baseline/after_pilot/train/test_actual_raw_epoch200/metrics.json) |

## 对应实验材料与尚无最终结果的项目

- 3000对S/M的[逐类AP/AR](复现/camera-baseline/per-class-baseline-results.md)、[S权重更正](runs/camera_recording_baseline/train/evaluation-weight-correction.json)、[M权重更正](runs/camera_recording_m/train/evaluation-weight-correction.json)。S/M预训练来源不同，不能作纯容量因果比较。
- 4081对的[逐类/录音/场景分析](复现/camera-baseline/scene-expanded-baselines-final-results.md)、[已使用715 test报告](复现/camera-baseline/scene-baselines-test715-results.md)。相机与声呐使用各自GT，指标差不能称蒸馏收益。
- 10epoch camera-M pilot是独立诊断，不与200epoch run拼接；见[pilot报告](复现/camera-baseline/camera-m-pilot-distribution.md)。
- 早期workstation camera-S fixed640 / sonar-S在本次发布依据的记录中没有最终actual raw结果，不能补写成完成，见[部署记录](DataSet/workstation_baselines/README.md)。
- 最新5229对camera-M仅有启动与迁移证据，本次未实时确认完成，无该版最终AP可填，见[最新进展](README.md)。
- 更早的E11、R0/R1/R2、多seed及融合历史保留在原代码[实验台账](../doc/experiments.md)与[历史日志](../doc/logs/)。这些记录涉及不同blob/all、val/val_id、平台与任务；本次没有重新核验全部原始产物，不搬入上方统一口径表。

这张表只登记已有模型成绩，不把完美GT/错类合成控制的AP当成训练模型指标。所有test结果均来自已有评价文件，当前整理没有读取原研究test图像或标注、没有新评价或调参。
