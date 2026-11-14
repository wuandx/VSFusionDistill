# 40 条录音形状普查 v2：先看哪一条

> 本文件由 `tools/census.py --every 1` 的产物（`out/census/census_v2.json`）生成，与 `out/census/CENSUS-V2.md` 同一口径。只回答**先看哪一条**；声呐侧没有 GT，`identity` 仍是 `unresolved`。

## 1. 结论（先读这一节）

1. **A 段（合格推荐）为空。** 40 条里没有一条同时满足 `geo_ok` + 覆盖闸 < 0.45 + `track_frac` ≥ 0.5：最高的 `track_frac` 只有 0.130（`2023-09-21_110229`），而它触发了"距离变化低于固定物体下界"；`geo_ok` 一共 6 条。**没有任何一条录音给出覆盖半条录音的连续回波**——这是本轮的主要结论，不是排表失手。

2. **排序口径换了。** 名次按 `base`（存在率 × 回波形状）排，闸门只做资格判定与告警。旧口径 `score = base × (1-覆盖闸) × geo_factor` 把整张表压进 0.000–0.058，名次实际上由"哪条闸响了"决定；它作为 `score（旧乘法）` 保留在表里，只供对照。

3. **同时通过"几何可辨识 + 覆盖闸不触发"的有 3 条：`2023-09-21_103728`（覆盖闸 0.28）、`2023-09-21_101622`（覆盖闸 0.00）、`2023-09-21_124039`（覆盖闸 0.35）。** 其中 base 最高的是 `2023-09-21_103728`（B6，base 0.067，覆盖闸 0.28），但它的链只覆盖 6.8% 的帧。这一组是本轮"值得先看"的实际答案，仍不能证明有目标。

4. **`2023-09-21_110229` 的矛盾是本轮第二个主结论。** 它 base 排第 1（0.129），判读员刚把它判成 object；但几何闸给出 `variation_ratio=0.032`——平台在录音内移动 1.80 m，回波距离的 p5–p95 只变了 4 mm，池内固定物体给不出这种信号，更像固定距离的环状回波（池壁/混响）。两种读数并列保留，不强行统一。

5. **三条录音不能导出成数据集**（manifest 里没有任何 `paired_role`）：`2023-09-20_182317`（B2）、`2023-09-21_110049`（B4）、`2023-09-20_175000`（B15）。其中 182317 是 A 段之外 base 第二高的一条，挑之前先看 `split_role` 列。

6. **与 v1 相比 19 条上升、19 条下降、2 条持平**。升降来自两件事：v1 只做单帧形状统计、v2 加了存在率与连续性；以及 v1 用旧 "banded frame" 判据，看不见 3–6 行的细带（`100927` 因此从第 6 掉到第 17）。

## 2. 方法

### 2.1 数据与采样

- 40 条 approved developing recordings（`manifest-resolved.json`）；**全部 `--every 1` 逐帧**，每行 `sampling: 1`，名次之间可比。上一版前 10 名 every=1、其余 every=12，`track_too_short` 是采样伪影（12 帧间隔下最长链只有 3 帧），已作废。
- 幅面：128 beams × 780 或 441 rows；`range = WindowStart + row * (WindowLength/SamplesPerBeam)`，三条录音的 step 都在 0.00298 m/row。

### 2.2 三个量

1. **beam 覆盖**（`beam_coverage_p995`）：5×5 平滑后，帧内 ≥ p99.5 的像素触到的 beam 比例。不平滑的覆盖率测的是远场噪声增益（同一条录音 0.758 vs 0.290），不能用作闸门。`band_gate_frac` = 覆盖率 ≥ 0.45 的帧占比。
2. **链式轨迹**（`chain_candidates`）：按 `range` 的 1-D 最近邻贪心关联，门限 0.025 m/帧、最大间隔 240 帧；`track_len` 是最长链，`track_frac = track_len / 采样帧数`。
3. **三项几何闸**（`geo_gates`，复用 `tools/locate.py::fit_point` 的有界 LM）：
   - `bounds_active`：b/xy/z 任一撞界 ⇒ 不可辨识；
   - `holdout_p90`：按帧奇偶对半，一半拟合、另一半算残差（两折都做，取较差折），≤ 0.15 m 才算可辨识；
   - **距离-位移一致性**：平台在录音内位移 Δ、平均视线方向 u，固定物体必然 `range 变化 >= |Δ·u|`；实测 `range_span` < 0.5 × 下界 ⇒ `geo_fixed_object_impossible`。

