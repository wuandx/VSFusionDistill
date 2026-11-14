# 声呐检测 / UXO / RGB-声呐多模态融合 —— 文献轴检索与核验记录

检索人：lit-sonar（teammate）。检索时间：2026-11-12（UTC+8 16:13–16:40）。
目标论文：CMOLD（Aydogmus & Erer, IEEE Access 2026, DOI 10.1109/ACCESS.2026.3666096）。
本文件只记录检索与元数据核验，**未下载任何 PDF / LaTeX 源码**（按分工由 Lead 统一获取）。

工具与通道说明（影响可复现性）：
- shell 只能走 `wsl`；WSL 内无出网，一切网络请求用 `/mnt/c/Windows/System32/curl.exe`。
- `export.arxiv.org` API 频繁 429，用 `sleep 20–25` 重试循环（每批最多 8 次）通过；`id_list=` 一次可批量核验 ≤12 个 id。
- 后期按 Lead 提示改用 arXiv **HTML 搜索页**（`searchtype=abstract`，间隔 ≥6 s）绕开限流。
- `web_search` 工具在本会话不可用（返回 402 并回显自动生成的 API key，已弃用）；非 arXiv 检索改走 `advanced_search engine=exa` + Crossref / OpenAlex / Zenodo / PMC 官方 API。
- 所有候选的标题、首次提交日、最新版本均以 `export.arxiv.org/api/query?id_list=...` 返回的 `<title>` / `<published>` / `<updated>` 为准；无一条凭记忆填写 ID。

---

## 检索记录

### A. arXiv API（`export.arxiv.org/api/query`，`sortBy=submittedDate&sortOrder=descending`，`max_results=60`）

