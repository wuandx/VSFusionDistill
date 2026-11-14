# FINAL-REPORT —— 声呐候选框生成 + VLM 判读：结项报告

> **状态快照：2026-11-12 03:50（+08:00）**（结项）。`out/` 与 `engine/` 在 02:40–03:19 之间持续被并行线改动
> （`cards.py` 03:00 修过、03:13 加上 `proposal_to_record()`），本报告的每个数字都注明了产物路径与生成时间；
> 复跑顺序见 `docs/RUNBOOK.md`。
>
> 事实层级：`[论文原文]`（本报告没有引用任何论文原文，见 §2.4）/ `[仓库原文]` 代码与文档原文 /
> `[实测]` 我亲自跑出的 stdout / `[复算]` 由产物数值算得 / `[推断]` 未证实的解释。

---

## 1. 结论

1. **这套东西的定位是 candidate 生成器 + 人工判断放大器，不是自动标注真值。**
   声呐侧没有人工 GT：原项目 converter 原文写着 `Sonar ground-truth boxes do not exist`，
   `sonar.json` 的框由相机框经位姿投影生成。因此任何"用这批数据训练/评测声呐检测器"的说法
   都不成立，导出器也把 `candidate_only_not_training_ready: true` 与 `sonar_gt_status: HOLD`
   写进了每一份 `provenance.json`。`[仓库原文]` `[实测]`

2. **扇面里最亮、最稳定的东西是类无关结构（倾斜波束打到水平池底的亮弧），不是目标。**
   三条录音里它 100% 存在（715/715、771/771、725/725），横跨 92–128 beam，
   主连通域径向厚度 107.5–111.5 px（0.321–0.333 m），峰值约 40/255 而背景约 13/255。
   判读协议因此规定：贯穿扇面的大亮弧**不得**被框成目标。`[复算]` `[仓库原文]`

3. **目标在声呐里的绝对位置算不出来。** `geometry.predict()` 恒为
   `available=False, reason="gantry_not_sonar_frame"`；`out/calibration.json` 的 `status` 是
   `degraded`，`unavailable=[sonar_pose, absolute_range, beam_angle, fov, target_position]`。
   `[实测]` `[复算]`

4. **回波传播位移目前两条路径给出的数不一致，尚未解决（口径②）。**
   `engine/track.py` 链式估计：`drow −5..+7`、`auto_frac 1.0`、`score_median 0.903`；
   直接对关键帧跨帧估计：bomb `−40..+43`。两者都在报告里并列保留，不合并。`[复算]` `[实测]`

5. **工程链路已全线闭合；测试 10:12 是 119 PASS / 0 FAIL / 0 ERROR / 0 SKIP。** `echo.py --proposals` → `cards.py`
   → `judge.py` 守卫 → `review/server.py`（:8771，人工复核）→ `dataset.py`（YOLO 导出）六步全部跑通。
   6 条录音各 12 张卡、各 12 条判定；`check --recording 2023-09-20_171105` = `12 条判定，0 条不合法`
   （卡片重渲后用 `resign` 重签，不重判）。导出实测 **14 条**（`out/_demo_v2`：110229 11 + 105230 2 +
   101840 1，`data_source="human"`，operator=**lead（agent，不是用户）**）；旧 `out/_demo_110229`
   的 10 条保留作历史，少的是 110229 那 4 帧（当时裁剪窗看不见候选、只能 `unsure`，补渲后已 accept）。
   上一轮唯一那条红灯（图例漏 `NOT a prediction`）已修：限定词前置、必需段不截断，新增三条测试锁住。`[实测]`

6. **VLM 判读在这批数据上不可复现。** 同模型同协议同 24 张卡，两个判读员一个报 object 21 条、
   一个报 structure 23 条，逐卡一致率 1/24、κ = 0.037（`out/judge_disagreement.json`，分析见
   `docs/FINDINGS.md` 第十一节）。所以本线的产出**只能**是候选 + 复核台 + provenance，
   不能是"模型标注"。这条也解释了为什么不让模型直接吐框。`[实测]`

7. **补记（03:40）：看不见目标的那三条只是"选错了录音"。** 40 条录音的形状普查显示，
   我们按"每类一条"选的三条恰好都是回波铺满扇面的；另有录音的回波只有 5–6 beam 宽、可跨 800+ 帧
   稳定跟踪（相邻帧质心位移中位 0.71 px）。**但"那是不是 UXO"仍无任何独立证据**，见 §8。
   `[实测]` `[推断]`

---

## 2. 目标、方法与边界

### 2.1 目标
在三条开发录音的声呐扇面上，产出**人可快速接受/否决的候选框**：把"值得看一眼"的位置找出来、
渲染成判读卡、交给 VLM/助手给意见，最后仍由人签收。人的注意力被压缩到少数可疑帧上。

### 2.2 为什么不让模型直接吐框
三条事实（§1 的 1–3）各自独立地否掉了"直接输出坐标"的路径：
没有真值可监督；最强信号是结构不是目标；位姿链算不出目标位置。
于是流水线被切成"分离结构 → 给候选 → 给判读材料"，身份（bomb/grenade/mortar）在声呐里
保持 `unresolved`。

### 2.3 判读协议的地位
`docs/judgment-protocol.md`（cards/v0）是唯一标准：一条贯穿扇面的亮弧不是目标；要框的是
"径向位置上时域稳定、比周围更亮、更紧凑"的扰动。协议里的形状先验 `dR ∈ 0.03–0.35 m`
是**经验区间**，不是论文事实。

### 2.4 与 CMOLD 的关系
**无。** 本仓库是独立的三维网格 + 声呐映射 + VLM 判读实验，不引用 CMOLD 论文的任何结论；
本报告里也没有任何"论文说"的句子。工作区 `AGENTS.md` 里的 CMOLD 语境属于另一条线。

---

## 3. 证据链：结论 → 脚本 → 数字 → 产物

