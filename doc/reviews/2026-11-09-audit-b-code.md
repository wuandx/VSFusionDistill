# CMOLD 复现代码审计（audit-b，只读）

- 审计对象：分支 `exp/cmold-paper-repro`，HEAD 与 `origin/main` 差 31 文件（+6325/−2）。
- 审计范围（均逐行读全文，非 grep）：`aodet/models/losses/cmold_kd.py`（313 行）、`aodet/models/detectors/two_stream_yolox.py` 的 cmold 接线（442 行）、`aodet/models/teachers/frozen_teacher.py`（141 行）、`aodet/datasets/repro_frame_split.py`（146 行）、`configs/repro_cmold/` 全部 11 个 `.py`（含 `teachers/`）、`scripts/cmold_repro_chain.sh`（882 行）、`tools/test.py`（211 行）、`tests/test_cmold_kd.py`（500 行）、`tools/check_cmold_off_is_noop.py`（210 行）。
- 论文依据：`docs/investigation/cmold_numbered.txt` 式(10)(11)(12)(14)(15)-(19)(21)-(24) 与 Algorithm 1。
- 只读约束遵守情况：本审计未修改任何代码/配置，未跑训练，未执行 git 写操作，未 ssh。本机无 torch/mmdet（`python -c "import torch"` 失败），故所有需要前向的核验都只能列为"待跑"，无法在本次给出数值。

## 0. 结论

实现把论文式(11)(14)(15)-(19)的**结构**忠实落地了：降序排序、K=min、1/K 分母、只取 objectness 与分类、τ² 缩放、α=β=0.5、τ=2、完全不碰 bbox_pred，教师三重只读（`no_grad` + `requires_grad=False` + 永久 `eval`），R0 逐位不进 KD 分支。这些点没有找到反例（见 §4）。

但**被检验的不是论文那个机制，而是一个参数化后规模小一个数量级的实例**：K 实测约 8–9 对/图，由论文里根本没有的 `score_thr=0.3` 决定；门控同时对**学生**生效，把"学生定位得不好的单元"整体排除在蒸馏之外；逐层 min 又让"某一层任一模态没有高置信单元"时整层消失；λ=1.0 也是论文未给的自由参数，而收敛末期 KD 项已经和整条检测损失同量级。三条都朝同一个方向偏置（收益变小、方差变大），因此 **R2 −2.1（AP）/−2.8（AP50）这一读数不能外推为"CMOLD 机制无效"**。

可以成立的表述只有一句：*在 K≈8–9、逐层配对、λ=1 的这一具体实例化下，单种子 seed 0 未测到正增益（Δ<1σ）。*

## 1. 高严重度

### H1 K 的实际规模由论文未给的 `score_thr=0.3` 决定，且逐层 min 会让"没有高置信单元"的层整层消失

- 文件:行号
  - `aodet/models/losses/cmold_kd.py:96-104`（`select_topk`：`masked_fill(scores < score_thr, -inf)`，`count = (scores >= score_thr).sum(1).clamp(max=m)`）
  - `aodet/models/losses/cmold_kd.py:133-139`（`_paired_k`：逐层 `k = torch.minimum(cnt_s, cnt_t)`）
  - `aodet/models/losses/cmold_kd.py:171-174`（`for lvl in range(n)`；`if k.sum()==0: continue`）
  - `configs/repro_cmold/r2_cmold_yoloxs.py:100-101`（`score_thr=0.3, max_dets=100, topk=None`）
  - 论文：`:405` 式(10) K=min；`:419-421` 式(11)；`:477` "a top-K selection strategy, as implemented in Algorithm 1"；`:482` "can be readily adapted to enforce an upper bound on K"（**上限是可选增强，不是默认**）。
