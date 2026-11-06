# 00 总报告：我方项目与 CMOLD 的逐项对齐，及 baseline 差距归因

> 任务：对齐本项目（VSFusionDistill，主线 F2）与 CMOLD（IEEE Access 2026, Aydogmus & Erer, ITU）的 baseline，探究为何我方读数与论文相差很大。
> 边界：**本次只做调查，不修改任何代码、配置、数据、权重、结果文件。** 报告内所有"建议"均为待批方案，未执行。
> 方法论来源：联网学习的深度学习/科研类 skill 方法论（systematic-debugging 4 阶段、ml-pipeline-workflow、rigorpilot-skills 的 ai-research-explore / ai-research-reproduction、deep-learning-experiment-principles、research-rigor-principles、experimental-design 的 Fisher 三原则）。映射与落地见 `调查/04_方法论与复现实验建议.md` 第 1 章。

---

## 0. 结论先行

### 0.1 一句话结论

我方 B0 与 CMOLD 的 baseline 之间**不存在"同一考场下的 4 倍能力差"**；现有证据支持的是一个更朴素但更重要的判断：**两者的评测集根本不是同一个东西**，而论文的评测集身份在论文里不可知（全文 15 页无 test set，唯一规模数字只声明 "nearly 4700 image pairs … used for training and validation"）。在这个前提下，我方读数低的第一原因不是模型弱，而是**我方在一个严格得多的考场里考试**。

### 0.2 四条给决策者看的结论

1. **不要把我方 val 的 0.3760 与论文的 0.943 放进同一张表并排。** 两者不是同一考场：同一份 E13-0 权重，只把评测集从"文献式考场"（val_id，帧级留出）换成"录音级留出"（val），AP50 就从 0.7174 掉到 0.3760，差 34.1 个点。这 34.1 点是**协议差异**，不是模型能力差异。
2. **协议层差距是真实且独立于声呐标签问题的，不应被声呐话题掩盖。** 证据：相机支路是全项目最干净的一路（相机图全标注、每帧恰 1 个目标、无伪标签、无投影几何、无 blob/projected 口径之争），在完全相同的评测装置下，我方相机 AP50 = 0.8101（三种子纯光学模型均值 0.8471），而论文的相机教师 AP50 = 0.997。**连最有利模态都差 15 到 19 个点**，这部分差距不可能由声呐 GT 质量解释，只能由协议层（评测集身份与构成、训练时长、教师权重来源）解释。
3. **CMOLD 的核心机制（跨模态 objectness 蒸馏）在我方有一个定位明确、可检验的发力格子，但这不等于"机制本身有效"。** val 里的三条 bomb 录音（`2023-09-20_171105` / `2023-09-20_174439` / `2023-09-20_180722`）呈现"相机 AP50 = 1.000、声呐 AP50 = 0.139 / 0.000 / 0.158"——目标在相机里清晰可见、位置已知，声呐端却几乎不报框。这正是跨模态 objectness 蒸馏（rank 对齐 objectness MSE）在原理上唯一能发力的位置。反面约束同样明确：bomb 在训练侧只有 7 条场次，蒸馏能否救得动是开放问题；**并且 CMHD 的实测表明，同一套机制在其自己的严格设定（轨迹级 6:2:2、类别均衡）下相对"不蒸馏"基线是 −1.7 个 mAP 点的负增益**（详见 3.7 节），所以"机制移植"必须先在严格设定下做 A/B，不能假定方向为正。
4. **"低 3.5 倍"这个说法本身就该改写。** 把三种起点（我方单 seed blob 0.2696 / 三 seed blob 0.2584 / 最严 all 口径 0.1769）各加回实测的"换考场"增益 A = +0.3414 后，残差是 0.3320 / 0.3432 / 0.4247 点，即真实能力差落在 **1.54× ~ 1.82×**，而不是 3.5×；仅"换考场"一项就占总分差（0.6734）的 **50.7%**，剩下的**未解释区间 0.3320 ~ 0.4247 点相当于总分差的 49.3% ~ 63.1%**，归属三项（GT 语义差 / 帧级切分 / 类别均衡与训练量），其中两项必须实测才能定量（详见 3.8.1）。

### 0.3 差距分层与可量化证据

| 层 | 机制 | 量化证据 | 该层能解释的差距 | 置信度 |
| --- | --- | --- | --- | --- |
| L0 评测集身份不可知 | 论文无 test set，唯一规模数字限定为 train+validation | `调查/cmold_numbered.txt:575`；全文 "test set" 0 命中 | **不可分解**（无法直接测量，只能做区间） | 存在性高，量级不可知 |
| L1a 协议层 · 域外泛化 | 录音级留出 vs 论文未述划分方式 | 同一权重 E13-0：val_id AP50 0.7174 → val 0.3760 | **AP50 −0.341**（我方内部实测） | 高 |
| L1b 协议层 · 类别与场景构成 | 27 条录音、类别极不均衡 vs CMHD 侧 95 轨迹/类别均衡 | 我方 train bomb 仅 7 条场次；val blob 中 mortar 占 61%（322/528） | 未量化 | 中 |
| L1c 协议层 · 相机侧残差 | 最有利模态仍差 → 协议层独立存在 | 相机 AP50 我方 0.8101 / 0.8471 vs 论文教师 0.997 | **AP50 −0.150 ~ −0.187** | 中高（跨论文口径） |
| L2 GT 标签层 | 声呐 GT 一半是自造投影框，且实测偏移 | 46.4% projected；中位偏 25.4 px；63.4% 超半框宽 | 对 all 口径 **AP −0.07 ~ −0.13**（已由主口径 blob 规避） | 高 |
| L3 任务难度层 · 类别轴 | 类别混淆，不是不均衡 | 类无关 AP50 0.3805 > 类感知 AP50 0.2696 | **AP50 −0.111** | 高 |
| L3 任务难度层 · 回波表观 | 回波斑块物理尺寸逐录音漂移 ~2.3 倍；blob 框不是目标框 | bomb 44.7–101.4 mm、grenade 35.8–77.5 mm、mortar 35.8–80.5 mm | 未量化（与 L3 类别轴部分重叠） | 中 |
| L4 实现层 · 训练密度与增广 | 每图曝光 305→52；无 Mosaic/MixUp/翻转；尺度只抖一个轴 | `configs/_base_/datasets/paired_uxo.py:6,16-28`；`configs/f2/e13_b0_sonar_only_dense_yoloxs.py:16-18,30-31` | 未量化 | 中 |
| L5 指标层 | maxDets 依赖默认、无 TTA、EMA 略低 | maxDets 走 pycocotools 默认 [1,10,100]，与论文口径一致 | ≤ 1–3 点 | 高（可排除为主因） |

### 0.4 已排除项（不再是差距来源候选）

以下八项在本次调查中逐条闭环，**排除**为 baseline 差距的主因，详见第 4 章：优化器与学习率家族、评测装置（dataloader/预处理器/GT/COCOeval）、训练闭环（train 自评 AP50 = 1.0000）、`sonar_fov_deg=130.0` 与 `M0Mapping`、`uxo_projection.py:785` 写死 441 行、COCOeval maxDets 实际取值、EMA 权重取舍、跨模态蒸馏项的实现路径。

### 0.5 永久不可知项（需要用"敏感性区间"而非"复现"来对待）

论文侧有 30 项可复现性缺口（完整清单见 `调查/01_CMOLD论文规格.md` 第 7 章）。其中真正影响结论的有六个：评测集身份与划分单位、伪标签阈值 γ、蒸馏权重 λ、输入分辨率与 resize 策略、伪标签规模 `|D_P|`、top-K 上界。**这六项在论文里无解**，因此"复现 CMOLD 的 0.797"在字面意义上不可达成，可达成的是"在我方考场下，按 CMOLD 机制复现其相对增益方向与量级"。

### 0.6 附带发现：口径治理是当前最高优先级的问题（不是科学问题）

调查过程中发现，同一天产出的四份仓库文档对"我方主口径是 `gt=blob` 还是 `gt=all`"说法互相矛盾，且主台账 `doc/experiments.md` 对本次全部关键读数**零入账**（grep 实测：0.2696 / 0.2584 / 0.589 / 0.8471 / 0.1769 / 0.1869 / 0.3959 / 0.8275 / 62,928 出现次数均为 0）。此外被广泛引用的"AP50 0.2696 / AP 0.11"是**跨 seed 跨口径混搭**（0.2696 是本机单 seed blob，0.11 是 5090 三 seed blob mAP，同一次运行的 mAP 其实是 0.1066）。

**含义**：这会让正确的读数被误读为错误的能力结论，且在写任何对比表之前必须先收敛。完整的 7 条口径治理问题（G-1 ~ G-7，含证据行号、影响与建议动作）见第 5.0 节。

---

## 1. 调查范围、方法与证据边界

### 1.1 方法论来源与本报告的落地方式

联网检索到的 skill 没有一个专门做"深度学习复现/基线差异排查"，因此本报告的骨架由六个 skill 的方法论拼接而成：

