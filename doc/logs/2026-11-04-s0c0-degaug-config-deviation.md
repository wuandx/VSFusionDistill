# 2026-11-04 s0_c0 相机基线配置偏离：AOSampleDegLevel 默认 probs

## 事实

本地跑的纯光学基线 `work_dirs/baseline_camera_only_seed0`（config `configs/f2/s0_c0_camera_only_yoloxs.py`）在训练 pipeline 里写了 `AOSampleDegLevel` 但没有给 `probs`，该 transform 因此回落到 `aodet/datasets/transforms/pack_paired.py:41-42` 的 `_DEFAULT_PROBS = {d0:0.16, d1:0.16, d2:0.16, d3:0.16, d4:0.16, dinf:0.20}`。即：训练时只有 16% 的帧是名义清晰（d0），20% 的帧相机被整块置零（D∞），其余 64% 是合成退化档。

导师的 `configs/f2/e11_bcam_camera_only_yoloxs.py` 显式写 `probs={'d0': 1.0, 'd1': 0.0, ..., 'dinf': 0.0}`，即全程名义清晰。

## 影响

| 读数（val，900 帧，d0） | 本地 s0_c0 | 5090 e11_bcam seed0 | 差 |
|---|---|---|---|
| camera AP@[.5:.95] | 0.5088 | 0.5400 | −0.031 |
| camera AP50 | 0.8101 | 0.8503 | −0.040 |
| camera AR@100 | 0.5960 | 0.6252 | −0.029 |

性质判定：不是环境差异（同一 config 同一 seed 在 5090 与本机的其它臂均能复现到 ±0.03 内），是配置语义差异。两条臂训练分布不同，因此不能作为同协议对照。

已受到的处置：
- 本臂改称"退化增强相机基线"（degradation-augmented camera baseline），不再用于"纯光学 baseline"这一格；
- 纯光学 baseline 引用 5090 的 `e11_bcam`×3（val d0 camera AP50 0.8503 / 0.8674 / 0.8236，均值 0.8471；AP 0.5300，AR 0.6158）；
- `configs/f2/s0_c0_camera_only_yoloxs.py` 头部加 PROVENANCE NOTE，把实际训练条件写进文件本身，避免日后误读；
- 结果归档 `results/2026-11-04_camera_b0/`，`run_meta.txt` 记录该 NOTE。

## 根因（过程层面）

启动前只人工核对了"声呐双头置 None、相机头存在"这一项结构性质，未把解析后的完整配置与参考 config 逐键比对。手抄 config 的风险点恰在于此：漏一个 `probs` 不会报错、不会改变 loss 的形态、也不会让冒烟测试失败（1 epoch 冒烟只验证能跑通，不验证训练分布）。

## 处置（新增的硬开关）

`tools/config_gate.py`：解析两份 config，逐键 diff；除白名单易变键（hooks、work_dir 等）外，任何差异必须用 `--expect <dotted.path>` 显式声明为"故意不同"，未声明的差异一律 `GATE: FAIL` 并返回非零，禁止发车。

用法：

```
PYTHONPATH=. .venv/bin/python tools/config_gate.py \
    --candidate configs/f2/<new>.py \
    --reference configs/f2/<reference>.py \
    --expect model.uncoupled_sonar_head --expect model.fusion.type
```

已验证它能拦住本次这个 bug：以 `s0_c0` 为候选、`e11_bcam` 为参考运行时，报 `train_dataloader.dataset.pipeline` 与 `train_pipeline` 两处未声明差异，差异内容正是 `AOSampleDegLevel` 少了 `probs`，结果为 `GATE: FAIL`。

另一条更强的规则：**派生臂不手抄 config，直接继承参考 config 并只写差异项**（例如纯光学就该直接跑 `e11_bcam`，而不是复制一份再改写）。

## 代价

4.5 GPU 小时（304 epoch × 207 iter，0.25 s/iter）与一个本可与 5090 直接对账的对照臂。
