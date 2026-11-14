# QA 报告 — sonar_llm_annotation

日期：2026-11-12 · 线：sonar_llm_annotation（独立线）· 执行：t-qa（QA 线，只写 `tests/`、`out/_qa/`、本文件）
证据层级：**【实测】** = 本目录脚本复算；**【源码】** = 读代码得到的行为；**【推断】** = 未证实假设。

---

## 0. 结论摘要

| 项 | 读数 |
|---|---|
| 用例总数 | **108** |
| PASS | **108**（结项前最终状态；交报告时为 98/10/0，10 条已全部修掉） |
| FAIL | **0** |
| 最终复跑 | `python tests/run_all.py` → `PASS 108  FAIL 0  ERROR 0 (13.5s)`，2026-11-12 03:39 |
| ERROR | 0 |
| 覆盖 | 单元（geometry / echo / track / mesh_prior / cards）、确定性、插件 CLI、judge 归一化、dataset 导出、端到端、异常路径、并发、HTTP 服务 |
| 端口 | 只用 8772 / 8773；测完已释放（§5） |

**最重要的三条（会直接污染产出，优先级从高到低）**

1. **F1** `engine/echo.py:estimate_shift` 在默认 `band=None` 时不满足「已知整数平移 ±1 行」判据：`drow=+7 → +3`、`drow=−7 → −3/−4`；历史「永远返回搜索窗下界 −40/−160」的**主入口已修**，但**退化 band 时仍会静默返回 `drow=−160`**，且大位移错误时 `clipped=False`（不报警）。
2. **F2** `plugin/sonarllm/dataset.py:export` 的 `provenance.json` 里 `n_exported` / `n_unassigned` 数的是 **staged 行**而不是**落盘文件**（实测 `n_exported=4` 而磁盘 3 个 label、`n_unassigned=2` 而磁盘 1 个），审计链条上的数字与产物不一致。
3. **F6** `review/server.py` 的「端口占用就拒绝启动」守卫在 **Windows 上无效**：`HTTPServer.allow_reuse_address=1` ⇒ `SO_REUSEADDR` 允许两个进程绑同一端口，第二个实例静默开始服务。**同一进程能起两个服务，产物会写进同一份 reviews.jsonl**。

另外 **F3**（导出到已存在非空目录不拒绝、不记录）、**F4**（坏 `reviews.jsonl` 行静默消失且 provenance 不留痕）、**F5**（零条已确认复核仍写出 `data.yaml`）三条都属于「静默通过」，与 task-5 §5「必须明确报错」口径不符。

---

## 1. 方法与可复现性

```bash
cd sonar_llm_annotation
# 全量（约 35 s）
PYTHONIOENCODING=utf-8 /mnt/c/Users/ASUS/AppData/Local/Programs/Python/Python312/python.exe tests/run_all.py
# 单模块
PYTHONIOENCODING=utf-8 .../python.exe tests/run_all.py --only 02
# 列用例
PYTHONIOENCODING=utf-8 .../python.exe tests/run_all.py --list
```

- 本机**没有 pytest**（`import pytest` → ModuleNotFoundError），也未安装 cv2 / scipy / skimage；`tests/run_all.py` 是自写的零依赖 runner：按定义序跑 `test_*`，`PASS/FAIL/ERROR` 三级，FAIL 带 `文件:行号`，结果写 `out/_qa/qa-results.json`（含 `counts`、`sources_tested`、`sources_changed_during_run`）。
- 每次运行**记录被测源文件的 sha256 前后值**；若期间被其他线改动会打印 `WARNING: sources changed during the run`。最终全量跑（03:19）`sources_changed_during_run = []`，读数对应的源码指纹：

| 文件 | sha256 前缀 |
|---|---|
| `engine/cards.py` | `18fd08b3` |
| `engine/echo.py` | `950340aa` |
| `engine/geometry.py` | `bd3daa34` |
| `engine/mesh_prior.py` | `3bccf66f` |
| `engine/track.py` | `8a086e8d` |
| `plugin/sonarllm/{__init__,__main__,cli,dataset,judge}.py` | `9207131c` / `307299fd` / `0d268c98` / `791bdd75` / `c7d1c53b` |
| `review/server.py` | `d8c44ca4` |

