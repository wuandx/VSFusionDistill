# 2026-11-09 文献引用审计 A：CMOLD / CMHD 的数字、协议与公式

审计员：audit-literature（只读）。审计对象：本项目（`code/VSFusionDistill`，分支 `exp/cmold-paper-repro`，HEAD `1c5d290`）及其调研文档对 CMOLD 与 CMHD 两篇论文的引用。审计方式：回到论文抽取件与表图逐格核对，不采信任何二手转述；本文件是本次审计唯一的写入。

判定口径：

- 成立：原文有该数字或陈述，且归属（哪个模型、哪个集合、哪个指标）与我们写的一致。
- 不成立：原文字面否定，或原文把该数字归属于另一个对象。
- 原文未述：该陈述在论文全文检索中计数为 0，或只有定性说法而无数字。此判定不等于"我方与论文不同"。

## 一、证据源与可得性

| 文件 | 形态 | 本次用途 | 备注 |
|---|---|---|---|
| `docs/investigation/cmold_numbered.txt` | 834 行，每行带行号前缀（`N` 加竖线） | CMOLD 权威行号来源，全部正文引用以此为据 | 双栏抽取，左右栏交错，需按语义拼接 |
| `docs/investigation/cmold_pymupdf_text.txt` | 67,374 字符 | 关键词计数交叉验证 | 与 numbered 计数一致 |
| `docs/investigation/cmold_layout_u8.txt` | 87,607 字符 | 关键词计数交叉验证 | 与 numbered 计数一致 |
| `docs/investigation/cmold_t1.png` … `cmold_t6.png` | 表格是图片对象，pdftotext 抽不出数字 | TABLE 1/2/3/5 逐格读图核对 | TABLE 4、TABLE 6 本次未逐格读（正文数字已够） |
| `docs/investigation/cmhd_fulltext.xml` | JATS，164,499 字节，全文压成单行 | CMHD 正文陈述（§3.1、§3.2、§4.1、§4.3、§5） | 单行文件，引用时给章节号不给行号 |
| `docs/investigation/cmhd_tables_u8.txt` | 65 行，表结构已展开为行 | CMHD TABLE 1–8 数值 | 行号即文件行号 |
| `docs/investigation/cmhd_params_numbered.txt` | 少量行 | CMHD 数据规模、分辨率、训练超参 | 与 §3.2 一致 |

一点必须写在前面：CMOLD 的表格数字全部是图片，任何"论文说 0.797"之类的引用，其真实出处是 `cmold_t5.png` 这张图或正文行，而不是可检索的文本。因此本审计对表内数字一律标注"表图"来源。

## 二、必查 8 条：断言 → 原文行号原文摘录 → 判定

