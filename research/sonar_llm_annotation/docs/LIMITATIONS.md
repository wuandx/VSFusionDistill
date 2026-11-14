# LIMITATIONS · 这套东西不能做什么

> 每一条都给出证据指针（脚本路径 / 产物路径 / 原始输出行）。层级标记沿用 `README.md` §6。
> 本文件不写"未来会解决"，只写**现在成立**的边界。

---

## 1. 声呐侧没有人工 GT，产出只能是 candidate

**【仓库原文】** `code/VSFusionDistill/aodet/datasets/converters/uxo_to_paired.py`（第 35–38 行）：

> `Sonar ground-truth boxes do not exist; they are produced later by the pose-based projection tool (F2 TODO 14.2), which fills sonar.json annotations and pairs.csv.`

即：旧项目 `sonar.json` 里的框是**位姿投影**填的，不是人画的。因此：

- 本仓库导出的任何框都是 **candidate**，`provenance` 里写死
  `candidate_only_not_training_ready: true`（实测 `plugin/out/_smoke_dataset/provenance.json`、
  `out/_guard_test/provenance.json`、以及本次 `export` 到临时目录的产物）。
- **不能用本仓库的产物去评价"模型读声呐的能力"**。`docs/FINDINGS.md` 记录的
  `[sonar_uncoupled @ d0 gt=blob] AP=0.1883 AP50=0.4004` 复现的是"能不能重现投影"，
  不是"能不能从声呐里检出目标"（【仓库历史记录】`results/2026-11-04_sonar_b0/eval_sonar_b0_valid.log`）。
  同一日志里 `AP @ area=large = -1.000`：投影框全是 small/medium。
- 没有 GT ⇒ **没有 AP/mAP 可以报**。任何"本流水线精度 xx"的说法都缺分母。

---

## 2. `gantry.csv` 不是声呐定位源（已三条证据否掉）

**【原始产物复算】**（`docs/geometry-calibration.md` §3、BRIEF §2.1/§2.2）：

| 否证 | 数字 |
|---|---|
| 圆拟合：gantry 轨迹是一个半径约 1.21 m 的圆，几乎是纯转动 | `R = 1.2121 m`，残差 11.6 mm，`z ≡ −0.7500`，只转了 0.32–0.36 圈 |
| 当成"目标–声呐向量"用会自相矛盾 | `|p|` 只有 0.689–2.407 m，若真是目标距离，回波应移动约 408 行；实测亮弧脊线只在 row 182–200（bomb） |
| 当成"目标位姿"用与光学标定冲突 | 同一条 gantry 同时是光学吊臂的轨迹（相机侧），两者不可能同时成立 |

结论：`gantry.csv` 只能当**时间对齐/结构运动参考**，不能当声呐位姿。
因此 `engine/geometry.py` 的 `FrameGeom.predict()` **永远**返回
`{"available": false, "reason": "gantry_not_sonar_frame"}`（实测三条录音都如此），
判定卡也**不画** 3D 预测框（`docs/judgment-protocol.md` 规定 `prior: unavailable` 时只给 `--`）。

---

## 3. FOV = 130° 已被排除，且"用亮弧宽度反解 FOV"这条路本身是空的

- **【原始产物复算】** 若把亮弧当目标本体，则 `beams = 2·atan(L/2r)/θ·128`，
  bomb 实测 `beams=116`、`L=0.737 m`、`r·θ ≈ 0.813 m·rad` ⇒ `θ ∈ [15.4°, 67.0°]`
  （`out/calibration.json:fov_bound_if_echo_is_target`，`status: conditional_bound_not_a_measurement`）。
  130° 落在区间外 ⇒ 130° 这个假设被排除。
- 但**这个上界本身也不可用**：它的前提是"亮弧 = 目标本体"，而 §4 已证伪。
  于是 `docs/geometry-calibration.md` 把它降级为"条件界"，
  `out/calibration.json` 里 `fov` 仍在 `unavailable` 列表里。
- **单视角原理性无解**：一条量测方程 `beams = 2·atan(L/2r)/θ·128` 里 `r` 与 `θ` 两个未知，
  没有第二种观测量就解不出来。**不要**再用"目标看起来多宽"去反推 FOV 或目标尺寸。

---

## 4. 亮弧是**类无关结构**，不是目标（厚度口径必须并列）

### 4.1 已确定的部分

**【原始产物复算】** `out/companion_test.json`（`tmp/lead_companion.py` 的产物）：

| 录音 | 主连通域 beam 跨度 | 径向厚度 | 换算 | 第二连通域 |
|---|---|---|---|---|
| 2023-09-20_171105 (bomb) | 125.0（p10 118.2 / p90 128.0） | **111.5 px** | **0.3326 m** | 42.5 beam / 54.0 px |
| 2023-09-21_120653 (grenade) | 104.5（56.9 / 128.0） | **109.0 px** | **0.3251 m** | 40.0 / 58.0 |
| 2023-09-21_100927 (mortar) | 113.5（60.5 / 128.0） | **107.5 px** | **0.3206 m** | 40.5 / 50.0 |

配合 `docs/FINDINGS.md` 的两条：全帧存在率 715/715、771/771、725/725；
脊线位置只随录音变（bomb row 182–200 / grenade 137–154 / mortar 146–160），
帧间几乎不动。**一条贯穿扇面、时域不动、跨类同尺寸的亮弧 = 支撑结构/池底回波**，
不是目标，也不能当标注对象。`docs/judgment-protocol.md` 因此把它列为"错误示例"第一位。

