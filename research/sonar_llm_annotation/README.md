# sonar_llm_annotation · 声呐候选框生成 + VLM 判读流水线

> **一句话定位**：这是一个 **candidate 生成器 + 人工判断放大器**，不是自动标注真值。
> 它把声呐帧里"值得看一眼"的位置找出来、渲染成判读卡、交给 VLM/助手给意见，最后仍由人签收。
> 任何"这批数据已经有标注了"的说法都不成立 —— 声呐侧没有人写给的真值框（见下）。

本文所有数字都来自仓库内实际产物（`out/*.json`、脚本 stdout）。命令均在
Windows + CPython 3.12 下实测通过，验证时间为 **2026-11-12 03:00–03:19**；
`engine/`、`plugin/`、`tests/` 当时仍在被别人改动（`cards.py` 03:00 修过、03:13 新增 `proposal_to_record()`，
`echo.py` 的 `--mode` 默认值 03:00 变过），复跑结果若与本文件不符，以你手上的产物为准并回写本节。

---

## 1. 它解决什么问题，为什么不指望"模型直接吐框"

目标是在三条开发录音的声呐扇面上，产出**可被人快速接受/否决的候选框**，
用 VLM 逐帧判读代替人眼逐帧扫图，从而把人的注意力压缩到"少数可疑帧"上。

做不到"模型直接吐框"的原因有三条，都是本仓库内部复算出来的，不是推测：

| 事实 | 证据 | 层级 |
|---|---|---|
| 声呐侧**没有人工 GT**，`sonar.json` 的框是位姿投影工具生成的 | `code/VSFusionDistill/aodet/datasets/converters/uxo_to_paired.py` 原文：`Sonar ground-truth boxes do not exist; they are produced later by the pose-based projection tool (F2 TODO 14.2)` | 仓库原文 |
| 扇面里最亮的东西是**类无关结构**（倾斜波束打到水平池底形成的亮弧），不是目标 | `out/companion_test.json`：三类亮弧径向厚度 107.5–111.5 px（0.32–0.33 m），全帧存在率 715/715、771/771、725/725。另有盲判目视口径 bomb 150–250 row（≈0.45–0.75 m），二者是不同物理量，**并列保留**（LIMITATIONS §4.2） | 原始产物复算 |
| 目标在声呐中的位置**算不出来**：`geometry.predict()` 恒返回 `available=False, reason="gantry_not_sonar_frame"` | `out/calibration.json`（`status="degraded"`，`unavailable=[sonar_pose, absolute_range, beam_angle, fov, target_position]`） | 原始产物复算 |

| **VLM 判读本身也不可复现** | 同模型同协议同 24 张卡：A 报 object 21，B 报 structure 23，逐卡一致率 1/24、**Cohen's κ = 0.037**（`out/judge_disagreement.json`） | 实测 |

所以本仓库只做三件事：**分离结构、给候选、给判读材料**。身份（bomb/grenade/mortar）
在声呐里目前是 `unresolved`，判定卡上也不画 3D 框（画不出来）。

最后那条很重要：判读员的 `verdict` 是**这一帧的一个意见**，不是标签。导出只认 `reviews.jsonl` 里的人的决定。
换句话说，这套工具放大人的判断，不替代它——这也是它唯一站得住的定位。

---

## 2. 流水线

```
声呐帧 (128 beam × 780|441 row)
   │
   ├─① 结构 / 扰动分离        engine/echo.py        → structures[]（类无关、排除）+ blobs[]
   ├─② 候选                   engine/echo.py --proposals → proposals.jsonl
   │   └─②' 紧凑目标（另一条） engine/compact.py  → 同一格式的 proposals.jsonl
   ├─②b 距离带（先验）         tools/rangeband.py     → out/<rec>/band.json（两条水平虚线，不是框）
   ├─③ 判定卡                 engine/cards.py       → out/cards/<recording>/<sample>__g<n>x.png
   ├─④ VLM / 助手判读         docs/judgment-protocol.md + out/.../judgments/<sample>.json
   ├─⑤ 人工复核               review/server.py（:8771）
   └─⑥ 导出                   plugin/sonarllm/cli.py export → candidate-only 数据集（不可直接训练）
```

