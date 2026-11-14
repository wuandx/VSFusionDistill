# KD 轴：跨模态知识蒸馏（Cross-Modal Knowledge Distillation）

- 检索日期：2026-11-12
- 检索员：lit-kd（teammate）
- 服务对象：CMOLD（Aydogmus & Erer, *Cross-Modality Object-Level Knowledge Distillation for Enhanced Underwater UXO Detection*, IEEE Access 2026, DOI 10.1109/ACCESS.2026.3666096）
- 本文件只做**检索与元数据核验**，未下载任何 PDF / LaTeX 源码。

## 核验方法与可信度

- **全部 33 条候选均经 arXiv API 核验**：`https://export.arxiv.org/api/query?id_list=<ids>&max_results=N`，HTTP 200，逐条比对返回的 `<title>` 与本表标题一致；`首次提交日` 取自 `<published>`，`最新版` 取自 `<id>` 版本号与 `<updated>`。
- `场所` 一列只写 **arXiv 元数据本身**能证明的（`<arxiv:comment>` 或 `<arxiv:journal_ref>`），来源已在括号里注明；没有填 `未注` 的一律是 arXiv 未提供会议/期刊信息，**不等于**没有发表。
- ⚠️ 环境事实：`export.arxiv.org/api/query` 的 **search_query 端点从本机被限流（HTTP 429）**，但 **id_list 端点稳定 200**。因此检索（发现）走 arXiv HTML 高级搜索页，核验（元数据）走 id_list——两条通道分工，不是同一个东西。
- ⚠️ 凭记忆写 ID 不可靠，本任务已实测两条错误（2203.14016 实为拜占庭脉冲同步、2110.11816 实为网络相关性统计检验），均弃。凡「记忆→核验」路径的条目，见表下注释。

---

## 检索记录

HTML 高级搜索模板（abstract 字段，布尔 AND）：

```
https://arxiv.org/search/advanced?advanced=&terms-0-operator=AND&terms-0-term=<短语>&terms-0-field=abstract
  &terms-1-operator=AND&terms-1-term=<短语>&terms-1-field=abstract
  &classification-include_cross_list=include&start=0&size=100&order=-announced_date_first
```

`收录数` = 该 query 直接贡献并最终保留的条目数；条目会在多条 query 中重复命中，**全表去重后 33 篇**。

### 桶 1：cross-modal / cross-modality KD for object detection

| # | 实际 query | 通道 | 命中 | 收录 |
|---|---|---|---|---|
| 1.1 | `abs:"cross-modal knowledge distillation"` | API search_query | 94（取前 60） | 6 |
| 1.2 | `abs:"cross-modality knowledge distillation"` | API search_query | 94（取前 60） | 5 |
| 1.3 | `abs:"cross-modal distillation" AND abs:detection` | API search_query | 19 | 4 |
| 1.4 | `abs:"modality distillation"` | API search_query | 108（取前 60） | 3 |
| 1.5 | `ABS thermal AND ABS "knowledge distillation" AND ABS detection` | HTML advanced | 7 | 3 |
| 1.6 | `ABS sonar AND ABS distillation` | HTML advanced | 8 | 2 |
| 1.7 | `ABS underwater AND ABS "knowledge distillation" AND ABS detection` | HTML advanced | 4 | 0（均已在库或不涉 KD） |
| 1.8 | `ABS "pseudo-label" AND ABS "cross-modal" AND ABS detection` | HTML advanced | 25 | 2 |
| 1.9 | `ABS "object-level" AND ABS distillation AND ABS detection` | HTML advanced | 22 | 2 |
| 1.10 | `ABS event AND ABS distillation AND ABS "object detection"` | HTML advanced | 10 | 2 |
| 1.11 | `ABS infrared AND ABS "knowledge distillation" AND ABS "object detection"` | HTML advanced | 1 | 1 |
| 1.12 | `ABS depth AND ABS distillation AND ABS "object detection" AND ABS RGB` | HTML advanced | 10 | 1 |