- 写入域：所有产物在 `out/_qa/**`；未改 `engine/`、`plugin/`、`review/` 任何字节；未触碰 `out/<真实录音>/`（模块级 `OUT`/`OUT_DIR`/`TMP_DIR` 在测试内被重定向）。唯一例外见 §5：8773 子进程启动时的 pid/json 记录被重定向到 `out/_qa/srv/tmp/`，**没有覆盖 8771 审阅线的 `tmp/review/server*.json`**。

---

## 2. 逐模块结果

| 模块 | 用例 | 结果 | 覆盖要点 |
|---|---|---|---|
| `test_01_geometry` | 12 | 12 PASS | 帧清单=磁盘、header 780/441、WindowStart/Length、`range_window` 顶部 441≈2.01 m vs 780≈3.02 m、row↔range 往返、`predict()` 必为 unavailable+reason、`beam_angle` 必须显式 FOV、`fov_bound`/`intersect_bounds`、未知录音 KeyError |
| `test_02_echo_shift` | 13 | 10 PASS / **3 FAIL** | 显式列完整 band 下 4 帧×15 位移全精确；默认 band 的 ±7 精度、合成夹具、搜索界、`clipped` 语义、dbeam、退化 band 信号、441 帧、track/echo 一致 |
| `test_03_track` | 12 | 12 PASS | `masked_mean_profile` 退化置零、`best_lag` 已知 lag、`band` 必填 TypeError、`track_path` 形状/范围/keyframe KeyError、`propagate` 框在界内、441 录音、`clip_box`、`box_contrast` |
| `test_04_mesh_prior` | 9 | 9 PASS | 球体 `2·asin(R/r)` 与列宽解析式误差 <0.1 px、441/780 同一 row 标尺、长轴 1.5 px、mask 合法 + `mask_sha256`、跨进程一致、`uniqueness is False`、`plausible_sweep`/`sweep_summary`、未知类别 KeyError |
| `test_05_cards` | 11 | 11 PASS | PNG 尺寸=meta、`out_sha256`、候选框回落链**绝不用 predicted**、`available=False` 时强制也不画、逐字节可复现、441 卡尺寸、退化候选标注、结构带/背景带标记、`write=False` 不落盘、meta JSON-safe |
| `test_06_determinism` | 6 | 6 PASS | 跨进程 + `PYTHONHASHSEED 0/12345`：silhouette / cards PNG / echo / background / track_path / judge manifest 逐字节一致 |
| `test_07_plugin_cli` | 6 | 5 PASS / **1 FAIL** | `--version`、`status`、未知子命令非零、`manifest`（有卡/无卡 rc=1）、`check` rc=0/1/2、`export` 真子进程产物与 provenance、**非空 dst 不拒绝（F3）** |
| `test_08_judge_normalize` | 14 | 14 PASS | `frame_h` 逐录音 780/441、合法归一化、verdict/shape/box 位数/退化/越界（441 用 441 判）/object 无框/confidence/sample 前缀/缺 sample/`card_sha256` 不符/非 dict 全部拒绝并给理由 |
| `test_09_dataset_export` | 6 | 4 PASS / **2 FAIL** | split 只来自 manifest `paired_role`、无 role → `unassigned`、fixture/unknown_category/pgm_missing/rejected 不导出、YOLO 5 字段且 [0,1]、441 归一化、PNG 128×780 vs 128×441、provenance 全键 + HOLD、真实 manifest 统计；**计数与落盘不符（F2）** |
| `test_10_e2e_pipeline` | 4 | 4 PASS | proposals.jsonl → cards → judgments → HTTP 201 → `reviews.jsonl` → `data.yaml`；bomb 780 归 `val`、mortar 441 无 role 归 `unassigned`；框回算一致；`data_source=human`；`card_sha256` 钉住卡片 |
| `test_11_error_paths` | 9 | 6 PASS / **3 FAIL** | 截断 PGM、P2 PGM、`detect` 无背景/坏 mode、`decode_frame` 无图、cards CLI 缺 proposals 都明确报错；**坏 reviews 行（F4）、空导出（F5）、非空 dst（F3）** 三条静默通过 |
| `test_12_concurrency` | 2 | 2 PASS | 两进程各 150 行追加到同一 `reviews.jsonl`：300 行全部可解析、无半行、无重复；20 个并发 POST 全部 201 且逐行合法 |
| `test_13_server` | 4 | 3 PASS / **1 FAIL** | 8772：`/` 200、`/api/health`、`/api/proposals|record|card|judgment|reviews`、404 矩阵、POST 400/404/201、box 按录音 grid 裁剪；8773：真子进程启动/应答/终止；**忙端口守卫失效（F6）** |