每一步的**当前真实状态**（不是设计意图）：

| 步骤 | 状态 | 说明 |
|---|---|---|
| ①echo 结构/扰动分离 | 可用；对**扩展目标**是负结论（只在这三条录音上成立） | 扇面外局部 SNR 峰值中位数 bomb 2.91 / incendiary 2.75 / mortar 2.47；暗影候选 20 帧内 0 个。它的背景是**时域**中位，会把静止目标一起减掉（FINDINGS §10.6） |
| ②proposals.jsonl | 通 | `out/<rec>/proposals.jsonl`；`cards.py` 的 `proposal_to_record()` 按录音名回读 `.pgm`。记录没有 `candidate` 时（如 bomb 0622）卡片是 `frame-default` 框，`box_is_candidate=false` |
| ②'compact 紧凑目标 | 通（新） | `engine/compact.py`：单帧块中位背景（16×16），宽度 ≥70 beams 判 `structure` 永不进候选。`2023-09-21_105230` 839 帧里 837 帧有候选，相邻帧质心位移中位 0.71 px |
| ②b rangeband 距离带 | 通，但**没有一条 `model_ok`**（2 条 `insufficient_detections`、3 条 `unreliable_model`） | 由 proposals 的检测距离反推单一 3D 点 `P` + 偏置 `b`（`range=\|P-c\|+b`）；`b`/`P_z` 撞搜索界或留出 p90 > 0.15 m 时拒绝出"预测带宽"，退回**观测带宽**（±N 行）。卡片上只画 `row_lo`/`row_hi` 两条虚线，`unreliable_model` 时标签写 `observed … model rejected; NOT a prediction`。它**只约束距离，不约束方位**（`identity` 仍未解） |
| ③cards 渲染 | 可用（`--selftest` 全 PASS） | 三种输入都能渲：统一记录、echo/compact proposals（jsonl）、dry-run 记录。`--crop-mode {candidate,band,auto}`（默认 `candidate`）决定 B/C 面板跟候选还是跟行带；`2023-09-21_110229` 的 4 张补渲卡在 `cards_supp/`。尺寸不恒定，只信卡片上的 `zoom=` 与 `prior=` |
| ④judge 判读 | 通 | 6 条录音 × 12 张卡判读全部落盘；`check --recording 2023-09-20_171105` → `12 条判定，0 条不合法`（10:0x 实测）。卡片重渲后用 `resign` 重签（记 `card_sha256_previous` / `resigned_*`） |
| ⑤review 服务 | 通 | `review/server.py --port 8771`；忙端口 rc=2；`out/review-shots/` 有 7 张真截图（含 06/07 两张带行带） |
| ⑥export | 通 | `out/_demo_v2`：**14 条**（110229 11 + 105230 2 + 101840 1；`train 1 / val 5 / unassigned 8`）；旧 `out/_demo_110229` 的 10 条保留作历史——少 4 条是因为那 4 帧当时只能判 `unsure`（裁剪缺陷，见 ③ 的 `--crop-mode`）。fixture 录音（171105）仍导出 0 |

---

## 3. 目录地图

