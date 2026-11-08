# CMOLD 复现 R0 冒烟（2026-11-08）

> 目的：在跑 200 epoch 之前，用 1 epoch / 64 帧确认四件事——数据能进模型、letterbox 几何符合计划 §3、K 头相关的数据通路没断、显存与时耗撑得住。
> 依据：`doc/logs/2026-11-08-cmold-paper-repro-plan.md` §3（未披露参数）、§4（阶梯成本）、§8（判据与停止条件）。
> 执行：`scripts/cmold_repro_chain.sh --arm r0 --smoke`（stages = gate,preflight,smoke_train,smoke_report）。
> 边界：**只冒烟，不训练全量**。200 epoch 需 Lead 明确批准后另起。

---

## 0. 一句话结论

R0 冒烟通过：64 帧 1 epoch（8 iter）跑完，loss 全部有限、无 NaN/inf，checkpoint 正常落盘；数据侧读对（train 3322 / val 830，与计划 §2 一致），letterbox 确认是等比缩放（640×105 内容）而非拉伸；显存与体量都远未触顶。唯一需要 Lead 拍板的是外推时耗——**7.55 h / 200 epoch，是计划 §4 估值（3–4 h）的约 2 倍**。

---

## 1. 环境与"跑的是哪份代码"

Windows 侧 checkout（`code\VSFusionDistill`）没有 `.venv-gpu`，只能借用旧 checkout 的解释器，因此"借来的解释器 + 这份代码"必须实测确认，否则可能静默跑成旧代码：

| 项 | 值 | 证据 |
|---|---|---|
| 解释器 | `/home/ty/mycode/VSFusionDistill/.venv-gpu/bin/python` | 链日志 `train: cmd ...` |
| `import aodet` 实际路径 | `/mnt/d/agent_workspace/水下/声呐目标检测/code/VSFusionDistill/aodet/__init__.py` | 链日志 `gate: aodet -> ...`（`scripts/cmold_repro_chain.sh:328` 的 gate 段打印） |
| torch / CUDA | 2.7.1+cu128 / CUDA available True，1 张卡 | 链日志 `System environment`（第 46-74 行）：PyTorch 2.7.1+cu128、CUDA Runtime 12.8、Python 3.10.12 |
| GPU | NVIDIA GeForce RTX 5060 Ti，16311 MiB | 同上 `GPU 0`；链日志 `gpu memory before launch: 1515 MiB` |
| TorchVision / OpenCV / MMEngine | 0.22.1+cu128 / 5.0.0 / 0.10.7 | 同上（OpenCV 5.0.0 是这份 venv 的实际版本，不是笔误） |

判定：导入路径落在 `/mnt/d/.../code/VSFusionDistill/`，即本次复现要用的那份代码，不是 `~/mycode` 的旧 checkout。

---

## 2. 前置检查（冒烟之前先过这一关）

命令：`scripts/cmold_repro_chain.sh --arm r0 --stages gate,preflight`。全部结果落在 `results/repro_cmold/smoke_r0/preflight.json`。

| # | 检查项 | 结果 | 证据 |
|---|---|---|---|
| 1 | 数据入口可读 | camera.json / sonar.json / frame_meta.csv / images/ 四项 OK | 链日志 `gate: OK ...`（data_root = `/mnt/d/pby/uxo-full/paired`） |
| 2 | 划分对不对 | train 3322、val 830；`frame_split.json` seed=0，counts {train:3322, val:830} | `preflight.json:len_train`、`:split_counts`；与计划 §2 的 3,322/830 一致 |
| 3 | 数据集类型 | `FrameSplitPairedSonarCameraDataset`（走 `split_file`，不是 frame_meta 的 recording 列） | `preflight.json:dataset_type`；`configs/repro_cmold/uxo_frame_split.py:67,72` |
| 4 | letterbox 是否等比 | 是。原图 780×128 → 内容 640×105（比例 6.09 保持），batch 画布 640×128 | `preflight.json:img_shape=[640,105]`、`:pad_shape=[640,128]`、`:letterbox.keep_ratio_effective=true` |
| 5 | Mosaic 是否生效 | 未配置（pipeline 共 4 项，无 Mosaic/MixUp；样本里也没有 mosaic 标记键） | `preflight.json:pipeline`、`:mosaic_entries=[]` |
| 6 | 标注是否进模型 | 抽 7 帧（index 0/200/800/1600/2400/3200/3321）**7 帧全部有 sonar 框**，共 7 个框 | `preflight.json:annotation_census`、`:census_frames_with_boxes="7/7"` |
| 7 | 可视化 | 640×105 HWC，GT 框（绿）与亮斑回波对齐 | `results/repro_cmold/smoke_r0/preflight_sample_sonar.png` |

