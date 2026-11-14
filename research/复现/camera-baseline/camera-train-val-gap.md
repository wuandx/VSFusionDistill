# camera S训练自评与val落差排查

2026-11-13，按用户授权及[事前计划](../../experiment/archive/camera-train-self-evaluation-plan.md)。只评已完成camera YOLOX-S640×384 epoch200 actual raw，不改训练、标签、split或阈值，不读test。继续使用research-workflow审计记录。

## 已取得的结论

当前不是“训练集也大量错类”。模型几乎记住了训练集，却没有将这种表现稳定迁移到部分val录音；这是实证的train–val落差。可称训练拟合充分、泛化受限，但不能仅凭此区分过拟合、采集条件差异、训练可见线索依赖，或断言200epoch造成过度训练。

| 集合 | 图片 | pooled mAP@[.5:.95] | AP50 | AP75 | AR1 |
|---|---:|---:|---:|---:|---:|
| train自评 | 1800 | 100.00 | 100.00 | 100.00 | 100.00 |
| val | 600 | 64.58 | 80.41 | 75.67 | 69.40 |

train三类各600、18条录音的相同指标均100%，这是训练自评，不是泛化成绩。val逐类mAP：bomb63.01、mortar82.43、grenade48.28。

## 固定阈值错误统计

score≥0.25/IoU≥0.5筛查，分组规则沿用前次诊断，不等于AP计算：

| 集合 | 同类匹配帧 | 错类重叠帧 | 其余未匹配帧 | 额外/不匹配预测FP |
|---|---:|---:|---:|---:|
| train | 1800 | 0 | 0 | 0 |
| val | 502 | 88 | 10 | 142 |

train在0.01/0.25/0.50三个预定门槛均1800个匹配、无额外框；最佳同类IoU最小0.9664、中位0.99644。val最佳同类IoU中位0.86123。这说明train AP100不是仅因IoU门槛宽松。

## 实现/数据核对

1. train与val的[权重身份](../../runs/camera_recording_baseline/train/train_actual_raw_epoch200/weight-identity.json)匹配同一epoch200 checkpoint SHA256 edff61c275274a58112e8e408a25a9a76dd308c79de8cfaba3e6474dbdc974a0，实际raw从ema_state_dict.module.*严格加载。均model.eval/no_grad、相同pipeline、BGR0–255、无增广、same score/NMS/max100；仅样本集合变为train，sampler关闭shuffle，没有拟合或更新参数。
2. 1800份训练原相机JSON的hash等于训练manifest记录值；原class、xyxy→xywh、COCO类别ID、数据加载labels、image_id及文件名逐项对应，通过。排除了已检查转换层面的全局类序反转/框错配，不认证原始人工标签的全部语义。
3. 从18条train与6条val录音各取首张，共24张，比较正常GT与清空GT后的模型预测：类别、框、分数逐项完全相等。[控制记录](../../runs/camera_recording_baseline/train/gt-independence.json)。连同源码predict只用图像/元信息的检查，未发现检查范围内推理使用GT伪造高分的证据，不升级为所有实现永远无错。
4. 先前88个错类val查询所检索出的同GT类别train近邻176次引用，逐个加入本轮真实预测，全部满足score≥.25/IoU≥.5。176是引用次数，不冒称176唯一训练帧。此前训练图只有GT，不能用其外观代替训练预测；本轮已补齐这项证据。

## 可直接查看的证据

[6组真实预测并排（本地产物说明）](../../ARTIFACTS.md#artifact-a7247ef120f7)：左val错分、右两张同类train近邻，三张都用同一模型实际预测，绿GT/红最高分预测，含上下文与GT裁剪。[全train/val固定阈值统计](../../DataSet/camera_train_self_review/summary.json)、[train逐帧CSV（本地产物说明）](../../ARTIFACTS.md#artifact-b0082fba5804)、[val逐帧CSV（本地产物说明）](../../ARTIFACTS.md#artifact-e51126498608)、[近邻真实预测（本地产物说明）](../../ARTIFACTS.md#artifact-cf77298a8514)。

实际查看121539_0088及182317_0285两组新增真实预测：前者val被认mortar，而train121124_0714/121327_0791认grenade正确；两训练图带明显标记块，val外观/背景有差异。后者val为大尺度底部截断并被认grenade，同类train181139_0208/175000_0152为更完整斜视且认bomb正确。可见差异只提供进一步假设，不证明标记/截断是原因，也不能断言近邻是同一3D视角。

当前没有需要用户代为排查的代码问题，不要求全量重标。若下一步需要人工提供信息，应限于明确样本：确认GT物体类别是否可信、是否存在截断/遮挡以及训练近邻与val的可见部件区别；不要据模型意见直接改标签。人工意见仍不能代替受控遮挡/背景对照。

## 后续边界

本轮无需重新训练即可确认第一种现象。不能以此立刻增加epoch、改标签或将val移进train；也不能据训练集100%认定模型“学会了稳定语义”。若继续查原因，应另行预登记只在train/val进行的背景/标记遮挡、尺度/截断与输入处理控制；这些测试可提示敏感性，若引入明显分布外操作也须限制解释。先完成现有四项统一权重评价，不用test选择修复。

完整指标：[train](../../runs/camera_recording_baseline/train/train_actual_raw_epoch200/metrics.json)、[val](../../runs/camera_recording_baseline/train/val_actual_raw_epoch200/metrics.json)。控制脚本最初逐字段赋空InstanceData触发长度检查，未完成控制；改为整体空切片后24张控制通过，初次失败日志保留gt-independence-preparation-failed.log，未改变模型或数据。
