# T-MESH · 3D 模型几何先验（engine/mesh_prior.py）

状态：可用（`--all --check` 全项通过，两次运行逐字节一致）。
产出物是 **candidate / pseudo-label 的边界先验**，不是 GT，也不是声学模型。

---

## 0. 这个模块回答什么、不回答什么

回答：某个 UXO（100lbs / incindiary / mortar_shell）在给定 **距离 r、方位 az、姿态 (yaw,pitch,roll)**
下，在声呐 (beam, row) 像素网格上**最多能占多大**——剪影掩膜、外接框、beam/row 跨度、面积。

不回答：

- **不模拟声学。** 无阴影（acoustic shadow）、无多径、无多次反射、无材质/入射角对回波强度的影响。
  剪影是几何占位（solid 的投影 = 阴影体），真实的蓝色高亮/黑尾往往只占其中一小块，面积不可当回波面积用。
- **不给唯一姿态。** 同一目标的剪影随姿态变化极大（见 §5：100lbs 在 r=1.26 m 下 beam 跨度 10.2–32.6 px、
  row 跨度 72.6–246.6 px）。任何单帧都不可能从剪影反推出姿态。所有输出带 `uniqueness: false`。
- **不用 `mesh_to_target`。** `DataSet/sonar_model_registration_consistency/mesh-registration.json` 里该字段
  是 `status: "HOLD: source-backed mesh_to_target unavailable"`、值为 `null`。本模块只用其中的
  **标称长度**（只按长轴做均匀缩放），并在 provenance 里注明 `mesh_to_target_used: false`。

---

## 1. 接口（BRIEF §4 T-MESH 契约）

```python
load_mesh(category: str) -> Mesh
    # Mesh.vertices  (M,3) float64 米，已按标称长度缩放、已转到规范系
    # Mesh.faces     (K,3) int     降采样后的三角形
    # Mesh.points    (P,3) float64 降采样点云（≤3000，供投影用）
    # Mesh.extent_m  (3,) 降采样点云的 AABB 尺度（米）

silhouette(mesh, range_m, az_deg, yaw_deg, pitch_deg, roll_deg, rec_meta) -> dict
    # 必有键：mask(np.bool_, (n_samples,n_beams)) / box_xyxy / beam_span_px /
    #         row_span_px / predicted_area_px / visible_frac
    # 诊断键：clipped, box_xyxy_unclipped, beam_span_cont_px, row_span_cont_px,
    #         range_min_m, range_max_m, pose_deg, raster, mask_sha256, grid,
    #         assumption, pose_convention, uniqueness(False)

plausible_sweep(mesh, range_m, az_deg, rec_meta, n_yaw=24, n_pitch=6, n_roll=6) -> list[dict]
    # 864 个姿态假设，每个含 yaw/pitch/roll、beam_span_px、row_span_px、
    # box_xyxy、hull_area_px、in_frame、backend="hull"
```

`category` 接受 manifest 值或模型名：`100lbs_aircraft_bomb`→`100lbs`、
`incindiary_grenade`→`incindiary`、`mortar_shell`→`mortar_shell`。
（`artillery_shell` 有模型但注册表无标称尺寸，故不提供，`load_mesh` 会明确报错。）

命令行：

```bash
python engine/mesh_prior.py --category mortar_shell --range 1.26 --az 10 --out out/prior_demo.json
python engine/mesh_prior.py --all --check                       # 断言 + 全量读数 → out/prior_check.json
python engine/mesh_prior.py --all --check --images tmp/mesh    # 另存剪影叠加图（只允许 tmp/mesh/ 下）
```

---

## 2. 单位、坐标系与像素映射（精确式子）

- 声呐系：`+x` 右舷、`+y` 下、`+z` 视线方向；方位 `az>0` 朝 `+x`。
- 波束：`beam = (n_beams-1)/2 + az/deg_per_beam`，`deg_per_beam = FOV/n_beams = 130°/128 = 1.015625°`。
- 距离：`row = (r - WindowStart)/(WindowLength/n_samples)`，`r = sqrt(x²+y²+z²)`（**透视**，非正交投影）。
- 投影对每个顶点独立做透视除法，所以一个 0.737 m 的物体在 1.26 m 处两端会有真实的近大远小。