| # | 结论 | 可复跑的命令/脚本 | 关键数字 | 产物 |
|---|---|---|---|---|
| 1 | 声呐无人工 GT | 读 `code/VSFusionDistill/aodet/datasets/converters/uxo_to_paired.py:35-38` | 原文即结论 | — |
| 2 | 亮弧＝结构 | `$PY tmp/lead_companion.py`（4 s，会重写 `out/companion_test.json`；隔离副本复跑与本文件逐字段一致） | 径向厚度 111.5/109.0/107.5 px = 0.3326/0.3251/0.3206 m；存在率 715/715、771/771、725/725 | `out/companion_test.json`（02:42:54） |
| 3 | 位置不可解 | `$PY engine/geometry.py --recording 2023-09-20_171105 --frames 622` | `predict(): gantry_not_sonar_frame (available=False)` | `out/calibration.json`（03:02:54） |
| 4 | FOV 只有条件界 | 同上 | `θ ∈ [15.4°, 67.0°]`，`status: conditional_bound_not_a_measurement` | `out/calibration.json` |
| 5 | 位移在配准误差内（链式） | `$PY -m engine.track --recording 2023-09-20_171105 --keyframe 622 --box 14,140,114,267 --out tmp/track_probe/622.json` | `drow_range [-5,7]`、`dbeam_range [0,0]`、`auto_frac 1.0`、`score_median 0.9033`（与仓库产物逐字段相同，4.1 s） | `out/propagate_2023-09-20_171105_622.json`（02:50:56） |
| 6 | 位移口径冲突（直接法） | `$PY tmp/lead_drift2.py`（0.3 s，只打印） | bomb `−40…+43`、grenade `−5…+53`、mortar `−19…+15` | `out/drift_probe.json`（02:49:29）＋ stdout |
| 7 | 结构非刚体 | `$PY tmp/lead_shear.py`（2.3 s，只打印） | 剪切模型增益 ≤0.113；相关 0.26–0.57（bomb）/0.07–0.14（mortar） | stdout |
| 8 | 网格先验可用且是上界 | `$PY engine/mesh_prior.py --all --check` | `all_pass True`；100lbs 侧视 34×80 px（2059 px²） | `out/prior_check.json`（02:59:37） |
| 9 | 卡片可渲染、自检通过 | `$PY engine/cards.py --selftest` | PASS；首卡 1264×1538、`zoom=4` | `tmp/cards/selftest/` |
| 10 | echo→cards 契约（03:13 起通） | `$PY engine/cards.py --proposals out/2023-09-20_171105/proposals.jsonl --limit 1 --out tmp/cards/echo_contract` | 03:13 以前：`ValueError: frame_data has neither 'img' nor image.path`（`cards.py:192`）；现在：`758x1764 zoom=2`（bomb 0622）、`1122x1600 zoom=3`（grenade 0163 / mortar 0087） | `tmp/cards/echo_contract*/`（03:16） |
| 11 | 判定已失效 | `cd plugin && $PY -m sonarllm.cli check --recording 2023-09-20_171105` | `card_sha256 与当前卡片不一致` | `out/2023-09-20_171105/judgments/` |
| 12 | 导出 0 条 | `cd plugin && $PY -m sonarllm.cli export --dst <tmp> --recording 2023-09-20_171105` | `n_exported: 0`，`candidate_only_not_training_ready: true` | — |
| 13 | 自检 119 绿 0 红 | `$PY tests/run_all.py` | PASS 119 / FAIL 0 / ERROR 0 / SKIP 0（17.9 s）；上一轮 118/1（图例措辞）已修 | `out/_qa/qa-results.json`（10:12） |

> 注：表里的 `$PY` = `/mnt/c/Users/ASUS/AppData/Local/Programs/Python/Python312/python.exe`
> （bash 自带的 `python` 是 WSL 3.10.12，没有 numpy）。`tmp/lead_*.py` 是**临时探针**，不是交付物；
> 它们存在只是为了让表第 2/6/7 行的数字可被重跑。

---

## 4. 三条录音的读数

### 4.1 几何（`engine/geometry.py`，`[实测]`）

| 录音 | rows | RES (m/row) | WindowStart | WindowLength | 距离窗 | `predict()` |
|---|---|---|---|---|---|---|
| `2023-09-20_171105`（bomb） | 780 | 0.00298256 | 0.6949365 | 2.3263969 | 0.6949..3.0184 m | 不可用 |
| `2023-09-21_120653`（grenade） | 441 | 0.00298322 | 0.6951 | 1.3156 | 0.6951..2.0077 m | 不可用 |
| `2023-09-21_100927`（mortar） | 441 | 0.00298254 | 0.6949 | 1.3153 | 0.6949..2.0072 m | 不可用 |

三条录音的 RES 互不相同；把 0.002983 当全局常数会在跨录音换算时引入约 0.2% 误差。

### 4.2 亮弧（`out/companion_test.json`，`[复算]`）

| 录音 | beam 跨度（中位） | 径向厚度（中位） | 换算米 | 第二连通域（beam/px） | 全帧存在率 | 脊线所在行 |
|---|---|---|---|---|---|---|
| bomb | 125.0（p10 118.2 / p90 128.0） | 111.5 px | 0.3326 m | 42.5 / 54.0 | 715/715 | 182–200 |
| grenade | 104.5（p10 56.9 / p90 128.0） | 109.0 px | 0.3251 m | 40.0 / 58.0 | 771/771 | 137–154 |
| mortar | 113.5（p10 60.5 / p90 128.0） | 107.5 px | 0.3206 m | 40.5 / 50.0 | 725/725 | 146–160 |

> 口径注：`tmp/lead_companion.py` 把 `RES = WIN/780` 写成了全局常数，因此 grenade/mortar 的
> 米数是拿 **bomb 的 RES** 换算的；与各自录音的真实 RES 相比差 ~0.02%（7×10⁻⁵ m），可忽略，
> 但引用"0.325 m / 0.321 m"时要知道它不是逐录音 RES 算的。
>
> 同一批帧的**盲判**（`out/blind_judge.json`，judge 未看数字、只看 9 张卡）给出另一种厚度口径：
> bomb 150–250 row（0.45–0.75 m）、grenade 10–60 row（0.03–0.18 m）、mortar 3–8 row。
> 两者**并列保留**，见 §5.1。

