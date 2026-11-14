# Camera-only teacher：标准化测评协议

状态：2026-11-10 冻结开发协议。最终 test 只能在本阶段模型选择全部结束后评价；不得反复用于调参或选择 split。

## 研究问题

验证 YOLOX-S camera-only 教师在同一数据版本、原生 camera GT、recording-disjoint 条件下的检测性能，并将同录音诊断与跨录音泛化分开。CMOLD 表 3 的 0.958/0.997 仅作独立参考，不是本地硬验收线。

## 数据角色

训练集与验证集按完整 recording 互斥，test 采用从未进入旧 paired 转换、旧训练、旧测试或旧验证的录音。按类别、几何和采集条件审查覆盖；不为了提升指标删除困难样本，也不以 sonar calibration gate 过滤纯相机样本。

同录音帧级 val 是辅助诊断，不是泛化证据。旧 900 帧 test 降级为 external/dev 对照，不能用于新教师选型。数据版本、split、annotation hash 与排除原因写入 manifest。

## 主指标与分解

相机支路、原生 GT=all、pooled COCOeval，报 AP@[.5:.95]、AP50、AP75、AR@1/10/100。必须附每 recording、每 class 的相同指标、图像/GT/预测数，及 pooled 与逐 recording 汇总的区别。

主终点为 recording-disjoint validation 的 AP@[.5:.95] 与 AP50，同时报告 test 的同一组指标（仅在最终冻结后）。同录音 val 报作诊断，不能用来代替主终点。报告 seed、初始化、final/best 与 EMA 状态、输入尺寸、resize/pad、score/NMS 阈值。

## 对照

保留当前 `t_camera_s` 的同录音结果作为已有诊断，不与新模型直接相减成方法增益。新模型与其必要的几何或增广对照，须使用同一 recording split、数据版本、训练预算和 seed。若要判断几何效应，训练和测试几何需各自保持一致，再单变量改变；若判断泛化，不能同时更改 split、标注与配方。

## 失败分析

固定按 recording 的最低分样例与逐类错误，报漏检、假阳性、类别混淆和 IoU 分布。可视化检查 train/dev 的原生框与图像几何；最终 test 的可视化只在冻结评价后生成。不能根据 test 失败样例修改 split 或调参。

## 输出与验收

每个版本在 `experiment/<版本名>/` 保存 `manifest.json`、resolved config、训练日志、checkpoint 身份、`metrics.json`、逐 recording 表与失败分析。在 `experiment/results.md` 追加，不覆盖。

相机教师进入后续蒸馏前，至少应有：无 recording 泄漏的 train/dev 证明；合理的主验证读数；无整类或整录音无法解释的全面失败；teacher 在蒸馏训练集上的预测可审计。没有跨 recording 证据时只能称“教师候选”，不能称“已验证教师基线”。