---

## 3. 缺陷清单

### F1（高）`estimate_shift` 在默认 band 下不满足 ±1；退化 band 仍返回搜索界垃圾值

**证据【实测】**（`test_02_echo_shift`，13 用例中 3 FAIL）

同一估计器，**只换 band**：

| 帧 | 位移 | 显式 `band=np.ones` | 默认 `band=None`（→`structure_band(b)`） |
|---|---|---|---|
| `2023-09-21_100927` 300 | +7 | **+7**（score_row>0.999） | **+3**（score_row=0.426，band_rows=69） |
| `2023-09-20_171105` 622 | −7 | **−7** | **−3**（score_row=0.582） |
| `2023-09-20_171105` 900 | −7 | **−7** | **−4**（score_row=0.740） |
| `2023-09-21_120653` 400 | −7 | **−7** | **−3**（score_row=0.582） |
| 合成宽脊夹具 seed 11 / 12 | +7 | — | **+5 / +0**（band 3.0%、58 行、profile std 0.32/0.35） |

显式全帧 band 时 4 帧 × 15 个位移（−41…+41）**全部精确** ⇒ `masked_mean_profile`/`best_lag` 的数学是对的，问题出在 `structure_band` 生成的、逐行列子集不同的薄 mask 上；masked mean 每行取不同列子集，整幅平移后并非精确移位复制。

**另一个入口（历史症状未彻底关闭）**：band 只有 3 行（<8 有效行门槛）时 `masked_mean_profile` 返回全零 → `best_lag` 每个 lag 分母为 0 → 返回**第一个 lag**，即 `drow=-160`、`score_row=-1.0`、`clipped=True`。当前实现靠 `clipped=True` 提示，但 `drow` 是垃圾值，下游若只看 drow 会当成真实位移。

**大位移静默错误**：`|drow|≥13` 且用默认 band 时误差可达 +48…+92 行（如 622 帧 +41 → +92、grenade 400 帧 +13 → +31），且 `clipped=False` ⇒ 调用方无法区分「准」与「错」，只能自己设阈值。

**影响**：`track_path` 的 chain/direct 对齐、`propagate` 的框传播在真实帧间（实测 drow 多为 0/−1，score 0.93–0.94）**目前安全**；但任何依赖默认 band 做**跨帧大位移**（丢帧、跳帧、拖拽重定位）的用法都会拿到错值。

**最小复现**

```bash
cd sonar_llm_annotation
PYTHONIOENCODING=utf-8 .../python.exe tests/run_all.py --only 02
# 只看扫描表（4 帧 × 15 位移，默认 band 与全帧 band 对照）
PYTHONIOENCODING=utf-8 .../python.exe out/_qa/probe_echo_sweep.py
```

**结论边界**：历史「永远 −40」的主入口已确认修复（本次 4 帧 × 15 位移无一返回搜索界）；这是**部分修复**，不是已解决。

### F2（高）`provenance.json` 的 `n_exported` / `n_unassigned` 与磁盘不符

**【实测】** 构造 6 个复核样本（3 个合法、1 个 mixed role、1 个 unknown category、1 个 pgm_missing）导出后：

- `n_exported = 4`，磁盘 `labels/**/*.txt` = **3**；
- `n_unassigned = 2`，磁盘 `labels/unassigned/*.txt` = **1**。

原因【源码】`dataset.py` 的 `role_count[split] += 1` 与 `staged.append(...)` 发生在 `find_pgm()` **之前**；`pgm_missing` 的样本已经计入统计，随后才 `continue`。

**影响**：provenance 是这条线唯一的审计凭据；「写了 4 条」而实际 3 条会让下游统计（每录音条数、split 比例）系统性偏高，且偏高幅度 = 后期拒绝数（不固定）。

**最小复现**

```bash
PYTHONIOENCODING=utf-8 .../python.exe tests/run_all.py --only 09
# 断言原文：provenance claims n_exported=4 but 3 labels exist on disk
```

### F3（中）导出到已存在的非空目录：不拒绝、不记录、直接覆盖