### `n_samples` 逐录音不同（重要）

| recording | class_dir | 网格 (row×beam) | WindowStart | WindowLength | m/row |
|---|---|---|---|---|---|
| 2023-09-20_171105 | 100lbs_bomb | **780**×128 | 0.6949365 | 2.3263969 | 0.00298256 |
| 2023-09-21_120653 | 20lbs_incendiary | **441**×128 | 0.6951 | 1.3156 | 0.00298326 |
| 2023-09-21_100927 | 15cm_mortar | **441**×128 | 0.6949 | 1.3153 | 0.00298326 |

三者 m/row 几乎相同，但**行数差 1.77 倍**（FOV 窗口 2.33 m vs 1.32 m）。任何下游若硬编码
`(780,128)` 处理 incendiary/mortar 都会错位或越界。

`rec_meta` 解析顺序：**逐帧 `aris_frame_meta.csv`**（WindowStart/WindowLength 的唯一逐帧来源，
`aris_file_meta.yaml` 里这两个值是 0）→ `engine.geometry.header_of()`（T-GEOM 的审计表）→
BRIEF §1 常量兜底。无论用哪一档，都会与 geometry 的 header 比对并把结果写进
`rec_meta.geometry_crosscheck`（当前三条录音均 `agree`，ΔWindowStart ≤2e-4 m、ΔWindowLength ≤3.2e-4 m）。

---

## 3. 姿态约定（`POSE_CONVENTION`）

模型规范系：原点=AABB 中心，`+x`=长轴（PCA 主轴，符号确定化），`y/z` 为横截面两轴。

`R = R_right(pitch) · R_down(yaw) · B · R_xmodel(roll)`，其中 `B` 把模型 `(x,y,z)` 映到声呐
`(视线, 下, -右舷)`：

- `yaw=0` → 长轴沿视线（端视，range 方向拉长、beam 方向最窄）；
- `|yaw|=90` → 侧视（beam 方向最宽）；
- `pitch>0` → 抬头；`roll` 绕自身长轴自转（对回转体几乎无影响，对真实网格有 1–7 px 影响）。

**这台声呐看不到真值姿态。** 姿态只能来自情景假设（gantry 轨迹 L→R、tilt -22°、"躺在海底"等），
所以本模块只给"姿态假设下的可能范围"，不给单一答案。

---

## 4. 网格降采样（≤3000 点，且保住真实 extent）

算法（纯 numpy，无 cv2/scipy/skimage）：

1. 流式解析 OBJ：`v` 行取前 3 个 float（Metashape 会多带 RGB），`f` 行取首个索引、多边形扇形三角化。
2. 用**原始全部顶点**做 PCA 建规范系，按 `标称长度 / PCA长轴` 均匀缩放。
3. 面重心体素聚类：对 n∈[4,256] 二分，取"占用体素数 ≤ 2992"的最大 n；
   每个占用体素保留**离该体素均值最近**的那个面（不是保留位置索引——这个 bug 曾让 2976 个面塌缩到 194 个唯一点）。
4. 强制注入 6 个原始轴极值点 → `decimated_extent == raw_extent` 严格成立（`extent_preserved: true`）。
5. 输出 `sha256_points` / `sha256_faces` / `sha256_obj` 与原始顶点数/面数。

| model | 原始 v/f | 降采样 点/面 | 体素 n | 体素边长 | 长×横×横 (m) |
|---|---|---|---|---|---|
| 100lbs | 95144 / 190248 | 2982 / 2976 | 53 | 13.9 mm | 0.7370 × 0.2090 × 0.2296 |
| incindiary | 90053 / 179999 | 2951 / 2945 | 48 | 9.2 mm | 0.4420 × 0.1533 × 0.1225 |
| mortar_shell | 63168 / 126370 | 2938 / 2932 | 67 | 8.7 mm | 0.5800 × 0.1308 × 0.1222 |

