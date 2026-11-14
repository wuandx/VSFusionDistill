# RUNBOOK —— 从原始 pgm 跑到可复核候选

> **状态快照：2026-11-12 03:19（+08:00）。** `out/` 与 `engine/` 仍在被其他并行线写入（`cards.py` 03:13 才加上 `proposal_to_record()`），本手册里的读数都标了生成时间；你在别的时间跑，先按 §1 重新核对，再相信任何数字。
>
> 事实层级沿用 README 的标记法：
> `[仓库原文]` = 代码/文档原文（带文件行号）；`[实测]` = 我在本机亲自跑出来的输出；
> `[复算]` = 由产物数值算得；`[推断]` = 未证实的解释，不得当结论引用。
>
> 这份手册**只读**代码与数据：除了 `out/`、`tmp/` 下的产物，不改 `engine/`、`plugin/`、`review/`、`tests/`，也不碰 `D:\agent_workspace\水下\声呐目标检测`。

---

## 0. 它能做什么 / 不能做什么

| 能做 | 不能做 |
|---|---|
| 在三条开发录音上，从 `.pgm` 跑到几何自检、回声诊断、mesh 先验、卡片、人工判定、导出 | 给出"自动标注真值"。这套东西的定位是 **candidate 生成器 + 人工判断放大器** |
| 每一步都有可复现的命令、期望输出行和失败定位点 | 画出 3D 框 / 给出目标位姿：`predict()` 恒为 `available=False`，见 §4.1 |
| 产物带 `candidate_only_not_training_ready: true` 与 `sonar_gt_status: HOLD` | 把候选当人工 GT 训练；原项目 converter 原文写明声呐 GT 框不存在 |

---

## 1. 一分钟自检（5 条命令）

```bash
cd /mnt/d/agent_workspace/水下/声呐目标检测_workflow/sonar_llm_annotation
PY=/mnt/c/Users/ASUS/AppData/Local/Programs/Python/Python312/python.exe

$PY engine/geometry.py --recording 2023-09-20_171105 --frames 622
$PY engine/echo.py --recording 2023-09-20_171105 --frames 622 --mode aligned
$PY engine/cards.py --selftest
$PY engine/mesh_prior.py --all --check
cd plugin && $PY -m sonarllm.cli status
```

期望看到的关键行（都是 `[实测]`）：

```
2023-09-20_171105  [100lbs_bomb / 100lbs_aircraft_bomb]
rows=780 beams=128  RES=0.00298256 m/row
WindowStart=0.6949365  WindowLength=2.3263969
range window 0.6949 .. 3.0184 m
predict(): gantry_not_sonar_frame (available=False)
```
```
  f622: n_cand=6 drop=-0.04 top=(18,240) span=8x14 snr=11.1 ov=0.00 score=5.4
  [summary] {..., "shift_abs_median": [16.0, 1.0], ...}    ← 位移只在 summary 里，不在逐帧行
```
```
sonarllm 0.1.0  root=D:\agent_workspace\水下\声呐目标检测_workflow\sonar_llm_annotation
recording              proposals  cards judged reviews  verdicts
2023-09-20_171105            100     12      1       6  {"structure": 1}
```

`cards` 列会随别人的重渲变动（03:12 是 17、03:19 是 12），且它是跨 `judge.card_roots()` 的统计，
不等于 `out/cards/` 里的文件数（详见 `docs/LIMITATIONS.md` §7.4）。只把 `proposals`/`judged`/`reviews` 当稳定读数。

**路径约定（最容易踩的一条）：** WSL 的 bash 认 `/mnt/c/...`，Windows 的 `python.exe` 只认 `C:/...`；两者混用会得到"文件不存在"（`[实测]`：把 `C:/.../x.jsonl` 传给 bash 的 `wc` → `No such file or directory`，文件其实在）。**中文目录不要出现在命令参数里**——唯一例外是 `cd` 到本仓库那一下（只能写完整路径），之后一律用相对路径；临时产物写到 `tmp/` 下。

（Windows 控制台上中文 stdout 会显示成 `���ź�`，这只是终端编码，文件内容是好的；`[实测]` `review/static/index.html` 6327 字符，U+FFFD 计数 0。）

---

## 2. 三条开发录音的固定参数（先查表，再谈像素）

| 录音 | 类别目录 / category | 帧范围 | rows | RES (m/row) | WindowStart | WindowLength | 距离窗 |
|---|---|---|---|---|---|---|---|
| `2023-09-20_171105` | `100lbs_bomb` / `100lbs_aircraft_bomb` | 622..1336 (715) | 780 | 0.00298256 | 0.6949365 | 2.3263969 | 0.6949 .. 3.0184 m |
| `2023-09-21_120653` | `20lbs_incendiary` / `incindiary_grenade` | 163..933 (771) | 441 | 0.00298322 | 0.6951 | 1.3156 | 0.6951 .. 2.0077 m |
| `2023-09-21_100927` | `15cm_mortar` / `mortar_shell` | 87..811 (725) | 441 | 0.00298254 | 0.6949 | 1.3153 | 0.6949 .. 2.0072 m |

`[实测]`（`engine/geometry.py`）＋ `[仓库原文]`（`engine/geometry.py:54` 的 `RECORDINGS` 表）。
**三条录音的 RES 不是同一个常数**（0.00298256 / 0.00298322 / 0.00298254）；写死 0.002983 去算跨录音的米数会引入 ~0.2% 误差，别把三条录音的行数直接当同一把尺子。

`range_m = WindowStart + row × RES`；`samples` 是距离向行，`beams`（列，恒 128）是方位向。`[仓库原文]`

---

## 3. 接入一条新录音