### 2.3 base 与分档

```
presence    = track_len / n_frames_sampled
continuity  = 1 - jumps / (top1 步数)
compactness = clip((70 - beam_span_med) / (70 - 25))
smoothness  = clip((12 - step_med_px) / 10)
brightness  = clip((snr_med - 3) / 5)
base        = presence * (0.35*continuity + 0.35*compactness + 0.15*smoothness + 0.15*brightness)
geo_factor  = 1.00 可辨识且留出通过 / 0.70 留出残差过大或样本不足 / 0.50 参数撞界 / 0.35 距离变化低于固定物体下界
```

`presence` 是**乘性**前置条件："有回波"是"回波形状好"的前提。加成项曾把一个只覆盖 20/768 帧的碎片（`101622`）抬到榜首，所以形状分只有在存在率之上才有意义。

### 2.4 为什么不用乘性总分排名

旧口径把两条闸乘进分数，A/B 之外还要再乘一次，结果是 A 段 0 条、B 段全部挤在 0.000–0.058，`#1 182317`（base 0.128）排在 `#13 110049`（base 0.160）之前——名次由闸门标志决定，不再回答"回波像不像一个紧凑物体"。现在闸门只回答"够不够资格先看"，base 回答"哪条更像"。

## 3. A 段（推荐先看）

条件：`geo_ok` 且 `band_gate_frac < 0.45` 且 `track_frac ≥ 0.5`，按 base 降序。

**（空）** 见 §1 第 1 条：没有任何一条录音的连续回波覆盖 ≥ 50% 的帧。

退一步的读法：如果要先看一条，B 段第 1 名 `2023-09-21_110229` 的 base 最高；但它触发"距离变化不足下界"，且与判读员的 object 判读冲突（§1 第 4 条）。若只接受闸门全过的，看 `2023-09-21_103728`（B6）。

## 4. B 段（其余，按 base 降序）

最右列是触发的闸；`geo` 列是分档分数与原因；`v1` 是 v1 的名次（共 40 条）。