| 方法论来源 | 核心原则 | 在本报告的落地 |
| --- | --- | --- |
| obra/superpowers `systematic-debugging` | Reproduce → Isolate → 5 Whys → Fix&Verify；不随机改动 | 第 2 章先做逐项对齐（Reproduce/Isolate），第 3 章做归因（5 Whys），第 4 章列排除项，第 5 章列待验证 |
| `ml-pipeline-workflow` | 目标澄清 → 数据准备/验证 → 训练 → 验证 → 部署；可复现性、数据版本化与血缘 | 第 2 章按"数据→标注→划分→模型→训练→增广→蒸馏→指标"流水线逐段对齐；第 3.1 节标注数据版本与血缘 |
| rigorpilot `ai-research-explore` | 外环冻结 task/dataset/benchmark/evaluation/budget；内环一次一个有界改动；不把探索性增益当可信复现 | 第 5 章把建议全部写成"有界改动 + 锚点对比 + 停止条件"；明确区分"复现读数"与"区间估计" |
| rigorpilot `ai-research-reproduction` | README-first；Trusted Target Selection；Patch Boundary；"record deviations instead of changing semantics" | 第 2 章逐项标注"论文给出/未给/推断"；第 4 章把"排除"当作结论记录；第 5 章建议优先走命令行/环境变量路径，不动架构与损失语义 |
| `deep-learning-experiment-principles` | 保持 baseline 含义与评测协议；记录实验上下文；不隐藏失败；区分 trick 与贡献 | 第 3.1 节列出我方 baseline 的完整实验上下文（ckpt/seed/git/python/config/split）；第 3.8 节不把"换考场"包装成提升 |
| `research-rigor-principles` | 不静默破坏可比性；工程修复不冒充研究贡献 | 第 2.10 节显式给出"可比/部分可比/不可比"三档判定；第 5 章把"对齐协议"与"改模型"分开成两类方案 |
| K-Dense `experimental-design` | Fisher 三原则：随机化/重复/区组；伪重复是最致命错误；重复层级必须等于随机化层级 | 3.2 节把"录音=随机化单元，帧=伪重复"作为我方与文献的根本分歧；6.2 节要求所有复现实验按录音级区组重复 |

### 1.2 证据分级图例

本报告每个数字都带来源与等级，请按等级决定引用强度：

- 【实测】本人本次在本地数据或源码上直接跑脚本/读原始文件得到（一手）。
- 【仓库】仓库既有 `doc/**` 或 `results/**` 记录（我方一手，但由既往实验产生）。
- 【论文】CMOLD 原文，行号指 `调查/cmold_numbered.txt`（833 行带行号版），表格数值均已回 PDF 原文图（`调查/cmold_t1..t6.png`）逐张核对。
- 【二手】CMHD 后继论文等交叉印证（`调查/cmhd_*`），只作旁证，不作主结论。
- 【推断】基于以上证据的推理，未直接观测。
- 【未知】双方都缺，需实验补。

### 1.3 本次调查没有做的事（只读边界）

- 未修改任何源码、配置、数据、权重、结果文件。仓库 `git status --porcelain` 在调查前后均只显示任务开始前既有的 12 个未跟踪文件（`doc/` 下 8 个 md、`doc/loss_trend/e13_t_teacher_dense_seed0.csv`、`tools/config_gate.py`、`tools/dashboard/`、`tools/subset_eval.py`）。
- 未训练任何模型，未开封 test 录音（`split= test` 的 1,500 帧只做了元数据统计，不读图、不算指标）。
- 未启动任何长任务或服务进程。
- 本机无 `pycocotools`（`ModuleNotFoundError: No module named 'pycocotools'`），因此所有 COCO 指标均引用仓库/远端既有评测产物，未本地复算 AP；本机只做了纯几何/统计类的一手复算。

### 1.4 本报告的文档分工

| 文档 | 内容 |
| --- | --- |
| `调查/00_总报告_我方与CMOLD对齐与差距归因.md`（本文） | 对齐矩阵 + 差距归因 + 排除项 + 未决项 |
| `调查/01_CMOLD论文规格.md` | CMOLD 逐项规格、全部表格数字、30 项可复现性缺口、CMHD 交叉印证 |
| `调查/02_我方_pipeline_审计.md` | 我方配置/数据集/几何/评测/模型五层审计，376 行，每条带 `路径:行号` |
| `调查/03_基线数字复核.md` | 我方 baseline 数字的原始出处、口径一致性检查、矛盾清单 |
| `调查/04_方法论与复现实验建议.md` | skill 方法论映射 + 分级实验方案（只提方案，不执行） |

---

## 2. 逐项对齐矩阵

读法：每张表按"CMOLD 口径 | 我方口径 | 是否可比 | 证据"排列。"是否可比"三档定义见 2.10。

### 2.1 数据与采集

| 维度 | CMOLD 口径 | 我方口径 | 可比性 | 证据 |
| --- | --- | --- | --- | --- |
| 数据集来源 | UXO 多模态公开集（Dahn et al., OCEANS-Halifax 2024） | 同源 UXO | 可比 | 【论文】`:139-142`,`:544-549`；【仓库】`aodet/datasets/converters/uxo_layout.py:17-40`（5 类源目录映射到 3 类） |
| 声呐设备 | ARIS Explorer 3000 + ARIS Rotator AR3 | 同源 | 可比 | 【论文】`:515-516` |
| 相机设备 | GoPro Hero 8 | 同源 | 可比 | 【论文】`:515-516` |
| 运动机构 | 吊车（Granty crane） | 同源 | 可比 | 【论文】`:515-516` |
| 源规模 | "nearly 4700 image pairs"，明确限定 train+validation；**无 test set** | 94 条录制轨迹、6,246 帧配对（`D:/pby/uxo-full/paired/`） | 规模可比，**身份不可比** | 【论文】`:575`；【实测】`frame_meta.csv` 6,246 行 |
| 源域 | ARIS raw 与 polar 两域都存在；学生输入用哪一域**未指明** | 实际用 polar（128×N 行） | 不可比 | 【论文】`:544-549`、`:372-376`【推断】学生为 polar；【实测】本地 sonar.json 宽度全 128 |
| 每帧目标数 | 论文未直接给；CMHD 对同集描述"each frame containing exactly one target" | 每帧恰好 1 个框（sonar 6,246 anns / 6,246 images；camera 同） | 可比 | 【实测】`sonar.json`、`camera.json` |
| 类别数与类别名 | 3 类：100lbs_aircraft_bomb / incendiary_grenade / mortar_shell | 同 3 类，同命名（category_id 1/2/3） | 可比 | 【论文】`:624`,`:627`；【实测】`camera.json` categories |
| 类别均衡 | 未给 | 训练 blob 帧 bomb 332 / grenade 493 / mortar 671；val blob 322/131/75（mortar 占 61%） | 不可比 | 【论文】未给；【实测】frame_meta × sonar.json 交叉统计 |
| 采集条件覆盖 | 不同角度/位置/深度，**不同 gain / resolution / range** | focus 10 档（493–648）、gain 5 档（0/5/10/12/15）、行数 4 档（441/603/771/780）、量程 3 档 | 覆盖度我方更细，但**我方增广未覆盖** | 【论文】`:584-587`；【实测】94 条 `aris_file_meta.yaml` |
| 相机-声呐配对核验 | 论文称人工核验过对应关系 | 我方逐录音标定投影，自研 | 可比 | 【论文】`:580-581`；【仓库】`aodet/datasets/converters/uxo_projection.py:749-793` |

### 2.2 声呐 GT 来源（本任务最关键的对齐层）

| 维度 | CMOLD 口径 | 我方口径 | 可比性 | 证据 |
| --- | --- | --- | --- | --- |
| 相机图标注 | 全标注 | 全标注 | 可比 | 【论文】`:282-283`；【实测】camera.json 6,246 anns |
| 声呐图初始标注 | **完全无标注** | **完全无标注** | 可比 | 【论文】`:258-260`；【仓库】`aodet/datasets/converters/uxo_projection.py:1-48`（文档串 "The UXO dataset ships camera GT boxes only"） |
| 声呐 GT 构造法 | 小人工集 `D_L` → 初检器 f → 置信度阈值 γ 生成伪标签 `D_P` → 质检（合并/删除矛盾框、随机目检、f 在 `D_L∪D_P` 微调）→ `D_final = D_L ∪ D_P` | 逐录音标定几何投影；blob 门限内取实测回波连通域，否则用投影框（source 二值 blob/projected） | **机制不同** | 【论文】`:270-360`；【仓库】同上 |
| 伪标签阈值 γ | **未给** | 无伪标签（无此环节） | 不可比 | 【论文】`:328-329` |
| 人工子集规模 `N_L` / 伪标签规模 `\|D_P\|` | **均未给** | — | 不可比 | 【论文】式(1) 只定义符号 |
| 声呐 GT 质量 | 论文未量化；CMHD 侧对应做法额外做人工目检剔除错位 | 11,558 个声呐框中 46.4% 为投影框；投影框到亮回波中心中位偏 **25.4 px**、**63.4%** 超半框宽；blob 框中位偏 5.6 px | 不可比 | 【仓库】`doc/logs/2026-11-05-projected-label-alignment.md:11-12,28-31` |
| GT 框的语义 | 目标框（人工标注 / 已知目标长度） | blob 框 = 回波连通域本身（`im >= percentile(im,99.5)` 后连通域，丢 area<20 / w<4 / h<4 / w>45 / h>70）；投影框按 `CLASS_LENGTH_M={1:1.20,2:0.40,3:0.55}` m 生成并夹到 40×60 px | **语义不同** | 【实测】`aodet/datasets/converters/uxo_projection.py:214-231`；【实测】blob 框物理高度同类跨录音离散 ~2.3 倍（bomb 44.7–101.4 mm） |
| 训练实际使用的声呐 GT | 论文：伪标签 `D_final`（全量） | 我方：`sonar_gt_sources=("blob",)`，**只用 blob** | 部分可比 | 【仓库】`configs/_base_/datasets/paired_uxo.py:57` |
| 弱回波帧的处理 | 论文未述 | blob-only 训练下，弱回波帧留在 batch 里**当诚实负样本**（对比度 projected +0.1..+7 vs blob +12..+51） | 不可比 | 【仓库】`configs/_base_/datasets/paired_uxo.py:51-57` 注释 |

### 2.3 划分与评测集身份（差距第一来源）

