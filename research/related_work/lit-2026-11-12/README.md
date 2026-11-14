# 相关论文检索：为 CMOLD 一系论文补文献面

生成时间：2026-11-13T11:29:12　检索方式：arXiv HTML 搜索（18 组 abstract 字段查询，592 条候选，去重并排除既有 63 篇后按主题打分）＋ 逐条 abs 页核验。

本文件只登记**已核验元数据**的条目：标题、作者、日期、arXiv 编号均取自 `https://arxiv.org/abs/<id>` 的 citation meta 标签，随附 SHA-256。未取得正文的不写内容判断，只写检索所见。

综述与定位判断（哪些说法立得住、撞车排查、反证）见 [SURVEY.md](SURVEY.md)；本文件只做逐篇登记。
代码可得性（91 篇逐个查过仓库）见 [CODE.md](CODE.md)。
## 0. 本轮口径

- 「我论文」按 CMOLD 理解：Aydogmus & Erer, *Cross-Modality Object-Level Knowledge Distillation for Enhanced Underwater UXO Detection*, IEEE Access 14, 2026, DOI 10.1109/ACCESS.2026.3666096。camera(RGB) teacher → sonar student，共享 YOLOX，object-level KD。

- 收录分三档：**A** 直接同题/同轴；**B** 方法或数据可迁移；**C** 背景与对照。分档是我方判断，不是论文自述。

- LaTeX 列只写**实际拿到的作者源包**；`e-print` 返回 PDF 的记为「作者只投 PDF」，不冒充 LaTeX。

- 统计：选中 102 篇，成功下载 102 篇，其中 96 篇带 .tex 源文件。


## 等级 A：直接同题/同轴，必须精读并引用（28 篇）

