# CMOLD 论文"数据划分"专项核查报告

核查对象：M. Aydogmus, I. Erer, "Cross-Modality Object-Level Knowledge Distillation for Enhanced Underwater Sonar Object Detection," IEEE Access, vol. 14, 2026, DOI 10.1109/ACCESS.2026.3666096。

核查范围：只读。仅读取 `docs\investigation\cmold_numbered.txt`（834 行，带行号 OCR 全文）、`literature\cmold\` 下的 PDF 与页面图、`docs\investigation\` 下的表格截图。未修改任何既有文件，未运行训练，未执行 git 写操作，未使用 ssh。本报告是本次唯一写出的文件。

素材口径说明：
- 表格截图实际位于 `docs\investigation\`（`cmold_t1.png` 至 `cmold_t6.png`），任务描述中提到的 `literature\cmold\` 目录下只有 `cmold.pdf`、`cmold_layout.txt`、`cmhd_fulltext.xml`、`cmhd_tables.txt` 以及 `page10_full.png`、`page11_full.png`、`page12_full.png`。本报告按实际路径引用表图文件名。
- 凡写"全文 0 命中"，指在 `cmold_numbered.txt` 全文 834 行内检索不到；关键项另用 `cmold_layout_u8.txt`、`cmold_pymupdf_text.txt` 两份抽取文本交叉复核，结论一致。
- 全文引用一律给 `cmold_numbered.txt:行号`，表格数值给图片文件名。
- 带行号文本只保留了表题（`:553`、`:622`、`:627`、`:629`、`:653`），表体不在 OCR 文本内，因此表内数值必须读图核对；本报告的表 1、表 2、表 3、表 5 数值均逐格看过对应 png。
- 本报告只以论文原文与表图为证据，不引用我方既有规格整理中的任何结论。

---

## 1. 训练集 / 验证集 / 测试集怎么划分

### 1.1 关键词统计（全文检索）

| 检索项 | 命中次数 | 行号 | 在说什么 |
|---|---|---|---|
| split / splits / splitting | 1 | 612 | "identical data splits"（同模态 KD 对比中两个模型共用同一划分） |
| seed | 0 | — | 无随机种子 |
| shuffle | 0 | — | 无 |
| k-fold / fold / cross-validation | 0 | — | 无交叉验证 |
| 80/20、6:2:2、70/15 等比例写法 | 0 | — | 无任何划分比例 |
| random | 2 | 343、755 | 343 是"伪标签图像随机抽一部分人工检查"，755 是参考文献 [11] 标题里的 "randomized degradation"，均与划分无关 |

结论：全文关于"切分"只有 1 处词形（第 612 行的 `splits`），没有第二处。

### 1.2 第 575 行的原文与边界

该句跨栏断开，前半句在第 550 行末尾，后半句在第 575 行行首：

> "…Fig. 7 shows the setup of the dataset collection. In our research,"（`cmold_numbered.txt:550`）
> "nearly 4700 image pairs were used for training and validation."（`cmold_numbered.txt:575`）

合起来是：In our research, nearly 4700 image pairs were used for training and validation.

它说了什么：
- 数据规模是"nearly 4700 image pairs"（`cmold_numbered.txt:575`）。
- 这 4700 对的用途是"training and validation"（`cmold_numbered.txt:575`）。

它没说什么（逐项核对）：
- 没说 4700 对里多少进训练、多少进验证。无比例（`cmold_numbered.txt:575`）。
- 没说是按帧切、按录音切还是按场次切。无划分单位（`cmold_numbered.txt:575`）。
- 没说验证集是独立留出的，还是从训练池里临时切出来的（`cmold_numbered.txt:575`）。
- 没给随机种子（`seed` 全文 0 命中）。

紧随其后的两句只交代"用哪种模态做什么"，仍不涉及集合划分：

> "In our evaluation, sonar imagery was used for baseline detection, whereas sonar-camera pairs were used to train and assess the cross-modal distillation framework."（`cmold_numbered.txt:576-578`）

### 1.3 第 612 行 "data splits" 指的是什么

原文：

> "In this comparison, both the teacher (YOLOX-M) and the student (YOLOX-S) were trained exclusively on sonar images under identical data splits and optimization settings."（`cmold_numbered.txt:610-612`）

判断：这里的 "data splits" 指"同模态 KD 对比实验中，教师模型与学生模型使用同一套数据划分"，不是"给出了划分比例"。

依据（三条，均来自原文本身）：
1. 主语是 "both the teacher (YOLOX-M) and the student (YOLOX-S)"，说的是两者之间的一致性，不是数据集被切成几份（`cmold_numbered.txt:610-612`）。
2. 同句给出的另一致性条件是 "optimization settings"（优化设置），与 "data splits" 并列，属于"保持对比公平"的表述，不是数据描述（`cmold_numbered.txt:612`）。
3. 该句所在段落讨论的是 "YOLOX KD [40]" 的增益（0.661 到 0.671），通篇没有出现百分比、份数或集合名（`cmold_numbered.txt:602-612`）。

也就是说：这句话成立的前提是"存在一套划分"，但它既没有说这套划分怎么来，也没有说这套划分有几个集合。

另需注意，这句话里的 teacher 与 student 都"trained exclusively on sonar images"（`cmold_numbered.txt:610-612`），所以严格讲它连"相机与声呐两模态共用同一划分"都不是，而是"同一个声呐数据集上两个模型共用同一划分"；跨模态蒸馏那一组（相机教师对声呐学生）是否也用这套划分，论文没有说（`cmold_numbered.txt:610-612`）。

### 1.4 全文 4 处 "valid" 逐条辨析

| 行号 | 原文 | 是不是"验证集" |
|---|---|---|
| 118 | "5. Validation on Real UXO Data: We evaluated the proposed framework using a multimodal dataset of UXO…" | 不是。是贡献点标题，指"用真实 UXO 数据做验证性实验"（`cmold_numbered.txt:118-120`） |
| 139 | "We validated our approach on an unexploded ordnance (UXO) dataset [22]…" | 不是。是"我们验证了方法"（`cmold_numbered.txt:139-142`） |
| 575 | "…were used for training and validation." | 是。全文唯一与集合相关的 "validation"，但没有比例、没有独立性说明（`cmold_numbered.txt:575`） |
| 701 | "Future work will focus on real-world validation using field-collected sonar data" | 不是。指未来现场验证（`cmold_numbered.txt:701-702`） |

### 1.5 与"训练集构成"相邻但不等于"划分"的内容

- 最终训练集 = 手工标注子集 + 伪标签：`Dfinal = DL ∪ DP`，"manually labeled and pseudolabeled sonar images were combined to form the final training dataset"（`cmold_numbered.txt:350-353`）。
- 伪标签筛选式为 `ỹj = ŷj if max(conf(ŷj)) ≥ θ`，但公式里的阈值 θ 在正文与表格中都没有给数值（`cmold_numbered.txt:321-330`；`cmold_t2.png` 的超参表也没有该项）。
- 扩增后的训练集覆盖了不同角度与反射的物体："an expanded dataset was obtained, which provided broader sonar image coverage and increased sample diversity…"（`cmold_numbered.txt:355-358`），这是规模描述，不是划分描述。

---

## 2. "帧"与"录音 / 场次"的关系

### 2.1 逐条命中

- "frame/frames" 作为独立词全文 3 处：
  - "a small set of manually labeled frames"（`cmold_numbered.txt:171`）——指手工标注的少量帧。
  - "raw and polar-domain ARIS 3000 imaging sonar frames"（`cmold_numbered.txt:548`）——指数据集包含原始与极坐标声呐帧。
  - "sonar frame in polar representation"（`cmold_numbered.txt:572`）——图 8 左图说明。
- "recording(s)" 全文 4 处：
  - "sonar recordings"（引言，`cmold_numbered.txt:60`）。
  - "synchronized optical and sonar recordings"（贡献点，`cmold_numbered.txt:120`）。
  - "synchronized sonar and camera recordings of UXOs captured within a controlled experimental setting"（数据集小节，`cmold_numbered.txt:546`）。
  - "The recordings were obtained at different angular positions and depths."（`cmold_numbered.txt:584`）。

这 7 处都没有给出"录音段数""每段多少帧""哪些帧属于同一段录音"。论文提到 recordings 时只用来描述"数据是同步采集的"，提到 frames 时只用来描述"输入样本是帧"，两者从未在句法上建立从属关系（`cmold_numbered.txt:546-548`、`cmold_numbered.txt:572-575`、`cmold_numbered.txt:584-587`）。

### 2.2 唯一涉及"同一时刻"的表述

> "A polar sonar image and camera image of the same capture moment is shown in Fig. 8."（`cmold_numbered.txt:581-582`）
> 图 8 标题："Each pair represents the same scene [22]."（`cmold_numbered.txt:572-573`）

这说的是相机帧与声呐帧按"采集时刻"配对，属于跨模态配对关系，不是录音分组，也不涉及训练/验证集合的隔离。

### 2.3 防泄漏表述：全文无

检索 adjacent、overlap、leak、trajectory、sequence、independent、held-out、holdout：与"同一段录音的相邻帧不得同时进入训练与验证"相关的句子为 0 条。零星命中均与泄漏无关：

- "Overlapping or contradictory bounding boxes were merged or removed."（伪标签框合并，`cmold_numbered.txt:340`）
- "measures the overlap between the predicted and ground-truth bounding boxes"（IoU 损失，`cmold_numbered.txt:538-539`）
- "continues to limit the learning of robust object representations"（`cmold_numbered.txt:211`）

### 2.4 采集条件的表述

> "The recordings were obtained at different angular positions and depths. Different gain, resolution and range settings were applied for the acquisition of sonar data; therefore, different reflections of the targets were obtained by Dahn et al. [22]."（`cmold_numbered.txt:584-587`）

这句说明采集条件多样（角度、深度、增益、分辨率、量程），但没有据此说明任何划分策略。

---

## 3. 全文 "test" 的所有出现

`test` 在 `cmold_numbered.txt` 全文命中 1 次：

> "To systematically evaluate the contribution of the components of CMOLD, we ablated the key supervision terms individually and tested the structural assumptions of the framework."（`cmold_numbered.txt:670-672`）

这一处是动词 "tested"（检验框架的结构假设），不是"测试集"。

逐项核对结论：
- 全文没有 "test set"、"testing set"、"test split"、"held-out test" 任何一种表述（0 命中）。
- 表 3、表 4、表 5、表 6 的标题只写 "Comparison of detection metrics…" / "Per-class AP and AR comparison…"，没有说明指标在哪个集合上计算（`cmold_numbered.txt:622`、`cmold_numbered.txt:627`、`cmold_numbered.txt:629`、`cmold_numbered.txt:653`；表体见 `cmold_t3.png`、`cmold_t5.png`、`cmold_t4.png`、`cmold_t6.png`）。
- 论文描述"评估"用的词是 evaluate/assessment，共 11 处（118、126、165、521、556、557、563、565、576、594、670），例如 "Experimental evaluations were carried out on sonar datasets supported by camera-based supervision"（`cmold_numbered.txt:556-558`）、"In our evaluation"（`cmold_numbered.txt:576`）、"comparative evaluation is restricted to capacity-matched sonar-based baselines"（`cmold_numbered.txt:594-596`），都不指向独立测试集。

---

## 4. 表 3 与表 5 的数值：正文有没有

### 4.1 表 3（相机教师 / 声呐学生）

表 3 表体（见 `cmold_t3.png`）：

| Model | AP@[0.50:0.95] | AP@0.50 | AP@0.75 | AR (maxDets=1) | AR (maxDets=10) | AR (maxDets=100) |
|---|---|---|---|---|---|---|
| Teacher (Camera) | 0.958 | 0.997 | 0.997 | 0.969 | 0.969 | 0.969 |
| Student (Sonar) | 0.661 | 0.943 | 0.764 | 0.718 | 0.725 | 0.726 |

正文对照：
- 0.958、0.997、0.969 在 `cmold_numbered.txt` 全文 0 命中（另在 `cmold_layout_u8.txt`、`cmold_pymupdf_text.txt` 亦 0 命中）。这三个数只在 `cmold_t3.png`。
- 正文对教师只有定性描述，没有数字："Near-perfect AP@0.50 and AP@0.75 scores indicate that the model accurately captures object boundaries, whereas stable AR values confirm its ability to detect nearly all ground-truth instances."（`cmold_numbered.txt:596-600`）
- 学生行的 0.661 / 0.943 / 0.764 / 0.718 / 0.725 / 0.726 在正文出现（`cmold_numbered.txt:602-604`、`cmold_numbered.txt:656-658`、`cmold_numbered.txt:676-678`）。

### 4.2 表 5（不同方法对比）

表 5 中 "YOLOX-CMOLD (Proposed)" 行（仅见 `cmold_t5.png`）：AP@[0.50:0.95] 0.797、AP@0.50 0.949、AP@0.75 0.828、AR@1 0.798、AR@10 0.824、AR@100 0.865。

正文对照：
- 0.797：正文出现 1 次——"achieving an AP@[0.50:0.95] of 0.797 corresponding to a 20.6% relative improvement over the baseline and 15.8% over the ViT-enhanced distillation model"（`cmold_numbered.txt:640-644`）。这是表 5 中唯一进入正文的 CMOLD 数值。
- 0.949：全文 0 命中，只在 `cmold_t5.png`。
- 0.828：全文 0 命中，只在 `cmold_t5.png`。
- 0.798 / 0.824 / 0.865 在正文以增量形式给出："AR(maxDets=1) increasing from 0.718 to 0.798, AR(maxDets=10) increasing from 0.725 to 0.824, and AR(maxDets=100) improving from 0.726 to 0.865"（`cmold_numbered.txt:655-658`），与 `cmold_t5.png` 一致。
- 基线行的 0.661、0.943、0.764、0.718、0.725、0.726 在正文出现（`cmold_numbered.txt:602-604`、`cmold_numbered.txt:676-678`）。

### 4.3 小结

| 数值 | 正文可查 | 只在表图 |
|---|---|---|
| 0.958 / 0.997 / 0.969（相机教师） | 否 | `cmold_t3.png` |
| 0.797（CMOLD AP@[0.50:0.95]） | 是（`cmold_numbered.txt:642`） | — |
| 0.949（CMOLD AP@0.50） | 否 | `cmold_t5.png` |
| 0.828（CMOLD AP@0.75） | 否 | `cmold_t5.png` |

---

## 5. 输入分辨率与 resize 方式

### 5.1 全文唯一提到输入分辨率的地方

> "Although the teacher and student share the same YOLOX architecture and input resolution, resulting in the same number of raw predictions, differences in objectness confidence distributions across modalities lead to different numbers of retained high-confidence predictions."（`cmold_numbered.txt:391-394`）

这句只说"教师与学生共用同一输入分辨率"，用于论证两者原始预测数相同、K 可对齐，没有给出任何分辨率数值（`cmold_numbered.txt:391-394`）。

### 5.2 resize 相关关键词：全部 0 命中

resize、letterbox、crop、padding、aspect、input size、640、512、608 在 `cmold_numbered.txt` 全文 0 命中；`cmold_layout_u8.txt`、`cmold_pymupdf_text.txt` 亦为 0 命中。

因此：论文既没有写 letterbox，也没有写直接拉伸或中心裁剪，没有任何图像缩放/填充策略的表述（全文 0 命中）。

### 5.3 两张配置表也没有

- Table 1 "Experiment environment"：Python 3.8.20、NVIDIA L4、Intel Xeon 2.20GHz、Ubuntu 20.04 LTS、CUDA 12.9、PyTorch 2.4.1。无输入尺寸（`cmold_t1.png`）。
- Table 2 "Hyperparameter configuration values"：Number of Epochs 200、Batch Size 8、Optimizer SGD、Initial LR 0.00125、Final LR 6.25e-5、Momentum 0.9、Weight Decay 5e-4。无输入尺寸、无 resize 项（`cmold_t2.png`）。

### 5.4 其余 "resolution" 命中均为定性描述

16 处 resolution 中，与数值无关的包括：高分辨率相机（`cmold_numbered.txt:17`、`cmold_numbered.txt:45`、`cmold_numbered.txt:220`）、声呐空间分辨率低（`cmold_numbered.txt:58`、`cmold_numbered.txt:60`、`cmold_numbered.txt:209`、`cmold_numbered.txt:400`、`cmold_numbered.txt:607`、`cmold_numbered.txt:705`）、两模态分辨率差异需要专门处理（`cmold_numbered.txt:298`、`cmold_numbered.txt:302`、`cmold_numbered.txt:378`）、采集时的分辨率设置（`cmold_numbered.txt:585`）。

---

## 6. 结论汇总（只报原文有什么 / 没有什么）

| 事项 | 论文是否披露 | 依据 |
|---|---|---|
| 存在训练 + 验证的用途划分 | 披露（仅此一句） | `cmold_numbered.txt:550` + `cmold_numbered.txt:575` |
| 数据规模 nearly 4700 image pairs | 披露 | `cmold_numbered.txt:575` |
| 划分比例（80/20、6:2:2 等） | 未披露，0 命中 | 全文检索 |
| 划分单位（帧 / 录音 / 场次） | 未披露，0 命中 | 全文检索 |
| 防止同一录音相邻帧跨集合的表述 | 未披露，0 命中 | 全文检索 |
| 随机种子 | 未披露，`seed` 0 命中 | 全文检索 |
| 验证集是否独立留出 | 未披露 | `cmold_numbered.txt:575` 未说明 |
| test set / 测试集 | 未披露，`test` 仅 1 次且为动词 tested | `cmold_numbered.txt:672` |
| 表 3–6 指标在哪个集合上计算 | 未披露 | `cmold_numbered.txt:622`、`629`、`653`；`cmold_t3.png`、`cmold_t5.png` |
| 两模型共用同一划分 | 披露（"identical data splits"，指一致性而非比例） | `cmold_numbered.txt:610-612` |
| 输入分辨率数值 | 未披露，0 命中 | `cmold_numbered.txt:391-394`；`cmold_t1.png`、`cmold_t2.png` |
| resize 方式（letterbox / 拉伸 / 裁剪） | 未披露，0 命中 | 全文检索 |

一句话总结：关于"数据划分"，这篇论文只披露了两件事——"nearly 4700 image pairs were used for training and validation"（`cmold_numbered.txt:550` + `cmold_numbered.txt:575`）和同模态对比中教师/学生使用"identical data splits"（`cmold_numbered.txt:612`）；至于按什么单位切、比例多少、种子是什么、验证集是否独立、指标在哪个集合上算，以及输入分辨率与 resize 方式，全文均无表述。
