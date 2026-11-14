# Camera-only teacher：实现证据复核与新增勘误

日期：2026-11-10。性质：只读审计，不是新实验。本报告接续 `branch-and-config-audit.md`、`results-and-failure-evidence.md`，只记录独立核实与新增纠错，不改写旧报告。原研究、Git、配置和权重未修改；未运行训练、模型推理或 COCOeval，未读取 test 图像、标注或预测。

## 1. 当前结论与快照

`t_camera_s` 可以保留为 camera-only teacher 候选：实际有相机 YOLOX-S、COCO backbone/neck 初始化、seed 0、200 epoch、同录音 val 830 的完整产物。它尚不能作为未见录音教师的验收结论，也不能据与 CMOLD 数字接近宣称论文协议复现。

本次快照为 `exp/cmold-paper-repro`、HEAD `4fadd06829c6c738977639a55b6e44ad0e35ac44`，`git --no-optional-locks status --porcelain=v1` 输出为空。旧报告的 `b005f41` 和 dirty 状态是旧快照，不能继续当当前状态。最新提交只修改 `doc/logs/2026-11-09-r2-cmold-and-geometry-readings.md`，新增的是声呐 R0/R2 的 seed 1/2 与 R1 读数；不是 camera teacher 新的 recording-level split 验证。