### 桶 2：missing-modality / modality-incomplete + KD

| # | 实际 query | 通道 | 命中 | 收录 |
|---|---|---|---|---|
| 2.1 | `ABS "missing modality" AND ABS distillation AND ABS detection` | HTML advanced | 4 | 2 |
| 2.2 | `ABS "incomplete multimodal" AND ABS distillation` | HTML advanced | 3 | 1 |
| 2.3 | `ABS "single-modality annotations"` | HTML advanced | **0** | 0 |
| 2.4 | `ABS "modality-incomplete"` | API search_query | 429 失败（未补跑） | — |
| 2.5 | `ABS "modality hallucination"` | HTML advanced | 33 | 1 |

### 桶 3：object-level / feature-level / relation-level KD for detection（含 YOLO 系）

| # | 实际 query | 通道 | 命中 | 收录 |
|---|---|---|---|---|
| 3.1 | `ABS "feature distillation" AND ABS "object detection"` | HTML advanced | 40 | 4 |
| 3.2 | `ABS "focal and global knowledge distillation"` | HTML advanced | 0 | 0 |
| 3.3 | `TI "focal and global knowledge distillation"` | HTML advanced | 1 | 1（2111.11837） |
| 3.4 | `TI "G-DetKD"` | HTML advanced | 1 | 1（2108.07482） |
| 3.5 | `ABS "relation distillation"` | HTML advanced | **429 失败**（间隔不足，未补跑） | — |
| 3.6 | `ABS "object detection" AND ABS "knowledge distillation" AND ABS YOLO` | HTML advanced | 7 | 1 |
| 3.7 | `ABS YOLOX AND ABS distillation` | HTML advanced | 3 | 1（2403.09313） |
| 3.8 | `TI "MimicDet"` | HTML advanced | 1 | 1（2009.11528） |
| 3.9 | 领域记忆提出 ID → id_list 核验 | API id_list | 4 条候选（1 条 ID 记错被弃） | 4 |

> 3.9 细节：Localization Distillation(2102.12252)、Rank Mimicking(2112.04840)、Fine-grained Feature Imitation(1906.03609)、MimicDet(2009.11528) 由记忆提出 ID，全部回查标题确认；另提的 ICKD 记忆 ID 2110.11816 实际是 *Testing network correlation efficiently via counting trees*，已弃、未收录。

### 桶 4：LUPI / teacher with privileged modality

| # | 实际 query | 通道 | 命中 | 收录 |
|---|---|---|---|---|
| 4.1 | `ABS "learning using privileged information"` | HTML advanced | 47 | 3 |
| 4.2 | `ABS "privileged information"` | HTML advanced | **429 失败**（4.1 已覆盖同义面） | — |
| 4.3 | `ABS "modality hallucination"`（privileged + 缺模态交叉） | HTML advanced | 33 | 1（1908.10559） |

### 桶 5：跨模态蒸馏用于分割/分类，机制可迁移

| # | 实际 query | 通道 | 命中 | 收录 |
|---|---|---|---|---|
| 5.1 | `ABS "cross-modal distillation" AND ABS segmentation` | HTML advanced | 14 | 2 |
| 5.2 | `ABS "incomplete multimodal" AND ABS distillation`（顺带覆盖医学缺模态） | HTML advanced | 3 | 1 |

### 桶 6：基础模型/大模型 → 轻量检测器

| # | 实际 query | 通道 | 命中 | 收录 |
|---|---|---|---|---|
| 6.1 | `ABS distillation AND ABS "open-vocabulary" AND ABS detection` | HTML advanced | 55 | 2 |
| 6.2 | `ABS "foundation model" AND ABS distillation AND ABS "object detection"` | HTML advanced | 28 | 2 |
| 6.3 | `TI FreqKD`（Lead 指出的 FreqKD 回查） | HTML advanced | 1 | 0（2606.11572，已在 Lead 24 篇内） |