1. **原始数据位置**：`<RAW_ROOT>/<class_dir>/<recording>/aris_raw/NNNN.pgm`，`RAW_ROOT = D:\pby\uxo-full\extracted\recordings`（`[仓库原文]` `engine/geometry.py:37`）。
2. **`RECORDINGS` 表之外也能用（03:30 起）**：`engine/geometry.py` 新增 `discover(recording)`——
   在 `RAW_ROOT/<class_dir>/<recording>/aris_raw` 下按目录名反查类别（`CLASS_CATEGORY`：
   `100lbs_bomb` / `100lbs_bomb_(floor)` → `100lbs_aircraft_bomb`；`20lbs_incendiary` → `incindiary_grenade`；
   `15cm_mortar` → `mortar_shell`），发现的 spec 会记进 `DISCOVERED` 并在 `notes` 里标注
   "不是在册的三条审计录音"。实测 `2023-09-21_105230` / `2023-09-21_101840` 可直接跑。
   **仍然拒绝的是**：既不在表里、目录里也找不到的情况（`KeyError`），这时要么路径写错，要么类别目录名不认得。
3. **header 的取值顺序**：`aris_file_meta.yaml` 的 `WindowStart`/`WindowLength` 在三条开发录音里是 0，
   拿它会得到一段从 0 开始的假距离。`header_of()` 现在是三级兜底：
   ① yaml → ② `aris_frame_meta.csv` **第一行数据**（实测 105230：`WindowStart 0.6949353218078613` /
   `WindowLength 1.3153067827224731`）→ ③ PGM 头读 `NumRawBeams`/`SamplesPerBeam`。
   **两者都拿不到就抛 `KeyError`**，理由是"距离轴会被发明出来，所以宁可拒绝"（源码注释原话）。
4. 列一遍实际帧号：`$PY engine/geometry.py --recording <rec> --list-frames`。

---

## 4. 分步流程

### 4.1 S1 几何自检（必跑，10 秒）

```bash
$PY engine/geometry.py --recording 2023-09-21_120653 --frames 163
```

期望（`[实测]`）：

```
2023-09-21_120653  [20lbs_incendiary / incindiary_grenade]
rows=441 beams=128  RES=0.00298322 m/row
WindowStart=0.6951  WindowLength=1.3156
range window 0.6951 .. 2.0077 m
predict(): gantry_not_sonar_frame (available=False)
```

**`predict(): gantry_not_sonar_frame` 是设计结果，不是故障。** `FrameGeom.predict()` 永远返回 `{available: false, reason: "gantry_not_sonar_frame"}`（`[仓库原文]`）。所以：卡片里不会出现 3D 框或 predicted 十字；任何文档里出现的"预测框"只能来自别的东西。

失败定位：`FileNotFoundError: missing ...aris_raw` → 数据盘没挂或 class_dir 写错；`KeyError: unknown recording` → §3.2。

### 4.2 S2 回声诊断：`local` 与 `aligned` 是两件事

```bash
$PY engine/echo.py --recording 2023-09-20_171105 --frames 622 --mode aligned
$PY engine/echo.py --recording 2023-09-20_171105 --frames 622            # 默认 --mode local
```

`[实测]` 同一帧、同一份数据，两个 mode 的结论完全不同：

| 命令 | bomb f622 结果 |
|---|---|
| `--mode local`（**当前默认**） | `f622: n_cand=0 drop=+0.67 top=None`（`empty_frames: 1`） |
| `--mode aligned` | `f622: n_cand=6 drop=-0.04 top=(18,240) span=8x14 snr=11.1 ov=0.00 score=5.4`；summary 里 `shift_abs_median [16.0, 1.0]` |

（逐帧行现在**不再**印 `shift=`；要看位移读 `[summary]` 的 `shift_abs_median`。03:00 之前的输出格式不同，别拿旧截图对。）

`[仓库原文]` `engine/echo.py:824`：`ap.add_argument("--mode", default="local", choices=["local","aligned","median","raw"])`。
**默认值在 03:00 前后从 `aligned` 改成 `local`**；`local` 下"亮带能量下降"是正的（+0.67），候选数归零。写报告引用候选数时，**必须同时记录 mode**，否则同一条录音会给出 6 和 0 两个"事实"。

grenade `--mode aligned --frames 163,700`（`[实测]`）：`f163: n_cand=2 … top=(46,216) span=6x6 snr=5.7`；`f700: n_cand=6 … top=(12,135) span=9x7 snr=11.0`。

### 4.3 S3 存诊断记录：`--proposals`

```bash
mkdir -p tmp/echo_probe
$PY engine/echo.py --recording 2023-09-21_120653 --frames 163,700 --mode aligned \
    --proposals tmp/echo_probe/grenade_aligned.jsonl
```

输出末行 `-> tmp\echo_probe\grenade_aligned.jsonl (2 records)`（`[实测]`）。
每条记录字段（`[实测]`）：`bg, blobs, energy, frame, mode, n_beams, n_candidates, n_rows, range_window_m, shift, structures, top`。

**这份文件的两种用途**：

- **留痕**：`shift`（drow/dbeam/align_score/clipped）、`structures`（`class_invariant` / `excluded_from_candidates`）、`n_candidates`。
- **喂卡片**（03:13 起）：`cards.py` 的 `proposal_to_record()` 会把每一行转成统一记录再渲染。
  录音名默认取**文件所在目录名**，所以放 `out/<recording>/` 下最省事；放别处就加 `--recording`：