| # | recording | 类 | split_role | base | score（旧乘法） | presence | track_frac | 覆盖闸 | geo | v1 | 触发 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B1 | `2023-09-21_110229` | mortar_shell | 有 | 0.129 | 0.0451 | 0.130 | 0.130 | 0.00 | 0.35 range_variation_below_fixed_object_lower_bound | 1 | 几何闸：range_variation_below_fixed_object_lower_bound；距离变化不足下界的 50% |
| B2 | `2023-09-20_182317` | 100lbs_aircraft_bomb | 无 | 0.128 | 0.0583 | 0.128 | 0.128 | 0.54 | 1.00 ok | 14 | 覆盖闸：54% 帧覆盖 >= 0.45 |
| B3 | `2023-09-21_105856` | mortar_shell | 有 | 0.103 | 0.0517 | 0.114 | 0.114 | 0.00 | 0.50 parameters_at_bounds | 23 | 几何闸：parameters_at_bounds |
| B4 | `2023-09-21_110049` | mortar_shell | 无 | 0.073 | 0.0171 | 0.076 | 0.076 | 0.53 | 0.50 parameters_at_bounds | 34 | 覆盖闸：53% 帧覆盖 >= 0.45；几何闸：parameters_at_bounds |
| B5 | `2023-09-21_123500` | incindiary_grenade | 有 | 0.067 | 0.0241 | 0.069 | 0.069 | 0.28 | 0.50 parameters_at_bounds | 7 | 几何闸：parameters_at_bounds |
| B6 | `2023-09-21_103728` | mortar_shell | 有 | 0.067 | 0.0482 | 0.068 | 0.068 | 0.28 | 1.00 ok | 3 | 未触发任何闸（base 排序） |
| B7 | `2023-09-21_101131` | mortar_shell | 有 | 0.064 | 0.0125 | 0.065 | 0.065 | 0.44 | 0.35 range_variation_below_fixed_object_lower_bound | 9 | 几何闸：range_variation_below_fixed_object_lower_bound；距离变化不足下界的 50% |
| B8 | `2023-09-20_180506` | 100lbs_aircraft_bomb | 有 | 0.063 | 0.0121 | 0.068 | 0.068 | 0.81 | 1.00 ok | 24 | 覆盖闸：81% 帧覆盖 >= 0.45 |
| B9 | `2023-09-21_101840` | mortar_shell | 有 | 0.051 | 0.0251 | 0.052 | 0.052 | 0.01 | 0.50 parameters_at_bounds | 8 | 几何闸：parameters_at_bounds |
| B10 | `2023-09-21_105230` | mortar_shell | 有 | 0.045 | 0.0156 | 0.046 | 0.046 | 0.01 | 0.35 range_variation_below_fixed_object_lower_bound | 2 | 几何闸：range_variation_below_fixed_object_lower_bound；距离变化不足下界的 50% |
| B11 | `2023-09-20_180722` | 100lbs_aircraft_bomb | 有 | 0.040 | 0.0011 | 0.043 | 0.043 | 0.92 | 0.35 range_variation_below_fixed_object_lower_bound | 13 | 覆盖闸：92% 帧覆盖 >= 0.45；几何闸：range_variation_below_fixed_object_lower_bound；距离变化不足下界的 50% |
| B12 | `2023-09-21_102500` | mortar_shell | 有 | 0.036 | 0.0076 | 0.037 | 0.037 | 0.40 | 0.35 range_variation_below_fixed_object_lower_bound | 10 | 几何闸：range_variation_below_fixed_object_lower_bound；距离变化不足下界的 50% |
| B13 | `2023-09-21_120912` | incindiary_grenade | 有 | 0.035 | 0.0101 | 0.037 | 0.037 | 0.42 | 0.50 parameters_at_bounds | 5 | 几何闸：parameters_at_bounds |
| B14 | `2023-09-21_103927` | mortar_shell | 有 | 0.034 | 0.0085 | 0.034 | 0.034 | 0.28 | 0.35 range_variation_below_fixed_object_lower_bound | 4 | 几何闸：range_variation_below_fixed_object_lower_bound；距离变化不足下界的 50% |
| B15 | `2023-09-20_175000` | 100lbs_aircraft_bomb | 无 | 0.030 | 0.0103 | 0.030 | 0.030 | 0.02 | 0.35 range_variation_below_fixed_object_lower_bound | 15 | 几何闸：range_variation_below_fixed_object_lower_bound；距离变化不足下界的 50% |
| B16 | `2023-09-21_120653` | incindiary_grenade | 有 | 0.030 | 0.0086 | 0.031 | 0.031 | 0.42 | 0.50 parameters_at_bounds | 11 | 几何闸：parameters_at_bounds |
| B17 | `2023-09-21_100927` | mortar_shell | 有 | 0.028 | 0.0048 | 0.029 | 0.029 | 0.52 | 0.35 range_variation_below_fixed_object_lower_bound | 6 | 覆盖闸：52% 帧覆盖 >= 0.45；距离变化不足下界的 50% |
| B18 | `2023-09-20_174439` | 100lbs_aircraft_bomb | 有 | 0.026 | 0.0015 | 0.027 | 0.027 | 0.88 | 0.50 parameters_at_bounds | 25 | 覆盖闸：88% 帧覆盖 >= 0.45；几何闸：parameters_at_bounds |
| B19 | `2023-09-20_171105` | 100lbs_aircraft_bomb | 有 | 0.024 | 0.0008 | 0.027 | 0.027 | 0.91 | 0.35 range_variation_below_fixed_object_lower_bound | 39 | 覆盖闸：91% 帧覆盖 >= 0.45；几何闸：range_variation_below_fixed_object_lower_bound；距离变化不足下界的 50% |
| B20 | `2023-09-21_101622` | mortar_shell | 有 | 0.023 | 0.0232 | 0.026 | 0.026 | 0.00 | 1.00 ok | 30 | 未触发任何闸（base 排序） |
| B21 | `2023-09-21_110411` | mortar_shell | 有 | 0.023 | 0.0107 | 0.026 | 0.026 | 0.06 | 0.50 parameters_at_bounds | 27 | 几何闸：parameters_at_bounds |
| B22 | `2023-09-20_175506` | 100lbs_aircraft_bomb | 有 | 0.022 | 0.0008 | 0.023 | 0.023 | 0.92 | 0.50 parameters_at_bounds | 33 | 覆盖闸：92% 帧覆盖 >= 0.45；几何闸：parameters_at_bounds |
| B23 | `2023-09-21_105017` | mortar_shell | 有 | 0.020 | 0.0101 | 0.022 | 0.022 | 0.00 | 0.50 parameters_at_bounds | 21 | 几何闸：parameters_at_bounds |
| B24 | `2023-09-20_173329` | 100lbs_aircraft_bomb | 有 | 0.020 | 0.0081 | 0.021 | 0.021 | 0.19 | 0.50 fit_not_meaningful | 19 | 几何闸：fit_not_meaningful |
| B25 | `2023-09-20_175905` | 100lbs_aircraft_bomb | 有 | 0.019 | 0.0001 | 0.021 | 0.021 | 0.99 | 0.50 parameters_at_bounds | 28 | 覆盖闸：99% 帧覆盖 >= 0.45；几何闸：parameters_at_bounds |
| B26 | `2023-09-21_124039` | incindiary_grenade | 有 | 0.019 | 0.0121 | 0.023 | 0.023 | 0.35 | 1.00 ok | 36 | 未触发任何闸（base 排序） |
| B27 | `2023-09-21_125048` | incindiary_grenade | 有 | 0.018 | 0.0062 | 0.021 | 0.021 | 0.03 | 0.35 range_variation_below_fixed_object_lower_bound | 31 | 几何闸：range_variation_below_fixed_object_lower_bound；距离变化不足下界的 50% |
| B28 | `2023-09-21_123841` | incindiary_grenade | 有 | 0.017 | 0.0053 | 0.020 | 0.020 | 0.36 | 0.50 parameters_at_bounds | 32 | 几何闸：parameters_at_bounds |
| B29 | `2023-09-21_104749` | mortar_shell | 有 | 0.017 | 0.0043 | 0.018 | 0.018 | 0.47 | 0.50 parameters_at_bounds | 22 | 几何闸：parameters_at_bounds |
| B30 | `2023-09-20_173615` | 100lbs_aircraft_bomb | 有 | 0.015 | 0.0076 | 0.016 | 0.016 | 0.00 | 0.50 parameters_at_bounds | 17 | 几何闸：parameters_at_bounds |
| B31 | `2023-09-21_103140` | mortar_shell | 有 | 0.014 | 0.0072 | 0.016 | 0.016 | 0.00 | 0.50 parameters_at_bounds | 29 | 几何闸：parameters_at_bounds |
| B32 | `2023-09-21_121539` | incindiary_grenade | 有 | 0.014 | 0.0072 | 0.017 | 0.017 | 0.00 | 0.50 parameters_at_bounds | 35 | 几何闸：parameters_at_bounds |
| B33 | `2023-09-21_160551` | 100lbs_aircraft_bomb | 有 | 0.014 | 0.0049 | 0.017 | 0.017 | 0.32 | 0.50 fit_not_meaningful | 37 | 几何闸：fit_not_meaningful |
| B34 | `2023-09-21_121124` | incindiary_grenade | 有 | 0.014 | 0.0025 | 0.016 | 0.016 | 0.50 | 0.35 range_variation_below_fixed_object_lower_bound | 18 | 几何闸：range_variation_below_fixed_object_lower_bound；距离变化不足下界的 50% |
| B35 | `2023-09-20_181139` | 100lbs_aircraft_bomb | 有 | 0.014 | 0.0067 | 0.015 | 0.015 | 0.05 | 0.50 parameters_at_bounds | 12 | 几何闸：parameters_at_bounds |
| B36 | `2023-09-21_101416` | mortar_shell | 有 | 0.013 | 0.0030 | 0.016 | 0.016 | 0.56 | 0.50 parameters_at_bounds | 26 | 覆盖闸：56% 帧覆盖 >= 0.45；几何闸：parameters_at_bounds |
| B37 | `2023-09-21_122608` | incindiary_grenade | 有 | 0.013 | 0.0024 | 0.016 | 0.016 | 0.47 | 0.35 range_variation_below_fixed_object_lower_bound | 16 | 几何闸：range_variation_below_fixed_object_lower_bound；距离变化不足下界的 50% |
| B38 | `2023-09-21_124915` | incindiary_grenade | 有 | 0.013 | 0.0066 | 0.015 | 0.015 | 0.00 | 0.50 parameters_at_bounds | 40 | 几何闸：parameters_at_bounds |
| B39 | `2023-09-21_121327` | incindiary_grenade | 有 | 0.013 | 0.0031 | 0.015 | 0.015 | 0.52 | 0.50 parameters_at_bounds | 20 | 覆盖闸：52% 帧覆盖 >= 0.45；几何闸：parameters_at_bounds |
| B40 | `2023-09-21_122855` | incindiary_grenade | 有 | 0.013 | 0.0063 | 0.015 | 0.015 | 0.00 | 0.50 parameters_at_bounds | 38 | 几何闸：parameters_at_bounds |