### 4.3 可检测性（`docs/geometry-calibration.md` §7 的产物复算）
扇面外局部 SNR 峰值中位数：bomb 2.91（最大 4.10，13% 帧 ≥4.0）、incendiary 2.75（4.26，7%）、
mortar 2.47（3.40，0%）。20 帧内暗影候选 0 个。⇒ **没有可分辨的离散目标回波**；
任何目标只能以"池底回波内部的强度调制"形式存在，且低于噪声。

### 4.4 网格先验（`out/prior_check.json`，`[复算]`）
r=1.26 m、az=10° 时：100lbs 侧视 34×80 px（面积 2059），端向 13×248；incindiary 21×43（805）；
mortar_shell 27×48（877）。解析核对 `2·atan(L/2/r)/1.015625+1` 给 33.1/20.6/26.5（实测 34/21/27）。
剪影是**框的上界**，不是声学模型；`uniqueness` 恒 False（同一剪影 864 个位姿）。

### 4.5 位移（两条路径，`[复算]`）

| 路径 | bomb | grenade | mortar | 备注 |
|---|---|---|---|---|
| `engine/track.py` 链式（715 帧全 auto） | −5..+7 | — | — | score 中位 0.903，`clipped_frac 0.0` |
| 直接跨帧估计（`tmp/lead_drift2.py`） | −40..+43 | −5..+53 | −19..+15 | 基准帧不同，读数不可直接相加 |
| `echo.py` 对齐报告（622 对 anchor 979） | +16 | — | — | 与链式的 −1 直接冲突 |

---

## 5. 三个口径差异（并列保留，不合并）

### 5.1 口径①：亮弧有多厚
| 来源 | 量的是什么 | 数值 | 米 |
|---|---|---|---|
| `out/companion_test.json`（主连通域径向跨度） | 亮弧的**主连通域** | 111.5 / 109.0 / 107.5 px | 0.333 / 0.325 / 0.321 m |
| `out/blind_judge.json`（盲判 agent 目视） | 整个"亮区"（含下方亮扇） | bomb 150–250 row；grenade 10–60；mortar 3–8 | 0.45–0.75 / 0.03–0.18 / 0.02–0.06 m |

差别来源是**是否把下方亮扇算进厚度**：主连通域只取最亮那条带，目视会把连着的扇面一起框进去。
两者是不同物理量的测量，**不得平均、不得互相纠正**；引用时必须写明是哪一种。
bomb 一档差 1.35–2.2×，这直接影响"目标尺寸先验 `dR 0.03–0.35 m`"能不能用——**目前不能**据此收紧。

### 5.2 口径②：回波传播了多远
| 来源 | bomb 关键帧 622 起 | 说明 |
|---|---|---|
| `engine/track.py` 链式估计（`out/propagate_2023-09-20_171105_622.json`） | `drow −5..+7`，自动采用 715/715（100%），score 0.903 | 699 条链式 + 15 条 direct + 1 条关键帧 = 715 |
| 直接对关键帧跨帧估计（`tmp/lead_drift2.py`） | `−40..+43`（f0693 −16、f0800 −29、f0979 −40、f1157 −17、f1264 +15、f1336 +43） | 宽搜索 ±200 row，相关 0.687–0.878 |
| `engine/echo.py` 自带配准（anchor 帧 979） | `shift_abs_median [16.0, 1.0]`（f622） | 与链式 622→979 的 `−1` 直接冲突 |
| `out/drift_probe.json` | 40 帧全部 `drow = −40`、`align_score = −1.0` | **退化解**：稀疏带（约 10% 覆盖）使剖面恒为 0、归一化分母为 0，`_best_lag` 回落到首个探测滞后 |

结论：**未解决**。三条独立读数（−1 / +16 / −40…+43）不能同时成立；`tests/run_all.py` 里 7 条
位移相关 FAIL（`+7→5`、`−11→−17`、`+13→8`、`−3→−1`、`+6→3` 等）`[实测]` 指向同一个估计器偏差。
在解决之前，任何"目标在帧间静止/移动 X 行"的判读证据都**不可作为定量依据**。

### 5.3 口径③：mortar 用多长做缩放（同样并列）
| 来源 | mortar 长度 | 说明 |
|---|---|---|
| `BRIEF.md` | "≈0.35 m"，且 `nominal_length_m: null` | 【仓库原文】任务书里的近似值，未标明来源 |
| `docs/mesh-prior.md` + `out/prior_check.json` | **0.58 m** | 【仓库原文/原始产物复算】剪影按标称长度缩放时实际用的值；网格 `mortar_shell` 只按长轴缩放 |

两者差 1.66×，会直接改变 §5.1 里"弧厚/目标长"的比值判据。本次所有 mortar 读数（剪影
`27×48 px`、`beam 5.5–26.4`、`row 43.5–194.7`）都是按 **0.58 m** 算的 `[原始产物复算]`；
凡是要和 `dR 0.03–0.35 m` 比的地方，必须写明用的是哪一个。**未解决，不得取中值。**

---

## 6. 当前工程状态

| 步骤 | 状态 | 证据 |
|---|---|---|
| ①结构/扰动分离（`engine/echo.py`） | 可用；定量可检测性是负结论 | §4.3 |
| ②候选记录（`--proposals`） | 通：`proposal_to_record()` 按录音名回读 pgm 再渲染；记录无 blob 时是 frame-default 框，不是候选 | §3 第 10 行、LIMITATIONS §7.1 |
| ③卡片（`engine/cards.py`） | 可用（`--selftest` 全 PASS） | `tmp/cards/selftest/` |
| ④判读（协议 + `judge.py` 守卫） | 通：6 条录音各 12 张卡判读全落盘；`check --recording 2023-09-20_171105` → `12 条判定，0 条不合法`；重渲后用 `resign` 可审计重签（只重签不重判） | `out/*/judgments/`、`sonarllm check` |
| ⑤复核台（`review/server.py`） | 通：`:8771` 起停、并发 20 POST 全 201、忙端口 rc=2 | `test_13`、`out/review-shots/` |
| ⑥导出（`plugin/sonarllm/dataset.py`） | 通：`out/_demo_dataset` 写出 2 条 human 复核样本 + `provenance.json` | `sonarllm export` |
| ⑦紧凑目标检测（`engine/compact.py`） | 通：两条新录音全帧扫描 837/839 与 769/782 帧有候选 | `docs/FINDINGS.md` §10.5 |