```bash
# 放对位置（目录名=录音名）：直接渲
$PY engine/cards.py --proposals out/2023-09-20_171105/proposals.jsonl --limit 1 --out tmp/cards/echo_contract
# 预期：[cards] ...\2023-09-20_171105\2023-09-20_171105_0622__g1x.png  758x1764  zoom=2  prior=unavailable

# 放错位置（tmp/echo_probe/）：必须显式给录音名，否则 KeyError: "unknown recording 'echo_probe'"
$PY engine/cards.py --proposals tmp/echo_probe/grenade_aligned.jsonl --recording 2023-09-21_120653 --limit 1 --out tmp/cards/adapt_ok
# 预期：...2023-09-21_120653_0163__g1x.png  1493x1554  zoom=6  prior=unavailable
```

> 03:12 之前这条链路是断的（`ValueError: frame_data has neither 'img' nor image.path`，`engine/cards.py:192`）。
> 现在的适配层只做重命名，**不产生新信息**；没有 blob 的帧会画 `frame-default` 框（`box_is_candidate: false`）——
> 那不是候选，别拿去判读。细节见 `docs/LIMITATIONS.md` §7.1。

### 4.4 S4 mesh 先验（可选，21 秒）

```bash
$PY engine/mesh_prior.py --all --check
```

期望末段 `all_pass: True`，写出 `out/prior_check.json`（`[实测]`：sha256 `b840cce292bef8a09c2a4812fc09634f5ea14ce6a8bf8328188c282e39c8e154`，21.3 s）。
单条录音取一张剪影：

```bash
$PY engine/mesh_prior.py --category 100lbs_aircraft_bomb --recording 2023-09-20_171105 \
    --frame 622 --out tmp/prior_probe/622.json
```

`[实测]` 返回 `box_xyxy [57,151,91,231]`、`visible_frac 1.000`。
**只传 `--recording` 不加 `--category`/`--all` 会报** `error: --category or --all is required`（`[实测]`）。
读剪影的三条纪律（`[仓库原文]` mesh-prior）：① 它是**候选框的上界**，不是声学模型（无阴影/多径/多次反射）；② `uniqueness` 恒 `False`，同一剪影对应 864 个位姿；③ `mesh_to_target` 是 HOLD，剪影只用标称长度缩放。

### 4.5 S5 生成卡片（唯一可用入口：带帧数据的记录）

```bash
$PY engine/cards.py --proposals tmp/cards/dryrun/proposals_dryrun.jsonl \
    --samples 2023-09-20_171105_0622 --flat --out tmp/cards/runbook_out --gain 1,3,5
```

`[实测]` 生成 3 张，每张一行：

```
[cards] tmp\cards\runbook_out\2023-09-20_171105_0622__g1x.png  1176x1576  zoom=6  prior=unavailable
[cards] tmp\cards\runbook_out\2023-09-20_171105_0622__g3x.png  1176x1576  zoom=6  prior=unavailable
[cards] tmp\cards\runbook_out\2023-09-20_171105_0622__g5x.png  1176x1576  zoom=6  prior=unavailable
```

常用开关：`--samples`（逗号分隔样本号）/ `--frames`（帧号）/ `--limit` / `--flat`（写到 `<out>/<sample>.png` 而不是 `<out>/<recording>/...`）/ `--gain 1,3,5` / `--scale` / `--margin` / `--neighbors` / `--report` / **`--crop-mode {candidate,band,auto}`**。
**`--crop-mode` 决定 B/C 面板裁哪里**（`[仓库原文]` docstring）：`candidate`（默认）以候选框为中心、忽略记录里的 `crop_box`；`band` 跟 `frame_data["crop_box"]`（110229 主批 12 张就是这种"候选列中心 × 行带"的取法）；`auto` 在两者都可用时取并集。
**因此复现主批与补渲是两条命令**：主批 12 张由 `tmp/cards_110229/make_cards.py` 用 `crop_mode=band` 渲出（该脚本显式把 `crop_box` 设成 `[cx−26, row_lo, cx+26, row_hi]`）；补渲 4 张用 `--crop-mode candidate`，落在 `out/2023-09-21_110229/cards_supp/`。
实测（10:12）：`$PY engine/cards.py --proposals out/2023-09-21_110229/proposals.jsonl --samples 2023-09-21_110229_0318 --crop-mode candidate --out tmp/cards_supp_probe --gain 1` → `1513x1474 zoom=5 crop=[0, 66, 116, 206] mode=candidate prior=unavailable`。
**像素尺寸不是特征**：同一帧在 03:00 与 03:12 两次渲染中量到 1176×1553 和 1176×1576 两个高度（`[实测]`，渲染器中间改过），随 `--neighbors`/`--scale`/`--margin` 变。只信卡片里的 `zoom=`、`prior=` 和 footer 的 `range_m`。
`--record-json` 只吃**单条**统一记录（JSON），不是 jsonl（`[仓库原文]` `engine/cards.py --help`："single unified record (JSON)"）。

卡片对输入的硬要求（`[仓库原文]` + `[实测]`）：统一记录里必须有 `img`（P5 字节）或 `image.path` 指向一个存在的 `.pgm`；可选 `candidate.box_xyxy`、`prior`、`provenance`。
**echo 的 proposals 行不算这种记录**，但 `cards.py` 现在会自动转（`proposal_to_record()`，03:13 起）——它用目录名/`--recording` 回读 pgm，把 `blobs[0]` 当候选（见 §4.3）。所以可渲染的输入有三种：统一记录（`--record-json`，单条）、echo proposals（`--proposals`，jsonl）、以及 dry-run 驱动产出的那种（`tmp/cards/dryrun/proposals_dryrun.jsonl`，`tmp/cards/dryrun_real.py` 是**临时脚本，不是交付物**）。

自检（不依赖任何数据文件）：

```bash
$PY engine/cards.py --selftest
```

