# Camera-only teacher：分支与配置独立审计

日期：2026-11-10。范围：CMOLD（DOI 10.1109/ACCESS.2026.3666096）目标下的现有 camera-only baseline；不判断未披露的论文设置。证据顺序为当前代码/配置、原始数据及运行产物、仓库历史；不把先前 AI 报告当作原始证据。未运行训练或评测，未读取 test 样本，未修改原研究目录或其 Git 状态。

## 结论先行

**保留** `t_camera_s_yoloxs.py` 作为单一 seed、同录音近邻帧 val 上的 camera-only 候选，以及 P2 几何诊断臂；**不要**把它们称为已验证的未见录音教师或论文协议复现。它确实只训练相机头，沿用主线的 YOLOX-S、COCO backbone/neck 初始化、SGD 和 EMA 家族，但数据、几何、增强及训练预算均不是 E11/E13 的简单继承。

**保留但不混用** `e11_bcam` 与 E13-cam：它们回答各自 uxo_full / dense 平台上的问题，配置、数据密度、曝光次数和指标均不能与 830 帧 val 直接相减。**停止将 `s0_c0_camera_only_yoloxs.py` 当作 Bcam 等价物**：实际文件继承 `paired_uxo` 的默认退化分布；历史记录也证实本地运行版本曾手抄 pipeline 而漏掉 `probs`。没有证据支持删除旧配置或权重；这里的 discard 指废弃错误对照/标签，不是删除文件。

## 1. 实际继承关系与分支边界

- 当前 checkout 是 `exp/cmold-paper-repro`，本地 HEAD `b005f41`，相对 `origin/exp/cmold-paper-repro` ahead 8；工作树有大量既有修改。受审主线文件在 `main` 与分支 HEAD 内容相同，但很多文件仅有换行形式差异。因此本报告描述**当前工作树**，不把历史 commit 当作当前事实。
- `t_camera_s` 唯一基座是 `../r0_baseline_yoloxs.py`，后者依次继承 `uxo_frame_split.py`、`two_stream_yolox_s.py`、`schedule_f2.py`、`default_runtime.py`（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\configs\repro_cmold\teachers\t_camera_s_yoloxs.py:47`；`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\configs\repro_cmold\r0_baseline_yoloxs.py:37-42`）。**不是**继承 e11_bcam/E13-cam；相同部件是共同祖先和显式重写，不是“同一份相机训练配置”。
- `e11_bcam -> e11_b2 -> s0_b2 -> s0_cross_attn -> 主线 model/dataset/schedule/runtime`（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\configs\f2\e11_bcam_camera_only_yoloxs.py:24-31`；`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\configs\f2\e11_b2_cross_attn_nominal_yoloxs.py:27-33`；`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\configs\f2\s0_b2_cross_attn_nominal_yoloxs.py:10-23`；`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\configs\f2\s0_cross_attn_yoloxs.py:15-20`）。
- E13-cam 的唯一副本在仓库外，继承 e11_bcam，改 dense data_root、63 epoch、1-epoch warmup、3-epoch constant tail（`D:\agent_workspace\水下\声呐目标检测\configs\f2\e13_bcam_camera_only_dense_yoloxs.py:28-60`）。仓库内的 `e13_m1/m2/dself` 是蒸馏配置，**不是** E13-cam 本体；不能拿它们代替相机 baseline（例如 `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\configs\f2\e13_m2_privilege_yoloxs.py:14-18,84-93`）。

## 2. 逐项证据对照

