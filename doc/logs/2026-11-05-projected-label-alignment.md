# 投影标注能不能当 GT：对齐实测与口径裁定（2026-11-05）

## 起因

本数据集（UXO 声呐-相机配对）的声呐标注有两种来源，写在 `sonar.json` 的
`source` 字段里：

- `blob`：程序在声呐图上检出了可见回波，框画在那团回波上；
- `projected`：声呐图上没检出回波，用相机看到的目标位置经标定投影过来，硬画一个框。

全部 11,558 个框里 **46.4% 是 projected**（train 3,655 / 7,960；val 372 / 900；
test 476 / 900；val_id 863 / 1,798）。

2026-11-05 上午曾裁定"对外主口径用 all（含 projected）"，理由是"两篇同数据集论文
都是每帧都有框，all 才同口径"。当天下午实测对齐后**撤回**，本文记录证据。

## 测法

对每个框，取框窗口内最亮的连通区域，量它的中心到框中心的距离（像素）。
判据：如果投影框是真的把"目标在声呐图上该出现的位置"标对了，那亮回波应当落在框内、
中心距应当接近 0（与 blob 框处于同一量级）。

工具：`tools/alignment_check.py`、`tools/session_offset.py`、`tools/echo_demo.py`
（后者渲染 `results/echo_demo.png`，同一场次相邻两帧的 blob / projected 对照图）。

## 结果

| 标注来源 | 框数 | 框到亮回波中心距（中位） | 框宽（中位） | 偏移 > 半个框宽 |
|---|---|---|---|---|
| blob（实测回波） | 6,192 | **5.6 px** | 27 px | 17.7% |
| projected（投影） | 5,366 | **25.4 px** | 40 px | **63.4%** |

分场次看，偏移既**不稳定也不可整体平移修正**：

- 场次中位偏移 dx 从 −29.7 px 到 +16.3 px、dy 从 −57.5 px 到 +30.4 px；
- 同一场次内部离散度更大（`2023-09-21_160551` 的 dx IQR 62.5 px、dy IQR 43.9 px）。

这与仓库里更早就留下的观察一致（`configs/_base_/datasets/paired_uxo.py:51-56`）：
projected 框位置的对比度只有 +0.1~+7，而 blob 框位置是 +12~+51——即投影框位置
根本没有回波。

## 影响面

1. **训练不受影响**：`configs/_base_/datasets/paired_uxo.py:57` 自 E07 起就是
   `sonar_gt_sources=("blob",)`，声呐头只用可见回波框训练，无框帧当作背景负样本。
   所以模型是干净的，投影框从未进入损失。
2. **只有评测的 `all` 口径被污染**：它把 372 帧（val）只有投影框的帧也算进分母，
   任何模型在这些帧上都拿不到分，与该模型强弱无关。
3. 这解释了同臂 all 比 blob 稳定低 0.07–0.13（相对低 26%–37%）：不是模型变了，
   是考场里混进了没有标准答案的题。

## 裁定

- **对外主口径 = `gt=blob`**（只评有实测回波的帧，其余整帧排除）；
- `gt=all` **降为诊断口径**，仅在需要说明"含未校准投影标签会怎样"时引用，
  不进主表；
- 论文写作时表注必须写明："声呐 GT 取自可见回波标注（blob）；另有 46.4% 的
  投影标注因标定误差（中位 25.4 px）未计入评测。"

同日撤销的文件内原裁定见 `doc/logs/2026-11-05-gt-metric-decision.md` 顶部留痕。

## 复现

```bash
cd ~/mycode/VSFusionDistill
PYTHONPATH=. .venv/bin/python tools/alignment_check.py
PYTHONPATH=. .venv/bin/python tools/session_offset.py
PYTHONPATH=. .venv/bin/python tools/echo_demo.py   # 出 results/echo_demo.png
```

## 待办（不属于本裁定）

若论文/审稿人要求"900 帧全覆盖"的读数，必须先**重做投影标定**（按场次逐帧对齐，
不是全局平移），这是数据侧工作，不属于模型侧。