- 现象：论文只说"only the retained high-confidence predictions are considered"（`:401-403`），**全文没有给保留阈值或保留数**（`:512` 起的 Table 2 与正文均无数值）。实现把保留准则定为 `sigmoid(obj) >= 0.3`，并在**每一层**独立做一次 top-K 配对；`score_thr` 直接进入 `count`，而 `count` 直接就是 K。项目自己的记录是每图 8–9 对（`doc/logs/2026-11-09-r2-cmold-and-geometry-readings.md:60-61`），`max_dets=100` 从未触顶（K≪100），所以真实约束是阈值而不是上限。
- 为什么影响结论：K 不是实现细节，它是这篇论文唯一的信息预算——式(14) 与式(16) 都是 `1/K Σ_{k=1..K}`，K 从论文可能的上百个位置（整图全部保留预测）降到 8–9，等价于把蒸馏信号压到 1/10 量级，同时把梯度噪声放大（每批 8 图 × 8 对 ≈ 64 项）。**用一个 K≈8 的稀疏变体得不到增益，不能推出 K 更大的原版得不到增益。** 另外"逐层 min"引入论文不存在的第二种稀疏化：全图单列排序时 K 只由两张列表长度决定，任何一层都不可能被整体丢弃；逐层 min 下只要教师在某层没有 ≥0.3 的单元（或学生没有），该层 `k.sum()==0` 直接 `continue`，该层的全部蒸馏信号消失。R2 记录里"教师 objectness 只在最粗层出现"（同文档 `:60-61`）正是这个机制的可见后果——三个 FPN 层只剩一层参与。
- 怎么验证（不需要改代码，只需前向）：
  1. 用 `work_dirs/repro_cmold/r0/epoch_200.pth` 与 `work_dirs/repro_cmold_teacher/t_camera_s/epoch_200.pth` 在 val 830 帧、`deg_level=d0` 上跑一次纯推理，按层打印 `cnt_s`、`cnt_t`、`k=min`，给出 K 的中位数/分位数/零层比例。这条也是 `doc/logs/2026-11-08-cmold-paper-repro-plan.md:122` 预登记的冒烟项（"K 的分布有记录（中位数、最大值）"），目前只有一句 8–9，没有分布。
  2. 阈值敏感性：`score_thr ∈ {0.01, 0.05, 0.1, 0.3, 0.5}` 各跑一次离线统计（只前向），看 K 随阈值变化的曲线。若 0.05 时 K 已到 40–60，则说明 0.3 这一格是凭 NMS 习惯选的，不是论文口径。
  3. 若要动手改，唯一需要改的是"把三层拼接成 (B, Σn) 后做一次 `select_topk` + 一次 `min`"，改完 K 与 loss 必须能被一个独立计算脚本复算对上——而不是像现在这样由 `tests/test_cmold_kd.py:156-167` 把逐层语义钉死。
- 备注：`doc/logs/2026-11-08-cmold-paper-repro-plan.md:51` 已把 0.3/100 登记为"中偏离"。本条的判断比"中偏离"重，理由是登记时没有量化它对 K 的影响；K 一旦是 8，就不是偏离，而是换了一个问题。

### H2 objectness 门控同样作用在学生身上，被蒸掉的恰是"学生已经定位得好"的单元

- 文件:行号
  - `aodet/models/losses/cmold_kd.py:96-104`（学生与教师共用同一个 `score_thr`）
  - `aodet/models/losses/cmold_kd.py:133-139`（`k = minimum(cnt_s, cnt_t)`，`cnt_s` 来自学生自己的 `scores >= score_thr`）
  - `aodet/models/losses/cmold_kd.py:172-174`（`k.sum()==0` 即整层跳过）
- 现象：K=min 的语义是"两张列表的较短者"，实现正确地落在了学生侧；但因为两张列表都先过 0.3 门控，学生的弱预测（`sigmoid(obj)<0.3`，即 IoU 目标低、定位差或漏检的单元）根本不进入候选集。学生某层一个 ≥0.3 的单元都没有时，`k.sum()==0`，该层零梯度。
- 为什么影响结论：这构成一个**方向性偏置**：蒸馏只能在校准"学生已经找到并且已经定位得不错"的单元上，对"学生漏掉或框歪"的单元既不给对象性监督也不给分类监督——而那正是跨模态蒸馏理应最有价值的部分。于是"加了 CMOLD 没有提升"这一观测天然被压低，且不能用它反驳"相机知识可以改善声呐的漏检"。论文的 K=min 是同样的公式，但论文没有阈值这一步，K 的上界只是"可选"（`:482`）；把一步可选的截断变成必经的门控，是在公式之外加的。
- 怎么验证：
  1. 在 val 上统计"GT 有目标、但学生该层 `max sigmoid(obj) < 0.3`"的帧比例（前向即可）。若这个比例不低（预期 >20%，学生 AP50 只有 0.74），说明大量真目标落在蒸馏视野之外。
  2. 反事实：把 `score_thr` 降到 0.01 后重算 K 与 `loss_obj`；若 `loss_obj` 量级变化不大而 K 显著上升，说明当前 loss 被少数高置信单元支配。
  3. 与 R3a（obj only）/R3b（cls only）联读：若两者都不动，先怀疑是"没有配对被选中"，而不是"知识没用"。