`base` 全表范围 0.013–0.129（中位 0.023）；`cov_med` 中位 0.41。

## 5. 反例（必须留在表里）

- `2023-09-21_100927`（B 段第 17 名；base 0.028，旧乘法分 0.0048）：cov 中位 0.45，覆盖闸 0.52；轨迹 21/725，geo `range_variation_below_fixed_object_lower_bound`
  - b=0.283（撞界 False），留出 p90=0.026 m，平台位移 2.00 m，理论最小距离变化 0.36 m，实测 range 跨度 p5–p95 0.110 m（min–max 0.196，ratio 0.303）
  - 覆盖闸只压掉 52% 的帧，**不足以把它排除**——它的回波是贯穿扇面的细带，视觉上不是物体；这条留在表里就是要说明"闸门不是判决"。
- `2023-09-21_105230`（B 段第 10 名；base 0.045，旧乘法分 0.0156）：cov 中位 0.27，覆盖闸 0.01；轨迹 39/839，geo `range_variation_below_fixed_object_lower_bound`
  - b=0.3（撞界 True），留出 p90=0.0336 m，平台位移 2.03 m，理论最小距离变化 0.67 m，实测 range 跨度 p5–p95 0.278 m（min–max 0.287，ratio 0.412）
  - 上一轮被当作"2 cm 残差证明固定点"的例子；打开边界后 b 与 P_z 都撞界，留出 p90 只有几厘米——小残差但**不可辨识**，不能当作解出来的位置。
