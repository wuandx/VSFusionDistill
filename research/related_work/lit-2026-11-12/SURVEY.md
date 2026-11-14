# 文献面综述与定位判断（2026-11-12）

本轮任务的直接问题是「搜与我这篇论文相关的论文，能拿 LaTeX 就拿」。因此本文件回答两件事：
**(a) 文献面长什么样；(b) 在既有文献面下，本文哪些说法立得住、哪些立不住。**
逐篇元数据、LaTeX 获取状态见同目录 [README.md](README.md)（机器生成）与 [index.md](index.md)（平表）；
两条检索轴的原始过程记录见 [notes/sonar-axis.md](notes/sonar-axis.md)、[notes/kd-axis.md](notes/kd-axis.md)。

**本文件的判断分层**，每处都标了来源：
`[原文]` 论文正文/摘要明写 ｜ `[元数据]` 仅 Crossref/OpenAlex/arXiv abs 页 ｜ `[我方判断]` 由前两者推出的比较结论 ｜ `[未决]` 没核到的。

---

## 0. 结论先讲

1. **arXiv 上不存在「水下 UXO + 声呐 + 检测」的论文。** `abs:UXO` 11 条、`"unexploded ordnance"` 15 条、
   `unexploded AND underwater` 仅 2 条，全部落在陆上 EMI、弹坑、航空热红外。`[元数据+检索留档]`
   这条空白可以直接写进 motivation，且不必担心被审稿人拿一篇 arXiv 论文打掉。
2. **但「跨模态蒸馏 + 只部署一个模态」本身不新。** 最新的一篇是 CrossFusionKD（TechRxiv 2025-11-17，
   RGB+IR 教师 → RGB-only 学生）。它的模态角色与本文**相反**（学生是充裕模态），且不涉声呐，
   所以不撞车；不过「推理期只要一个传感器」这个卖点已经有人说过更早（1908.10559, 2019）。`[元数据]`
3. **本文真正稀缺的东西不是"蒸馏 + 声呐"，而是三件具体的事**（详见 §3）：
   推理期只留声呐、object-level 蒸馏作用在「光学 → 声呐」这一步、以及 recording-level split 下可比的读数。
4. **有两条反证必须进 discussion**：2609.31785（跨模态 KD 到弱模态只移动工作点、PR-AUC 不动）、
   2409.05564（跨模态 KD +3.9 < 多阶段 thin-out +4.2）。它们要求把增益拆项报告，不能笼统归因。`[原文摘要]`

---

## 1. 检索与核验口径（可复查）

| 项 | 值 |
|---|---|
| 发现通道 | arXiv HTML 高级搜索（`searchtype=abstract`），18 个 bucket；arXiv API `search_query` 端点 429，只用 `id_list` 做核验 |
| 候选池 | 592 条（去重后）；过主题门槛 339 条；最终收录见 README 统计 |
| 筛选门槛 | 标题/摘要命中 `sonar｜underwater｜distill｜explode｜cross-modal` 之一，再按 axes 加权排序 |
| 核验 | 每条经 `export.arxiv.org/api/query?id_list=...` 返回 200 且标题逐字比对；日期取 `<published>`，场所只写 `<arxiv:comment>`/`<arxiv:journal_ref>` 里真有的，没有写「未注」 |
| 已知空白 | 检测 KD 综述：arXiv 查无（`survey+distillation+object detection` 命中均非综述）；`"single-modality annotations"` 精确短语 0 命中；`"modality hallucination"` 33 条全是大模型幻觉，与本文无关 |
| 失败留档 | `relation distillation`、`privileged information`、`modality-incomplete` 三条 query 因限流未补跑；同义面已由其他 query 覆盖（见 notes） |

非 arXiv 一侧只做到**元数据层**（Crossref / OpenAlex / Europe PMC JATS），没有读正文的地方在 §6 明确写出。

---

## 2. 现状地图（按 CMOLD 的三小节归位）

