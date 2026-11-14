## 更正：本初稿已作废

下文“400/400通过”及待用户split批准的结论均已撤回。最终为393接受+7未决，已经导出为5229版；不是400接受。几何检查被过早登记为目视准入的错误、完整24项修框与历史保留见[更正及交付报告](four-recording-paired-expansion-5229.md)。以下保留原初稿作为错误历史，不作当前准入依据。

# 四条优先录音双端候选复核

2026-11-14，针对全94录音审计提出的180126、124241、124440、125924，建立独立的双模态候选目录 `DataSet/four_recording_paired_annotation/`。公开matches与ARIS FrameTime→SD offset映射均来自本地来源；每条取100个不同的共同可映射身份，合计400个。相机框和声呐框先由图像处理生成候选，再在20张覆盖全程的逐对总览页中复核。

结果：400/400通过候选框几何和目视同类对应登记为 `accepted_candidate`；没有整条录音被否决。180126为bomb z500/tilt−34/roll90；124241与124440为grenade z250/tilt−42/roll90的两种采集设置；125924为grenade z750/tilt−22/roll0 Min/15dB。每个候选保留相机、raw声呐、帧号、SD索引和SHA-256。候选框是本轮助手新增标注，不是原始标签，也不是专家GT；没有认证精密同步。

这400个样本还没有加入4,836对数据集、没有进入train/val/test，也没有训练、推理或新的test访问。`review-decisions.json`中的`dataset_admission=pending_user_split_review`保留准入边界。124241/124440保守放在同一候选来源组；正式重分前仍需按recording-level split与repeat关系决定角色。所有原始源和现有数据保持不变。

浏览材料：

- [全程候选总览（本地产物说明）](../../ARTIFACTS.md#artifact-2a82a570312f)
- [逐对框复核页（本地产物说明）](../../ARTIFACTS.md#artifact-e2edc67983a9)
- [复核决定（本地产物说明）](../../ARTIFACTS.md#artifact-3dfa448166fb)
- [复核摘要（本地产物说明）](../../ARTIFACTS.md#artifact-2328e7daf516)