| 桶 | query | 命中数 | 收录数 | 备注 |
|---|---|---|---|---|
| 1 FLS/成像声呐检测 | `abs:"forward-looking sonar" AND abs:detection` | 22 | 6 | 命中大量已在排除表（2503.22880、2608.22072、2609.14025、2609.24195 等） |
| 1 | `abs:sonar AND abs:"sonar image" AND abs:"detection"`（t10） | 26 | 5 | 含 2510.03353 数据集综述 |
| 1 | `abs:"forward-looking sonar" AND abs:"semantic segmentation"`（u4） | 3 | 1 | 唯一新命中 2603.21071 |
| 1 | `abs:"multibeam" AND abs:sonar AND abs:detection`（s9） | 10 | 0 | 仅 2212.00352（Lead 池已有） |
| 1 | `abs:sonar AND abs:YOLO`（u3） | 2 | 0 | 均为池内/排除表 |
| 1 SAS | `abs:"synthetic aperture sonar"`（t1；批次1同 query 首次返回 0 字节，重跑成功） | 48 | 4 | 2304.11875、2101.03603、1706.09858、2607.23770 |
| 1 半监督 | `abs:sonar AND abs:"semi-supervised"`（s8） | 3 | 1 | 2101.03603 |
| 2 RGB-声呐融合 | `abs:sonar AND abs:RGB`（t3） | 16 | 1 | 排除表已覆盖 2608.25367 RSFusionDet、2608.27795 uScenes |
| 2 跨模态 | `abs:sonar AND abs:"cross-modal"`（t2） | 14 | 2 | 2609.04411、2303.12946 |
| 2 声光融合 | `abs:"acoustic" AND abs:"optical" AND abs:"fusion" AND abs:underwater`（t8） | 7 | 1 | 2603.13585 |
| 2 多模态宽 | `abs:sonar AND abs:"multimodal"`（HTML 复核） | 21 | 0 | 新命中全部在排除表（2609.17929、2608.27795、2608.25367、2608.27793） |
| 3 UXO | `abs:"unexploded ordnance"`（s5） | 15 | 0 | 命中全为陆上/电磁感应/航空热红外（如 2610.38177 EM 分类、2510.02700 高光谱、2209.11299 弹坑） |
| 3 UXO | `abs:"unexploded" AND abs:underwater`（u5） | 2 | 0 | 无水下声呐 UXO 检测 |
| 3 UXO | `abs:UXO`（HTML 页） | 11 | 0 | 同上；**arXiv 侧无「水下声呐 UXO 检测」论文**（详见第 4 节） |
| 3 MCM | `abs:mine AND abs:sonar AND abs:detection`（t6） | 7 | 0 | 池内/排除表 |
| 3 MCM | `abs:"mine-like" OR abs:"minehunting" OR abs:"mine hunting"`（u1） | 7 | 1 | 2604.00383 Mine-JEPA |
| 4 域适应 | `abs:sonar AND abs:"domain adaptation"`（s6） | 3 | 0 | 命中与声呐无关；域适应本体由 g5 收 2604.00383 |
| 4 伪标签/少标注 | `abs:sonar AND abs:"pseudo-label"`（t9） | 4 | 1 | 2603.21071（另见 2601.12715，排除表） |
| 4 教师-学生 | `abs:sonar AND abs:"teacher"`（u2） | 8 | 1 | 2603.21071 |
| 4 迁移/少样本 | `abs:sonar AND abs:"transfer learning"`（u8） | 11 | 2 | 1706.09858、2108.01111 |
| 4 零样本 | `abs:"sonar" AND abs:"zero-shot"`（u7） | 9 | 0 | 2609.01738 在 Lead 池 |
| 4 基础模型 | `abs:sonar AND abs:"foundation model"`（u6） | 6 | 0 | 无新命中 |
| 5 增强 | `abs:sonar AND abs:"data augmentation"`（t4） | 5 | 1 | 2607.23770 |
| 5 仿真/sim-to-real | `abs:"sonar simulation" OR abs:"sim-to-real" AND abs:sonar`（t5） | 8 | 2 | 2310.01667、2606.06130 |
| 5 合成数据 | `abs:sonar AND abs:"synthetic" AND abs:detection`（HTML） | 26 | 1 | 2210.06535；最强的 2605.19712（physics-informed 仿真）已在排除表 |
| 5 图像合成 | `abs:sonar AND abs:"image synthesis"`（HTML） | 2 | 2 | 2410.08612、2504.00159 |
| 5 图-图转换 | `abs:sonar AND abs:"image-to-image"`（HTML） | 2 | 0 | 2604.19901、2601.12715（后者排除表） |
| 6 KD | `abs:sonar AND abs:"knowledge distillation"`（s7） | 4 | 0 | 2403.09313、2410.10554、2603.15200 全在 Lead 池，无第 4 篇新文 |
| 6 KD | `ti:sonar AND abs:distillation`（t7） | 6 | 0 | 同上 |
| 综述/数据集 | `abs:"underwater object detection"`（s10） | 53 | 1 | 2510.03353 |
| 广域宽查询 | 首轮宽查询（query 串未落盘，返回内容为声呐多模态/RGB 混合） | 33 | 2 | 2412.11840（此前被我误判为池内 2411.05863，实为不同论文）、2503.01655 |

### B. arXiv HTML 搜索页（`searchtype=abstract`）
`abs:"ARIS" AND sonar` → 5（0 收录；5 条里只有 2511.13922 与本文有关，2108.06800 在 Lead 池，2109.10664 是鱼类声学相机、2606.03638 是编码理论误命中）；`UXO` → 11（0）；`"forward-looking sonar" AND detection` → 22（与 API 同）；`sonar AND "knowledge distillation"` → 4（0）；`sonar AND "pseudo-label"` → 4（1）；`sonar AND "domain adaptation"` → 3（1）；`sonar AND "synthetic" AND detection` → 26（1）；`SonarCloud` → 2（0，无该 FLS 数据集的 arXiv 版）；`"Cross-Modality Object-Level Knowledge Distillation"`（searchtype=all）→ **0 结果，CMOLD 本身无 arXiv 预印本**。

### C. 非 arXiv 检索（exa + Crossref/OpenAlex/Zenodo/PMC）
| 目的 | 手段 | 结果 |
|---|---|---|
| CMOLD 是否开放获取 | OpenAlex `works/doi:` + Crossref `message.license` | `is_oa=True, oa_status=gold`，license `CC-BY-4.0` |
| CMHD 全文入口 | Crossref + MDPI/PMC 直连 | MDPI 403；PMC13417324 200 |
| DFKI UXO 论文 | Crossref + OpenAlex + exa | Crossref/OpenAlex 判 closed，但 exa 找到 DFKI 官方 PDF（Cloudflare 质询） |
| CMHD / CMOLD / UXO 论文的引文网络 | OpenAlex `filter=cites:W...` | 分别 1 / 5 / 11 条，逐条列出，见下 |
| 竞争路线非 arXiv 论文 | Crossref 单条核验 DOI | 见第 3 节第 5 小节（9 条，含 3 条引用 CMOLD 的 closed access 文章） |
| 失败记录 | `web_search`（402+回显 key，弃用）、`advanced_search engine=bing`（返回无关中文结果，弃用）、tavily（429 daily cap）、Semantic Scholar（429） | 均未用于结论 |