| 维度 | CMOLD 口径 | 我方口径 | 可比性 | 证据 |
| --- | --- | --- | --- | --- |
| 是否有 train/val/test 三分 | **未给**；全文 "test set" 0 命中；"split" 仅 1 命中，指 KD 对比内部一致 | train / val / test / val_id 四列 | 不可比 | 【论文】`:575`、`:610-612` |
| 划分单位（帧级 vs 轨迹级） | **未给**；全文无 trajectory/sequence | **录音级**（trajectory-level）留出，按类别×几何分层约 6:2:2 | **根本分歧** | 【仓库】`tools/split_uxo_recordings.py:2-38,48-89` |
| 随机种子 | **未给**（全文 seed 0 命中） | seed 默认 0（CLI），`deterministic=False` | 不可比 | 【仓库】`tools/train.py:33,53` |
| 每类样本量 | 未给 | 见 2.1 | 不可比 | 【论文】TABLE 4 无样本量列 |
| 我方划分实例 | — | uxo_full 平台：train 27 录音 / 1,650 帧、val 900、test 900、val_id 378；dense 平台：同 27 录音 / 7,960 帧、val 900、test 900、val_id 1,798 | — | 【仓库】`configs/f2/e13_b0_sonar_only_dense_yoloxs.py:3-8`；【实测】frame_meta.csv |
| 泄漏检查 | 不可查 | **零泄漏**：train 与 val_id 同 27 条录音（val_id 是录音内帧级留出），val 10 条、test 10 条与 train 不相交 | — | 【实测】`split_manifest.json`：94 → train 27 / val 10 / test 10 / excluded 47 |
| 被排除的源轨迹 | 未述 | 47 条被排除：行残差 p50 > 28 px（9 条）、缺标定（37 条）、方位残差 rms 3.35°（1 条） | — | 【实测】`D:/pby/uxo-full/split_manifest.json` |

### 2.4 模型与教师

| 维度 | CMOLD 口径 | 我方口径 | 可比性 | 证据 |
| --- | --- | --- | --- | --- |
| 检测器框架 | YOLOX（arXiv:2107.08430） | YOLOX（mmdet 风格自建双流实现） | 可比 | 【论文】`:96-99`,`:794-795` |
| 学生容量 | YOLOX-S 9.0 M / 26.8 GFLOPs | YOLOX-S（deepen 0.33 / widen 0.5、out_indices (2,3,4) + PAFPN + decoupled head, 3 类） | 可比 | 【论文】`:611-616`；【仓库】`configs/_base_/models/two_stream_yolox_s.py:25-46` |
| KD 基线里的教师容量 | YOLOX-M 25.3 M / 73.8 GFLOPs | 论文侧对应教师在我方为 YOLOX-L | 部分可比（我方更大） | 【论文】`:610-616`；【仓库】`configs/f2/e10_t_b2_yoloxl_teacher.py:36-57` |
| 跨模态教师 | 与学生同架构、同输入分辨率、权重冻结 | 教师 = YOLOX-L 两流（cam/sonar 双流 + CrossAttnFusion embed 256 / 8 heads）；跨模态教师头在 dense val 上 all AP 0.1247 / blob 0.2015 | 部分可比 | 【论文】`:392-393`,`:348`；【仓库】`doc/logs/2026-11-05-gt-metric-decision.md:35-37` |
| 教师权重来源 | **未给** | 我方教师在 dense 平台训练所得（非 COCO 预训练直用） | 不可比 | 【论文】`:282-283`,`:610-616` |
| 相机/声呐特征关系 | 不做任何几何或像素级对齐 | CrossAttnFusion：sonar 作 query、camera 作 key/value，2D 正弦位置编码必需，LayerScale γ 零初始化（起始等价 sonar-only）；相机特征不重采样 | 可比（都是"不硬对齐"） | 【论文】`:372-380`；【仓库】`aodet/models/fusion/cross_attn.py:86-113` |

### 2.5 训练超参（这一层完全对齐，不是差距来源）

| 维度 | CMOLD（TABLE 2） | 我方 | 可比性 | 证据 |
| --- | --- | --- | --- | --- |
| Epochs | 200 | 304（uxo_full，62,928 iter）/ 63（dense，62,685 iter） | 迭代预算可比，epoch 不可直接比 | 【论文】TABLE 2；【仓库】`configs/f2/e11_b0_sonar_only_yoloxs.py`、`e13_b0_sonar_only_dense_yoloxs.py:16-18` |
| Batch size | 8 | 8 | 可比 | 同上 |
| Optimizer | SGD | SGD（nesterov） | 可比 | 同上 |
| Initial LR | 0.00125 | 0.01×8/64 = **0.00125** | **完全一致** | 同上 |
| Final LR | 6.25e-5 | cosine eta_min = lr×0.05 = **6.25e-5** | **完全一致** | 【仓库】`configs/_base_/schedules/schedule_f2.py` |
| Momentum | 0.9 | 0.9 | 可比 | 同上 |
| Weight decay | 5e-4 | 5e-4 | 可比 | 同上 |
| 其他 | 未给：label smoothing / EMA / 早停 / 模型选择准则 / 多卡 / AMP | clip_grad 35、EMA 1e-4、无早停、ckpt 由 CLI 指定 | 不可比 | 【论文】`:512`,`:553` |
| 环境 | Python 3.8.20 / NVIDIA L4 / CUDA 12.9 / PyTorch 2.4.1 / Ubuntu 20.04 | Python 3.10.12 / 5060Ti 与 5090 混合 / 权重在远端 5090 | 不可比（但不构成能力差） | 【论文】TABLE 1；【仓库】`results/2026-11-04_sonar_b0/run_meta.txt` |

### 2.6 数据增广

| 维度 | CMOLD 口径 | 我方口径 | 可比性 | 证据 |
| --- | --- | --- | --- | --- |
| 增广清单 | **仅一句** "Data augmentation was applied to increase the robustness" | 可枚举：行轴尺度抖动 (0.6–1.8, prob=1.0)、同步翻转 prob=0.0、相机退化等级采样 | **不可比**（我方可见 vs 论文不可见） | 【论文】`:294`；【仓库】`configs/f2/e09_s0_b0_jitter_yoloxs.py` |
| Mosaic / MixUp | 未述 | **明确关闭**（W3 决策） | 不可比 | 【仓库】`configs/_base_/datasets/paired_uxo.py:6` 注释 "No Mosaic/MixUp anywhere (§4.4(2))" |
| 翻转 | 未述 | 关闭（极坐标左右翻转改变方位，语义破坏，关闭是合理选择） | 不可比但我方更保守 | 【仓库】`AOPairedSyncFlip(prob=0.0)` |
| 尺度抖动轴 | 未述 | **只动行轴**（测距轴），不动波束轴 | 不可比 | 【仓库】`aodet/datasets/transforms/paired_geometric.py:137-225` |
| 声呐物理增广（增益/焦距/量程） | 未述 | **无**；但我方数据显示 focus 10 档、gain 5 档、量程 3 档构成域偏移，val 录音的 (类别,行数,focus,gain) 在 train 中精确匹配数仅 0–4 条 | 不可比 | 【实测】94 条 `aris_file_meta.yaml` + frame_meta 交叉统计 |
| 相机退化 | 未述 | B0 链 d0..d4 各 0.16 + dinf 0.20；B2/Bcam/教师 d0=1.0 | 部分可比 | 【仓库】审计第 2 章；【仓库】`aodet/datasets/transforms/pack_paired.py:119-121` |

### 2.7 蒸馏机制（CMOLD 的核心，我方复现的落脚点）

| 维度 | CMOLD 口径 | 我方口径 | 可比性 | 证据 |
| --- | --- | --- | --- | --- |
| 匹配规则 | **不按 IoU 匹配**，按 objectness 降序排序后第 k 位对第 k 位（rank 对齐） | objectness 加权软目标 KL（背景 floor 后与 YOLOX obj loss 同量级） | 机制族相近（均为 objectness 对齐），细节不同 | 【论文】`:419-431`；【仓库】`aodet/models/losses/branch_kd.py:1-33` |
| L_obj | 对 top-K 逐位置的 objectness **MSE**；α = 0.5 | 我方为加权软目标 KL（背景 floor） | **不等价**：MSE vs KL 目标函数不同 | 【论文】`:484-506`,`:530-533` |
| L_cls | 温度软化 τ=2 的 KL，×τ²；β = 0.5 | score_kd 逐类 Bernoulli KL（σ(cls)·σ(obj)） | 机制族相近，τ 语义不同 | 【论文】`:451-473`,`:534-535`；【仓库】同上 |
| K | K = min(两侧保留数)，**上界未给**；保留标准未定义 | 未见对应显式 K 约束 | 不可比 | 【论文】`:405`,`:419-421`,`:475-482` |
| 框回归是否蒸馏 | **否**（跨模态几何失配） | **从不蒸框回归** | **完全一致** | 【论文】`:134-137`,`:378-380`；【仓库】`branch_kd.py:1-33` |
| 总损失 | `L_total = L_det + λ·L_CMOLD`，**λ 未给** | 有 KD 路由但 λ 口径需另定 | 不可比 | 【论文】`:548-551` |
| 特征蒸馏 | 论文无 | 有（前景掩码 MSE） | 我方额外项 | 【仓库】同上 |
| 蒸馏增益来源 | 消融：仅 objectness 0.661→**0.794**；仅分类 0.661→0.771；full 0.797 → **增益约 98% 来自 objectness 项** | — | — | 【论文】TABLE 6,`:681-696` |

### 2.8 指标与后处理