已知缺陷清单见 `docs/LIMITATIONS.md` §7；操作步骤与故障排查见 `docs/RUNBOOK.md`。

---

## 7. 不能声称的东西

- ❌ "这套数据有标注" / "候选即真值"：声呐侧无人工 GT，导出器自己就写 `HOLD`。
- ❌ "亮弧是目标"：它是类无关结构，100% 帧存在，判读协议明令不得框它。
- ❌ "FOV = 130°"：已被排除；现有只有"若回波即目标"的条件界 `[15.4°, 67.0°]`，前提是假的。
- ❌ "目标在 (x, y, z)"：`predict()` 恒不可用，`unavailable` 里就有 `target_position`。
- ❌ "身份已判定"：bomb/grenade/mortar 在声呐里是 `unresolved`。
- ❌ "位移已量化"：口径② 未解决（§5.2）。
- ❌ "mortar 就是 0.35 m / 0.58 m"：口径③ 两个数并存且未解决（§5.3），引用必须写明出处。
- ❌ "那两条新录音里的亮点就是 UXO"：没有 GT、没有注册、没有独立测量，`identity: unresolved`（§8.4）。
- ❌ "VLM 判读稳定/可用于标注"：同模型同协议 κ = 0.037，两个判读员结论相反（LIMITATIONS §9.6）。
- ❌ "论文证明"：本仓库与 CMOLD 无关，无任何论文原文引用。

---

## 8. 下一步（按优先级，附判定标准）

1. ~~修 ②→③ 契约~~（03:13 已闭合，见 §3 第 10 行）。接手的下一步是**让退化框不再冒充候选**：
   实测 bomb 0700 的 rank-0 blob 是 `[45,55,49,59]`（4×4 px）而报告里 `candidate_degenerate: false`。
   判据：`--proposals` 渲出的卡片里，框 <6×6 px 时 `candidate_degenerate` 必须为 true，且 footer 标 `degenerate`。
2. **解决口径②**：用带掩模的稠密剖面重估位移，或用结构脊线跟踪替代整带相关。
   判据：三条读数（链式 / 直接法 / echo 对齐）在 bomb 622→1336 上落到同一区间，且
   `tests/test_02_echo_shift.py` 的 7 条位移 FAIL 至少转 5 条。
3. **让位移不再污染判读**：在协议里明确"a2 位置一致性"只在 ±X row 内计数（X 由第 2 步定），
   在此之前把 a2 视为"不可用证据"。判据：`docs/judgment-protocol.md` 更新 + 判读表新增字段。
4. **重建判定**：先按 RUNBOOK §6 备份 → 重渲 → 重判；判据：`cli check` 0 FAIL，且每条判定
   都能对上当前卡片的 `card_sha256`。
5. **只有在 1–4 完成后**，才谈"用候选训练一个小检测器"；届时也必须在
   `candidate_only_not_training_ready` 的前提下，把它定义为**弱监督预训练**，而不是复现任何论文指标。

---

## 9. 复现入口

```bash
cd /mnt/d/agent_workspace/水下/声呐目标检测_workflow/sonar_llm_annotation
PY=/mnt/c/Users/ASUS/AppData/Local/Programs/Python/Python312/python.exe
$PY engine/geometry.py --recording 2023-09-20_171105 --frames 622     # 几何 + predict 不可用
$PY engine/echo.py --recording 2023-09-20_171105 --frames 622 --mode aligned
$PY engine/mesh_prior.py --all --check                                 # 21 s，写 out/prior_check.json
$PY engine/cards.py --selftest
$PY engine/cards.py --proposals out/2023-09-20_171105/proposals.jsonl --limit 1 --out tmp/cards/echo_contract
# ↑ 预期：...2023-09-20_171105_0622__g1x.png 758x1764 zoom=2 prior=unavailable（03:16 实测）
$PY -m engine.track --recording 2023-09-20_171105 --keyframe 622 --box 14,140,114,267 \
    --out tmp/track_probe/622.json
cd plugin && $PY -m sonarllm.cli status
```

完整步骤、期望输出与故障索引见 `docs/RUNBOOK.md`；不能做什么见 `docs/LIMITATIONS.md`。

---

## 8. 结项补记（03:40）：三条录音之外的转向

### 8.1 为什么要把话说完整

§1–§7 的结论"亮弧是结构、目标不可见"是对的，但只对**那三条录音**成立。把范围放大到 40 条之后，
结论要改写成：**不是这套数据看不见目标，是我们最初按"每类一条"挑的三条恰好都是回波铺满扇面的录音。**
完整论证见 `docs/FINDINGS.md` 第十节，这里只留结论与读数。

### 8.2 三条独立的"看不见"检验（都通过）

| 检验 | 结果 |
|---|---|
| 长时间积分（每 4 帧一帧，`clip(frame−local_median(±10),0)` 累加） | 带外 max 3.028 / p99 2.939 / mean 2.371（bomb）→ **max 与 p99 只差 3%**，没有任何紧凑亮点浮出 |
| 声影缺口（积分负残差） | 缺口全落在弧脊行（bomb 181–197、grenade 140–160、mortar 149–170），max 4.7 vs p99 3.8 → 是弧自身闪烁 |
| 盲判 36 张卡（两轮） | **object = 0**（bomb 7 structure/5 unsure；grenade 7/5；mortar 10/2） |

### 8.3 形状普查与两条新录音