---

## 候选清单

> 等级：**A** = 应进正文相关工作、直接支撑论证；**B** = 值得引一句（数据集协议/域差/背景）；**C** = 边缘相关，仅在需要举例时引。
> 「核验状态」列：`id_list 核验` = 用 arXiv API `id_list=` 取回并人工比对标题、`<published>`、`<updated>` 一致。

| 等级 | arXiv ID | 标题 | 首次提交日 | 场所 | 相关性一句话（落在具体论证点） | 核验状态 |
|---|---|---|---|---|---|---|
| A | 2412.11840 | Sonar-based Deep Learning in Underwater Robotics: Overview, Robustness and Challenges | 2024-12-16 | arXiv；期刊版 IEEE JOE 2025（10.1109/JOE.2025.3531933） | 声呐深度学习综述，明确把「训练数据有限 + 声呐固有噪声」列为本领域主要瓶颈——「为什么要跨模态监督」的主引证 | id_list 核验 v1（仅 v1，无更新） |
| A | 2603.21071 | CTFS: Collaborative Teacher Framework for Forward-Looking Sonar Image Semantic Segmentation with Extremely Limited Labels | 2026-03-22 | CVPR 2026 Findings（comment 自述） | 前视声呐上的**教师-学生**框架：1 个通用教师 + 多个声呐专用教师 + 跨教师可靠性评估抑制噪声伪标签；FLSMD 上 2% 标注即比 SOTA +5.08 mIoU——本论文「教师给声呐学生」最难绕开的同期工作 | id_list 核验，最新 v4（2026-11-05） |
| A | 2604.00383 | Mine-JEPA: In-Domain Self-Supervised Learning for Mine-Like Object Classification in Side-Scan Sonar | 2026-04-01 | CVPR 2026 MACVi Workshop | 水雷类目标首个域内自监督预训练：仅 1170 张无标注 SSS 图，二分类 F1 0.935 > 微调 DINOv3 的 0.922，3 类 0.820；且显示域内 SSL 会让基础模型掉 10–13 点——支撑「声呐域内信号比外来大模型更值钱」 | id_list 核验 v1 |
| A | 2503.01655 | Can Optical Denoising Clean Sonar Images? A Benchmark and Fusion Approach | 2025-03-03 | arXiv | 9 个光学去噪模型逐一迁到声呐，5 数据集 × 4 检测器（含 YOLOX）基准 + 互监督多源融合——直接检验「光学架构能否迁到声呐」，是 camera→sonar 蒸馏可行性论证的前提 | id_list 核验，最新 v2（2025-07-20） |
| A | 2304.11875 | Underwater object classification combining SAS and transferred optical-to-SAS Imagery | 2023-04-24 | arXiv | 7052 对 SAS/光学图像上做光学→声学影像迁移，用影/亮几何形状描述子克服两模态强度与成像差异——**光学→声学监督迁移的直接先例** | id_list 核验 v1 |
| A | 2609.04411 | AquaBEV: Monocular Underwater BEV Occupancy with 3D Sonar Supervision | 2026-09-03 | arXiv | 跨模态监督方向相反（声呐监督相机）：31.4 Visible IoU / 38.6 Observed IoU，比最强迁移基线 +4.0/+4.3——说明「跨模态监督」本身不限于 camera-teacher 一种方向 | id_list 核验，最新 v2（2026-09-12） |
| A | 2310.01667 | STARS: Zero-shot Sim-to-Real Transfer for Segmentation of Shipwrecks in Sonar Imagery | 2023-10-02 | arXiv | 纯仿真训练、不做真实微调即超最佳基线 +20%（形变场 + 异常体融合）——sim-to-real 域差能被压到什么程度的关键证据 | id_list 核验 v1 |
| A | 2406.07189 | RGB-Sonar Tracking Benchmark and Spatial Cross-Attention Transformer Tracker | 2024-06-11 | arXiv | 50 序列 >87000 框的 RGB–声呐配对集；提出 SRST 把 RGB 图转成「声呐样显著图」造伪配对训练——fusion 路线 + 合成配对，两件事都踩在本论文的假设上 | id_list 核验，最新 v3（2024-06-26） |
| A | 2410.08612 | Synth-SONAR: Sonar Image Synthesis with Enhanced Diversity and Realism via Dual Diffusion Models and GPT Prompting | 2024-10-11 | arXiv | 双扩散 + GPT prompt 生成声呐图像以补数据多样性——「合成声呐数据能否训练检测器」的可引证起点（本论文最可能被问的替代方案） | id_list 核验 v1 |
| B | 2303.12946 | Underwater Camouflage Object Detection Dataset | 2023-03-01 | arXiv | 1972 张，分 UW-R（光学）与 UW-S（声呐）两部分——少见的成对 RGB/声呐标注集，可作「配对数据稀缺」的量化例子 | id_list 核验 v1 |
| B | 2603.13585 | Sonar-MASt3R: Real-Time Opti-Acoustic Fusion in Turbid, Unstructured Environments | 2026-03-13 | ICRA 2026 | 浊度 <0.5 至 >12 NTU 范围内实时声-光融合，是 fusion 路线在 ICRA 2026 的最新代表（部署期也要相机） | id_list 核验 v1 |
| B | 2404.18663 | Terrain characterisation for online adaptability of automated sonar processing: Lessons learnt from operationally applying ATR to sidescan sonar in MCM applications | 2024-04-29 | UACE 2023（Kalamata） | 显示 ATR 在非良性海底条件下迅速退化，用两种在线地形表征提升 MCM 可解释性——「域差来自海底/环境而非模型」的现实证据 | id_list 核验 v1 |
| B | 1706.09858 | What's Mine is Yours: Pretrained CNNs for Limited Training Sonar ATR | 2017-06-29 | OCEANS 2017 Anchorage（MTS/IEEE） | 最早的「声呐样本少 → 借预训练 CNN」路线（SAS 多示例检测）——把「跨域借力」写成本领域既有传统的引证 | id_list 核验 v1 |
| B | 2005.04621 | A Comparison of Few-Shot Learning Methods for Underwater Optical and Sonar Image Classification | 2020-05-10 | Global OCEANS 2020 | 首个同时比较水下光学与 side-scan 声呐的 few-shot 研究，FSL 显著优于微调迁移——支持「模态不同则迁移策略要变」 | id_list 核验，最新 v2（2020-10-26） |
| B | 2101.03603 | Target Detection and Segmentation in Circular-Scan SAS Images using Semi-Supervised Convolutional Encoder-Decoders | 2021-01-10 | arXiv（投稿 IEEE JOE） | 多分支编解码器在半监督下做 CSAS 检测/分割，5 类真实数据；明确指出自然图像模型需改造才适配成像声呐 | id_list 核验，最新 v4（2022-02-17） |
| B | 2607.23770 | A Comparison of Data Augmentation Methods for Training Deep Neural Networks on Synthetic Aperture Sonar | 2026-07-26 | ICA 2026 | 系统比较多种（含物理动机）增强与 transformer 架构：增强有效但并非全都有效——避免「加增强就涨点」的过度声明 | id_list 核验，最新 v3（2026-07-29） |
| B | 2606.06130 | Towards Realistic 3D Sonar Simulation | 2026-06-04 | arXiv | 仿真 3D 声呐与真实港区数据对标，量化剩余 sim-to-real gap——若审稿人问「为何不用仿真补数据」，这是可引的答案 | id_list 核验 v1 |
| B | 2510.03353 | Sonar Image Datasets: A Comprehensive Survey of Resources, Challenges, and Applications | 2025-10-02 | SIBGRAPI 2025（4 页短文） | 按 SSS/FLS/SAS/MBES/DIDSON 与任务制表，是「公开标注数据稀缺」最省事的一句引证 | id_list 核验 v1 |
| B | 2210.06535 | Development of a Simulation Environment for Evaluation of a Forward Looking Sonar System for Small AUVs | 2022-10-12 | OCEANS 2019 Seattle（DOI 10.23919/OCEANS40490.2019.8962650） | 光线追踪的高保真 FLS 模型 + 仿真环境（波束参数评估）——FLS 仿真工具链的经典入口 | id_list 核验 v1 |
| B | 2504.00159 | SonarSplat: Novel View Synthesis of Imaging Sonar via Gaussian Splatting | 2025-03-31 | IEEE RA-L 2025（DOI 10.1109/LRA.2025.3627089） | 用 3D 高斯 + 声学反射/饱和属性渲染 range/azimuth 声呐图并显式建模 acoustic streaking——「可微渲染出发声呐图」的现成工具 | id_list 核验，最新 v3（2025-11-03） |
| C | 2409.07004 | Performance Assessment of Feature Detection Methods for 2-D FS Sonar Imagery | 2024-09-11 | arXiv | 在 5 种真实声呐设备上评估局部特征检测器，结论是 RGB 检测器不适配声呐斑点噪声——可用于「跨模态不能直接搬」的一句话 | id_list 核验 v1 |
| C | 2108.01111 | Pre-trained Models for Sonar Images | 2021-08-02 | Global OCEANS 2021 | 每类 10–30 样本即可迁移，并跨 Gemini 720i 验证——少样本声呐检测的早期量化结果 | id_list 核验 v1 |
| C | 2511.13922 | Self-Supervised Compression and Artifact Correction for Streaming Underwater Imaging Sonar (SCOPE) | 2025-11-17 | WACV 2026（comment 自述） | 指出斑点/运动模糊/混响/声影影响多达 98% 的声呐帧，自监督联合压缩+伪影校正——可用于「声呐成像退化」的背景句 | id_list 核验，最新 v2（2025-12-02） |