**【实测】** `python -m sonarllm export --dst <已有 1 个无关文件的目录>` → `exit 0`，`data.yaml`/`provenance.json` 被覆盖，无关文件保留，provenance 里**没有任何** `pre_existing_files` 记录。CLI（`test_07`）与直接调 `ds.export`（`test_11`）两条路径都一样。

**影响**：两次导出会静默合并成一份「看起来完整」的数据集；旧 `data.yaml` 指向的图片可能属于上一次实验。

### F4（中）`reviews.jsonl` 坏行静默消失，且 provenance 不留痕

**【实测】** 2 行文件（1 合法 + 1 截断）→ `dataset.read_reviews` 返回 1 条，无异常、无警告；导出后 `provenance.json` 键表里没有 `n_bad_review_lines` 之类字段。对照：`review/server.py:read_reviews` **有** `(latest, n_writes, n_bad)` 三元组并正确计 1 条坏行（`test_11` PASS）。

**影响**：一条人工复核可以在磁盘上「消失」，而报表里只表现为 n 少 1，无法定量对账。

### F5（中）零条已确认复核仍写出 `data.yaml`

**【实测】** `reviews.jsonl` 为空 → `export()` 正常返回 `n_exported=0`，并写出 `data.yaml`（`train: images/train`、`val: images/val`）。训练器会把空目录当成合法数据集读入，得到「无样本的 0 指标」而不是「数据缺失」。

**期望**（本报告口径）：`n_exported == 0` 时要么拒绝导出，要么不写 `data.yaml`，或至少写 `empty: true`。

### F6（中）忙端口守卫在 Windows 上失效：两实例可同绑 8773

**【实测】** 8773 已有实例在服务时，用同一 `main()` 再起一个：第二个进程**成功绑定并开始服务**（输出 `review service listening on http://127.0.0.1:8773 (pid 47480)`），20 s 后仍存活；`/api/health` 返回的是第一个实例的 pid。代码里的 `ERROR: cannot bind ... refusing to auto-switch ports` 分支从未触发。

原因【源码+平台事实】：`http.server.HTTPServer.allow_reuse_address = 1`，Windows 上映射为 `SO_REUSEADDR`（而非 POSIX 语义的 TIME_WAIT 复用），允许**第二个监听者**绑定同一地址；`bind()` 不抛 `OSError`，`main()` 的 `try/except` 不会走到。

**影响**：两个审阅页同时指向同一 `out/<recording>/reviews.jsonl`；追加本身是原子的（`test_12` PASS），但「谁写的是哪一份」失去意义，且 `/api/health` 无法用来判断该杀哪个 pid。

**修复建议（不在本线改代码）**：`class Server(ThreadingHTTPServer): allow_reuse_address = False`（Windows 上再加 `SO_EXCLUSIVEADDRUSE`），或在 `main()` 里先 `socket.create_connection()` 探测端口再 bind。

**最小复现**

```bash
PYTHONIOENCODING=utf-8 .../python.exe tests/run_all.py --only 13   # 最后一条用例，约 21 s
```

### O1（文档不一致）`BRIEF.md:19` 写「高=780 samples」，实测两条录音是 441

**【实测】** `BRIEF.md` 第 19 行：「P5 灰度，**宽=128 beams，高=780 samples(距离)**」。而 `docs/RUNBOOK.md:69-70`、`docs/FINAL-REPORT.md:96-97` 与几何 header 都记 `2023-09-21_120653` / `2023-09-21_100927` = **441**。

**影响**：新读者（含 Agent）会照 BRIEF 硬编码 780。本套件对「任何 780 硬编码」的守护点为：`test_01`（header 逐录音）、`test_08`（`judge.frame_h` 必须读 PGM 头，441 的越界框用 441 判）、`test_09`（YOLO 用真实高度归一化）、`test_05`（441 卡尺寸）、`test_10`（导出 PNG 128×441）、`test_13`（服务 grid 按录音）。当前**代码侧全部通过**；只有 BRIEF 文字是错的。

### O2（契约观察）`POST /api/review` 强制要求 `final_box`

**【实测】** `status=uncertain|reject` 且不带 `final_box` → 400 `final_box must be [x0,y0,x1,y1]`（`review/server.py:957-959`）。即「我看不清/没有目标」这类判定也必须编一个四元框才能落盘。