| # | 断言（我方引用） | 原文行号 | 原文摘录（逐字） | 判定 |
|---|---|---|---|---|
| 1a | 基线 YOLOX-Sonar Only No KD：AP@[.50:.95] 0.661、AP50 0.943 | `cmold_numbered.txt:602-604` | "achieving an AP@[0.50:0.95] of 0.661 and an AR(maxDets=1) of 0.718. Although it reached a high AP@0.50 score of 0.943, its performance at stricter IoU thresholds decreased." | 成立 |
| 1b | 同基线 AP75 0.764 | `cmold_numbered.txt:674-678`（另见表图 `cmold_t5.png`） | "The ``YOLOX-Sonar Only No KD'' model reaches an AP@[0.50:0.95] of 0.661 and an AP@0.75 of 0.764, indicating that while detections are feasible under lower thresholds (AP@0.50 = 0.943)" | 成立 |
| 1c | 同基线 AR(maxDets=1) 0.718 | `cmold_numbered.txt:602-604`；表图 `cmold_t3.png`、`cmold_t5.png` | 同 1a；TABLE 3 Student (Sonar) 行与 TABLE 5 首行第 4 列均为 0.718（AR@1），AR@10 0.725、AR@100 0.726 | 成立 |
| 2a | CMOLD 完整法 AP@[.50:.95] 0.797 | `cmold_numbered.txt:642-644` | "leading to an AP@[0.50:0.95] of 0.797 corresponding to a 20.6% relative improvement over the baseline and 15.8% over the ViT-enhanced distillation model." | 成立 |
| 2b | CMOLD AP50 0.949、AP75 0.828 | 表图 `cmold_t5.png`（TABLE 5 "YOLOX-CMOLD (Proposed)" 行） | TABLE 5 该行六列为 0.797、0.949、0.828、0.798、0.824、0.865；正文**没有**印 0.949 与 0.828（正文检索 `0.949`、`0.828` 均 0 命中；双栏抽取有断行风险，故表述为"正文未载"） | 成立（来源仅表图，正文未载） |
| 3 | 相机教师 AP@[.50:.95] 0.958、AP50 0.997、AP75 0.997、AR 0.969 | 表图 `cmold_t3.png`（TABLE 3 Teacher (Camera) 行） | TABLE 3 该行六列为 0.958、0.997、0.997、0.969、0.969、0.969（后三列为 AR@1/AR@10/AR@100，三个都等于 0.969）；正文只有定性句 `cmold_numbered.txt:578-580` "The camera model (teacher) provides a stable and informative baseline for transferring object-level semantic knowledge to the sonar (student) network."，正文检索 `0.958`、`0.997`、`0.969` 均 0 命中（双栏抽取有断行风险） | 成立（来源仅表图；"AR 0.969"其实是三列同值，引用时须写明是哪一列） |
| 4a | 传统 KD 基线 AP@[.50:.95] 0.671 | `cmold_numbered.txt:607-609`；表图 `cmold_t5.png` | "Conventional knowledge distillation ``YOLOX KD [40]'' yields marginal gains, increasing AP@[0.50:0.95] from 0.661 to 0.671 and AR(maxDets=10) from 0.725 to 0.736."；TABLE 5 该行 0.671、0.948、0.766、0.722、0.736、0.762 | 成立 |
| 4b | YOLOX-M 25.3 M / 73.8 GFLOPs 的归属 | `cmold_numbered.txt:610-617` | "In this comparison, both the teacher (YOLOX-M) and the student (YOLOX-S) were trained exclusively on sonar images under identical data splits and optimization settings. The teacher model provides higher-capacity supervision due to its larger parameter count and deeper backbone, with YOLOX-M containing approximately 25.3 M parameters and 73.8 GFLOPs, compared to the compact YOLOX-S student with 9.0 M parameters and 26.8 GFLOPs." | 成立，但归属只能是**传统 KD（YOLOX KD [40]）那一行的教师**，且该教师只用声呐图训练。把它写成"CMOLD 的相机教师容量"即 不成立 |
| 4c | CMOLD 的相机教师容量 | `cmold_numbered.txt:392-393` | "Although the teacher and student share the same YOLOX architecture and input resolution, resulting in the same number of raw predictions" | 原文未述（论文只给同架构同分辨率，未给相机教师参数量或 FLOPs） |
| 5a | SGD 1.25e-3 → 6.25e-5、mom 0.9、wd 5e-4、bs 8、200 epochs | 表图 `cmold_t2.png`（TABLE 2）；`cmold_numbered.txt:537-541` 说明这些只在表里 | 正文无任何超参数值：`epoch`、`learning rate`、`batch size`、`momentum`、`weight decay` 在三个文本抽取中均 0 命中；正文只写 "the experimental setup details and hyperparameter configurations are listed in Table 2."。TABLE 2 逐格：Number of Epochs 200、Batch Size 8、Optimizer SGD、Initial Learning Rate 0.00125、Final Learning Rate 6.25e-5、Momentum 0.9、Weight Decay 5e-4 | 成立（唯一来源是 TABLE 2 图片；引用时必须写"TABLE 2"，不能写"正文"） |
| 5b | α = β = 0.5 | `cmold_numbered.txt:530-533` | "During training, the objectness-level and classification-level distillation losses were equally weighted with α = β = 0.5, ensuring a balanced transfer of detection confidence and semantic category information from the teacher to the student model." | 成立（正文） |
| 5c | τ = 2 | `cmold_numbered.txt:534-535` | "The temperature parameter τ was set to 2 to soften the teacher's class logits during class-level distillation." | 成立（正文） |
| 6a | 论文有没有 test set | `cmold_numbered.txt` 全文；`cmold_pymupdf_text.txt`；`cmold_layout_u8.txt` | `test set` = 0、`testing set` = 0、`testset` = 0、`test data` = 0、`held-out` = 0（三个抽取一致）；`split` 唯一 1 次，在 `:610-612` 的 "identical data splits"。正文 `:575` 只提 "training and validation" | 原文未述（论文未声明独立测试集，也未见 held-out 或三次划分的描述） |
| 6b | "nearly 4700 image pairs" | `cmold_numbered.txt:575` | "nearly 4700 image pairs were used for training and validation."（紧接 `:576-578` "In our evaluation, sonar imagery was used for baseline detection, whereas sonar-camera pairs were used to train and assess the cross-modal distillation framework."） | 成立（逐字），但原文把规模限定在 training and validation；"assess" 所用集合未指明 |
| 6c | 论文有没有给输入分辨率 | `cmold_numbered.txt:392-393` 是全文唯一 `input resolution` 命中；表图 `cmold_t1.png` 无分辨率行 | "share the same YOLOX architecture and input resolution" —— 只有"相同"，没有数字。三份抽取中 `640` 仅 `cmold_numbered.txt` 命中 1 次（分栏伪影，非设置陈述）、`resize` = 0、`input size` = 0；TABLE 1 实验环境只列 Python 3.8.20 / NVIDIA L4 / Intel Xeon 2.20GHz / Ubuntu 20.04 LTS / CUDA 12.9 / Pytorch 2.4.1 | 原文未述（无数值，不可写成"论文用 640"） |
| 7a | 式(11) 取 top-K | `cmold_numbered.txt:405`、`:421`、`:475-482` | 式(10) 取教师与学生预测条数的较小者（K = min(·, ·)）；式(11) 为 "PT = P~T[1:K], PS = P~S[1:K]"；"CMOLD generalizes this formulation to a top-K selection strategy, as implemented in Algorithm 1, where K is determined by the number of available teacher and student predictions after objectness-based confidence ranking. This formulation allows distillation to operate over multiple confidence-ranked predictions and can be readily adapted to enforce an upper bound on K if desired." | 成立（论文未给 K 的数值，只说可由可用预测数决定、可加上界） |
| 7b | 式(14) objectness 用 MSE | `cmold_numbered.txt:491-496` | "It is defined as the mean squared error (MSE) over the K highest-confidence predictions selected after objectness-based ranking."；式(14) "Lobj = 1/K Σ_k (sS^(k) − sT^(k))^2" | 成立 |
| 7c | 式(19) 是总损失 | `cmold_numbered.txt:492-497`、`:502`、`:548-551` | 小标题原文即 "c: OVERALL LOSS FUNCTION OF CMOLD MODEL"，其后 "the object-level distillation loss combines only the objectness and class distillation components: LCMOLD = Lobj + Lcls scaled (19)"；`:502` "The overall training loss integrates the standard YOLOX detection loss, Ldet with the object-level distillation."；式(24) "Ltotal = Ldet + λ LCMOLD"，"where λ controls the overall weight of the distillation term"（λ 无数值） | 部分成立：论文自己的小标题确实把式(19) 叫 "overall loss function of CMOLD model"，但式(19) 只含两项蒸馏项；含检测损失的训练总损失是式(24)。引用时须写清是哪一个，且 λ 为"未给" |
| 7d | 只蒸 objectness + 分类，不碰框回归 | `cmold_numbered.txt:133-137`、`:378-380`、`:493-494` | "loss is applied only to bounding box classification probabilities and objectness scores, whereas box regression is excluded because of the geometric mismatch between the optical and sonar modalities."；"Because of the different cross-modal geometries between camera and sonar, bounding-box regression outputs are not used for cross-modal distillation."；"Because geometric alignment is not used, the object-level distillation loss combines only the objectness and class distillation components" | 成立（三处独立陈述，措辞一致） |
| 8a | CMHD 复现 CMOLD 得 75.3 / 78.6 | `cmhd_tables_u8.txt:50`（TABLE 6 行 CMOLD）；`cmhd_fulltext.xml` §4.3 | TABLE 6 该行逐列为 89.2、91.5、49.9、54.9、87.0、89.4、75.3、78.6；§4.3 评价 "CMOLD gains slight precision on easy classes but degrades severely on hard targets"；§4.3 另写 "CMHD achieves highest overall performance on the UXO† test set" | 成立（注意 TABLE 6 单位是 %，即 75.3% 而非 0.753，与 CMOLD 原文 0–1 标度不同，比较前须换算） |
| 8b | 同表无蒸馏基线 77.0 / 79.9 | `cmhd_tables_u8.txt:48`（TABLE 6 行 YOLOX-S-Ghost）；`:25`（TABLE 4 无蒸馏行，cls ×、obj ×） | TABLE 6 该行逐列为 87.4、89.6、56.5、61.4、87.0、88.9、77.0、79.9；TABLE 4 无蒸馏行逐列为 87.3、89.6、56.6、61.4、87.2、88.9、77.0、79.9 | 成立（两处给同一 mAP/mAR；逐类数字互差 0.1–0.2，属论文自身不一致，不影响结论） |
| 8c | CMHD 的 77.0 是 AP@[.5:.95] 还是 AP50 | `cmhd_tables_u8.txt:44`（TABLE 6 表题）；`cmhd_fulltext.xml` §4.1 | 表题逐字 "All AP/mAP values are AP@[0.50:0.95] (%), and all AR/mAR values are AR (maxDets=1) (%)"；§4.1 "all AP and mAP metrics are reported as AP@[0.50:0.95]. Since the adopted subset contains one dominant UXO† instance per image, AR is reported with maxDets = 1" | 成立：77.0 是 **AP@[0.50:0.95]**，不是 AP50；79.9 是 AR(maxDets=1)。写成 AP50 即 不成立 |
| 8d | 复现 CMOLD 时教师与学生同为 YOLOX-S-Ghost | `cmhd_fulltext.xml` §4.3 | "(4) CMOLD [28] is a homogeneous teacher–student cross-modal distillation method … similar to CMHD, it distills only classification and objectness branches to avoid unreliable regression supervision caused by RGB–sonar geometric misalignment. Following the homogeneous teacher–student design of the original CMOLD method and the lightweight modeling principle of this paper, our setup uses YOLOX-S-Ghost for both teacher and student architectures."；同节 "All detectors are trained and evaluated on the same geometrically projected sonar labels of the UXO† dataset, with identical input resolution (640 × 640), 50 training epochs" | 成立，但主语只能是"CMHD 用来复现 CMOLD 的那一臂"。CMHD 本体的教师是 YOLOX-M：§5 结论 "CMHD adopted YOLOX-M as RGB teacher network and enhanced YOLOX-S-Ghost as sonar student network"；TABLE 2 教师消融（student 固定 Ghost）YOLOX-L 79.3/81.9、YOLOX-M 79.6/82.6、YOLOX-S 78.5/81.5（`cmhd_tables_u8.txt:11-13`）；TABLE 3 蒸馏源 TABLE 3 蒸馏源一行（YOLOX-M 作 RGB 教师、YOLOX-S-Ghost 作声呐学生）为 79.6 / 82.6（`:20`）。把"同为 YOLOX-S-Ghost"说成 CMHD 的配置即 不成立 |