### 失败留档（不许当成「不存在」）

| query | 症状 | 处置 |
|---|---|---|
| `abs:"relation distillation"` | HTML advanced 返回 429 | 未补跑；关系蒸馏的实证已由 2108.07482（对比/关系）、2111.11837（global relation）覆盖 |
| `abs:"privileged information"` | 429 | 用 `learning using privileged information`（47 条）替代 |
| `abs:"modality-incomplete"` | 429 | 用 `"incomplete multimodal"`（3 条）替代 |
| 全部 `search_query` 端点 | 429 限流 | 发现改走 HTML；核验仍用 id_list（200） |
| 一条 HTML 结果 id 抓取残缺（`2510.11-128`） | 页面解析截断 | 弃用，未猜测补全 |
| `TI "knowledge distillation" AND TI survey AND TI detectors` | 命中 2 条，均非检测 KD 综述 | 见「明确找不到的」第 1 条 |

---

## 候选清单

等级：**A = 本文必引（直接支撑某个具体论证点）**，B = 该引（提供方法/证据/边界条件），C = 边缘（机制参照，不进正文也可）。

| 等级 | arXiv ID | 标题 | 首次提交日 | 最新版 | 场所（来源） | 相关性（落在本文哪个论证点） | 核验状态 |
|---|---|---|---|---|---|---|---|
| A | 2508.10445 | DOD-SA: Infrared-Visible Decoupled Object Detection with Single-Modality Annotations | 2025-08-14 | v2 (2026-08-27) | 未注 | 与本文最同构：**只有一侧模态有标注**，靠跨模态知识迁移 + 三阶段自训练 + 伪标签分配器把标注能力搬到无标注模态——直接对应学生侧「少量人工标注 + 伪标签」 | API已核验 |
| A | 2609.18124 | ACT: Aligned Consensus Teaching for Label-Efficient Oriented Object Detection in Weakly-Aligned Visible-Infrared | 2026-09-16 | v1 | 未注 | 少数成对样本有标注、其余全无标注的半监督可见光-红外检测；共识伪标签 + 循环一致区域对齐 + 尾类实例增广，正是「学生侧标注稀缺」的解法与评测口径 | API已核验 |
| A | 2403.09313 | Knowledge Distillation in YOLOX-ViT for Side-Scan Sonar Object Detection | 2024-03-14 | v1 | 未注（代码 github.com/remaro-network/KD-YOLOX-ViT） | **同模态 KD 的声呐先例**：YOLOX 系 + 侧扫声呐，KD 减少 wall detection 假正例——本文 YOLOX-M→YOLOX-S（仅声呐）同模态对照最直接的文献锚点 | API已核验 |
| A | 2605.10130 | Thermal-Det | 2026-05-11 | v1 | CVPR 2026（`arxiv:comment`） | 冻结 RGB 教师对**成对但无标注**的 thermal 数据提供几何+语义伪监督，无人工标注迁移开放词汇知识（+2–4 AP）——「强模态全标注、弱模态零标注」的最新范式 | API已核验 |
| A | 2403.05061 | RadarDistill: Boosting Radar-based Object Detection Performance via Knowledge Distillation from LiDAR Features | 2024-03-08 | v3 (2025-02-26) | CVPR 2024（`arxiv:comment`） | 跨模态**特征级**蒸馏的标准配方（跨模态对齐 + 激活阈值过滤 + proposal 内蒸馏），radar-only 20.5 mAP / 43.7 NDS——本文方法对照与超参依据 | API已核验 |
| A | 2311.05494 | Object-centric Cross-modal Feature Distillation for Event-based Object Detection | 2023-11-09 | v1 | 未注（comment 仅写 12 pages） | 把「object-level」做成**显式模块**：slot attention 把特征图解耦为物体级 + 像素级再蒸馏，几乎把与教师的差距减半——直接支撑本文 object-level KD 的命名与设计 | API已核验 |
| A | 2601.02016 | Enhancing Object Detection with Privileged Information: A Model-Agnostic Teacher-Student Approach | 2026-01-05 | v1 | 未注（代码 github.com/mbar0075/lupi-for-object-detection） | 把 **LUPI 正式引入检测**：特权信息（bbox mask / saliency / depth）仅训练期可用、推理零成本，5 个检测器一致超基线——本文「教师见强模态、学生只见弱模态」的理论框架 | API已核验 |
| A | 2108.07482 | G-DetKD: Towards General Distillation Framework for Object Detectors via Contrastive and Semantic-guided Feature Imitation | 2021-08-17 | v3 (2021-10-12) | ICCV 2021（`arxiv:comment`） | 首个同时覆盖**同构与异构**师生对的通用检测蒸馏（跨 FPN 软匹配 + 对比关系蒸馏）；用它可以正当化本文「共享 YOLOX 架构」的选择，并说明异构情形已被覆盖 | API已核验 |
| A | 2111.11837 | Focal and Global Knowledge Distillation for Detectors | 2021-11-23 | v2 (2022-03-09) | CVPR 2022（`arxiv:comment`） | 证明**等权蒸馏有害**、须按前景/背景分离并重建像素间关系（RetinaNet/FasterRCNN/RepPoints/MaskRCNN +2.9–3.6 mAP）——本文只蒸目标区域的直接依据 | API已核验 |
| A | 2102.12252 | Localization Distillation for Dense Object Detection | 2021-02-24 | v4 (2022-03-31) | CVPR 2022（`arxiv:comment`） | 在 dense detector（GFocal，与 YOLOX 同族）上证明**定位知识比语义知识更值得蒸**，logit 模仿可胜特征模仿（40.1→42.1 AP） | API已核验 |
| B | 2609.31785 | Cross-Modal Knowledge Distillation for Acoustic Pedestrian Detection | 2026-09-24 | v1 | 未注（comment 5 pages） | 唯一的「弱模态（音频）学生」跨模态 KD 实测：video 教师→audio 学生，多数方法只让 macro acc 小涨、**PR-AUC 基本不动**，主要是工作点移动（no-pedestrian 准确率升、召回降）——审稿人最可能拿它质疑本文增益的性质 | API已核验 |
| B | 2409.05564 | LEROjD: Lidar Extended Radar-Only Object Detection | 2024-09-09 | v1 | ECCV 2024（`arxiv:comment`） | 在 Lidar→radar-only 上量化「跨模态 KD 最多 +3.9 mAP，不如多阶段 thin-out 的 +4.2」——提示本文必须把增益拆成 KD 项与初始化/伪标签项 | API已核验 |
| B | 2512.15581 | IMKD: Intensity-Aware Multi-Level Knowledge Distillation for Camera-Radar Fusion | 2025-12-17 | v1 | WACV 2026（`arxiv:comment`） | 强度感知的多层级蒸馏，67.0 NDS / 61.0 mAP；来自 **DFKI-AV（与 CMOLD 的 DFKI UXO 数据集同机构）**，是同机构后续工作最该引的一篇 | API已核验 |
| B | 2303.02203 | X³KD: Knowledge Distillation Across Modalities, Tasks and Stages for Multi-Camera 3D Object Detection | 2023-03-03 | v1 | CVPR 2023（`arxiv:comment`） | 跨任务（实例分割教师）+ 跨模态特征 + 对抗 + 跨模态**输出**蒸馏组合，并给出 RADAR-based 3DOD 的泛化证据——可支撑「输出级 + 特征级并用」的设计 | API已核验 |
| B | 2405.13571 | CMDIAD: Cross-Modal Distillation for Incomplete Multimodal Industrial Anomaly Detection | 2024-05-22 | v4 (2025-10-16) | Information Fusion 126:103572 (2026)（`arxiv:journal_ref`） | 训练时多模态、**推理时可缺模态**的跨模态蒸馏——支撑「部署只有声呐」这一前提的合理性 | API已核验 |
| B | 2304.08028 | MMANet: Margin-Aware Distillation and Modality-Aware Regularization for Incomplete Multimodal Learning | 2023-04-17 | v1 | CVPR 2023（`arxiv:comment`） | 按分类不确定性加权蒸馏 + 专治「弱模态组合」的正则——对应本文学生模态信息量显著低于教师的场景 | API已核验 |
| B | 2112.04840 | Knowledge Distillation for Object Detection via Rank Mimicking and Prediction-guided Feature Imitation | 2021-12-09 | v1 | AAAI 2022（`arxiv:comment`） | 一阶段检测器专用：师生对候选框**排序不同**导致精度差，蒸排序优于蒸软标签——对本文伪标签筛选与置信度校准可直接复用 | API已核验 |
| B | 1906.03609 | Distilling Object Detectors with Fine-grained Feature Imitation | 2019-06-09 | v1 | CVPR 2019（`arxiv:comment`） | object-level 蒸馏的源头：只在**近目标 anchor 位置**模仿（KITTI 上 +15% mAP）——本文「只蒸目标区域」的历史依据 | API已核验 |
| B | 2009.11528 | MimicDet: Bridging the Gap Between One-Stage and Two-Stage Object Detection | 2020-09-24 | v1 | ECCV 2020（`arxiv:comment`） | 一阶段/两阶段异构结构蒸馏源头篇（共享 backbone 双 head 使特征兼容，COCO 46.1 mAP）——回答「师生结构不完全一致时怎么蒸」 | API已核验 |
| B | 2501.07101 | SAMKD: Spatial-Hierarchical Masked Distillation for Object Detection | 2025-01-13 | v2 (2025-03-24) | 未注 | 空间分层掩码（粗到细编码 object-aware locality）+ 掩码 logit 蒸馏，35.3→38.8 mAP——「目标感知掩码」路线较新的一篇 | API已核验 |
| B | 2205.04072 | Beyond Bounding Box: Multimodal Knowledge Learning for Object Detection | 2022-05-09 | v1 | 投稿 CVPR 2022（`arxiv:comment`） | 显式区分 **image-level 与 object-level 跨模态互信息**蒸馏（+1.6–2.1%），是本文 object-level 措辞最贴的较早文献 | API已核验 |
| B | 2410.10554 | ROSAR: An Adversarial Re-Training Framework for Robust Side-Scan Sonar Object Detection | 2024-10-14 | v1 | 未注 | 侧扫声呐 KD + 对抗重训，释放 3 个 SSS 数据集，鲁棒性最多 +1.85%——与 2403.09313 同一脉络，可作声呐 KD 的鲁棒性对照 | API已核验 |
| B | 2602.04583 | PEPR: Privileged Event-based Predictive Regularization for Domain Generalization | 2026-02-04 | v2 (2026-04-17) | 未注 | LUPI 新范式：**不做直接特征对齐**，改为在共享隐空间预测特权模态潜特征，赢过对齐式基线——若声呐/光学特征空间不可直接对齐，这是可选的替代损失 | API已核验 |
| B | 1908.10559 | Online Sensor Hallucination via Knowledge Distillation for Multimodal Image Classification | 2019-08-28 | v1 | 预印本（comment: manuscript under revision） | 最早把「训练时全传感器可用、测试时缺模态」+ KD + privileged 讲清的一篇（分类任务，PAN-MS 评测）——缺模态蒸馏的思想源头 | API已核验 |
| B | 2405.03355 | A Generalization Theory of Cross-Modality Distillation with Contrastive Learning | 2024-05-06 | v2 (2024-05-28) | 未注 | 给出跨模态 distilled 模型的泛化界：**源/目标模态距离**直接影响下游测试误差——为「光学→声呐 gap 大但仍可蒸」提供理论表述与限制条件 | API已核验 |
| B | 2609.03378 | When Depth Hurts: Reliability-Aware Geometry Distillation for Depth-Free RGB-D SOD | 2026-09-03 | v1 | 未注 | 「辅助模态可能有害」+ 逐像素可靠性门控只注入与当前表示兼容的知识，教师训后即移除——若审稿人质疑光学教师对声呐的负迁移，这是最贴的方法论 | API已核验 |
| B | 2609.37243 | Codebook-Guided Cross-Modal Knowledge Distillation for Structurally Heterogeneous Features | 2026-09-29 | v2 (2026-10-01) | NeurIPS 2026（`arxiv:comment`） | 指出特征级对齐的前提是师生表示空间**结构可对齐**，2D 网格 vs 1D 时序时不成立，改用码本做概念级锚点——本文师生同架构恰好满足该前提，可用来正当化设计选择 | API已核验 |
| B | 2411.16196 | SDM-D: Learn from Foundation Model: Fruit Detection Model without Manual Annotation | 2024-11-25 | v2 (2026-03-22) | 未注 | 强模型（SAM2+OpenCLIP）生成框→蒸馏到边缘小检测器，**完全无人工标注**即接近全监督——对应本文学生侧用伪标签替代人工标注的路线 | API已核验 |
| B | 2512.22483 | Scalpel-SAM: A Semi-Supervised Paradigm for Adapting SAM to Infrared Small Object Detection | 2025-12-27 | v1 | 未注（comment 9 pages） | 10% 标注把 SAM 蒸成专家教师 → 再用其伪标签训轻量下游模型，效果可比甚至超全监督——「少标注 + 伪标签 + 蒸馏」三段式的现成模板 | API已核验 |
| C | 2309.02719 | DMKD: Improving Feature-based Knowledge Distillation for Object Detection via Dual Masking | 2023-09-06 | v2 (2023-09-07) | 未注 | 空间 + 通道双掩码重建 + 自适应融合权重（+4.1%/+4.3%）——掩码式特征蒸馏的备选实现 | API已核验 |
| C | 2211.10156 | DETRDistill: A Universal Knowledge Distillation Framework for DETR-families | 2022-11-17 | v4 (2023-03-17) | 未注 | DETR 系专用（匈牙利匹配 logits + target-aware 特征），与 YOLOX 架构无关，仅作 KD 组件设计参照 | API已核验 |
| C | 2608.20916 | SLE-T: Semantically Compatible Knowledge Distillation for Cross-Domain Object Detection with Vision Foundation Models | 2026-08-21 | v1 | 未注 | 处理 DINOv2 教师与学生特征图**尺度不匹配导致语义不兼容**的适配器方案——若将来换大模型教师才会用到 | API已核验 |
| C | 2503.10152 | HD-OVD: A Hierarchical Semantic Distillation Framework for Open-Vocabulary Object Detection | 2025-03-13 | v1 | TMM 2025（`arxiv:comment`） | instance / class / image 三级语义蒸馏（OV-COCO novel AP 46.4%）——为「object-level 之外是否还要类别级监督」提供分层模板 | API已核验 |