CMOLD §II 的实际结构（`cmold/evidence-existing/cmold_numbered.txt:144/215/201`）：
**II-A** UNDERWATER OBJECT DETECTION USING SONAR IMAGES｜**II-B** ADVANCES IN CAMERA-SONAR FUSION APPROACHES｜
**II-C** KNOWLEDGE DISTILLATION TECHNIQUES。index.md 的 `cmold_section` 列就按这三节 + `II-C→跨模态` + `III/IV` + `V` 标注。

### 2.1 声呐图像目标检测（II-A）

- **2412.11840** *Sonar-based Deep Learning in Underwater Robotics: Overview, Robustness and Challenges*
  （arXiv 2024-12-16；期刊版 IEEE JOE 2025，`10.1109/JOE.2025.3531933`）——领域首选综述，把「训练数据有限 + 声呐固有噪声」列为本领域主要瓶颈。`[原文]` **注意：此前记录里的 2411.05863 是错的**，正确编号是 2412.11840。
- **2403.09313** *Knowledge Distillation in YOLOX-ViT for Side-Scan Sonar Object Detection*——YOLOX 系 + 侧扫声呐 + KD，
  本文同模态对照最直接的锚点（作者放了源码 `remaro-network/KD-YOLOX-ViT`）。
- **2410.10554** *ROSAR*——侧扫声呐 KD + 对抗重训，同时释放 3 个 SSS 数据集。与 2403.09313 同一课题组路线。
- **2603.21071** *CTFS*（CVPR 2026 Findings）——**前视声呐语义分割**上的教师-学生框架（1 个通用教师 + 多个声呐专用教师 + 跨教师集成），
  只用极少量标注。这是与本文最接近的 FLS 侧工作：同样"教师带学生"，但它的教师仍在声呐域、任务是分割；本文教师跨模态、任务是检测。
- **2604.00383** *Mine-JEPA*——SSS 域内自监督，1170 张无标注图 F1 0.935；同时报告"域内 SSL 会使基础模型掉 10–13"，
  是"少标注 + 强先验"路线的对照组，也是"预训练权重跨域迁移有害"的证据点。
- **2503.01655** *Can Optical Denoising Clean Sonar Images?*——9 个光学去噪器迁到声呐，下游 4 个检测器（含 YOLOX）验证。
  这是「光学域方法迁声呐」的**图像级**先例，与本文的**知识级**迁移正好构成对照。
- **2304.11875**——7052 对光学 → SAS 的迁移学习，规模最大的光学-声呐配对实验。
- **2406.07189**——RGBS50 配对集 + SRST 造"声呐样"伪配对，属于用生成弥合模态差。

### 2.2 camera–sonar 融合（II-B）

这一节**几乎全部是融合，不是蒸馏**，这是本文可选的最干净的对比面。已核到元数据的直接竞争路线（均为 fusion 或单模态少样本）：
Chrs-Net（`10.3390/jmse14121094`）、Dual-Modal（`10.3390/jmse14040338`）、FS2-DETR（`10.3390/jmse14030304`）、
SCFusion（`10.1016/j.oceaneng.2026.126793`）、MFTCA-Net、大坝声呐-相机融合。`[元数据]`

- **AOPQ-Net**（*Remote Sensing* 18(16):2703, 2026-08-11, CC-BY, `10.3390/rs18162703`）——DFKI UXO 数据集 11 条引用里最新的一篇，
  且是唯一 CC-BY 可全文获取的。**是否直接使用该数据集需读正文确认**`[未决]`，这是本轮最该补读的一篇非 arXiv 文献。

### 2.3 跨模态蒸馏方法谱系（II-C）

**源头层**（写作时作为方法学引用，不必逐篇评述）：1906.03609（object-level 蒸馏源头，近目标 anchor 模仿，CVPR19）、
2009.11528（MimicDet，一阶段/两阶段异构，ECCV20）、2108.07482（G-DetKD，同构+异构统一，ICCV21）、
2111.11837（Focal & Global KD，证明等权蒸馏有害，CVPR22）、2102.12252（定位蒸馏，dense detector 上定位知识 > 语义知识）、
2112.04840（Rank Mimicking，一阶段候选框排序）。

**object-level 做得最实的一篇**：2311.05494（object-centric cross-modal KD, RGB→event），
用 slot attention 把物体级与像素级知识解耦，是唯一把 "object-level" 做成显式模块的工作。