### 4.2 口径差异 ①：厚度到底多少（**并列保留，不合并**）

| 口径 | 数字 | 出处 | 差别成因 |
|---|---|---|---|
| 主连通域径向跨度（单一连通域） | 111.5 px = **0.333 m**（bomb）；另两类 0.325 / 0.321 m | 【原始产物复算】`out/companion_test.json` | 只统计"最大那个亮块"的行向跨度，**不含**它下方那片亮度略低的扇面 |
| 盲判看图估读 | bomb 亮带厚 **150–250 row ≈ 0.45–0.75 m**；grenade 10–60 row ≈ 0.03–0.18 m；mortar 3–8 row 细线 | 【助手目视】`out/blind_judge.json:cross_card_observations[0]`（原文："bomb 三帧的亮带都是128 beam 全宽、厚度可达150–250 row（约0.45–0.75 m）并拖着下方亮扇"） | 把亮弧**连同下方亮扇**一起算进"亮带"厚度 |

两者相差约 1.35–2.2 倍，**不是同一物理量**：一个量"主连通域"，一个量"视觉上连成一片的亮区"。
在阈值、种子点、连通域规则统一定义之前，**这两个数都必须留着**；
引用时写清"哪一个口径"，禁止取平均、禁止只引其中一个。

### 4.3 由此推不出的东西

- 不能因为"三类厚度都是 0.32–0.33 m"就说"目标是同一类物体" —— 那是结构自身的几何。
- 不能因为"厚度 0.33 m 与目标长度 0.44–0.74 m 同量级"就说"亮弧就是目标"——
  `docs/judgment-protocol.md` a3 明确：`dR ≈ L` 时必须判 `uncertain`。

---

## 5. 关键帧传播只在"配准误差内"成立；结构**不是**刚体

**【原始产物复算】**：

- `out/propagate_2023-09-20_171105_622.json`：715 帧全自动（`auto_frac 1.0`），
  `score_median 0.903`，`drow_range [-5, 7]`、`dbeam_range [0, 0]`、`clipped_frac 0.0`。
- 剪切模型实验（`tmp/lead_shear.py`，2.3 s，只打印不落盘）：
  刚体平移 vs `row' = row + a + b·beam`，bomb 的相关系数只有 **0.26–0.57**，
  shear 相对平移的增益 **≤ 0.113**；mortar 的相关系数只有 **0.07–0.14**。
  ⇒ 亮弧的形状逐帧在变（非刚体），一个 (drow, dbeam) 平移量描述不完。
- `docs/geometry-calibration.md` §6 的运动补偿实验**失败**（判据是残差下降 ≥60%）：
  1-D 行移 −2%、2-D −25%、旋转+行移 −38%、弹性 −21%，全部没达标。

### 5.1 口径差异 ②：位移到底多大（**并列保留，未解决**）

| 口径 | 数值 | 出处 |
|---|---|---|
| `engine/track.py` 链式估计（相邻帧逐步累加） | bomb 622 起：`drow ∈ [−5, +7]`，`dbeam ≡ 0`，auto 100%，score 中位数 0.903 | 【原始产物复算】`out/propagate_2023-09-20_171105_622.json`；本次以 `$PY -m engine.track ...` 重跑，数值逐项相同（4.1 s） |
| 同一关键帧的**直接**估计（宽窗 ±200 行、掩膜均值剖面） | bomb：`−40 … +43`（f0979 −40、f1336 +43，相关系数 0.687/0.740）；grenade `−5 … +53`；mortar `−19 … +15` | 【原始产物复算】`tmp/lead_drift2.py`（0.32 s，只打印） |
| `engine/echo.py` 自带配准（anchor 帧 979） | `[summary] shift_abs_median [16.0, 1.0]`（f622；逐帧行不再印 shift） | 【原始产物复算】`$PY engine/echo.py --recording 2023-09-20_171105 --frames 622,700 --mode aligned` |
| `out/drift_probe.json` 的旧批量探测 | 全部 `drow = −40`（正好等于搜索下界）、`align_score = −1.0` | 【原始产物复算】退化饱和，见 `tmp/lead_shiftfix.py` 记录的原因：稀疏带的中值投影处处为 0 → 剖面常数 → 归一化相关分母为 0 → `_best_lag` 回退到第一个候选 lag |

**未解决。** 目前只能确定：链式估计与直接估计相差一个量级（`−5..+7` vs `−40..+43`），
`echo.py` 自己在同一对帧上又给出 +16，而链式说 −1。
**在差异解释清楚之前，不能用传播结果做"同一目标跨帧一致"的定量结论**；
判定协议 a2 只用它做"位置大致稳定"的弱证据，且漂移门限写的是 0.05–0.15 m（约 17–50 行），
已经小于直接估计的极值。

**【推断】**（未证实）：`tests/test_02_echo_shift.py` 在合成已知位移上系统偏差
（已知 +7 → 估 drow=5；已知 −11 → −17；已知 +13 → 8），提示 `estimate_shift` 在
"结构剖面接近常数"时会**系统性低估或跳变**——这与 §5.1 里"链式只给出小位移"方向一致。
这是线索，不是结论。

---

## 6. `mesh_to_target` 仍是 HOLD；剪影只是**上界**