## 三、判定汇总

- 按主项计：成立 6 条（1 基线、2 CMOLD、3 相机教师、5 超参、7 蒸馏公式、8 CMHD 数字；第 4 条拆成两半，4a/4b 成立、4c 未述）。其中 2、3、5 的部分数字只有表图出处，5 的优化器项也只在表里；7 的子项 7c 只能判"部分成立"（式(19) 与式(24) 须分清）；8 的子项 8d 成立但主语须限定。归属类判定：4b 成立的前提是写成"传统 KD 基线的教师"。
- 原文未述 3 处：4c 相机教师容量、6a test set、6c 输入分辨率。无一条出现数值被改动的迹象。
- 需要改口的不是数值，而是来源标注与归属：基线/CMOLD/相机教师的六列数字里，AP50、AP75、AR 三项在正文根本没有印，唯一出处是 `cmold_t3.png` 与 `cmold_t5.png`；超参数唯一出处是 `cmold_t2.png`。凡写成"正文说 0.828"或"正文给出 200 epochs"的句子都是错的引用方式。

## 四、与 lead 说法冲突的条目

下表每一行是一处"我方说法与原文不符或原文不支持"。左列给出该说法在本仓库的落点，右列给出原文事实。若 lead 的对外口径采用了左列表述，须按右列修改。