39 条录音的中间帧，峰值行 116–697、宽度 5–110 beams。我们三条的宽度是 76 / 57 / 23（宽），
而 `2023-09-21_105230` 宽 **5**、`2023-09-21_101840` 宽 **6**——目视是一颗"亮头 + 细尾"的彗星。

`engine/compact.py`（单帧块中位背景，16×16 块；宽度 ≥70 beams 判 `structure` 永不进候选）实测：

| 录音 | 帧数 | 有候选 | 相邻帧 top-1 质心位移 中位 / p90 / <10px |
|---|---|---|---|
| `2023-09-21_105230` | 839 | **837（99.8%）** | 0.71 px / 6.86 px / 91.1% |
| `2023-09-21_101840` | 782 | **769（98.3%）** | 0.82 px / 7.97 px / 91.3% |

逐帧位移中位 0.7–0.8 px 是最有力的证据：**这是连贯轨迹，不是散斑跳变**（散斑会给 10–20 px 随机跳）。

### 8.4 这条转向不能说的话

- 不能说那个亮斑是 UXO：无 GT、无注册、无独立测量 → `identity: unresolved`。
- 不能回头改那 36 张卡的判读：cards 已 FROZEN，`object=0` 是那批卡的事实；新录音另立一批卡。
- 不能把横向像素当角度或米：`row↔range` 是标定过的（0.00298256 m/row），横向仍未标定。

### 8.5 一个必须记住的方法论缺陷

我们最初的背景模型是**时域**局部中位数，对"相对声呐几乎不动"的目标是破坏性的——中位数里就包含目标本身。
所以"demed 之后什么都没有"**不能**反推"原图里也没有东西"。改成单帧空间背景（块中位数）之后，
同一批录音立刻有了稳定候选。两次失败的替代方案（31×31 CFAR、`local_snr`）都记在 `docs/FINDINGS.md` 第八、十节，
因为它们划出了"这个指标对扩展目标不成立"的边界。

---

## 附录 A · 本轮补记（2026-11-12 09:5x，t-docs）

> 本附录只补"这一轮新增的四件东西 + 两条必须保留的缺陷"，不改 §1–§9 的任何结论与读数。
> 数字全部来自磁盘产物；只有明确标 `【回执】` 的才是别人口头给、我没在产物里复核的。

### A.1 距离带先验（`tools/rangeband.py` → `out/<rec>/band.json`）

- **它是什么**【仓库原文】：给定 gantry 平台轨迹、声呐头偏移与一条录音的检测距离，拟合单一世界点
  `P` 与距离偏置 `b`（`range_i = |P − c_i| + b`），偶帧拟合、奇帧留出；schema
  `sonar_llm_annotation/rangeband/v0`。**它不预测方位**（docstring：声呐头稳定，|beam vs world azimuth| r²<0.01），
  所以卡片上只能画 `row_lo`/`row_hi` 两条水平虚线。
- **三种状态**【原始产物复算，`out/<rec>/band.json`】：

| 录音 | status | n_detections | band_rows | 读数 |
|---|---|---|---|---|
| 2023-09-20_171105 | `insufficient_detections` | 0 | — | 旧 echo proposals 无可连接检测 |
| 2023-09-21_100927 | `insufficient_detections` | 0 | — | 同上 |
| 2023-09-21_101840 | `unreliable_model` | 769 | 31 | 留出 p90 **0.1627 m** > 0.15（in-sample 0.1564） |
| 2023-09-21_105230 | `unreliable_model` | 837 | 25 | `b=−0.300000`、`P_z=−1.999511` 双双撞界 |
| 2023-09-21_110229 | `unreliable_model` | 533 | 6 | `b=+0.300000` 撞界；in-sample p90 0.4186 / 留出 0.4177 |

- **结论**：三条"已评估"录音**全部**不是 `model_ok`。撞界时 in-sample 残差再小（105230 中位 0.021 m、p90 0.078 m）也不能当
  "固定 3D 点"的证据——这条更正写在 `docs/FINDINGS.md` 第十二节，`docs/LIMITATIONS.md` §6.5 有机制说明。
- **循环性（必须一起读）**：`unreliable_model` 的带是本录音**自己的检测**按 MAD 修剪出的观测散布
  （docstring：*a statement about our detections, not about the target*）。110229 的 381–393 与候选同源，
  **不构成独立证据**；它窄（6 行）也不代表更确定（若模型被接受，按留出 p90 0.4177 应给 ≈140 行）。
  105230 的同型矛盾（25 行 vs 40 行）是 QA 的 O3，未修。
- **可复现**【原始产物复算】：09:58 在仓库副本里跑
  `$PY tools/rangeband.py --recording 2023-09-21_110229`，产物与 `out/2023-09-21_110229/band.json`
  逐字节相同（md5 `3a59fb0267ef345010532e92ac56c21f`）。命令会覆盖 `out/<rec>/band.json`，先复制再跑。

### A.2 卡片上的行带：两条虚线，措辞按状态分支

- **【仓库原文】** `engine/cards.py`：`C_BAND = (236, 176, 84)`（琥珀色；注释 "never cyan, never a prior hue"）；
  `_blend_band_rows` docstring："A band is a *row* interval. The azimuth is not solvable on this data,
  so the band is drawn as two lines and never as a rectangle"。
- 标签分支（**照代码抄，不润色**）：`model_ok` → `range band … (predicted ±N rows)`；
  `unreliable_model` → `range band … (observed ±N rows; model rejected; NOT a prediction)`；
  `insufficient_detections` → 本帧无条目（不画）。footer 同步写 `band, predicted` / `band, observed; model rejected`。
- **谁来挂 band**：`cards.py` 没有 `--band`（只有 `--band-h`），记录里没有 `band` 字段就没有虚线。
  `tmp/cards_110229/make_cards.py` 是现成 driver（docstring：*Nothing here detects anything … only picks frames
  and attaches the two*）。QA §10.2 用 amber 像素数对照验证：传 band 464 px，不传 0 px。
- **截图证据**：`out/review-shots/06-band-110229.png`（493197 B）与
  `out/review-shots/07-band-110229-sample.png`（368438 B），均为 09:54。

