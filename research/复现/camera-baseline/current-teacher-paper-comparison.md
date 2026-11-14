# 当前相机教师与相关论文baseline并列

2026-11-13。按用户要求核对同模态与同规模边界；不运行新训练或test。

## 相机检测读数

单位%，mAP=AP@[.5:.95]，mAR=AR(maxDets=1)。

| 来源 | 模型/模态 | mAP | AP50 | AP75 | mAR |
|---|---|---:|---:|---:|---:|
| 本地600张val，epoch200 actual raw | YOLOX-S camera | 64.58 | 80.41 | 75.67 | 69.40 |
| 本地600张val，epoch200 actual raw | YOLOX-M camera | 67.37 | 86.85 | 79.51 | 70.25 |
| CMOLD表3，论文评价集身份未披露 | camera teacher，具体规模未确定 | 95.80 | 99.70 | 99.70 | 96.90 |

本地M与CMOLD报告的数值差为mAP28.43、AP50 12.85、AP75 20.19、mAR26.65个百分点。差距较大，但不是统一数据、划分、预处理和权重选择后的能力差值。CMOLD使用约4700对train+validation；本地1800train/600val、冻结recording-level split、SD→640×384 pad。CMOLD表2确认200epoch/batch8/SGD；不能将训练轮数整体写成未知。评测集身份未披露不能升级为采用帧级随机划分。其sonar-only KD对照中的YOLOX-M不是camera teacher规模证据。

## CMHD同规模模型的含义

CMHD明确使用RGB YOLOX-M教师，输入640×640；但表2固定声呐YOLOX-S-Ghost学生，换教师后报告的是学生结果：S教师78.5/81.5、M教师79.6/82.6（mAP/mAR）。这些不是相机S/M本体AP，不能直接与本地64.58/67.37作教师精度差值。此次未找到可直接填入的CMHD独立RGB教师S/M逐类评价表。相同模型规模并不等于同一评价任务。

结论：相对CMOLD已报告相机教师，本地当前数值明显偏低；相对CMHD同规模RGB M，现有公开表格不能确认相机精度差距。应继续用当前val上的错分类/漏检/定位证据定位原因，不能以声呐学生成绩代替相机教师目标，也不能把差距全归于容量、输入尺寸或数据划分。

## 原始证据

- CMOLD本地PDF及表图：[PDF（本地产物说明）](../../ARTIFACTS.md#artifact-b44090068078)、[表3（本地产物说明）](../../ARTIFACTS.md#artifact-ea06e21b6c21)、[表2（本地产物说明）](../../ARTIFACTS.md#artifact-a4edd924ba67)；文本抽取[575–618段（本地产物说明）](../../ARTIFACTS.md#artifact-109cd67ccf39)。这些是PDF/表图证据，不是LaTeX。
- CMHD：[官方HTML](https://www.mdpi.com/1424-8220/26/14/4340)，§2.1/2.2.1/4.1、表2；[本地JATS（本地产物说明）](../../ARTIFACTS.md#artifact-f5ac120ef892)。在线已核对同规模与表2的学生评价含义；不是LaTeX。
- 本地[逐类表](per-class-baseline-results.md)、[M raw](../../runs/camera_recording_m/train/val_actual_raw_epoch200/metrics.json)、[S raw](../../runs/camera_recording_baseline/train/val_actual_raw_epoch200/metrics.json)。