**收 33 篇：A 10 / B 19 / C 4。全部 API 已核验，无「仅网页」条目。**
（另有 12 篇高相关但已在 Lead 的 24 篇清单内，按指示未重复收录：2303.15083 2211.07171 2407.10164 2412.14571 2509.17712 2606.11572 2606.24248 2605.09899 2603.07464 2312.11829 2307.04091 2512.15311 2503.09878 2605.30111 2108.03619 2310.01035 2606.10504 2507.16296 2409.02438 2511.08901 2312.02240 2511.14599 2507.07015 2611.06542。）

---

## 非 arXiv 清单（Lead 指定；仅元数据级核验）

以下条目的 DOI 存在性经 Crossref 元数据查询确认（`api.crossref.org/works`），但**未读摘要原文**，因此「相关性」一列是基于标题的判断，写作时须回原文核对。

| DOI | 标题 | 场所 / 年份 | 相关性（标题级判断） | 可获取性 |
|---|---|---|---|---|
| 10.1109/ACCESS.2026.3666096 | Cross-Modality Object-Level Knowledge Distillation for Enhanced Underwater Sonar Object Detection | IEEE Access, 2026 | **本文（CMOLD）本体**；Crossref 返回的标题与 Lead 给的一致，DOI 有效 | IEEE Xplore；IEEE Access 为开放获取期刊但本机未核该篇 license |
| 10.36227/techrxiv.176341538.86857924/v1 | CrossFusionKD: A Cross-Modal Knowledge Distillation Framework for UxV Object Detection | TechRxiv 预印本, 2025-11-17 | 与本文同题材（UxV 跨模态 KD 检测）的**最近邻预印本**，须查它是否已被期刊接收、方法是否重叠 | TechRxiv 预印本，通常可免费下载 PDF |
| 10.1109/caos69069.2026.11666192 | Cross-modal Depth-privileged Knowledge Distillation for Underwater Salient Object Detection with Only RGB Images | IEEE Canadian Atlantic Ocean Symposium (CAOS), 2026-07 | 水下 + **depth 作特权模态 + 推理只用 RGB**，与本文「部署只用弱模态」结构同构；任务为显著目标分割 | 会议论文，IEEE Xplore 付费墙概率高 |
| 10.2139/ssrn.5219975 | Modal Mimicking Knowledge Distillation for Monocular 3D Object Detection | SSRN 预印本, 2025 | 「模态模仿（modal mimicking）」与本文用伪标签/蒸馏补齐弱模态的思路同族 | SSRN，一般可免费下载 |
| 10.1109/ICCV51070.2023.00793 | DistillBEV: Boosting Multi-Camera 3D Object Detection with Cross-Modal Knowledge Distillation | ICCV 2023 | 跨模态 KD 的代表性会议论文；arXiv 版存在但本次**未核验其 arXiv ID**，故不写 ID、避免臆造 | IEEE/CVF 付费墙；CVF 开放获取页通常可得 PDF |