- **【仓库原文】** `docs/mesh-prior.md`：`mesh_to_target` 为 HOLD/null ⇒ 所有读数带
  `mesh_to_target_used: false`，只按**标称长度**做缩放（`100lbs 0.737 m` /
  `incindiary 0.442 m` / 剪影 `mortar_shell 0.58 m`，而 BRIEF 里 mortar 的标称长度是
  "≈0.35 m"且 `nominal_length_m: null` —— 这个不一致**没有解决**，读数里必须写清用的是哪个）。
  这就是**口径③**（mortar 缩放长度 0.58 m vs ≈0.35 m，差 1.66×），与 §4.2 的 ①、§5.1 的 ②
  并列保留，**不得取中值**。
- 剪影 = 阴影体（shadow volume），**不模拟**遮挡、多径、多次反射、材质。
  因此它给出的是候选框的**上限**（"目标最多占这么大"），不是"回波应该长这样"。
- `uniqueness: False` 写死在返回值里：同一个剪影对应 864 个位姿（24 yaw × 6 pitch × 6 roll，
  pitch 只到 ±30°、yaw 步长 15°），**位姿不唯一**。任何"由剪影反推位姿"的说法都错。
- 已知偏差：只按长轴缩放 ⇒ incindiary 的横截面 +21%/−3%，波束跨度可能偏宽约 20%。
- 实测读数（r=1.26 m、az=10°、broadside）：100lbs 34×80 px / area 2059；
  incindiary 21×43 / 805；mortar_shell 27×48 / 877（`out/prior_check.json`，8 项断言 all_pass）。

---

## 6.5 距离带（rangeband）：三态里两态是"拒绝"，且**退路带宽与候选同源**

`tools/rangeband.py`（schema `sonar_llm_annotation/rangeband/v0`）把一条录音的 top-1 检测距离
`range_i` 与声呐头位置 `c_i` 一起拟合 `range_i = |P − c_i| + b`（有界 LM；`P` 3D 点、`b` 偏置），
**偶帧拟合、奇帧留出**交叉验证，然后按状态给带：

| status | 触发 | 带宽 | 卡片/导出的措辞（代码里的实际字符串） |
|---|---|---|---|
| `model_ok` | 无参数撞界 **且** 留出 p90 ≤ 0.15 m | `ceil(p90/res)` | `range band … (predicted ±N rows)` |
| `unreliable_model` | 撞界（`b`/`P_z`/`P_xy`）或留出 p90 > 0.15 m | `max(6, ceil(3·MAD/res))`，退回**观测散布** | `range band … (observed ±N rows; model rejected; NOT a prediction)` |
| `insufficient_detections` | 通过 snr≥6 与 gantry 连接的检测 <12 条 | 无（`frames: {}`） | 本帧无条目（不画线） |

五条录音的实测（`out/<rec>/band.json`，读盘）：

| 录音 | status | n | band_rows | 拒绝原因（字段原值） |
|---|---|---|---|---|
| 2023-09-20_171105 | `insufficient_detections` | 0 | — | 旧 echo proposals 没有可连接检测 |
| 2023-09-21_100927 | `insufficient_detections` | 0 | — | 同上 |
| 2023-09-21_101840 | `unreliable_model` | 769 | 31 | 留出 p90 **0.1627 m** > 0.15（in-sample p90 0.1564） |
| 2023-09-21_105230 | `unreliable_model` | 837 | 25 | `bounds_active {b:true,z:true}`：`b=−0.300000`、`P_z=−1.999511` |
| 2023-09-21_110229 | `unreliable_model` | 533 | 6 | `bounds_active {b:true,z:false}`：`b=+0.300000`；in-sample p90 0.4186、留出 0.4177 |

**为什么撞界就不是"解出来了"**：平台相对目标的横向位移太小、杠杆臂短（`docs/QA-REPORT.md` §10.1 的原话是"1.5 m 距离上平台只移动约 0.2 m"；普查另记 105230/110229 的平台总位移 2.03 m / 1.80 m，那是沿轨迹的总路程，不是有效杠杆臂），
`(P_radial, b)` 沿一条平坦谷底可以互换而残差几乎不变；优化器顶到墙说明**数据没有选中这个参数**。
所以 in-sample 2–3 cm 的残差（105230）不能当作"固定 3D 点"的证据——这是对早期说法
"残差 2–3 cm 证明是固定 3D 点"的**更正**，更正记录见 `docs/FINDINGS.md` 第十二节。

**退路带是循环的（必须写清）**：`unreliable_model` 时给出的带，是**同一批检测**的距离分布按
`3·MAD` 修剪出来的（`tools/rangeband.py` docstring 的原话：*a statement about our detections,
not about the target*）。也就是说：带子的位置来源于候选本身，把它画回卡片**不可能帮人找到候选**——
它只能显示"检测器已经在哪里响过"。

> 110229 的 band 381–393（6 行）是在模型被拒（留出 p90 0.4177 m）之后，由该录音自己的 top-1
> 检测行按 MAD 修剪得到的；它与候选同源，**不构成独立证据**，不得用于"在带内找目标"或据此认为
> 候选可信。真正需要的是外部标定（scipy + 标定球）或人工给一个已知距离的目标。