### A.3 形状普查 v2（`tools/census.py` → `out/census/`）

- **公式与排序口径**【仓库原文 + 原始产物，`out/census/CENSUS-V2.md` 10:12 版】：
  `base = presence × (0.35·continuity + 0.35·compactness + 0.15·smoothness + 0.15·brightness)`；
  旧复合分 `score = base × (1 − band_gate_frac) × geo_factor`（`geo_factor` 四档 1.00/0.70/0.50/0.35）
  **已降为对照列**，不再决定名次。10:12 起权威表的主键是 **`base`**，闸门只做资格判定与告警。
- **规模**【原始产物复算】：`out/census/census_v2.json` schema `sonar-llm-annotation/census/v2`，
  n_recordings **40**、`--every 1`（全部逐帧），参数 `{rank_key: base, every 1, refine_top 0, snr 5.5,
  min_area 12, cov_pct 99.5, cov_smooth 5, band_gate 0.45, gate_m_per_frame 0.025,
  jump_m_per_frame 0.03, holdout_p90_max 0.15, min_track 8}`。
- **A 段为空，且不是排表失手**：没有一条同时满足 `geo_ok` + 覆盖闸 < 0.45 + `track_frac ≥ 0.5`；
  最高 `track_frac` 只有 0.130（110229，69/533），而它触发几何闸；`geo.geo_ok`（无撞界且留出通过）全库只有 6 条，其中 `geo_factor` 仍为 1.00 的只有 5 条（100927 的 `geo_ok` 为真，但"距离变化低于固定物体下界"把它压到 0.35）。
  同时过"几何可辨识 + 覆盖闸不触发"的 3 条是 103728（base 0.067，覆盖闸 0.28，轨迹 47/693 ≈ 6.8%）、
  101622（0.023，0.00）、124039（0.019，0.35）——**没有一条录音给出覆盖半条录音的连续回波**。
- **base 前 5**：110229 `0.1288`（旧复合分 0.0451；轨迹 69/533、闸 0.00、geo 0.35）、
  182317 `0.1276`（0.0583；64/501、闸 0.543、geo 1.00，**无 `paired_role`**）、
  105856 `0.1035`（0.0517；25/220、闸 0.00、geo 0.50 撞界）、
  110049 `0.0731`（0.0171；43/566、闸 0.534，**无 role**）、123500 `0.0671`（0.0241）。
  无 `paired_role` 的三条是 182317（base #2）、110049（#4）、175000（#15）——可以看，**不能导出**。
- **所谓"名次变化"是口径而不是算法**：旧文里的"110229 1→4、105230 2→26、100927 6→25"是**复合分**名次；
  改成 base 主键后 110229 回到第 1、101840 第 9、105230 第 10、100927 第 17、171105 第 19。
  两种名次都留在 `census_v2.json`（`rank` 与 `v1_rank`/`delta_vs_v1`），不要混用。
- **反例仍在**：100927 的覆盖率闸只删掉 52% 的帧（"闸门不是判决"），base 仅 0.0284；
  171105 的带跨 92–128 beams、闸门删掉 90.6% 的帧（base 0.0236）。26/40 条录音覆盖闸 < 0.45。
  普查是**排序器**，不是检测器；`identity` 一律 unresolved。
- 表已落盘为 `out/census/CENSUS-V2.md`（10:12）；文字版由 t-geom 落为 `docs/CENSUS-V2.md`（10:13，18775 B）。

### A.4 110229 的 12 张卡与双人盲判（κ=1.0，但**不是**"VLM 可靠"）

- **卡集**【原始产物复算】：`tmp/cards_110229/frames.json` 固定 12 帧
  `[125,173,222,270,318,367,415,464,512,560,609,657]`（规则："整段等距、含首尾"），
  卡片在 `out/2023-09-21_110229/cards/`，`report.json` 记 `n_cards 12`、每张 `out_sha256`。
- **两位盲判**：A → `judge_a/`，B → `judge_b/`，各 12 个 JSON；合并用
  `tools/merge_judgments.py`（`--recording` 必填）→ `judgments/`。
- **一致性**【原始产物复算，`judge_agreement.json`】：n=12、逐卡一致率 `po=1.0`、
  随机一致率 `pe=0.5139`、**Cohen's κ=1.0**；两人都是 object 7 / unsure 5；不一致 0 条。
- **合并规则**【仓库原文】：分歧时保留 **A** 的 verdict 并记 `alt_verdict`/`alt_reason`，
  不取平均、不静默转 unsure（本次没有触发）。
- **与上一批的差异来源**（任务要求写清）：这一批 12 张卡里 **8 张的候选确实落在裁剪窗内**（另 4 张正是 A.6 的
  裁剪缺陷），判读员看得见本体；B 还被要求先写可数判据（`thr60`、`N=0`、`dR`、峰值/背景比）再给 verdict，
  而上一批 24 张是宽弧卡、两人对"有没有闭合轮廓"各执一词（κ=0.037）。**可见性 + 可数判据**是差异来源，
  不是"模型变强了"。
- **不能写成"可靠"**：这是同一模型的两次独立判读，不是两套独立方法；A 从不写 `dR`，B 每张都写
  （0.018–0.030 m）；0512 两人都 `unsure` 但理由不同（A：c6，框只盖住左段、亮头压在框外；
  B：a3，`dR=0.018 m` 低于 0.03 m 下限）。12 张卡同属一条录音、同一种"亮头+淡线"形态，
  不覆盖 24 卡那批宽弧形态——那批仍是 **κ=0.037**（`out/judge_disagreement.json`，24 张）。
  **结论：κ=1.0 只支持"这 12 张卡上 verdict 一致"，不支持下述任何一句："VLM 判读已可用"、"找到了 7 个目标"、
  "可以按 object 导出标签"。**