`[实测]` 通过（10 项断言全 PASS），写出 `tmp/cards/selftest/`；`card1 [1264, 1538] zoom=4 sha=350510bb14a84d69`。
**sha 不是常量**：03:00 时同一张卡是 `e8ae01f2…`，渲染器一改就变——这正是 §6 判定作废的机制。
（02:55 时这一步曾崩在 `NameError: name 'neighbors' is not defined`（`cards.py:870`），03:00:09 由 T-CARDS 修好；再遇到同类报错，先看 `cards.py` 的 mtime 是不是刚被改过。）

### 4.6 S6 轨迹跟踪：必须走 `-m`

```bash
$PY -m engine.track --recording 2023-09-20_171105 --keyframe 622 \
    --box 14,140,114,267 --out tmp/track_probe/622.json
```

`[实测]` 4.1 s，stdout 摘要与仓库里的 `out/propagate_2023-09-20_171105_622.json` 一致：

```
2023-09-20_171105 keyframe 622 box [14, 140, 114, 267]
  frames 715  auto 715 (100.0%)  score median 0.903
  path {'drow_range': [-5, 7], 'dbeam_range': [0, 0], 'clipped_frac': 0.0}
```

（JSON 文件里的键名是 `n_frames` / `n_auto` / `auto_frac` / `score_median` / `path_summary`；
stdout 用的是缩写词，两者别混。）

直接 `python engine/track.py ...` 会报 `ImportError: attempted relative import with no known parent package`（`[仓库原文]` `track.py:32` `from . import echo`；`engine/` 没有 `__init__.py`，但作为命名空间包可用）。
`--box` 的格式是 `beam1,row1,beam2,row2`（帧像素，不是米）。**这条链的 `drow −5..+7` 与直接跨帧估计的 `−40..+43` 不一致，尚未解决**（见 LIMITATIONS §5.1）。引用位移数字时必须写明来自哪条路径。

### 4.7 S7 复核台（人工判定）

服务**已经在跑**（§5.1），直接开 `http://127.0.0.1:8771/`。判读口径只看 `docs/judgment-protocol.md`：一条贯穿扇面的大亮弧 = 结构，不是目标；要框的是"在径向位置上时域稳定、比周围更亮、更紧凑"的扰动。

进页面前先确认它读的是**哪份 proposals**（`proposals_root` 会被别人换）：

```bash
$PY -c "import json,urllib.request;d=json.load(urllib.request.urlopen('http://127.0.0.1:8771/api/proposals',timeout=5));print(d['count'], [(r['recording'],r['n'],r['source'],r['fixture']) for r in d['recordings']])"
```

`[实测]` 03:21（pid 50776）：`300` 条，三条录音各 100、`source='proposals'`、`fixture=False` —— 即真实 echo 候选。
02:43–03:17 期间同一端口指向 `tmp\review\proposals`（fixture 数据），那时的复核记录在 `reviews.jsonl` 里仍标着
`data_source: "fixture"`，不会被这次切换洗白。

判定落盘：`out/<rec>/judgments/<sample>.json` + `_manifest.json`（含 `card_sha256`）。

### 4.8 S8 一致性检查与导出

```bash
cd plugin
$PY -m sonarllm.cli check --recording 2023-09-20_171105
$PY -m sonarllm.cli export --dst ../tmp/export_probe/dataset --recording 2023-09-20_171105
```

`check` 当前输出（`[实测]`，10:0x）：

```
2023-09-20_171105: 12 条判定，0 条不合法
```

（03:xx 时这里报过 `FAIL …0622: card_sha256 与当前卡片不一致` + `1 条判定，1 条不合法`；
后来用 `resign` 把旧判定重签到新卡，守卫通过。`resign` 只重签 sha、**不重判**，
所以只在"卡片的声呐像素没变、只是渲染器改了"时用；它会写 `card_sha256_previous` / `resigned_at` /
`resigned_by` / `resigned_note`（`plugin/sonarllm/cli.py:69-108`）。用法：
`cd plugin && $PY -m sonarllm.cli resign --recording <rec> [--by <name>]`（`--recording` 必填，10:0x `--help` 实测；它会改写该录音的 judgments 文件）。）

守卫本身在 `plugin/sonarllm/judge.py:157-165`（`[仓库原文]` "图和结论必须对得上"）。重渲后的处置见 §6。

`export` 的两种结果（都是 `[实测]`，10:0x）：

```bash
# (a) 只有 fixture 复核的录音 → 0 条，并打印中文原因
cd plugin && $PY -m sonarllm.cli export --dst ../tmp/export_probe3/d3 --recording 2023-09-20_171105
# 导出 0 条：没有 status=accept/revise 的**人类**复核记录。已故意不写 data.yaml（见 _EMPTY_DO_NOT_TRAIN.txt）。
# {"n_exported": 0, "per_recording": {"2023-09-20_171105": 0}, "recordings_per_split": {}, ...}

# (b) 有真人（这里 operator 是 agent lead）accept 的录音 → 按样本导出
$PY -m sonarllm.cli export --dst ../tmp/export_probe3/d2 --recording 2023-09-21_110229
# {"n_exported": 7, "per_recording": {"2023-09-21_110229": 7},
#  "recordings_per_split": {"val": 4, "unassigned": 3}, "n_unassigned": 3,
#  "n_fixture_skipped": 0, "candidate_only_not_training_ready": true}
# 补渲 4 帧被 accept 之后（10:0x），同一条命令给 n_exported 11；汇总产物见 (c)。

# (c) 现成的汇总集（lead 10:09 导出，只读）
$PY -c "import json;d=json.load(open('out/_demo_v2/provenance.json',encoding='utf-8'));print(d['n_exported'],d['recordings_per_split'],d['n_fixture_skipped'])"
# 14 {'train': 1, 'val': 5, 'unassigned': 8} 5
# 14 = 110229 11（主批 7 + supp 4）+ 105230 2 + 101840 1；旧 out/_demo_110229 的 10 条是历史
```