而且"更窄"不等于"更确定"：110229 的 6 行是 `max(6, ceil(3·MAD/res))` 的**下限**（MAD 触底），
若模型被接受，按留出 p90 0.4177 m 应给 `ceil(0.4177/0.0029826) ≈ 140` 行——退路带比模型带窄了 20 多倍。
同类矛盾在 105230 上已被 QA 记为 **O3（已知残留，未修）**：退路 25 行反而窄于被接受时本会给出的
40 行（`ceil(0.1178/0.0029826)`），原因见 `docs/QA-REPORT.md` §10.1；本轮不改代码，只记录。

**它约束什么**：只有距离（两条水平线 `row_lo`/`row_hi`），**不约束方位**——`tools/rangeband.py`
的 docstring 记了 |beam vs world azimuth| 的 r² < 0.01，所以卡片上画的是两条线，**永远不是矩形**
（`engine/cards.py` 的 `_blend_band_rows` 注释："a band is a *row* interval … never as a rectangle"）。
`insufficient_detections` 的录音在卡片与 `export.json` 里都没有带；不要把"没有带"读成"距离不对"。

---

## 6.6 卡片是拉伸过的：**看卡片不能代替看原始灰度**

`engine/cards.py` 的显示拉伸是共享的 p0.5–p99.5 锚点 + shoulder（不是线性、更不是原始灰度）。
所以"卡片上很白"只能说明它落在这一帧的高分位上，不能直接说明原始灰度有多亮。反过来说，
也**不能**因为"原始灰度只是中位数的 2 倍"就把它否掉——这两个方向都会骗人。

`out/2023-09-21_110229/raw_contrast.json`【原始产物复算，lead 10:0x 做的】把两批框放回原始 PGM
（背景取框外全帧，`bg_med` 27.0）：

| sample | 框 px | in_max | in_mean | bg_p99 | in_max/bg_med | 框内 ≥bg_p99 比例 |
|---|---|---|---|---|---|---|
| 0318 supp | 39×16 | 142 | 53.2 | 46 | 5.26 | 57.4% |
| 0367 supp | 30×22 | 130 | 56.1 | 46 | 4.81 | 69.5% |
| 0415 supp | 23×16 | 124 | 56.9 | 45 | 4.59 | 73.1% |
| 0464 supp | 23×17 | 133 | 61.4 | 45 | 4.93 | 79.3% |
| 0125 主批 | 19×9 | 133 | 59.4 | 44 | 4.93 | 67.8% |
| 0173 主批 | 25×10 | 148 | 52.9 | 43 | 5.48 | 54.0% |
| 0560 主批 | 26×9 | 143 | 55.0 | 43 | 5.30 | 58.1% |
| 0657 主批 | 16×10 | 140 | 56.1 | 43 | 5.19 | 59.4% |

**两条结论都必须写进去**：

1. supp 那 4 帧在**原始灰度**上与主批 7 条同一量级（`in_max 124–148` 对 `133–148`；
   框内过 p99 的比例 57–79% 对 54–68%，supp 反而更高）。它们**不是**"卡片拉伸放大出来的幻影"，
   在原始数据里本来就是一块高出路面的回波。
2. 但"亮"不等于"是目标"：这些头的最大灰度约 `4.6–5.5×` 帧中位数，而它们坐着的那条淡线
   只比中位数高 **+14 gray**（见 §7.7 与 FINDINGS 第十二、十三节）。分辨率只有 128 beam，
   "线上的强散射点"与"躺在线上的一块石头"仍无法区分——`identity: unresolved`。

以后凡是要判断"这块回波到底有多亮/多大"，先看 `raw_contrast.json` 这类原始灰度统计，
再回来看卡片；**只凭卡片的观感下结论，等于让拉伸函数替你判读**。

---

## 7. 当前工程缺陷（实测，非设计边界）

> 下文命令里的 `$PY` = `/mnt/c/Users/ASUS/AppData/Local/Programs/Python/Python312/python.exe`。
> bash 里直接敲 `python` 会用到 WSL 自带的 3.10.12（**没有 numpy**），跑 `engine/*.py` 必失败。

### 7.1 echo→cards 的契约：03:13 起可用，但只是"重命名+回读"，不产生新信息

03:12 之前把 echo 记录喂给卡片会直接崩：

```
$PY engine/echo.py --recording 2023-09-20_171105 --frames 622 --proposals <tmp>/p2.jsonl
$PY engine/cards.py  --proposals <tmp>/p2.jsonl --out <tmp>/cards ...
  → ValueError: frame_data has neither 'img' nor image.path; cannot render a card
    (engine/cards.py:192, in decode_frame)
```

03:13 `engine/cards.py` 新增 `proposal_to_record()`（`[仓库原文]`，函数 docstring：`Adapt one engine/echo.py
proposals.jsonl row to the BRIEF record shape`）后不再崩。它做三件事：① 用**文件所在目录名**当录音名
（或 `--recording` 覆盖）回读该帧 `.pgm`；② 把 echo 的 `blobs[0]` 原样改名为 `candidate`；
③ 补 `predicted: {available: false, reason: "gantry_not_sonar_frame"}`、`prior: {model: null, ...}`。
**没有任何检测发生**（函数注释：`no detection happens in this module`）。

实测（03:16–03:19）：

