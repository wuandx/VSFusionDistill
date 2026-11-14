# 声呐 LLM 辅助标注 · 独立路线 BRIEF

> 这是一条**独立线**。主 Agent 的目录（`tools/`、`DataSet/`、`复现/`、`experiment/`、`handoff.md`、8765 服务）**只读**。
> 本线所有产物只写在 `sonar_llm_annotation/` 下。

## 0. 目标

用「3D 模型 + 声呐基础映射模型」生成候选框，用**视觉语言模型（我们自己的 Agent）**逐帧审视、修订、判定，
把未标注的声呐图像变成可交给人快速验收的**候选标注**（candidate / pseudo-label）。

**不是**正式 GT。任何产物都不得写成 GT、training-ready 或新 split。人工验收仍由用户完成。

## 1. 数据事实（已核实，不要重新猜）

原始录音根目录：`D:\pby\uxo-full\extracted\recordings\<class_dir>\<recording>\`

| 内容 | 路径 | 说明 |
|---|---|---|
| 声呐原始帧 | `aris_raw\<frame:04d>.pgm` | P5 灰度，**宽=128 beams，高=距离采样数**。**高度逐录音不同**：`2023-09-20_171105` 是 **780**，`2023-09-21_120653` / `2023-09-21_100927` 是 **441**（实测 PGM 头，见 §1.3）。任何代码都不得硬编码 780 |
| 声呐扇形图 | `aris_polar\` | 该录音为空，不可用 |
| 逐帧元数据 | `aris_frame_meta.csv` | 按 `FrameIndex` 索引 |
| 文件头元数据 | `aris_file_meta.yaml` | `NumRawBeams`=128（三条录音一致）；`SamplesPerChannel` 与上表同，逐录音读 |
| 目标真三维位置 | `gantry.csv` | `aris_frame_idx,x,y,z`（米） |
| 相机标注 | `labels\<frame>.json` | LabelMe，与本线无关 |

`class_dir`：`100lbs_bomb` / `20lbs_incendiary` / `15cm_mortar`；另有 `100lbs_bomb_(floor)`（录音 `2023-09-21_160551`）。

类别值（manifest 口径）：`100lbs_aircraft_bomb` / `incindiary_grenade` / `mortar_shell`。

允许开发录音清单（**唯一权威**）：`DataSet/camera_temporal_all/manifest-resolved.json` → `items[]`，
字段 `sample`（`<recording>_<frame:04d>`）、`recording`、`aris_frame`、`category`、`paired_role`。
只使用其中 `paired_role ∈ {train,val,val_id}` 的身份；**不碰 test**。

### 本轮选定的 3 条录音（每类 1 条）

| 类别 | recording | class_dir | 帧数 |
|---|---|---|---|
| 100lbs_aircraft_bomb | `2023-09-20_171105` | `100lbs_bomb` | 715 |
| incindiary_grenade | `2023-09-21_120653` | `20lbs_incendiary` | 771 |
| mortar_shell | `2023-09-21_100927` | `15cm_mortar` | 725 |

### 3D 模型与标称尺寸

`related_work/sonar-projection-audit-assets/data_export_3dmodels/3d_models/`：
`100lbs.obj` / `incindiary.obj` / `mortar_shell.obj` / `artillery_shell.obj`。

标称尺寸登记（只读）：`DataSet/sonar_model_registration_consistency/mesh-registration.json`
（100lbs: length 0.737 m, diameter 0.208 m）。**不要**使用该文件里的 `mesh_to_target`（为空/HOLD）。

标定链（只读）：`related_work/sonar-projection-audit-assets/calibration__transforms.yaml`
含 `setup/portal_crane → setup/ar3 → setup/aris → setup/sonar` 的平移+四元数。
`setup/sonar` 相对 `setup/aris` 平移 `x=-0.108725`，四元数 `(0.5,0.5,0.5,0.5)`。

## 2. 已核实的可行性证据（不要再重复验证，直接接上）

录音 `2023-09-20_171105` 帧 622：
- 回波：`thr=p99=47`，连通域 beam 质心 66.0、row 质心 177.6，beam 跨度 [14,113]，row 跨度 [140,266]。
- gantry 目标 `(0.165, 0.9995, -0.75)`，`|p|=1.2604 m`。
- `WindowStart=0.6949`、`WindowLength=2.3264`、`SamplesPerBeam=780` →
  `row = (range - WS) / (WL/780)` → 预测 row **189.6**，与回波质心 177.6 相差 12 行（≈3.6 cm）**✓ 落在回波上**。
- 方位：FOV 取 130°、128 beams → 1.0156°/beam。`atan2(±x,z)` 给 beam 74.06 / 53.94，回波质心 66 居中，
  **单帧无法定符号**，必须用跨帧轨迹定标（见 §4 任务 T-GEOM）。

结论：**gantry 目标位置 + 声呐位姿 + range/beam 映射可以预测回波位置**，无需解决主线的相机注册。

### 2.1 更正（Lead，2026-11-12 02:36）：§2 的判据是巧合，几何模型要改

新证据（`tmp/lead_morph.py`、`tmp/lead_diag.py`、`tmp/lead_geom_hypothesis.py` 可复现）：

1. **亮弧是静态的**：bomb 录音 4 帧 |p| 从 1.087→2.303 m（若按 §2 假设，回波应移动 531 行），
   实测亮弧几乎不动。时域中位数图显示弧脊线恒定在 row 182–200。
   → §2 里「帧 622 预测 row 189.6 落在残差 12 行内」是**巧合**，因为该帧 |p|=1.260 恰好接近真实 range。
   **不得**再以单帧吻合作为映射正确的证据。

2. **gantry 轨迹是一个圆**（代数圆拟合，715/771/725 点）：

   | recording | center (x,y) | R (m) | 残差中位 | z |
   |---|---|---|---|---|
   | 2023-09-20_171105 | (1.207, 1.496) | 1.2121 | 11.6 mm | 恒 −0.7500 |
   | 2023-09-21_120653 | (1.195, 1.451) | 1.1713 | 16.9 mm | 恒 −0.7500 |
   | 2023-09-21_100927 | (1.207, 1.500) | 1.2157 | 11.5 mm | 恒 −0.7500 |

   → 目标绕着竖直轴做圆周运动（转台/旋转吊臂），不是被任意摆放。

3. **观测弧顶行 ≈ 圆周半径**：bomb 弧顶 row≈170 → `range = 0.6949365 + 170×0.00298256 = 1.202 m`，
   而 R=1.2121 m；行残差 ≈3 行（9 mm）。若声呐在 z=0、目标在 z=−0.75，斜距应为
   `√(1.212²+0.75²)=1.42 m`→row 243，与观测差 73 行。
   → 声呐应在**圆周圆心附近、与目标等高 z≈−0.75**，range 天然近似恒定。这解释了亮弧为何不动。

4. **方位确实在扫动**：`corr(绕圆心方位角, 观测弧顶 beam) = −0.818`(bomb) / −0.590(grenade) / −0.484(mortar)，n=40。
   弧顶 beam 实测 span：bomb 44.2–72.4、grenade 48.0–79.3、mortar 44.0–85.0。

**因此正确的求解方式改成「用轨迹反解声呐位姿」**：
未知量 = 声呐位置 (3) + 朝向/约定（少量离散+连续参数），观测量 = 逐帧 (apex_beam, apex_row)，
约束 = 目标在已知圆周上运动。几百帧约束 4–6 个未知量，是超定且可检的。
残差若收敛到个位数行/列，说明模型成立，可用于预测；若不收敛，如实报告并放弃该假设。

**仍然成立**：§2 的帧头常量、分辨率 0.00298256 m/sample、以及「图像可判读」的目视结论。
**作废**：把 gantry xyz 直接当目标-声呐矢量的做法；把 |p| 当 range 的做法。

### 2.2 第二次更正（Lead，2026-11-12 02:39）：§2.1 也错了；gantry 不可用于声呐定位

`tmp/lead_periodicity.py`、`tmp/lead_pred_probe.py` 可复现：

1. **亮弧 100% 帧存在**（715/715、771/771、725/725），且**横向占 92–128 / 128 beams**
   （bomb 中位 116、grenade 126、mortar 128）。0.737 m 目标在 1.2 m 处、FOV 取 130° 时最多占 33 beams。
   → 亮弧不是"一个目标体"，它填满整个扇面。
2. **整条录音累计只转 0.32–0.36 圈**（gantry 方位角 unwrap），不是 360° 环扫。
3. **去静态后远场是纯噪声**：对 6 帧（|p| = 1.02/1.08/1.21/1.52/1.95/2.34 m），
   在 `row = (|p|−WS)/RES` 附近 ±60 行做 `frame − temporal_median` 后观察，
   |p| ≥ 1.52 m（row ≥ 276）的区域没有可辨目标回波，只有斑点噪声。
   → **`|p|`→row 的假设不成立**（它预测 531 行扫动，实测 ≈ 0）。

**因此：`gantry.csv` 不能用来预测声呐回波位置。** 最可能是光学相机的轨道龙门（半径 1.21 m、等高 z=−0.75、
只走 1/3 圈），与声呐无关，也可能只是转台。**不要**再用它做 range/bearing 预测。

4. **FOV=130° 是假设，不是测量**，且它显然与观测矛盾：若取 130°、要让 0.737 m 目标占 116 beams，
   需要 r = 0.22 m，落在窗口起点 0.695 m 之内（不可能）。
5. **关键退化关系**：径向厚度只由物理尺寸和距离分辨率决定（`rows = D/0.00298256`，与 range、FOV 无关）；
   方位宽度满足 `beams = 2·atan(L/2r)/θ · 128`。**一个方程两个未知量 (r, θ)，单视图不可解。**
   → 任何"从单帧反推绝对距离"的做法都是不成立的，不得声称解出。

**本线因此把几何降到次要地位，明确降级：**
- 仍可用且精确：`row ↔ range`（`range = WS + row·RES`）、`row` 向的米制标尺、每录音帧号集合、帧头常量。
- **不可用**：绝对 range、绝对方位角、FOV、目标姿态、gantry 定位。
- 3D 模型的贡献降为：**形状/长宽比先验** + 给视觉模型的参考剪影（按假定 (r,θ) 渲染，必须显式标注为假设）。
- 标注主证据改为：**图像本身**（时域静态抑制 + 局部 SNR + 连通域 + 跨帧持续性）+ **VLM 判读**。

**待标注对象的口径也据此明确**：本线标注的是「扇面内占优的、时域稳定的、紧凑的高 SNR 回波结构」——
即人在这种图上会去框的那个东西；它是否等于物理目标，作为 `identity: unresolved` 字段如实记录，不冒充。

## 3. 目录与写权限（严格）

```
sonar_llm_annotation/
  BRIEF.md        <-- 本文件（Lead 维护，只读）
  engine/         geometry.py echo.py mesh_prior.py cards.py  ...按任务分文件
  out/            <recording>/proposals.jsonl, cards/, judgments/, calibration.json
  review/         审阅页与服务
  docs/           证据与报告
  tmp/            草稿