> 说明：本表所有标题均逐字取自 `export.arxiv.org` 返回的 `<title>`（含原有标点冗余，如 `CTFS :` 的空格），未做改写；「相关性」列的一句话由 `<summary>` 压缩而来，不是原文。

### 已核验但按 Lead 指示不重复收录（已在 Lead 的 14 篇池）
`2403.09313`（YOLOX-ViT + KD for SSS）、`2603.15200`（Physically Motivated KD for SSS geometric correction）、`2410.10554`（ROSAR）、`2212.00352`（UATD 多波束 FLS 数据集）、`1907.00734`（objectness）、`1709.02600`（objectness proposals）、`2108.06800`（ARIS Explorer 3000 海洋垃圾分割）、`2107.10504`（External-Memory low-shot FLS）、`1910.05374`（旋转不变沉船识别）、`2308.11633`（SAS SSL 进展）、`2609.01738`（UAV 热红外 UXO 筛查）、`2411.05863`、`2410.12953`、`2111.08379`。

### 排除表内在本次检索里反复命中的（用于说明「这一桶已被库里占满」）
`2608.25367` RSFusionDet（RGB–声呐多模态检测）、`2608.27795` uScenes（RGB+3D 声呐数据集）、`2605.19712`（physics-informed 声呐仿真）、`2609.18100`（GAN 合成声呐数据的任务相关评估）、`2609.14025` Quantum-Gated LiteSSD、`2608.22072` SNN FLS 检测、`2601.12715` RSOD（极少标注）、`2505.06694`、`2506.01445`、`2503.22880`。