| 维度 | CMOLD 口径 | 我方口径 | 可比性 | 证据 |
| --- | --- | --- | --- | --- |
| AP 定义 | AP@0.50 / AP@0.75 / AP@[0.50:0.95] | pycocotools COCOeval，同一套 | **可比** | 【论文】`:556-567`；【仓库】`aodet/evaluation/per_branch_metric.py:89-103` |
| AR 定义 | AR@1 / AR@10 / AR@100（不同 maxDets） | 只设 `ev.params.imgIds`，**未显式设 maxDets** → 走 pycocotools 默认 [1,10,100] | **口径一致（依赖默认）** | 【论文】同上；【仓库】`per_branch_metric.py:85-103`（本次已核） |
| 类别感知 | 论文按类报（TABLE 4），总体 AP 口径未明示是否类感知 | **类感知**（逐 category 平均）；另提供类无关视图 | 需注意 | 【仓库】`per_branch_metric.py:94-103`,`:170-187` |
| NMS / max_per_img / score_thr | **未给**（全文 "NMS" 0 命中） | score_thr 0.01 / NMS 0.65 / max_per_img 100 / nms_pre 1000 | 不可比（量级 1–3 点） | 【仓库】`configs/_base_/models/two_stream_yolox_s.py:89-96` |
| TTA / 多尺度 | 未述 | **无** | 不可比（我方偏保守） | 【仓库】`tools/test.py:177-185` |
| 模型选择 | 未给（200 ep 训完 or 取最佳） | ckpt 由 CLI 指定，**无 best 逻辑** | 不可比 | 【仓库】`tools/test.py:126-135` |
| GT 口径 | 论文只有一套声呐 GT（伪标签） | sonar 侧 **all** 与 **blob** 双口径；主口径 = blob，all 降为诊断 | 我方更细，但 all/blob 差 0.07–0.13 | 【仓库】`doc/logs/2026-11-05-gt-metric-decision.md`；【仓库】审计第 5 章 |
| split 口径 | 未述 | `--split` 可多值，`val,val_id` 是**合并读数**（n_img 1278），不可与纯 val / 纯 val_id 混引 | — | 【仓库】`tools/test.py`；【仓库】`doc/logs/2026-11-04-literature-baseline-protocol-comparison.md:99-102` |

### 2.9 输入分辨率与预处理

| 维度 | CMOLD 口径 | 我方口径 | 可比性 | 证据 |
| --- | --- | --- | --- | --- |
| 输入分辨率 | **全文 15 页无任何分辨率数字**（640/448/416/320/"resize"/"input size" 0 命中）；只声明教师学生共享同一分辨率 | 640×640，`keep_ratio=False`（逐侧独立缩放） | **不可比（论文缺项）** | 【论文】`:392-393` + 全文 grep；【仓库】`configs/_base_/datasets/paired_uxo.py:14` |
| resize 几何后果 | 未述 | 源 128×N 行 → 640×640：波束轴 ×5.00、测距轴 ×0.8205（441 行）/ ×1.0000（780 行）；**各向异性 6.09×**（441 行录音）；源宽高比中位 1.29 → resize 后 7.87 | — | 【实测】本地 sonar.json 尺寸与框统计 |
| 归一化 | 未述 | 无 mean/std 归一化；`pad_size_divisor=32` | 不可比 | 【仓库】`configs/_base_/datasets/paired_uxo.py` |
| 物理分辨率一致性 | 未述 | m/px(row) = aris_sampleperiod × aris_soundspeed / 2 = 4 × 1491.28 / 2 ≈ **2982.56**，**与行数无关**；量程随行数变化（780 行 2.33 m / 603 行 1.80 m / 441 行 1.32 m） | — | 【实测】94 条 `aris_file_meta.yaml` + frame_meta |
| 尺度先验错位 | 未述 | train 各类 resized blob 高中位 bomb 23.0 / grenade 30.5 / mortar 20.3；val 侧 mortar 三条录音比值 1.93/1.86/1.71，bomb 0.68/0.54/0.96，grenade 0.81/0.90/0.86 | — | 【实测】resized 框高分组统计 |

### 2.10 对齐矩阵总结：三档可比性判定

**可比（可直接并列引用）**

- 检测器框架与学生容量档位（YOLOX-S）；
- 优化器家族与学习率（0.00125 → 6.25e-5，SGD / bs 8 / mom 0.9 / wd 5e-4 完全一致）；
- AP/AR 的指标定义与 maxDets 口径；
- "跨模态不做几何对齐、框回归不参与蒸馏"这一设计原则；
- 每帧恰 1 个目标、3 类、数据同源。

**部分可比（需在表中并列并注明）**

- 声呐基线数字：AP50 可作量级参照，AP@[0.50:0.95] 不可；
- 相机支路：我方 0.8101 / 0.8471 vs 论文教师 0.997，差 15–19 点，只能作为"协议层残差存在"的证据，不能当作能力结论；
- 蒸馏增益方向：可对照"objectness 主导"这一结构，不能对照绝对值。

**不可比（禁止并列引用）**

- 我方 val 0.3760 vs 论文 0.943（评测集身份不同）；
- 我方 val AP@[0.50:0.95] 0.1318 vs 论文 0.661；
- 声呐 GT 质量与语义（伪标签 vs 回波连通域框）；
- 划分单位（录音级 vs 论文未述）；
- 增广强度（我方可见 vs 论文一句带过）。

---

## 3. 差距归因

### 3.1 我方 baseline 的完整实验上下文（引用任何我方数字前必读）

| 项 | 值 |
| --- | --- |
| checkpoint | `work_dirs/baseline_sonar_only_seed0/epoch_304.pth`（E13 dense 链用 `epoch_63.pth`） |
| config | `configs/f2/e11_b0_sonar_only_yoloxs.py`（dense 变体 `e13_b0_sonar_only_dense_yoloxs.py`） |
| seed / git / python | 0 / `14f3536196a959b62942ccf36adf710b5ba5f217` / 3.10.12 |
| 平台 | uxo_full（train 27 录音 / 1,650 帧 / 304 ep / 62,928 iter）与 dense（27 录音 / 7,960 帧 / 63 ep / 62,685 iter） |
| 主口径 | 声呐支路、类感知、blob 口径；`--split val` |
| 读数（seed 0，uxo_full） | val all AP 0.0718 / AP50 0.1869；val blob AP 0.1066 / AP50 0.2696（AP75 0.063、AR@100 0.1503） |
| 读数（seed 0/1/2，uxo_full，仓库汇总口径） | AP 0.0715、AP50(all) 0.1769±0.028、AP50(blob) 0.2584±0.031 |
| 读数（dense，E13-0） | AP 0.1318、AP50(all) 0.2567、AP50(blob) 0.3760 |
| 读数（dense，val_id 文献式考场） | AP 0.4236、AP50 0.7174 |
| 读数（相机支路） | B0 camera d0 gt=all AP 0.5088 / AP50 0.8101；Bcam 三种子 AP 0.5300 / AP50 0.8471±0.022 |
| 失败对照 | train blob AP 0.9818 / **AP50 1.0000**（27/27 条录音每条 AP50 均为 1.0000） |

来源：【仓库】`results/2026-11-04_sonar_b0/**`、`results/2026-11-04_camera_b0/ap_summary_304.json`、`doc/logs/2026-11-05-consolidated-teacher-student-table.md`。

### 3.2 协议层：最大的一块，且有三条独立证据

**证据一：同一份权重，换考场就差 34.1 点。**

| 评测集 | 身份 | E13-0（dense）读数 |
| --- | --- | --- |
| val_id | train 录音**内**的帧级留出（与文献"帧级随机切分"最接近的合法口径） | AP 0.4236 / AP50 **0.7174** |
| val | **录音级**留出（10 条从未见过的录制） | AP 0.1318 / AP50 **0.3760** |
| 差 | 同一权重、同一 GT、同一评测代码 | AP50 **−0.3414**（−47.6% 相对） |

这不是模型变弱，是考场变难。对照 CMHD 后继论文：CMOLD 方法在其困难子集上 0.796→0.461（−33.5 点），与我方 val-ID→val 的 −33 点同量级——两个独立来源观测到同一量级的"换考场跌幅"，说明这是跨数据集的普遍现象，而不是我方的实现缺陷。【仓库】`doc/logs/2026-11-04-literature-baseline-protocol-comparison.md:22-30`

**证据二：论文评测集比我们的干净得多，而且可以从论文自己的数字反推。**

论文相机教师三个 AR 完全相同（AR@1 = AR@10 = AR@100 = 0.969），这在数学上意味着**每帧一个目标且几乎全部检得出**（recall 在 maxDets=1 就已到 0.969）。我方 val 的 900 帧里，**只有 528 帧（58.9%）拥有可用 blob GT**，其余 372 帧的声呐 GT 或是弱回波投影框（标签本身不可用），或无标注。同一个"评测集"概念，难度差一个层级。

**证据三：连相机支路都差 15–19 点。**

相机这一路没有伪标签、没有投影几何、没有 blob/projected 口径之争，是我方链路里最干净的一路。同一评测装置下：

- 我方 B0 相机头 d0 gt=all：AP50 **0.8101**（AP 0.5088）；Bcam 三种子：AP50 **0.8471±0.022**（AP 0.5300）；
- 论文相机教师：AP50 **0.997**（AP@[.5:.95] 0.958，三个 AR 均 0.969）。

差 **0.150 ~ 0.187**。这部分差距**在原理上不可能由声呐 GT 质量解释**，只能归到协议层：评测集身份与构成、每类样本量与均衡性、训练时长与增广、教师权重来源（论文未披露是否用 COCO 预训练权重微调）。

**结论**：协议层至少解释 AP50 **0.15–0.19** 的差距，且这一层是论文侧不可知、我方侧严格执行的落差。**在我方考场里做出的任何"复现 CMOLD"读数，都不应以 0.797 为目标，而应以"同一考场下的相对增益"为目标。**

### 3.3 GT 标签层：机制清楚，但主口径已规避

**规模**：11,558 个声呐框中 46.4% 为几何投影框（train 3,655/7,960、val 372/900、test 476/900、val_id 863/1,798）。