| 路径 | 职责 | 谁维护 |
|---|---|---|
| `BRIEF.md` | 任务书：目标、数据路径、已排除的假设（gantry / FOV 130°） | Lead |
| `docs/FINDINGS.md` | 结论汇总 + "论文/产物/推断"分层 | Lead |
| `docs/geometry-calibration.md` | 距离轴标定、变换链、FOV 上界（已降级为条件界） | T-GEOM |
| `docs/mesh-prior.md` | 3D 网格剪影先验（上界，不是声学模型） | T-MESH |
| `docs/judgment-protocol.md` | 判读协议 cards/v0（唯一的判读标准） | T-JUDGE |
| `docs/LIMITATIONS.md` | **这套东西不能做什么**（每条带证据） | T-DOCS |
| `docs/RUNBOOK.md` | 复现与运维手册（命令 + 预期输出 + 故障排查） | T-DOCS |
| `docs/FINAL-REPORT.md` | 结项报告（证据链、三条录音读数、已知缺陷） | T-DOCS |
| `engine/geometry.py` | 逐帧头信息、`range = WindowStart + row×RES`、`predict()`（恒不可用） | T-GEOM |
| `engine/echo.py` | 背景模型、结构分割、扰动候选、位移估计 | T-ECHO |
| `engine/track.py` | 关键帧 → 全序列的候选传播（链式） | T-TRACK |
| `engine/mesh_prior.py` | 网格加载、剪影栅格化、位姿扫描 | T-MESH |
| `engine/cards.py` | 判读卡渲染（三面板 + 时间条 + 页脚溯源） | T-CARDS |
| `plugin/sonarllm/` | 状态/清单/校验/导出/起服务（`python -m sonarllm.cli`） | T-PLUGIN |
| `review/` | 复核台（HTTP 服务 + 静态页 + `POST /api/review`） | T-REVIEW |
| `tests/` | 自检（10:1x 实测 **119 PASS / 0 FAIL / 0 ERROR / 0 SKIP**，17.9 s；见 LIMITATIONS §7.5） | T-TESTS |
| `out/` | 产物：`calibration.json`、`companion_test.json`、`blind_judge.json`、`propagate_*.json`、`cards/`、`<rec>/judgments/` | 各线 |
| `tmp/` | 草稿（`tmp/cards/dryrun/`、`tmp/review/`），**不是交付物** | 各线 |

---

## 4. 5 分钟跑通（逐条可复制，均已实测）

先决条件：`D:\pby\uxo-full\extracted\recordings\` 存在三条录音（bomb / grenade / mortar）；
Python 只需 `numpy` + `Pillow` + `pyyaml`（**没有** cv2 / scipy / skimage，代码也不依赖它们）。
所有命令都在仓库根目录执行，路径**不要写成中文 Windows 绝对路径**（脚本自己用
`Path(__file__).resolve().parents[1]` 定位仓库）。

```bash
cd /mnt/d/agent_workspace/水下/声呐目标检测_workflow/sonar_llm_annotation
PY=/mnt/c/Users/ASUS/AppData/Local/Programs/Python/Python312/python.exe

# 0) 环境自检：看 Python 与依赖（bash 里的 python 是 WSL 的 3.10，没 numpy，别用它）
$PY -c "import sys, numpy, PIL, yaml; print(sys.version.split()[0], numpy.__version__, PIL.__version__)"
# 预期：3.12.10 2.5.4 13.0.0

# 1) 几何：逐帧头信息 + 距离轴（bomb 780 行 / 另两条 441 行）
$PY engine/geometry.py --recording 2023-09-20_171105 --frames 622,700
# 预期含：rows=780 beams=128  RES=0.00298256 m/row
#         WindowStart=0.6949365  WindowLength=2.3263969
#         range window 0.6949 .. 3.0184 m
#         predict(): gantry_not_sonar_frame (available=False)

# 2) 回波：结构/扰动分离（务必显式给 --mode，默认值会变）
$PY engine/echo.py --recording 2023-09-20_171105 --frames 622,700 --mode aligned
# 预期含：f622: n_cand=6 drop=-0.04 top=(18,240) span=8x14 snr=11.1 ov=0.00 score=5.4
#         [summary] {..., "shift_abs_median": [16.0, 1.0], ...}
# 注意：位移现在只出现在 [summary]，不再印在逐帧行上

# 3) 传播：关键帧候选沿全序列传播（必须用 -m，脚本直跑会 ImportError）
$PY -m engine.track --recording 2023-09-20_171105 --keyframe 622 --box 14,140,114,267 --out tmp/track_probe/622.json
# 预期尾行：wrote tmp\track_probe\622.json（省略 --out 会写 out/propagate_<rec>_<kf>.json）
# 摘要：frames 715  auto 715 (100.0%)  score median 0.903
#       path {'drow_range': [-5, 7], 'dbeam_range': [0, 0], 'clipped_frac': 0.0}
#       （JSON 文件里的键名是 n_frames / n_auto / score_median / path_summary）