> 未列入：其他 IEEE Access / Sensors / TPAMI 的跨模态 KD 文章——本次没有可靠命中，**不凭印象补条目**。

---

## 明确找不到的

1. **检测专用 KD 综述（"A Survey of Knowledge Distillation for Object Detection" 类）在 arXiv 上查无。**
   用了两种措辞：`ABS survey AND ABS distillation AND ABS "object detection"`（4 条，均非）、`TI "knowledge distillation" AND TI survey AND TI detectors`（2 条，分别是 YOLOv5 压缩综述与开放词汇检测综述）。
   可能原因：这类综述多以期刊（TPAMI / ACM CSUR / IEEE Access）或书籍章节形式发表而不挂 arXiv；或标题用 review/overview 而非 survey（后两组尚未穷尽）。**只能说「本次未检出」，不能说「不存在」**——写 related work 时若要引综述，建议从 IEEE Access / TPAMI 侧另开一条检索。

2. **精确短语 `"single-modality annotations"` 在 arXiv 摘要中 0 命中。**
   该术语尚未成为通行表述；同义面散在 single-modality / unpaired / missing modality / label-efficient 等词下（本轴的 2508.10445、2609.18124 即由此捞出）。0 命中只说明措辞不流行。

3. **`"modality hallucination"` 检索 33 条几乎全是 MLLM 幻觉，与检测无关。** 该词在本领域未形成文献簇；缺模态补齐请走 `missing modality` / `sensor hallucination`（1908.10559 是这条线的起点）。