### 2.1 关于第 5 项（Mosaic）

仓库里**没有** Mosaic/MixUp 实现，三处出现都是禁止性注释（`configs/_base_/datasets/paired_uxo.py:6`、`aodet/datasets/transforms/paired_geometric.py:10`、`aodet/models/detectors/two_stream_yolox.py:16`）。本轮按 Lead 2026-11-08 决定不实现、R0 不带增强跑，登记偏离见 `configs/repro_cmold/uxo_frame_split.py:48-57`。冒烟只做"确认没配"，不改数据处理语义。

### 2.2 关于第 4 项：实际画布不是 640×640

计划 §3 写的是"640×640 letterbox keep_ratio=True"，实测更准确的描述是：**等比缩放到 640 长边、不补边**（`aodet/datasets/transforms/paired_geometric.py:77-82` 只 resize 不 pad），补边发生在 batch 组装时由 `PairedDataPreprocessor.stack_batch` 按 `pad_size_divisor=32`、`pad_value=114`（`configs/repro_cmold/r0_baseline_yoloxs.py:48`）补到**本批最大宽度**，所以 2 张 105 宽的样本得到 640×128，而不是固定的 640×640。YOLOX 原配方是每张图 Pad 到 640×640 固定画布——这一条按偏离登记，不影响本轮判据，但读 per-image 结果时要记得画布宽度随批变化。

---

## 3. 冒烟数字

命令：`scripts/cmold_repro_chain.sh --arm r0 --smoke`（`--cfg-options train_cfg.max_epochs=1 train_dataloader.dataset.indices=64`，见 `scripts/cmold_repro_chain.sh:663`）。
产物：`work_dirs/repro_cmold/smoke_r0/epoch_1.pth`、`results/repro_cmold/smoke_r0/smoke.json`。
时间线：21:57:32 起链 → 21:57:43 起训 → 21:57:52 训完 → 21:57:58 出报告，整链 26 s，rc=0。

| 指标 | 值 | 说明 |
|---|---|---|
| 规模 | 8 iter × bs 8 = 64 帧，1 epoch | `smoke.json:iters_per_epoch_smoke=8` |
| 总 loss | 26.7423 | epoch 末一行 |
| loss_cls / loss_bbox / loss_obj | 1.5278 / 4.3566 / 20.8578 | 三者相加即总 loss |
| loss 有限性 | **全部有限，无 NaN/inf** | `smoke.json:loss_all_finite=true`、`:fatal_terms=[]` |
| grad_norm | 436.2094 | 裁剪前的总范数（见注 1） |
| lr | 5.0000e-05（base_lr 同值） | warmup 第 1 epoch，符合 `r0_baseline_yoloxs.py:60` 的 base_lr=1.25e-3 与 5 epoch 二次 warmup 的组合 |
| 每步耗时 | 0.3267 s/iter（最后一步同值） | `smoke.json:sec_per_iter_mean` |
| 数据时间 | 0.069 s/iter → dataloader 约 115.9 imgs/s | `:data_time_mean`、`:dataloader_imgs_per_s` |
| 训练吞吐 | 24.49 imgs/s | `:train_imgs_per_s` |
| 显存（torch 侧） | 900 MB（max_memory_allocated） | `:torch_max_mem_mb` |
| 显存（设备侧） | 峰值 2688 MiB，启动前 1515 MiB | `:vram_peak_mib`、`:vram_first_mib`（2 s 采样 6 次） |
| 外推 | 416 iter/epoch → 135.9 s/epoch → **200 epoch ≈ 7.55 h** | `:iters_per_epoch_full`、`:sec_per_epoch_full_est`、`:full_run_hours_est` |

注 1：`grad_norm` 是**裁剪前**的总范数。mmengine 的 `OptimWrapper._clip_grad` 调用 `torch.nn.utils.clip_grad_norm_`（该函数返回裁剪前的总范数）后把返回值写进 `train/grad_norm`（venv 内 `mmengine/optim/optimizer/optimizer_wrapper.py:135-136,294-299`）。所以 436.2094 说明前 8 个 iter 的梯度被 max_norm=35 大幅裁剪（`configs/_base_/schedules/schedule_f2.py:36`）——YOLOX 冷启动期 lr 很小而 `loss_obj` 仍大（20.86），属常见形态，不作为异常判据；要看的是全量前若干 epoch 是否降下来。
注 2：`loss` 只记录到 **1 个点**，因为 LoggerHook interval=50 而本 epoch 只有 8 iter，所以 `loss_min == loss_max == epoch 末值`；这不是"loss 没变化"，而是采样粒度问题。绝对数值也不代表收敛水平（1 epoch × 64 帧、warmup 首段）。

