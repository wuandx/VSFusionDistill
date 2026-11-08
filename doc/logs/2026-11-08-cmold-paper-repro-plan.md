# CMOLD 论文式复现计划（分支 exp/cmold-paper-repro）

日期：2026-11-08　分支：`exp/cmold-paper-repro`（自 `main` 82b9e7d 切出）　状态：计划冻结，待执行

## 0 结论先行

本分支的目标只有一件事：**按论文描述从零搭一条 CMOLD 复现链，看论文的四个读数能不能在我方数据与实现下复现出来。**

主线 F2 与本分支的界限：本分支不参与主线，不改 `main` 的任何配置、权重、台账与读数；本分支的所有数字都只在本分支内部比较，不与主线 E11/E13 的读数混比（划分协议不同，见 §2）。

四个待复现的目标读数（TABLE 1 与 TABLE 5，`docs/investigation/cmold_numbered.txt:600-640`）：

| 级 | 臂 | 论文 AP@[.5:.95] | 论文 AP50 | 论文 AP75 |
| --- | --- | --- | --- | --- |
| R0 | YOLOX-Sonar Only No KD | 0.661 | 0.943 | 0.764 |
| R1 | YOLOX KD（声呐教师 M → 学生 S） | 0.671 | — | — |
| R2 | CMOLD（相机教师 → 声呐学生） | 0.797 | 0.949 | 0.828 |
| R3a | CMOLD 仅 objectness 项 | 0.794 | — | 0.804 |
| R3b | CMOLD 仅分类项 | 0.771 | — | 0.796 |

**论文有 12 处关键参数未披露**（§3 逐条列表）。本计划对每一处给出一个确定取值并登记为偏离；R2 的增益一律相对本分支自己的 R0，而不是相对论文的 0.661。

## 1 边界

**做**：新增文件（工具、损失、配置、测试、链脚本）；在本分支提交；在本机 WSL 的 5090/GPU 环境跑训练与评测。

**不做**：不改 `configs/f2/*`、`configs/_base_*` 的既有语义；不改 `aodet/` 既有模块的行为（只允许加性、默认关闭的接线）；不动 `doc/experiments.md`（台账由导师维护，出数后另行申请追加）；不改数据平台 `D:/pby/uxo-full` 的任何既有文件（新增子目录可以）。

**红线**：`test` 10 条录音不开封。论文本身**没有 test 集**（只写 "training and validation"，`docs/investigation/01_CMOLD论文规格.md:100`），所以这条红线与论文协议天然一致——本复现只用 train + val 两组录音。

## 2 平台与划分

| 项 | 取值 | 依据 |
| --- | --- | --- |
| 平台 | `D:/pby/uxo-full/paired` | 唯一在本机的完整平台 |
| 帧数 | train 2,652 + val 1,500 = **4,152 帧 / 37 条录音** | `frame_meta.csv` 实测；论文 "nearly 4700 image pairs … training and validation"（`01_CMOLD论文规格.md:100`）的最接近尺度 |
| 划分 | **帧级随机 8:2，seed 0，逐类分层** → 3,322 / 830 | 论文无"录音"概念；文献比较文档已量化录音级留出与帧级随机的代价差 +34.1 AP50 点（`doc/logs/2026-11-05-literature-comparison-blob.md:21`） |
| 训练集占比 | 80% | 论文未给，取 YOLOX 常用做法 |
| 声呐 GT | blob + projected 两源全用 | 论文的声呐标签来自人工标注子集 `D_L`，我方无等价物；且论文的 `D_L` 规模未披露（§3） |

**偏离 1（重要）**：本分支的帧级随机划分与主线的录音级留出**不可比**。同一份权重换考场可差 34.1 AP50 点，所以本分支的 R0 若明显高于主线 B0 的 0.258，属预期，不是矛盾。

## 3 论文未披露项的处置

| 项 | 论文写法 | 本分支取值 | 依据 / 偏离等级 |
| --- | --- | --- | --- |
| 伪标签阈值 γ | 未给（`:328-329`） | R4 才用；扫 0.5 / 0.7 / 0.9，主报 0.9 | 高偏离，仅 R4 |
| 总损失权重 λ | 未给（式 24） | 1.0，即 `L_total = L_det + L_CMOLD` | 高偏离 |
| α / β | 0.5 / 0.5 | 0.5 / 0.5 | 无偏离（已给） |
| 温度 τ | 2 | 2.0 | 无偏离 |
| top-K 的 K 上界 | 未给（`:405`、`:419-421`） | 保留 objectness ≥ 0.3 且每图至多 100 个，`K = min(教师保留数, 学生保留数)` | 中偏离 |
| 输入分辨率 | 全文无数字 | **640×640，letterbox（keep_ratio=True）**；注意本仓库的 letterbox **不 pad 到固定 640×640 画布**，只按比例缩放，padding 由 `PairedDataPreprocessor` 补到批内最大尺寸（`aodet/datasets/transforms/paired_geometric.py:77-82`、`aodet/models/data_preprocessors/paired_preprocessor.py:53`、`pad_size_divisor=32`、`pad_value=114`） | 中偏离；640 由 CMHD 复现佐证（`01:395`），letterbox 是 YOLOX 规范；画布随批变化是第三种偏离 |
| 数据增强 | 仅一句 "applied to increase the robustness"（`:294`） | **不实现 Mosaic/MixUp**（仓库无此实现，且 paired 双流同步 Mosaic 属数据语义级改动），同步翻转保持 prob=0.0，仅保留 letterbox 与既有几何/尺度抖动 | 中偏离；R0 若因此低于 0.611 再单独立项决定是否补 |
| NMS / 置信度门限 | 未给 | NMS IoU 0.65、score 0.01、每图 300（YOLOX 默认） | 低偏离 |
| 评测 maxDets | 未给 | pycocotools 默认 [1, 10, 100] | 低偏离 |
| 教师容量 | "same architecture as student"（`:392-393`） | **YOLOX-S 纯相机**（9.0 M 级），冻结 | 无偏离（照论文） |
| 教师训练数据 | 相机图全标注 | 相机 GT 全量（4,152 帧的相机框） | 无偏离 |
| 划分比例 | 未给 | 8:2 帧级 | 高偏离 |