- **supp 批（10:0x，补渲的 4 张；合并用 `tools/merge_supp.py`，产物 `judge_agreement_supp.json` 记 `published_to_judgments: false`）**：主批里看不见候选的那 4 帧按 `--crop-mode candidate` 补渲到
  `cards_supp/`，双人各自目录盲判 → **4/4 `object`**。`judge_agreement_supp.json` 是 `n=4`、`po=1.0`、
  **`kappa: null`**（`kappa_note: "undefined, not zero"`）：两人只用了 `object` 一个标签、`pe=1`，
  κ 的公式**无定义**，既不能写 0（会被读成"不如随机"）也不能写 1（会被读成"完美一致"）。
  它**不能**和主批的 κ=1.0 相加成"16/16"——两个数字口径不同（主批 `pe=0.5139`，supp `pe=1`）。

### A.5 人工验收与导出（operator 是 agent，不是用户；当前 14 条）

- **复核**【原始产物复算，`out/2023-09-21_110229/reviews.jsonl`】：**18 条写入、12 个样本**（append-only，
  同一 `sample` 以最后一行为准），`accept 13` / `uncertain 5`；判为 `accept` 的样本 **11 个**
  （主批 7：0125/0173/0222/0270/0560/0609/0657；supp 4：0318/0367/0415/0464），只有 0512 仍是 `uncertain`。
  `operator` 全部是 **`lead`（一个 agent，不是人类用户）**，`data_source: "human"`（不是 fixture）。
  supp 4 条的 `final_box` 分别 `[38,129,76,144]` / `[46,118,75,139]` / `[52,110,74,125]` / `[52,108,74,124]`
  （两位判读员框的并集 +1 px）；接受理由不是"卡片上好看"，而是**同一横向位置（beams 40–76）在四个时刻
  row 单调上移 132→118→112→110**——一个回波在靠近，`identity` 仍未解。
- **导出**【原始产物复算，`out/_demo_v2/provenance.json`，10:09】：`n_exported 14` =
  110229 **11** + 105230 2（0386/0805）+ 101840 1（0797）；`recordings_per_split {train:1, val:5, unassigned:8}`
  （这是 **item** 数，不是录音数）、`n_unassigned 8`、`n_fixture_skipped 5`；
  `candidate_only_not_training_ready: true`；`sonar_gt_status: HOLD`；`classes` 三条（`mortar_shell` 是第 2 类）；
  `image_size_by_recording` 全为 128×441；png/txt 逐 split 相等（1/1、5/5、8/8）。
- **历史**：`out/_demo_110229` 的 **10 条**保留不删，它少 4 条正是因为当时那 4 帧只能判 `unsure`
  （裁剪缺陷）；补渲、复核之后才变成 14。`out/export.json`（09:51）早于这 4 条复核（10:08），
  它的 `n_reviewed 19` 是那一分钟的台账快照，**不要**拿它推当前导出数。
- **全量台账**【原始产物复算，`out/export.json` 35920 B，09:51，operator `t-review-band`】：
  `n_proposals 2454`、`n_reviewed 19`、`n_unreviewed 2435`、`by_status {accept 9, revise 4, uncertain 5, reject 1}`；
  带块 `available: true`、`n_recordings_with_band 5`，disclaimer "**band 只约束距离，不约束方位；identity unresolved**"。
  注意 `n_reviewed 19` 含 8 条 `data_source: "fixture"` 的自测复核（导出器会跳过它们），所以 19 ≠ 可导出数。
- **导出闸门**【仓库原文】：只收 `accept`（取 `final_box`）与带 `final_box` 的 `revise`；`fixture` 默认跳过
  （`plugin/sonarllm/dataset.py:169-175`）。CLI 现在有 `--allow-fixture`（"只给自测用，别拿去训练"）。

### A.6 两个必须保留的缺陷（第一个已修，第二个仍是 identity unresolved）

1. **裁剪窗看不见候选（已修，靠补渲而不是重判主批）**：主批 12 张固定裁 `rows 317–441`，而
   0318/0367/0415/0464 四帧候选在 `rows 109–140`，卡面写 `candidate rows 132-140 outside crop`，
   两位判读员对这 4 张都只能 `unsure`；`report.json` 里 `requested_xyxy [6,317,114,457]` 被帧高截成
   `[6,317,114,441]`。`engine/cards.py` 现在有 `--crop-mode {candidate,band,auto}`（默认 `candidate`），
   补渲的 4 张在 `out/2023-09-21_110229/cards_supp/`（`crop_mode: "candidate"`，crop 行区间
   `[66,206]`/`[55,196]`/`[44,185]`/`[45,186]`）；**主批 12 张一字节未动**
   （`cards/report.json`: `byte_identical_rerender: true`、`mismatch: []`、`n_cards 12`）。
   补渲批的判定不写进 `judgments/`（sha 与规范卡不同会被守卫拒收，`judge_agreement_supp.json` 记
   `published_to_judgments: false`），但人工复核仍落 `reviews.jsonl`、仍能导出。

2. **亮头坐在一条极淡的全宽细线上（identity 仍未解）**：主批 7 个 accept 的候选都是 15–24 × 8–10 px 的亮头，
   径向厚 3–4 行，`Δrow 0–1`（±2 帧内稳定）；补渲 4 帧的框更大（23–39 × 16–22 px，把头部连同下方亮扇一起框住）。
   同一个"倍数"有三种参照物，必须分清【回执 + 原始产物复算】：
   - 相对检测阈值 `hi`：**2.7–3.0×**（复核理由与判读员 B 用的口径）；
   - 相对那条淡线的行均值：**≈1.7×**（lead 09:53 更正的写法；我的复算 3.17×/3.30×/2.88× 是取
     "列最大值 vs 行均值"，口径不同）；
   - 相对全帧中位数 27.0：头部 **+38 gray 左右（≈2.5×）**；而那条线只比中位数高 **+14 gray**。
   - 覆盖率也是口径依赖的：lead 报 11/10/12 beams 过"行均值一半"，我按同样阈值数到 69/58/61 beams（54/45/48%）；
     按"每 beam 在 rows 381–393 的局部最大值 ≥40"数则是 68/57/59%（≥37 时 79/77/83%，这才是复核日志
     "66–84%" 的可复现口径）。
   **结论**：头部确实比它所坐的线更厚（3–4 行）更亮（≈1.7× 线、2.5× 中位数），但在 128 beam 的分辨率下，
   "线上的一处强散射点"与"躺在线上的一块石头"**无法区分**——`identity: unresolved`，不是 UXO 标签。