| 输入 | 结果 |
|---|---|
| `--proposals out/2023-09-20_171105/proposals.jsonl --limit 1` | `758x1764 zoom=2 prior=unavailable`（0622） |
| `--proposals out/2023-09-21_120653/proposals.jsonl --limit 1` | `1122x1600 zoom=3 prior=unavailable`（0163） |
| `--proposals out/2023-09-21_100927/proposals.jsonl --limit 1` | `1122x1600 zoom=3 prior=unavailable`（0087） |
| `--proposals tmp/echo_probe/grenade_aligned.jsonl` | `KeyError: "unknown recording 'echo_probe'"`（目录名不是录音名） |
| 同上 + `--recording 2023-09-21_120653` | `1493x1554 zoom=6 prior=unavailable` |

两个必须知道的后果：

1. **`out/<rec>/proposals.jsonl` 里的 100 条记录都是 `mode: local`**（`[复算]` 逐行统计），而 local 模式
   大多给 0 个候选：bomb 100 帧里只有 37 帧 `n_candidates>0`、grenade 8/100、mortar 8/100。
   没有 blob 的帧，卡片画的是 `frame-default` 框（`box_is_candidate: false`）——**那不是候选**。
2. 有 blob 的帧，`candidate.box_xyxy` 就是 echo 的 rank-0 blob，可能是退化框。实测 bomb 0700 的框是
   `[45.0, 55.0, 49.0, 59.0]`（4×4 px），而渲染报告里 `candidate_degenerate: false` —— **退化框没有被自动拦下**，
   判读时必须按 `docs/judgment-protocol.md` 的 c4「退化候选」自己判 `uncertain`。


### 7.2 `engine/echo.py` 的 `--mode` 默认值已经变过一次

02:58 时默认 `aligned`（bomb 622：`n_cand=6`），03:00 时默认 `local`（同一帧：`n_cand=0`，
`drop=+0.67`；grenade 163 也是 `n_cand=0`）。
候选数量对模式高度敏感 ⇒ **所有命令显式传 `--mode`**，产物的 `mode` 字段必须随记录保存
（`echo.py` 确实写进了记录，可用于事后分辨）。

### 7.3 `card_sha256` 守卫：重渲即失效，靠 `resign` 重签（不是重判）

03:xx 时的实测（现在已不成立，留作历史）：

```
cd plugin && $PY -m sonarllm.cli check --recording 2023-09-20_171105
  → FAIL 2023-09-20_171105_0622: card_sha256 与当前卡片不一致（卡片已重渲染，判定需重做）
  → 2023-09-20_171105: 1 条判定，1 条不合法
```

10:0x 再查是 `2023-09-20_171105: 12 条判定，0 条不合法`——因为加了 `resign`
（`plugin/sonarllm/cli.py:69-108`）：把旧判定的 `card_sha256` 重签到新卡，
并记 `card_sha256_previous` / `resigned_at` / `resigned_by` / `resigned_note`。
**它只重签不重判**，只在"声呐像素没变、只是渲染器改了"时成立；像素变了就必须重判。
守卫本身（`plugin/sonarllm/judge.py:157-165`）仍是"图和结论必须对得上"。
仍然要记住：**任何重渲都会让未重签的判定失效**。

### 7.4 导出 0 条：两道闸，都不是"导出器坏了"

```
cd plugin && $PY -m sonarllm.cli export --dst <tmp>/dataset --recording 2023-09-20_171105
  → n_exported: 0, recordings_per_split: {}, candidate_only_not_training_ready: true
```

`plugin/sonarllm/dataset.py:169-175`【仓库原文】有两道闸：① 只导出 `accept`（取 `final_box`）
与带 `final_box` 的 `revise`；② `data_source == "fixture"` 的复核默认跳过。
`out/2023-09-20_171105/reviews.jsonl` 现存 8 条**全部**是 `data_source: "fixture"`
（accept 4 / revise 2 / uncertain 1 / reject 1，`proposals_path` 指向 `tmp\review\proposals\...`）【实测】，
所以一条也出不去——这是故意的防污染设计，CLI 还会打印：
`导出 0 条：没有 status=accept/revise 的**人类**复核记录。已故意不写 data.yaml（见 _EMPTY_DO_NOT_TRAIN.txt）。`

**反过来，有真人 accept 的录音是能出的**（10:0x【实测】）：
`export --recording 2023-09-21_110229` → `n_exported 7`、`recordings_per_split {val: 4, unassigned: 3}`、
`n_fixture_skipped 0`，全部带 `candidate_only_not_training_ready: true`。
supp 4 条复核（10:08）之后，同一条命令给 **`n_exported 11`、`{val: 5, unassigned: 6}`、`n_fixture_skipped 0`**
（10:13 实测）——差数就是那 4 帧从 unsure 变 accept。

**当前汇总口径（10:09【原始产物复算，`out/_demo_v2/provenance.json`】）**：`n_exported 14`
= 110229 **11**（主批 7 + supp 4）+ 105230 2 + 101840 1；`recordings_per_split {train:1, val:5, unassigned:8}`
（item 数）、`n_unassigned 8`、`n_fixture_skipped 5`、14 张 PNG 全为 128×441、png/txt 逐 split 相等。
旧 `out/_demo_110229` 的 **10 条**保留作历史：它少 4 条，是因为当时那 4 帧（0318/0367/0415/0464）
只能判 `unsure`（裁剪缺陷，见 §7.7）；补渲 + 复核后由 10 变 14，不是重跑导出器改了口径。
注意 `out/export.json`（09:51）**早于**这 4 条复核（10:08），所以它里面的 `n_reviewed 19`
是那一分钟的台账快照，不能用它推当前的 14 条——当前数以 `out/_demo_v2` 为准。