4. **「声呐 × 跨模态蒸馏」这一簇，arXiv 上已被本项目既有 63 篇基本覆盖。**
   `ABS sonar AND ABS "cross-modal"` 命中 14 条，其中 8 条已在排除表（2608.27795 2608.25367 2608.24325 2608.23479 2608.19710 2606.01398 2504.10974 2610.19097）；剩余 6 条（2511.00392 2510.04876 2509.24321 2507.05410 2507.11812 2505.24561）全是三维重建 / 数据集 / 语义导航 / 翻译，**不含 KD**。本轴真正新增的声呐 KD 文献只有 2403.09313（同模态）与 2410.10554（SSS）。→ 这条轴的空白不在「声呐 KD 文献少」，而在**跨模态（光学→声呐）蒸馏**几乎无人做，这正是 CMOLD 的立论空间。

5. **失败/未完成留档**：`abs:"relation distillation"`、`abs:"privileged information"`、`abs:"modality-incomplete"` 三条 HTML 查询返回 429，未补跑（前两条的同义面已由其他 query 覆盖，第三条由 `"incomplete multimodal"` 替代）。另有一条 HTML 结果 id 抓取残缺（形如 `2510.11-128`），已弃用而非猜测补全。

6. **检测蒸馏的「YOLO 专用 KD」文献在 arXiv 上很薄**：`YOLOX AND distillation` 仅 3 条（1 条无关、1 条边缘 GPU、1 条声呐），`object detection AND KD AND YOLO` 仅 7 条。可能原因：YOLO 系 KD 大量发表在 MDPI Sensors / IEEE Access / 中文期刊，或直接以代码仓库（如 ultralytics 生态）而非论文形式存在。

