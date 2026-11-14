# 91 篇的代码可得性（核查于 2026-11-12）

> 核查口径：只看**作者在论文里给出的链接**（源包 `.tex/.bib` 里的 github/gitlab/huggingface/zenodo URL），
> 再逐个访问仓库判断「有代码 / 只有数据 / 只有 README」。模板仓（CVPR_Template、author-kit）与依赖仓
> （open-mmlab、ultralytics、Lightning-AI）不计。星标与体积为 2026-11-12 GitHub API 读数。

## 总览

| 状态 | 篇数 | 占 91 篇 |
|---|---|---|
| 有可运行代码 | **27** | 30% |
| 只放数据/权重、不放训练代码 | 4 | 4% |
| 宣称开源但仓库是空壳 | 3 | 3% |
| 未找到作者代码 | 57 | 63% |

**与本文直接相关（camera→sonar / object-level KD / YOLOX / UXO）且真能跑起来的只有 3 个**：
`remaro-network/KD-YOLOX-ViT`（2403.09313）、`pingggg516/CTFS`（2603.21071）、`wzyii/M2SDF`（2503.01655）。
其余有代码的多是 RGB-IR / LiDAR-camera / 单目 3D 场景：实现可借用，数据与协议不可比。

## 一、有可运行代码（27 篇）