---

## 非 arXiv 可得性核查

> 结论口径：只写「我实际请求到了什么」。`403`/`202` 均如实记录，不推断「不存在」。

### 1. CMOLD（IEEE Access，DOI 10.1109/ACCESS.2026.3666096）——**开放获取，但脚本拿不到 PDF**
- 许可与 OA 状态：OpenAlex `works/doi:10.1109/access.2026.3666096` → `is_oa=True`、`oa_status=gold`、`cited_by_count=5`；Crossref → `license: https://creativecommons.org/licenses/by/4.0/ (vor)`。**是 CC-BY 的 gold OA，可以合法取 PDF。**
- 直连结果（2026-11-12 实测）：
  - `https://ieeexplore.ieee.org/document/...` HEAD → **202**（WAF/Akamai 挑战页，非真实文章页）；
  - `https://ieeexplore.ieee.org/iel8/.../11397899.pdf` HEAD → **301** 跳 `stamp/redirect.jsp`（防盗链跳转）。**`curl.exe` 拿不到正文，需要浏览器会话或先过 Cloudflare/Akamai 挑战。**
- **无 arXiv 预印本**：`searchtype=all` 搜 `"Cross-Modality Object-Level Knowledge Distillation"` → 0 结果；`abs:sonar AND abs:"knowledge distillation"` 4 条也不含它。**因此按 AGENTS.md 第 8 条，本项目拿不到该文的 LaTeX 源码，只能有 PDF/HTML。**