- `2023-09-21_110229`（B 段第 1 名；base 0.129，旧乘法分 0.0451）：cov 中位 0.31，覆盖闸 0.00；轨迹 69/533，geo `range_variation_below_fixed_object_lower_bound`
  - b=0.3（撞界 True），留出 p90=0.0453 m，平台位移 1.80 m，理论最小距离变化 0.11 m，实测 range 跨度 p5–p95 0.004 m（min–max 0.004，ratio 0.032）
  - 判读员判成 object，而 `variation_ratio=0.032`：平台移动 1.80 m，回波距离 p5–p95 只变 4 mm。数据侧另有两个近恒定距离簇（1.85 m 贯穿全程；1.03–1.17 m 出现在 f300–f550，每帧 3–5 个候选），montage 里 1.85 m 是画面底部那条横线、1.1 m 是中段的小亮块。**两种读数并列保留，不强行统一。**
- `2023-09-20_171105`（B 段第 19 名；base 0.024，旧乘法分 0.0008）：cov 中位 0.65，覆盖闸 0.91；轨迹 19/715，geo `range_variation_below_fixed_object_lower_bound`
  - b=0.3（撞界 True），留出 p90=0.0122 m，平台位移 1.99 m，理论最小距离变化 0.23 m，实测 range 跨度 p5–p95 0.009 m（min–max 0.012，ratio 0.04）
  - 亮带横跨 92–128 beams，覆盖闸 0.91；链被带的边缘反复打断，几何拟合残差远大于像元，任何"点"的说法都不成立。