# 4) 网格先验：自检（21 秒左右，写 out/prior_check.json）
$PY engine/mesh_prior.py --all --check
# 预期尾行：all_pass: True   （8 项断言全过）

# 5) 判读卡：自检 + 从真实候选记录渲染一张（03:13 起 echo→cards 已通）
$PY engine/cards.py --selftest
# 预期尾行：[selftest] PASS
$PY engine/cards.py --proposals out/2023-09-20_171105/proposals.jsonl --limit 1 --out tmp/cards/quickstart
# 预期：[cards] ...\2023-09-20_171105_0622__g1x.png 758x1764 zoom=2 prior=unavailable
# 注：0622 在 local 模式下 n_candidates=0，所以这张卡是 frame-default 框，不是候选框

# 6) 紧凑目标：另一条检测路径（单帧空间背景，不吃静止目标）
$PY -m engine.compact --recording 2023-09-21_105230 --every 50 --print
# 预期：每帧一行，含 n=... snr=... box=[x0,y0,x1,y1]；尾行 [compact] N frames, M with a candidate

# 7) 复核台：确认服务在跑（只读，不会动别人的进程）
$PY -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8771/api/health',timeout=3).read().decode()[:120])"
# 预期：{"ok": true, "service": "review", "port": 8771, ...}
```

> 第 2 步加 `--proposals <路径>` 就能把诊断记录落盘；第 5 步可以直接吃这种文件（03:13 起有
> `proposal_to_record()` 适配）。但录音名是**从文件所在目录名推的**：
> `out/2023-09-20_171105/proposals.jsonl` 没问题，而 `tmp/echo_probe/xxx.jsonl` 会报
> `KeyError: "unknown recording 'echo_probe'"`（实测）——这种就加
> `--recording 2023-09-21_120653`（实测可渲出 1493×1554 `zoom=6`）。
> 另外：记录里没有 blob 时卡片画的是"整帧默认框"（`box_source: frame-default`、`box_is_candidate=false`），
> **不是候选**，别当候选判读。03:13 之前这里会报 `ValueError: frame_data has neither 'img' nor image.path`。

起服务、重渲卡片后为什么要重做判定、导出与回滚，见 `docs/RUNBOOK.md`。

---

## 4.1 为什么有两条检测路径（`echo` 与 `compact`）

| | `engine/echo.py` | `engine/compact.py` |
|---|---|---|
| 背景 | **时域**局部中位（±10 帧） | **单帧空间**块中位（16×16 块） |
| 对静止目标 | 被当成背景减掉 | 目标占不满半块时背景不动 |
| 对宽亮弧 | 减不掉，靠 `structure` 角色排除 | 宽度 ≥70 beams 直接判 `structure` |
| 适用 | 回波铺满扇面、目标在动的录音 | 紧凑目标、相对声呐几乎不动的录音 |

结论层面这件事很重要：**"背景扣除后什么都没有"不能反推"原图里没有东西"**。
三条选定录音里目标回波不可检（三条独立方法 + 两轮盲判 object=0），换两条录音之后
`compact` 立刻给出 99.8% 帧覆盖、逐帧位移中位 0.71 px 的连贯候选。

## 4.2 距离带（rangeband）与形状普查（census）：两条"排先看哪条"的命令

```bash
cd /mnt/d/agent_workspace/水下/声呐目标检测_workflow/sonar_llm_annotation
PY=/mnt/c/Users/ASUS/AppData/Local/Programs/Python/Python312/python.exe

# 1) 距离带：从 proposals 的距离序列反推一个 3D 点 + 偏置，写 out/<rec>/band.json
#    ⚠ 会重写该录音的 band.json（卡片行带、export.json 的 band 块都读它）；只想看看就先复制仓库
$PY tools/rangeband.py --recording 2023-09-21_110229
# [rangeband] 2023-09-21_110229 status=unreliable_model n=533 band_rows=6
#   P=[1.289, 1.424, -1.733] b=0.300 resid med 0.321 holdout med 0.322 p90 0.418 m
#   single fixed point does not explain this recording (parameter on its bound (b));
#   band is the OBSERVED range spread, not a prediction
# （2026-11-12 09:58 在仓库副本里跑的；产物与 out/2023-09-21_110229/band.json 逐字节相同，md5 3a59fb02…）