另外，`status` 表里的 `cards` 列是**跨目录统计**（`judge.card_roots()` = `OUT/cards`、
`tmp/cards/dryrun`、`tmp/cards` 及 `OUT/*/cards`，`plugin/sonarllm/judge.py:50-54`），
别拿它当卡片总张数：03:12 时 `out/cards/` 是 37 张扁平 PNG、`status` 报 17；03:19 再查是
36 张（12/录音）+ `out/_qa/cards` 1 张，而 `status` 报 12/录音【实测】。
两次数都对不上，**别拿这一列当卡片总张数**（具体计数口径没读透，此句仅为【推断】：按样本号跨根统计）。

### 7.5 自检：现在 119 PASS / 0 FAIL / 0 SKIP；历史 118/1 与 9/9/4 都保留

现状（10:12【实测】，17.9 s，写 `out/_qa/qa-results.json`）：

```
PASS 119   FAIL 0   ERROR 0   SKIP 0   (17.9s)
```

上一轮唯一那条红灯（图例缺 `NOT a prediction`，`tests/test_15_cards_band.py:129`）已经修掉，
修法是**把限定词前置、必需段永不截断**：`amber dash = range band (NOT a prediction; observed +-N rows)`
（`engine/cards.py:1218`）；`model_ok` 时仍写 `predicted +-N rows`。新增的三条测试锁住：
句首必须是 `amber dash = range band (NOT a prediction`、图例内不得出现 `...`、N 必须从 `band.json` 实算。
这是**诚实性修复**（标签不能被版面裁成一句乐观的话），不是"测试放宽"。

历史，保留不删：

- 10:02【实测】：`PASS 118 / FAIL 1 / ERROR 0`（14.9 s），红灯就是上面那条图例措辞。
- 03:03【实测】：`PASS 9 / FAIL 9 / ERROR 4`。失败分两类：
  **测试与引擎 API 不同步**（4 ERROR：`range_window` 当方法调 → `TypeError: 'tuple' object is not callable`；
  `intersect_bounds` 用旧键 `'fov_deg_min'` → `KeyError`；`estimate_shift()` 少 `band` 参数）；
  **估计器本身不准**（9 FAIL：已知 +7 估成 5、−11 估成 −17、+13 估成 8；行剖面只在 58/780 行非零；
  已知 +5 beam 估成 3）。
- `tests/` 在 03:00–03:01 仍被改动，9/9/4 是 **03:03 的快照**。

### 7.6 其它已知小缺陷

- `engine/echo.py:810-817` 有一段写在 `return 0` 之后的重复 jsonl 写入代码（死代码，无害）。
- `docs/geometry-calibration.md` §2 给 bomb 的距离窗口上界写作 `3.0229 m`，
  但按它自己表里的 `WindowStart 0.6949` + `WindowLength 2.3264` 应为 `3.0213 m`，
  按"最后一行"口径应为 `3.0184 m`（`out/calibration.json` 与 `engine/geometry.py` 用的都是后者）。
  **以 `out/calibration.json` 为准**；§2 的 3.0229 是笔误级不一致。
- 距离分辨率**逐录音**不同：bomb `0.00298256`、grenade `0.00298322`、mortar `0.00298254` m/row。
  用 0.002983 去乘别人录音的行数会带来 <0.1% 的误差，但写"精确等于"就是错的。

### 7.7 行带要靠 driver 挂上去；裁剪窗缺陷已修（supp 批），但修法是"补渲"不是"重判主批"

- **`cards.py` 不读 `band.json`**：它没有 `--band` 参数（只有 `--band-h`，那是 16×16 块的高度），
  只有帧记录里带 `band` 字段时才画两条虚线。`tmp/cards_110229/make_cards.py` 是那个 driver
  （docstring：*Nothing here detects anything … only picks frames and attaches the two*）。
  所以"卡片上没有虚线"通常不是 band 算错了，而是记录里没挂——`docs/QA-REPORT.md` §10.2 用
  amber 像素数做过对照：挂 band 时 464 px，不挂时 0 px。
- **裁剪缺陷与修法（已落地）**：主批 12 张卡的裁剪窗固定取 `rows 317–441`（候选列中心 × band 行），
  而 `0318 / 0367 / 0415 / 0464` 四帧的候选在 `rows 109–140`，落在窗外；卡面写
  `candidate rows 132-140 outside crop`，两位判读员对这四张都只能给 `unsure`。
  `engine/cards.py` 现在有 `--crop-mode {candidate,band,auto}`（默认 `candidate`），lead 用它补渲到
  `out/2023-09-21_110229/cards_supp/`（4 张，crop 分别为 `[66,206]`、`[55,196]`、`[44,185]`、`[45,186]` 的行区间）。
  **主批 12 张一字节未动**：`out/2023-09-21_110229/cards/report.json` 记 `byte_identical_rerender: true`、
  `mismatch: []`、`n_cards 12`。补渲后双人盲判 **4/4 `object`**，合并见 §9.7。
- **补渲卡的判定故意不写进 `judgments/`**：那 4 条的 `card_sha256` 属于 supp 卡，而插件按规范卡
  （主批冻结卡）校验，放进去会被哈希守卫拒收；`judge_agreement_supp.json` 的 `note` 写明了这一点
  （`published_to_judgments: false`）。它们的**人工复核**仍在 `reviews.jsonl` 里，也仍能导出
  （这是"判定"与"复核"两条链的区别）。