**缺模态 / 特权信息**：1908.10559（最早：训练时全传感器、测试缺模态 + KD）、2304.08028（MMANet，不确定性加权）、
2405.13571（CMDIAD，推理可缺模态）、2602.04583（PEPR：不对齐特征，改预测特权模态潜特征）、
2601.02016（LUPI 正式引入检测，特权信息仅训练期可用）、2609.03378（When Depth Hurts：辅助模态有害 + 可靠性门控）。

**单侧标注 / 无标注学生**：2508.10445（DOD-SA，红外-可见光单侧标注，设定最同构）、
2609.18124（ACT，少数配对 + 共识伪标签）、2605.10130（Thermal-Det，冻结 RGB 教师给无标注 thermal 伪监督，CVPR26）、
2411.16196（SDM-D，基础模型出框蒸馏到边缘小检测器，零人工标注）、2512.22483（Scalpel-SAM，10% 标注把 SAM 蒸成教师）。

**理论**：2405.03355 给出跨模态蒸馏的泛化界，**源/目标模态距离直接影响下游误差**。
`[我方判断]` 这条能被用来解释为什么 camera↔sonar 的收益不该期望与 RGB↔IR 同量级——但只能当解释，不能当实验证据。

### 2.4 UXO 与数据生态（III/IV）

- 数据：DFKI UXO（Zenodo 13778485，bsd-3-clause，4 个 7z 共 96 GB）；原始论文 OCEANS 2024（`10.1109/OCEANS55160.2024.10754316`，闭源，dfki.de 有 PDF 但受 Cloudflare challenge）。
- 引用面：该数据集 11 条引用中，仅 AOPQ-Net（CC-BY）与 SonarCloud（OCEANS 2025，闭源）为近期工作 `[元数据]`。
- **arXiv 上的 UXO 文献（11+15 条）全是陆上场景**，与水下声呐无交集 `[元数据]`。

---

## 3. 与既有文献的差异：能写的三条，不能写的三条

### 能写（且能被打不掉的）

1. **推理期只留声呐**。fusion 系列（§2.2）全部要求推理期两路数据，本文只在训练期用相机。
   单看这条不新 —— 1908.10559 已表述、CrossFusionKD 已做 RGB+IR 版；新的是**在声呐上做，且学生是感知更受限的那一侧**。
2. **object-level 蒸馏作用在「光学 → 声呐」这一步**。`[我方判断]` 关键：arXiv 上 `sonar × cross-modal` 共 14 条，
   8 条已在既有库，剩 6 条全是重建/数据集/导航/翻译，**无一含 KD**。所以空白不能写成"声呐 KD 文献少"
   （2403.09313、2410.10554、CTFS 都在），只能写成"这一步没人做"。
3. **recording-level split 下给出可比读数**。`[我方判断]` 这是最硬的一条：fusion 与 distillation 从未在同一数据集、
   同一划分下被比较过；CMHD 用 per-class 10 轨迹 × 100 帧 6:2:2，CMOLD 用 recording-level，两者读数不可直接相减。
   把这条写清楚，比再多引 20 篇都有用。

### 不能写

1. ~~首个跨模态蒸馏~~ / ~~首个声呐 UXO 检测~~——前者见 1908.10559、2311.05494、2508.10445；
   后者被 2603.21071（FLS 教师-学生）、2403.09313（SSS + YOLOX + KD）与整个 §2.2 融合线堵住。
2. ~~"文献采用帧级随机划分"~~——CMHD 是每类 10 条轨迹各 100 帧后 6:2:2，这既不代表 CMOLD，也不等于帧级随机；
   AGENTS.md 已把这条列为禁止升级。
3. ~~"KD 对弱模态普遍有效"~~——见下面两条反证。

---

## 4. 反证与风险（discussion 必写）