### H3 λ=1.0 是论文未给的自由参数，而 KD 项在收敛末期与整条检测损失同量级

- 文件:行号
  - `configs/repro_cmold/r2_cmold_yoloxs.py:24-26`（docstring 自述"语义 α=β=0.5、τ=2、score_thr=0.3、max_dets=100、topk=None、λ=1.0 结构性"）
  - `configs/repro_cmold/r2_cmold_yoloxs.py:97-99`（`obj_weight=0.5, score_weight=0.5, tau=2.0`）
  - `aodet/models/losses/cmold_kd.py:181`（`den += float(k.sum())`）、`:244`（`den += k.sum()`）、`:247`（`* tau**2`）
  - `aodet/models/detectors/two_stream_yolox.py:375-376`（返回 `cmold/loss_obj`、`cmold/loss_score`，键里带 `loss`，`parse_losses` 直接求和）
  - 论文：`:548` 式(24) Ltotal = Ldet + λ·LCMOLD；`:550` λ 控制蒸馏项总权重，**未给数值**；`:531-535` α=β=0.5、τ=2（这两项实现与论文完全一致）。
- 现象：式(20)-(23) 的检测项分母分别是总位置数 `N_all`、正样本数 `N_pos`（`:521-525`、`:531-533`、`:542`），而两个蒸馏项的分母是 `Σ_g K_g`（约 8–9 对/图）。两者不是同一个归一化尺度，实现里没有任何让它们可比的换算，λ 取 1.0 就等于让两项按"各自的均值"直接相加。实测后果：R2 训练日志（经 R2 记录 `:60-61` 转述）`cmold/loss_obj` 0.08–0.09、`cmold/loss_score` 0.07–0.29；同日 R0 收敛末期（`work_dirs/repro_cmold/r0/20261108_220411/20261108_220411.log`，epoch 200）总 loss 0.1385–0.1542，其中 cls 0.049–0.054、bbox 0.087–0.097、obj 0.0027–0.0043。也就是说蒸馏项之和已经追上甚至超过整条检测损失。
- 为什么影响结论：这意味着 R2 不是"R0 + 一个小扰动"，而是"R0 + 一个与之等量级的第二目标"。当第二目标与检测目标冲突（相机与声呐的 objectness 分布本来就不同），−2.8 点是**过强蒸馏**的合理结果，不能读成"跨模态知识无用"。论文没有给 λ，所以我方取 1.0 既不能称"对齐"，也不能称"偏离"，只能称"未定"；在这种参数自由度下得到负结果，方向性结论不可用。
- 怎么验证：
  1. 用 λ∈{0.1, 0.25, 1.0} 三格（其余不动）各跑一次 seed 0，看 ΔAP50 随 λ 的走向。若 λ=0.1 时 Δ≈0 而 λ=1 时 −2.8，则负结果归因于权重而非机制。
  2. 更便宜的前置检查：在 R2 的 checkpoint 上分别关掉 KD 项评估（评测本来就不走 KD，见 `two_stream_yolox.py:378-410`），确认 −2.8 是训练期造成的而不是评测路径造成的（后者已被代码排除，但值得留一条反证）。
  3. 记录每 100 步 `cmold/loss_obj`、`cmold/loss_score` 与 `uncoupled_sonar/loss_*` 的比值曲线；本机无 R2 日志，这条是"应当有但现在没有"的产物。

## 2. 中严重度

### M1 没有任何"蒸馏确实在生效"的断言，KD 静默为 0 是可达状态

- 文件:行号
  - `aodet/models/losses/cmold_kd.py:174`（`if k.sum() == 0: continue`，静默跳过整层）
  - `aodet/models/losses/cmold_kd.py:182-184`（没有累加任何项时 `num` 为 None，返回 `_zero_like` 的 0）
  - `aodet/models/losses/cmold_kd.py:308-312`（只在 `matched == 0` 时 raise；`matched` 计的是"route × 层配对尝试"，不是"真实配对数"）
  - `aodet/models/detectors/two_stream_yolox.py:370-371`（`t_in is None` → `return {}`，不报错）
  - `scripts/cmold_repro_chain.sh:810-813`（评测只要求 `ap_summary.json` 存在）、`:816-834`（summary 不读 loss）
