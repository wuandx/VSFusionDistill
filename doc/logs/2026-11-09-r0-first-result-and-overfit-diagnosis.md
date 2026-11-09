# R0 首次读数与过拟合诊断（2026-11-09）

分支 `exp/cmold-paper-repro`，臂 R0（声呐单支路 YOLOX-S，无蒸馏），
`work_dirs/repro_cmold/r0/epoch_200.pth`，200 epoch 完整跑完
（`r0.train.ok`，2026-11-09 01:12）。评测 `--levels d0`，val 830 帧
（帧级 8:2 随机划分，`D:/pby/uxo-full/repro/frame_split.json`）。

## 1 读数

| 口径 | AP@[.50:.95] | AP50 | AP75 |
|---|---|---|---|
| gt=all（blob+projected，与训练标签同源） | 0.5347 | 0.7429 | 0.5697 |
| gt=blob | 0.3989 | 0.6979 | 0.4273 |

论文 R0（YOLOX-Sonar Only No KD，TABLE 1/5）：0.661 / 0.943 / 0.764。
按 gt=all 口径，差 −0.126 / −0.200 / −0.194。

逐类（gt=all，录音平均，`ap_breakdown.json`）：

| 类别 | 录音 | n_gt | mean AP | mean AP50 |
|---|---|---|---|---|
| 100lbs_aircraft_bomb | 11 | 456 | 0.5255 | 0.6918 |
| mortar_shell | 16 | 674 | 0.5054 | 0.7546 |
| incindiary_grenade | 13 | 530 | 0.6224 | 0.8212 |

gt=blob 口径下炸弹塌到 0.2855 / 0.4827 —— 与"训练同时吃 projected 框、
评测只看 blob 框"一致，说明模型有相当一部分置信度落在几何投影框上。
28 条 val 录音全部非零（mainline 录音级留出时出现过的"整条 AP=0"没有
出现），与帧级划分把同一场次的相邻帧分到两边的预期一致。

## 2 预登记判据核对

计划 §5 的闸门是"R0 与 0.661 差 ≤0.05 才继续"。实测差 0.126，**未过闸门**，
因此 R1/R2/R3a/R3b 不得发车；按计划先做归因。

## 3 过拟合诊断（决定性）

同一份 `epoch_200.pth` 在其**自己的训练划分**（3,322 帧）上重评：

| 划分 | AP@[.50:.95] | AP50 | AR@100 |
|---|---|---|---|
| train 3,322 帧 | **0.9947** | 0.9967 | 0.9988 |
| val 830 帧 | 0.5347 | 0.7429 | 0.5200 |

读法：网络、损失、优化器、数据管线都能正确表达这个任务（训练集几乎满分），
差距全部来自**泛化**而不是上游实现错误。R0 的训练管线除 letterbox 缩放外
没有任何增强——`configs/repro_cmold/uxo_frame_split.py:87-95` 只有
`AOLoadPaired → AOPairedResize → AOPairedSyncFlip(prob=0.0) → AOPackPairedInputs`，
而 YOLOX 公开配方依赖 Mosaic 1.0 / MixUp 0.5 / HSV / RandomAffine / flip 0.5
（mmdet 3.3.0 `configs/yolox/yolox_s_8xb8-300e_coco.py`）。论文对增强只有一句
"applied to increase the robustness"（`docs/investigation/01_CMOLD论文规格.md`
第 3 节），不写具体增强集——因此"论文用了哪些增强"属永久未知，"我方一个
都没用"是已核实事实。

## 4 与文献的横向对照（口径已核）

CMHD 原文写明 "all AP and mAP metrics are reported as AP@[0.50:0.95]"
（`docs/investigation/cmhd_params_numbered.txt`），因此其无蒸馏基线
YOLOX-S-Ghost 77.0 = 0.770 AP@[.50:.95]，CMHD 复现的 CMOLD 75.3 = 0.753。
同一 CMHD 还写明所有检测器都在 "the same geometrically projected sonar
labels" 上训练评测，故**标签噪声不是我方独有的劣势**。

