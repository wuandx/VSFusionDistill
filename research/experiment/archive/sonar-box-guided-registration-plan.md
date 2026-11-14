# sonar_box_guided_registration：已审核框约束固定3D注册

2026-11-12，执行前登记。用户明确要求利用 paired_assistant_review 中已有较好框帮助复现3D投影并交付成果。本轮重新授权的是固定注册诊断，不改发布时钟/外参、不逐帧拟合、不训练。

## 目的与唯一改动

在固定官方 gantry、ARIS 姿态、外参、beam 符号、名义模型尺度下，将注册观测改为已接受的声呐可见回波框四边，估计每类一套固定6DOF world_from_model。该观测是助手标签，不是独立专家真值；可见回波框与完整3D外包框的语义差异保留为误差来源。

## 数据与隔离

- 输入：paired_assistant_review/decisions.json（244决策，191 accepted），仅 mortar 103728、grenade 123500 有 accepted；bomb 24 unresolved，不拿待定框拟合。
- 每类 accepted 按ARIS帧排序，前60%中均匀取12帧fit；中间20%只作时间间隔，不计验证；最后20%作 same_recording_check。这是本次求解的数据隔离，不是从未看过的盲测或正式split。
- 另 paired_visible_reviewed/export/manifest.json 中 mortar 102500、grenade 123841/124039 的338 accepted 作 cross_recording_check。只在参数冻结后算标签误差，不用于选解。
- 只访问现有40录音开发manifest allowlist，无原test；所有输入hash固定，旧标注不写回。

## 投影与对照

主框为完整模型表面投影的raw beam/range轴对齐包围框与图像矩形交集（不裁elevation），0 padding。固定±7°裁剪另列诊断，不据check结果择优。投影采用官方实际beam edges/centers，物理azimuth取负转换为raw beam角，range采用每帧声速与采样起点/间隔。

对照：旧PCA注册和上次near-surface固定注册，全部按同一个主框定义重算；不能将主框改变的收益归到新损失。优化单位为平移米、旋转弧度；平移限定官方target原点各轴±0.5m，尺度不拟合。12个固定旋转初值+旧PCA/旧refinement初值，每个有界least_squares最多250次，soft_l1四边残差按参考框宽高归一化；加入非正深度惩罚。选fit目标最小者，全部候选留存。用稀疏表面求解、密集模型重放；稀密边界差过大只报失败，不据check调参。

## 判定与停止

输出每帧新旧IoU、四边误差、中心偏差、投影elevation范围；按录音分别报中位数及IoU≥0.5/0.75比例，均是与助手可见框的一致度，不是AP。改进要求check中位IoU超过两对照；实用候选门槛预定中位IoU≥0.5且≥80%帧IoU≥0.5；这只是本地门槛，不是论文规定。无同步认证时即便通过也不升级为物理正确或正式GT。

输入身份/hash错误立即停；所有初值耗尽即保留最好失败候选，不改变时间/尺度、裁剪阈值或逐帧补偿。若跨录音失败，交付失败叠图、固定参数及误差，不能宣称全局标定成功。交付HTML浏览页、PNG对照、JSON/CSV、报告和可重跑脚本。抽查fit、同录音check及每条跨录音check的首/中/末；抽查不冒充全量专家审核。