# 2) 形状普查：单条自查（--only 会关闭 refine，数字与 out/census 全量表不可比）
$PY tools/census.py --only 2023-09-21_110229 --every 12 --refine-top 0 --out tmp/census_probe
# 实测：[ 1/1] 2023-09-21_110229  cov=0.32 band=0.00 trk=15 /45 jumps=6 \
#        geo=0.35(range_variation_below_fixed_object_lower_bound) score=0.111
# 全量 40 条（写 out/census/，会覆写 census_v2.json 与 CENSUS-V2.md，较慢；本次未重跑）：
#   $PY tools/census.py --every 1
# 权威表是 out/census/CENSUS-V2.md（10:12，排序主键 base）；文字版 docs/CENSUS-V2.md（10:13）
```

三个状态要分清（`out/<rec>/band.json` 的 `status`）：

| status | 触发条件 | 卡片/导出里的含义 |
|---|---|---|
| `model_ok` | 无参数撞界 **且** 留出 p90 ≤ 0.15 m | `range band … (predicted ±N rows)`：这是模型给的带 |
| `unreliable_model` | 有参数撞界，或留出 p90 > 0.15 m | `range band … (observed ±N rows; model rejected; NOT a prediction)`：**观测散布**，不是预测 |
| `insufficient_detections` | 通过 snr 与 gantry 连接的检测 < 12 条 | 不画带（`frames: {}`），这是数据结论，不是崩溃 |

已评估的 5 条录音全部不是 `model_ok`：`2023-09-20_171105`、`2023-09-21_100927` 是
`insufficient_detections`（0 条检测）；`101840` 是留出 p90 0.163 m > 0.15；`105230`（b=−0.300、P_z=−1.9995）
与 `110229`（b=+0.300）是撞搜索界。撞界时 in-sample 残差再小也不能当位置解——详见
`docs/LIMITATIONS.md` §6.5 与 `docs/FINDINGS.md` 第十二节（含对早期"2–3 cm 残差证明固定点"的更正）。

---

## 4.3 补渲看不见候选的卡片，以及"按形状重排"视图

```bash
cd /mnt/d/agent_workspace/水下/声呐目标检测_workflow/sonar_llm_annotation
PY=/mnt/c/Users/ASUS/AppData/Local/Programs/Python/Python312/python.exe

# 1) 裁剪窗跟候选走（默认就是 candidate；band 才是跟行带，auto 是两者取并）
#    实测：crop=[0, 66, 116, 206]，卡片页脚印 mode=candidate
$PY engine/cards.py --proposals out/2023-09-21_110229/proposals.jsonl \
  --samples 2023-09-21_110229_0318 --crop-mode candidate --out tmp/cards_supp_probe --gain 1
# 110229 的 4 张补渲卡（0318/0367/0415/0464）已在 out/2023-09-21_110229/cards_supp/，
# 主批 12 张一字节未动（cards/report.json: byte_identical_rerender true, mismatch []）