`n_exported 0` 有两个明确的闸门，都不是"导出器坏了"（`[仓库原文]` `plugin/sonarllm/dataset.py:169-175`）：
1. 只导出 `accept`（取 `final_box`）与带 `final_box` 的 `revise`；
2. `data_source == "fixture"` 的复核默认跳过。`out/2023-09-20_171105/reviews.jsonl` 里现存的 8 条全部是 `data_source: "fixture"`（`[实测]`），所以一条也出不去——这是**故意**的防污染设计。

导出成功时会写 `data.yaml`、`labels/<split>/<sample>.txt`（YOLO 归一化坐标）、`images/<split>/<sample>.png`、`provenance.json`。`provenance.json` 里必须能看到 `candidate_only_not_training_ready: true` 和 `sonar_gt_status: HOLD`（`[实测]`，`out/_guard_test/provenance.json`、`plugin/out/_smoke_dataset/provenance.json` 都带这两条）。

### 4.9 S8b 距离带：`tools/rangeband.py`（会写 `out/<rec>/band.json`）

```bash
# 会覆盖该录音的 band.json；只想看数字，先把整个仓库复制一份再在副本里跑
$PY tools/rangeband.py --recording 2023-09-21_110229
```

`[实测]`（09:58，仓库副本，产物与 `out/2023-09-21_110229/band.json` 逐字节相同、md5 `3a59fb02…`）：

```
[rangeband] 2023-09-21_110229 status=unreliable_model n=533 band_rows=6
  P=[1.289, 1.424, -1.733] b=0.300 resid med 0.321 holdout med 0.322 p90 0.418 m
  single fixed point does not explain this recording (parameter on its bound (b)); band is the OBSERVED range spread, not a prediction
```

三个状态要分清（`out/<rec>/band.json` 的 `status`，也是卡片标签的分支）：

| status | 触发 | 带是什么 | 卡片/导出 |
|---|---|---|---|
| `model_ok` | 无参数撞界 **且** 留出 p90 ≤ 0.15 m | `ceil(p90/res)` 行的**预测**带 | `range band … (predicted ±N rows)` |
| `unreliable_model` | 有参数撞界（`b`/`P_z`/`P_xy`）或留出 p90 > 0.15 m | `max(6, ceil(3·MAD/res))` 的**观测散布** | `range band … (observed ±N rows; model rejected; NOT a prediction)` |
| `insufficient_detections` | 通过 `snr≥6` 且能连 gantry 的检测 < 12 条 | 无（`frames: {}`） | 本帧没有条目，卡片不画线 |

自查（读 `band.json`，不要只看 stdout）：

```bash
$PY - <<'EOF'
import json
b = json.load(open("out/2023-09-21_110229/band.json", encoding="utf-8"))
print(b["status"], b["n_detections"], b.get("band_rows"), len(b["frames"]))
f = b["frames"]["125"]
assert f["row_lo"] < f["row"] < f["row_hi"]
print(f)
EOF
```

`[实测]` 输出 `unreliable_model 533 6 533` 与 `{'range_m': 1.8489, 'row': 387, 'row_lo': 381, 'row_hi': 393}`。
**不要**把 `unreliable_model` 的带当先验去"在带内找目标"：它由同一批检测的距离分布按 MAD 修剪而来，
与候选同源（`docs/LIMITATIONS.md` §6.5 有完整说明与 5 条录音的读数）。

### 4.10 S8c 形状普查：`tools/census.py`（排先看哪条录音）

```bash
# 单条自查：--only 会关闭 refine，数字与 out/census 全量表不可比
$PY tools/census.py --only 2023-09-21_110229 --every 12 --refine-top 0 --out tmp/census_probe
# 全量 40 条：写 out/census/{census_v2.json,CENSUS-V2.md}（会覆写产物，本次未重跑）
#   $PY tools/census.py --every 1     # 10:12 的权威表就是这样生成的（rank_key=base）
```

`[实测]` 单条输出：

```
[ 1/1] 2023-09-21_110229 cov=0.32 band=0.00 trk=15 /45 jumps=6 geo=0.35(range_variation_below_fixed_object_lower_bound) score=0.111
```

读法：`cov` = 宽弧覆盖率（闸门阈值 0.45）、`band` = 被闸门删掉的采样帧比例、`trk` = 最长轨迹长 / 采样帧数、
`jumps` = 步长 > 0.03 m 的次数、`geo` = 几何可信度因子（1.00/0.70/0.50/0.35）、`score` = 综合分。
**它是"先看哪条"的排序器，不是"哪里有目标"的检测器**——顶部分高只说明"值得先排这条录音"。

### 4.11 S8d 补渲看不见候选的卡 + 按形状重排普查

```bash
# 1) 补渲：裁剪窗跟候选（默认 candidate），不写回主批目录
$PY engine/cards.py --proposals out/2023-09-21_110229/proposals.jsonl \
    --samples 2023-09-21_110229_0318 --crop-mode candidate \
    --out tmp/cards_supp_probe --gain 1
# [cards] tmp\\cards_supp_probe\\2023-09-21_110229\\2023-09-21_110229_0318__g1x.png
#         1513x1474  zoom=5  crop=[0, 66, 116, 206]  mode=candidate  prior=unavailable

# 2) 合并 supp 两批盲判（只写 judge_agreement_supp.json，不写 judgments/）
$PY tools/merge_supp.py
# [supp] n=4 po=1.0 kappa=undefined (pe=1, both judges used one label)

# 3) 按形状证据（base）重排：只覆盖 out/census/RANK-BY-SHAPE.md
$PY tools/rank_by_shape.py
```

