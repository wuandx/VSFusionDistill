# UXO声呐目标检测与camera-only teacher基线

**历史baseline入口：[模型结果汇总](research/BASELINES.md) · [对应数据集与划分](research/DATASETS.md) · [指标CSV](research/baselines.csv)。**

本仓库保存VSFusionDistill模型代码，以及基于公开UXO数据的相机—声呐数据整理、基线复现和实验记录。当前阶段先固定数据、标注、recording-level split与测评协议，验证camera-only teacher，再推进相机到声呐的知识蒸馏。

**研究快照：2026-11-14。** 建议老师先读[最新进展与结果](research/README.md)，再按需查看证据。

| 当前工作 | 状态与入口 |
|---|---|
| 数据构建与扩充 | 当前5229对、42条录音、35个保守来源组；[构建与更正记录](research/复现/camera-baseline/four-recording-paired-expansion-5229.md) |
| 当前划分 | train4138 / val573 / test518；[覆盖与限制](research/复现/camera-baseline/weak-scene-coverage-resplit-5229.md) |
| 已完成的开发baseline | 旧4081对划分下camera-M val mAP89.37%、sonar-S val mAP51.38%；[完整结果](research/复现/camera-baseline/scene-expanded-baselines-final-results.md) |
| 最新camera-only YOLOX-M | 最新划分下已启动并迁移至5090；发布依据是18:09启动记录，未实时查询或确认完成；[部署证据](research/复现/camera-baseline/weak-coverage-camera-m-5090-deployment.md) |
| 论文与下一步 | [草稿版本说明](research/paper/README.md)；完成最新教师训练核验后，登记当前划分val结果，再决定后续蒸馏 |

上述旧baseline结果不属于最新5229对划分，不能直接用来证明扩充收益。当前划分受旧val/test诊断启发，属于开发协议，不能称未触碰盲测；新增393对的相机框为助手补标，非官方原标注或专家GT。细节见[测评协议](research/experiment/evaluation.md)。

## 阅读与代码入口

- [研究进展、数据版本与指标](research/README.md)
- [实验登记](research/experiment/results.md) / [测评协议](research/experiment/evaluation.md)
- [数据说明](research/dataset.md) / [最新录音划分表](research/DataSet/paired_weak_scene_coverage_pan_split/recordings.csv)
- [模型代码](aodet/) / [已有配置](configs/) / [研究处理脚本](research/tools/)
- [复现输入与运行边界](research/REPRODUCIBILITY.md) / [数据与本地产物](research/ARTIFACTS.md)
- [早期架构与运行说明](README.legacy.md) / [历史中文说明](README.zh-CN.md)

`research/`是本地workflow的精选发布快照；完整图像、视频、权重和历史浏览页资源保存在本地。代码历史继续保留，历史记录中的结论以较新的明确更正为准。原仓库的早期融合/退化研究说明保留在历史入口中。