| 等级 | arXiv | 标题 | 仓库 | 说明 |
|---|---|---|---|---|
| A | 2102.12252 | Localization Distillation for Dense Object Detection | [HikariTJU/LD](https://github.com/HikariTJU/LD) | 含 train.py/config，mmdet 系；定位蒸馏 |
| A | 2111.11837 | Focal and Global Knowledge Distillation for Detectors | [yzd-v/FGD](https://github.com/yzd-v/FGD) | 官方实现，细粒度/全局蒸馏，object-level 对照 |
| A | 2303.15083 | UniDistill: A Universal Cross-Modality Knowledge Distillation Framework for 3D Object Detection in Bird's-Eye View | [megvii-research/CVPR2023-UniDistill](https://github.com/megvii-research/CVPR2023-UniDistill) | 跨模态检测 KD 的标准实现 |
| A | 2403.05061 | RadarDistill: Boosting Radar-based Object Detection Performance via Knowledge Distillation from LiDAR Features | [geonhobang/RadarDistill](https://github.com/geonhobang/RadarDistill) | 仓库自述 [CVPR2024] Official；论文源包未给链接 |
| A | 2403.09313 | Knowledge Distillation in YOLOX-ViT for Side-Scan Sonar Object Detection | [remaro-network/KD-YOLOX-ViT](https://github.com/remaro-network/KD-YOLOX-ViT) | 声呐 + YOLOX + KD，与本课题最近的可跑代码 |
| A | 2406.07189 | RGB-Sonar Tracking Benchmark and Spatial Cross-Attention Transformer Tracker | [LiYunfengLYF/RGBS50](https://github.com/LiYunfengLYF/RGBS50) | RGB-声呐配对基准；训练代码在 LiYunfengLYF/SCANet |
| A | 2503.01655 | Can Optical Denoising Clean Sonar Images? A Benchmark and Fusion Approach | [wzyii/M2SDF](https://github.com/wzyii/M2SDF) | 9 种光学去噪器迁声呐 + 4 检测器（含 YOLOX） |
| A | 2508.10445 | DOD-SA: Infrared-Visible Decoupled Object Detection with Single-Modality Annotations | [Hang-J/DOD-SA](https://github.com/Hang-J/DOD-SA) | 单侧标注跨模态迁移 + 三阶段自训练 |
| A | 2601.02016 | Enhancing Object Detection with Privileged Information: A Model-Agnostic Teacher-Student Approach | [mbar0075/lupi-for-object-detection](https://github.com/mbar0075/lupi-for-object-detection) | LUPI 特权信息用于检测 |
| A | 2603.21071 | CTFS : Collaborative Teacher Framework for Forward-Looking Sonar Image Semantic Segmentation with Extremely Limited Labels | [pingggg516/CTFS](https://github.com/pingggg516/CTFS) | FLS 教师-学生 + 2% 标注；2026-11-06 仍在推 |
| A | 2606.10504 | Cross-Modal Knowledge Distillation without Paired Data: Theoretical Foundation and Algorithm | [anhducchu/UCMKD](https://github.com/anhducchu/UCMKD) | 原 Duckduck-05/UCMKD 已改名；含 kd_losses.py |
| B | 1906.03609 | Distilling Object Detectors with Fine-grained Feature Imitation | [twangnh/Distilling-Object-Detectors](https://github.com/twangnh/Distilling-Object-Detectors) | object-level 蒸馏源头（CVPR19） |
| B | 2211.07171 | Cross-Modality Knowledge Distillation Network for Monocular 3D Object Detection | [Cc-Hy/CMKD](https://github.com/Cc-Hy/CMKD) | 含 pcdet/，单目 3D 跨模态 KD |
| B | 2304.08028 | MMANet: Margin-aware Distillation and Modality-aware Regularization for Incomplete Multimodal Learning | [shicaiwei123/MMANet-CVPR2023](https://github.com/shicaiwei123/MMANet-CVPR2023) | 原 MMANet 仓已改名；含 classification/segmentation |
| B | 2307.04091 | CMDFusion: Bidirectional Fusion Network with Cross-modality Knowledge Distillation for LIDAR Semantic Segmentation | [Jun-CEN/CMDFusion](https://github.com/Jun-CEN/CMDFusion) | 含 main.py/network/，LiDAR-camera 融合 |
| B | 2407.10164 | LabelDistill: Label-guided Cross-modal Knowledge Distillation for Camera-based 3D Object Detection | [sanmin0312/LabelDistill](https://github.com/sanmin0312/LabelDistill) | 相机 3D 检测的标签蒸馏 |
| B | 2409.05564 | LEROjD: Lidar Extended Radar-Only Object Detection | [rst-tu-dortmund/lerojd](https://github.com/rst-tu-dortmund/lerojd) | LiDAR→Radar-only；跨模态 KD 反证案例 |
| B | 2410.10554 | ROSAR: An Adversarial Re-Training Framework for Robust Side-Scan Sonar Object Detection | [remaro-network/ROSAR-framework](https://github.com/remaro-network/ROSAR-framework) | SSS 鲁棒检测框架 |
| B | 2411.16196 | Learn from Foundation Model: Fruit Detection Model without Manual Annotation | [AgRoboticsResearch/SDM-D](https://github.com/AgRoboticsResearch/SDM-D) | 基础模型蒸馏到小检测器；含 SDM.py |
| B | 2512.15581 | IMKD: Intensity-Aware Multi-Level Knowledge Distillation for Camera-Radar Fusion | [dfki-av/IMKD](https://github.com/dfki-av/IMKD) | intensity-aware 多层 KD；DFKI 同机构 |
| B | 2606.06130 | Towards Realistic 3D Sonar Simulation | [GRAAL-Lab/IsaacSim_Underwater](https://github.com/GRAAL-Lab/IsaacSim_Underwater) | 3D 声呐仿真环境 |
| B | 2609.31785 | Cross-Modal Knowledge Distillation for Acoustic Pedestrian Detection | [yonghyunk1m/cmkd-ped-detect](https://github.com/yonghyunk1m/cmkd-ped-detect) | 声学行人跨模态 KD；含 PR-AUC 反证结论 |
| C | 2503.10152 | A Hierarchical Semantic Distillation Framework for Open-Vocabulary Object Detection | [iSEE-Laboratory/HD-OVD](https://github.com/iSEE-Laboratory/HD-OVD) | 开放词表检测的分层语义蒸馏 |
| C | 2507.07015 | MST-Distill: Mixture of Specialized Teachers for Cross-Modal Knowledge Distillation | [Gray-OREO/MST-Distill](https://github.com/Gray-OREO/MST-Distill) | 多教师混合蒸馏 |
| C | 2512.15311 | KD360-VoxelBEV: LiDAR and 360-degree Camera Cross Modality Knowledge Distillation for Bird's-Eye-View Segmentation | [Tom-E-Durham/KD360-VoxelBEV](https://github.com/Tom-E-Durham/KD360-VoxelBEV) | 含 train_distill.py |
| C | 2603.07464 | Selective Transfer Learning of Cross-Modality Distillation for Monocular 3D Object Detection | [DingCodeLab/MonoSTL](https://github.com/DingCodeLab/MonoSTL) | 选择性迁移 CMKD，单目 3D |
| C | 2608.20916 | Semantically Compatible Knowledge Distillation for Cross-Domain Object Detection with Vision Foundation Models | [hnu-vis/SLE-T](https://github.com/hnu-vis/SLE-T) | 跨域语义兼容蒸馏；含 adapteacher/dinoteacher |

## 二、只放数据/权重（4 篇）

| 等级 | arXiv | 标题 | 仓库 | 说明 |
|---|---|---|---|---|
| B | 1907.00734 | Learning Objectness from Sonar Images for Class-Independent Object Detection | [mvaldenegro/marine-debris-fls-datasets](https://github.com/mvaldenegro/marine-debris-fls-datasets) | FLS 数据集 + 预训练权重（mvaldenegro 系） |
| C | 2108.01111 | Pre-trained Models for Sonar Images | [mvaldenegro/pretrained-models-sonar-images](https://github.com/mvaldenegro/pretrained-models-sonar-images) | 声呐图像预训练模型权重 |
| C | 2108.06800 | The Marine Debris Dataset for Forward-Looking Sonar Semantic Segmentation | [mvaldenegro/marine-debris-fls-datasets](https://github.com/mvaldenegro/marine-debris-fls-datasets) | 海洋垃圾 FLS 分割数据集 |
| C | 2411.05863 | Exploring the Feasibility of Affordable Sonar Technology: Object Detection in Underwater Environments Using the Ping 360 | [junayed/Sonar-Scan-Dataset-with-Ping-360](https://github.com/junayed/Sonar-Scan-Dataset-with-Ping-360) | Ping360 廉价声呐扫描数据集 |

## 三、宣称开源但仓库里没有代码（3 篇）

| 等级 | arXiv | 标题 | 仓库 | 说明 |
|---|---|---|---|---|
| B | 2412.14571 | SCKD: Semi-Supervised Cross-Modality Knowledge Distillation for 4D Radar Object Detection | [Ruoyu-Xu/SCKD](https://github.com/Ruoyu-Xu/SCKD) | 仓里只有 README（17 字节「SCKD AAAI 2025」）/LICENSE/.gitignore，无代码 |
| B | 2511.08901 | Asymmetric Cross-Modal Knowledge Distillation: Bridging Modalities with Weak Semantic Consistency | [weirl-922/ACKD](https://github.com/weirl-922/ACKD) | 正文写「Code coming soon」，仓里只有 README.md |
| C | 2605.30111 | xModel-KD: Cross-modal Knowledge Distillation for 3D Scene Perception using LiDAR | [thenukan/xModel-KD](https://github.com/thenukan/xModel-KD) | 仓里只有 README.md，GitHub 报 size=0 |

## 四、未找到作者代码（57 篇）

这一组已逐篇 grep 源包：既没有仓库链接，正文也没有「code is available / released」类承诺。

| 等级 | arXiv | 标题 |
|---|---|---|
| A | 2108.07482 | G-DetKD: Towards General Distillation Framework for Object Detectors via Contrastive and Semantic-guided Feature Imitation |
| A | 2304.11875 | Underwater object classification combining SAS and transferred optical-to-SAS Imagery |
| A | 2310.01035 | Learnable Cross-modal Knowledge Distillation for Multi-modal Learning with Missing Modality |
| A | 2311.05494 | Object-centric Cross-modal Feature Distillation for Event-based Object Detection |
| A | 2410.08612 | Synth-SONAR: Sonar Image Synthesis with Enhanced Diversity and Realism via Dual Diffusion Models and GPT Prompting |
| A | 2410.12953 | Syn2Real Domain Generalization for Underwater Mine-like Object Detection Using Side-Scan Sonar |
| A | 2412.11840 | Sonar-based Deep Learning in Underwater Robotics: Overview, Robustness and Challenges |
| A | 2603.15200 | Physically Motivated Knowledge Distillation for Blind Geometric Correction of Side-Scan Sonar Imagery |
| A | 2604.00383 | Mine-JEPA: In-Domain Self-Supervised Learning for Mine-Like Object Classification in Side-Scan Sonar |
| A | 2605.10130 | Thermal-Det: Language-Guided Cross-Modal Distillation for Open-Vocabulary Thermal Object Detection |
| A | 2606.11572 | FreqKD: Frequency-Decoupled Cross-Modal Knowledge Distillation for Infrared Object Detection |
| A | 2609.18124 | Aligned Consensus Teaching for Label-Efficient Oriented Object Detection in Weakly-Aligned Visible-Infrared Imagery |
| B | 1706.09858 | What's Mine is Yours: Pretrained CNNs for Limited Training Sonar ATR |
| B | 1908.10559 | Online Sensor Hallucination via Knowledge Distillation for Multimodal Image Classification |
| B | 2005.04621 | A Comparison of Few-Shot Learning Methods for Underwater Optical and Sonar Image Classification |
| B | 2009.11528 | MimicDet: Bridging the Gap Between One-Stage and Two-Stage Object Detection |
| B | 2101.03603 | Target Detection and Segmentation in Circular-Scan Synthetic-Aperture-Sonar Images using Semi-Supervised Convolutional Encoder-Decoders |
| B | 2111.08379 | Minimax Robust Landmine Detection Using Forward-Looking Ground-Penetrating Radar |
| B | 2112.04840 | Knowledge Distillation for Object Detection via Rank Mimicking and Prediction-guided Feature Imitation |
| B | 2205.04072 | Beyond Bounding Box: Multimodal Knowledge Learning for Object Detection |
| B | 2210.06535 | Development of a Simulation Environment for Evaluation of a Forward Looking Sonar System for Small AUVs |
| B | 2212.00352 | A Dataset with Multibeam Forward-Looking Sonar for Underwater Object Detection |
| B | 2303.02203 | X$^3$KD: Knowledge Distillation Across Modalities, Tasks and Stages for Multi-Camera 3D Object Detection |
| B | 2303.12946 | Underwater Camouflage Object Detection Dataset |
| B | 2310.01667 | STARS: Zero-shot Sim-to-Real Transfer for Segmentation of Shipwrecks in Sonar Imagery |
| B | 2404.18663 | Terrain characterisation for online adaptability of automated sonar processing: Lessons learnt from operationally applying ATR to sidescan sonar in MCM applications |
| B | 2405.03355 | A Generalization Theory of Cross-Modality Distillation with Contrastive Learning |
| B | 2405.13571 | Incomplete Multimodal Industrial Anomaly Detection via Cross-Modal Distillation |
| B | 2409.02438 | Non-target Divergence Hypothesis: Toward Understanding Domain Gaps in Cross-Modal Knowledge Distillation |
| B | 2501.07101 | SAMKD: Spatial-aware Adaptive Masking Knowledge Distillation for Object Detection |
| B | 2503.09878 | CleverDistiller: Simple and Spatially Consistent Cross-modal Distillation |
| B | 2504.00159 | SonarSplat: Novel View Synthesis of Imaging Sonar via Gaussian Splatting |
| B | 2507.16296 | Cross-Modal Distillation For Widely Differing Modalities |
| B | 2509.17712 | RCTDistill: Cross-Modal Knowledge Distillation Framework for Radar-Camera 3D Object Detection with Temporal Fusion |
| B | 2510.03353 | Sonar Image Datasets: A Comprehensive Survey of Resources, Challenges, and Applications |
| B | 2512.22483 | Scalpel-SAM: A Semi-Supervised Paradigm for Adapting SAM to Infrared Small Object Detection |
| B | 2602.04583 | PEPR: Privileged Event-based Predictive Regularization for Domain Generalization |
| B | 2603.13585 | Sonar-MASt3R: Real-Time Opti-Acoustic Fusion in Turbid, Unstructured Environments |
| B | 2606.24248 | M^2C-EvDet: Multi-Domain Multi-Order Cross-Modal Knowledge Distillation for Event-based Object Detection |
| B | 2607.23770 | A Comparison of Data Augmentation Methods for Training Deep Neural Networks on Synthetic Aperture Sonar |
| B | 2609.01738 | UAV Thermal Imagery for Inert Ordnance Screening: Multi Campaign Dataset Development,Object Detection, and Practical Recommendations |
| B | 2609.03378 | When Depth Hurts: Reliability-Aware Geometry Distillation for Depth-Free RGB-D Salient Object Detection |
| B | 2609.37243 | Codebook-Guided Cross-Modal Knowledge Distillation for Structurally Heterogeneous Features |
| C | 1709.02600 | Objectness Scoring and Detection Proposals in Forward-Looking Sonar Images with Convolutional Neural Networks |
| C | 1910.05374 | Rotation-invariant shipwreck recognition with forward-looking sonar |
| C | 2107.10504 | External-Memory Networks for Low-Shot Learning of Targets in Forward-Looking-Sonar Imagery |
| C | 2108.03619 | Learning an Augmented RGB Representation with Cross-Modal Knowledge Distillation for Action Detection |
| C | 2211.10156 | DETRDistill: A Universal Knowledge Distillation Framework for DETR-families |
| C | 2308.11633 | Advances in Self-Supervised Learning for Synthetic Aperture Sonar Data Processing, Classification, and Pattern Recognition |
| C | 2309.02719 | DMKD: Improving Feature-based Knowledge Distillation for Object Detection Via Dual Masking Augmentation |
| C | 2312.02240 | Contrastive Learning-Based Spectral Knowledge Distillation for Multi-Modality and Missing Modality Scenarios in Semantic Segmentation |
| C | 2312.11829 | RadOcc: Learning Cross-Modality Occupancy Knowledge through Rendering Assisted Distillation |
| C | 2409.07004 | Performance Assessment of Feature Detection Methods for 2-D FS Sonar Imagery |
| C | 2511.13922 | Self-Supervised Compression and Artifact Correction for Streaming Underwater Imaging Sonar |
| C | 2511.14599 | CCSD: Cross-Modal Compositional Self-Distillation for Robust Brain Tumor Segmentation with Missing Modalities |
| C | 2605.09899 | Hyperbolic Distillation: Geometry-Guided Cross-Modal Transfer for Robust 3D Object Detection |
| C | 2611.06542 | EvoOPD: Evolving Privileged Information Strategies for Black-Box On-Policy Distillation |

## 五、建议先跑哪几个

| 优先级 | 仓库 | 为什么 |
|---|---|---|
| 1 | [remaro-network/KD-YOLOX-ViT](https://github.com/remaro-network/KD-YOLOX-ViT) ★98 | 声呐 + YOLOX + KD 三件事同时占，脚本齐全，是唯一「同架构·同任务·同蒸馏」的外部实现 |
| 2 | [pingggg516/CTFS](https://github.com/pingggg516/CTFS) ★15 | 前视声呐教师-学生 + 2% 标注，2026-11-06 仍在更新；最近邻工作，差异必须先复现它的对照才能谈 |
| 3 | [wzyii/M2SDF](https://github.com/wzyii/M2SDF) | 9 个光学去噪器迁声呐 × 4 检测器（含 YOLOX），现成的「光学→声呐」迁移表 |
| 4 | [LiYunfengLYF/SCANet](https://github.com/LiYunfengLYF/SCANet) + [RGBS50](https://github.com/LiYunfengLYF/RGBS50) ★32 | 配对 RGB-声呐数据 + 跨注意力融合，是 fusion 路线的直接对照；本文卖点依赖「fusion 与 distillation 未在同一数据/划分下比较」这一空白 |
| 5 | [megvii-research/CVPR2023-UniDistill](https://github.com/megvii-research/CVPR2023-UniDistill) ★119 | 通用跨模态检测 KD 的经典实现，作 baseline 用 |

> 注意：`weirl-922/ACKD`、`Ruoyu-Xu/SCKD`、`thenukan/xModel-KD` 有星标、也被论文点名，但仓里没有代码——
> **不能把「论文宣称开源」写成「代码可用」**。RadarDistill 的仓由作者自标 official，论文源包里没有这条链接，引用时按「仓库自述」标注。