### 3.1 与计划 §8 判据的对照

| §8 判据 | 本轮结果 | 判定 |
|---|---|---|
| 所有 loss 有限 | 是 | 过 |
| obj/score loss 与检测 loss 同量级（0.1–10） | R0 无 KD 分支，obj 属检测 loss 本体（20.86）；KD 的量级判据留给 R2 | 不适用 |
| K 分布 | R0 无 KD | 不适用 |
| 显存峰值可接受 | torch 0.9 GB / 设备 2.7 GB，16 GB 卡余量充足 | 过（计划 §9 首条 OOM 风险基本解除，R2 带教师另测） |

---

## 4. 本轮修掉的四个脚本缺陷（都是冒烟过程中暴露的，记录以备复查）

| # | 现象 | 原因 | 处理 |
|---|---|---|---|
| 1 | 训练明明成功，链却判 `liveness FAILED` 并重试一次 | `run_training` 把"10 分钟内退出"一律当死亡，而 64 帧 1 epoch 只要 3 s | 改为"窗口内退出且 rc=0 且已有 checkpoint → 接受为短跑"，真正的静默早退仍判失败（`scripts/cmold_repro_chain.sh:282-299`） |
| 2 | 可视化报 `libpng error: Invalid IHDR data`，`imwrite` 返回 False | `img_sonar` 是 CHW，直接喂 `cv2.imwrite` 被当成 H×W×640 | 转 HWC + RGB→BGR，并检查写入返回值；数据本身无问题（PGM/JPEG 解码全程无报错） |
| 3 | 标注普查一开始永远是 0 个框 | `AOPackPairedInputs` 把框移进 `data_samples_*.gt_instances` 后，结果字典里已没有 `boxes_sonar`（`aodet/datasets/transforms/pack_paired.py:151-158`） | 改从 `data_samples_<side>.gt_instances.bboxes` 读，并新增 7 帧普查（`scripts/cmold_repro_chain.sh:527-546`） |
| 4 | `fatal_terms` 报 `INF`，且在重跑时"越报越多" | 子串匹配把 mmengine 的 `INFO` 当成 `inf`；重跑时报告把自己的 JSON 转储写进链日志，又被自己扫到 | 改词边界正则 `\b(?:nan|inf)\b`，并把扫描范围截到 `smoke: collecting numbers` 之前（`scripts/cmold_repro_chain.sh:700-706,787`） |

---

## 5. 偏离与未决项

1. **外推时耗 7.55 h vs 计划 §4 的 3–4 h（约 2 倍）**。首轮含 cudnn 预热与基准点采样，稳态应快于此，故 7.55 h 视为上界；但要坐实需跑前 1–2 个 epoch 的稳态值。R0 全量发车前需要 Lead 决定：接受 7.5 h，还是先补测稳态。
2. **Mosaic/MixUp 未实现**（§2.1），登记偏离。
3. **输入画布随批变化**（§2.2），非固定 640×640，登记偏离。
4. **解释器借用旧 checkout 的 venv**（§1）；代码侧已确认导入正确，但环境不是这份 checkout 自带的。
5. **同步翻转 prob=0.0**（`uxo_frame_split.py:93`）、多尺度关闭（`uxo_frame_split.py:82-84`）——配置里已按计划登记，本轮未复查其影响。
6. 脚本落在**仓库内** `scripts/cmold_repro_chain.sh`（按 task-4 写作用域），而历史链都在工作区根 `scripts/`；两处并存，用时注意路径。
7. `doc/logs/README.md` 的索引行尚未加（该文件不在本次写作用域，留给 Lead 统一补）。

---

## 6. 下一步

1. R0 全量 200 epoch：**等 Lead 明确批准**。命令 `scripts/cmold_repro_chain.sh --arm r0 --full`（估 7.5 h 上界）。
2. R0 出 AP 后按计划 §8 过门禁：|AP − 0.661| ≤ 0.05 才允许上 R2；若 R0 < 0.611，先按 Lead 的"低于 0.611 再单独立项决定是否补 Mosaic"规则处理。
3. 评测一律 `--split val --levels d0`（脚本 `stage_eval` 已固定），测试场次保持封存。