| 来源 | AP@[.50:.95] |
|---|---|
| 我方 R0（帧级 val 830） | 0.5347 |
| CMOLD 原文 R0 | 0.661 |
| CMOLD 原文 R2（CMOLD） | 0.797 |
| CMHD 复现 CMOLD | 0.753 |
| CMHD 无蒸馏基线 | 0.770 |

即：我方 R0 比论文 R0 低 12.6 点，比同组可复现水平（0.753–0.770）低 22–24 点。
在差距归因完成前，不得用"protocol 不同"解释这 12.6 点——本次已是帧级划分，
与论文同性质。

## 5 处置（诊断臂，非阶梯的一级）

新增 `configs/repro_cmold/r0a_aug_yoloxs.py`：只加本仓库**已有**的两个增强
——`AOPairedSyncFlip(prob=0.5)`（双流同步水平镜像）与
`AOSonarScaleJitter((0.8,1.25), prob=0.8)`（仅声呐距离轴）。两者都是几何精确
的标签变换，不引入标签噪声。Mosaic/MixUp 仍缺（计划 §3：双流同步 Mosaic 属
数据语义级改动）。

**读取规则（发车前已固定，写在配置 docstring 里）**：val AP@[.50:.95] 若
< 0.58，说明两个廉价增强解决不了、Mosaic/MixUp 才是候选；若 ≥ 0.58，则阶梯的
R0 应带增强重定义（属计划修订，需批准，不静默替换）。

## 6 未解决项

1. `tools/test.py --split` 与 split_file 数据集不兼容（`--split` 会把
   `dataset.split` 置 None，而该数据集拒绝 None）。**处置改为分支隔离**：不修
   共享工具，链脚本的 eval 阶段改用 `--cfg-options
   test_dataloader.dataset.split=val`（config 已钉 val，效果等价，test 仍不开封），
   共享的 `tools/test.py` 与 `tests/test_anatomy_tools.py` 在本分支保持与 main
   逐位一致。
2. 台账 `doc/experiments.md` 尚未入账（共享文件，按只追加规则待批）。
3. 我方 R0 与论文 R0 的"增强集"差异只能定性：论文未披露，属永久未知。

## 7 R0-aug 结果（2026-11-09 07:10 训完，08:55 评测）

| 臂 | gt | AP@[.50:.95] | AP50 | AP75 | AR@100 |
|---|---|---|---|---|---|
| R0 | all | 0.5347 | 0.7429 | 0.5697 | 0.6163 |
| R0-aug | all | **0.5247** | 0.7444 | 0.5652 | 0.6037 |
| R0 | blob | 0.3989 | 0.6979 | 0.4273 | 0.5200 |
| R0-aug | blob | **0.4236** | 0.7141 | 0.4483 | 0.5222 |

按 §5 事先固定的读取规则：val AP 0.5247 < 0.58 → **两个廉价增强不是答案**，
翻转与距离轴缩放不但没救回差距，在 gt=all 口径下还低了 1.0 点（gt=blob 口径
高 2.5 点，方向不一致，视为噪声）。结论：Mosaic/MixUp 或标签语义才是候选，
不能靠"补两个便宜的增强"了事。

## 8 诊断 C：画布补边（batch-max padding）不是原因

训练时一批 8 张图补到批内最大尺寸，评测 `batch_size=1` 时完全不补（105×780
原图按比例缩到 105×640 的长条）。怀疑这构成训练/评测画布不一致，于是用同一份
权重、同一划分、`test_dataloader.batch_size=8` 重评：

| 评测批大小 | AP@[.50:.95] | AP50 | AR@100 |
|---|---|---|---|
| 1（原读数） | 0.5347 | 0.7429 | 0.6163 |
| 8（对齐训练时的补边行为） | 0.5347 | 0.7426 | 0.6166 |

逐位相同 → 补边不影响结果，画布假设排除。这条也说明 `r0_baseline_yoloxs.py`
docstring 里"读每图结果时要记得画布随批变化"的提醒，在本任务上无实际后果。