- **图例截断（已修，10:0x）**：`unreliable_model` 的图例曾被版面截成 `range band (observed, ...`，
  `NOT a prediction` 正好被截掉。现在限定词前置且必需段永不截断：
  `amber dash = range band (NOT a prediction; observed +-N rows)`（`engine/cards.py:1218`），
  `model_ok` 时是 `predicted +-N rows`；`tests/test_15_cards_band.py` 的三条新断言锁住它（见 §7.5）。
  这是一条**诚实性缺陷**：标签被裁掉后，一张"观测散布"会看起来像"预测"。

---

## 8. 判读协议本身的边界（不是实现问题）

- `docs/judgment-protocol.md` 的 a3 尺寸区间 `dR ∈ [0.03, 0.35] m` 是**经验区间，不是论文事实**；
  它来自我们自己的三类读数，样本是 3 条录音。
- **水平方向（方位/beam）没有米制标尺**：波束角未知（§3），所以"目标多长"不能由像素宽度推。
  唯一能直读的目标尺寸是径向 `dR = (y1−y0)×RES`。
- 卡片上 `prior: unavailable` 时意味着"无信息"，不是"负证据"；
  `amber` 虚线/预测十字来自已被否证的 gantry 假设，**不得当证据**。
- 助手目视的判断（`out/blind_judge.json`）9 张卡里 6 张是全宽亮带、框大小 1×4–100×22 px
  与带宽无关 —— 这正是"追最亮点"的失败模式，说明**当前候选框本身不适合直接当标注**。

---

## 9. 数据与划分的边界

- **【原始产物复算】** manifest `DataSet/camera_temporal_all/manifest-resolved.json` 共 26761 items；
  三条录音里带 `paired_role` 的帧只是少数：
  bomb `val 150 / 715`、grenade `train 96 + val_id 22 / 771`、mortar `train 96 + val_id 22 / 725`。
  ⇒ 约 **20%** 的帧有角色，其余 `None`。**不要**把这 20% 说成"数据集"，也**不要**给 `None` 补角色。
- 导出策略是"只用既有 `paired_role`，不新建划分；同一录音多 role 时拒绝导出"
  （`provenance.json:split_policy`）。
- `val_id` 只是"同录音留出诊断"，不是文献协议，也不是"考场"。
- 三条录音都是**开发集**；`test` 一律不读、不评、不调参。
- 目标身份（bomb/grenade/mortar）在声呐侧 **unresolved**；判读只能给"这里有一个紧凑回波结构"，
  不能给类别。跨类比较（如"mortar 的弧更细"）只能作为**假设**提出，不能当结论。

---

## 9.5 三条录音是"最坏样本"，`compact` 只在两条录音上调过

**样本偏差（重要）**：本线最初按"每类挑一条"选了 `2023-09-20_171105` / `2023-09-21_120653` /
`2023-09-21_100927`。40 条录音的形状普查（`out/recording_survey.json`）显示，这三条的峰值行宽度分别是
76 / 57 / 23 beams，都落在"宽"的一端；另外还有宽度只有 5–6 beams 的录音。
所以"目标不可检"这个结论**只对这三条成立**，不能推广到整个数据集——这是选样造成的，不是数据本身的性质。

**`compact.py` 的调参边界**：`snr 5.5 / min_area 12 / open 0` 是在 `2023-09-21_105230` 与
`2023-09-21_101840` 两条录音上看图定的，**没有在这两条之外做任何交叉验证**（不可能做：没有 GT）。
换录音、换 ping mode、换增益都会改变阈值的最优值。它给的是"值得看一眼的候选"，不是"检测率"。

**时域背景的破坏性**：`echo.py` 用 ±10 帧局部中位做背景，对相对声呐几乎不动的目标是**破坏性**的
（中位数里包含目标本身）。因此"demed 之后什么都没有"**不能**当作"原图里没有目标"的证据。
同理，`engine/track.py` 的传播框在静止目标上也会"看起来完美对齐"——因为两边都被减掉了。

**演示数据集的规模**：`out/_demo_dataset` 只有 2 条样本（`2023-09-21_105230` 的 0386 revise、0805 accept），
两条都落在 `unassigned`（这两个样本在 manifest 里没有 `paired_role`）。它能证明链路闭合，
**不能**用来训练或评测任何东西。

## 9.6 VLM 判读在这批数据上**不可复现**（κ ≈ 0.04）

同一条模型、同一份判读协议、同样的 24 张卡，两个判读员的结论几乎完全相反：

| | object | structure | unsure |
|---|---|---|---|
| 判读员 A | 21 | 0 | 3 |
| 判读员 B | 0 | 23 | 1 |

逐卡一致率 **1/24**，Cohen's κ = **0.037**（与随机不可区分）。完整明细见 `out/judge_disagreement.json`，
分析见 `docs/FINDINGS.md` 第十一节。

原因不是谁看错，而是判据"有没有闭合轮廓"在 128 beam 的分辨率下不可执行——回波是镜面亮头 + 拖尾，
本来就没有闭合边界。**因此**：