### A.7 10:0x 收尾复核（写文档时又跑了一遍）

| 项 | 命令 | 10:0x 的实际输出 |
|---|---|---|
| 状态总表 | `cd plugin && $PY -m sonarllm.cli status` | 6 条录音，每条 `proposals 100–839 / cards 12 / judged 12 / reviews 1–12`；判读分布 171105 `{structure 7, unsure 5}`、100927 `{structure 10, unsure 2}`、101840 `{object 11, unsure 1}`、105230 `{object 10, unsure 2}`、110229 `{object 7, unsure 5}`、120653 `{structure 7, unsure 5}` |
| 判定合法性 | `check --recording 2023-09-20_171105` | `12 条判定，0 条不合法`（`resign` 已把旧判定重签到新卡；`resign` 只重签不重判） |
| 单录音导出 | `export --dst <tmp> --recording 2023-09-21_110229` | `n_exported 11`、`{val: 5, unassigned: 6}`、`n_fixture_skipped 0`（10:13 实测；补渲 4 条计入后从 7 变 11） |
| fixture 录音导出 | `export --dst <tmp> --recording 2023-09-20_171105` | `n_exported 0` + 中文原因行（8 条复核全是 fixture） |
| 自检 | `$PY tests/run_all.py` | `PASS 119  FAIL 0  ERROR 0  SKIP 0 (17.9s)`（10:12）；上一轮 118/1 的红灯（图例缺 `NOT a prediction`）已修 |
| band.json 自查 | 读 `out/2023-09-21_110229/band.json` | `unreliable_model 533 6 533`、f125 `{row 387, row_lo 381, row_hi 393}` |

两条要一起记住的：

1. **`resign` 不是重判**。它只把判定的 `card_sha256` 重签到当前卡片并留审计字段；声呐像素变了就必须重判。
   现在 6 条录音的 `judged 12` 是靠 resign 保住的，不能读成"12 条都是新判的"。
2. **`status` 的 `cards`/`judged` 列不是文件数**，是跨卡片根按样本计的；`out/cards/` 与
   `out/<rec>/cards/` 同时存在，列里的 12 只代表"这条录音有 12 个样本号被计到"。

### A.8 原始灰度对照：卡片是拉伸的，看卡片不能代替看原始灰度

`out/2023-09-21_110229/raw_contrast.json`【原始产物复算】把两批框放回原始 PGM（背景取框外全帧，
`bg_med` 27.0）。存在的意义是**防止"卡片拉伸骗人"**：`cards.py` 用共享 p0.5–p99.5 锚点 + shoulder 拉伸，
卡片上的白不代表原始灰度高，反过来"原始灰度只有中位 2 倍"也不能拿来否掉它。

| sample | 框 px | in_max | in_mean | bg_p99 | in_max/bg_med | 框内 ≥bg_p99 |
|---|---|---|---|---|---|---|
| 0318 supp | 39×16 | 142 | 53.2 | 46 | 5.26 | 57.4% |
| 0367 supp | 30×22 | 130 | 56.1 | 46 | 4.81 | 69.5% |
| 0415 supp | 23×16 | 124 | 56.9 | 45 | 4.59 | 73.1% |
| 0464 supp | 23×17 | 133 | 61.4 | 45 | 4.93 | 79.3% |
| 0125 主批 | 19×9 | 133 | 59.4 | 44 | 4.93 | 67.8% |
| 0173 主批 | 25×10 | 148 | 52.9 | 43 | 5.48 | 54.0% |
| 0560 主批 | 26×9 | 143 | 55.0 | 43 | 5.30 | 58.1% |
| 0657 主批 | 16×10 | 140 | 56.1 | 43 | 5.19 | 59.4% |

**结论**：supp 那 4 帧在原始灰度上与主批 7 条**同一量级**（`in_max 124–148` 对 `133–148`；
框内过 p99 的比例 57–79% 对 54–68%，supp 反而更高）——它们不是"卡片拉伸放大出来的幻影"。
但"亮"不等于"是目标"：这些头约为帧中位数的 4.6–5.5 倍，而它们坐着的那条淡线只比中位数高 +14 gray；
128 beam 的分辨率下，"线上的强散射点"与"躺在线上的一块石头"仍无法区分，`identity: unresolved`。
完整论述见 `docs/LIMITATIONS.md` §6.6。

### A.9 普查的第二个视图：按 `base`（形状证据）重排

`tools/rank_by_shape.py` → `out/census/RANK-BY-SHAPE.md`。为什么需要它：`census.py` 的复合分是
`base × (1−覆盖闸) × geo`，三道闸乘完 40 条全落在 0.000–0.058，名次由"哪道闸响了"决定；
而闸考察的几何可辨识性**已知不成立**（三条受审计录音全 `unreliable_model`）。所以"先看哪条"
应由 `base` 回答，闸只当警告。

前 8（base 序）：110229 `0.129`（cov 0.00）、182317 `0.128`（cov 0.54）、105856 `0.103`、
110049 `0.073`（cov 0.53，**无 `paired_role`，不能导出**）、123500 `0.067`、103728 `0.067`、
101131 `0.064`、180506 `0.063`（cov 0.81）。无 role 的三条仍是 182317 / 175000 / 110049。

**一句话结论**：几何闸只能用来**否决**，不能用来**认证**——182317 的 `base` 与 110229 几乎相同
（0.128 对 0.129），但它 54% 的帧是整幅覆盖（那是结构），它"几何闸通过"只因为候选少而稳。
`docs/CENSUS-V2.md` 已由 t-geom 落盘（10:13，18775 B）；`census.py` 现在也按 `base` 排序（`rank_key=base`），所以本视图与权威表同序，只保留“为什么不看复合分”的解释。