若前端总是回填候选框，这是可接受的设计；但作为 HTTP 契约，它使「无框判定」不可能，且会让 `uncertain` 行带上一个并非操作者确认的框。**建议**：`uncertain`/`reject` 允许 `final_box=null`，落盘时写 `final_box: null` 并保留 `candidate_box`。

---

## 4. 已验证正确的关键点（不要重复怀疑）

- **silhouette 解析式【实测】**：球体 d=0.2 m、r=1.0 m 时列宽 11.2993 px（解析 `2·asin(R/r)/θ`=11.25，误差 <0.1 px）、行跨 67.0354（解析 `2R/row_m`=67.06）；bomb 长轴 yaw=90 时 40.60 px vs 39.8（0.8 px）。**注意**：这只证明实现与**配置的 FOV=130°** 自洽；FOV=130° 本身已被 `docs/FINDINGS.md` §三 的退化不变量证伪（θ∈[15.4°,67°]），本报告不据此宣称几何正确。
- **逐录音帧高**：geometry header / `judge.frame_h` / 卡片 / 导出 YOLO / 服务 grid / provenance 全部按真实 PGM 头（780 / 441 / 441）走，无 780 硬编码（`test_01/05/08/09/10/13` 共 20+ 断言）。
- **manifest 与 unassigned**：26761 items，**4746 带 `paired_role`（17.7%）**；`sample_roles()` 返回 4746 个样本且全部有 role；27 条录音跨 role（所以必须按 sample 而非按 recording 取）。无 role 的样本导出到 `images|labels/unassigned/`，`data.yaml` **不含** unassigned，`unassigned_note` 明写「不得被默认塞进 train」。
- **YOLO 行**：5 字段、`[0,1]`、按该录音真实高度归一化（bomb `cy·780`、mortar `cy·441` 都与框中心一致到 <0.02 px）。
- **判定归一化**：非法 verdict / shape / 框位数 / 退化框 / 越界（含 441 录音）/ `object` 无框 / confidence 越界 / sample 不属于录音 / `card_sha256` 不符 / 非 dict —— **14/14 全部拒绝并给理由**。
- **卡片**：`predicted.available=False` 时**即使 `draw_predicted=True` 也不画**（不越权造预测）；候选框回落链 `candidate → echo.rank0 → 默认框`，**绝不**用 predicted 充候选；同记录逐字节可复现；441 录音卡片 1122×1600、`row_scale=441`。
- **确定性**：5 个模块在跨进程 + 不同 `PYTHONHASHSEED` 下逐字节一致（含 `judge` manifest 的键序）。
- **并发**：两进程各 150 行并发追加 → 300 行全部可解析、无半行、无重复；20 并发 POST 全部 201 且逐行合法 JSON（`O_APPEND|O_BINARY` + 单次 `os.write` 成立）。
- **异常路径**：截断 PGM、P2 PGM、`detect()` 无背景 / 未知 mode、`decode_frame` 无图、cards CLI 缺 proposals、未知录音、keyframe 缺失 —— 全部明确报错（`test_11`/`test_03`/`test_01`）。
- **服务**：`/`、`/api/health`、`/api/proposals`、`/api/record`、`/api/reviews`、`/api/card`（真 PNG）、`/api/judgment`、未知路由 404、POST 400 矩阵（缺 sample / 坏 status / 3 元 final_box / 退化框 / 非 JSON 对象）、未知 sample 404、成功 201 且 box 按该录音 grid 裁剪 —— 全通过。

---

## 5. 端口与进程确认

| 端口 | 用途 | 测时 | 测后 |
|---|---|---|---|
| 8771 | t-review 审阅线（**他人**） | 未监听 | **未触碰**；`netstat` 显示 PID 48856 仍在 LISTENING（该线自己的服务） |
| 8772 | 本套件 in-process 全量 API + 20 并发 POST | LISTENING | **无 LISTENING**（仅 TIME_WAIT），`port_is_free(8772)` = True |
| 8773 | 本套件真子进程 `main()` 启动/应答/终止 | LISTENING | **无 LISTENING**（仅 TIME_WAIT），`port_is_free(8773)` = True |