- `judgments/` 里的 `verdict` 只能当"这一帧值得看一眼"的提示，**不能当标签**，更不能直接导出。
- 不要写"模型找到了 N 个物体"、"AI 标注 mAP = …"这类话。
- 要得到可用的判读，协议必须改成可数的像素判据 + 双人独立写不同文件 + 算 κ；κ < 0.4 的批次只能进人工队列。

这条限制与 §8（判读协议本身的边界）不同：§8 说的是协议**没覆盖到**的情况，这里说的是协议**覆盖了也判不稳**。

### 9.7 补记：110229 上 12/12 一致（κ=1.0）**不**代表"VLM 变可靠了"

同一批新卡（110229 的 12 帧）、两个盲判读员 A / B、同一份 `cards/v0` 协议：

| | object | unsure | structure |
|---|---|---|---|
| 判读员 A | 7 | 5 | 0 |
| 判读员 B | 7 | 5 | 0 |

`out/2023-09-21_110229/judge_agreement.json`：n=12、逐卡一致率 `po=1.0`、
随机一致率 `pe=0.5139`、Cohen's κ=**1.0**；不一致 0 条（合并规则：分歧时保留 A 的 verdict
并记 `alt_verdict`，不取平均、不静默转 unsure）。

**为什么不能写成"可靠"**：

- 这是**同一模型**的两次独立判读（`judge_model` 里能看到 `t-judge (deepseek-v4, cards-only)` 与
  `t-judge-b`），不是两套独立方法；一致性说明的是"同一条流水线可复现"，不是"判对了"。
- 两人的**理由并不相同**：A 从不写 `dR`，B 每张都写（0.018–0.030 m）；只有 0512 这张两人都
  `unsure`，但 A 的理由是 c6（候选只盖住亮块左段、最亮的头压在框外与尾巴连成一片），
  B 的理由是 a3（`dR=0.018 m` 低于 0.03 m 先验下限）——同一 verdict，不同判据。
- κ 在这个样本上对基础率很敏感：`pe` 已经 0.514，7/5 的分布让"全给同一答案"也能拿到高 κ。
- 12 张卡都来自**同一条录音、同一个候选形态**（亮头 + 淡线），样本不覆盖 24 卡那批
  （105230 / 101840）的宽弧形态；那批的 κ 仍是 **0.037**（§9.6），没有任何证据表明那里变好了。

**结论**：κ=1.0 只支持"这 12 张卡上两人的 verdict 一致"，不支持下述任何一句：
"VLM 判读已经可用"、"模型找到了 7 个目标"、"可以按 object 导出标签"。
它有价值的部分是**流程价值**（12 帧盲判、按 sha 钉住卡面、分歧留有记录），不是判读价值。

#### 9.7.1 supp 批（补渲的 4 张）：4/4 `object`，**κ = null（无法计算，不是 0）**

主批那 4 帧因为裁剪窗看不见候选，只能 `unsure`（§7.7）。按候选行带补渲后（`cards_supp/`，
双人各自目录盲判：`judge_a_supp/`、`judge_b_supp/`），两人对 **4 张全部判 `object`**：

| | object | unsure | structure |
|---|---|---|---|
| 判读员 A | 4 | 0 | 0 |
| 判读员 B | 4 | 0 | 0 |

`out/2023-09-21_110229/judge_agreement_supp.json`【原始产物复算】：`n=4`、`po=1.0`、**`kappa: null`**
并带 `kappa_note: "undefined, not zero"`。该文件由 `tools/merge_supp.py`（无参数）生成，内部记 `published_to_judgments: false`——supp 判定故意不进 `judgments/`。

**为什么是 null 而不是 0/1**：两位判读员只用了 `object` 一个标签，随机一致率 `pe = 1`，
`κ = (po − pe)/(1 − pe)` 的分母为 0，**公式无定义**。写成 0 会被读成"不如随机"，
写成 1 会被读成"完美一致"，两种都是伪造读数。能说的只有：4 张、两人都判 object、无分歧。

**它支持什么**：这 4 帧在补渲之后**不是"看不到所以 unsure"，而是"看得见且两人都认为像目标"**；
再结合 §6.6 的原始灰度（与主批同一量级），它推翻的是"这 4 帧是渲染幻觉"，不是"这 4 帧是 UXO"。
`identity` 仍是 `unresolved`。人工复核（`operator: lead`，是 agent 不是用户本人）对这 4 条全 `accept`，
box 取两位判读员框的并集 +1 px；理由不是"卡片上好看"，而是**同一横向位置（beams 40–76）在四个时刻
row 单调上移 132→118→112→110**——一个回波在靠近，但"是什么"仍未解。

**它不支持什么**：不能与主批的 κ=1.0 合并成"16/16 一致"——主批 12 张有 7/5 两个标签（`pe=0.5139`，
κ 有定义），supp 4 张只有一个标签（`pe=1`，κ 无定义）；**两个数字口径不同，不能相加或平均**。
也不支持"VLM 变可靠"：还是同一模型、同一条流水线（详见 §9.6 的 24 卡 κ=0.037）。

## 10. 一句话总结

这套东西能做的：**在三条录音上，稳定地把"类无关亮弧"和"可能的局部扰动"分开、
渲染出可审计的判读卡、并给出一条可复核的候选链**。
它不能做的：**给真值、给类别、给位姿、给精度指标、给可直接训练的标签**。
把它当"标注加速器"用会翻车；把它当"人眼扫描的替代品 + 判断放大器"用才对。