补渲这一批的现成产物在 `out/2023-09-21_110229/cards_supp/`（4 张，`report.json` 里 `crop_mode: "candidate"`），
盲判在 `judge_a_supp/`、`judge_b_supp/`，合并是 `judge_agreement_supp.json`（`n=4, po=1.0, kappa=null`）。
**`kappa=null` 是"无法计算"**（两人只用了 `object` 一个标签，`pe=1`），不是 0、也不是 1；详见 `docs/LIMITATIONS.md` §9.7.1。
补渲卡的判定**不要**手工塞进 `judgments/`：那里的 12 条绑定主批冻结卡，sha 不同会被守卫拒收（§6）。

`rank_by_shape.py` 只回答"先看哪条"：它按 `base` 排序、把三道闸当警告列。原因是复合分把三闸乘在一起后
40 条全落在 0.000–0.058，名次由"哪道闸响了"决定，而闸考的几何可辨识性已知不成立（§4.9 的
`unreliable_model`）。**几何闸只能用来否决，不能用来认证**：`182317` 的 `base 0.128` 与 110229 的
`0.129` 几乎相同，但 54% 帧整幅覆盖（那是结构）。

---

## 5. 复核台服务

### 5.1 先查，别急着起

```bash
curl -s -o /dev/null -w '%{http_code}\n' --max-time 4 http://127.0.0.1:8771/
curl -s --max-time 4 http://127.0.0.1:8771/api/health
```

`[实测]` 03:19 时的状态：

| 端口 | 状态 | 说明 |
|---|---|---|
| 8771 | **200，已在跑**（03:21 时 pid 50776，03:19:56 起，`proposals_root` = `<repo>/out`） | 共享复核台，别重启；**pid 与 proposals_root 都会被别人换掉**（02:43 pid 52888 / root `tmp\review\proposals`；03:04 53312；03:10 37076；03:17 48856；03:19 50776 / root `out`），以 `/api/health` 现值为准 |
| 8765 | `000`（不在跑） | 空端口 |
| 8799 | 被 T-REVIEW 的 fixture 服务占用（pid 39908，`proposals_root` = `out`） | 别人的进程，**不要 kill** |

`/api/health` 返回 `{"ok": true, "service": "review", "port": 8771, ...}`。

### 5.2 起 / 停（只在你自己需要时）

```bash
cd plugin
$PY -m sonarllm.cli serve --port 8912        # 换端口自测
```

`[实测]`（在隔离副本上做的，端口 8912）：`GET /` 200 HTML、`/api/health` 200（含 `pid`）；启动时写 `tmp/review/server.json` 与 `tmp/review/server.pid`。

停（**先回到仓库根目录**，`server.pid` 在根的 `tmp/review/` 下，不在 `plugin/tmp/`）：

```bash
cat tmp/review/server.pid          # 取出 pid
taskkill /PID <pid> /F
```

`[实测]` `taskkill` 后端口关闭（curl 得到 `000`），CLI 包装进程返回码 1（无害）。

**两个坑：**
- `review/server.py:878-879`（`[仓库原文]`）在启动时**覆盖**写 `tmp/review/server.json` + `server.pid`。所以只要起第二个实例，先起那个的 pid 就丢了 —— 这就是"不要随手再起一个"的实际理由，不只是端口冲突。
- `plugin/sonarllm/cli.py` 只能以模块方式跑（`cd plugin && $PY -m sonarllm.cli ...`）；直接 `python plugin/sonarllm/cli.py` 会 `ImportError: attempted relative import with no known parent package`（`[实测]`，`cli.py:19`）。

---

## 6. 重渲卡片 = 旧判定作废

机制（`[仓库原文]`）：`judge.py:157-165` 要求判定文件里的 `card_sha256` 等于当前卡片文件的 sha256，否则判定非法。
后果：**任何一次重渲（换 gain、换 scale、换裁剪参数、甚至上游修 bug 后重跑）都会让此前的判定全部失效**，`check` 会逐条报 `FAIL ... 卡片已重渲染，判定需重做`。

正确顺序：

```bash
# 1) 先备份旧卡片 + 旧判定（判定要和它对应的那张卡一起存）
TS=$(date +%Y%m%d_%H%M)
mkdir -p "tmp/backup/${TS}_cards"
cp -r out/cards "tmp/backup/${TS}_cards/"
cp -r out/2023-09-20_171105/judgments "tmp/backup/${TS}_cards/"

# 2) 重渲（--proposals 吃 jsonl；--out 换成实际输出目录）
$PY engine/cards.py --proposals <records.jsonl> --out tmp/cards/rerender --gain 1,3,5

# 3) 重新生成判定清单，再人工重判
cd plugin && $PY -m sonarllm.cli manifest --recording 2023-09-20_171105
# 4) 判完再 check
$PY -m sonarllm.cli check --recording 2023-09-20_171105
```

`[实测]` `cp -r` 备份：`out/2023-09-20_171105` 共 4 个文件（`judgments/0622.json`、`judgments/_manifest.json`、`proposals.jsonl`、`reviews.jsonl`），源/目标文件数都是 4。
`rm -rf` 在这台环境的 wsl 工具里需要显式 `allowDangerous`；`mkdir /c/...` 会 permission denied，改用 `/mnt/c/...`（`[实测]`）。