- 两个端口在各自用例的 `finally` 里 `shutdown()/server_close()` 或 `terminate() + wait()`，并**在测试内用 socket 连接断言已释放**（不是只看日志）。
- `netstat -ano | grep :877x`：8772/8773 只有 `TIME_WAIT`（TCP 拆除态，非监听），8771 是审阅线的服务。
- 8773 子进程的 `server-8773.json/.pid` 被重定向到 `out/_qa/srv/tmp/`，**没有**写 `tmp/review/server*.json`（否则会覆盖 8771 的 pid 记录）。为此 `tests/_serve_child.py` 在调用 `main()` 前先改模块级 `TMP_DIR`。

---

## 6. 未覆盖 / 限制

1. **前端交互未测**：`review/static` 的 DOM 行为（拖框、缩放、键盘）没有在真实浏览器里驱动；只测了 HTTP 契约与静态 `index.html` 可返回。
2. **`plausible_sweep` 只验 `backend="hull"`**：`shadow` 光栅在大姿态下的行为未逐个断言。
3. **`test` 划分未读取**（遵守 AGENTS.md 第 7 条）；本套件只碰 `train/val/val_id/None`。
4. **性能与内存未测**：`background_model(n_sample=121)` 全量耗时、卡片批量渲染的峰值内存没有基准。
5. **`<engine>` 在测试期间被其他线持续修改**：`echo.py`（03:03）、`cards.py`（03:19）、`server.py`（03:20 起多次）都动过；本报告的读数对应 §1 的 sha 表，**若之后再改，需重跑 `tests/run_all.py` 再引用**。
6. **F1 的 ±1 判据只在「整幅图按已知整数平移」的合成场景上定义**；真实帧间位移多为 0/−1 行，实测 score 0.93–0.94，故该缺陷**当前不影响已有轨迹产物**，只影响未来大位移用法。

---

## 7. 附录：读数在哪里

| 内容 | 路径 |
|---|---|
| 机器可读结果（含每用例耗时/消息/源码 sha） | `out/_qa/qa-results.json` |
| echo 默认 band vs 全帧 band 扫描表 | `out/_qa/probe_echo_sweep.py` 运行输出 |
| 端到端产物（proposals/cards/judgments/reviews/data.yaml/provenance） | `out/_qa/e2e/` |
| 导出异常路径样本 | `out/_qa/err/`（每个子目录一个失败场景） |
| 服务测试树（proposals/cards/judgments/tmp） | `out/_qa/srv/` |
| CLI 真子进程产物 | `out/_qa/cli/` |

复现全部结论只需两条命令：`tests/run_all.py`（约 35 s，含 8773 子进程用例的 21 s）+ `out/_qa/probe_echo_sweep.py`。

---

## 9. 结项前的最终状态（lead 复跑，覆盖上面 §0–§8 的历史读数）

`python tests/run_all.py` → **PASS 108 / FAIL 0 / ERROR 0（13.5 s）**。

10 条历史 FAIL 的归宿：

| 编号 | 处置 | 证据 |
|---|---|---|
| F1 echo 默认 band 精度 | **已修**（`_support_profile()`：band 只定支撑范围，profile 在全宽正交轴平均；退化输入 `ok=False`） | `test_02` 13/13；合成帧 +7→+7（score 1.0000） |
| F2/F3/F5 导出计数与空集 | **已修**（先落图再落标签、只数真正写成功的、非空 dst 拒绝、零条不写 `data.yaml` 改写 `_EMPTY_DO_NOT_TRAIN.txt`） | `test_09` 6/6、`test_11` 9/9 |
| F4 坏 JSON 行静默丢弃 | **已修**（`read_reviews_counted()` 返回 `n_bad`，provenance 记 `review_log_stats`） | `test_11` |
| F6 忙端口守卫失效 | **已修**（`SO_EXCLUSIVEADDRUSE` + 关 `allow_reuse_address` + 预检，二次启动 rc=2） | `test_13` |
| O1 BRIEF 写死 780 | **已修**（`BRIEF.md` §1 改逐录音） | `test_01` |
| O2 reject 也要求 final_box | **已修**（accept/revise 必填且 revise 必须与候选不同；reject/skip/uncertain 存 `null`） | `test_13` POST 矩阵 |