- 现象：三种"看不见的失效"都通向同一个终点——训练照常、曲线照常、loss 键照常存在（值为 0 或极小），没有任何一环会失败。学生前 2 个 epoch objectness 全低于 0.3 时 KD 恒为 0（R2 记录 `:60-61` 说"从第 3 轮起"出现 0.08–0.09，与此一致）；若某种配置下始终为 0，产出的 R2 就是一个换了种子的 R0，而报告里会写"KD 已开启但无增益"。
- 为什么影响结论：这是最典型的"机制看起来无效"的静默通道，而且它不会被测试抓住——`tests/test_cmold_kd.py:143-153` 把"空保留 → 0 且有限"当作**期望行为**固定下来。
- 怎么验证：在 `stage_smoke_train` 的产物里加一条硬断言：`cmold/loss_obj` 的中位数 > 0 且 K 的记录非空；`stage_eval` 前读训练日志确认最后 10 个 epoch 的 `cmold/loss_*` 非零。当前 R2 实际是激活的（有 0.08–0.09 的记录），所以这条目前未造成事故，但它是下一次静默失效的入口。

### M2 `--split val` 在新数据集上不可用，"评测一律显式 `--split val`"的硬纪律实际无法执行

- 文件:行号
  - `tools/test.py:118-123`（传 `--split` 时把 `dl_cfg.dataset.split = None`）
  - `aodet/datasets/repro_frame_split.py:107-111`（`split_file` 非空而 `split` 不在 `("train","val")` 时 raise，"refusing to fall back to 'every frame' ... would admit the test recordings"）
  - `scripts/cmold_repro_chain.sh:802-812`（注释解释因此不用 `--split`，改用 `--cfg-options test_dataloader.dataset.split=val`）
  - `configs/repro_cmold/uxo_frame_split.py:128-130`（`test_dataloader` 自身已写 `split="val"`）
- 现象：CLAUDE.md 的硬纪律要求评测显式传 `--split val`，但这条路径在新数据集上必然抛异常（`split=None` 被数据集拒绝）。chain 的绕法是对的（`:811`），代价是"评测用哪个 split"完全由 config 一处决定，没有任何二次校验；任何人手工跑 `tools/test.py config ckpt --split val` 会直接崩，而手工跑 `tools/test.py config ckpt`（不传）则依赖 config 恰好写着 val。
- 为什么影响结论：混入 test 录音是不可恢复的事故，而现在的防线只剩"config 里那一行没被改错"。这次没有混（830 帧口径与 `frame_split.json` 一致，见 `scripts/cmold_repro_chain.sh:485` 的 `EXPECTED_LEN`），但机制上缺一道闸。
- 怎么验证：跑 `tools/test.py configs/repro_cmold/r0_baseline_yoloxs.py <ckpt> --split val` 应得到 `ValueError`（未确认实际异常类型，按 `:107-111` 推断）。建议在 `stage_eval` 里评测后回读 `pred.*.json` 的 image_id 集合与 `frame_split.json["val"]` 求差集，差集非空即 exit 1。

### M3 `stage_eval` 取"最新 mtime 的 epoch_*.pth"，不校验 epoch

- 文件:行号：`scripts/cmold_repro_chain.sh:799`（`ckpt="$(newest_ckpt "$WD")"`，实现是 `ls -1t epoch_*.pth | head -1`）、`:810-813`
- 现象：训练中断（或 `TRIES=2` 用尽后人工续跑）时目录里留下 `epoch_190.pth` 之类，`stage_eval` 会照常评测它并写进 `results/.../eval_val`，`ap_summary.json` 也照常生成，链路不报错。`run_training` 的存活判据（`:266-326`，`LIVENESS_S=600`）只判"还活着"，不判"跑完了"。
- 为什么影响结论：一个训练不完整的臂会被当作 R2 出数，方向通常是**低估**（少训 10 轮）；而结果文件与完整臂同名同目录，事后无法从产物判别。
- 怎么验证：读 checkpoint 的 `meta["epoch"]`（mmengine 会写）与 `max_epochs=200`（`r0_baseline_yoloxs.py:44`）比对。本机无 R2 产物（`results/repro_cmold` 下无 `r2`），**5090 上实际取到的是哪一轮，未确认**。

