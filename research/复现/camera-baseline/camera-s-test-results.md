# camera S冻结test首次评价

2026-11-13，用户明确授权查看当前冻结test，按[事前计划](../../experiment/archive/camera-s-test-evaluation-plan.md)。只评价当前camera S640×384 epoch200 actual raw；和train/val同checkpoint/hash、输入及score.01/NMS.65/max100，未挑epoch/权重/阈值。原研究其余test不读取，未上传test到工作站。

600张、三类各200、6录音/5保守来源组。图片hash、600图全解码、原SD框边界及类名核对通过，未改数据。代表三类test GT概览已实际查看；非全600人工验收。完整预测数649。

| 类别 | AP@[.5:.95] | AR1 |
|---|---:|---:|
| 100lbs_aircraft_bomb | 58.62 | 59.10 |
| mortar_shell | 78.32 | 79.75 |
| incindiary_grenade | 99.00 | 99.25 |
| 整体mAP/mAR | 78.65 | 79.37 |

整体AP50=89.27%、AP75=84.69%；均为百分数、pooled COCO，不以逐录音均值替代。

| 录音 | mAP | AP50 |
|---|---:|---:|
| 2023-09-20_175506 | 97.59 | 100.00 |
| 2023-09-21_101840 | 79.84 | 100.00 |
| 2023-09-21_102500 | 76.81 | 100.00 |
| 2023-09-21_122608 | 99.27 | 100.00 |
| 2023-09-21_122855 | 98.87 | 100.00 |
| 2023-09-21_160551 | 17.23 | 34.73 |

解释：test mAP78.65%高于val64.58%，但不是比val更独立或模型突然提升；是同一模型面对不同录音的读数。test grenade近99%，val grenade48.28%，不能据此概括所有跨录音都会失败。floor bomb160551（原train无floor录音）17.23%，另一bomb17550697.59%，表现与条件强相关；尚不能唯一归因背景、姿态、截断或缺数据。grenade test两条仅一个保守来源组，保留统计依赖限制。当前test已被查看，不据此调参、重选split后继续称未触碰最终评价；历史开发使用边界保持。

[原始指标](../../runs/camera_recording_baseline/train/test_actual_raw_epoch200/metrics.json)、[权重身份](../../runs/camera_recording_baseline/train/test_actual_raw_epoch200/weight-identity.json)、[数据核验（本地产物说明）](../../ARTIFACTS.md#artifact-d01b8639a940)。未运行新训练或蒸馏。