**降采样误差实测**（同一位姿下，用全部 95k 点与 3000 点各投影一次，比较 footprint 四边，单位 px）：

| model | yaw=90 | yaw=45 | yaw=0 | 最大 |
|---|---|---|---|---|
| 100lbs | ≤0.13 | ≤0.16 | 0.00 | **0.158** |
| incindiary | ≤0.06 | ≤0.36 | ≤0.02 | **0.357** |
| mortar_shell | ≤0.37 | ≤0.10 | ≤0.01 | **0.368** |

即 30 倍降采样对框的影响 < 0.4 px（像素本身 3 mm/row、1.0°/beam），远小于姿态不确定性。

---

## 5. 已验证读数（`--all --check`，r=1.26 m，az=10°，姿态 yaw=90 侧视）

| model | beam_span_px | row_span_px | area_px | 端视 (yaw=0) b×r | sweep beam | sweep row |
|---|---|---|---|---|---|---|
| 100lbs | **34** | **80** | 2059 | 13 × 248 | 10.2–32.6 | 72.6–246.6 |
| incindiary | **21** | **43** | 805 | 7 × 149 | 6.0–20.2 | 41.5–150.3 |
| mortar_shell | **27** | **48** | 877 | 6 × 195 | 5.5–26.4 | 43.5–194.7 |

解析式核对（不受网格/降采样影响，用来验证投影本身）：
`2·atan(L/2 / r)/1.015625 + 1` → 0.737 m→33.1（实测 34）；0.442→20.6（实测 21）；0.58→26.5（实测 27）。
差 1 px 来自 3 mm/row 的像素化与"跨度=像素个数"的定义。

**0.2 m 直径 ≈ 67 rows 的判据**：用合成球（0.208 m，Fibonacci 20000 点）单独测投影，
得到 `row_span_px = 69.735`（期望 0.208/0.00298256 = 69.739，差 0.004 px）、`beam_span_px = 9.323`
（2·atan(0.104/1.26)=9.44°/1.015625=9.3 ✓），已作为 `sphere_0p208_row_span_64_72` 写进 `--check`。
**长条目标在侧视下 row 跨度大于直径是物理必然**：0.737 m 长条横放时两端比中心远 0.37 m，
两端贡献 ±0.37 m 的距离差，所以 100lbs 侧视是 80 rows 而不是 67——不是投影错，
而是"径向跨度=diameter"只对球/短目标成立。端视时反过来：row 跨度≈全长（248 rows）。

形状自查：用 `--images` 出图后逐张 `read_image` 看过 6 张（侧视/端视 × 3 类）：
侧视是带锥头/尾的实心长条（34×80），端视是沿 range 拉长的细条（13×248，近端更宽），
不是糊团也不是空白；`incindiary` 侧视是最规整的 21×43 矩形。

---

## 6. 姿态扫描（`plausible_sweep`）

24 yaw（0–345°，15° 步）× 6 pitch（±6/18/30°）× 6 roll（0–300°）= **864 个假设**。
`beam_span_px` / `row_span_px` 是"连续长度"（凸包口径），`box_xyxy` 是整数像素框。

| model | 全部 864 姿态 envelope (x0,y0,x1,y1) | 仅 \|yaw\|=90（36 个） |
|---|---|---|
| 100lbs | [56, 65, 92, 315]（36×250） | [56, 150, 91, 237]（35×87） |
| incindiary | [63, 113, 85, 267]（22×154） | [63, 162, 85, 224]（22×62） |
| mortar_shell | [59, 88, 88, 291]（29×203） | [59, 163, 88, 223]（29×60） |

用法建议：**姿态未知时 envelope 几乎不能约束 row**（100lbs 跨 250 行 = 0.75 m）。
只有当情景能排除端视（例如目标躺在海底、长轴大致水平且垂直于波束扇面）才用
\|yaw\|=90 那一档，row 约束立刻收到 62–87 px。

---

## 7. 输出字段语义