**行带也是卡面的输入**：卡片上的两条虚线来自记录里的 `band` 字段（`row_lo`/`row_hi`），
而 `band` 来自 `out/<rec>/band.json`。所以 `band.json` 一变（换了 proposals、改了 `--min-snr`），
重渲出的卡片 sha 就变，旧判定同样作废——按本节顺序处理。当前 `rangeband` 对同一输入是幂等的
（`[实测]` 09:58 在仓库副本里重跑，产物与 `out/2023-09-21_110229/band.json` 逐字节相同，md5 `3a59fb02…`），
但那是"输入没变"的结果，不是保证。

---

## 7. 备份与回滚

- **`out/` 没有版本控制**，重跑会覆盖同名文件（`proposals.jsonl`、`reviews.jsonl`、`cards/*.png` 一律原地覆盖）。
- 动 `out/` 之前先按 §6 的 `cp -r` 备份到 `tmp/backup/<时间戳>_<内容>/`。回滚 = 用备份覆盖回去；**注意覆盖回旧卡片会让基于新卡片的判定失效**（sha 变了），两者要一起回滚。
- `out/calibration.json`、`out/prior_check.json` 是脚本产出的**可再生**文件，回滚价值低；`reviews.jsonl` 与 `judgments/*.json` 是**人工劳动**，必须备份。
- 一次只动一条录音：`out/<rec>/` 是天然的作用域。

---

## 8. 失败索引

| 症状 | 原因 | 处置 |
|---|---|---|
| `KeyError: "unknown recording ... known: [...]"` | `RECORDINGS` 表没有该录音 | 见 §3.2（需改源码） |
| `FileNotFoundError: missing .../aris_raw` | 数据盘没挂 / class_dir 拼错 | 查 `RAW_ROOT` 下实际目录 |
| `ImportError: attempted relative import with no known parent package` | 直接跑脚本文件 | `engine/track` 用 `$PY -m engine.track`；plugin 用 `cd plugin && $PY -m sonarllm.cli` |
| `ValueError: frame_data has neither 'img' nor image.path` | 用的是 03:12 及以前的 `cards.py`；或记录真的既无 `img` 也无 `image.path` | 更新到含 `proposal_to_record()` 的版本；echo 记录走 `--proposals`（§4.3） |
| `KeyError: "unknown recording '<目录名>'"` | `--proposals` 的录音名取自文件所在目录名 | 文件放进 `out/<recording>/`，或加 `--recording`（§4.3） |
| `rangeband` 打出 `status=insufficient_detections n=0` | 该录音没有能同时过 `snr≥6` 与 gantry 连接的检测（旧 echo proposals 常见） | **不是崩溃**，是数据结论；`frames: {}`、卡片不画带（§4.9） |
| 卡片上没有两条虚线 | 记录里没有 `band` 字段；`cards.py` 没有 `--band`，只有 `--band-h` | 由 driver 把 `band` 挂到每条记录上（`tmp/cards_110229/make_cards.py` 是现成例子；§4.9） |
| 卡面写 `candidate rows … outside crop` | 裁剪窗跟了行带（`crop_mode=band` 或记录里的 `crop_box`），候选在窗外（110229 有 4 帧如此） | 已修：`--crop-mode candidate` 重渲到 `cards_supp/`（`docs/LIMITATIONS.md` §7.7）。主批 12 张不要重渲——它们已冻结、判定绑 sha；补渲批单独盲判即可 |
| 候选数从 6 变 0，`drop` 由负变正 | `--mode` 默认值变成 `local` | 显式写 `--mode aligned` 并记录 mode |
| `card_sha256 与当前卡片不一致` | 卡片重渲过 | §6：备份 → 重渲 → 重判 |
| `n_exported: 0` | 没有合法 accept/revise，或复核是 fixture | §4.8 两道闸；不要用 `--allow-fixture`（CLI 也没暴露） |
| `error: --category or --all is required` | `mesh_prior.py` 少了主体参数 | 加 `--category <name>` 或 `--all` |
| bash 报某个 `C:/...` 文件不存在 | bash 不认盘符路径 | 用 `/mnt/c/...`，或先 `cd` 再用相对路径 |
| 中文输出显示成乱码 | 控制台代码页 | 不影响文件；需要看内容就 `read` 文件 |
| `URLError: 由于目标计算机积极拒绝，无法连接`（8771） | 服务正在被别的线重启（换 pid / 换 root） | 等几秒重试；`[实测]` 03:19:5x 自检时正好撞上一次重启窗口，重试即 200 |
| `tests/run_all.py` 有红 | 见下 | 现状 `PASS 119 / FAIL 0 / ERROR 0 / SKIP 0`（`[实测]`，10:12，17.9 s；lead 连跑 3 次一致），结果写进 `out/_qa/qa-results.json`。上一轮的 118/1 与 03:03 的 9/9/4 是历史快照（`docs/LIMITATIONS.md` §7.5）；若又出现红灯，先看是不是别人正在改 `engine/` |

测试现状（`[实测]`，`tests/run_all.py` 0.6 s）：ERROR 4 条一半是接口漂移（`range_window` 变成 tuple 属性 → `TypeError: 'tuple' object is not callable`；`intersect_bounds` 少了 `fov_deg_min` 键；`estimate_shift()` 多了一个必填 `band` 参数），FAIL 9 条里有 7 条是位移估计器本身的偏差（例如 `+7 → 5`、`−11 → −17`、`+13 → 8`、`−3 → −1`、441 行帧 `+6 → 3`），与 §4.6/§5.1 的口径②直接相关。

---

## 8.5 另一条检测路径：`engine/compact.py`（紧凑目标）

`echo.py` 的背景是**时域**局部中位，会把"相对声呐几乎不动"的目标一起减掉。若录音里的目标是紧凑点状
（形状普查宽度 <10 beams），走这条：