### 2. CMHD（MDPI Sensors 26(14):4340，DOI 10.3390/s26144340）——**CC-BY，PMC 可读，MDPI 直连 403**
- Crossref：CC-BY-4.0，出版日 2026-07-08，作者 Qiao / Liu / Liu / Hao / Ren；OpenAlex `gold`，`cited_by_count=1`（唯一引用者 2608.19710，在排除表内）。
- `https://www.mdpi.com/1424-8220/26/14/4340` → **403**（Cloudflare 拦截脚本）。
- `https://pmc.ncbi.nlm.nih.gov/articles/PMC13417324/` → **200**；页面 meta 实测 `citation_title=Lightweight Underwater Sonar Object Detection via RGB-Guided Heterogeneous Distillation`、`citation_doi=10.3390/s26144340`，正文 PDF 相对链接 `pdf/sensors-26-04340.pdf`（即 PMC 上可下 PDF）。
- LaTeX 源码：MDPI 只提供 PDF / HTML / XML(JATS)，**没有正文 LaTeX 源**（作者模板包不是本文源码）；PMC OA 打包服务 `oa.fcgi?id=PMC13417324` 返回 **404**（该文尚未进 OA subset 或 id 未收录），因此可确认「有 PDF/HTML，无 LaTeX」。

### 3. DFKI UXO 数据集论文（OCEANS 2024 - Halifax，DOI 10.1109/OCEANS55160.2024.10754316）——**出版方付费墙，作者机构页有 PDF 但需过 Cloudflare**
- Crossref：`OCEANS 2024 - Halifax`，2024-09-23，作者 Dahn / Bande Firvida / Sharma / Christensen / Geisler / Mohrmann / Frey / Sanghamreddy / Kirchner；`license: stm-asf`（非 OA）。
- OpenAlex：`is_oa=False`、`oa_status=closed`、`cited_by_count=11`（引文网络见第 4 节）。
- 但 exa 检索到 DFKI 官方全文 PDF：`https://www.dfki.de/fileadmin/user_upload/import/15133_20240801_oceans24_uxo_dataset_full.pdf`，HEAD → **403 `Cf-Mitigated: challenge`**（Cloudflare 质询）。**浏览器可过，脚本不行——属"公开可得但需浏览器"，不是"不存在"也不是"纯订阅"。**
- 配套数据（Zenodo 13778485）核实：标题 `An Acoustic and Optical Dataset for the Perception of Underwater UXO`，v1.1，2024-09-23，`access_right: open`，license `bsd-3-clause`，`related_identifiers` 含 `10.1109/OCEANS55160.2024.10754316 (isDescribedBy)`；文件 `data_export_recordings.7z` 16.6 GB、`data_processed.7z` 61.5 GB、`data_export_polar.7z` 16.5 GB、`sample.7z` 1.7 GB；累计下载 17261。另有旧版 record 11068046（v1.0.0）。代码仓 `github.com/dfki-ric/uxo-dataset2024`（24 stars，2026-11-04 更新，仓库无 license 字段）。

### 4. IEEE OCEANS / ICRA / IROS 近两年「sonar object detection」「underwater multimodal detection」的公开 PDF
- **OCEANS 2025/2024**：在我检索到的范围内，绝大多数为 IEEE Xplore 付费（Crossref 无 CC 许可）。例外两类：(a) 作者机构/项目页挂 PDF——如上面 DFKI 那篇（Cloudflare 质询）；(b) 数据集类论文有 arXiv 版——`2212.00352`（UATD，OCEANS 2022）、`2503.22880`（Marine Debris FLS 数据集，排除表）。`SonarCloud: A Simulated Forward Looking Sonar Dataset`（OCEANS 2025，DOI 10.23919/oceans59106.2025.11245033）在 arXiv 上**未检索到**（`SonarCloud` 只命中两篇代码静态分析论文），OpenAlex 判 `closed`。
- **ICRA 2026**：命中 1 篇直接相关且有 arXiv 预印本——`2603.13585` Sonar-MASt3R（opti-acoustic 融合）。**ICRA/IROS 的正式版 PDF 通常不公开，但 arXiv 版可取。**
- **IROS**：本次检索**未检索到**「sonar object detection」相关条目（`abs:"forward-looking sonar" AND abs:detection` 的 22 条与 `abs:sonar AND abs:"multimodal"` 的 21 条中均无 IROS 标注）。**这只说明我的查询没命中，不说明 IROS 没有此类论文**；若要写"近两年 IROS 无相关工作"必须先补检索 DBLP。

