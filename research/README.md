# 研究进展与证据入口

**历史baseline入口：[模型结果汇总](BASELINES.md) · [对应数据集与划分](DATASETS.md) · [指标CSV](baselines.csv)。**

更新日期：2026-11-14。本页用于阶段汇报；详细原始记录和更正继续保留。数据处理、已完成模型结果和最新训练分别列出。

## 已完成的工作

1. 审计CMOLD/CMHD论文与原实现，区分论文事实、原始产物复算和我方选择；[文献核验](related_work/paper-evidence-review.md)。
2. 追查相机SD/FHD时间对应问题，保留原标签与重建血缘；[完整源审计](复现/camera-baseline/annotation-issues/full-source-timing-cause-audit.md)。
3. 扩充配对数据、双端审阅、补标与独立核验，当前5229对、42录音、35保守来源组；[四录音扩充报告](复现/camera-baseline/four-recording-paired-expansion-5229.md)。
4. 完成一版camera-M与sonar-S开发baseline，并按类、录音、场景分析失败；[完整结果](复现/camera-baseline/scene-expanded-baselines-final-results.md)。
5. 针对已知薄弱条件重划分，并在最新train/val启动camera-only YOLOX-M；[划分报告](复现/camera-baseline/weak-scene-coverage-resplit-5229.md)、[启动与迁移](复现/camera-baseline/weak-coverage-camera-m-5090-deployment.md)。

## 当前数据版本

权威版本：`paired_weak_scene_coverage_pan_split`。保守来源组整体分配，不在不同集合之间拆开。

| 集合 | 配对数 | 录音数 | 保守来源组数 |
|---|---:|---:|---:|
| train | 4138 | 33 | 27 |
| val | 573 | 5 | 5 |
| test | 518 | 4 | 3 |
| 总计 | 5229 | 42 | 35 |

八种已登记scene进入train，27种已有scene×z×tilt×roll联合条件覆盖；这不等于覆盖所有设置、视图或物理姿态。floor ellipse和两种bomb flyby无独立留出，test只有三个保守来源组。旧val/test曾用于开发，重新划分不会消除这段历史。新增393对含助手相机标注；7个未决候选没有纳入训练，也不作为负样本。

证据：[协议](DataSet/paired_weak_scene_coverage_pan_split/protocol.json)、[录音表](DataSet/paired_weak_scene_coverage_pan_split/recordings.csv)、[独立核验](DataSet/paired_weak_scene_coverage_pan_split/independent-verification.json)、[完整manifest压缩副本](DataSet/paired_weak_scene_coverage_pan_split/manifest.json.gz)。

## 已完成结果：旧4081对数据版本

两模型均seed0、200epoch、固定epoch200 actual raw，train2472 / val894。指标为pooled COCOeval百分数，各模态使用各自图像和GT。

| 模型 | val mAP@[.5:.95] | val AP50 | val AP75 | val AR@1 |
|---|---:|---:|---:|---:|
| camera-only YOLOX-M | 89.37 | 97.35 | 95.68 | 91.17 |
| sonar-only YOLOX-S | 51.38 | 84.30 | 48.27 | 58.30 |

上述分数不属于最新5229对划分，两个模态的分数差也不代表蒸馏收益。train自评mAP均100%，但flyby和部分录音存在明显val落差。未验证唯一原因。[逐类/逐录音/场景结果](复现/camera-baseline/scene-expanded-baselines-final-results.md)、[原始汇总JSON](runs/scene_baselines_after_pilot_review/results.json)。

旧715对test已按事前方案评价，此后属于已使用测试集：[历史test报告](复现/camera-baseline/scene-baselines-test715-results.md)。新旧test与原研究保留test必须分开，不将其表述为未触碰最终盲测。

## 最新教师训练：尚无本次确认的最终指标

最新camera-only YOLOX-M采用train4138 / val573，COCO-M fresh backbone/neck、随机三类head、seed0、batch8、200epoch/103600次更新、无增广。固定epoch200 actual raw为主结果，每10epoch仅监测val，EMA单列。

最新已保存的远端启动记录来自2026-11-14 18:09，位置为epoch2的200/518；本地尝试已停止，远端从COCO重新开始，两次日志不拼接。本次发布只整理既有材料，没有实时查询远端，也不据启动记录推断当前仍在训练或已经完成。

证据：[预登记](experiment/archive/weak-coverage-camera-m-training-plan.md)、[数据冻结](runs/weak_coverage_camera_m_teacher/dataset-freeze.json)、[部署报告](复现/camera-baseline/weak-coverage-camera-m-5090-deployment.md)、[独立启动核验](DataSet/weak_coverage_camera_m_5090_deployment/startup-verification.json)。

后续先确认最新run实际完成、epoch200权重身份与val结果，再评估教师可用性与后续蒸馏方案。本次发布没有启动实验、改变划分或新增模型评价。

## 更多记录

- [实验结果登记](experiment/results.md) / [测评协议](experiment/evaluation.md)
- [数据演进与标注来源](dataset.md) / [历史计划](experiment/archive/)
- [论文草稿版本说明](paper/README.md) / [完整交接记录](handoff.md)
- [复现输入与运行边界](REPRODUCIBILITY.md) / [本地产物说明（本地产物说明）](ARTIFACTS.md#artifact-b4ed386eb700)

`publication-manifest.json`记录每个导入文件的源hash与发布hash；`publication-link-rewrites.json`记录本地链接在发布时的改写。历史报告正文保留，发布横幅和链接调整可追踪。正文中的绝对路径是历史运行位置，不能据此认为其他电脑可以直接运行。