| # | 我方说法（出处） | 原文事实（行号） | 冲突性质 | 建议改法 |
|---|---|---|---|---|
| 1 | "论文全文无 test 集" —— 这一条**正确**，但 `doc/logs/2026-11-08-cmold-paper-repro-plan.md:29` 与 `:36` 把依据引成 `docs/investigation/01_CMOLD论文规格.md:100`，该行是 §3.1 表头，不含此结论 | 正确依据是 `docs/investigation/01_CMOLD论文规格.md:16` 或 `:309`；论文侧 `cmold_numbered.txt:575` 与全文 `test set` 0 命中 | 行号错引，结论本身成立 | 改引 `01:16`（并保留 `cmold_numbered.txt:575`） |
| 2 | `docs/investigation/00_总报告_我方与CMOLD对齐与差距归因.md:567` 把 CMOLD 的评测集写成"纯声呐基线，**帧级随机**，train+validation"；同文件 `:353` 写"在**帧级随机切分**的协议下带来 +20.6% 的增益"；`docs/investigation/03_基线数字复核.md:187-188` 同样写"论文侧切分为帧级随机" | 论文对切分只字未提：`split` 全文 1 次且指 KD 对比的内部一致性（`cmold_numbered.txt:610-612`），`test set` 0 命中，`:575` 只说规模用于 training and validation。仓库里两处**正确**的表述可作对照：`code/VSFusionDistill/doc/logs/2026-11-04-literature-baseline-protocol-comparison.md:117`"CMOLD 未述切分"、`code/VSFusionDistill/doc/logs/2026-11-09-r0-first-result-and-overfit-diagnosis.md:325`"论文是否用帧级随机划分未披露" | **实质冲突**：把我方假设（复现时选帧级随机 8:2）写成了论文事实。这是"论文没写"被升级成"论文如此"的典型 | 统一改为"论文未述切分方式与单位；帧级随机 8:2 是我方复现选择（偏离项，见复现计划 `:37`）"。同文件 `:136`（"是否有 train/val/test 三分 未给"）本来就是对的，`:567` 与之自相矛盾 |
| 3 | 若对外说"CMOLD 的相机教师是 YOLOX-M，25.3 M / 73.8 GFLOPs" | `cmold_numbered.txt:610-617`：25.3 M / 73.8 GFLOPs 属**传统 KD 基线**的教师 YOLOX-M，且该教师与学生在"identical data splits"下只用**声呐**图训练；CMOLD 的相机教师只有 `:392-393`"same YOLOX architecture and input resolution"，无容量 | **实质冲突**（归属错位）。这是最容易传播的一处：数字是真的，主谓是错的 | 写成"传统 KD 基线的教师 YOLOX-M 为 25.3 M / 73.8 GFLOPs（纯声呐训练）；CMOLD 的相机教师容量论文未给，只能确定与 YOLOX-S 同架构同分辨率"。仓库里 `01:133`、`00:150`、`code/VSFusionDistill/CLAUDE.md:87` 已经是正确写法，不要被 `01:378` 的并列写法带偏 |
| 4 | 若说"CMHD 的教师与学生同为 YOLOX-S-Ghost"（不加限定） | 该句只存在于 §4.3 对"复现 CMOLD 那一臂"的描述；CMHD 本体 §5 "CMHD adopted YOLOX-M as RGB teacher network"，TABLE 3 `:20` 选用的是 YOLOX-M RGB→Ghost，TABLE 2 `:11-13` 教师消融中 Ghost 教师（78.5/81.5）反而低于 YOLOX-M（79.6/82.6） | **实质冲突**（主语错位） | 写成"CMHD 复现 CMOLD 的那一臂用 YOLOX-S-Ghost 做教师与学生；CMHD 本体用 YOLOX-M 做 RGB 教师"。`01:382`、`01:405`、`04:51`、`CLAUDE.md:93` 均已限定，`00:570` 括号内"CMOLD 复现用教师与学生同为 YOLOX-S-Ghost"也是对的，保持即可 |
| 5 | 若把 CMHD TABLE 6 的 77.0 当 AP50 用，或与 CMOLD 的 AP50 0.943 并列 | `cmhd_tables_u8.txt:44` 表题与 §4.1 均明确 AP/mAP 一律 AP@[0.50:0.95]；AR/mAR 一律 maxDets=1 | 指标口径错 | 只能写成 "CMHD 侧 YOLOX-S-Ghost 无蒸馏基线 mAP 77.0 / mAR(maxDets=1) 79.9"，不得与 AP50 或 AR@100 相提并论。`00:358`、`01:411` 已写对 |
| 6 | 若说"式(19) 是总损失"而不加限定 | 式(19) 在 `:497`，是 Lobj + Lcls_scaled 两项蒸馏项之和（小标题虽叫 "OVERALL LOSS FUNCTION OF CMOLD MODEL"）；训练总损失是式(24) `:548` Ltotal = Ldet + λ LCMOLD，λ 无数值（`:550-551`） | 术语含混 | 报"蒸馏损失 = 式(19)，训练总损失 = 式(24)，λ 未给"。仓库现行文档没有把式(19) 称总损失的写法（`01:198` 标式(19) 为 L_CMOLD、`01:199` 标式(24) 为 L_total、`doc/logs/2026-11-04-literature-baseline-protocol-comparison.md:63` 也正确），此条属预防性提示 |
| 7 | `doc/logs/2026-11-08-cmold-paper-repro-plan.md:11` 写"四个待复现的目标读数（**TABLE 1 与 TABLE 5**，`docs/investigation/cmold_numbered.txt:600-640`）" | 四个读数在 TABLE 3 与 TABLE 5，消融的 0.794/0.771 在 TABLE 6；`0.797` 出现在 `:642-644`，不在 `:600-640` 区间内 | 表号与行号双错（数字本身 `:13-19` 全对） | 改为 "TABLE 3 与 TABLE 5、TABLE 6；`cmold_numbered.txt:602-604`、`:642-644`、`:675-678`、`:681-692`" |
| 8 | `doc/logs/2026-11-08-cmold-paper-repro-plan.md:125` 写"论文称 objectness 项贡献约 98%" | 原文 `:681-683` 只说 "Introducing only ``Objectness KD'' delivers the largest single-component gain, boosting AP@[0.50:0.95] from 0.661 to 0.794"；98% 是 (0.794−0.661)/(0.797−0.661)=97.8% 的我方算得值 | 把自家算术挂到论文名下 | 改为"我方由 TABLE 6 三个数算得 objectness-only 占增益的 97.8%，论文原文只说 largest single-component gain" |

