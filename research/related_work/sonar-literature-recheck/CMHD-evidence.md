# CMHD 声呐标注路线：原文复核

复核日期：2026-11-11。本次只读论文和既有文献副本，没有访问本地 test 样本、训练或生成标签。

## 来源与格式

- 论文：*Lightweight Underwater Sonar Object Detection via RGB-Guided Heterogeneous Distillation*，DOI [10.3390/s26144340](https://doi.org/10.3390/s26144340)。
- 官方全文入口：[PMC13417324](https://pmc.ncbi.nlm.nih.gov/articles/PMC13417324/)。
- 本次直接解析的是 [JATS XML（本地产物说明）](../../ARTIFACTS.md#artifact-f5ac120ef892)，**不是 LaTeX**；抓取来源为 [Europe PMC fullTextXML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13417324/fullTextXML)。
- 该副本与 `source-check-20261110/cmhd-europepmc-fulltext.xml`、`recording-split-review-20261111/cmhd-fulltext.xml` 的 SHA256 均为 `7e1cf91e74e20f063656fd91c8c64e8f0b59c1b2d4c7272e597fdd261f3f9601`。
- [可读段落索引（本地产物说明）](../../ARTIFACTS.md#artifact-94799dbed714)第 55–57 行对应 §3.1；第 102 行对应 §4.6 的标注限制。本次引文均在原始 XML 中核对。

## §3.1：作者确实描述了可使用的声呐标注路线

> Using the target’s initial pose, gantry motion trajectories, sonar extrinsics, and ARIS polar imaging geometry from system calibration, we projected the 3D UXO model onto sonar images frame by frame and generated physically grounded axis-aligned bounding boxes.

作者明确使用目标初始位姿、gantry 运动轨迹、声呐外参、ARIS 极坐标成像几何逐帧投影 3D 模型，生成轴对齐声呐框。不能把这条路线描述为不可用，也不能要求先完成 GoPro 标定才允许检查这条直接声呐链。

> These sonar bounding boxes were generated automatically through geometry-based frame-by-frame projection rather than manually drawn from scratch.

> To improve annotation quality, we additionally conducted manual visual inspection of the projected results and checked samples with obvious misalignment or anomalies. When necessary, such problematic samples were handled during dataset curation to reduce the influence of possible sensor calibration drift, gantry motion errors, and sonar imaging noise as much as possible.

作者声明做了投影、人工目视检查及异常样本处理。这里没有具体说明异常是删帧、修框、修标定还是其他操作；不能替作者选择一种解释，更不能据此声称作者逐帧调模型。

> Nevertheless, we note that this physics-guided annotation strategy may still be affected by slight residual calibration or motion errors and therefore is not fully equivalent to exhaustive frame-by-frame manual annotation.

作者并未声称每个框均经过独立、逐帧专家标注，也承认几何标签的残余误差。

## Data Availability Statement：作者生成的标签未在正文直接附出

原始 XML 的 `back/fn-group` 中：

> The public UXO multi-modal dataset used in this study is available at https://github.com/dfki-ric/uxo-dataset2024 (accessed on 16 June 2026). The geometrically projected sonar annotations generated in this study are available from the corresponding author upon reasonable request.

因此，论文引用公开 UXO 原始数据，并称其额外生成的声呐框可向通讯作者合理申请。该陈述不等于公开 UXO 已经包含这些声呐框，也不等于没有作者回复就无法自行实现投影。

## 正文能确认和仍不能确认的边界

- 能确认：上述投影路线；人工 QA 与异常处理；每类随机选 10 条完整轨迹、每轨迹均匀采 100 帧、轨迹级 6:2:2；1800/600/600 配对样本；作者承认残余误差。
- 正文未给出可直接复算的各模型 `mesh→target` 数值注册矩阵、逐轨迹初始目标位姿数值、beam 方位符号公式、range/beam 到最终图片像素的完整实现，以及异常样本的具体处理清单。
- 原文共 9 个编号公式，涉及蒸馏损失、门控及网络模块，没有提供 ARIS 投影公式。全文未给出 beam 取反作为修正的论据。
- 本次所查文章 XML 没有投影实现代码链接；不能扩大成“互联网上绝无实现”。
- §4.4 另有 100 张困难声呐图像的手工标注评估子集；不能把这项手工标注追认到全部 3000 张几何标签。

## 对当前失败的含义

论文报告实现成功，而当前本地固定 mesh 候选尚未得到可信对齐，这说明本地复现链尚未核对到同等程度。当前 18 帧失败不能证伪 UXO 数据或上述物理路线。仅凭人工观察反号后更接近回波，也不能认证 beam 符号；符号应由物理坐标系、官方 beam 编号和显示方向的完整映射确定。
