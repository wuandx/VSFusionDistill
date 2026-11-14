# weak_coverage_sonar_s_student：本地单声呐学生基线

用户“我本地再跑一个吧，跑一个单声呐的学生模型”授权本地训练。目的：在当前配对划分上取得sonar-only YOLOX-S无蒸馏基线，为后续camera-M→sonar-S比较提供独立起点。本次不依赖相机教师结果，不执行KD。

固定paired_weak_scene_coverage_pan_split：只导出4138train/573val声呐，共4711图；身份/录音/组与相机教师完全相同，原可见回波框和标签血缘保持。不读取原研究test或当前test图/框，不修改任何旧数据和run。旧val/test用于开发划分、声呐助手标注非专家GT、部分场景缺独立留出的限制保持。

相对旧scene_sonar_s_baseline，计划变动仅数据版本及随完整epoch增加的更新数，模型/初始化/输入处理/优化器/日程/评价保持。由于划分与样本量均变，不将新旧AP差当单因素泛化收益。相机M教师与声呐S模型容量/模态/硬件不同，不作仅模态因果比较。

YOLOX-S，COCO-S backbone/neck fresh初始化，三类head随机；不续旧UXO权重。checkpoint SHA256 4592a793b95f18f62fd73fbb6cfe61dd445f71a8e072366e114e7134d4492760。seed0，batch8，200epoch，每epoch完整4138样本、518更新、末batch2，总103600更新。FP32，无增广；声呐原图等比resize到640范围，右/底114补为640×640，BGR0–255，不改变原图增益或翻转。SGD lr.00125、momentum.9、nesterov、wd.0005、clip35，继承5epoch warmup、cosine与15epoch尾段。每10epoch actual raw val；固定epoch200实际raw主结果，EMA单列，不选best。score.01/NMS.65/max100，pooled/逐类/逐录音完整COCO AP/AR，test关闭。

准入：数据源与确认划分hash匹配，4711复制hash/解码/原框/YOLO–COCO往返、身份和组互斥、跨角色重复校验，且与教师train/val身份相同；实际GPU batch8含各类/尺寸、末batch2前后向、严格逐tensor COCO初始化、推理逆几何、raw/EMA保存身份通过；预检和正式训练数据/实现/源/冻结/初始化/配置语义hash相同。与旧sonar配方独立比较。

停止：任何核验失败、非有限loss/梯度或CUDA失败即停止并保留尝试，不自动换batch/学习率/数据、无自动重试。持久WSL user service Restart=no，确认真实优化迭代后登记启动；完成须确认epoch200/103600及最后raw val才登记AP。本地原camera尝试保持停止，不影响远端camera-M。