三处**测试**（不是被测代码）按新契约改了断言，清单见 `tests/test_10_e2e_pipeline.py`、`tests/test_11_error_paths.py`、`tests/test_13_server.py` 的行内注释：revise 的框必须与候选不同、混合 role 的样本必须避开、拒绝目录要在"预检"与"bind 失败"两条路径间二选一。

结项时新增的模块 `engine/compact.py`（单帧块中位背景 + 结构宽度排除）由 lead 写完并实测，**不在本报告的 108 条里**——它的验收在 `docs/FINDINGS.md` 第十节（837/839 帧有候选、相邻帧质心位移中位 0.71 px）。

---

## 10. task-15：rangeband 行带 + 卡片行带（新增 11 条，覆盖 §9 的计数）

`python tests/run_all.py` → **119 条 / PASS 119 / FAIL 0 / ERROR 0 / SKIP 0（15 s）**。
§9 的 108 条仍然全绿（`test_02` 13/13、`test_07` 6/6、`test_09` 6/6、`test_11` 9/9、`test_13` 4/4），本轮没有为通过而改任何旧断言；唯一一次期望变更见 §10.1，是 lead 裁决后的**规格**变更，不是放宽被测代码的语义。

新增：`tests/test_14_rangeband.py`（7 条）、`tests/test_15_cards_band.py`（4 条）；runner 增加 SKIP 状态（`tests/_util.SkipTest`，本轮 0 次使用），`_util.source_hashes()` 增加 `tools/*.py`。测试时指纹：`tools/rangeband.py` `0cd80b9589eb`、`tools/locate.py` `24ceaceef50a`、`engine/cards.py` `e140dfacc4ca`、`engine/compact.py` `4153235f9d2e`、`plugin/sonarllm/dataset.py` `602a92159b9f`、`review/server.py` `748accd35fb1`。

### 10.1 B1 结案：门禁正确，规格改口（lead 裁决 ①）

首轮唯一的 FAIL 是「规格期望 `model_ok` vs 代码判 `unreliable_model`」。lead 裁决：**改规格，不动门禁**——`abs(abs(b) - B_HI) < 1e-3` 这一票否决保留，它是这条门禁的全部意义。

| 读数 | 值 |
|---|---|
| 期望（裁决后） | `status == "unreliable_model"`、band 走观测带宽分支 |
| 当前代码 | `unreliable_model`、`band_rows = 25`、`frames = 837` |
| 残差 | in-sample p90 **0.0782 m**、留出 p90 **0.1178 m**，两条都 ≤ 0.15 m |
| 撞界证据 | `bounds_active = {"b": True, "z": True, "xy": False}`：`b_m = -0.300000`（恰在 `B_HI`）、`P = [1.373684, 1.455527, -1.999511]`（`P_Z_LO = -2.0`） |
| 带宽 | `3*MAD/res = 24.90 → 25` 行，837 帧共用同一 `row = 253`（退路不伪造逐帧预测） |

裁决理由（也写进了 `tests/test_14_rangeband.py` 的 docstring，不只留在回执里）：两个参数同时压在搜索界上，说明数据没有选中它们、是优化器顶到了墙；此时 in-sample 0.078 m 与留出 0.118 m 再漂亮也不构成"解出来了"，因为 `(P_radial, b)` 沿一条平坦谷底可以互换而残差几乎不变（1.5 m 距离上平台只移动约 0.2 m，杠杆臂太短），正是原仓库 docstring 里点名的退化。

落地为三条锁：
1. `test_a_fit_that_rests_on_its_bounds_is_rejected_even_though_the_residuals_pass`：真实 105230——先断言残差两条都过 0.15（证明不是精度判掉的），再断言 `bounds_active` 精确等于 `{b: True, z: True, xy: False}`、`b_m` 与 `P_z` 各在界上 1e-3 内（撞界是被**识别**的，不是碰巧），最后按 `3*MAD/res` 重算带宽并断言 837 帧共用一行、note 写明 `bound` 与 `not a prediction`。
2. `test_a_depth_pinned_to_its_bound_is_rejected_even_with_a_perfect_holdout`：合成——`P_z` 钉在 `P_Z_LO`、留出完美，仍须 `unreliable_model`。
3. `test_the_veto_sits_exactly_on_the_bound_not_somewhere_near_it`：合成同批量检测、同 0.05 m 留出，只有 `b` 不同——`b = 0.29`（界内）→ `model_ok` 且带宽 `= ceil(0.05/res)`；`b = 0.300001`（压界）→ `unreliable_model`。两条路径都被钉住，不依赖真实数据的偶然性。