| 标题 | arXiv | 日期 | 相关性（我方判断） | 对应章节 | LaTeX |
|---|---|---|---|---|---|
| Localization Distillation for Dense Object Detection | [2102.12252](https://arxiv.org/abs/2102.12252) | 2021/02/24 | 在 dense detector（GFocal，与 YOLOX 同族）上证明**定位知识比语义知识更值得蒸**，logit 模仿可胜特征模仿（40.1→42.1 AP） | II-C | 有（1 个 .tex） |
| G-DetKD: Towards General Distillation Framework for Object Detectors via Contrastive and Semantic-guided Feature Imitation | [2108.07482](https://arxiv.org/abs/2108.07482) | 2021/08/17 | 首个同时覆盖**同构与异构**师生对的通用检测蒸馏（跨 FPN 软匹配 + 对比关系蒸馏）；用它可以正当化本文「共享 YOLOX 架构」的选择，并说明异构情形已被覆盖 | II-C | 有（2 个 .tex） |
| Focal and Global Knowledge Distillation for Detectors | [2111.11837](https://arxiv.org/abs/2111.11837) | 2021/11/23 | 证明**等权蒸馏有害**、须按前景/背景分离并重建像素间关系（RetinaNet/FasterRCNN/RepPoints/MaskRCNN +2.9–3.6 mAP）——本文只蒸目标区域的直接依据 | II-C | 有（1 个 .tex） |
| UniDistill: A Universal Cross-Modality Knowledge Distillation Framework for 3D Object Detection in Bird&#39;s-Eye View | [2303.15083](https://arxiv.org/abs/2303.15083) | 2023/03/27 | universal cross-modality KD for 3D detection | II-C→跨模态 | 有（7 个 .tex） |
| Underwater object classification combining SAS and transferred optical-to-SAS Imagery | [2304.11875](https://arxiv.org/abs/2304.11875) | 2023/04/24 | 7052 对光学/SAS 影像迁移，光学→声学监督迁移直接先例 | II-B | 无（作者只投 PDF） |
| Learnable Cross-modal Knowledge Distillation for Multi-modal Learning with Missing Modality | [2310.01035](https://arxiv.org/abs/2310.01035) | 2023/10/02 | cross-modal KD when a modality is missing at test time | III/IV | 有（2 个 .tex） |
| Object-centric Cross-modal Feature Distillation for Event-based Object Detection | [2311.05494](https://arxiv.org/abs/2311.05494) | 2023/11/09 | 把「object-level」做成**显式模块**：slot attention 把特征图解耦为物体级 + 像素级再蒸馏，几乎把与教师的差距减半——直接支撑本文 object-level KD 的命名与设计 | II-C | 有（23 个 .tex） |
| RadarDistill: Boosting Radar-based Object Detection Performance via Knowledge Distillation from LiDAR Features | [2403.05061](https://arxiv.org/abs/2403.05061) | 2024/03/08 | 跨模态**特征级**蒸馏的标准配方（跨模态对齐 + 激活阈值过滤 + proposal 内蒸馏），radar-only 20.5 mAP / 43.7 NDS——本文方法对照与超参依据 | II-C | 有（6 个 .tex） |
| Knowledge Distillation in YOLOX-ViT for Side-Scan Sonar Object Detection | [2403.09313](https://arxiv.org/abs/2403.09313) | 2024/03/14 | sonar+YOLOX+KD, closest single precedent | II-C | 有（10 个 .tex） |
| RGB-Sonar Tracking Benchmark and Spatial Cross-Attention Transformer Tracker | [2406.07189](https://arxiv.org/abs/2406.07189) | 2024/06/11 | RGB–声呐配对跟踪基准 + 造伪配对的 SRST | II-B | 有（28 个 .tex） |
| Synth-SONAR: Sonar Image Synthesis with Enhanced Diversity and Realism via Dual Diffusion Models and GPT Prompting | [2410.08612](https://arxiv.org/abs/2410.08612) | 2024/10/11 | 双扩散+GPT 合成声呐图像，替代方案的最近邻 | V | 有（1 个 .tex） |
| Syn2Real Domain Generalization for Underwater Mine-like Object Detection Using Side-Scan Sonar | [2410.12953](https://arxiv.org/abs/2410.12953) | 2024/10/16 | unexploded mine-like objects, side-scan, domain generalization | II-A | 有（1 个 .tex） |
| BESTAnP: Bi-Step Efficient and Statistically Optimal Estimator for Acoustic-n-Point Problem | [2411.17521](https://arxiv.org/abs/2411.17521) | 2024/11/26 | BESTAnP：acoustic-n-point 解耦平移(range)与旋转(azimuth)，FLS 投影/位姿的标准解法 | III/IV | 有（1 个 .tex） |
| Sonar-based Deep Learning in Underwater Robotics: Overview, Robustness and Challenges | [2412.11840](https://arxiv.org/abs/2412.11840) | 2024/12/16 | 声呐深度学习综述：数据有限+固有噪声为本领域瓶颈 | II-A | 有（6 个 .tex） |
| Can Optical Denoising Clean Sonar Images? A Benchmark and Fusion Approach | [2503.01655](https://arxiv.org/abs/2503.01655) | 2025/03/03 | 9 个光学去噪器迁声呐 × 4 检测器含 YOLOX；光学→声呐可行性前提 | II-B | 有（1 个 .tex） |
| Rejecting Outliers in 2D-3D Point Correspondences from 2D Forward-Looking Sonar Observations | [2503.16066](https://arxiv.org/abs/2503.16066) | 2025/03/20 | 2D FLS 的 2D-3D 对应外点剔除（90% 外点率），真实数据上 3D→声呐对应的可靠性边界 | III/IV | 有（1 个 .tex） |
| A Convex and Global Solution for the P$n$P Problem in 2D Forward-Looking Sonar | [2504.04445](https://arxiv.org/abs/2504.04445) | 2025/04/06 | 2D FLS 的 PnP：point-to-line 3D 配准 + 正交近似，把 3D 点投到 FLS 的正向模型与全局最优解——投影框的几何底座 | III/IV | 有（1 个 .tex） |
| Feature Geometry for Stereo Sidescan and Forward-looking Sonar | [2507.05410](https://arxiv.org/abs/2507.05410) | 2025/07/07 | 唯一显式做「把一侧声呐看到的特征投到另一侧声呐」的几何方法（FLS↔侧扫，仿极线几何） | III/IV | 有（1 个 .tex） |
| DOD-SA: Infrared-Visible Decoupled Object Detection with Single-Modality Annotations | [2508.10445](https://arxiv.org/abs/2508.10445) | 2025/08/14 | 与本文最同构：**只有一侧模态有标注**，靠跨模态知识迁移 + 三阶段自训练 + 伪标签分配器把标注能力搬到无标注模态——直接对应学生侧「少量人工标注 + 伪标签」 | II-C | 有（1 个 .tex） |
| Enhancing Object Detection with Privileged Information: A Model-Agnostic Teacher-Student Approach | [2601.02016](https://arxiv.org/abs/2601.02016) | 2026/01/05 | 把 **LUPI 正式引入检测**：特权信息（bbox mask / saliency / depth）仅训练期可用、推理零成本，5 个检测器一致超基线——本文「教师见强模态、学生只见弱模态」的理论框架 | II-C | 有（1 个 .tex） |
| Physically Motivated Knowledge Distillation for Blind Geometric Correction of Side-Scan Sonar Imagery | [2603.15200](https://arxiv.org/abs/2603.15200) | 2026/03/16 | KD used to correct side-scan imagery geometry | II-C | 有（1 个 .tex） |
| CTFS : Collaborative Teacher Framework for Forward-Looking Sonar Image Semantic Segmentation with Extremely Limited Labels | [2603.21071](https://arxiv.org/abs/2603.21071) | 2026/03/22 | 前视声呐教师-学生分割，2% 标注；同期最接近的师生框架 | II-C | 有（2 个 .tex） |
| Mine-JEPA: In-Domain Self-Supervised Learning for Mine-Like Object Classification in Side-Scan Sonar | [2604.00383](https://arxiv.org/abs/2604.00383) | 2026/04/01 | SSS 域内自监督，仅 1170 张无标注图；支撑声呐域内预训练 | II-A | 有（9 个 .tex） |
| Thermal-Det: Language-Guided Cross-Modal Distillation for Open-Vocabulary Thermal Object Detection | [2605.10130](https://arxiv.org/abs/2605.10130) | 2026/05/11 | 冻结 RGB 教师对**成对但无标注**的 thermal 数据提供几何+语义伪监督，无人工标注迁移开放词汇知识（+2–4 AP）——「强模态全标注、弱模态零标注」的最新范式 | II-C | 有（11 个 .tex） |
| Cross-Modal Knowledge Distillation without Paired Data: Theoretical Foundation and Algorithm | [2606.10504](https://arxiv.org/abs/2606.10504) | 2026/06/09 | cross-modal KD without paired data (theory+algorithm) | III/IV | 有（1 个 .tex） |
| FreqKD: Frequency-Decoupled Cross-Modal Knowledge Distillation for Infrared Object Detection | [2606.11572](https://arxiv.org/abs/2606.11572) | 2026/06/10 | RGB->IR cross-modal KD for object detection (closest modality gap analogue) | II-C→跨模态 | 有（7 个 .tex） |
| Aligned Consensus Teaching for Label-Efficient Oriented Object Detection in Weakly-Aligned Visible-Infrared Imagery | [2609.18124](https://arxiv.org/abs/2609.18124) | 2026/09/16 | 少数成对样本有标注、其余全无标注的半监督可见光-红外检测；共识伪标签 + 循环一致区域对齐 + 尾类实例增广，正是「学生侧标注稀缺」的解法与评测口径 | II-C | 有（1 个 .tex） |
| SonarVoxNet: Diver Detection in 3D Bounding Box using 3D Sonar | [2610.01644](https://arxiv.org/abs/2610.01644) | 2026/10/01 | SonarVoxNet：3D 声呐里的 3D bbox + 全身朝向（原只读 literature 已有 PDF，此处补 LaTeX） | II-A | 有（1 个 .tex） |

## 等级 B：方法或数据集可迁移，应引用（51 篇）

| 标题 | arXiv | 日期 | 相关性（我方判断） | 对应章节 | LaTeX |
|---|---|---|---|---|---|
| What&#39;s Mine is Yours: Pretrained CNNs for Limited Training Sonar ATR | [1706.09858](https://arxiv.org/abs/1706.09858) | 2017/06/29 | 最早的「声呐样本少→借预训练 CNN」路线 | II-A | 有（1 个 .tex） |
| Distilling Object Detectors with Fine-grained Feature Imitation | [1906.03609](https://arxiv.org/abs/1906.03609) | 2019/06/09 | object-level 蒸馏的源头：只在**近目标 anchor 位置**模仿（KITTI 上 +15% mAP）——本文「只蒸目标区域」的历史依据 | II-C | 有（1 个 .tex） |
| Learning Objectness from Sonar Images for Class-Independent Object Detection | [1907.00734](https://arxiv.org/abs/1907.00734) | 2019/07/01 | class-independent sonar object detection | II-A | 有（1 个 .tex） |
| Online Sensor Hallucination via Knowledge Distillation for Multimodal Image Classification | [1908.10559](https://arxiv.org/abs/1908.10559) | 2019/08/28 | 最早把「训练时全传感器可用、测试时缺模态」+ KD + privileged 讲清的一篇（分类任务，PAN-MS 评测）——缺模态蒸馏的思想源头 | II-C | 有（1 个 .tex） |
| A rasterized ray-tracer pipeline for real-time, multi-device sonar simulation | [2001.03539](https://arxiv.org/abs/2001.03539) | 2020/01/08 | 光栅+光线追踪声呐仿真：3D 场景→声呐图的正向管线，可验证投影框可见性 | II-A | 有（1 个 .tex） |
| A Comparison of Few-Shot Learning Methods for Underwater Optical and Sonar Image Classification | [2005.04621](https://arxiv.org/abs/2005.04621) | 2020/05/10 | 水光与侧扫声呐 few-shot 对比，FSL 优于微调 | III/IV | 有（15 个 .tex） |
| MimicDet: Bridging the Gap Between One-Stage and Two-Stage Object Detection | [2009.11528](https://arxiv.org/abs/2009.11528) | 2020/09/24 | 一阶段/两阶段异构结构蒸馏源头篇（共享 backbone 双 head 使特征兼容，COCO 46.1 mAP）——回答「师生结构不完全一致时怎么蒸」 | II-C | 有（1 个 .tex） |
| Target Detection and Segmentation in Circular-Scan Synthetic-Aperture-Sonar Images using Semi-Supervised Convolutional Encoder-Decoders | [2101.03603](https://arxiv.org/abs/2101.03603) | 2021/01/10 | 半监督 CSAS 检测/分割；自然图像模型需改造 | II-A | 有（1 个 .tex） |
| Minimax Robust Landmine Detection Using Forward-Looking Ground-Penetrating Radar | [2111.08379](https://arxiv.org/abs/2111.08379) | 2021/11/16 | UXO/landmine detection, non-optical sensor | II-A | 有（20 个 .tex） |
| Knowledge Distillation for Object Detection via Rank Mimicking and Prediction-guided Feature Imitation | [2112.04840](https://arxiv.org/abs/2112.04840) | 2021/12/09 | 一阶段检测器专用：师生对候选框**排序不同**导致精度差，蒸排序优于蒸软标签——对本文伪标签筛选与置信度校准可直接复用 | II-C | 有（1 个 .tex） |
| Beyond Bounding Box: Multimodal Knowledge Learning for Object Detection | [2205.04072](https://arxiv.org/abs/2205.04072) | 2022/05/09 | 显式区分 **image-level 与 object-level 跨模态互信息**蒸馏（+1.6–2.1%），是本文 object-level 措辞最贴的较早文献 | II-C | 有（1 个 .tex） |
| Learning Pseudo Front Depth for 2D Forward-Looking Sonar-based Multi-view Stereo | [2208.00233](https://arxiv.org/abs/2208.00233) | 2022/07/30 | FLS 单图 3D 病态性 + 伪前视深度/多视图立体：缺仰角为何使 3D 框投出区域 | II-A | 有（1 个 .tex） |
| Development of a Simulation Environment for Evaluation of a Forward Looking Sonar System for Small AUVs | [2210.06535](https://arxiv.org/abs/2210.06535) | 2022/10/12 | 光线追踪高保真 FLS 仿真环境（OCEANS 2019） | V | 有（1 个 .tex） |
| Cross-Modality Knowledge Distillation Network for Monocular 3D Object Detection | [2211.07171](https://arxiv.org/abs/2211.07171) | 2022/11/14 | cross-modality KD, monocular 3D | II-C→跨模态 | 有（1 个 .tex） |
| A Dataset with Multibeam Forward-Looking Sonar for Underwater Object Detection | [2212.00352](https://arxiv.org/abs/2212.00352) | 2022/12/01 | forward-looking sonar detection dataset (ARIS-adjacent) | II-A | 有（1 个 .tex） |
| Underwater Camouflage Object Detection Dataset | [2303.12946](https://arxiv.org/abs/2303.12946) | 2023/03/01 | UW-R/UW-S 成对光学与声呐标注集，量化配对稀缺 | II-B | 有（1 个 .tex） |
| X$^3$KD: Knowledge Distillation Across Modalities, Tasks and Stages for Multi-Camera 3D Object Detection | [2303.02203](https://arxiv.org/abs/2303.02203) | 2023/03/03 | 跨任务（实例分割教师）+ 跨模态特征 + 对抗 + 跨模态**输出**蒸馏组合，并给出 RADAR-based 3DOD 的泛化证据——可支撑「输出级 + 特征级并用」的设计 | II-C | 有（26 个 .tex） |
| MMANet: Margin-aware Distillation and Modality-aware Regularization for Incomplete Multimodal Learning | [2304.08028](https://arxiv.org/abs/2304.08028) | 2023/04/17 | 按分类不确定性加权蒸馏 + 专治「弱模态组合」的正则——对应本文学生模态信息量显著低于教师的场景 | II-C | 有（1 个 .tex） |
| CMDFusion: Bidirectional Fusion Network with Cross-modality Knowledge Distillation for LIDAR Semantic Segmentation | [2307.04091](https://arxiv.org/abs/2307.04091) | 2023/07/09 | bidirectional fusion + cross-modality KD | II-C→跨模态 | 有（9 个 .tex） |
| Motion Degeneracy in Self-supervised Learning of Elevation Angle Estimation for 2D Forward-Looking Sonar | [2307.16160](https://arxiv.org/abs/2307.16160) | 2023/07/30 | FLS 仰角自监督估计与运动退化：单帧仰角不可解的实证 | II-A | 有（1 个 .tex） |
| STARS: Zero-shot Sim-to-Real Transfer for Segmentation of Shipwrecks in Sonar Imagery | [2310.01667](https://arxiv.org/abs/2310.01667) | 2023/10/02 | 纯仿真训练零样本 sim-to-real 分割，+20% | II-A | 有（1 个 .tex） |
| AONeuS: A Neural Rendering Framework for Acoustic-Optical Sensor Fusion | [2402.03309](https://arxiv.org/abs/2402.03309) | 2024/02/05 | AONeuS：声-光联合神经表面重建，把光学几何与声学观测对齐 | II-B | 有（11 个 .tex） |
| Terrain characterisation for online adaptability of automated sonar processing: Lessons learnt from operationally applying ATR to sidescan sonar in MCM applications | [2404.18663](https://arxiv.org/abs/2404.18663) | 2024/04/29 | ATR 在非良性海底迅速退化；域差来自环境 | II-A | 无（作者只投 PDF） |
| A Generalization Theory of Cross-Modality Distillation with Contrastive Learning | [2405.03355](https://arxiv.org/abs/2405.03355) | 2024/05/06 | 给出跨模态 distilled 模型的泛化界：**源/目标模态距离**直接影响下游测试误差——为「光学→声呐 gap 大但仍可蒸」提供理论表述与限制条件 | II-C | 有（2 个 .tex） |
| Incomplete Multimodal Industrial Anomaly Detection via Cross-Modal Distillation | [2405.13571](https://arxiv.org/abs/2405.13571) | 2024/05/22 | 训练时多模态、**推理时可缺模态**的跨模态蒸馏——支撑「部署只有声呐」这一前提的合理性 | II-C | 无（作者只投 PDF） |
| LabelDistill: Label-guided Cross-modal Knowledge Distillation for Camera-based 3D Object Detection | [2407.10164](https://arxiv.org/abs/2407.10164) | 2024/07/14 | label-guided cross-modal KD, camera-based detector | II-C→跨模态 | 有（26 个 .tex） |
| Non-target Divergence Hypothesis: Toward Understanding Domain Gaps in Cross-Modal Knowledge Distillation | [2409.02438](https://arxiv.org/abs/2409.02438) | 2024/09/04 | analysis of domain gaps in cross-modal KD | III/IV | 有（1 个 .tex） |
| LEROjD: Lidar Extended Radar-Only Object Detection | [2409.05564](https://arxiv.org/abs/2409.05564) | 2024/09/09 | 在 Lidar→radar-only 上量化「跨模态 KD 最多 +3.9 mAP，不如多阶段 thin-out 的 +4.2」——提示本文必须把增益拆成 KD 项与初始化/伪标签项 | II-C | 有（9 个 .tex） |
| ROSAR: An Adversarial Re-Training Framework for Robust Side-Scan Sonar Object Detection | [2410.10554](https://arxiv.org/abs/2410.10554) | 2024/10/14 | side-scan sonar detector robustness | II-A | 有（11 个 .tex） |
| Learn from Foundation Model: Fruit Detection Model without Manual Annotation | [2411.16196](https://arxiv.org/abs/2411.16196) | 2024/11/25 | 强模型（SAM2+OpenCLIP）生成框→蒸馏到边缘小检测器，**完全无人工标注**即接近全监督——对应本文学生侧用伪标签替代人工标注的路线 | II-C | 有（1 个 .tex） |
| SCKD: Semi-Supervised Cross-Modality Knowledge Distillation for 4D Radar Object Detection | [2412.14571](https://arxiv.org/abs/2412.14571) | 2024/12/19 | semi-supervised cross-modality KD, radar | II-C→跨模态 | 有（1 个 .tex） |
| SAMKD: Spatial-aware Adaptive Masking Knowledge Distillation for Object Detection | [2501.07101](https://arxiv.org/abs/2501.07101) | 2025/01/13 | 空间分层掩码（粗到细编码 object-aware locality）+ 掩码 logit 蒸馏，35.3→38.8 mAP——「目标感知掩码」路线较新的一篇 | II-C | 有（1 个 .tex） |
| OceanSim: A GPU-Accelerated Underwater Robot Perception Simulation Framework | [2503.01074](https://arxiv.org/abs/2503.01074) | 2025/03/03 | OceanSim：GPU 水下仿真 + 实时成像声呐渲染（含代码），合成台 | II-A | 有（8 个 .tex） |
| CleverDistiller: Simple and Spatially Consistent Cross-modal Distillation | [2503.09878](https://arxiv.org/abs/2503.09878) | 2025/03/12 | simple spatially-consistent cross-modal distillation | II-C→跨模态 | 有（3 个 .tex） |
| SonarSplat: Novel View Synthesis of Imaging Sonar via Gaussian Splatting | [2504.00159](https://arxiv.org/abs/2504.00159) | 2025/03/31 | 高斯泼溅渲染声呐图，可微渲染工具 | V | 有（5 个 .tex） |
| Cross-Modal Distillation For Widely Differing Modalities | [2507.16296](https://arxiv.org/abs/2507.16296) | 2025/07/22 | cross-modal distillation across very different modalities | III/IV | 有（1 个 .tex） |
| RCTDistill: Cross-Modal Knowledge Distillation Framework for Radar-Camera 3D Object Detection with Temporal Fusion | [2509.17712](https://arxiv.org/abs/2509.17712) | 2025/09/22 | cross-modal KD radar-camera with temporal fusion | II-C→跨模态 | 有（13 个 .tex） |
| Sonar Image Datasets: A Comprehensive Survey of Resources, Challenges, and Applications | [2510.03353](https://arxiv.org/abs/2510.03353) | 2025/10/02 | 声呐数据集综述，数据稀缺最省事的引证 | II-A | 有（10 个 .tex） |
| Asymmetric Cross-Modal Knowledge Distillation: Bridging Modalities with Weak Semantic Consistency | [2511.08901](https://arxiv.org/abs/2511.08901) | 2025/11/12 | asymmetric cross-modal KD with weak semantic consistency | III/IV | 有（1 个 .tex） |
| IMKD: Intensity-Aware Multi-Level Knowledge Distillation for Camera-Radar Fusion | [2512.15581](https://arxiv.org/abs/2512.15581) | 2025/12/17 | 强度感知的多层级蒸馏，67.0 NDS / 61.0 mAP；来自 **DFKI-AV（与 CMOLD 的 DFKI UXO 数据集同机构）**，是同机构后续工作最该引的一篇 | II-C | 有（10 个 .tex） |
| Scalpel-SAM: A Semi-Supervised Paradigm for Adapting SAM to Infrared Small Object Detection | [2512.22483](https://arxiv.org/abs/2512.22483) | 2025/12/27 | 10% 标注把 SAM 蒸成专家教师 → 再用其伪标签训轻量下游模型，效果可比甚至超全监督——「少标注 + 伪标签 + 蒸馏」三段式的现成模板 | II-C | 有（2 个 .tex） |
| PEPR: Privileged Event-based Predictive Regularization for Domain Generalization | [2602.04583](https://arxiv.org/abs/2602.04583) | 2026/02/04 | LUPI 新范式：**不做直接特征对齐**，改为在共享隐空间预测特权模态潜特征，赢过对齐式基线——若声呐/光学特征空间不可直接对齐，这是可选的替代损失 | II-C | 有（3 个 .tex） |
| Sonar-MASt3R: Real-Time Opti-Acoustic Fusion in Turbid, Unstructured Environments | [2603.13585](https://arxiv.org/abs/2603.13585) | 2026/03/13 | ICRA26 实时声-光融合，浊度 0.5–12 NTU | II-B | 有（8 个 .tex） |
| Towards Realistic 3D Sonar Simulation | [2606.06130](https://arxiv.org/abs/2606.06130) | 2026/06/04 | 3D 声呐仿真与真实港区对标，量化 sim-to-real gap | V | 有（2 个 .tex） |
| M^2C-EvDet: Multi-Domain Multi-Order Cross-Modal Knowledge Distillation for Event-based Object Detection | [2606.24248](https://arxiv.org/abs/2606.24248) | 2026/06/23 | multi-order cross-modal KD for event detection | II-C→跨模态 | 有（1 个 .tex） |
| A Comparison of Data Augmentation Methods for Training Deep Neural Networks on Synthetic Aperture Sonar | [2607.23770](https://arxiv.org/abs/2607.23770) | 2026/07/26 | SAS 数据增强系统比较，避免「加增强就涨点」 | II-A | 无（作者只投 PDF） |
| Geometry-Driven Opti-Acoustic Co-Registration and View-Invariant Reflectivity Mapping for Side-Scan Sonar | [2608.23479](https://arxiv.org/abs/2608.23479) | 2026/08/24 | 几何驱动声-光共配准（侧扫）：跨模态几何对齐的另一实现路径（原目录已有 PDF，补 LaTeX） | II-B | 有（1 个 .tex） |
| UAV Thermal Imagery for Inert Ordnance Screening: Multi Campaign Dataset Development,Object Detection, and Practical Recommendations | [2609.01738](https://arxiv.org/abs/2609.01738) | 2026/09/01 | inert ordnance detection from aerial imagery | II-A | 无（作者只投 PDF） |
| When Depth Hurts: Reliability-Aware Geometry Distillation for Depth-Free RGB-D Salient Object Detection | [2609.03378](https://arxiv.org/abs/2609.03378) | 2026/09/03 | 「辅助模态可能有害」+ 逐像素可靠性门控只注入与当前表示兼容的知识，教师训后即移除——若审稿人质疑光学教师对声呐的负迁移，这是最贴的方法论 | II-C | 有（1 个 .tex） |
| Cross-Modal Knowledge Distillation for Acoustic Pedestrian Detection | [2609.31785](https://arxiv.org/abs/2609.31785) | 2026/09/24 | 唯一的「弱模态（音频）学生」跨模态 KD 实测：video 教师→audio 学生，多数方法只让 macro acc 小涨、**PR-AUC 基本不动**，主要是工作点移动（no-pedestrian 准确率升、召回降）——审稿人最可能拿它质疑本文增益的性质 | II-C | 有（8 个 .tex） |
| Codebook-Guided Cross-Modal Knowledge Distillation for Structurally Heterogeneous Features | [2609.37243](https://arxiv.org/abs/2609.37243) | 2026/09/29 | 指出特征级对齐的前提是师生表示空间**结构可对齐**，2D 网格 vs 1D 时序时不成立，改用码本做概念级锚点——本文师生同架构恰好满足该前提，可用来正当化设计选择 | II-C | 有（28 个 .tex） |

## 等级 C：背景或对照，可择要引用（23 篇）

| 标题 | arXiv | 日期 | 相关性（我方判断） | 对应章节 | LaTeX |
|---|---|---|---|---|---|
| Objectness Scoring and Detection Proposals in Forward-Looking Sonar Images with Convolutional Neural Networks | [1709.02600](https://arxiv.org/abs/1709.02600) | 2017/09/08 | early FLS detection proposals | II-A | 有（1 个 .tex） |
| Rotation-invariant shipwreck recognition with forward-looking sonar | [1910.05374](https://arxiv.org/abs/1910.05374) | 2019/10/11 | FLS recognition, rotation invariance | II-A | 有（1 个 .tex） |
| External-Memory Networks for Low-Shot Learning of Targets in Forward-Looking-Sonar Imagery | [2107.10504](https://arxiv.org/abs/2107.10504) | 2021/07/22 | low-shot target learning in FLS imagery | II-A | 有（1 个 .tex） |
| Pre-trained Models for Sonar Images | [2108.01111](https://arxiv.org/abs/2108.01111) | 2021/08/02 | 每类 10–30 样本即迁移，跨 Gemini 720i 验证 | II-A | 有（1 个 .tex） |
| Learning an Augmented RGB Representation with Cross-Modal Knowledge Distillation for Action Detection | [2108.03619](https://arxiv.org/abs/2108.03619) | 2021/08/08 | augmented RGB via cross-modal KD (modality substitution) | II-C→跨模态 | 无（作者只投 PDF） |
| The Marine Debris Dataset for Forward-Looking Sonar Semantic Segmentation | [2108.06800](https://arxiv.org/abs/2108.06800) | 2021/08/15 | FLS semantic segmentation dataset | II-A | 有（1 个 .tex） |
| DETRDistill: A Universal Knowledge Distillation Framework for DETR-families | [2211.10156](https://arxiv.org/abs/2211.10156) | 2022/11/17 | DETR 系专用（匈牙利匹配 logits + target-aware 特征），与 YOLOX 架构无关，仅作 KD 组件设计参照 | II-C | 有（17 个 .tex） |
| Advances in Self-Supervised Learning for Synthetic Aperture Sonar Data Processing, Classification, and Pattern Recognition | [2308.11633](https://arxiv.org/abs/2308.11633) | 2023/08/12 | self-supervised learning on SAS data | II-A | 有（1 个 .tex） |
| DMKD: Improving Feature-based Knowledge Distillation for Object Detection Via Dual Masking Augmentation | [2309.02719](https://arxiv.org/abs/2309.02719) | 2023/09/06 | 空间 + 通道双掩码重建 + 自适应融合权重（+4.1%/+4.3%）——掩码式特征蒸馏的备选实现 | II-C | 有（6 个 .tex） |
| Contrastive Learning-Based Spectral Knowledge Distillation for Multi-Modality and Missing Modality Scenarios in Semantic Segmentation | [2312.02240](https://arxiv.org/abs/2312.02240) | 2023/12/04 | spectral KD with missing modality | III/IV | 有（7 个 .tex） |
| RadOcc: Learning Cross-Modality Occupancy Knowledge through Rendering Assisted Distillation | [2312.11829](https://arxiv.org/abs/2312.11829) | 2023/12/19 | cross-modality occupancy KD via rendering | II-C→跨模态 | 有（1 个 .tex） |
| Performance Assessment of Feature Detection Methods for 2-D FS Sonar Imagery | [2409.07004](https://arxiv.org/abs/2409.07004) | 2024/09/11 | RGB 特征检测器不适配声呐斑点噪声 | II-A | 有（7 个 .tex） |
| Exploring the Feasibility of Affordable Sonar Technology: Object Detection in Underwater Environments Using the Ping 360 | [2411.05863](https://arxiv.org/abs/2411.05863) | 2024/11/07 | low-cost sonar object detection | II-A | 有（1 个 .tex） |
| A Hierarchical Semantic Distillation Framework for Open-Vocabulary Object Detection | [2503.10152](https://arxiv.org/abs/2503.10152) | 2025/03/13 | instance / class / image 三级语义蒸馏（OV-COCO novel AP 46.4%）——为「object-level 之外是否还要类别级监督」提供分层模板 | II-C | 有（1 个 .tex） |
| MST-Distill: Mixture of Specialized Teachers for Cross-Modal Knowledge Distillation | [2507.07015](https://arxiv.org/abs/2507.07015) | 2025/07/09 | mixture of specialized teachers, cross-modal KD | III/IV | 有（1 个 .tex） |
| Self-Supervised Compression and Artifact Correction for Streaming Underwater Imaging Sonar | [2511.13922](https://arxiv.org/abs/2511.13922) | 2025/11/17 | 斑点/混响/声影影响多达 98% 声呐帧 | II-A | 有（2 个 .tex） |
| CCSD: Cross-Modal Compositional Self-Distillation for Robust Brain Tumor Segmentation with Missing Modalities | [2511.14599](https://arxiv.org/abs/2511.14599) | 2025/11/18 | compositional self-distillation, missing modalities | III/IV | 有（1 个 .tex） |
| KD360-VoxelBEV: LiDAR and 360-degree Camera Cross Modality Knowledge Distillation for Bird&#39;s-Eye-View Segmentation | [2512.15311](https://arxiv.org/abs/2512.15311) | 2025/12/17 | LiDAR-camera cross-modality KD, BEV | II-C→跨模态 | 有（9 个 .tex） |
| Selective Transfer Learning of Cross-Modality Distillation for Monocular 3D Object Detection | [2603.07464](https://arxiv.org/abs/2603.07464) | 2026/03/08 | selective cross-modality distillation, monocular 3D | II-C→跨模态 | 有（1 个 .tex） |
| Hyperbolic Distillation: Geometry-Guided Cross-Modal Transfer for Robust 3D Object Detection | [2605.09899](https://arxiv.org/abs/2605.09899) | 2026/05/11 | geometry-guided cross-modal transfer, 3D detection | II-C→跨模态 | 有（1 个 .tex） |
| xModel-KD: Cross-modal Knowledge Distillation for 3D Scene Perception using LiDAR | [2605.30111](https://arxiv.org/abs/2605.30111) | 2026/05/28 | cross-modal KD for 3D scene perception | II-C→跨模态 | 有（1 个 .tex） |
| Semantically Compatible Knowledge Distillation for Cross-Domain Object Detection with Vision Foundation Models | [2608.20916](https://arxiv.org/abs/2608.20916) | 2026/08/21 | 处理 DINOv2 教师与学生特征图**尺度不匹配导致语义不兼容**的适配器方案——若将来换大模型教师才会用到 | II-C | 有（1 个 .tex） |
| EvoOPD: Evolving Privileged Information Strategies for Black-Box On-Policy Distillation | [2611.06542](https://arxiv.org/abs/2611.06542) | 2026/11/04 | privileged information distillation strategies | III/IV | 有（22 个 .tex） |

## 按 CMOLD 章节归位

### 声呐图像的水下目标检测（CMOLD §II-A）（28 篇）

- **Syn2Real Domain Generalization for Underwater Mine-like Object Detection Using Side-Scan Sonar**（arXiv:2410.12953，2024/10/16）——unexploded mine-like objects, side-scan, domain generalization
- **Sonar-based Deep Learning in Underwater Robotics: Overview, Robustness and Challenges**（arXiv:2412.11840，2024/12/16）——声呐深度学习综述：数据有限+固有噪声为本领域瓶颈
- **Mine-JEPA: In-Domain Self-Supervised Learning for Mine-Like Object Classification in Side-Scan Sonar**（arXiv:2604.00383，2026/04/01）——SSS 域内自监督，仅 1170 张无标注图；支撑声呐域内预训练
- **SonarVoxNet: Diver Detection in 3D Bounding Box using 3D Sonar**（arXiv:2610.01644，2026/10/01）——SonarVoxNet：3D 声呐里的 3D bbox + 全身朝向（原只读 literature 已有 PDF，此处补 LaTeX）
- **What&#39;s Mine is Yours: Pretrained CNNs for Limited Training Sonar ATR**（arXiv:1706.09858，2017/06/29）——最早的「声呐样本少→借预训练 CNN」路线
- **Learning Objectness from Sonar Images for Class-Independent Object Detection**（arXiv:1907.00734，2019/07/01）——class-independent sonar object detection
- **A rasterized ray-tracer pipeline for real-time, multi-device sonar simulation**（arXiv:2001.03539，2020/01/08）——光栅+光线追踪声呐仿真：3D 场景→声呐图的正向管线，可验证投影框可见性
- **Target Detection and Segmentation in Circular-Scan Synthetic-Aperture-Sonar Images using Semi-Supervised Convolutional Encoder-Decoders**（arXiv:2101.03603，2021/01/10）——半监督 CSAS 检测/分割；自然图像模型需改造
- **Minimax Robust Landmine Detection Using Forward-Looking Ground-Penetrating Radar**（arXiv:2111.08379，2021/11/16）——UXO/landmine detection, non-optical sensor
- **Learning Pseudo Front Depth for 2D Forward-Looking Sonar-based Multi-view Stereo**（arXiv:2208.00233，2022/07/30）——FLS 单图 3D 病态性 + 伪前视深度/多视图立体：缺仰角为何使 3D 框投出区域
- **A Dataset with Multibeam Forward-Looking Sonar for Underwater Object Detection**（arXiv:2212.00352，2022/12/01）——forward-looking sonar detection dataset (ARIS-adjacent)
- **Motion Degeneracy in Self-supervised Learning of Elevation Angle Estimation for 2D Forward-Looking Sonar**（arXiv:2307.16160，2023/07/30）——FLS 仰角自监督估计与运动退化：单帧仰角不可解的实证
- **STARS: Zero-shot Sim-to-Real Transfer for Segmentation of Shipwrecks in Sonar Imagery**（arXiv:2310.01667，2023/10/02）——纯仿真训练零样本 sim-to-real 分割，+20%
- **Terrain characterisation for online adaptability of automated sonar processing: Lessons learnt from operationally applying ATR to sidescan sonar in MCM applications**（arXiv:2404.18663，2024/04/29）——ATR 在非良性海底迅速退化；域差来自环境
- **ROSAR: An Adversarial Re-Training Framework for Robust Side-Scan Sonar Object Detection**（arXiv:2410.10554，2024/10/14）——side-scan sonar detector robustness
- **OceanSim: A GPU-Accelerated Underwater Robot Perception Simulation Framework**（arXiv:2503.01074，2025/03/03）——OceanSim：GPU 水下仿真 + 实时成像声呐渲染（含代码），合成台
- **Sonar Image Datasets: A Comprehensive Survey of Resources, Challenges, and Applications**（arXiv:2510.03353，2025/10/02）——声呐数据集综述，数据稀缺最省事的引证
- **A Comparison of Data Augmentation Methods for Training Deep Neural Networks on Synthetic Aperture Sonar**（arXiv:2607.23770，2026/07/26）——SAS 数据增强系统比较，避免「加增强就涨点」
- **UAV Thermal Imagery for Inert Ordnance Screening: Multi Campaign Dataset Development,Object Detection, and Practical Recommendations**（arXiv:2609.01738，2026/09/01）——inert ordnance detection from aerial imagery
- **Objectness Scoring and Detection Proposals in Forward-Looking Sonar Images with Convolutional Neural Networks**（arXiv:1709.02600，2017/09/08）——early FLS detection proposals
- **Rotation-invariant shipwreck recognition with forward-looking sonar**（arXiv:1910.05374，2019/10/11）——FLS recognition, rotation invariance
- **External-Memory Networks for Low-Shot Learning of Targets in Forward-Looking-Sonar Imagery**（arXiv:2107.10504，2021/07/22）——low-shot target learning in FLS imagery
- **Pre-trained Models for Sonar Images**（arXiv:2108.01111，2021/08/02）——每类 10–30 样本即迁移，跨 Gemini 720i 验证
- **The Marine Debris Dataset for Forward-Looking Sonar Semantic Segmentation**（arXiv:2108.06800，2021/08/15）——FLS semantic segmentation dataset
- **Advances in Self-Supervised Learning for Synthetic Aperture Sonar Data Processing, Classification, and Pattern Recognition**（arXiv:2308.11633，2023/08/12）——self-supervised learning on SAS data
- **Performance Assessment of Feature Detection Methods for 2-D FS Sonar Imagery**（arXiv:2409.07004，2024/09/11）——RGB 特征检测器不适配声呐斑点噪声
- **Exploring the Feasibility of Affordable Sonar Technology: Object Detection in Underwater Environments Using the Ping 360**（arXiv:2411.05863，2024/11/07）——low-cost sonar object detection
- **Self-Supervised Compression and Artifact Correction for Streaming Underwater Imaging Sonar**（arXiv:2511.13922，2025/11/17）——斑点/混响/声影影响多达 98% 声呐帧

### 相机–声呐融合（CMOLD §II-B）（7 篇）

- **Underwater object classification combining SAS and transferred optical-to-SAS Imagery**（arXiv:2304.11875，2023/04/24）——7052 对光学/SAS 影像迁移，光学→声学监督迁移直接先例
- **RGB-Sonar Tracking Benchmark and Spatial Cross-Attention Transformer Tracker**（arXiv:2406.07189，2024/06/11）——RGB–声呐配对跟踪基准 + 造伪配对的 SRST
- **Can Optical Denoising Clean Sonar Images? A Benchmark and Fusion Approach**（arXiv:2503.01655，2025/03/03）——9 个光学去噪器迁声呐 × 4 检测器含 YOLOX；光学→声呐可行性前提
- **Underwater Camouflage Object Detection Dataset**（arXiv:2303.12946，2023/03/01）——UW-R/UW-S 成对光学与声呐标注集，量化配对稀缺
- **AONeuS: A Neural Rendering Framework for Acoustic-Optical Sensor Fusion**（arXiv:2402.03309，2024/02/05）——AONeuS：声-光联合神经表面重建，把光学几何与声学观测对齐
- **Sonar-MASt3R: Real-Time Opti-Acoustic Fusion in Turbid, Unstructured Environments**（arXiv:2603.13585，2026/03/13）——ICRA26 实时声-光融合，浊度 0.5–12 NTU
- **Geometry-Driven Opti-Acoustic Co-Registration and View-Invariant Reflectivity Mapping for Side-Scan Sonar**（arXiv:2608.23479，2026/08/24）——几何驱动声-光共配准（侧扫）：跨模态几何对齐的另一实现路径（原目录已有 PDF，补 LaTeX）

### 水下目标检测中的知识蒸馏（CMOLD §II-C）（34 篇）

- **Localization Distillation for Dense Object Detection**（arXiv:2102.12252，2021/02/24）——在 dense detector（GFocal，与 YOLOX 同族）上证明**定位知识比语义知识更值得蒸**，logit 模仿可胜特征模仿（40.1→42.1 AP）
- **G-DetKD: Towards General Distillation Framework for Object Detectors via Contrastive and Semantic-guided Feature Imitation**（arXiv:2108.07482，2021/08/17）——首个同时覆盖**同构与异构**师生对的通用检测蒸馏（跨 FPN 软匹配 + 对比关系蒸馏）；用它可以正当化本文「共享 YOLOX 架构」的选择，并说明异构情形已被覆盖
- **Focal and Global Knowledge Distillation for Detectors**（arXiv:2111.11837，2021/11/23）——证明**等权蒸馏有害**、须按前景/背景分离并重建像素间关系（RetinaNet/FasterRCNN/RepPoints/MaskRCNN +2.9–3.6 mAP）——本文只蒸目标区域的直接依据
- **Object-centric Cross-modal Feature Distillation for Event-based Object Detection**（arXiv:2311.05494，2023/11/09）——把「object-level」做成**显式模块**：slot attention 把特征图解耦为物体级 + 像素级再蒸馏，几乎把与教师的差距减半——直接支撑本文 object-level KD 的命名与设计
- **RadarDistill: Boosting Radar-based Object Detection Performance via Knowledge Distillation from LiDAR Features**（arXiv:2403.05061，2024/03/08）——跨模态**特征级**蒸馏的标准配方（跨模态对齐 + 激活阈值过滤 + proposal 内蒸馏），radar-only 20.5 mAP / 43.7 NDS——本文方法对照与超参依据
- **Knowledge Distillation in YOLOX-ViT for Side-Scan Sonar Object Detection**（arXiv:2403.09313，2024/03/14）——sonar+YOLOX+KD, closest single precedent
- **DOD-SA: Infrared-Visible Decoupled Object Detection with Single-Modality Annotations**（arXiv:2508.10445，2025/08/14）——与本文最同构：**只有一侧模态有标注**，靠跨模态知识迁移 + 三阶段自训练 + 伪标签分配器把标注能力搬到无标注模态——直接对应学生侧「少量人工标注 + 伪标签」
- **Enhancing Object Detection with Privileged Information: A Model-Agnostic Teacher-Student Approach**（arXiv:2601.02016，2026/01/05）——把 **LUPI 正式引入检测**：特权信息（bbox mask / saliency / depth）仅训练期可用、推理零成本，5 个检测器一致超基线——本文「教师见强模态、学生只见弱模态」的理论框架
- **Physically Motivated Knowledge Distillation for Blind Geometric Correction of Side-Scan Sonar Imagery**（arXiv:2603.15200，2026/03/16）——KD used to correct side-scan imagery geometry
- **CTFS : Collaborative Teacher Framework for Forward-Looking Sonar Image Semantic Segmentation with Extremely Limited Labels**（arXiv:2603.21071，2026/03/22）——前视声呐教师-学生分割，2% 标注；同期最接近的师生框架
- **Thermal-Det: Language-Guided Cross-Modal Distillation for Open-Vocabulary Thermal Object Detection**（arXiv:2605.10130，2026/05/11）——冻结 RGB 教师对**成对但无标注**的 thermal 数据提供几何+语义伪监督，无人工标注迁移开放词汇知识（+2–4 AP）——「强模态全标注、弱模态零标注」的最新范式
- **Aligned Consensus Teaching for Label-Efficient Oriented Object Detection in Weakly-Aligned Visible-Infrared Imagery**（arXiv:2609.18124，2026/09/16）——少数成对样本有标注、其余全无标注的半监督可见光-红外检测；共识伪标签 + 循环一致区域对齐 + 尾类实例增广，正是「学生侧标注稀缺」的解法与评测口径
- **Distilling Object Detectors with Fine-grained Feature Imitation**（arXiv:1906.03609，2019/06/09）——object-level 蒸馏的源头：只在**近目标 anchor 位置**模仿（KITTI 上 +15% mAP）——本文「只蒸目标区域」的历史依据
- **Online Sensor Hallucination via Knowledge Distillation for Multimodal Image Classification**（arXiv:1908.10559，2019/08/28）——最早把「训练时全传感器可用、测试时缺模态」+ KD + privileged 讲清的一篇（分类任务，PAN-MS 评测）——缺模态蒸馏的思想源头
- **MimicDet: Bridging the Gap Between One-Stage and Two-Stage Object Detection**（arXiv:2009.11528，2020/09/24）——一阶段/两阶段异构结构蒸馏源头篇（共享 backbone 双 head 使特征兼容，COCO 46.1 mAP）——回答「师生结构不完全一致时怎么蒸」
- **Knowledge Distillation for Object Detection via Rank Mimicking and Prediction-guided Feature Imitation**（arXiv:2112.04840，2021/12/09）——一阶段检测器专用：师生对候选框**排序不同**导致精度差，蒸排序优于蒸软标签——对本文伪标签筛选与置信度校准可直接复用
- **Beyond Bounding Box: Multimodal Knowledge Learning for Object Detection**（arXiv:2205.04072，2022/05/09）——显式区分 **image-level 与 object-level 跨模态互信息**蒸馏（+1.6–2.1%），是本文 object-level 措辞最贴的较早文献
- **X$^3$KD: Knowledge Distillation Across Modalities, Tasks and Stages for Multi-Camera 3D Object Detection**（arXiv:2303.02203，2023/03/03）——跨任务（实例分割教师）+ 跨模态特征 + 对抗 + 跨模态**输出**蒸馏组合，并给出 RADAR-based 3DOD 的泛化证据——可支撑「输出级 + 特征级并用」的设计
- **MMANet: Margin-aware Distillation and Modality-aware Regularization for Incomplete Multimodal Learning**（arXiv:2304.08028，2023/04/17）——按分类不确定性加权蒸馏 + 专治「弱模态组合」的正则——对应本文学生模态信息量显著低于教师的场景
- **A Generalization Theory of Cross-Modality Distillation with Contrastive Learning**（arXiv:2405.03355，2024/05/06）——给出跨模态 distilled 模型的泛化界：**源/目标模态距离**直接影响下游测试误差——为「光学→声呐 gap 大但仍可蒸」提供理论表述与限制条件
- **Incomplete Multimodal Industrial Anomaly Detection via Cross-Modal Distillation**（arXiv:2405.13571，2024/05/22）——训练时多模态、**推理时可缺模态**的跨模态蒸馏——支撑「部署只有声呐」这一前提的合理性
- **LEROjD: Lidar Extended Radar-Only Object Detection**（arXiv:2409.05564，2024/09/09）——在 Lidar→radar-only 上量化「跨模态 KD 最多 +3.9 mAP，不如多阶段 thin-out 的 +4.2」——提示本文必须把增益拆成 KD 项与初始化/伪标签项
- **Learn from Foundation Model: Fruit Detection Model without Manual Annotation**（arXiv:2411.16196，2024/11/25）——强模型（SAM2+OpenCLIP）生成框→蒸馏到边缘小检测器，**完全无人工标注**即接近全监督——对应本文学生侧用伪标签替代人工标注的路线
- **SAMKD: Spatial-aware Adaptive Masking Knowledge Distillation for Object Detection**（arXiv:2501.07101，2025/01/13）——空间分层掩码（粗到细编码 object-aware locality）+ 掩码 logit 蒸馏，35.3→38.8 mAP——「目标感知掩码」路线较新的一篇
- **IMKD: Intensity-Aware Multi-Level Knowledge Distillation for Camera-Radar Fusion**（arXiv:2512.15581，2025/12/17）——强度感知的多层级蒸馏，67.0 NDS / 61.0 mAP；来自 **DFKI-AV（与 CMOLD 的 DFKI UXO 数据集同机构）**，是同机构后续工作最该引的一篇
- **Scalpel-SAM: A Semi-Supervised Paradigm for Adapting SAM to Infrared Small Object Detection**（arXiv:2512.22483，2025/12/27）——10% 标注把 SAM 蒸成专家教师 → 再用其伪标签训轻量下游模型，效果可比甚至超全监督——「少标注 + 伪标签 + 蒸馏」三段式的现成模板
- **PEPR: Privileged Event-based Predictive Regularization for Domain Generalization**（arXiv:2602.04583，2026/02/04）——LUPI 新范式：**不做直接特征对齐**，改为在共享隐空间预测特权模态潜特征，赢过对齐式基线——若声呐/光学特征空间不可直接对齐，这是可选的替代损失
- **When Depth Hurts: Reliability-Aware Geometry Distillation for Depth-Free RGB-D Salient Object Detection**（arXiv:2609.03378，2026/09/03）——「辅助模态可能有害」+ 逐像素可靠性门控只注入与当前表示兼容的知识，教师训后即移除——若审稿人质疑光学教师对声呐的负迁移，这是最贴的方法论
- **Cross-Modal Knowledge Distillation for Acoustic Pedestrian Detection**（arXiv:2609.31785，2026/09/24）——唯一的「弱模态（音频）学生」跨模态 KD 实测：video 教师→audio 学生，多数方法只让 macro acc 小涨、**PR-AUC 基本不动**，主要是工作点移动（no-pedestrian 准确率升、召回降）——审稿人最可能拿它质疑本文增益的性质
- **Codebook-Guided Cross-Modal Knowledge Distillation for Structurally Heterogeneous Features**（arXiv:2609.37243，2026/09/29）——指出特征级对齐的前提是师生表示空间**结构可对齐**，2D 网格 vs 1D 时序时不成立，改用码本做概念级锚点——本文师生同架构恰好满足该前提，可用来正当化设计选择
- **DETRDistill: A Universal Knowledge Distillation Framework for DETR-families**（arXiv:2211.10156，2022/11/17）——DETR 系专用（匈牙利匹配 logits + target-aware 特征），与 YOLOX 架构无关，仅作 KD 组件设计参照
- **DMKD: Improving Feature-based Knowledge Distillation for Object Detection Via Dual Masking Augmentation**（arXiv:2309.02719，2023/09/06）——空间 + 通道双掩码重建 + 自适应融合权重（+4.1%/+4.3%）——掩码式特征蒸馏的备选实现
- **A Hierarchical Semantic Distillation Framework for Open-Vocabulary Object Detection**（arXiv:2503.10152，2025/03/13）——instance / class / image 三级语义蒸馏（OV-COCO novel AP 46.4%）——为「object-level 之外是否还要类别级监督」提供分层模板
- **Semantically Compatible Knowledge Distillation for Cross-Domain Object Detection with Vision Foundation Models**（arXiv:2608.20916，2026/08/21）——处理 DINOv2 教师与学生特征图**尺度不匹配导致语义不兼容**的适配器方案——若将来换大模型教师才会用到

### 跨模态知识蒸馏用于目标检测（CMOLD §II-C 之外，属新增长轴）（15 篇）

- **UniDistill: A Universal Cross-Modality Knowledge Distillation Framework for 3D Object Detection in Bird&#39;s-Eye View**（arXiv:2303.15083，2023/03/27）——universal cross-modality KD for 3D detection
- **FreqKD: Frequency-Decoupled Cross-Modal Knowledge Distillation for Infrared Object Detection**（arXiv:2606.11572，2026/06/10）——RGB->IR cross-modal KD for object detection (closest modality gap analogue)
- **Cross-Modality Knowledge Distillation Network for Monocular 3D Object Detection**（arXiv:2211.07171，2022/11/14）——cross-modality KD, monocular 3D
- **CMDFusion: Bidirectional Fusion Network with Cross-modality Knowledge Distillation for LIDAR Semantic Segmentation**（arXiv:2307.04091，2023/07/09）——bidirectional fusion + cross-modality KD
- **LabelDistill: Label-guided Cross-modal Knowledge Distillation for Camera-based 3D Object Detection**（arXiv:2407.10164，2024/07/14）——label-guided cross-modal KD, camera-based detector
- **SCKD: Semi-Supervised Cross-Modality Knowledge Distillation for 4D Radar Object Detection**（arXiv:2412.14571，2024/12/19）——semi-supervised cross-modality KD, radar
- **CleverDistiller: Simple and Spatially Consistent Cross-modal Distillation**（arXiv:2503.09878，2025/03/12）——simple spatially-consistent cross-modal distillation
- **RCTDistill: Cross-Modal Knowledge Distillation Framework for Radar-Camera 3D Object Detection with Temporal Fusion**（arXiv:2509.17712，2025/09/22）——cross-modal KD radar-camera with temporal fusion
- **M^2C-EvDet: Multi-Domain Multi-Order Cross-Modal Knowledge Distillation for Event-based Object Detection**（arXiv:2606.24248，2026/06/23）——multi-order cross-modal KD for event detection
- **Learning an Augmented RGB Representation with Cross-Modal Knowledge Distillation for Action Detection**（arXiv:2108.03619，2021/08/08）——augmented RGB via cross-modal KD (modality substitution)
- **RadOcc: Learning Cross-Modality Occupancy Knowledge through Rendering Assisted Distillation**（arXiv:2312.11829，2023/12/19）——cross-modality occupancy KD via rendering
- **KD360-VoxelBEV: LiDAR and 360-degree Camera Cross Modality Knowledge Distillation for Bird&#39;s-Eye-View Segmentation**（arXiv:2512.15311，2025/12/17）——LiDAR-camera cross-modality KD, BEV
- **Selective Transfer Learning of Cross-Modality Distillation for Monocular 3D Object Detection**（arXiv:2603.07464，2026/03/08）——selective cross-modality distillation, monocular 3D
- **Hyperbolic Distillation: Geometry-Guided Cross-Modal Transfer for Robust 3D Object Detection**（arXiv:2605.09899，2026/05/11）——geometry-guided cross-modal transfer, 3D detection
- **xModel-KD: Cross-modal Knowledge Distillation for 3D Scene Perception using LiDAR**（arXiv:2605.30111，2026/05/28）——cross-modal KD for 3D scene perception

### 缺失模态、特权信息与无配对蒸馏（CMOLD §III/§IV 的方法学支撑）（14 篇）

- **Learnable Cross-modal Knowledge Distillation for Multi-modal Learning with Missing Modality**（arXiv:2310.01035，2023/10/02）——cross-modal KD when a modality is missing at test time
- **BESTAnP: Bi-Step Efficient and Statistically Optimal Estimator for Acoustic-n-Point Problem**（arXiv:2411.17521，2024/11/26）——BESTAnP：acoustic-n-point 解耦平移(range)与旋转(azimuth)，FLS 投影/位姿的标准解法
- **Rejecting Outliers in 2D-3D Point Correspondences from 2D Forward-Looking Sonar Observations**（arXiv:2503.16066，2025/03/20）——2D FLS 的 2D-3D 对应外点剔除（90% 外点率），真实数据上 3D→声呐对应的可靠性边界
- **A Convex and Global Solution for the P$n$P Problem in 2D Forward-Looking Sonar**（arXiv:2504.04445，2025/04/06）——2D FLS 的 PnP：point-to-line 3D 配准 + 正交近似，把 3D 点投到 FLS 的正向模型与全局最优解——投影框的几何底座
- **Feature Geometry for Stereo Sidescan and Forward-looking Sonar**（arXiv:2507.05410，2025/07/07）——唯一显式做「把一侧声呐看到的特征投到另一侧声呐」的几何方法（FLS↔侧扫，仿极线几何）
- **Cross-Modal Knowledge Distillation without Paired Data: Theoretical Foundation and Algorithm**（arXiv:2606.10504，2026/06/09）——cross-modal KD without paired data (theory+algorithm)
- **A Comparison of Few-Shot Learning Methods for Underwater Optical and Sonar Image Classification**（arXiv:2005.04621，2020/05/10）——水光与侧扫声呐 few-shot 对比，FSL 优于微调
- **Non-target Divergence Hypothesis: Toward Understanding Domain Gaps in Cross-Modal Knowledge Distillation**（arXiv:2409.02438，2024/09/04）——analysis of domain gaps in cross-modal KD
- **Cross-Modal Distillation For Widely Differing Modalities**（arXiv:2507.16296，2025/07/22）——cross-modal distillation across very different modalities
- **Asymmetric Cross-Modal Knowledge Distillation: Bridging Modalities with Weak Semantic Consistency**（arXiv:2511.08901，2025/11/12）——asymmetric cross-modal KD with weak semantic consistency
- **Contrastive Learning-Based Spectral Knowledge Distillation for Multi-Modality and Missing Modality Scenarios in Semantic Segmentation**（arXiv:2312.02240，2023/12/04）——spectral KD with missing modality
- **MST-Distill: Mixture of Specialized Teachers for Cross-Modal Knowledge Distillation**（arXiv:2507.07015，2025/07/09）——mixture of specialized teachers, cross-modal KD
- **CCSD: Cross-Modal Compositional Self-Distillation for Robust Brain Tumor Segmentation with Missing Modalities**（arXiv:2511.14599，2025/11/18）——compositional self-distillation, missing modalities
- **EvoOPD: Evolving Privileged Information Strategies for Black-Box On-Policy Distillation**（arXiv:2611.06542，2026/11/04）——privileged information distillation strategies

### 讨论与未来工作（声呐图像合成/翻译）（4 篇）

- **Synth-SONAR: Sonar Image Synthesis with Enhanced Diversity and Realism via Dual Diffusion Models and GPT Prompting**（arXiv:2410.08612，2024/10/11）——双扩散+GPT 合成声呐图像，替代方案的最近邻
- **Development of a Simulation Environment for Evaluation of a Forward Looking Sonar System for Small AUVs**（arXiv:2210.06535，2022/10/12）——光线追踪高保真 FLS 仿真环境（OCEANS 2019）
- **SonarSplat: Novel View Synthesis of Imaging Sonar via Gaussian Splatting**（arXiv:2504.00159，2025/03/31）——高斯泼溅渲染声呐图，可微渲染工具
- **Towards Realistic 3D Sonar Simulation**（arXiv:2606.06130，2026/06/04）——3D 声呐仿真与真实港区对标，量化 sim-to-real gap


## 获取记录

| arXiv | PDF | 源包 | 说明 |
|---|---|---|---|
| 2102.12252 | 4343 KB | tar |  |
| 2108.07482 | 1894 KB | tar |  |
| 2111.11837 | 9958 KB | tar |  |
| 2303.15083 | 6167 KB | tar |  |
| 2304.11875 | 1966 KB | pdf | 作者只投 PDF，无 LaTeX |
| 2310.01035 | 1596 KB | tar |  |
| 2311.05494 | 3667 KB | tar |  |
| 2403.05061 | 5760 KB | tar |  |
| 2403.09313 | 1098 KB | tar |  |
| 2406.07189 | 8223 KB | tar |  |
| 2410.08612 | 3077 KB | tar |  |
| 2410.12953 | 3207 KB | tar |  |
| 2411.17521 | 3066 KB | tar |  |
| 2412.11840 | 1052 KB | tar |  |
| 2503.01655 | 3740 KB | tar |  |
| 2503.16066 | 1744 KB | tar |  |
| 2504.04445 | 1915 KB | tar |  |
| 2507.05410 | 6531 KB | tar |  |
| 2508.10445 | 9676 KB | tar |  |
| 2601.02016 | 13128 KB | tar |  |
| 2603.15200 | 16240 KB | tar |  |
| 2603.21071 | 3916 KB | tar |  |
| 2604.00383 | 1924 KB | tar |  |
| 2605.10130 | 2686 KB | tar |  |
| 2606.10504 | 649 KB | tar |  |
| 2606.11572 | 1159 KB | tar |  |
| 2609.18124 | 13426 KB | tar |  |
| 2610.01644 | 2032 KB | tar |  |
| 1706.09858 | 5167 KB | tar |  |
| 1906.03609 | 4165 KB | tar |  |
| 1907.00734 | 1824 KB | tar |  |
| 1908.10559 | 511 KB | tar |  |
| 2001.03539 | 3465 KB | tar |  |
| 2005.04621 | 1479 KB | tar |  |
| 2009.11528 | 4841 KB | tar |  |
| 2101.03603 | 36596 KB | tar |  |
| 2111.08379 | 3341 KB | tar |  |
| 2112.04840 | 3152 KB | tar |  |
| 2205.04072 | 3717 KB | tar |  |
| 2208.00233 | 2673 KB | tar |  |
| 2210.06535 | 1804 KB | tar |  |
| 2211.07171 | 8600 KB | tar |  |
| 2212.00352 | 3048 KB | tar |  |
| 2303.12946 | 1509 KB | tar |  |
| 2303.02203 | 8754 KB | tar |  |
| 2304.08028 | 3455 KB | tar |  |
| 2307.04091 | 5212 KB | tar |  |
| 2307.16160 | 1636 KB | tar |  |
| 2310.01667 | 3063 KB | tar |  |
| 2402.03309 | 9846 KB | tar |  |
| 2404.18663 | 5185 KB | pdf | 作者只投 PDF，无 LaTeX |
| 2405.03355 | 435 KB | tar |  |
| 2405.13571 | 3790 KB | pdf | 作者只投 PDF，无 LaTeX |
| 2407.10164 | 10221 KB | tar |  |
| 2409.02438 | 4604 KB | tar |  |
| 2409.05564 | 2050 KB | tar |  |
| 2410.10554 | 5821 KB | tar |  |
| 2411.16196 | 17334 KB | tar |  |
| 2412.14571 | 3300 KB | tar |  |
| 2501.07101 | 869 KB | tar |  |
| 2503.01074 | 5848 KB | tar |  |
| 2503.09878 | 7437 KB | tar |  |
| 2504.00159 | 4109 KB | tar |  |
| 2507.16296 | 1143 KB | tar |  |
| 2509.17712 | 12067 KB | tar |  |
| 2510.03353 | 3706 KB | tar |  |
| 2511.08901 | 3315 KB | tar |  |
| 2512.15581 | 11883 KB | tar |  |
| 2512.22483 | 804 KB | tar |  |
| 2602.04583 | 54058 KB | tar |  |
| 2603.13585 | 5140 KB | tar |  |
| 2606.06130 | 2015 KB | tar |  |
| 2606.24248 | 4685 KB | tar |  |
| 2607.23770 | 355 KB | pdf | 作者只投 PDF，无 LaTeX |
| 2608.23479 | 26653 KB | tar |  |
| 2609.01738 | 13325 KB | pdf | 作者只投 PDF，无 LaTeX |
| 2609.03378 | 1885 KB | tar |  |
| 2609.31785 | 322 KB | tar |  |
| 2609.37243 | 1113 KB | tar |  |
| 1709.02600 | 1130 KB | tar |  |
| 1910.05374 | 7237 KB | tar |  |
| 2107.10504 | 12027 KB | tar |  |
| 2108.01111 | 4686 KB | tar |  |
| 2108.03619 | 1814 KB | pdf | 作者只投 PDF，无 LaTeX |
| 2108.06800 | 6197 KB | tar |  |
| 2211.10156 | 7121 KB | tar |  |
| 2308.11633 | 539 KB | tar |  |
| 2309.02719 | 900 KB | tar |  |
| 2312.02240 | 4665 KB | tar |  |
| 2312.11829 | 9371 KB | tar |  |
| 2409.07004 | 2020 KB | tar |  |
| 2411.05863 | 6257 KB | tar |  |
| 2503.10152 | 4171 KB | tar |  |
| 2507.07015 | 3071 KB | tar |  |
| 2511.13922 | 3915 KB | tar |  |
| 2511.14599 | 3033 KB | tar |  |
| 2512.15311 | 18376 KB | tar |  |
| 2603.07464 | 5829 KB | tar |  |
| 2605.09899 | 7132 KB | tar |  |
| 2605.30111 | 3710 KB | tar |  |
| 2608.20916 | 2995 KB | tar |  |
| 2611.06542 | 1246 KB | tar |  |
