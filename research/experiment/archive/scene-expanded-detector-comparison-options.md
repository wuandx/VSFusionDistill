# 不涉及蒸馏的检测baseline与补充实验建议

2026-11-13。用户要求在4081对数据上讨论可与相关论文对接的baseline；仅建议，不启动训练、不修改既定两臂方案或划分。

## 建议范围

首批声呐比较五种：YOLOX-S（已有计划）、YOLOX-M、YOLOv8s、Faster R-CNN R50-FPN、RT-DETR-R18。覆盖当前模型、同家族容量、更换单阶段检测器、两阶段检测器和Transformer检测器。R18只是RT-DETR的预算选择，不称与S严格同参数；实际参数/FLOPs/速度须实测。相机先保留YOLOX-M；需要教师容量对照时再加camera-S，不要求每个检测器双模态全量铺开。

候选扩展：YOLOX-Nano；CMHD的未蒸馏YOLOX-S-Ghost（含文中CA及局部LightGhostCSP设计，须先取得或核验实现；普通Ghost替换不能冒充原结构）；再考虑一项有可核验代码的声呐专用方法。不能把完整CMHD、CMOLD、KD-YOLOX-ViT放进无蒸馏表并忽略其训练监督差异。

## 论文依据与证据格式

- CMHD，已读本地XML提取与发布商HTML，没有LaTeX源码：4.3节明确未蒸馏YOLOX-Nano/YOLOX-S-Ghost；采用几何投影声呐标签、640输入、50epoch。它们可作为在我方数据重训的方法候选，论文原表不是我方可见回波标签上的成绩。来源：https://www.mdpi.com/1424-8220/26/14/4340 。
- UATD数据集论文，已有本地LaTeX `related_work/fls-multibeam-detection-dataset/source/main.tex`：比较Faster R-CNN多backbone与YOLOv3；支持选择Faster R-CNN作为声呐领域传统对照，不意味着我方采用它的12epoch/ImageNet/512高配方。来源：https://arxiv.org/abs/2212.00352 。
- YOLO-SONAR论文发布商HTML比较Faster R-CNN、RetinaNet、YOLOv8、YOLOv10及Transformer等多类检测器；这里选择YOLOv8s为我方预算决策，未宣称该论文使用s规模。来源：https://www.frontiersin.org/journals/marine-science/articles/10.3389/fmars.2025.1539210/full 。
- RT-DETR官方仓库列出R18及COCO-only和COCO+Objects365不同权重；建议COCO-only避免引入额外预训练数据。来源：https://github.com/lyuwenyu/RT-DETR 。

## 公平比较

固定现2472/894/715身份、原始图像和GT语义、来源组隔离、类别编号、pooled COCOeval及场景报告。test保持封存。各方法使用COCO-only预训练，记录实际发布版本、载入范围与随机head；不得引入已见UXO权重。统一目标输入画布，逐一验证框逆变换，不能默许RT-DETR或YOLO实现默认stretch而将其与keep_ratio混称同一几何。

跨家族不把YOLOX的SGD/.00125强制用于所有模型。各模型的优化器/LR/增广按核实的官方配置作适配，执行前冻结；给相同val调参预算并报告全部尝试，注明这比较的是模型及配方组合。受控架构比较则另表固定可共享的配方，不能与官方配方结果混写。沿用200epoch最终raw规则可以建立统一预算表，但须检查每个家族是否正常收敛，不因它未收敛就称架构差；任何延长预算另登记。

首轮seed0筛查运行有效性；形成正式主要结论时对纳入主比较的模型补0/1/2并报均值/标准差。检测器原生NMS与端到端后处理保留其语义，统一最终maxDets与COCO评价；不强迫无NMS模型添加NMS。低score导出阈值验证不会改变AP排序后冻结。真实raw/EMA身份按各实现核验。

参数/FLOPs只统计有效推理网络；同GPU、batch1、精度、输入、预热、CUDA同步与同一计时范围比较延迟。记录网络forward和含各模型必要后处理的延迟，不直接引用论文FPS到本表。

## 比继续堆模型更有价值的补充实验

1. 固定模型和共同val的扩量对照：先检查旧训练录音与新val是否重叠；旧checkpoint不可直接复用。用新train内的场景受限子集与全部2472训练相同模型、种子和配方，比较相同894val。自然扩量版会同时改变数量与场景；要分离场景多样性，另取相同数量的少场景/多场景子集，记录可行性及类别/录音差异。固定epoch与固定更新次数分别回答不同问题，事前选择并如实报告，不宣称其他因素全部不变。
2. 逐场景评价：所有主表模型必做，不另训练；pooled场景AP、逐录音失败、样本和独立来源数量。train-only场景没有独立留出结果，记N/A，不重分现有test凑覆盖。
3. 增广对照：以已完成YOLOX-S baseline为对照，预登记一种具体增广及参数；其他成员/预算/起点不变，只用val选择，不一次混加多种后声称单因素收益。
4. 少样本曲线：必要时对train做25/50/100%子集，保持来源组/场景分布可追溯并报告实际数量；不能把相邻帧当独立来源增长，固定val。优先级低于主比较和扩量控制。

所有建议仍需在实际实施前登记各run目的、唯一改动或复合平台差异、对照、判定和停止条件。没有预设AP门槛。当前标注和开发历史不同于论文，论文原值只能在单独背景表中引用，不与本地结果直接排序或计算提升。暂不另开UATD数据建设；如需公共benchmark主张，再独立预登记UATD官方划分实验。