## 6. 不能导出成数据集的录音（`split_role=无`）

manifest 里没有任何 `paired_role` 的录音可以**看**，但不能进 train/val 划分：

- `2023-09-20_182317`：B 段第 2 名，base 0.128（覆盖闸：54% 帧覆盖 >= 0.45）
- `2023-09-21_110049`：B 段第 4 名，base 0.073（覆盖闸：53% 帧覆盖 >= 0.45；几何闸：parameters_at_bounds）
- `2023-09-20_175000`：B 段第 15 名，base 0.030（几何闸：range_variation_below_fixed_object_lower_bound；距离变化不足下界的 50%）

## 7. 与 v1 的逐条升降

v1（`out/census/census.json`，已保留）按单帧 blob 形状 + "banded frame" 判据打分，看不见 3–6 行的细带；v2 加了存在率、链式连续性、三项几何闸，并把采样统一到 every=1。

- 上升 19 条、下降 19 条。升得最多的：`2023-09-21_110049` 34→4；`2023-09-21_105856` 23→3；`2023-09-20_171105` 39→19。
- 降得最多的：`2023-09-20_181139` 12→35；`2023-09-21_122608` 16→37；`2023-09-21_121327` 20→39。
- `2023-09-21_100927` 从 v1 第 6 掉到第 17：v1 的 "banded frame" 要求连续 ≥60 beams，它的细带只有 3–6 行；v2 的覆盖闸看得见它，几何闸又说距离变化不足。

## 8. 复现

```bash
# 全量 40 条，逐帧（约 4.5 min），写 out/census/census_v2.json + CENSUS-V2.md + top2/
python tools/census.py --every 1 --refine-top 0 --montage 2

# 单条复查（含 6 帧拼图）
python tools/census.py --only 2023-09-21_103728 --every 1 --montage 1
```

产物：`out/census/census_v2.json`（逐条含 `base/score_old/geo.*/split_role/sampling`）、`out/census/CENSUS-V2.md`（同一份表）、`out/census/top2/B01_*.png`、`B02_*.png`（base 前二名的 6 帧拼图，青框 = `compact` 的候选框）。

## 9. 限制与不回答的问题

- **没有 GT**：`base` 只表示"这条录音里的回波更像一个紧凑、连续、几何上说得通的回波"，不表示"这是 UXO"；`identity` 仍是 `unresolved`。
- **局部中位数背景会吃掉慢目标**（见 `docs/geometry-calibration.md` §6.2）：整段只转 0.32 圈，±10 帧内目标只挪 1–2 行；因此"残差低"不等于"没有目标"，反过来"候选少"也不等于"干净"。
- **几何闸是必要条件不是充分条件**：撞界只能说明"没解出来"，不能说明"不是固定物体"；距离-位移一致性只排除"固定物体"，不排除"移动的物体"。
- **A 段阈值（track_frac ≥ 0.5）没有被数据满足**，本报告没有为了凑出一段而放宽它；如果后续要放宽，应作为新口径重新登记，而不是改这一版的数字。