| 项目 | e11_bcam / E13-cam | `t_camera_s`（当前实现及落盘配置） | 判定 |
|---|---|---|---|
| 相机检测器 | 三头 TwoStreamYOLOX 容器，仅 camera head 有监督；两个 sonar heads 和 fusion 禁用 | 同为 YOLOX-S：CSPDarknet 0.33/0.5、PAFPN 128、三类 YOLOXHead，SimOTA；只有 camera loss=1（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\configs\repro_cmold\teachers\t_camera_s_yoloxs.py:78-117`） | **同类同宽**。并非单流类：sonar backbone/neck 仍构造，但没有 sonar head，loss/predict 跳过 sonar forward（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\aodet\models\detectors\two_stream_yolox.py:124-142,240-266,378-400`）。测试固定 live=8,938,456、dead=7,162,816 参数，但本审计未重新构建计数（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\tests\test_repro_teacher_configs.py:64-71`） |
| 初始化 | 主线 base 对两个 stream 的 backbone/neck 都指定同一份 YOLOX-S COCO，head 没有该 init（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\configs\_base_\models\two_stream_yolox_s.py:14-22,25-46,61-65`） | 相机 backbone/neck 显式恢复同一 URL 和 prefix；无用 sonar stream `init_cfg=None`；head 无 pretrained init（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\configs\repro_cmold\teachers\t_camera_s_yoloxs.py:56-73,97-110`） | **相机初始化一致，容器初始化不同**。日志显示相机 stem 的 COCO 加载；E13 实际加载日志未在本机取得（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\work_dirs\repro_cmold_teacher\t_camera_s\20261109_022400\20261109_022400.log:1288-1295`） |
| 优化器 | SGD lr=0.00125、momentum=0.9、Nesterov、weight_decay=5e-4、norm/bias 不衰减、grad clip=35，EMA momentum=0.0001；E13 不改 optimizer（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\configs\_base_\schedules\schedule_f2.py:22-37,59-66`） | 完全沿用 | **一致，但不是完整 YOLOX recipe**：没有 Mosaic/MixUp/HSV、BatchSyncRandomResize 或 YOLOXModeSwitchHook。无依据将缺项称为论文差异 |
| 预算 | e11 为 304 epoch、5 warmup、cosine 至 289、15 constant（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\configs\f2\e11_b2_cross_attn_nominal_yoloxs.py:35-59`）；E13 为 63 epoch、1 warmup、cosine 至 60、3 constant（`D:\agent_workspace\水下\声呐目标检测\configs\f2\e13_bcam_camera_only_dense_yoloxs.py:35-60`） | 200 epoch、5 warmup、cosine 至 185、15 constant、floor=0.0000625（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\configs\repro_cmold\r0_baseline_yoloxs.py:44,60-63,78-97`） | **不同**。新 run 为 416 iter/epoch，200 epoch 完成（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\work_dirs\repro_cmold_teacher\t_camera_s\20261109_022400\20261109_022400.log:3901-3911`）；单进程、seed=0、deterministic=False（同文件 `:32-40`） |
| 训练 pipeline | 同步 flip=0；AOSampleDegLevel 强制 d0=1；AOStudentCameraView(dinf=zero,jitter=.08)；squeeze 至 640×640（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\configs\f2\s0_b2_cross_attn_nominal_yoloxs.py:12-23`） | Load、keep_ratio=True resize、flip=0、Pack；**没有** AOSampleDegLevel 或 AOStudentCameraView，也没有 Mosaic/MixUp/HSV/multiscale（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\configs\repro_cmold\uxo_frame_split.py:87-102`） | **不同**。重要更正：D0 的物理参数全零，jitter 对 D0 无实际强度变化，只做 float/uint8 round-trip（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\aodet\datasets\transforms\camera_degradation.py:74-80,125-164,177-200,276-281`）；不能说 e11 的 d0 等效“加 8% 图像扰动” |
| 几何/预处理 | 1920×1080 非等比 squeeze 到 640×640，BGR 转 RGB、float、无 mean/std normalize；base 未指定 pad_value，框架默认 | 长边限制 640，1920×1080 -> 640×360；预处理时 pad 到 batch 最大且可被 32 整除，pad=114；同样 BGR->RGB、float、无 normalize（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\aodet\datasets\transforms\paired_geometric.py:72-95`；`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\aodet\models\data_preprocessors\paired_preprocessor.py:42-53,64-86`；落盘 `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\work_dirs\repro_cmold_teacher\t_camera_s\t_camera_s_yoloxs.py:130-131`） | **不同但 train/val 各自一致**。新实现不是固定 640×640 letterbox canvas。GT 随 x/y 实际缩放（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\aodet\datasets\transforms\paired_geometric.py:54-55,77-84`） |
| eval pipeline | squeeze 后 AOStudentCameraView，按工具指定 d0/d1/...；配置 val，E11 约定 CLI `--split val` / 事后 val_id | resize + Pack，无 camera-view fork；dataset 已由 split_file 限定 val；d0 仅作为结果标签，无图像退化（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\configs\repro_cmold\uxo_frame_split.py:97-135`；`D:\agent_workspace\水下\声呐目标检测\tools\oneshot\eval_camera_teacher.sh:21-26`） | **几何不同，d0 图像内容实质一致于 resize 后**；推理 score=0.01、NMS=.65、max=100；COCOeval 默认 maxDets，pooled AP（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\configs\_base_\models\two_stream_yolox_s.py:89-96`；`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\aodet\evaluation\per_branch_metric.py:88-103`） |
| checkpoint | E13 脚本选 final epoch_63 后评 val/val_id（`D:\agent_workspace\水下\声呐目标检测\scripts\e13_chain.sh:62-75`；`D:\agent_workspace\水下\声呐目标检测\tools\eval\eval_e13_valid.sh:13-18`）；E11 的每个实际文件/EMA 状态未在本机核实 | 固定 final `epoch_200.pth`（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\configs\repro_cmold\teachers\t_camera_s_yoloxs.py:49-51`）；`val_cfg=None`，无 in-loop best selection；每 10 epoch 保存、仅留 3 个；EMA 开启 | **都是 final-epoch 约定，不是 best-val**。新 eval 脚本没有显式 EMA 权重交换，不能默认报成 EMA AP；本机无法验证旧 run 是否使用 EMA 权重 |
| 数据/GT | 配置声明 `data/paired/uxo_full`（1,650 train 帧）与 `uxo_full_dense`（7,960 train 帧），来自另一套 capped/dense 转换（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\configs\f2\e11_b2_cross_attn_nominal_yoloxs.py:29-33`；`D:\agent_workspace\水下\声呐目标检测\configs\f2\e13_bcam_camera_only_dense_yoloxs.py:28-33`） | `/mnt/d/pby/uxo-full/paired`，用 `FrameSplitPairedSonarCameraDataset` 按 sonar image_id 过滤 train/val，不使用原 `frame_meta.split` 列（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\aodet\datasets\repro_frame_split.py:96-146`） | **不是同一数据池或曝光**。新相机监督直接读 camera annotations；`sonar_gt_sources=(blob,projected)` 只影响未使用的 sonar 侧，不能称为相机标签来源（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\aodet\datasets\paired_dataset.py:112-134`） |

## 3. 原始数据、指标与可比性

### 3.1 原始 split / annotation 复核

- `D:\pby\uxo-full\repro\frame_split.json:1-7` 给出 seed=0、train=3,322、val=830；`:4164-4182` 的三类 val 数为 228/265/337；`:4184-4194` 表明池是 4,152 帧/37 条录音，并排除了 test/val_id。`:4255-4371` 的 train/val/shared 录音清单相同，37/37 共享。
- 独立只读复算：train/val **帧 id 无交集**，并集恰为原 `frame_meta.csv` 的 train+val 4,152 id；记录的 frame_meta SHA-256 与当前文件一致。`repro/camera.json` 和 `sonar.json` 相对 `paired/` 原件只增加 image split 字段，annotations/categories/其余 image 内容未变；新增 split 的 830 个 camera id 与 split 文件 val id 完全一致。camera 原始图为 1920×1080，830 val 帧各一框。读取器真正使用 `paired/camera.json`，不是 repro 副本（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\aodet\datasets\paired_format.py:69-95,144-156`）。
- 因此新 830 val 是**同录音、近邻帧留出**，不是 recording-level val；它没有使用 `val_id`，更不是 test。独立按 `frame_idx` 复算，每个 val 帧均有同录音 train 帧，最近距离 median=5、max=19，766/830 (92.3%) 不超过 5；不得把 frame id 不相交写成“无泄漏”。旧 `val_id` 另是 dense/uxo_full 的同录音留出诊断，不能冒充论文划分。