```

各任务只写自己声明的文件；**不要**改别人正在写的文件，需要改接口先报告 Lead。

## 4. 任务与接口契约

### T-GEOM — `engine/geometry.py` + `engine/echo.py`

**geometry.py**
```python
REPO: Path                      # 项目根，脚本内部解析，不用命令行传绝对路径
RECORDINGS: dict[str, RecordingSpec]   # 见 §1 表
def load_recording(recording: str) -> Recording
class Recording:
    spec; n_frames: int
    def frame(self, f: int) -> FrameGeom
class FrameGeom:
    recording; frame; category
    def predict(self) -> dict
      # {"beam": float, "row": float, "range_m": float, "az_deg": float,
      #  "target_xyz_m": [x,y,z], "in_window": bool, "convention": str}
def beam_angle_deg(i) -> float      # beam 索引 → 相对声呐正向的方位角
def row_range_m(j) -> float         # row 索引 → 距离
```
要求：
1. 用 YAML 标定链 + `SonarPan/Tilt/Roll` 建立正确的变换，**不要**假定轴约定正确后就冻结：
   对候选约定（旋转顺序 × 方位符号 × FOV/偏置）在**整条录音**上做定标，
   判据 = `predict()` 的 (beam,row) 与 `echo.detect()` 提取的回波主连通域质心的残差，
   跨帧中位数最小、且**跨帧位移方向相关性**为正。把胜出约定与全部候选读数写进
   `out/calibration.json`（含 `n_frames`、每约定 `median_abs_beam_err`、`median_abs_row_err`、`sign_of_motion_corr`）。
2. 只在 `in_window` 为真时给预测；越界如实返回 `in_window: false`，**不要外推**成"没目标"。
3. 记录每条录音 `NumRawBeams`、`WindowStart/Length`、`SamplesPerBeam`，不同录音可能不同。

**echo.py**
```python
def detect(img: np.ndarray, predicted: dict | None, **kw) -> list[Blob]
# Blob = {"box_xyxy":[x0,y0,x1,y1], "area":int, "peak":int, "mean":float, "snr":float,
#         "centroid":[x,y], "n_components_merged":int, "rank":int}
def local_background(img, k=31) -> np.ndarray   # 不用 scipy，自己用 numpy
def label_numpy(mask) -> (labels, n)            # 自己实现连通域（4/8 邻接）
```
要求：
1. 纯 numpy + PIL + yaml，**不要** import cv2/scipy/skimage（Windows python 没有）。
2. 背景估计用局部窗（rolling quantile 或 盒滤波近似），阈值用相对 SNR，不用全图固定阈值。
3. 输出按 snr 降序；`rank=0` 为主要候选。`box_xyxy` 用像素边缘坐标，允许超界但须附 `clipped` 字段。
4. 必须在**同一帧**上稳定可复现（同参数两次运行输出逐字节相同）。

CLI（自检用）：
```
python engine/geometry.py --recording 2023-09-20_171105 --frames 622,700,715
python engine/echo.py --recording 2023-09-20_171105 --frames 622,700
```

### T-MESH — `engine/mesh_prior.py`

```python
def load_mesh(category: str) -> Mesh          # category 用 manifest 值
# Mesh: vertices(np.float64 Nx3, 单位米，已按标称长度归一), faces(int Mx3), extent_m
def silhouette(mesh, range_m, az_deg, yaw_deg, pitch_deg, roll_deg, rec_meta) -> dict
# {"mask": np.bool_ (780,128), "box_xyxy": [...], "beam_span_px": float,
#  "row_span_px": float, "predicted_area_px": int, "visible_frac": float}
def plausible_sweep(mesh, range_m, az_deg, rec_meta, n_yaw=24, n_pitch=6, n_roll=6) -> list[dict]
```
要求：
1. OBJ 很大（10–20 MB，9.5 万顶点）。加载时按面采样/顶点去重降采样到 ≤ 3000 点，**保留最终 extent**；
   记录原始顶点/面数与降采样后数目，二者 hash 独立存证。
2. 正交近似：range 1–3 m、目标 0.2–0.75 m，先用透视投影（FOV 130°），把顶点投影到 (az, range)，
   再映射到 (beam,row) 像素，光栅化凸包/三角形填充得到 mask。**不要**做声学阴影/多径模拟。
3. 只用于"可能的框范围"，**不要**声称某姿态是唯一解。输出必须带 `pose_convention` 与 `assumption` 字段。
4. 需要 `rec_meta`（NumRawBeams/Window*/SamplesPerBeam）才能落在同一像素网格：从 `geometry.load_recording` 取。

CLI：
```
python engine/mesh_prior.py --category mortar_shell --range 1.26 --az 10 --out out/prior_demo.json
python engine/mesh_prior.py --all --check     # 三类各跑一次，打印 extent/像素跨度
```

### 统一记录格式（全线路唯一脊柱，勿改字段名）

```json
{
  "sample": "2023-09-20_171105_0622",
  "recording": "2023-09-20_171105",
  "category": "100lbs_aircraft_bomb",
  "aris_frame": 622,
  "image": {"path": "...", "width": 128, "height": 780, "sha256": "..."},
  "predicted": {"beam": 74.06, "row": 189.6, "range_m": 1.2604, "az_deg": 10.22,
                "in_window": true, "convention": "..."},
  "echo": {"blobs": [{"box_xyxy": [..], "area": 0, "peak": 0, "mean": 0.0, "snr": 0.0,
                      "centroid": [0.0, 0.0], "n_components_merged": 1, "rank": 0,
                      "clipped": false}], "params": {}},
  "prior": {"model": "100lbs", "length_m": 0.737, "diameter_m": 0.208,
            "sweep": [{"yaw_deg": 0, "beam_span_px": 0.0, "row_span_px": 0.0, "box_xyxy": [..]}]},
  "candidate": {"box_xyxy": [0.0, 0.0, 0.0, 0.0], "source": "echo_primary+prior",
                "score": 0.0, "notes": ""},
  "provenance": {"engine_version": "v0", "inputs_sha256": {}, "params": {}}
}
```

`frame_data`（给 `cards.render`）就是上面这条记录，外加可选 `"img": numpy.ndarray`（已解码的原始灰度，
避免重复读盘）与 `"prior_masks": [np.bool_ (780,128)]`。

### T-CARDS — `engine/cards.py` + `docs/judgment-protocol.md`

**卡片**：给视觉模型看的一张 PNG，固定版式：
`左：原始帧全图（带预测十字 + 候选框）｜中：候选框 2× 放大裁切（带框）｜右：2–3 个模型剪影叠加（不同姿态）`
底部一行写明：`sample / 类别 / 距离 / 候选来源 / 版本`。

```python
def render(sample: str, frame_data: dict, out_path: Path, scale=2) -> Path
```
要求：
1. 灰度用**稳健拉伸**（p5–p99.5）+ `gain` 可选 1/3/5×，否则回波看不出来。
2. 裁切必须包含回波与框，宽高比固定；框线 2 px，颜色可辨（不用红绿配对以免色弱）。
3. 不改像素内容，不锐化、不描边，避免制造假边界。
4. `docs/judgment-protocol.md` 写清判定协议：什么算"目标存在"、什么算"框住本体"、
   哪些是支架/多径/阴影必须排除、什么时候必须答 `uncertain`。
   **框规则沿用项目既有口径**：框围目标本体，含可确认的尾翼与端部，不包支架、阴影或多径。

### T-REVIEW — `review/`（独立端口 8771）

一个本地审阅页：左侧录音/类别统计，中间原图 + 框（可拖动/缩放/重画），
保存 accept / revise / uncertain / reject，落盘 `out/<recording>/reviews.jsonl`（追加写，带 hash 与时间）。
导出 `out/export.json`。**不要**复用 8765 服务的状态或端口；不要读它的 `reviews.lock`。

## 5. 工程规则

1. Python 用 `C:\Users\ASUS\AppData\Local\Programs\Python\Python312\python.exe`（有 numpy/PIL/yaml）。
2. **禁止**在命令行里传含中文的 Windows 绝对路径（`wsl` 工具会改写路径）。
   脚本内部用 `Path(__file__).resolve().parents[1]` 定位 REPO。
3. 所有 JSON：`ensure_ascii=False`, `indent=2`, `allow_nan=False`。
4. 只读访问 `D:\pby\...` 与主 Agent 目录；不写、不删、不改 mtime。
5. 每一步产物带输入 hash（sha256）与参数，便于复核。
6. 失败要留档并如实报告（`status: failed` + 原因），不要静默重试到"看起来成功"。
7. 不确定就写 `unknown`，不要用猜测填补。