## 五、其他引用瑕疵（不影响数字结论，但应修）

| 位置 | 问题 | 建议 |
|---|---|---|
| `docs/investigation/01_CMOLD论文规格.md:198` | 式(19) 写成 "L_CMOLD = α * L_obj + β * L_cls_scaled"。原文抽取的式(19) 没有 α/β 系数（`:497`），系数只出现在紧随其后的文字（`:499-500`）。同时 Algorithm 1 `:466` 写作 "LCMOLD = Lobj + τ² Lcls"，与正文 α = β = 0.5 的记号也不一致 | 注明"原式未印系数；α = β = 0.5 来自 `:530-533`；Algorithm 1 的写法为 L_obj + τ²L_cls，原文记号内部不一致" |
| `docs/investigation/01_CMOLD论文规格.md:378` | 参数量行并列 "YOLOX-M 25.3 M / 73.8 GFLOPs；YOLOX-S 9.0 M / 26.8 GFLOPs"，未注明前者属传统 KD 基线的教师 | 与同文件 `:133` 保持一致，补"（传统 KD 基线的教师，纯声呐训练）" |
| `docs/investigation/03_基线数字复核.md:190` | "骨干与蒸馏：YOLOX-S 学生 + RGB YOLOX-L 教师"——这是我方臂的配置（`CLAUDE.md:91` 记 E13-T 为 116.58 M），但列在文献对照表内易被读成论文配置 | 加"（我方 E13-T 配置；论文的相机教师容量未给）" |
| `docs/investigation/03_基线数字复核.md:168-172` | 数字全对，但把出处写成 `cmold_layout.txt:602-604` 等。layout 与 numbered 两份文件行号目前巧合一致（numbered 是 layout 加前缀），若日后重抽会整体错位 | 统一改引 `cmold_numbered.txt`，它是唯一带稳定行号前缀的版本 |
| `doc/logs/2026-11-08-cmold-paper-repro-plan.md:47-59` | 未披露项清单把 K 的上界依据引成 `:405`、`:419-421`（那是式(10)、式(11) 本体）；说明 top-K 机制与"可设上界"的文字在 `:475-482` | 补引 `:475-482` |