**O3（已知残留，未修）——"拒了模型反而更窄"**：105230 的退路带宽 **25 行**反而窄于被接受时本会给出的 **40 行**（`ceil(0.1178/0.0029826)`）。原因是 `3*MAD` 取 50% 分位附近的稳健尺度，而该录音残差尾部重（max 0.2795 m、p90 0.0782 m），MAD 严重低估。

lead 裁决（2026-11-12）：**这一轮不改代码，只记录**。卡片已冻结（12 张卡里嵌了 band 数值 381–393），判读员 A/B 正按当前 sha 判读，此时改 `3*MAD` 口径会让 `card_sha256` 守卫把这批判读全部作废，代价大于收益。矛盾本身是真的：读者容易把"更窄"误读成"更确定"，这一轮靠标签 `observed … NOT a prediction` 兜住，属已知残留风险。

下一轮二选一：① 退路取 `max(3*MAD, hold-out p90)`（保守合并，25 → 40 行）；② 干脆不画带——不是预测的带只是重复检测器输出。

### 10.2 其余 5 条按规格通过（证据）

| 规格 | 结果 | 证据 |
|---|---|---|
| ② `2023-09-21_110229` 必须自曝 | PASS | `unreliable_model`、band 6、frames 533、in-sample p90 0.4186 / 留出 0.4177、`b_m = +0.300000`；note 含 `does not explain this recording` 与 `not a prediction`；533 帧共用同一 `row`（不伪造逐帧预测） |
| ③ <12 条检测 | PASS | 11 条 → `insufficient_detections`、`frames == {}`、无 `band_rows`、不抛异常；无 proposals 文件同样 |
| ④ 0.15 切换 | PASS | stub 驱动**留出** p90：0.1499 → `model_ok`，0.1501 → `unreliable_model`；模型带随 p90 单调不减；退路三次相同且 ≥ 模型带；in-sample 恒 0.01 m 仍被拒 → note 必须写 `hold-out` 与 `0.40`（证明门禁看留出、不看 `residual_m`） |
| ④ 补充 可辨识性 | PASS | 人为把 `P[2]` 钉在 `P_Z_LO` 且留出残差完美 → 仍 `unreliable_model` 且 note 含 `bound`（105230 被判掉的同一机制） |
| ⑥ CLI | PASS | `RB.main(["--recording", …])` rc=0、stdout 含 `status=` 且与 `build()` 同值、`band.json` schema 与帧集一致；`python -m tools.rangeband --help` rc=0 |
| ⑤ 卡片行带 | PASS | 110229 卡面 label `range band … (observed ±6 rows; model rejected; NOT a prediction)`，`meta["band"]` 记 row_lo/row_hi/status；amber 像素 464（不传 band 时 0，对照同一像素检查可失败）；footer 末段是 `engine_version compact/v0`，而 `cards.ENGINE_VERSION == "v1"`（证明来自记录而非渲染器默认）；`meta["input"]` 指向真实 `15cm_mortar/…/aris_raw/0125.pgm`，全卡无 `dryrun` |

`model_ok` 的措辞（`predicted ±N rows`）用构造的 `model_ok` 条目单独测，因为 105230 目前拿不到该状态——测的是"标签是状态的函数"，与门禁裁决解耦。

### 10.3 复现

```
python tests/run_all.py            # 119 条，约 15 s
python tests/run_all.py --only 14  # 只跑 rangeband
python -m tools.rangeband --recording 2023-09-21_105230
```

本轮不启服务，未触碰 8771（t-review）与 8765（主 Agent）；§5 的端口确认仍然有效。收尾实测：8772/8773 socket 探测 `closed`，8771 `OPEN`（t-review 的服务，未碰）。

读数可审计性说明：最后一次全量跑到 119/119 时，runner 报 `sources changed during the run: tools/census.py`（另一条线正在改该文件）——这说明 runner 的 source hash 前后对比确实能抓到并发改动，值得保留。`census.py` 不在本轮覆盖范围内（覆盖的是 `tools/rangeband.py`、`tools/locate.py`、`engine/cards.py`、`engine/compact.py`），其 sha 变化不影响 119 条的任何断言；引用该次读数时请注意这一条。
