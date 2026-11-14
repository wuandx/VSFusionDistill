# 冻结epoch200 raw的715对test评价

2026-11-14。用户明确授权当前715对test。模型、数据角色与阈值在评价前冻结；camera-M/sonar-S均使用after_pilot epoch200 actual raw，不比较或选择EMA/其他epoch，不训练、不重分、不修框。

## 总体（百分数）

| 模型 | val mAP | test mAP | test AP50 | test AP75 | test AR@1 | test AR@10/100 |
|---|---:|---:|---:|---:|---:|---:|
| camera | 89.37 | 85.54 | 98.68 | 97.63 | 87.94 | 87.97/87.97 |
| sonar | 51.38 | 67.73 | 90.74 | 76.65 | 74.22 | 74.60/74.60 |

## 逐类test（百分数）

| 类别 | 帧数 | camera mAP/AP50/AP75 | sonar mAP/AP50/AP75 |
|---|---:|---:|---:|
| 100lbs_aircraft_bomb | 308 | 87.34/100.00/98.96 | 80.69/97.65/89.73 |
| mortar_shell | 246 | 92.92/100.00/100.00 | 59.24/89.46/58.27 |
| incindiary_grenade | 161 | 76.34/96.04/93.94 | 63.27/85.12/81.95 |

## 逐场景test（各自场景内pooled，百分数）

| 场景 | 帧数/组数 | camera mAP | sonar mAP |
|---|---:|---:|---:|
| 100lbs_aircraft_bomb / floor / ellipse | 57/1 | 81.11 | 48.70 |
| 100lbs_aircraft_bomb / standard / L_to_R | 251/2 | 88.88 | 87.06 |
| incindiary_grenade / standard / L_to_R | 102/1 | 66.85 | 73.04 |
| incindiary_grenade / standard / flyby | 59/1 | 90.98 | 56.09 |
| mortar_shell / standard / L_to_R | 246/2 | 92.92 | 63.51 |

普通bomb flyby、地面bomb flyby、mortar flyby无test，记N/A；本次无法独立检验此前最差的mortar flyby。当前test五场景不能称覆盖全部八场景。

## 七条录音（百分数）

| recording | 帧数 | camera mAP | sonar mAP |
|---|---:|---:|---:|
| 2023-09-20_175506 | 120 | 94.40 | 88.71 |
| 2023-09-20_181139 | 131 | 82.89 | 85.71 |
| 2023-09-21_103140 | 128 | 90.76 | 82.32 |
| 2023-09-21_104749 | 118 | 96.39 | 35.89 |
| 2023-09-21_121539 | 102 | 66.85 | 73.04 |
| 2023-09-21_124735 | 59 | 90.98 | 56.09 |
| 2023-09-21_155609 | 57 | 81.11 | 48.70 |

## 协议与边界

- 每模型完整715身份推理，各715图/715GT；检查输出身份无重复/遗漏、预测有限且类别在0/1/2。7录音/7来源组与train/val互斥，图像hash跨角色重复0。独立副本1430图全部解码并核对复制hash、坐标和类别。
- 输入与val完全相同：各模态原图/各自GT，keep_ratio fixed640右底pad114、BGR0–255、无增广，score.01/NMS.65/maxDets100。各模型父checkpoint、raw导出和resolved config hash预先冻结并核验。
- 原test候选已有数据建设/开发审阅历史，因此不能称整个研究完全未触碰的外部盲测；本次后明确登记模型评价使用，不能据此调参后仍宣称保持独立。未访问另外的原研究test来源。
- 这是seed0结果，val/test录音与场景组成不同，二者差值不能单独归因于过拟合强弱或数据难度。两个模态输入/GT不同，AP差不是方法增益或蒸馏收益。
- 助手接受可见回波框、尺寸—类别/采集设置关联、正样本筛选分布与缺少纯背景验证的边界保持。没有进行test逐框专家复审，也未因本轮结果改标注。

证据：[完整JSON](../../runs/scene_baselines_test715_review/results.json)、[场景CSV](../../runs/scene_baselines_test715_review/per-scene.csv)、[冻结协议（本地产物说明）](../../ARTIFACTS.md#artifact-aa0e92bbdb7a)、[副本核验](../../DataSet/scene_baseline_test715/verification.json)。原始metrics/predictions/weight-identity分别位于两个after_pilot/train/test_actual_raw_epoch200目录。