### M4 逐层聚合 `Σ_g Σ_k / Σ_g K_g` 与式(14) 的"单图单一 K"不等价（当前近似巧合）

- 文件:行号：`aodet/models/losses/cmold_kd.py:181`、`:244`（`den` 跨层累加）、`:184`、`:247`（返回 `num/den`）
- 现象：实现的输出是"按层拆开的 K 个 pair 的池化均值"，权重是各层 K；论文式(14) 是单图 K 个 pair 的 `1/K`，跨图再由批量平均。当前因只有最粗层有配对（H1），两者数值恰好一致；一旦多层同时有配对，图像之间按 K 加权的权重就与论文不同（K 大的图像权重大）。
- 为什么影响结论：现在影响为零（只有一层），所以它不改变 R2 的读数；但它意味着"若按 §H1 改成全图单列，聚合也必须一起改"，否则会把两种偏离叠在一起。`tests/test_cmold_kd.py:156-167` 已经把 `(2*lvl0 + 1*lvl1)/3` 写成断言，改动会同时打破测试——测试保护的是实现契约，不是论文。
- 怎么验证：构造一个两层各有配对的 batch，手算 `Σ/ΣK` 与"逐层均值再平均"的差异；两者不等即为证据（用现有测试夹具即可，无需真实数据）。

## 3. 低严重度

### L1 `stage_summary` 的 headline 过滤条件永远匹配不到

- 文件:行号：`scripts/cmold_repro_chain.sh:828`（`r["branch"]=="sonar"`）
- 现象：实测 `results/repro_cmold/r0/eval_val/ap_summary.json` 的 `branch` 字段是 `"sonar_uncoupled"`（`two_stream_yolox.py:223-228` 的分支名；R0/R2 没有 fused 头，`outs` 里不存在 `"sonar"`）。因此 `:829-832` 的 headline 分支永远为空，只打印表格。
- 为什么影响结论：不影响 AP，只影响"链跑完有没有 headline"这一可用性判据；操作者可能误判 summary 失败。属于汇报缺陷。
- 怎么验证：`Get-Content results/repro_cmold/r0/eval_val/ap_summary.json` 直接看 `branch` 值（本次已核）。

### L2 objectness 项在 fp16 下计算

- 文件:行号：`aodet/models/losses/cmold_kd.py:176-179`（`vs`/`vt` 未 `.float()`，`diff**2` 在 autocast 的 fp16 里完成）；对比 `:235-238`（KL 项显式 `autocast(enabled=False)` + `.float()`）
- 现象：两个损失项精度处理不一致。`diff` 量级 1e-2–1e-1，平方后 1e-4–1e-2，fp16 尾数在 1e-3 量级仍有 ~6 位有效数字，**当前不构成错误**；但 `k` 很小时（H1）单批只有几十项，舍入误差相对放大。
- 为什么影响结论：只在"Δ 极小"的判据下才有意义（本审计的 Δ 是 2.1–2.8 点，远大于舍入误差），故判低。
- 怎么验证：把 `:178` 前加 `.float()`，同 batch 前后比对 loss 的相对差（应 <1e-3）。

### L3 教师侧死流每步都前向，且教师权重取最后一轮而非 EMA/最优

- 文件:行号：`aodet/models/teachers/frozen_teacher.py:127`（`son_feats = model.sonar_neck(model.sonar_backbone(sonar))` 无条件执行）、`:129-138`（有 uncoupled 头才输出该分支）；`configs/repro_cmold/r2_cmold_yoloxs.py:73-75`（注释承认"the sonar stream exists (class invariant) but has no head"）；`configs/repro_cmold/teachers/t_camera_s_yoloxs.py:112-113`（`uncoupled_sonar_head=None, fused_sonar_head=None`）
- 现象：相机教师带着 7.16M 参数的死声呐流（ckpt 16.10M vs 训练 8.94M），每个训练步多做一次 640×640 的 backbone/neck 前向；教师权重是 `epoch_200` 的最后一轮，没有 EMA 也没有 best 选择。
- 为什么影响结论：成本翻倍（每步），教师质量略低于 EMA（相机教师 val AP 0.9025，`doc/logs/2026-11-09-r2-cmold-and-geometry-readings.md:13-21`），会略微削弱可蒸信号——方向与 H1 相同但量级小。是否配了 EMA hook 未查（`configs/_base_/default_runtime.py`、`schedule_f2.py`），**未确认**。
- 怎么验证：读 `default_runtime.py` 是否有 EMAHook；若有，确认保存时用的是 EMA 权重还是模型权重。