## 六、本次未覆盖与未能核实

- CMOLD TABLE 4（分类别指标）与 TABLE 6（消融表图）未逐格读图；TABLE 6 的结论已由正文 `:681-692` 的数字核到（objectness-only 0.794、cls-only 0.771、AP@0.75 0.804 与 0.796），逐类 6 列未核。
- CMOLD 的 `cmold_alg1.png`（Algorithm 1 图）未读图；本报告引用的 Algorithm 1 内容取自文本抽取 `:466`，该行有下标与符号丢失（α/β/τ² 在抽取中残缺），如需引用 Algorithm 1 的精确系数，应回图核对。
- CMHD 的 `cmhd_params_be.txt`、`cmhd_params_extract_u8.txt`、`cmhd_snips*.txt` 未读；`cmhd_params_numbered.txt` 与 `cmhd_fulltext.xml` §3.1/§3.2 已互相印证，本报告以这两处为准。
- 论文是否在补充材料中给出划分比例、输入分辨率或 K 值：本次只核了正文与表格，补充材料不在抽取件内，故记为"未找到"。此处不推测。
- 复算核对：0.797/0.661 = 1.2057（论文写 20.6% 相对提升，对上）；0.797/0.688 = 1.1584（写 15.8%，对上）；77.0 − 75.3 = 1.7（我方写 −1.7 mAP 点，对上）；79.6 − 75.3 = 4.3、82.6 − 78.6 = 4.0（CMHD 写 "4.3/4.0 percentage points"，对上）；79.6 − 71.6 = 8.0、82.6 − 75.8 = 6.8（写 "8.0/6.8"，对上）。

## 七、结论

必查 8 条里的数字，除 4c、6a、6c 三条原文未述外，其余全部能在原文（正文或表图）找到逐字依据，**未发现数值被改动或伪造**。真正需要处理的是三类引用卫生问题：

1. 来源错标：表内数字被当成正文结论引用（0.949、0.828、0.958、0.997、0.969 以及全部超参数）。
2. 归属错位：25.3 M / 73.8 GFLOPs 被从"传统 KD 基线教师"挪到"CMOLD 相机教师"；"同为 YOLOX-S-Ghost"被从"复现 CMOLD 那一臂"挪到 CMHD 本体。
3. 假说被写成事实：论文切分方式未述，而 `00:567`、`00:353`、`03:187-188` 把我方复现选择（帧级随机 8:2）写成论文协议。这一条影响最大，因为它直接支撑"0.797 与我方 val 不可比"这个核心判断的措辞——判断本身仍站得住（论文评测集身份不可知），但论据只能是"论文未述"，不能是"论文帧级随机"。