## 4 复现阶梯

| 级 | 内容 | 关键改动 | 锚点 | 成本（本机 5060 Ti 16G） |
| --- | --- | --- | --- | --- |
| R0 | 声呐纯监督、无 KD、200 epoch、bs 8、SGD 1.25e-3→6.25e-5、mom 0.9、wd 5e-4 | 帧级划分 + letterbox + Mosaic/MixUp | 0.661 / 0.943 / 0.764 | 约 3–4 小时 |
| R1 | 传统 KD：声呐 YOLOX-M 教师 → YOLOX-S 学生（可选） | 教师 M、logit KD | 0.671 | 约 5 小时 |
| R2 | CMOLD：相机 YOLOX-S 教师（冻结）→ 声呐 YOLOX-S 学生，rank 配对 obj+cls，不蒸框 | 新增 `cmold_kd.py` + 接线 + 配置 | 0.797 / 0.949 / 0.828 | 约 4 小时 |
| R3a | R2 去分类项（β=0） | 配置覆盖 | 0.794 / AP75 0.804 | 约 4 小时 |
| R3b | R2 去 objectness 项（α=0） | 配置覆盖 | 0.771 / AP75 0.796 | 约 4 小时 |
| R4 | 伪标签自训练环（式 3/4 + Algorithm 1） | 新增伪标生成 + 二次微调 | 无对照（论文未给 γ） | 约 8 小时，最后再做 |

R0 必须先跑通并解释，再往上走：R2 的增益是相对 R0 的，R0 本身偏了，后面全部无意义。

## 5 代码改动清单（写作用域，互不重叠）

| 文件 | 归属 | 内容 |
| --- | --- | --- |
| `tools/make_frame_split.py`（新） | repro-split | 帧级 8:2 分层划分，seed 0；产出 `D:/pby/uxo-full/repro/frame_split.json` |
| `tests/test_frame_split.py`（新） | repro-split | 覆盖：三层分层比例、无重复、seed 可复现、只用 train+val 录音 |
| `aodet/models/losses/cmold_kd.py`（新） | repro-kd | 式 (11)(14)(15-18)：`select_topk`、`objectness_kd_rank`、`score_kd_rank`、`cmold_kd_losses` |
| `aodet/models/losses/__init__.py`（+1 行） | repro-kd | 导出四个符号 |
| `aodet/models/detectors/two_stream_yolox.py`（加性、默认关闭） | repro-kd | `distillation_cmold` 分支：有则调用新损失，无则走原路径 |
| `tests/test_cmold_kd.py`（新） | repro-kd | 覆盖：K=min 正确、名次单调配对、τ 缩放、梯度只对学生、α=0/β=0 时缺项不报错 |
| `configs/repro_cmold/uxo_frame_split.py`（新） | repro-config | 数据侧：新 ann 文件 + letterbox + Mosaic/MixUp + 关闭退化增强 |
| `configs/repro_cmold/r0_baseline_yoloxs.py`（新） | repro-config | R0 |
| `configs/repro_cmold/r1_kd_yoloxs.py`（新） | repro-config | R1（R0 不通则不建） |
| `configs/repro_cmold/r2_cmold_yoloxs.py`（新） | repro-config | R2 |
| `configs/repro_cmold/r3a_obj_only.py` / `r3b_cls_only.py`（新） | repro-config | R3 |
| `tests/test_repro_configs.py`（新） | repro-config | 配置可解析、`_base_` 链完整、关键键存在 |
| `scripts/cmold_repro_chain.sh`（新） | repro-run | `.ok` 断点 + 重试两次 + 日志；训练→评测→汇总 |
| 本文件 | Lead | — |

## 6 接口契约（并行前提，先冻结再开工）