### L4 评测期仍重建教师模型

- 文件:行号：`tools/test.py:104`（`DET_MODELS.build(cfg.model)`，R2 的 `cfg.model.cmold` 会触发 `two_stream_yolox.py:173-176` → `:186-206` 建 `FrozenTeacher` 并加载 ckpt）
- 现象：评测根本不用 KD（`two_stream_yolox.py:378-410` 的 `predict` 不碰教师），但 R2 的评测必须能找到教师 ckpt，否则 `:87-95` 直接 raise。教师模型加载后常驻显存（16.10M 参数 + 优化器无关的权重）。
- 为什么影响结论：不影响数值；但它把"训练期产物"变成"评测期依赖"，任何想复评 R2 的人必须同时拥有教师 ckpt，否则误以为 R2 的 ckpt 坏了。
- 怎么验证：在只有 R2 学生 ckpt、没有教师 ckpt 的目录上跑一次评测，预期在 `frozen_teacher.py:87-95` 抛 `RuntimeError`（而不是静默用随机教师——这点代码是对的，值得记一笔）。

## 4. 核对后确认等价的点（无缺陷）

| 论文要求 | 实现位置 | 结论 |
|---|---|---|
| 教师=camera，学生=sonar（`:393`） | `r2_cmold_yoloxs.py:96`（`teacher_input="camera"`）、`two_stream_yolox.py:359-374`（`batch_inputs["camera"]` 送教师）、`:103`（`routes=dict(sonar_uncoupled="camera")`） | 对齐。R0/R2 没有 fused 头，学生侧只能是 `sonar_uncoupled`，`:86-96` 的 docstring 也把这条写清楚了 |
| 按 objectness 降序排序（`:444-446`） | `cmold_kd.py:96-104`（`masked.topk(m)` 降序） | 对齐（同分按索引定序，不影响语义） |
| K=min(教师保留数, 学生保留数)（`:405`） | `cmold_kd.py:133-139` | 对齐（但见 H1/H2 对"保留数"的取值） |
| 只取前 K（`:419-421`） | `cmold_kd.py:107-130`（`idx[:, :kmax]` + `arange(kmax)<k` 掩码） | 对齐；超出自身 k 的行被 mask 掉，不污染求和 |
| `1/K Σ(s_S−s_T)²`（`:454-455`） | `cmold_kd.py:178-184`（`diff=sigmoid(sS)−sigmoid(tT)`，`(diff**2).masked_fill(~mask,0).sum()/Σk`） | 对齐：用置信度而非 logit（`:500-501` 的 "objectness (confidence) scores"），分母是真实配对数 |
| 分类项 `softmax(c/τ)` + KL（`:450-464`） | `cmold_kd.py:239-242` | 对齐：`log_softmax(vs/τ)`、`softmax(vt/τ)`，KL 在 C 维上，逐 pair 求和后除以配对数 |
| `τ²·L_cls`（`:483`） | `cmold_kd.py:247`（`(num/den)*tau**2`） | 对齐：乘在均值外，与式(18) 等 |
| α=β=0.5，τ=2（`:531-535`） | `r2_cmold_yoloxs.py:97-100` | 与 Table 2 逐字一致 |
| 不蒸 bbox（`:493-497`） | `cmold_kd.py:295`（`s_cls, _, s_obj = s_branch`） | 对齐：`bbox_pred` 被显式丢弃，全文无第三项 |
| 教师冻结 | `frozen_teacher.py:83-85`（`eval()` + `requires_grad=False`）、`:97-98`（`train()` 永久返回 `train(False)`）、`:100`（`@torch.no_grad()`）、`two_stream_yolox.py:204-206`、`:372-374`（外层再包一层 `no_grad`） | 三重只读，且对 `model.train()` 免疫（BN 不会更新） |
| 学生梯度可达 | `cmold_kd.py:176-177`（学生 gather 不 detach、教师 `.detach()`） | 对齐；`tests/test_cmold_kd.py:215-244` 双向覆盖 |
| 教师 ckpt 与 teacher 配置匹配 | `teachers/t_camera_s_yoloxs.py:112-113` 把两个头置 None；`r2_cmold_yoloxs.py:74-80` 同样置 None；`frozen_teacher.py:87-95` 对 missing/unexpected 都 raise | 对齐：键集相同，加载走的是"严格失败"而非"部分加载"；这是本次审计中风险最高的一处，结论是好的 |
| R0 完全不进 KD 分支 | `r0_baseline_yoloxs.py` 全文无 `cmold`/`distillation` 键；`:49-54` camera 三件套与 fused 头置 None、`fusion=NoneFusion`；`:57` 只留 `uncoupled_sonar` 权重；`two_stream_yolox.py:173-176`（无 cmold 则 `cmold_teacher=None`）、`:276-280`（`is not None` 才进） | 对齐；`tests/test_cmold_kd.py:435-475` 用"把 `_cmold_losses` 换成抛异常"的方式证明无 cmold 键时该路径不可能被触达，且逐位一致 |
| 阈值边界一致 | `cmold_kd.py:98`（`< score_thr` 掩 −inf）与 `:100`（`>= score_thr` 计数） | 对齐：恰好 0.3 的单元被保留计数，不会被误掩 |
| 展平顺序一致（obj 与 cls 同一位置） | `cmold_kd.py:107-130`（`x.reshape(b,c,n)`，obj 的 `c=1` 与 cls 的 `c=C` 共用 `n=H*W`） | 对齐：同一 head 的两支输出，同一 row-major 序 |