```bash
# 1) 先看形状（峰值行宽度小 = 紧凑目标；宽 = 整片扇面，换一条录音）
$PY -c "import sys;sys.path.insert(0,'.');from engine import compact as c;print(c.__doc__[:200])"

# 2) 全帧扫描（839 帧约 40 秒）
$PY -m engine.compact --recording 2023-09-21_105230 --every 1 \
    --snr 5.5 --min-area 12 --open 0 --out out/2023-09-21_105230/proposals.jsonl

# 3) 卡片（记得 --neighbors 2 才有 D 栏时间条）
$PY engine/cards.py --proposals out/2023-09-21_105230/proposals.jsonl \
    --recording 2023-09-21_105230 --frames 106,386,805 --out out/2023-09-21_105230/cards --neighbors 2

# 4) 判定 → 复核 → 导出（与 echo 路径完全相同）
cd plugin && $PY -m sonarllm.cli manifest --recording 2023-09-21_105230
$PY -m sonarllm.cli check    --recording 2023-09-21_105230
$PY -m sonarllm.cli export   --dst ../out/_dataset
```

判据（写死在模块 docstring 里）：宽度 ≥70 beams 的连通域一律 `role:"structure"`、`class_invariant:true`、
**永不进候选**——这是"别把罐壁标成炸弹"的硬闸。参数 `snr/min_area/open` 只在两条录音上看图定过，
**没有交叉验证**（LIMITATIONS §9.5）。

---

## 9. 接续验收清单

跑完一遍，以下都应成立（都能用命令复核）：

- [ ] `engine/geometry.py` 三条录音都能打印 `RES/WindowStart/WindowLength`，且 `predict()` 是 `gantry_not_sonar_frame`；
- [ ] `engine/echo.py --mode aligned` 在有亮带的帧上给出 >0 候选；`--mode local` 给出 0（这是 mode 差异，不是数据变化）；
- [ ] `engine/cards.py --selftest` 全过；
- [ ] `engine/mesh_prior.py --all --check` 打印 `all_pass: True`；
- [ ] `engine.track`（`-m`）复现 `drow_range [-5, 7]`、`auto_frac 1.0`；
- [ ] `sonarllm.cli status` 三行，`proposals` 列与 `out/<rec>/proposals.jsonl` 行数一致；
- [ ] `check` 的每条 FAIL 都能解释（卡片重渲 / 无判定）；
- [ ] 导出目录里 `provenance.json` 带 `candidate_only_not_training_ready: true`；
- [ ] 没有动 `D:\agent_workspace\水下\声呐目标检测`，没有 kill 别人的服务。

### 4.12 相机面板：重定时 SD 帧（默认视图）

发布的 `gopro/<frame>.jpg` 是用 SD 片段匹配出来的索引去切 FHD 片段，两段起点不同却没做补偿
（`out/CAMERA-RETIMED.md`：|offset| 中位 75 帧、最大 201）。所以默认视图改成"与这一帧同时刻的 SD 帧"。

```bash
# 1) 把某条录音需要的 SD 帧解出来（每条一次，~1 秒解码 + 十几 MB 磁盘）
python -m tools.sd_frames --recording 2023-09-21_105230

# 2) 自检：发布图应该落在"released"那一格，而不是"simultaneous"那一格
python -m tools.sd_frames --recording 2023-09-21_105230 --check 400
#   -> verdict: published_matches_released_slot   (ncc released 0.999 vs simultaneous 0.884)

# 3) 起服务，面板默认就是 SD 同时刻；点"发布图（早 N 帧）"切回旧视图
python review/server.py --port 8771 --operator <name> \
  --proposals out/<rec>/proposals.jsonl --cards out/<rec>/cards --judgments out
```

接口与失败语义（服务端不猜）：
- `GET /api/camera_sd/<recording>/<sonar_frame>` → JPEG，响应头带 `X-SD-Frame` / `X-Retime-Offset-Frames` / `X-Retime-Tier`。
- `404 no_retime`：该帧不在 `camera_retimed_index.csv` 里。
- `404 outside_sd_clip`：同时刻的 SD 帧落在片段之外（逐录音 0–82 帧，见索引里的 `in_clip`）。
- `404 not_extracted`：还没跑第 1 步；前端会**静默退回发布图并写明原因**，不会假装有定时视图。
- 标注框在 SD 模式下画成虚线并标注 `label@发布图`：label 是画在发布图上的，与同时刻帧之间隔着几十到两百帧的运动，**位置不对齐**。

## 4.13 把标注框搬到同时刻帧（可选，画在 `tracked` 绿框里）

```bash
# 单帧试（会打印 JSON，并给一张左发布图/右同时刻的两栏图）
python -m tools.cam_track --recording 2023-09-21_105230 --frame 400 --shot tmp/t400.png

# 整条录音预跑：结果写 out/camera_track/<rec>/<frame>.json，面板随后是秒开
python -m tools.cam_track_batch --recording 2023-09-21_105230
python -m tools.cam_track_batch --all      # 已在 out/camera_sd 里解过的全部录音
```

要点：
- 只在 `sd_released` 与 `sd_simultaneous` 两个槽位都在缓存里时才算（先跑 §4.12 第 1 步）。
- 失败不是错误：`round_trip_failed` / `low_ncc` / `outside_sd_clip` 都会退回虚线框，页面写明原因。
- 改了 `tools/cam_track.py` 的判据就要 `rm -rf out/camera_track` 重跑，否则读的是旧结论。
- 语义：平移跟踪，不是重标。它回答"你框的那块东西现在在哪"，位移里同时含相机运动和物体自身运动。