### 5. 非 arXiv 但在本轴上是直接竞争路线的期刊论文（Crossref 逐条核验，均 CC-BY-4.0 gold，可合法取 PDF）
| 论文 | 出处 | 日期 | DOI | 与本论文关系 |
|---|---|---|---|---|
| Chrs-Net: A Dual-Stream YOLO Network for Underwater RGB–Sonar Object Detection | JMSE 14(12):1094 | 2026-06-13 | 10.3390/jmse14121094 | 双流 RGB–声呐检测，fusion 路线正面对手 |
| Dual-Modal Vision–Sonar Object Detection for Underwater Robots Based on Deep Learning | JMSE 14(4):338 | 2026-02-10 | 10.3390/jmse14040338 | 同上，机器人平台 |
| AOPQ-Net Acoustic–Optical Proposal Query Network for Underwater Multimodal Object Detection | Remote Sensing 18(16):2703 | 2026-08-11 | 10.3390/rs18162703 | 引用 DFKI UXO 数据集做声-光多模态检测，**离本论文最近的一篇非 arXiv 工作** |
| FS2-DETR: Transformer-Based Few-Shot Sonar Object Detection with Enhanced Feature Perception | JMSE 14(3):304 | 2026-02-04 | 10.3390/jmse14030304 | 单模态少样本路线（替代 KD 的另一种解法） |
| SCFusion: Cross-modality underwater object detection via vision guided sonar–camera feature fusion | Ocean Engineering | 2026 | 10.1016/j.oceaneng.2026.126793 | 引用 CMOLD，closed access |
| MFTCA-Net: multimodal fusion temporal context-aware network for underwater object detection | JMST | 2026 | 10.1007/s00773-026-01162-7 | 引用 CMOLD，closed access |
| Automated underwater dam damage detection using sonar–camera multimodal image fusion | Automation in Construction | 2026 | 10.1016/j.autcon.2026.107216 | 引用 CMOLD，closed access |
| SonarNet: A Real-time Anchor-free Detector for Sonar Object Detection | ICUS 2024, pp.77–83 | 2024-10-18 | 10.1109/icus61736.2024.10840081 | 单模态检测器基线，**closed**（Crossref 无 CC 许可） |
| Sonar Image Generation by MFA-CycleGAN（GAN 造声呐图提升检测） | IEEE JOE 2024 | 2024 | 见 IEEE Xplore | 与「合成声呐数据」同题，**closed**，本次只有元数据 |

（其余只取到元数据、未逐条打开页面的：CenterNet-Saccade `10.3390/s24020665`、ESL-YOLO / UWS-YOLO / YOLO-variant-eval（JMSE 2025–2026）、Small-Sample YOLOv11 `10.3390/rs18203459`、SAS 高精检测（Remote Sensing 2025）、Sonar-DETR（IWACCE 2025，closed）、DSB-net（Neurocomputing 2026，closed）、Transformers & Ensembles for SSS（DLR elib 2025，closed）。这些**没有**做 PDF 可获取性实测。）

---

## 与本论文的定位判断（fusion 路线 vs distillation 路线）