| 论文 | 反证内容 | 对本文的要求 |
|---|---|---|
| 2609.31785 *Cross-Modal KD for Acoustic Pedestrian Detection* | video 教师 → audio 学生，KD 只**移动工作点**，PR-AUC 不涨、召回反降 | 报 PR 曲线/工作点，不只报 AP50 一个数 |
| 2409.05564 *LEROjD* | Lidar→radar-only：跨模态 KD 最多 **+3.9**，不如多阶段 thin-out 的 **+4.2** | 必须给"不用 KD"的强基线（thin-out / 伪标签 / 直接微调） |
| 2609.03378 *When Depth Hurts* | 辅助模态可能有害，需逐像素可靠性门控 | 若增益不稳，先检查教师知识的对齐质量，而不是加蒸馏权重 |
| 2405.03355 *A Generalization Theory of CMKD* | 模态距离越大，蒸馏泛化收益越差 | 解释 camera↔sonar 的收益量级，但不得当作实验结果 |

`[我方判断]` 这四条合起来指向一个具体动作：**把总增益拆成 KD 项 / 初始化（教师权重起始）项 / 伪标签项**分别报告。
这也正好回应 AGENTS.md「不强行将绝对差距归因给单一因素」。

---

## 5. 撞车排查：CrossFusionKD（本轮的最近邻预印本）

- 出处：TechRxiv，2025-11-17，`10.36227/techrxiv.176341538.86857924/v1`；题目 *CrossFusionKD: A Cross-Modal Knowledge
  Distillation Framework for UxV Object Detection*；作者 Abidi, Masuduzzaman, Raza, Shin。`[元数据, Crossref]`
- 内容（摘要）：RGB+IR 教师 → **RGB-only 轻量学生**，channel-wise 蒸馏，推理时不需要 IR；LLVIP 96.7 mAP（RGB-only）、
  融合 98.3、KAIST 92.1、STUJ-SMOD 92.8。`[元数据, 摘要]`
- 代码：GitHub `Murtazaabidi1/CrossFusionKD-Framework-for-UxV-Object-Detection` 目前是**空占位仓**（README 仅"待发布"）。`[已查]`
- **判定：不撞车。** 理由：①无 sonar、无 UXO、无水下；②模态角色相反——它的学生是 RGB（充裕、便宜），
  本文的学生是声呐（受限、贵）；③它是 channel-wise 特征蒸馏，本文是 object-level。
- **一处未决**：`STUJ-SMOD` 这个数据集名未能核验含义（TechRxiv 全文受 Cloudflare 403）。若它其实是声呐数据集，
  第 ② 条理由要重估。`[未决]` 处理办法：写作时引它一句作为"单模态推理 KD 的先例"，不要引它的数字。

---

## 6. 获取状态与不可得（LaTeX 优先）

- 逐篇状态见 [README.md](README.md) 的「获取记录」表：`tex=0` 且 `eprint=pdf` 的是作者只投 PDF，不算 LaTeX。
- **CMOLD 本体**：IEEE Access CC-BY gold OA，但 202/WAF、PDF 走 301 防盗链，脚本拿不到；**arXiv 无预印本**（3 次查询 0 命中）
  → 不存在公开 LaTeX。只能靠浏览器过 WAF 取 PDF。
- **CMHD**：MDPI 403，PMC 200 可读 JATS XML（`https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13417324/fullTextXML`），
  无 LaTeX；PMC `oa.fcgi` 404。
- **DFKI UXO 原始论文（OCEANS 2024）**：闭源；dfki.de 的 PDF 返回 403 `Cf-Mitigated: challenge`，浏览器可过。
- **AOPQ-Net**：CC-BY，理论可下，但同样在 MDPI 域，脚本 403 → 需浏览器。`[未决：未取]`
- 规矩：**只拿到元数据的条目，一律不得当作已读正文**；README 表里没有 .tex 的，不许在综述里引用其具体数字。

---

## 7. 下一步（按优先级）

1. 用浏览器取 AOPQ-Net 全文，确认它是否真用 DFKI UXO——这决定 §2.2 里"融合线在 UXO 上的最近工作"怎么写。
2. 写完 related work 时按 II-A / II-B / II-C 三节归位，直接用 index.md 的 `cmold_section` 列筛。
3. 在 `experiment/evaluation.md` 里把 §3.3 的不可比边界（CMHD 6:2:2 vs recording-level）写成一条冻结条款。
4. §4 的四条反证进 discussion，并把"拆项报告"写进实验登记模板。
