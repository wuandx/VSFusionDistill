# 124915完整下环复审P

2026-11-13。对ARIS143–169的27个未决身份完成原幅值gain1/1.5/2.5逐帧放大检查，再保存P完整下环提案并逐项查看相机—声呐双端页面；**27个接受，124915由81增至108个唯一接受**。不为了精确100将已看通过帧任意标未决；总导出可沿用主任务既定规则选100。

前轮M下边界236截断可能关联的下环，保留为失败。P包含主亮体、其连接的下环和内部暗区，不只是最亮区域。低亮度显示帮助分清下环与更下方分离亮斑；其间存在暗间隔。轴对齐框内不可避免的横向条纹重叠不单独否决，同时框左右只包主目标，没有沿条纹扩至外部支架/背景。143–169相机端完整，末帧近底边但底端可见。

这次修正了前轮过于保守的“条纹重叠即不确定”处理；没有增加物理同步或真实回波归属证据，仍是助手可见回波标注判断，非专家GT。旧81个接受的身份和框、M失败、原始数据与时间对应全部保留。未改共享handoff/results/evaluation/dataset、split或训练。

预先记录目的与准入见[计划第三阶段P](../../experiment/archive/paired-grenade-remaining-plan.md)。27个候选源身份均已存在于DataSet/paired_visible_expansion/candidates.json，无需增加导出身份库存。

- 新审核根：`DataSet/paired_assistant_grenade_complete_ring`，含decisions.json、review-events.jsonl、3组page JSON/JPG。
- 新候选提案：[candidates.json（本地产物说明）](../../ARTIFACTS.md#artifact-4e8cb2fa52e0)，按帧顺序143–169，P原始坐标范围逐项保存；仅为新提案元数据。
- 三亮度原图：`DataSet/paired_grenade_complete_ring/gain-00.png`至`gain-08.png`，九张全部实际查看。
- 双端审核：[143–154（本地产物说明）](../../ARTIFACTS.md#artifact-8d7a9e460d94)、[155–166（本地产物说明）](../../ARTIFACTS.md#artifact-6fbb73a95ae3)、[167–169（本地产物说明）](../../ARTIFACTS.md#artifact-78e8940d737e)。全部实际查看后才写接受。

[verification.json](../../DataSet/paired_grenade_complete_ring/verification.json)确认新27决策、108次hash检查通过：source、camera、camera标注、审核页与spec一致，接受框等于展示提案，与旧接受身份交集0。九张gain图及旧decision文件保存hash快照。该核验不代表专家准确率。

本子任务七条最终计数变为117/130/102/100/101/108/100，合计758个唯一接受，七条均≥100；各类正式导出和论文数据量是否达到目标由主任务统一核验，不能仅据本子任务宣称整个数据集完成。