**质量**：投影框到亮回波中心的中位偏移 25.4 px（框宽 40 px），**63.4% 的投影框偏移超过半框宽**；blob 框中位偏移仅 5.6 px。场次级系统偏移 dx −29.7..+16.3 px、dy −57.5..+30.4 px，`2023-09-21_160551` 的 dx IQR 达 62.5 px（不可整体平移）。标定基点漂移（converter 先裁剪 → projector 后跑，裁剪后约 90 帧重拟合，P 漂移 0.9–2.5 m）导致终版 7/47 条越 20 px 门；补救后 45/47 条在门内，val/test 干净（10 条 val 全窗 p50 ≤ 15.1 px）。【仓库】`doc/logs/2026-11-05-projected-label-alignment.md:11-12,28-31`、`doc/logs/2026-11-03-e11-final-gt-calib-drift.md:7-17`

**框语义**：这是比偏移更深一层的问题。blob 框来自 `im >= np.percentile(im, 99.5)` 后的连通域——**它量的是回波斑块，不是目标**。实测物理高度：bomb 44.7–101.4 mm、grenade 35.8–77.5 mm、mortar 35.8–80.5 mm，同一类跨录音仍有约 2.3 倍离散。而论文与 CMHD 的声呐框是**目标框**（人工标注或按已知目标长度生成）。这意味着我方声呐任务的"定位"在语义上是"定位回波"，与论文的"定位目标"不是同一个量纲，而 AP@[0.50:0.95] 对框语义差异的惩罚远重于对"检出"的惩罚。

**已采取的规避**：主口径已从 gt=all 改回 gt=blob（all 比 blob 低 0.07–0.13，相对 26%–37%），且训练只用 blob。**因此这一层对"当前主读数"的影响已经大部分被规避掉了**；它的影响体现在两处：一是 all 口径的诊断读数；二是 blob-only 训练把弱回波帧当诚实负样本，让"没检出"从漏检变成正确行为——这在 blob 口径下不扣分，但会让模型学不到"弱回波也是目标"的边界。

**残余**：投影框对 val 全口径仍有影响（372 帧），以及对"回波 ≠ 目标"的语义错配仍然存在，无法通过换口径消除。

### 3.4 任务难度层：类别轴与回波表观轴

**类别轴（可量化）**：val blob 逐类 AP50 = mortar 0.4893 / grenade 0.2947 / **bomb 0.0248**；总体 0.2696；而**类无关 AP50 = 0.3805**。类无关比类感知高 0.111（相对 41%），说明**除了类别不均衡（类别先验导致地板效应），还存在真实的类别混淆**（同一目标被判成别的类）。这两条是不同机制，必须分开归因：前者是数据分布，后者是模型判别力。

在个别录音上类别轴是结构性失效：某录音类无关 AP50 0.9247、top-1 IoU 中位 0.62（定位已解），但预测类别 cat2:cat3 = 1347:145，类感知 AP50 掉到近 0。【仓库】`doc/experiments.md:458`

**回波表观轴（机制级，量化不完整）**：同一条录音内，回波对比度与检出率并不同向——失败场次对比度 +2.79 / +3.50 / +5.18 / +4.41 与成功场次 +1.83…+4.94 **完全重叠**；最亮的 `124915`（+5.18）反而只有 0.029。同时"几乎不出框"与"出了框但全错"是两种失效：某场次 33 回波帧只报 10 框、20 帧只报 1 框、22 帧报 8 框。【仓库】`doc/logs/2026-11-05-sonar-failure-session-diagnosis.md`

**失败的三条 bomb 录音是本任务最干净的信号**：

| 录音 | 类别 | 有回波帧 | GT 框中位 px | 回波对比度 | 声呐 AP50 | 相机 AP50 |
| --- | --- | --- | --- | --- | --- | --- |
| `2023-09-20_171105` | bomb | 33 | 43×19 | +4.41 | 0.139 | **1.000** |
| `2023-09-20_174439` | bomb | 20 | 18×15 | +3.50 | **0.000** | **1.000** |
| `2023-09-20_180722` | bomb | 22 | 30×26 | +2.79 | 0.158 | **1.000** |

失败恰好落在"相机全对、声呐全错"的格子。两条失效机制不同：`174439` 只输出 2 个预测（几乎不检出）且是 GT 行残差越门的录音（p50 25.8 px），属"标签错位与失效同源"；`124915` 输出 31 个预测但无一匹配，且不在漂移名单内，属类别混淆/回波形态差异嫌疑，**尚未定位**。

**尺度先验错位（部分因素，不是主因）**：val 侧 mortar 三条录音的 resized blob 高比值为 1.93 / 1.86 / 1.71（train 中位 20.3），而这两条恰好是 val 中 AP50 较高的（0.5120 / 0.3767）；两条 AP50 = 0 的录音反而不是尺度偏移最大者（bomb 0.54×、grenade 0.86×）。**结论：尺度错位是部分因素，不能解释整条失效链。**

### 3.5 实现层：训练密度与增广

| 项 | 我方 | 风险 | 证据 |
| --- | --- | --- | --- |
| 每图曝光次数 | uxo_full 约 305 次；dense 约 **52 次** | dense 平台 62,685 iter 与 uxo_full 62,928 iter 预算相同，但训练帧从 1,650 涨到 7,960，单帧曝光降到 1/5.9 | 【仓库】`configs/f2/e13_b0_sonar_only_dense_yoloxs.py:16-18,30-31` |
| 增广族 | 无 Mosaic/MixUp、无翻转、仅行轴尺度抖动 | 27 条录音上的记忆风险（train blob AP50 = 1.0000） | 【仓库】`configs/_base_/datasets/paired_uxo.py:6,16-28` |
| 声呐物理增广 | 无增益/焦距/量程模拟 | focus 10 档 × gain 5 档 × 量程 3 档构成的域偏移未被覆盖 | 【实测】`aris_file_meta.yaml` |
| 空标签帧 | `paired_dataset.py` **不过滤 empty-GT 帧**（全仓 grep `filter_empty|remove_empty|len(boxes_sonar)==0` 无命中） | 大量帧声呐侧标签为空，被当负样本 | 【仓库】`aodet/datasets/paired_dataset.py:104-133` |
| 平台可重建性 | dense 平台的 7,960 帧由**仓库外**的 converter 补丁（`tools/_patch_converter_train_cap.sh`，给 `convert()` 加 `max_frames_per_recording_train`）生成；仓库 HEAD `14f3536` 的 `uxo_to_paired.py` CLI 只有 `--max-frames`（`:541`），**不存在** `max-frames-train` 字样 | 平台不可从仓库重建；GT 一致性还依赖外部 `projection_calib.json` 缓存 | 【实测】`dense_chain.sh:21-24,51,59-62`；【实测】`uxo_to_paired.py:541` |
| 确定性 | seed 默认 0、`deterministic=False` | 单种子读数不可复现 | 【仓库】`tools/train.py:33,53` |

### 3.6 指标层：量级小，可排除为主因

- maxDets：只设 `ev.params.imgIds`，走 pycocotools 默认 [1,10,100]，与论文 AR@1/10/100 一致；
- 无 TTA / 无多尺度（我方偏保守，若论文用了，差距会更大而非更小）；
- EMA 权重 blob AP50 0.2617 vs 非 EMA 0.2696（−0.0079），EMA 未生效原因未定位（仓库记录）；
- NMS 0.65 / max_per_img 100 / score_thr 0.01：论文未给，估计 1–3 点量级。

### 3.7 CMHD 交叉印证：论文读数在其同组后继论文里也复现不出来

这是理解"论文读数"本身的重要背景，也是本报告最重要的免责性结论之一。CMHD（同组，Li 等, Sensors 2026）在**轨迹级 6:2:2、类别均衡（1800/600/600）、固定 640×640、50 epochs** 的自建 UXO† 上，用与 CMOLD 同族的超参（lr 1.25e-3、mom 0.9、wd 5e-4、batch 8）复现 CMOLD。全部数值来自 `调查/cmhd_tables_u8.txt`（Table 1–7）与 `调查/cmhd_params_numbered.txt`（二手抽取，已回原表逐行核对）。

**Table 6（UXO† 上的主对比，全部为 AP@[0.50:0.95]）**

| 方法 | 100 lb GP AN-M30 Bomb AP | 120 mm Mortar Bomb DM81 AP | INC 30 lb MK III Phosphor Bomb AP | mAP | mAR |
| --- | --- | --- | --- | --- | --- |
| YOLOX-Nano | 80.7 | 42.6 | 78.8 | 67.3 | 70.9 |
| **YOLOX-S-Ghost（无蒸馏基线）** | 87.4 | 56.5 | 87.0 | **77.0** | **79.9** |
| KD-YOLOX-ViT | 77.2 | 56.3 | 81.2 | 71.6 | 75.8 |
| **CMOLD** | 89.2 | **49.9** | 87.0 | **75.3** | **78.6** |
| CMHD（本文） | 87.3 | 65.0 | 86.6 | 79.6 | 82.6 |

**这里有一个比"低 4.4 点"更重要的发现**：在 CMHD 自己的严格设定下，**CMOLD（75.3 / 78.6）低于同表的无蒸馏基线 YOLOX-S-Ghost（77.0 / 79.9）1.7 个 mAP 点**。也就是说，CMOLD 的蒸馏机制在帧级随机切分的协议下带来 +20.6% 的增益，但**换到轨迹级留出 + 类别均衡的协议下，它相对"不蒸馏"是负增益**。

**读表须知（两条，避免误用）**：
- CMHD 的 mAR 是 **AR(maxDets=1)**（原文："Since the adopted subset contains one dominant UXO† instance per image, AR is reported with maxDets = 1."），与 CMOLD 的 AR@1/10/100 不是同一指标。**跨两篇论文只能比 mAP，不能比 mAR。**
- "YOLOX-S-Ghost" 在 CMHD 里既指 Table 4/6 的**不蒸馏基线**（77.0 / 79.9），也指 Table 1/3 里**被蒸馏的学生架构**（79.6 / 82.6，教师为 YOLOX-M）。引用时必须带"是否蒸馏"，否则两个 77.0 与 79.6 会被混用。

**Table 4（蒸馏分支消融，同一设定）**同样显示 objectness 主导：