可重复的审计脚本为 [audit_camera_implementation.py（本地产物说明）](../../ARTIFACTS.md#artifact-9d78f841b491)，结果与逐文件 SHA-256 为 [implementation-audit.json（本地产物说明）](../../ARTIFACTS.md#artifact-9b0a8c57ffaf)。脚本使用明确的非 test 路径白名单，读取 JSON、配置文本、日志、checkpoint ZIP 元数据；不导入项目模型。权重只用 `zipfile` 与 `pickletools.genops` 静态扫描，没有 unpickle 或 `torch.load`。当前 hash 绑定当前磁盘产物，不倒推历史评测时的逐位身份。

## 2. 新增勘误：需要先修正这些推理

| 原陈述与位置 | 更正 | 实际影响 |
|---|---|---|
| stage-review `:74-75,83`：从自家 37 条录音中按录音留出，再评现有权重，“不重训”得到严格口径 | 现权重的 train 已包含全部 37 条录音。从这些录音重新挑帧，无法消除训练时见过该录音的事实。要验证 recording-level split，必须预先划分并从 COCO/独立初始化重新训练；不能从已见留出录音的 UXO checkpoint warm-start | 这条旧建议必须停止；现有 200-epoch 权重不能补一次评测就变成未见录音 baseline |
| branch-and-config-audit `:29`：eval 没显式交换 EMA，故 EMA 状态未知 | MMEngine 0.10.7 保存时已经把 EMA 交换进 checkpoint 的 `state_dict`；直接加载该字段正是部署路径。见第 3 节 | 不能把“可能漏用 EMA”当当前模型低分原因；旧 E11/E13 的实际 EMA 身份仍未认证 |
| stage-review `:94,102`、branch-and-config-audit `:61`：3,322 训练帧 vs 论文 nearly 4,700，作为已知训练规模差 | 论文句子的分母是 training **and validation**。正确可比项是我方总池 4,152（3,322+830）vs 论文约 4,700；论文 train 数未知 | 不得据“少 1,378 训练帧”归因或直接定补数据配额 |
| stage-review `:63-64,103`：掉分来自考场，差距集中框贴合度，原生标注不含争议 | 论文评测集未知；本地 AP50/AP75 的差只支持本地描述。相机使用原生 GT，仍须验证数据版本、纳入规则、类别映射和旧新平台逐框一致性 | 不得把数据同源升级成协议/标注等值，也不得把论文差距分解为纯定位误差 |
| branch-and-config-audit `:9` 将 s0_c0 “实际文件”作为当前证据 | 当前 HEAD 与 `main` 的 configs 树均找不到该文件。存在的是旧 run_meta、旧偏离记录与结果；可以证明历史臂身份，不能说已检查当前该配置 | s0_c0 只按历史产物立论，须追回当时 resolved config 才能恢复完整训练语义 |
| 旧报告将“缺 MixUp”概括成未使用完整 YOLOX-S 原论文 recipe | YOLOX LaTeX `yolox.tex:253` 对 YOLOX-S/Tiny/Nano 明确去掉 MixUp，并减弱 Mosaic；不能把一般 YOLOX 或 MMDetection recipe 冒充小模型原论文 recipe | 可以保留“本地无 Mosaic/HSV/多尺度”的事实；缺 MixUp 本身不能作为 YOLOX-S 偏离证据；CMOLD 完整增强仍未知 |

stage-review 为 [原研究阶段审查（本地产物说明）](../../ARTIFACTS.md#artifact-a67ec9a045d1)。上述更正保留旧文，供后续引用时覆盖相应结论。

最新声呐报告还存在不应带入 camera 结论的推理：`2026-11-09-r2-cmold-and-geometry-readings.md:128` 写符号检验 p=0.125 后“不是噪声”，不能从这个数排除随机性；`:147-152` 将较弱教师对应的 KD 无增益写为“必然”、并排除容量/优化，均超出该对照。M 从零训练、S 使用 COCO 初始化，本身也没有隔离容量。这里仅登记逻辑边界，不重审声呐实验或推进 KD。

## 3. EMA 身份：这次比旧审计多核实了一层

证据链：

1. 训练日志 [20261109_022400.log:30（本地产物说明）](../../ARTIFACTS.md#artifact-c2daea8a24fd) 写 `MMEngine: 0.10.7`；`:412-413` 写 `before_save_checkpoint` 的 EMAHook。
2. [schedule_f2.py:62（本地产物说明）](../../ARTIFACTS.md#artifact-a46a85eac287) 和落盘配置均启用 EMAHook，`ExpMomentumEMA(momentum=0.0001, update_buffers=True)`。
3. 实际 WSL 解释器的库目录是 `\\wsl.localhost\Ubuntu-22.04\home\ty\mycode\VSFusionDistill\.venv-gpu\lib\python3.10\site-packages\mmengine`。只读比较其 `hooks/ema_hook.py`、`runner/checkpoint.py` 与官方 v0.10.7 文件，SHA-256 完全一致。
4. [官方 EMAHook](https://raw.githubusercontent.com/open-mmlab/mmengine/v0.10.7/mmengine/hooks/ema_hook.py) 的本地副本 [ema_hook_v0.10.7.py:159（本地产物说明）](../../ARTIFACTS.md#artifact-8e171b3e9179) 保存时先写 `ema_state_dict`，再将 EMA 交换进 `state_dict`（交换实现 `:215-223`）；`ema_state_dict` 中的 `module.*` 对应原训练参数。不是凭字段名字猜含义。
5. 两个 epoch_200 checkpoint 静态扫描都存在 `state_dict`、`ema_state_dict` 与 `module.camera_backbone...` 字符串。checkpoint hash：`t_camera_s` = `34885b4d64d95a3da09a8d2434ec1178b7832a2ce5d42c32bbbed590996f94dd`；P2 = `574a48e7f78e835d35647e0d15101a7b20804559fd33370d0621370c13acab0a`。
6. [tools/test.py:110（本地产物说明）](../../ARTIFACTS.md#artifact-9536c8ca6454) 直接 `load_checkpoint`；[官方 checkpoint 实现](https://raw.githubusercontent.com/open-mmlab/mmengine/v0.10.7/mmengine/runner/checkpoint.py) 的本地副本 [checkpoint_v0.10.7.py:569（本地产物说明）](../../ARTIFACTS.md#artifact-bd246a1c3d1c) 使用 `checkpoint['state_dict']`。

因此，按日志、现存 checkpoint、实际库和评测脚本组成的可核查链，当前评测加载的是保存时的 EMA 权重。不能继续说“因为 eval 没写 swap 所以没用 EMA”。这仍不是本次重新运行历史预测，也不是对评测时环境、dirty diff 和 checkpoint 路径身份的逐位复现保证。

官方源码于 2026-11-10 从上述 URL 获取。`ema_hook_v0.10.7.py` SHA-256=`edb7d228a45f91febaacfbc1c3267dc2b50ef0e8fcd16be62868cf0f6d84565d`；`checkpoint_v0.10.7.py`=`ed6108c9dd8f7ea914efdd3f0dd047a35ae6741c4f12ae885b76ad493f52c321`。下载与实际安装 hash 记录于 JSON。

## 4. 哪些实现差异确实有证据

| 臂 | 实现/身份证据 | 可以回答什么 |
|---|---|---|
| 早期 s0_c0 / B0-cam | 研究根 `results/2026-11-04_camera_b0/run_meta.txt:1-5` 写 seed0、val900、d0 eval，并明确训练使用默认 d0–d4 各0.16、dinf0.20。`ap_summary_304.json:6-12` 有 camera/all AP0.508777、AP50 0.810065。当前 config 缺失，历史偏离说明在 `doc/logs/2026-11-04-s0c0-degaug-config-deviation.md:5-7` | 这不是 e11_bcam 的全程 nominal d0 训练对照；保留为退化增强历史臂 |
| e11_bcam | `configs/f2/e11_bcam_camera_only_yoloxs.py:24-30` 继承 e11_b2，仅去 sonar heads/fusion；`s0_b2_cross_attn_nominal_yoloxs.py:12-20` 显式 d0=1.0、squeeze640×640 | 名义清晰相机基线。旧实际数据/日志与权重身份尚不完整，不据配置注释认证历史结果 |
| E13-cam | 研究根 `configs/f2/e13_bcam_camera_only_dense_yoloxs.py:28-40` 继承 e11_bcam，dense根、63 epoch、warmup1/tail3；注释中的“每图约52次”与63 epoch不相符，不能按注释推曝光次数 | 旧 dense 平台，不能与新同录音 val 直接相减为改进 |
| t_camera_s | `configs/repro_cmold/teachers/t_camera_s_yoloxs.py:47,78-116`；落盘 `work_dirs/repro_cmold_teacher/t_camera_s/t_camera_s_yoloxs.py:101-164,245-293` | 单独的 camera-only 候选，只有 camera 监督；sonar backbone/neck 仍构造但 `predict`/`loss` 跳过无 head 的 sonar forward |
| P1 | 研究根 `tools/oneshot/p1_geometry_probe.sh:13-18` 同权重只改 eval `keep_ratio=False` | 训练/推理几何不匹配的敏感性，不是拉伸训练的效果 |
| P2 | 两份落盘配置以安全 AST 数据解析逐键比较，在 model/optimizer/scheduler/train_cfg/dataloaders/hooks/randomness 这些功能字段里，唯二差异为 train/test dataset pipeline 的 `keep_ratio True→False`，JSON 已记录 | 同 split/seed/预算的几何对照，仍然只是一次训练重复 |

两种实际几何均已复核：[paired_geometric.py:77（本地产物说明）](../../ARTIFACTS.md#artifact-5d12232f2ab6) 保持比例时只 resize，无固定 canvas；[paired_preprocessor.py:42（本地产物说明）](../../ARTIFACTS.md#artifact-1cea3d1e67cc) 再逐流 pad 到 batch 最大且可被32整除。相机1920×1080对应640×360，再pad到640×384；不是固定640×640 canvas。框使用实际 fx/fy，pack `scale_factor` 与 head `rescale=True` 路径相接。不能单凭“letterbox”名字假定与其他实现逐位相同。P2 落盘顶层仍残留 `keep_ratio=True` 变量，但真正 dataset pipeline 已为 False；应查实际管线，不能只读这个闲置变量。

D0 的物理参数在 `camera_degradation.py:75` 全为0，`:125-126` 的 jitter 为乘法；不能把 e11 的 `jitter=.08` 写成 D0 实际加8%扰动。

## 5. 非 test 产物复核与因果边界

本次直接解析以下四组 summary、breakdown、prediction JSON，并核对 summary 与 pooled 行的 AP/AP50/AP75/AR@100 在1e−12内一致；不等于重新从 GT 计算了 AP。

| 权重/几何，val830、camera/all、pooled COCOeval | AP | AP50 | 预测框数 | recording数 |
|---|---:|---:|---:|---:|
| t_camera_s / 保持比例 | 0.9024874436 | 0.9897153654 | 836 | 37 |
| t_camera_s / P1 squeeze | 0.2712356471 | 0.7215974336 | 1,388 | 37 |
| P2 / squeeze | 0.8743583982 | 0.9603439800 | 849 | 37 |
| E13-cam / squeeze，在本项目val | 0.6407657051 | 0.9067519159 | 1,016 | 37 |

前三者来自原代码仓 `results/repro_cmold/{t_camera_s/eval_val,t_camera_s/eval_val_stretch,t_camera_s_stretch/eval_val}`；第四者来自 `results/xeval/e13cam_on_ourval_stretch`。完整路径/hash 在 JSON。没有读取任何 test 目录的 JSON。本次也不从旧报告重复列出 test 数字或计算其差值。

P2 相比 t_camera_s 的 AP 差为 −0.0281290454；这是同录音、seed0的一次受控观测。P1 差 −0.6312517966，支持在该模型和该 val 上严重几何不匹配会失败。它们都不能支持“几何已被排除为跨录音或对论文差距的主因”。P2 还有 recording `2023-09-20_173615`（23帧）AP=0；高 pooled AP 不应掩盖整录音失败。t_camera_s 的37条逐录音 AP 均非0，但均是训练中已见录音，仍不提供未见录音证据。

## 6. 精简后保留的工作

1. **保留** t_camera_s 的权重、落盘配置、日志和同录音 val 产物；身份定为“同录音 teacher 候选”，不删除或覆盖。P1/P2 归入几何诊断，不再把它们作为论文协议对齐证明。
2. **停止** 反复在同录音 val 追论文绝对数值、用现权重抽录音假装严格留出、混用s0_c0/e11/E13读数、因缺显式EMA swap而修评测脚本。停止本阶段继续扩展KD/容量臂；当前教师任务不依赖它们。
3. **先补协议和身份**：冻结未见录音 train/dev 及类别/采集条件覆盖、确认原生相机标注血缘、记录 config/data/split/ckpt hash；旧模型若已用过某录音，不能充当该录音的折外教师。
4. **后续最少训练**：从独立初始化按冻结的 recording-level split 训练一条相机 YOLOX-S；沿用当前已核实的单一配方作为基准。不要同时改 split、数据池、增强和容量再归因。后续对照必须另行预登记目的、唯一改动、对照、判定与停止条件；本次未启动。

当前缺口是未见录音证据，而不是已经证明模型结构、EMA或容量存在错误。没有这样的证据时，“泛化能力不强”只能作为待检验问题；旧平台现象与本地几何探针可以提出候选解释，不能完成单因素归因。

## 7. 红队追加：实际 LR 尾值并未到配置 eta_min

总报告复核时新增核实：`t_camera_s` 的训练日志 [20261109_022400.log:3909（本地产物说明）](../../ARTIFACTS.md#artifact-f10d67d1ae7c) 明确写 epoch200、iter400/416 的 `base_lr=lr=6.4641e-05`。因此不能把本地实际学习率终点直接写成论文 Table2 的 `6.25e-5`，也不能宣称该项数值完全一致。

配置的 `eta_min=base_lr*0.05=6.25e-5` 是目标参数，不等于训练实际到达值。[r0_baseline_yoloxs.py:85（本地产物说明）](../../ARTIFACTS.md#artifact-ce5463194cbb) 配置 cosine `begin=5`、`end=185`，但 `T_max=185`；该阶段时间窗口为180 epoch，而周期参数为185，随后进入 `ConstantLR(factor=1)` 尾段。调度窗口与 T_max 不相等，不能只从 eta_min 推实际末值。当前稳妥记录为“初始 LR .00125；配置 eta_min6.25e-5；日志 epoch200 尾部实测6.4641e-5”。

这是一项实际配方差异/审计记录，不是已证明的泛化差原因。本次不修改原配置、不补跑、不为精确达到论文 final LR 而另开训练。后续若改变 scheduler，必须单独登记，避免同 recording split、标注和增广变化混在一起归因。