### 3.2 有本地原始指标文件的读数

以下都是 camera、d0、GT=all、**pooled COCOeval**，不是逐录音均值；均不来自 test。

| run / 同一 830 val 上的条件 | AP | AP50 | AP75 | AR@100 | n_images / n_gt / n_pred | 原始证据 |
|---|---:|---:|---:|---:|---:|---|
| `t_camera_s` epoch_200，保持比例 | **0.9024874436450422** | **0.9897153653852183** | **0.9574760308975963** | **0.9316866193159591** | 830 / 830 / 836 | `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\results\repro_cmold\t_camera_s\eval_val\ap_summary.json:1-13`；`...\ap_breakdown.json:1348-1365` |
| P2 `t_camera_s_stretch` epoch_200，squeeze 训练+eval | 0.8743583982348356 | 0.9603439799642828 | 0.928750576949223 | 0.8996476592634938 | 830 / 830 / 849 | `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\results\repro_cmold\t_camera_s_stretch\eval_val\ap_summary.json:1-13`；对应 breakdown `:1348-1365` |
| 同一 `t_camera_s` 权重，**只在 eval** 改 squeeze（不匹配探针） | 0.27123564705059555 | 0.7215974335593517 | 0.16253843941532217 | 0.3668767097184201 | 830 / 830 / 1,388 | `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\results\repro_cmold\t_camera_s\eval_val_stretch\ap_summary.json:1-13` |
| E13-cam epoch_63 权重，本分支容器，squeeze eval | 0.6407657050720271 | 0.9067519158578681 | 0.6575415912405377 | 0.702817393314389 | 830 / 830 / 1,016 | `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\results\xeval\e13cam_on_ourval_stretch\ap_summary.json:1-13`；权重/配置来源 `D:\agent_workspace\水下\声呐目标检测\tools\oneshot\xeval_b2_stretch.sh:6-14` |