- `mask`：投影阴影（solid）在 (n_samples, n_beams) 上的填充，bool。
  实现：点云 splat → **逐 beam 列在 range 方向闭包** → 3×3 闭运算 → 逐行闭包。
  逐列闭包等价于"该波束内目标占的 range 区间连续"，对凸体成立（这些 UXO 成立），
  这是让 3000 点云不出现筛孔的关键；不引入额外沿 range 的膨胀。
- `box_xyxy`：`[x0,y0,x1,y1]` 像素**边界**（x1/y1 为开区间），由 `mask` 非零行列得到。
- `visible_frac`：`框内面积 / 投影总面积`。目标被 WindowStart/WindowEnd 或方位 FOV 截断时 <1，
  此时 `clipped: true`、`box_xyxy_unclipped` 给出未裁剪框，**不要**把 `beam_span_px` 当真实跨度。
- `predicted_area_px`：框内像素数（阴影面积，不是回波面积，见 §0）。

---

## 8. 复现

```bash
cd /mnt/d/agent_workspace/水下/声呐目标检测_workflow/sonar_llm_annotation
PY="/mnt/c/Users/ASUS/AppData/Local/Programs/Python/Python312/python.exe"

# 1) 断言 + 全量读数（7 项 check 全 true）
"$PY" engine/mesh_prior.py --all --check
#    → out/prior_check.json   sha256=516ad4f3279e8065ce50a73e5615e18ecba10378c2392ba03661da59d8ff31f4

# 2) BRIEF 的单类别示例
"$PY" engine/mesh_prior.py --category mortar_shell --range 1.26 --az 10 --out out/prior_demo.json
#    → out/prior_demo.json    sha256=c3806b2f53f2902e66809e1125dd5a9b10e38a0f4f179a49c44070a035f5ed42

# 3) 剪影图（只写 tmp/mesh/）
"$PY" engine/mesh_prior.py --all --check --images tmp/mesh
```

`--check` 断言的 7 项：`extent_preserved_all`、`100lbs_broadside_beam_span_30_36`、
`100lbs_broadside_row_span_60_82`、`mask_nonempty_all`、`no_uniqueness_claim`、
`decimation_footprint_le_1px`、`mask_reproducible`（同进程内重算掩膜，sha256 必须相同）。
**两次独立运行 `--all --check` 的 JSON 逐字节一致**（同一 sha256，已实测）。

---

## 9. 已知偏差与未解决项

1. **只按长轴缩放。** 注册表只给标称长度，故横截面完全取自网格比例：

   | model | 网格横向 (m) | 标称直径 (m) | 偏差 |
   |---|---|---|---|
   | 100lbs | 0.209 / 0.230 | 0.208 | +0.5% / +10% |
   | incindiary | 0.153 / 0.123 | 0.127 | **+21% / -3%** |
   | mortar_shell | 0.131 / 0.122 | 0.120 | +9% / +2% |

   → incindiary 的 beam 跨度可能系统性偏宽约 20%（21 px 里约 4 px）。
   等 `mesh_to_target` 解 HOLD 后应改用真标定；在那之前不要用本模块判定"目标比预期宽/窄"。
2. **网格比例来自摄影测量网格本身**，含 Metashape 的缩放/稠密重建误差；`artillery_shell` 无标称尺寸。
3. **剪影是阴影体，不是可见面。** 真实回波由入射角、材质、海底底质决定，可能只覆盖剪影的一小部分，
   也可能因多径出现在剪影之外。本模块的框应作为**候选框的上界**，不是预测框。
4. **姿态假设不完整。** 864 个离散姿态覆盖 ±30° pitch、全 roll、15° yaw 步进；真实姿态可能落在网格之间
   （剪影连续性保证误差 ~1 px 量级，但未做量化）。没有"躺海底/半埋"这类约束建模。
5. **不是"范围"而是"上界"。** 本模块从不说"目标一定在这个框里"，只说"若姿态在假设集合内，则不会超出此包络"。
6. `engine.geometry`（T-GEOM）就绪后已接入交叉校验；若 geometry 的审计表与逐帧 CSV 未来出现分歧，
   `geometry_crosscheck.status` 会变成 `differ`，此时以 CSV 为准并应上报。