1. **两条路线的体量差距是实质性的，不是修辞**：引用 CMOLD 的 5 篇中 4 篇是 fusion（SCFusion、声呐-相机大坝检测、MFTCA-Net，加 CMHD 自身走蒸馏）；引用 DFKI UXO 数据集论文的 11 篇里，AOPQ-Net 与 DualPathUNet 亦为声-光融合。2026 年新出的 JMSE 三篇（Chrs-Net、Dual-Modal、FS2-DETR）也全在「双流融合」或「单模态少样本」——**在我检索到的范围内，没有一篇走跨模态 KD**（这是检索结论，不是穷尽性断言）。
2. 因此**不能**把差异点写成「首个做水下跨模态检测」（fusion 一派已占位），也**不能**写成「首个用声呐做 UXO 检测」（DFKI 数据集论文 2024 已给基线）。可辩护的差异点只剩两条：**推理期只需要声呐**（fusion 要求配准相机流；本论文部署单模态），以及 **object-level KD + recording-level split 的协议**。
3. 「光学资源能否迁到声呐」这条前提已被前人打过样：`2304.11875`（光学→SAS 影像迁移）、`2503.01655`（光学去噪器迁声呐 + YOLOX 基准）、`2406.07189`（RGB→"声呐样"显著图造伪配对）。**这些是相关工作，不是卖点**——本论文若声称"首次验证光学→声呐监督可行"会被直接反驳。
4. sim-to-real 与合成数据已有一条完整替代路线（`2310.01667` STARS、`2606.06130` Isaac Sim、`2210.06535` 仿真环境、`2410.08612` Synth-SONAR、`2504.00159` SonarSplat），审稿人极可能问"为什么不用仿真/合成补数据"。**建议在 limitation 里正面回答，而不是回避。**
5. 最近的邻居要显式区分，否则会被当增量：`2603.21071`（FLS 上的协作教师 + 2% 标注，但任务是语义分割、且教师仍在声呐域内）与 CMHD（同数据集、同方向，但 RGB 教师 + 异构蒸馏）。**本论文相对 CMHD 的差异必须落在协议（recording-level split）和 object-level 实现上，不能只剩"我们也做蒸馏"。**
6. 一个可加分的定位：`2609.04411` 显示跨模态监督可以反向（声呐监督相机），本论文是正向（相机监督声呐）——**"监督方向可互换、但声呐侧监督更省标注"** 这个论点目前没人正面写过，是可占的缝隙。

---

## 建议优先读的 5 篇

| 序 | arXiv ID | 为什么先读 |
|---|---|---|
| 1 | `2603.21071` | **最像的同期工作**：FLS + 教师-学生 + 极限少标注。读完才能回答"你和 CTFS 有什么不同"（它做分割、教师仍在声呐域，你做检测、教师跨模态）。 |
| 2 | `2412.11840` | 我检索到的唯一一篇把"声呐数据少 + 噪声大"写成系统论述的综述，第 2–3 节的引证骨架可以直接从这里抄结构。 |
| 3 | `2406.07189` | fusion 路线的代表（RGBS50 配对集 + 交叉注意力 + 合成配对），而且是**双向**的：既能当对照，也解释了为什么"配对数据"是 fusion 的命门。 |
| 4 | `2604.00383` | 声呐域内自监督的硬数据（1170 张无标注 → F1 0.935；域内 SSL 还会让基础模型掉 10–13 点）。若审稿人问"为什么不直接自监督/基础模型"，答案在这里。 |
| 5 | `2503.01655` | 把"光学架构/权重迁到声呐"做成对照实验的那一篇（9 个光学去噪器 × 5 数据集 × 4 检测器，含 YOLOX）。本论文整个 camera→sonar 前提的可行性证据，也是限制条件。 |

备选（若时间允许）：`2609.04411`（反向跨模态监督，第 6 条定位的弹药）、`2310.01667`（sim-to-real 上限）、`2607.23770`（增强到底有没有用）。

---

## 附：本轴的空白（写引言时可用）

- **在我检索到的范围内，arXiv 上没有"水下 UXO + 声呐 + 目标检测"的论文**：`abs:UXO`（11 条）、`abs:"unexploded ordnance"`（15 条）、`abs:"unexploded" AND abs:underwater`（2 条）三次查询的命中全是陆上/航空/电磁感应（EMI）UXO 分类或弹坑检测。水下 UXO 检测的公开工作只存在于**非 arXiv**：DFKI 数据集论文（OCEANS 2024）、CMOLD（IEEE Access 2026）、CMHD（Sensors 2026）——**这个空白本身可以写成一句有分量的 motivation**。
- 真正的缺口不是"没人做融合"，而是"**没人验证过融合与蒸馏在同一数据/同一划分协议下的可比性**"：CMHD 用了 per-class 10 轨迹 × 100 帧、6:2:2，CMOLD 用 recording-level split，两者都自称"同一数据集"却不可直接比。**这是本论文最该讲清楚的差异点。**
