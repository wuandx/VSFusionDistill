# 182317 原相机库存与完整可见数量上限独立审计

**没有发现 source-inventory 漏掉原本有相机图和原标签的允许配对。** 当前 2023-09-20_182317 的 146 个身份恰好等于本地与官方导出归档中全部原相机标签：ARIS frame 140–285。按当前时间关联和相机完整可见要求，该录音无法达到 100；对边缘过渡作最宽松计算，完整相机候选上限仍只有 **36**。36 是保守上界，不是新增接受数量。

## 来源核验

[机器记录（本地产物说明）](../../ARTIFACTS.md#artifact-00d88669a991) 保存关键文件 SHA256、完整 0–139 时间重放、每张审核图 hash。

| 原始产物 | 本地数量 / frame范围 | 官方导出归档 catalog |
|---|---|---|
| gopro JPG | 501 / 140–640 | 完全相同 |
| aris_raw PGM | 501 / 140–640 | 完全相同 |
| labels JSON | 146 / 140–285 | 完全相同 |
| temporal manifest | 146 / 140–285 | 全部原标签身份 |
| source-inventory | 146 / 140–285 | 与 temporal 身份集合完全一致 |

对这 146 个身份的原图与原标签共 292 个文件，本轮逐一复核：大小及 CRC32 等于已获取的官方导出归档 catalog，SHA256 等于 temporal manifest 的原始输入记录。这里复核的是已保存官方归档目录元数据，没有重新下载整个归档。

本地原文件目录：D:/pby/uxo-full/extracted/recordings/100lbs_bomb/2023-09-20_182317/。归档目录证据：related_work/uxo/sd-fhd-trace/data_export_recordings/catalog.json。原研究与原数据保持只读。

## 为什么 1–139 不在库中

1–139 不只缺少当前副本，而是官方导出目录本身没有这些 native gopro JPG 与 labels JSON。现有 matches.csv 的 aris_onset=61，gopro_offset=-161。沿既有公式 `int((FrameTime - onset_time) / 1e6 * fps) + gopro_offset`、fps=30000/1001 重放，0–139 全为负 SD index；frame139→−2，140→0，141→2。140 恰好是现行 SD 对应起点。因此不能把提前139帧写为“源库存漏选”。

SD 视频 1017 帧、起点 PTS 7.378；FHD 1024 帧，比SD早7帧。少量 FHD 头部覆盖不提供缺失的原相机标签，也不能无验证切换配对时基。

**该 matches 行 notes 明确含 `incorrect gopro offset`。** 这是官方原始记录的已知疑点；本次仅说明现行发布关联链如何生成覆盖范围，不认证其正确同步，更不能根据标签数量自行改 offset 或用注册吸收误差。

## 286–640 是否是被漏掉的可用配对

该范围存在 355 个 native gopro JPG / ARIS PGM，但没有原 camera labels。它们不属于“保留原相机框的配对库存”遗漏，而是缺少原标注；扩大到这些身份需要新增相机标注及相应准入流程。本次未打开这些标签缺失身份的图像、未自行造框、未纳入候选。

库存生成代码 tools/build_paired_paper_scale.py 对 temporal manifest 每个 member 都写一行 inventory，并未先按可见性把 1–139 或 286+ 删去。temporal 从已有 gallery 中原始有标注身份建立；本轮身份集合核验也直接排除了 inventory 这一级的遗漏。

## 相机完整可见上界

实际查看该录音全部 146 张已有 reference_sd 图，并查看 164–179 原底端放大图。原相机框自166开始 ymax=360，直到285共120个。这只能算触边警示，**不是166起物体全部截断的证据**：166–170还能看到底部帽缘；171–175处于触底或开始裁切的过渡。176以后明显截断，后续全部146身份检查未见目标重新完整进入画面。

为避免用临界帧过度收紧结论，即使把140–175全部36个身份都当作完整可见，其余176–285的110个仍明显截断。因此当前原标签与现行关联下相机完整帧数≤36，严格低于100。实际合格数量还要检查声呐边界及框，不能把36直接计入accepted。

证据页：DataSet/bomb182317-camera-coverage-audit/camera-0000.jpg、camera-0036.jpg、camera-0072.jpg、camera-0108.jpg、camera-0144.jpg；底部过渡：bottom-transition.jpg、bottom-transition-late.jpg，全部已实际查看。

## 边界

本次为独立只读审计，未改任何原决定、原相机框、时间、注册、split或训练；没有打开原test图像或评价test。当前硬上界限定于既有标签、现行发布关联和完整相机准入条件，不应升级为该次采集在任何新时间校正/新增标注条件下都不可能凑100。若换时间或新增camera标签，那是新的准入问题，必须独立取得证据，不能靠放宽库存描述达成数量。