| 蒸馏分支 | mAP | mAR |
| --- | --- | --- |
| 无蒸馏 | 77.0 | 79.9 |
| 仅 cls | 78.7 | 82.3 |
| 仅 obj | **79.8** | 82.5 |
| cls + obj | 79.6 | **82.6** |

（CMHD 自述的最优权重 **λ_cls = 0.1、λ_obj = 0.5**，见 Table 5 `:42` → 79.6 / 82.6；Table 5 `:39` 的 λ_obj=1.0 掉到 75.5 / 78.6。）

**CMHD 对 CMOLD 的评语**：**"CMOLD gains slight precision on easy classes but degrades severely on hard targets, resulting in imbalanced overall performance."**——逐类数据完全对应：CMOLD 在"简单类"（GP AN-M30 Bomb）89.2 > 基线 87.4，但在"困难类"（120 mm Mortar Bomb DM81）49.9 < 基线 56.5，掉了 6.6 点。

**Table 7（困难子集）**：CMOLD mAP 34.0 / mAR 26.7，AP Drop 34.0；CMHD 33.5 / 28.4。

**推论（对本任务的直接影响）**：

1. CMOLD 的 0.797 是一个**协议绑定**的读数，不能作为异构协议下的绝对目标去追；追不到，而且会误导实验设计。
2. 更强的推论：**CMOLD 增益的来源可能不是"跨模态 objectness 蒸馏本身有效"，而是"帧级随机切分放大了跨模态增益"**。因为把切分收紧到轨迹级、类别补齐之后，同一套机制就掉到基线以下了。含义：我方若以 CMOLD 为蓝本做机制移植，**必须先复刻 CMHD 的严格设定**（640×640、轨迹级 6:2:2、类别均衡），否则无法区分"机制无效"与"协议放大了机制"。
3. 因此 CMHD 的设定是本任务**唯一有可比数字的第三方考场**（见 `调查/04_方法论与复现实验建议.md` 的 E2-c）。

### 3.8 归因汇总：把 0.943 → 0.376 的 0.567 差距拆开

AP50 口径、声呐学生、我方用 dense 平台 E13-0 的 blob 口径（0.3760）：

| 段 | 变化 | 归因层 | 证据强度 |
| --- | --- | --- | --- |
| 论文 0.943 → 我方 val_id 0.7174 | −0.226 | 协议层（评测集身份、类别均衡、场景数、教师来源）+ 任务难度层 | 中（跨论文，评测集不可知） |
| 我方 val_id 0.7174 → 我方 val 0.3760 | −0.341 | 协议层（录音级留出 = 域外泛化） | **高（我方内部实测，同权重同代码）** |
| 合计 | −0.567 | — | — |

叠加旁证：相机支路上 0.997 → 0.8471/0.8101 的 **−0.150 ~ −0.187** 差额**不可能由声呐标签解释**，因此协议层至少吃掉 0.15–0.19。

#### 3.8.1 三种起点的残差演算（来自 `调查/03_基线数字复核.md` §3.2）

总差距（AP50，点）：0.943 − 0.2696 = **0.6734**，即论文为我方 **3.50×**。按不同起点做残差演算：

| 起点（我方读数） | 起点值 | 加"换考场"实测 A（+0.3414） | 残差 | 残差倍数 |
| --- | --- | --- | --- | --- |
| 本机单 seed blob | 0.2696 | 0.6110 | **0.3320** | 1.54× |
| 5090 三 seed blob | 0.2584 | 0.5998 | **0.3432** | 1.57× |
| 5090 三 seed all（最严口径） | 0.1769 | 0.5183 | **0.4247** | 1.82× |

若起点改用 all 口径（即不享 blob 的"只评有回波帧"优惠），则还须加回 GT 口径差 **B = +0.0815 ~ +0.0827**（同臂实测，相对 +30.7% ~ +31.5%）；但 A 与 B 不作简单叠加——A 是在 blob 口径下测的，与 all 起点相减属跨口径读法，是三条里最不保守的一条（残差 0.4247）。**因此正确的表述是：已实测的"换考场" A 一项就吃掉总差距的 50.7%（0.3414 / 0.6734），剩下 0.3320 ~ 0.4247 点（占总分差 49.3% ~ 63.1%）是尚未解释的区间，而不是已经归因到的量。**

剩余的 0.33 ~ 0.42 点归属三项，其中两项**必须实测**才能定量：

| # | 残差项 | 量级 | 性质 | 依据 |
| --- | --- | --- | --- | --- |
| C | **GT 语义差**：论文用投影+伪标把帧填满，我方只评 528 帧有实测回波的帧 | 方向确定（我方更难），量级**未知** | 未知/需实测 | 【论文】`cmold_numbered.txt:284-291`；【仓库】`doc/logs/2026-11-05-projected-label-alignment.md:7-11` |
| D | **帧级随机切分**（论文无场次级隔离，我方录音级 27:10:10） | 文档估"落在 0.589 与 1.0 之间"，**无实测数** | 估算（无实测） | 【仓库】`doc/logs/2026-11-04-literature-baseline-protocol-comparison.md:150-163` |
| E | **类别均衡 / 训练量**：论文 ~4,700 对 / 200 ep，我方 dense 7,960 帧 / 62,685 iter（63 ep） | 量级**未知** | 未知/需实测 | 【论文】`:575`；【仓库】`doc/logs/2026-11-05-consolidated-teacher-student-table.md:16-19` |

**结论**：任何把 0.2696 直接对 0.943 写成"低 3.5 倍"的表述，都缺了这 50.7% 的实测口径折算；真实的能力差（待 C/D/E 实测后）落在 **1.54× ~ 1.82×** 区间，而不是 3.5×。

**综合判断（按贡献排序）**：

1. **协议层（评测集身份 + 域外泛化 + 类别/场景构成）** —— 贡献至少 0.34（我方内部实测）+ 至少 0.15（跨模态旁证），是**第一原因**。
2. **任务难度层（类别混淆 + 回波表观漂移 + 框语义错配）** —— 类别轴单独吃掉 0.111（类无关 vs 类感知），回波漂移未量化但机制清楚。
3. **GT 标签层（46.4% 投影框、回波≠目标的框语义）** —— 对 all 口径 0.07–0.13，对 blob 主口径已大部分规避。
4. **实现层（训练密度、增广族、物理增广缺失）** —— 未量化，但训练自评 AP50 = 1.0000 与 val 的大幅跌落是"记忆而非泛化"的典型形态。
5. **指标层** —— ≤ 1–3 点。

**这五个层里，只有第 3 层有"我方单方面可修"的部分；第 1 层是口径问题（要靠"改读法"解决，不能靠改模型）；第 4 层有我方可修的部分（增广与密度）但会破坏与既往 baseline 的可比性，必须走"预登记修订"流程；第 2 层最本质。**

---

## 4. 已排除项清单（逐条给证据，不留悬念）

| # | 候选主因 | 排除依据 | 残留解释力 |
| --- | --- | --- | --- |
| 1 | 优化器 / 学习率 / batch 不一致 | lr 0.00125、final 6.25e-5、SGD、mom 0.9、wd 5e-4、batch 8 **与 TABLE 2 完全一致** | 无 |
| 2 | 评测装置（dataloader/预处理器/GT/COCOeval 代码有 bug） | 同一装置下相机头 AP50 0.8101 正常；声呐头训练闭环正常（train blob AP50 1.0000）；`tools/subset_eval.py` 在本地 GT 上重算的 blob 值与 5090 自记录值**四位小数完全一致** | 无 |
| 3 | 网络/优化器/训练循环无法表达所学 | train blob 27/27 条录音每条 AP50 = 1.0000；EMA 权重也非退化 | 无 |
| 4 | `sonar_fov_deg=130.0` 与实际扇面 ~30° 混用 | `M0Mapping` 只被 `aodet/models/losses/cross_plane_mil.py` 使用，而 `CrossPlaneMILLoss` **只在 tests/ 里实例化**（`tests/test_two_stream_model.py:275,445,463,531`），`two_stream_yolox.py` 未引用 | 无（不在 B0 训练/评测路径） |
| 5 | `uxo_projection.py:785` 写死 441 行截断 GT | 94 条录音 SamplesPerChannel = 441×65 / 780×20 / 603×5 / 771×4；全部 6,246 个框 y1 最大值恰为 441.0；projected 框仅 **6 个（0.2%）** 触及 441（其中 4 个来自 `2023-09-21_125236`）；**blob 框无一超过 441** | 0.2% 的 projected 框 |
| 6 | COCOeval maxDets 与论文口径不一致 | `per_branch_metric.py:85-103` 只设 `ev.params.imgIds`，未设 maxDets → 默认 [1,10,100]，与论文 AR@1/10/100 一致 | 无（仅需在报告中注明依赖默认） |
| 7 | EMA 权重取舍错误 | EMA blob AP50 0.2617 vs 非 EMA 0.2696，差 0.0079 | 0.8 点（EMA 未生效原因另查） |
| 8 | 跨模态蒸馏项实现路径错误 | `branch_kd.py` 从不蒸框回归，与论文一致；objectness 软目标 KL 与论文的 rank-MSE **量纲与目标函数不同**，这是**复现风险**而非已致差距（因为当前主读数是 B0 纯声呐，无蒸馏） | 见 6.3 的复现实验 |

> 补充排除：`dense_chain.sh:51` 传 `--max-frames-train 100000` 而仓库 converter CLI 只有 `--max-frames`（`uxo_to_paired.py:541`）——这不是"差距原因"，而是**平台不可从仓库重建**的证据链一环（见 3.5）。审计待验证项 6（B0 链默认 deg probs）同样对 B0 无影响：`degrade_camera` 只作用于 `img_camera`（`aodet/datasets/transforms/pack_paired.py:119-121`），而 B0 的相机头为 None。

---

## 5. 未决问题清单

### 5.0 口径治理问题（新增，来自 `调查/03_基线数字复核.md`，优先级最高）