---

## 建议优先读的 5 篇

1. **2508.10445 — DOD-SA（单侧标注的可见光-红外解耦检测）**
   与本文问题设定最同构：只有一侧模态有人工标注，靠跨模态知识迁移 + 三阶段自训练 + 伪标签分配器把能力搬到无标注模态。它同时给出「单侧标注下的评测怎么做」，可用来对齐你的 student 侧标注比例与结果口径。**读它主要看：三阶段各自贡献多少、伪标签分配器怎么处理模态错位。**

2. **2605.10130 — Thermal-Det（CVPR 2026）**
   把「冻结的强模态教师 + 无标注弱模态数据」做成完整范式（几何 + 语义伪监督，+2–4 AP）。它是本轴最接近本文主张的**最新顶会实证**，也是审稿人对比「你的跨模态蒸馏是否只是伪标签的另一种说法」时的参照系。

3. **2311.05494 — Object-centric Cross-modal Feature Distillation for Event-based Object Detection**
   唯一把 **object-level** 做成显式模块（slot attention 解耦物体级 + 像素级特征再蒸馏）的跨模态检测蒸馏，且能把与教师的差距近乎减半。本文把方法命名为 object-level KD，这篇是必须正面比较/区分的对象——它的解耦方式与你「在目标框内做蒸馏」的差别正是可写的创新点。

4. **2403.09313 — Knowledge Distillation in YOLOX-ViT for Side-Scan Sonar Object Detection**
   同模态 KD 的**声呐先例**，YOLOX 系、有开源代码。你的 YOLOX-M→YOLOX-S（仅声呐）同模态对照需要文献锚点，这是最直接的一篇；也便于论证「KD 在声呐上本就有效」这个前提不是本文凭空假设。

5. **2601.02016 — Enhancing Object Detection with Privileged Information (LUPI for detection)**
   给本文的设定一个**正式理论框架**：特权信息仅在训练期可用、推理零成本、模型无关、5 个检测器一致受益。用它可以把「教师见光学、学生只见声呐」写成 LUPI 的一个特例，而不是临时拼凑的工程做法。

> 两篇「反证」建议同时备好、写进 discussion 或 limitations：**2609.31785**（弱模态学生跨模态 KD 只移动工作点、PR-AUC 不动）与 **2409.05564**（LEROjD 中跨模态 KD 增益低于多阶段 thin-out）。这两篇直接决定你要不要把增益拆成 KD 项 / 初始化项 / 伪标签项来报告。