## 5. 未确认 / 无法在本机验证

1. **论文的保留阈值到底是多少**：`cmold_numbered.txt` 全文没有数值（`:401-403` 只说 "retained high-confidence"），`:482` 只说"可以加上限"。所以"0.3 是偏离"这一判断本身只能相对"论文未给"成立，不能说论文用了别的数。
2. **K≈8–9 与"仅最粗层"**：本机 `results/repro_cmold` 下没有 `r2`，`work_dirs/repro_cmold` 下没有 `r2`/教师训练目录，无法独立复现；唯一来源是 `doc/logs/2026-11-09-r2-cmold-and-geometry-readings.md:60-61`。
3. **能否用预测文件反推 K**：不能。`pred.*.json` 是 NMS 之后的框（`r0` 的 `pred.sonar_uncoupled.d0.json` 1100 条检测、825 个 image_id；教师 `pred.camera.d0.json` 836 条、830 个 image_id），而 `select_topk` 数的是每层 raw head 里 `sigmoid(obj)≥0.3` 的**单元**。两者不可互换，任何"从预测文件数 K"的做法都是错的。
4. **5090 上 `stage_eval` 实际取到的 ckpt epoch**：本机无产物，未确认。
5. **mmdet YOLOXHead 的 `avg_factor` 归一化**：本机无 torch/mmdet，无法读源码也无法跑前向，因此"KD 项与 det 项分母不可比"（H3）只能以 loss 量级为证据，不能给出梯度层面的比值。
6. **论文 λ 的数值**：`:550` 只说"控制总权重"，无数值。
7. **教师训练是否配 EMA hook**：未读 `configs/_base_/default_runtime.py` 与 `schedule_f2.py`。

## 6. 建议的核验顺序（全部只读/前向，不改代码）

1. 先做 §H1 的第 1 条（按层打印 `cnt_s`/`cnt_t`/`k`）——它同时回答 H1 与 H2，且不需要训练，只需 R0 与教师两个 ckpt（本机两者都在：`work_dirs/repro_cmold/r0/epoch_200.pth`、`work_dirs/repro_cmold_teacher/t_camera_s/epoch_200.pth`）。
2. 再做 §H1 第 2 条（阈值扫 K），确定 0.3 是否为量级拐点。
3. §H3 的 λ 三格是唯一需要重训的实验；在它出数之前，任何"CMOLD 无效"的表述都应加上"λ=1、K≈8"的限定。
4. §M1 的断言与 §M2 的 split 回读属于链路加固，成本低、优先做。

---

审计结论一句话：**代码把论文的公式抄对了，但把公式里没写的三个数（保留阈值、λ、逐层还是整图）都选在了"信号最少"的一端，且没有任何断言阻止 KD 静默归零；在这个实例上得到的负结果，不足以支持关于 CMOLD 机制的任何方向性结论。**