这三项不是科学问题，是**传播性风险**：它们会让正确的读数被误读为错误的能力结论。

| # | 问题 | 证据 | 影响 | 建议动作（只提方案） |
| --- | --- | --- | --- | --- |
| G-1 | **同日三份文档主口径互相矛盾**：blob（`doc/logs/2026-11-05-gt-metric-decision.md:3`「对外主口径 = `gt=blob`」）vs all（`doc/logs/2026-11-05-consolidated-teacher-student-table.md:4`「主口径 `gt=all`，`gt=blob` 仅作诊断列」）vs blob（`doc/logs/2026-11-05-literature-comparison-blob.md:5`）;另 `进度/2026-11-05_组会任务对照与现状.md:94-95` 写「与文献同口径的是 all」——与前两份相反 | 四处行号已定位 | 对外报告的"我方主口径"无法自洽，审稿人可据此质疑全部对比 | 定一份《口径总则》，其余文档加一行引用；对外只用一套主口径 + 一行诊断列 |
| G-2 | **"AP50 0.2696 / AP 0.11"是跨 seed 跨口径混搭**：0.2696 = 本机 5060Ti 单 seed blob；0.11 = 5090 三 seed blob mAP 均值；本机同一次运行的 mAP 是 **0.1066** | `results/2026-11-04_sonar_b0/eval_sonar_b0_val/ap_summary.json:18-19`；`remote_5090/doc/experiments.md:592` | 当前被广泛引用的基线数字本身不是一次实验的读数 | 统一写成「本机 seed0：0.2696 / 0.1066」或「5090 三 seed：0.2584±0.031 / 0.1098±0.017」 |
| G-3 | **主台账 `doc/experiments.md` 零入账**：实测 grep，0.2696 / 0.2584 / 0.589 / 0.8471 / 0.110 / 0.1869 / 0.1769 / 0.3959 / 0.8275 / 0.8743 / 0.4284 / 62,928 出现次数**均为 0**；E11 段（L507 起）只有预登记无结果表；§5 冻结区（L661-665）仍写"尚无冻结数据" | grep 实测；该文档 §6 L670「数字可溯源」、L676「出数 24 小时内入账」 | 违反自定纪律；是口径混乱能长期存活的根因 | 把底表按其格式回填 E11 节 |
| G-4 | **效应阈值 0.063 ≠ 公式复算值 0.064**；换 all 口径漂到 0.056 | max(2×0.0316, 0.02) = 0.0632 → 0.063（取整）；all 口径 σ=0.0278 → 0.0556 | P2/P3 的"增益 ≥ 0.063"门槛随口径漂移 | 统一写成 max(2σ, 0.02) 并注明取整，同时标注当前建立在 blob σ 上 |
| G-5 | **"本地单跑 val-ID 0.6333"无产物可追溯** | 全仓 grep 仅命中 `doc/logs/2026-11-04-literature-baseline-protocol-comparison.md:99` 与 `:102`，无对应 ap_summary/ap_breakdown 文件 | 协议文档的核心"换机复现"证据不可核 | 补产物，或在文中标注"产物已清理，仅台账留存" |
| G-6 | **本机相机臂 0.8101 与 5090 Bcam 0.8471 不可作对照**（训练分布不同：DEFAULT AOSampleDegLevel vs d0=1.0） | `results/2026-11-04_camera_b0/run_meta.txt:5`；`doc/logs/2026-11-04-s0c0-degaug-config-deviation.md:13-17` | 若把两者并列引用，等于把配置偏离当成方法差异 | 引用时只取 5090 Bcam 作为纯光学基线；本机臂仅作装置健康度证据 |
| G-7 | **clean8"两个教师都没训过"是脚本注释断言，不是从训练清单推出** | `tools/dashboard/gen_teachers.py:11-13,56-58` | 若旧教师 3 条训练录音含 clean8 其他 6 条，则 clean8 对旧教师不是干净考场 | 补旧教师训练录音名单对照，或把注释改为可核验清单引用 |

### 5.1 我方侧可测（可用只读/短脚本闭环）

| # | 问题 | 为什么要测 | 建议验证方式 |
| --- | --- | --- | --- |
| U1 | `124915`（grenade，最亮回波 +5.18 却 AP50 0.029、31 个预测全错）为何单场失效 | 它是唯一"标签与信号都正常却彻底失效"的场次，是当前最大的未解释异常 | 逐帧看漏检/错检位置是否系统性偏移；查该录音的标定残差与类别轴输出 |
| U2 | EMA 权重为何略低于非 EMA | 0.8 点量级，且与"EMA 是否生效"是实现正确性问题 | 打印 EMA decay 与实际更新次数 |
| U3 | blob 框的"目标语义"可改进空间 | 若 blob 框能逼近目标框，AP@[0.50:0.95] 的天花板会整体上移 | 量化：按类别先验（`CLASS_LENGTH_M`）缩放 blob 框后，在**仅开发集**上估计 IoU 变化（不碰 test） |
| U4 | 采集条件（focus/gain/量程）域偏移的覆盖缺口有多大 | 决定"物理增广"这条实现层修法值不值得做 | 在开发集内按 (行数, focus, gain) 分层统计训练/验证分布距离 |
| U5 | dense 平台可复现性 | 平台不可从仓库重建，任何 dense 读数都难以被第三方复现 | 把仓库外的 converter 补丁以"可审计 diff"形式纳入仓库，或至少在文档中记录补丁哈希 |
| U6 | B0 dense 链所用 ckpt 与最佳 epoch 是否一致 | 无 best 逻辑，手工指定 | 列出 `work_dirs/e13_b0_sonar_only_dense_seed0/` 全部 epoch 的 val 读数 |
| U7 | 论文侧"4700 对"与原 UXO 规模的关系 | 论文唯一规模数字无法解释原数据集规模 | 对照 CMHD 侧记载的"95 条录制轨迹、74,437 声呐帧、48,462 帧配相机图、37,278 相机帧带框标注"【二手】 |

### 5.2 论文侧永久不可知（只能做敏感性区间，不能"复现"）

评测集身份与划分单位（G1/G2）、随机种子（G3）、每类样本量（G4）、"nearly 4700" 的精确构成（G6）、raw 域还是 polar 域（G7）、伪标签阈值 γ（G8）、`D_L` 规模与选帧规则（G9）、`|D_P|` 与接受率（G10）、一致性检查规则（G11）、目检抽检比例（G12）、f 微调超参与是否迭代自训练（G13）、λ（G14）、K 上界与保留标准（G15）、objectness 取 logit 还是 sigmoid 后分数（G16）、KL 是否 detach 教师（G17）、额外匹配过滤项（G18）、跨模态配对采样策略（G19）、输入分辨率与 resize（G20）、增广清单（G21）、label smoothing（G22）、EMA（G23）、早停与模型选择（G24）、多卡/AMP/梯度累积（G25）、教师权重来源（G26）、NMS/maxDets/AP 插值（G27–G29）、教师/学生同架构同分辨率（G30）。

完整表述见 `调查/01_CMOLD论文规格.md` 第 7 章（30 项，按影响程度排序）。

---

## 6. 对主线 F2 的含义

### 6.1 主线前提被重新表述

F2 的命题是"相机退化时相机信息进入声呐支路的收益/来源/代价"。本次调查给这个命题补上了两个此前缺失的前提：

1. **"收益"的基线不是一个弱基线，而是一个在严格考场下的强记忆基线**：B0 纯声呐在训练集上 AP50 = 1.0000，在 10 条未见录音上 0.3760。融合能带来的增益上限因此**不是**"从 0 到 0.94"，而是"在同考场下从 0.3760 往上走多少"。
2. **蒸馏发力点已被定位**：失败集中在"相机 AP50 = 1.000、声呐 AP50 ≈ 0.05–0.16"的三条 bomb 录音。这是 object-level 跨模态蒸馏在原理上唯一能补的格子（相机知道目标存在与大致方位，声呐不需要对齐像素）。但 bomb 在训练侧只有 7 条场次、且 val 里 61% 是 mortar —— **增益期望与数据供给同时受限**。

### 6.2 现有融合读数需要按新口径重读

【仓库】`doc/logs/2026-11-05-consolidated-teacher-student-table.md`：

| 对照 | 读数 | 解读 |
| --- | --- | --- |
| 纯声呐学生 旧平台 → dense | AP50(all) 0.1769 → 0.2567（+45%） | 同预算、不同数据密度 → **数据密度有效** |
| 纯光学 旧平台 → dense | 0.8471 → 0.8180（−3.4%） | 相机端对数据密度不敏感 |
| B2 融合·声呐头 vs B0 纯声呐（旧平台，blob） | 0.2584 → 0.1827（**−29%**） | **当前融合实现是负增益**，这才是 F2 的真问题 |
| 同平台 纯光学 vs 教师相机头 | +1.2% | 平台内一致 |
| 同平台 纯声呐 vs 教师声呐头 | −2.8% | 学生已接近教师声呐头 |

**结论**：融合目前没有把"相机知道目标"这件事传进声呐头，且在旧平台上还掉了 29%。这与 3.4 节的结论一致（失败是"不报框"，而 objectness 蒸馏能直接治"报不报"），说明 **F2 的抓手是对的，但当前实现的 KD 形式（objectness 加权软目标 KL，而非论文的 rank 对齐 MSE）与 rank 对齐机制不匹配**——论文消融显示增益 98% 来自 objectness rank 项，而 rank 对齐的前提是"两侧按 objectness 排序后第 k 位对第 k 位"，这在跨模态下依赖两侧的 objectness 排序具有可比性。我方当前实现是逐位置/逐框软目标，没有 rank 对齐。