- P2 比 letterbox 低 0.028129 AP、0.029371 AP50；这只是同分支、同 seed、同预算下的几何对照，**不能**证明旧平台差距由几何造成，也不能把 P2 作为 CMOLD rung（配置本身已限定诊断用途，`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\configs\repro_cmold\teachers\t_camera_s_stretch_yoloxs.py:19-30,51-85`）。
- `t_camera_s` 的三类 pooled AP/AP50 分别为 aircraft bomb 0.940355/0.989008、incindiary grenade 0.895062/1.000000、mortar shell 0.872045/0.980139（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\results\repro_cmold\t_camera_s\eval_val\ap_breakdown.json:1297-1347`）。这不是多样性证据：单 seed 且所有 val 录音都在训练池。
- `results\2026-11-05_platform_compare\bcam_seed{0,1,2}_camera.json` 是一行 prediction JSON，不是 `ap_summary.json` 或评测集/标注清单；不能仅凭它们宣称已独立核实 E11 AP。E13 旧 val/val_id 读数（0.5228/0.8180、0.6401/0.9664）目前只追溯到历史表，原始 dense 数据、训练日志和原始 summary 不在本机（历史表 `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\doc\logs\2026-11-05-literature-comparison-blob.md:14-22`；缺失记录 `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\doc\reviews\2026-11-09-audit-d-trace.md:94-95`）。**本报告不将这些数列为已验证 raw metric。**

## 4. Keep / discard / revise（不删除原文件）

1. **KEEP — `t_camera_s_yoloxs.py`、epoch_200 和 830-val 原始产物。** 可审计的 camera-only、同分布候选；引用时固定写“seed 0、200 epoch、frame-level 8:2、37 shared recordings、GT=all、pooled”。训练/评测脚本记录于 `D:\agent_workspace\水下\声呐目标检测\tools\oneshot\eval_camera_teacher.sh:21-26`；final ckpt 存在，run metadata 为 `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\work_dirs\repro_cmold_teacher\t_camera_s\run_meta.txt:1-5`。
2. **KEEP AS DIAGNOSTIC — P2 squeeze 与 geometry-mismatch 探针。** 分别回答“训练几何”和“train/eval 几何不一致”，不可互换，也不可选高者覆盖原结果。
3. **KEEP SEPARATE — e11_bcam / E13-cam。** 它们是原平台的 final-epoch baseline；不可与 `t_camera_s` 拼成一次受控消融。原始 `s0_c0` 若需继续研究，只能明确标成默认退化相机臂；其本地手抄 pipeline 偏离和 D0–D4/D∞ 分布有历史记录（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\doc\logs\2026-11-04-s0c0-degaug-config-deviation.md:1-23`）。
4. **DISCARD — “t_camera_s 继承 e11/E13 全部 recipe”、跨平台绝对差归因、“D0 jitter=8% 图像退化”、以及把 val/val_id/test 拼接或称为论文协议。** 特别是 val_id 不是论文已知协议，test 900 的文档读数没有本机 raw artifacts，不能在本审计中升级成事实。
5. **REVISE — 下一版候选配置/协议（不改动原仓）。** 固定并版本化数据、标注和 recording-level split，先评 val 再冻结 final test；同一协议下对照模型，并记录 split/annotation/checkpoint hash、resolved config、seed、输入尺寸和是否 EMA。若要改善论文可比性，仅能把“3,322 对 nearly 4,700 对图像”列为已知规模差；不能编造论文 resize、split、初始化、checkpoint selection 或增强细节。增加 seed 只能支持稳定性结论，不能替代未见录音验证。
6. **REVISE — 实现层面可单独提出 camera-only 单流配置/容器。** 当前 7.16M 死 sonar 参数不进入 forward，并非功能错误，但会让“camera-only 参数量/部署大小”含混。该优化不应与数据/协议变化混入同一实验。
7. **REVISE — 产物元数据。** 当前 `ap_summary.json` 只写 branch/level/gt/metric（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\tools\test.py:197-207`）；split、样本数、config/ckpt hash、geometry 和 EMA 状态只能由其他文件拼接。建议后续工具把这些信息写入 manifest，而非修改既有读数。

## 5. 明确未知与停止条件

- 论文的 split 单位/比例/seed、输入分辨率与缩放、完整增强、初始化、训练时长及 checkpoint 选择未由本次代码审计确定；本项目设置只能称“我方选择”。
- E11/E13 的真实 resolved configs、训练日志、本地 `data/paired/uxo_full*` 标注、best/final 与 EMA 权重细节、原始 val/val_id metrics 均未完整获得。不能把配置注释中的帧数或历史数字升级为独立验证。
- 新训练快照记录的 git 是 `e4b1dc7...`（`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\work_dirs\repro_cmold_teacher\t_camera_s\run_meta.txt:1-4`），与当前 HEAD 不同；本地快照没有 dirty diff、依赖锁、数据/标注/ckpt SHA-256 或完整评测命令日志。因此“配置一致”有证据，“整个训练/评测环境逐位复现”没有。
- 两套相机标注在重叠帧上是否逐框一致仍未知；本审计只证明**当前新平台 repro 与 paired 标注一致**，没有证明旧 3,828/3,900-ish 平台同源等值。
- 单 seed 的 0.9025 不能支持跨录音泛化、统计显著性或“已达到论文能力”的结论。900 帧 test 历史读数、test 对照和由此衍生的“1.2 点/26 点”归因均不在本次 raw evidence 内，且不得用 test 追选配置。