- 划分产物：`D:/pby/uxo-full/repro/frame_split.json` = `{"seed":0, "counts":{"train":N,"val":M}, "train":[sonar_image_id...], "val":[...]}`；带 `--check` 自检（打印逐类分布与总帧数）。
- 数据接入（已实测确认，2026-11-08 定案）：现有数据集的分组只来自 `frame_meta` 的 `split` 列（`aodet/datasets/paired_format.py:84` `"split": row.get("split", "")`、`aodet/datasets/paired_dataset.py:105` `if self.split and sample["split"] != self.split`），而 ann 的 `images` 里没有 `split` 键、`aodet/` 全树也没有该键的读者 —— 所以改写 `repro/*.json` 的 `split` **不会被读到**，那两份文件只作留档。真正接线用新增子类 `aodet/datasets/repro_frame_split.py` 的 `FrameSplitPairedSonarCameraDataset`，按 `frame_split.json` 的 id 集合过滤 `d["coco_sonar_image_id"]`（`paired_dataset.py:124`），`split_file=None` 时与父类逐位一致。配置写法：`type="FrameSplitPairedSonarCameraDataset"`、`split_file="/mnt/d/pby/uxo-full/repro/frame_split.json"`、`split="train"|"val"`，`data_root` 仍指向 `/mnt/d/pby/uxo-full/paired`（`repro/` 没有 `frame_meta.csv`/`pairs.csv`/`images/`）。
- KD 接口（冻结签名）：

  ```python
  cmold_kd_losses(student_out, teacher_out, cfg) -> Dict[str, Tensor]
  # student_out / teacher_out: {branch: (cls, bbox, obj)}，每项为逐层 list
  # cfg: obj_weight=0.5  score_weight=0.5  tau=2.0
  #      score_thr=0.3  max_dets=100  topk=None（None 表示 K=min 保留数）
  # 返回 {"obj": scalar, "score": scalar}；某项权重为 0 时不返回该键
  ```

- 配置层：`model.cmold=dict(teacher_ckpt=..., routes={"sonar": "camera"}, ...)`，默认不存在即完全走旧路径。

## 7 团队与顺序

| 成员 | 作用域 | 交付 |
| --- | --- | --- |
| repro-split | `tools/make_frame_split.py`、`tests/test_frame_split.py` | 划分产物 + 自检通过 |
| repro-kd | `aodet/models/losses/cmold_kd.py`、`.../__init__.py`、`two_stream_yolox.py`（仅加性）、`tests/test_cmold_kd.py` | 损失 + 单测全绿 + 接线默认关闭 |
| repro-config | `configs/repro_cmold/*`、`tests/test_repro_configs.py` | 6 份配置 + 解析测试 |
| repro-run | `scripts/cmold_repro_chain.sh` | 冒烟（1 epoch）+ 发车 + 评测汇总 |

顺序：split / kd / config 三路并行（接口已在 §6 冻结）→ Lead 集成审阅并跑全量单测 → repro-run 冒烟 → R0 全量 → R2 → R3。

## 8 判据与停止条件

- 冒烟（1 epoch）：loss 全部有限值；`obj`/`score` 与检测损失同量级（0.1–10）；K 的分布有记录（中位数、最大值）；显存峰值记录。
- R0 判定：与论文 0.661 的绝对差 ≤ 0.05 → 通过，继续；> 0.05 → **停**，先解释 R0（数据标签差异 / 尺度差异 / 评测差异），不得往上堆 R2。
- R2 判定：`Δ = R2 − R0`（本分支自己的 R0）。`Δ ∈ [0.05, 0.25]` → 机制可复现；`Δ < 0.05` → 不可复现；`Δ < 0` → 反号（此时立刻停，并记录）。
- R3 判定：`R3a` 应接近 R2（论文称 objectness 项贡献约 98%），`R3b` 应明显低于 R2。若两者相反，说明我方实现与论文机制有实质性分歧，须回查配对逻辑。
- 任一级出现 NaN / 发散：重试一次，仍失败则停链并记录，不静默改超参。

## 9 风险

| 风险 | 影响 | 处置 |
| --- | --- | --- |
| 我方声呐 GT 是投影/回波框，论文是人工标注 | R0 可能系统性低于 0.661，甚至低很多 | 这本身就是结论；R0 超差时先做标签侧诊断，不直接改模型 |
| 4,152 帧 < 论文 "nearly 4700" | 绝对值偏低 | 记录，不调 epoch 找补 |
| 帧级随机划分造成近邻泄漏 | R0/R2 绝对值偏高 | 这是论文协议的性质，不是缺陷；但与主线不可比，须在表注写明 |
| 本机 16 GB 显存 + bs 8 @640 | 可能 OOM | 先冒烟测峰值；必要时开 AMP，记为偏离 |
| 论文的伪标签环节我方可复现性最低 | R2 若不含 R4，可能与 0.797 有系统性差距 | R2 先不带伪标签跑，差距归入"数据扩量缺失"一项 |

## 10 与主线的关系

本分支产出的是"论文机制在我方实现下的可复现性"这一独立结论。它**不**修改主线任何判断，但会给主线两个输入：其一，rank 配对 KD 的可用实现（若 R2 为正，主线蒸馏格可直接复用）；其二，letterbox 与帧级划分各自的量级（供主线判断"输入几何"与"协议"两项各值多少点）。
