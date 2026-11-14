# sonarllm — 用大模型辅助标注声呐图像

> 输出定性：**candidate / pseudo-label**。不是 GT，不是 training-ready。
> 声呐侧正式 GT 状态仍为 **HOLD**。

## 为什么要有这个东西

你的痛点是"不想手标"。常见的做法（把大模型接进标注网页，让它直接吐框）在这批声呐图上会**悄悄标错**，原因是这条数据有个陷阱：

扇面里最亮、最显眼的那条**贯穿左右的大亮弧**，实测不是目标。

| 类 | 标称长度 | 该弧的横向角宽 | 该弧的径向厚度 |
|---|---|---|---|
| 100lbs_bomb | 0.737 m | 125.0 beams | 0.333 m |
| incendiary | 0.442 m | 104.5 beams | 0.325 m |
| mortar_shell | ~0.35 m | 113.5 beams | 0.321 m |

三类目标的尺寸差近 4 倍，而这条弧的角宽和厚度几乎不变（跨三条不同日期的录音只差 ~1%）。**尺寸不随目标变的回波，不是目标**——它是类无关结构（转台/支架/罐壁一类）。

所以"找最大最亮的连通域当目标"会把结构标成炸弹。这种错不会报错，只会静默污染数据集。本工具的全部设计都是为了不犯这个错。

另外一条同样重要的事实（原项目 `aodet/datasets/converters/uxo_to_paired.py` 第 35-38 行原文）：

> `Sonar ground-truth boxes do not exist; they are produced later by the pose-based projection tool (F2 TODO 14.2)`

也就是说，仓库里 `sonar.json` 的框是**相机框经位姿投影算出来的**，不是人标的声呐真值。因此 `AP50=0.40` 这类读数评的是"能否复现投影"，不是"能否看声呐"。

## 管线

```
engine  (纯 numpy 回波检测)      -> out/<recording>/proposals.jsonl
cards   (三栏判读卡 PNG)          -> out/cards/<sample>.png
judge   (任何能看图的模型)        -> out/<recording>/judgments/<sample>.json
review  (人工复核网页, 8771)      -> out/<recording>/reviews.jsonl
dataset (按既有 paired_role 打包) -> out/dataset/{images,labels}/...
```

每一环都是**独立的文件契约**，任何一环可以被人替换、被重跑、被审计。

## 判读协议：为什么不让模型直接吐框

参考了 BKRC_ChatLabel（`pip install bkrc-chatlabel`）那类工具的形态：拖图进网页 → 模型输出 `[{"label":..., "bbox_2d":[...]}]` → 渲染预览 → 导出 YOLO。它有两个值得吸收的点，我拿过来了：

1. **两级分工**：轻的负责快（这里是 numpy 引擎，毫秒级），重的负责准（这里是 VLM 判读）。不让大模型做它不擅长的像素级定位。
2. **坐标与导出标准化**：标注是数据资产，导出必须落到 YOLO/COCO 这类通用格式，且划分要能追溯。

但它有一个在这个场景下会出事的设计：**模型直接产出最终框**。本工具反过来，把判定拆成"证据卡 + 结构化 JSON"：

- 引擎只负责**把证据摆清楚**（全帧 / 6× 裁切 / 尺度参考，外加 provenance 行）；
- 判读员只负责**看图说结论**（`verdict` / `shape` / `box` / `reason` / `confidence`）；
- 两者之间没有 API 依赖——任何能读图的模型（DSH teammate、Claude、GPT、本地 VLM、甚至人）都能当判读员，判定可留痕、可复算、可换模型重跑。

`verdict` 的取值刻意包含 `structure` 和 `empty`，而不是只有"有目标/没目标"：**允许模型说"这只是结构"**，这一点决定了工具会不会污染数据。

## 用法

```bash
# 总览
python -m sonarllm status

# 1) 给判读员派活（生成清单 + 判读说明）
python -m sonarllm manifest --recording 2023-09-20_171105

# 2) 判读员逐张 read_image 看图，写 out/<rec>/judgments/<sample>.json
#    （schema 见下）

# 3) 校验：JSON 合法性 + 图与结论是否对得上（card_sha256）
python -m sonarllm check --recording 2023-09-20_171105

# 4) 人工复核
python -m sonarllm serve --port 8771

# 5) 导出
python -m sonarllm export --dst out/dataset
```

判定 JSON 例子：

```json
{
  "sample": "2023-09-20_171105_0622",
  "verdict": "structure",
  "shape": "short_arc",
  "box": null,
  "discrete_object_present": false,
  "structure_present": true,
  "structure_overlap": 0.95,
  "reason": "亮带自左下连续探到右侧边缘，沿距离方向厚度均匀，无离散边界",
  "confidence": 0.7,
  "judge_model": "dsv4-flash",
  "card_sha256": "..."
}
```

## 导出时守的三条规矩

写在 `sonarllm/dataset.py` 里，不只是文档：

1. **不新建划分**：划分只从 `DataSet/camera_temporal_all/manifest-resolved.json` 的 `paired_role` 取；同一条录音若出现多个 role（说明不是录音级划分），**拒绝导出**并在 `provenance.json` 里记原因。
2. **不冒充 GT**：每个导出目录带 `provenance.json`，写 `candidate_only_not_training_ready: true` 和声呐 GT 的实际状态。
3. **只导出人确认过的框**：`accept` 取 `final_box`，`revise` 需带 `final_box`，`reject`/`skip` 不导出。

## 已知边界

- 单张声呐图**解不出绝对距离与 FOV**：`beams = 2·atan(L/2r)/θ_rad·128` 是一个方程两个未知量。由实测 + 采样窗硬约束只能得到 `θ ∈ [15.4°, 67°]`（130° 被排除）。任何声称给出绝对 range 的输出都是不可信的。
- `gantry.csv` 不能用于声呐定位：它是圆周轨道（圆拟合残差 11-17 mm，z 恒为 −0.7500），不是目标位姿。
- 精确可用的只有 `range_m = 0.6949365139007568 + row × 0.00298256`（径向标尺）与帧号集合。
- 详见 `../docs/FINDINGS.md`。