# 2) 普查的"按形状证据重排"视图（只覆盖 out/census/RANK-BY-SHAPE.md，不碰 census_v2.json）
#    10:12 起 census.py 自己也按 base 排序（rank_key=base），所以这个视图与权威表同序
$PY tools/rank_by_shape.py
# 前 8（base）：110229 0.129 / 182317 0.128 / 105856 0.103 / 110049 0.073 /
#               123500 0.067 / 103728 0.067 / 101131 0.064 / 180506 0.063
```

为什么要重排：复合分数是 `base × (1−覆盖闸) × geo`，三道闸把 40 条全压到 0.000–0.058，
名次实际由"哪道闸响了"决定；而闸考察的几何可辨识性我们**已经知道不成立**（三条受审计录音全
`unreliable_model`）。所以"先看哪条"应由 `base`（形状/检出证据）回答，闸只当**否决**用：
`2023-09-20_182317` 的 `base 0.128` 与 110229 的 `0.129` 几乎相同，但 54% 帧整幅覆盖（那是结构），
它"几何闸通过"只因为候选少而稳。**几何闸能否决，不能认证。**

---

## 5. 常见坑

1. **两个 Python 别混用**：bash 里的 `python` 是 WSL 自带的 **3.10.12（没有 numpy）**，
   跑 `engine/*.py` 会直接 `ModuleNotFoundError`；要的是 Windows 侧
   `Python312\python.exe`（下文的 `$PY`）。路径也要配对：bash 认 `/mnt/c/...`，
   那个 `python.exe` 只认 `C:/...`，混着传会报"文件不存在"。中文绝对路径不要进命令行，
   先 `cd` 到仓库、再用相对路径。
2. **Python 没有 cv2 / scipy / skimage**：不要写依赖它们的脚本；连通域、卷积都在
   `numpy` 里手写（`engine/cards.py`、`tmp/cards/dryrun_real.py` 是现成例子）。
3. **780 行 vs 441 行**：bomb 是 780 个距离采样，grenade/mortar 是 441 个；距离分辨率
   也不同（0.00298256 / 0.00298322 / 0.00298254 m/row）。任何写死 780 的代码都是错的。
4. **端口 8771 与 8765**：`8771` 是本仓库复核台的默认端口（`review/server.py:DEFAULT_PORT`）；
   `8765` 属于主 Agent 的另一套服务，两者无关。本次核验时 8765 未监听（`http=000`）。
5. **中文在终端里会乱码**：本会话的终端对 UTF-8 中文输出显示为 `���ź�` 之类的替换符。
   文件内容本身是对的（`review/static/index.html` 里 U+FFFD 计数为 0），别据此判断"页面坏了"。
6. **`engine/echo.py` 的 `--mode` 默认值会变**：同一份代码在 02:58 默认 `aligned`、
   03:00 默认 `local`，同一帧 622 的候选数因此从 6 变成 0。文档与脚本里**一律显式传 `--mode`**。
7. **`python engine/track.py` 不能直跑**：它用 `from . import echo` 相对导入，
   必须 `$PY -m engine.track ...`（`engine/` 是命名空间包，无需 `__init__.py`）。
   同理 `plugin/sonarllm/cli.py` 要在 `plugin/` 目录下 `$PY -m sonarllm.cli ...`。
8. **别开第二个复核台**：`review/server.py` 启动时会覆盖 `tmp/review/server.json` 与
   `server.pid`，别人正在用的实例信息会被写掉。要验证就查 `/api/health`，要起就在副本目录里起。
9. **空帧时 stdout 不是合法 JSON**：`[summary]` 行里会出现 `NaN`（`empty_frames>0` 时），
   严格 JSON 解析器会拒绝；记录文件里对应字段是 `null`（`echo.py --proposals` 产物可正常解析）。

---

## 6. 事实层级（全文统一）

| 标记 | 含义 |
|---|---|
| **论文原文** | 只用于 `related_work/` 里的文献；本仓库与 CMOLD 论文**无关**，不要互相引用 |
| **仓库原文** | 仓库内代码/文档里的字符串原文（如 converter 注释） |
| **原始产物复算** | 由 `out/*.json`、脚本 stdout 直接读出或算术得到 |
| **仓库历史记录** | 旧日志、旧报告里的读数（如 `results/2026-11-04_sonar_b0/eval_sonar_b0_valid.log`） |
| **推断** | 由上述事实推得、但未直接测量 |
| **助手目视** | VLM/助手看卡片得到的观察（如 `out/blind_judge.json`） |

本次交付的 `README.md` / `docs/LIMITATIONS.md` / `docs/RUNBOOK.md` / `docs/FINAL-REPORT.md`
四份文档里，凡结论句都带层级标记；未标记的句子是操作说明，不是事实主张。