**但方向本身也未被验证**：CMHD 在其严格设定下测得 CMOLD 相对无蒸馏基线为 −1.7 mAP 点（3.7 节），说明"跨模态 objectness 蒸馏必然带来正增益"不能作为前提。含义：**F2 的第一步不应是"把 CMOLD 机制移植进来"，而应是"在我方考场下先做一组有界 A/B，证明该机制方向为正"**（见 `调查/04` 的 E2-c 与 E3-a/E3-d）。若该 A/B 证伪，直接止损的成本远低于移植后才发现机制无效。

### 6.3 建议的方向（详见 `调查/04_方法论与复现实验建议.md`，只提方案不执行）

1. **先固化协议，再谈模型**：把"同一考场下的相对增益"写成唯一可比的验收口径（我方 val + val_id 双列，禁止与论文绝对值并列）。
2. **把论文的机制做成有界改动**（Patch Boundary 优先命令行/环境变量/路径，不改架构与训练语义）：
   - 第一刀：把 objectness 项从"加权软目标 KL"改为"rank 对齐 MSE"，并在开发集上做 1 个 seed 的有界 A/B；
   - 第二刀：加 K 上界（论文未给，CMHD 隐含小 K 倾向）；
   - 第三刀：只在 bomb 的 7 条训练场次上做"相机全对、声呐全错"格子的定点诊断，确认增益是否落在预期位置。
3. **每个实验必须带锚点**：B0 同 seed 同 ckpt 重评、train blob AP50（记忆健康度）、val blob AP50 + AP@[0.50:0.95]（主终点）、val_id blob（文献式考场）、相机头 AP50（装置健康度）。
4. **可比性红线**：任何改动后必须重跑同 seed 的 B0 锚点，否则新读数不可与既往 baseline 并列。

---

## 附录 A：证据出处速查

**我方源码与配置（一手核对）**

- 划分：`tools/split_uxo_recordings.py:2-38,48-89`
- 数据集/GT 过滤：`aodet/datasets/paired_dataset.py:104-133`（无 empty-GT 过滤）
- 声呐 GT 生成：`aodet/datasets/converters/uxo_projection.py:1-48,214-231,749-793`（blob 检测、441 截断在 `:785`）
- 转换器：`aodet/datasets/converters/uxo_to_paired.py:146,161-169,172-185,396-405,541`
- 配置：`configs/_base_/datasets/paired_uxo.py:6,14,16-28,51-57`；`configs/_base_/models/two_stream_yolox_s.py:25-46,89-96`；`configs/_base_/schedules/schedule_f2.py`；`configs/f2/e11_b0_sonar_only_yoloxs.py`；`configs/f2/e13_b0_sonar_only_dense_yoloxs.py:3-8,16-18,30-31`；`configs/f2/e09_s0_b0_jitter_yoloxs.py`；`configs/f2/e10_t_b2_yoloxl_teacher.py:36-75`
- 评测：`aodet/evaluation/per_branch_metric.py:85-103,106-137,170-187,273-277`；`tools/test.py:126-135,160-215`
- 模型：`aodet/models/detectors/two_stream_yolox.py:1-20,60-62,104-133,176-181,290-333`；`aodet/models/fusion/cross_attn.py:1-26,36-51,55-84,86-113`；`aodet/models/losses/branch_kd.py:1-33`
- 几何：`aodet/geometry/aris_beam_table.py:117-118`；`aodet/geometry/m0.py:44-64`
- 增广：`aodet/datasets/transforms/paired_geometric.py:59-95,137-225`；`aodet/datasets/transforms/camera_degradation.py`；`aodet/datasets/transforms/pack_paired.py:119-121`
- 链脚本：`dense_chain.sh:21-24,51,59-62`；`e13_b0_chain.sh:41-43`

**我方结果与日志**

`results/2026-11-04_sonar_b0/**`、`results/2026-11-04_camera_b0/ap_summary_304.json`、`results/2026-11-05_platform_compare/**`、`doc/logs/2026-11-05-sonar-failure-session-diagnosis.md`、`doc/logs/2026-11-05-consolidated-teacher-student-table.md`、`doc/logs/2026-11-05-gt-metric-decision.md`、`doc/logs/2026-11-05-projected-label-alignment.md`、`doc/logs/2026-11-05-literature-comparison-blob.md`、`doc/logs/2026-11-04-literature-baseline-protocol-comparison.md`、`doc/logs/2026-11-03-e11-final-gt-calib-drift.md`、`doc/experiments.md:260-262,281,458,572`

**CMOLD 原文**

`调查/cmold_numbered.txt`（833 行带行号）、`调查/cmold_t1.png`…`cmold_t6.png`（TABLE 1–6 原图）、`调查/cmold_eq34.png`、`调查/cmold_eq24.png`、`调查/cmold_alg1.png`、`调查/cmold_pymupdf_text.txt`（15 页全文，供 grep）

**CMHD 旁证**

`调查/cmhd_fulltext.xml`、`调查/cmhd_params_extract_u8.txt`、`调查/cmhd_tables_u8.txt`、`调查/cmhd_snips*.txt`

**数据平台（一手统计源）**

`D:/pby/uxo-full/paired/{sonar.json,camera.json,frame_meta.csv}`、`D:/pby/uxo-full/split_manifest.json`、`D:/pby/uxo-full/extracted/recordings/**/aris_file_meta.yaml`（94 条）

---

## 附录 B：口径自洽的对外数字表（引用请直接取用这一份）

本表是全报告唯一建议对外使用的读数集合，每行标注来源与口径。**禁止把不同行的口径混搭引用**（原因见 5.0 节 G-1 ~ G-4）。

| 用途 | 协议 | 帧数 | AP@[.50:0.95] | AP@0.50 | 出处 |
| --- | --- | --- | --- | --- | --- |
| **我方主读数**（本机 5060Ti，单 seed 0） | B0 纯声呐 / val / 10 条未见录音 / GT=blob / 类感知 | 528（all 900） | **0.1066** | **0.2696** | `results/2026-11-04_sonar_b0/eval_sonar_b0_val/ap_summary.json:18-19` |
| 我方主读数（远端 5090，三 seed） | 同上 | 528（all 900） | 0.1098±0.017 | 0.2584±0.031 | `remote_5090/doc/experiments.md:586,592` |
| 我方诊断口径 | 同上，GT=all（含 46.4% 投影框） | 900 | 0.0718 | 0.1869 | 同上 `:6-7` |
| 我方诊断口径（远端三 seed） | 同上 | 900 | 0.0715 | 0.1769±0.028 | `remote_5090/doc/experiments.md:586` |
| 我方同场次留出（"文献式考场"近似） | B0 / val_id（train 录音内帧级留出）/ GT=blob | 198（all 378） | 0.315±0.013 | 0.589±0.016 | `remote_5090/doc/experiments.md:586,592`；`remote_5090/doc/logs/2026-11-03-e11-c1-val-id-decomposition.md:9` |
| 我方 dense 平台 · 录音级留出 | E13-0 纯声呐 / val / GT=blob | 900 中部分 | 0.1945 | 0.3760 | `doc/logs/2026-11-05-literature-comparison-blob.md:16` |
| 我方 dense 平台 · 文献式考场 | E13-0 / val_id / GT=blob | 1,798 | 0.4236 | 0.7174 | 同上 `:16` |
| 我方相机支路（装置健康度） | Bcam 纯光学 / 三 seed | 900 | 0.5300 | 0.8471±0.022 | `doc/logs/2026-11-05-consolidated-teacher-student-table.md:16-19` |
| 我方相机支路（本机单 seed） | B0 camera d0 / GT=all | 900 | 0.5088 | 0.8101 | `results/2026-11-04_camera_b0/ap_summary_304.json` |
| 记忆健康度（失败对照） | B0 / train / GT=blob | 1,650 | 0.9818 | **1.0000** | `results/2026-11-04_sonar_b0/eval_sonar_b0_train/ap_summary.json` |
| **CMOLD 论文读数**（独立列，不与上表并列） | 纯声呐基线，帧级随机，train+validation | ~4,700 对 | 0.661 | 0.943 | `调查/cmold_t3.png`、`cmold_t5.png`；`调查/cmold_numbered.txt:602-604` |
| CMOLD 论文读数 | YOLOX-CMOLD（蒸馏后） | ~4,700 对 | 0.797 | 0.949 | `调查/cmold_t5.png`、`cmold_t6.png` |
| CMOLD 论文读数 | 相机教师 | 同上 | 0.958 | 0.997 | `调查/cmold_t3.png` |
| CMHD 后继论文旁证（二手） | 轨迹级 6:2:2、类别均衡、640×640、50 ep 下复现 CMOLD（**该行未标注复现时的教师/学生配置**） | 600 帧 test | 0.753 | — | `调查/cmhd_tables_u8.txt:44` |
| CMHD 同表**无蒸馏基线**（YOLOX-S-Ghost，二手） | 同上设定，**不蒸馏** | 600 帧 test | **0.770** | — | `调查/cmhd_tables_u8.txt:44`（CMOLD 低其 1.7 mAP 点，见 3.7 节） |
| CMHD 困难子集（二手） | — | — | 0.461（较 0.796 掉 33.5 点） | — | `调查/cmhd_tables_u8.txt:53-60` |

**读表约束**：
- 论文的 0.943 与我方的 0.2696 **不可并列**【仓库】`doc/logs/2026-11-04-literature-baseline-protocol-comparison.md:121`、`doc/logs/2026-11-05-literature-comparison-blob.md:152`。
- 可并列的是：论文 mAP 0.661 ↔ 我方文献式考场 mAP 0.4236；论文 AP50 0.943 ↔ 我方文献式考场 AP50 0.7174。
- `--split val,val_id` 是**合并口径**（all 1,278 帧 / blob 728 帧），既不是纯 val 也不是纯 val_id，不可当任一者引用。
- CMHD 的 0.753（复现 CMOLD）与 0.770（同表无蒸馏基线）是**同一设定下的两个数**，必须成对出现；单引 0.753 会把"机制本身无增益"误读成"我方落后 4.4 点"。
