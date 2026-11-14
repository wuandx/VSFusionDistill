# Camera-only teacher：本机结果、失败证据与泛化边界

复核日期：2026-11-10。本文只读既有研究，不训练、不重跑推理、不重评 test，不修改原研究；唯一写入是本文件。AP 均指 COCO `AP@[.5:.95]`；读数只按各自评测集、相机支路、`level=d0`、`gt=all` 使用。

## 0. 结论先行

1. **本机直接支持的 camera-only teacher 基线是 `t_camera_s` 在同一批 37 条训练录音的 val 830 帧上取得 AP 0.902487、AP50 0.989715、AP75 0.957476、AR@100 0.931687。** 原始 `ap_summary.json`、`ap_breakdown.json`、预测 JSON、200 epoch 权重、训练日志、`run_meta.txt` 和两份逐字节相同的 resolved config 都在本机。
2. **这不是 recording-level generalization 读数。** 已有审计 E 从帧名单核实 val 830 全部有同录音 train 兄弟帧，最近帧距中位 5、p90 5、最大 19；本报告没有再次把训练样本或 test 当评测输入。它也不支持“跨录音泛化已解决”。
3. **`t_camera_s_stretch` 是 P2 几何诊断臂，不是另一份 teacher baseline。** 训练、评测都用直接拉伸时，相对 letterbox 的差为 −0.028129 AP / −0.029371 AP50；而同一份 letterbox 权重仅在评测时改为拉伸，下降 0.631252 AP / 0.268118 AP50。证据支持“train/test 几何不匹配是严重失败”，不支持把这种失败等同于跨录音泛化，也不支持“拉伸训练更差/更好”的一般结论。
4. **本机 val 上，`t_camera_s` 的分类不是聚合 AP50 的主要失败轴；高 IoU 框质量仍是 AP50 与 AP75 之间的可见差。** 但“差距集中在框贴合度”不能就此升级为已完成的对论文差距归因；论文评测集与划分未披露，不能用这些本地读数建立对论文的新主张。
5. **更正两项旧审计的“本机无产物”状态：**早期 `2026-11-04_camera_b0` 文件实际位于研究根目录而非 code 仓的 `results`；`ours_letterbox_test` 的 900 帧文件当前也有本地副本。后者是**5090 远端运行产生的文件的本地副本**，不是本地运行证据，且本次不使用 test 读数作泛化结论。

## 1. 复核规则、产物计数和评测器

依据 `D:\agent_workspace\水下\声呐目标检测_workflow\AGENTS.md`、`D:\agent_workspace\水下\声呐目标检测_workflow\handoff.md`：val/val_id、blob/all、pooled/逐录音均值、本机/远端不可混用；论文未披露的划分不补写；test 只在协议冻结后使用。

本次直接读取并解析 `ap_summary.json`、`ap_breakdown.json` 和预测 JSON，而不只摘录旧报告。聚合一致性如下：

| 本机目录 | n_images / n_gt / n_pred | pred JSON 框数 / 有框 image_id 数 | summary 与 pooled breakdown |
|---|---:|---:|---|
| `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\results\repro_cmold\t_camera_s\eval_val` | 830 / 830 / 836 | 836 / 830 | 一致 |
| `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\results\repro_cmold\t_camera_s\eval_val_stretch` | 830 / 830 / 1,388 | 1,388 / 827 | 一致 |
| `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\results\repro_cmold\t_camera_s_stretch\eval_val` | 830 / 830 / 849 | 849 / 830 | 一致 |

每个目录均有同名 `ap_summary.json`、`ap_breakdown.json`、`pred.camera.d0.json`。37 个 recording 的 `n_images`、`n_gt`、`n_pred` 分别加和为上述 pooled 数；逐类 GT 数固定为 bomb 228、grenade 265、mortar 337，合计 830。`ap_summary.json` 本身不含样本数、权重路径或执行主机，因此身份核对依赖 breakdown、运行脚本与训练产物，不能单凭 summary 的数值。

评测实现：

- `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\tools\test.py` 的第 111 行加载指定 checkpoint；第 143–149 行从 `camera.json` 取图像 id 和类别映射；第 167–195 行保存预测并计算 COCO 指标和 breakdown。
- `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\aodet\evaluation\per_branch_metric.py` 第 88–103 行使用 `pycocotools.COCOeval`，`ev.stats` 的 0/1/2/8 分别为 AP/AP50/AP75/AR@100；`maxDets=100` 为 COCO 默认。
- 同一文件第 170–187、273–277 行显示 `AP50_class_agnostic` 仅把 GT 与预测的 `category_id` 全改成 1，保留图像 id、框和 score，再算 AP50。它衡量的是 IoU≥0.5 的类无关检出；**不能单独证明定位准确，更不能解释 AP@[.5:.95] 中跨阈值/排序的影响。**
- 本次仅验证已有 JSON 的内容与算术，未在本机重新运行 COCOeval；不能把 JSON 相互一致表述为“从原始图像与 GT 重新独立复算出 AP”。审计 E 已在 sonar R0 上验证该 COCO 插值实现，但那不是本次对 camera 原始预测的重新评分。

## 2. 训练身份与配置

### 2.1 `t_camera_s`：主基线

`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\work_dirs\repro_cmold_teacher\t_camera_s\run_meta.txt`：

- config = `configs/repro_cmold/teachers/t_camera_s_yoloxs.py`；seed = 0；记录 git = `e4b1dc7467b1382e41536ad949ac1a76631059c2`；Python 3.10.12。

Resolved config：

- `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\work_dirs\repro_cmold_teacher\t_camera_s\t_camera_s_yoloxs.py`
- `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\work_dirs\repro_cmold_teacher\t_camera_s\20261109_022400\vis_data\config.py`

二者大小均为 9,071 B，SHA-256 均为 `cc8515085deafb24df29a8ad1de59d79177fb14cb4542bb2578fe0bbf149ed28`。关键字段：

- YOLOX-S camera backbone/neck/head，`num_classes=3`；backbone 与 neck 为 COCO pretrained init，head 未指定该 init。
- 只有 camera loss 权重为 1；声呐 stream 虽构建但无 head、无监督，不能把 checkpoint 大小当有效 camera 参数量。
- 200 epoch、batch 8、SGD `lr=0.00125`、momentum 0.9、weight decay 0.0005；5 epoch warmup，cosine 至 185，后 15 epoch 常数尾段；`val_cfg=None`，无训练内 val 选择。
- train/test 均 `AOPairedResize(640,640), keep_ratio=True`；train `split='train'`、test `split='val'`；`flip prob=0.0`；resolved config 的 `known_deviations` 明示无 paired Mosaic/MixUp、无多尺度 batch augmentation。
- 推理 `score_thr=0.01`、NMS IoU 0.65、`max_per_img=100`、`nms_pre=1000`。

`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\work_dirs\repro_cmold_teacher\t_camera_s\20261109_022400\20261109_022400.log` 开头记录本机 WSL/Linux、单张 RTX 5060 Ti；结束于 epoch 200 的 416 iter 和 `Saving checkpoint at 200 epochs`。`epoch_200.pth` 为 179,431,393 B；另有 epoch_180/190 checkpoint，`last_checkpoint` 指向 epoch_200。

### 2.2 `t_camera_s_stretch`：几何对照

对应 `run_meta.txt` 记录 config `t_camera_s_stretch_yoloxs.py`、seed 0、git `253c931bad7642c170f62d02d0b3403b57d52ec1`。以下两份 resolved config 相同，均 9,312 B、SHA-256 `e3a7dd0cd7b0465c3975d53a787d42e7b4b83d041878f3f835117644930c5698`：

- `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\work_dirs\repro_cmold_teacher\t_camera_s_stretch\t_camera_s_stretch_yoloxs.py`
- `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\work_dirs\repro_cmold_teacher\t_camera_s_stretch\20261109_092259\vis_data\config.py`

train/test 均为 `keep_ratio=False`；其余模型、优化器、划分与 epoch 调度同上。配置明确写为 “P2 diagnostic arm, not a rung”。`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\work_dirs\repro_cmold_teacher\t_camera_s_stretch\20261109_092259\20261109_092259.log` 结束于 epoch 200；`epoch_200.pth` 为 179,438,241 B。

### 2.3 权重/数据关系与执行脚本

三条评测均使用对应 epoch_200：

- `D:\agent_workspace\水下\声呐目标检测\tools\oneshot\eval_camera_teacher.sh`：`t_camera_s` / letterbox / `split=val`。
- `D:\agent_workspace\水下\声呐目标检测\tools\oneshot\p1_geometry_probe.sh`：同一 `t_camera_s` 权重，只把 test resize 改为 `keep_ratio=False`。
- `D:\agent_workspace\水下\声呐目标检测\tools\oneshot\eval_p2.sh`：`t_camera_s_stretch` 权重 / `keep_ratio=False` / `split=val`。

resolved config 指向 `/mnt/d/pby/uxo-full/paired` 和 `/mnt/d/pby/uxo-full/repro/frame_split.json`。这些是运行环境路径；本次没有重新推导或改写划分。审计 E 的相邻帧统计保留为**已有原始帧名单复核的结论**，与本报告直接读到的 37 条 recording breakdown 相互吻合，但不是两个独立重复实验。

## 3. 本地 val 结果、逐类和逐录音失败

### 3.1 Pooled COCO 结果

| 权重 / 评测几何 | AP | AP50 | AP75 | AR@100 | 直接产物 |
|---|---:|---:|---:|---:|---|
| `t_camera_s` / letterbox | 0.9024874436450422 | 0.9897153653852183 | 0.9574760308975963 | 0.9316866193159591 | `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\results\repro_cmold\t_camera_s\eval_val\ap_summary.json` |
| `t_camera_s` / stretch（几何不匹配） | 0.27123564705059555 | 0.7215974335593517 | 0.16253843941532217 | 0.3668767097184201 | `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\results\repro_cmold\t_camera_s\eval_val_stretch\ap_summary.json` |
| `t_camera_s_stretch` / stretch | 0.8743583982348356 | 0.9603439799642828 | 0.928750576949223 | 0.8996476592634938 | `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\results\repro_cmold\t_camera_s_stretch\eval_val\ap_summary.json` |

全部只有 `gt=all` 相机行；没有 blob 相机行，不能把声呐 blob 口径套到相机。`AP_small`、`AP_medium` 均为 −1，`AP_large` 等于 AP；这是 COCO 面积分桶没有 small/medium GT 的表现，不是额外的模型能力证据。

关键计算：

- 仅 test-time 改拉伸：`0.2712356471−0.9024874436 = −0.6312517966`（−63.1252 个百分点）；AP50 `−0.2681179318`；AP75 `−0.7949375915`；AR `−0.5648099096`。
- 训练、测试都用拉伸：`0.8743583982−0.9024874436 = −0.0281290454`（−2.8129 个百分点）；AP50 `−0.0293713854`；AP75 `−0.0287254539`；AR `−0.0320389601`。
- 两臂均同录音 val、单 seed；−2.8129 点是观测差，不是包含跨录音或训练随机性的不确定性界。

### 3.2 `t_camera_s` 的逐类与逐录音

`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\results\repro_cmold\t_camera_s\eval_val\ap_breakdown.json`：

| 类别（pooled，n_gt） | AP | AP50 | AP75 | AR@100 |
|---|---:|---:|---:|---:|
| 100lbs_aircraft_bomb（228） | 0.9403552831 | 0.9890075418 | 0.9788596473 | 0.9574561404 |
| incindiary_grenade（265） | 0.8950623037 | 1.0000000000 | 0.9405851076 | 0.9343396226 |
| mortar_shell（337） | 0.8720447441 | 0.9801385544 | 0.9529833378 | 0.9032640950 |

三类 AP 均值 = `(0.9403552831 + 0.8950623037 + 0.8720447441)/3 = 0.9024874436`；AP50 均值 = 0.9897153654，与 summary 闭合。类别最低为 mortar，不能说三类无差异。

逐录音 `category=all` 有 37 行，AP 全部大于 0；最低 `2023-09-21_101622` AP 0.7236089323（21 帧），最高 1.0。逐录音算术均值 AP = 0.9051461114，而 pooled AP = 0.9024874436；两者不可替换。逐录音高 AP 不消除其全部与训练录音重合这一限制。

`t_camera_s_stretch` 另有明确的局部失败：`2023-09-20_173615` 23 帧的 AP/AP50/AP75/AR 全为 0；逐录音均值 AP 0.8792205311 也不同于 pooled 0.8743583982。故“聚合表现高”不能代替逐录音失败清单。

## 4. “定位 vs 分类”与“泛化差”到底证明了什么

### 4.1 本地 val 上确实有的证据

`AP50_class_agnostic` 来自上述 breakdown 的 pooled `category=all` 行：

| 运行 | class-aware AP50 | class-agnostic AP50 | 后者−前者 | AP50−AP75 |
|---|---:|---:|---:|---:|
| `t_camera_s` / letterbox | 0.9897153654 | 0.9898542535 | +0.0001388881 | 0.0322393345 |
| `t_camera_s_stretch` / stretch | 0.9603439800 | 0.9603467489 | +0.0000027689 | 0.0315934030 |
| `t_camera_s` / stretch 不匹配 | 0.7215974336 | 0.8715279896 | +0.1499305560 | 0.5590589941 |

前两项表明：在**本 val、AP50、该预测分数/NMS 组合**下，去掉类别几乎不改变聚合结果。可写为“分类不是该 AP50 的主要失败轴”，不能写成“模型分类能力已被普遍证明”或“定位是唯一瓶颈”。mortar 的 AP50 低于其他两类，也说明逐类信息仍需保留。

第三项同时有类无关 AP50 的大幅下降和更大的 class-aware 降幅，不能只用“框不够紧”或只用“分类错”解释。它至少同时受 IoU 匹配、漏检、假阳性、类别与置信度排序影响；已有文件没有逐框匹配类型分解。

### 4.2 本地 val 尚不能证明的命题

- **不能从 val 证明 unseen-recording generalization。** 高 val AP 与审计 E 的近邻帧证据共同表明它最多是同录音留出诊断。
- **不能用 AP50≈AP75 的某个差或论文表格差，独自证明“只有框定位问题”。** AP50→AP75 的下降支持严格 IoU 下存在损失；但不分离分类、检出和排序，且 CMOLD 未披露其评测集。阶段审查中“论文同口径/残差集中框贴合度”的表述需要降级为本地、描述性的现象。
- **不能用几何探针证明跨录音差的原因。** P1 固定权重/集合改 test geometry；P2 改 train+test geometry。两者没有改动 recording split，不能替代未见录音评估。
- **没有 camera 的 train-self-evaluation。** `t_camera_s` 下没有 `eval_train`；因此不能给这个 camera baseline 报 train/val “过拟合差”。
- **没有跨 seed 或 recording-level 相机结果。** 本基线 `seed=0`，本地结果没有跨 seed 方差或未见录音的不确定性界。
- **没有本报告的逐帧可视化或 IoU 中心偏移复核。** 不能把历史 sonar/其他 camera 模型的失败机制直接移植到此权重。

## 5. 900 帧交叉评测：文件现在本地可读，但仍是远端运行、且本次不使用 test

### 5.1 更新“本机无产物”的旧状态

当前存在以下两组**内容完全相同**的文件（每个文件 SHA-256 相同）：

- `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\results\xeval\ours_letterbox_test\ap_summary.json`
- `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\results\xeval\ours_letterbox_test\ap_breakdown.json`
- `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\results\xeval\ours_letterbox_test\pred.camera.d0.json`
- 同目录 `ours_letterbox_test_20261110\` 下三份同名文件。

因此审计 D 表 C4、审计 E §0.2 和阶段审查第 2.2 节“该 900 帧读数本机无 JSON”已不适用于**当前磁盘状态**。应改成“有远端运行产物的本地副本”；不应再写“完全没有本地原始文件”，也不能倒写成“本次在本地评测”。

执行出处为 `D:\agent_workspace\水下\声呐目标检测\tools\oneshot\wzl_xeval_clean.sh`：明确使用 5090 的 `/root/wzl`，上传的 `t_camera_s_epoch200.pth`，`PairedSonarCameraDataset`，`split="test"`，letterbox，输出到远端 `$WZL/results/xeval/ours_letterbox_test`。本地结果目录没有对应的 resolved eval config、stdout log 或独立 run_meta；副本内嵌的时间戳子目录也不是原始终端日志。

这些文件与旧文档记载的 900 帧相机行一致：AP `0.6408361391`、AP50 `0.8669416197`、AP75 `0.6940350483`、AR `0.7009567901`；breakdown 为 10 recordings、900 GT、932 predictions。与本地 val 的形式差为：

- AP：`0.6408361391−0.9024874436 = −0.2616513046`（−26.1651 个百分点）；
- AP50：`−0.1227737456`；AP75：`−0.2634409826`；AR：`−0.2307298292`。

**但这组数字来自既有 test 运行。本次遵守“不使用 test”的约束，没有运行它、不读其原始 test 图像/标注，也不据此确认泛化差或作模型选择。** 差值仅用于解释历史“26.2 点”主张的出处，不是本报告新验收的泛化结果。两套平台/相机标注是否逐框一致仍未核实；不能把该差分解为纯粹的 recording split、标注、几何或数据难度效应。

### 5.2 其他交叉评测的本地/远端区分

- `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\results\xeval\e13cam_on_ourval\ap_summary.json`：本地三件套存在，E13-cam 在本项目 val 830 上但**错误地 letterbox 喂入**，AP 0.1595091714 / AP50 0.5814202792。
- `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\results\xeval\e13cam_on_ourval_stretch\ap_summary.json`：本地三件套存在，E13-cam / 本项目 val 830 / stretch，AP 0.6407657051 / AP50 0.9067519159 / AP75 0.6575415912 / AR 0.7028173933。脚本 `D:\agent_workspace\水下\声呐目标检测\tools\oneshot\xeval_b_e13cam_on_ourval.sh` 指向 WSL 的 `/home/ty/mycode/.../e13_bcam_camera_only_dense_seed0/epoch_63.pth`，不是当前 `t_camera_s` 权重。
- **E13-cam 在他们 test 900 上的 0.6530/0.8844 仍未找到本地原始 JSON。** 全 `results` JSON 没有该读数；`wzl_xeval_clean.sh` 只记录远端 `$WZL/results/xeval/theirs_stretch_test`。故“同 900 帧两模型仅差 1.2 点”的一半仍是文档/远端主张，且本报告不采用它作结论。

## 6. 早期 camera baseline：真实路径与口径

更正审计 D 表 B12 和 audit-synthesis 更正表第 10 项：旧路径被假定在 `code\VSFusionDistill\results`，但真实位置是：

`D:\agent_workspace\水下\声呐目标检测\results\2026-11-04_camera_b0\`

实际文件：`run_meta.txt`、`eval_cam_both.log`、`ap_summary_250.json`、`ap_breakdown_250.json`、`ap_summary_304.json`、`ap_breakdown_304.json`。其中无 `pred.camera.d0.json`，所以只有指标/分解/文字元数据，不能重新检查逐框预测。

`run_meta.txt` 明确写 `s0_c0_camera_only_yoloxs seed0`、val 900、`d0`、默认退化抽样（不是 d0=1.0 训练）。JSON 核对：

| checkpoint | AP | AP50 | AP75 | AR@100 | n_images / GT / pred |
|---|---:|---:|---:|---:|---:|
| epoch 304 | 0.5087772269 | 0.8100654684 | 0.5171697293 | 0.5960185185 | 900 / 900 / 1,255 |
| epoch 250 | 0.5090178798 | 0.8084178514 | 0.5110552944 | 0.5967592593 | 900 / 900 / 1,269 |

epoch 304 的 pooled `AP50_class_agnostic=0.8284257323`，class-aware 0.8100654684；它不能与新模型 0.9025 直接相减成“同协议提升”，因为训练池、训练退化、数据组织和可能的输入几何均不同。旧报告中的 `E13-cam` val 0.5228 / val_id 0.6401 也不是这份 B0-cam epoch304 的 0.5088：模型/训练配置和集合不可混名。

这些历史文件的存在修正的是**路径审计**，不是对其旧平台 split 或标注的重新认证。`D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\doc\logs\2026-11-05-literature-comparison-blob.md` 和 `2026-11-06-e13-caliber-note.md` 的 E13 数字本身是历史文档读数，不应因 B0 文件存在而被当作 E13 原始产物。

## 7. 对既有审查的最小更正与安全结论

已阅读：

- `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\doc\reviews\2026-11-09-audit-d-trace.md`
- `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\doc\reviews\2026-11-09-audit-e-redteam.md`
- `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\doc\logs\2026-11-09-stage-review-camera-baseline.md`
- `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\doc\logs\2026-11-09-audit-synthesis.md`

应保留的审查纪律：论文划分未述；val 是同录音近邻帧诊断；`val_id` 不能称“文献式考场”；不能把 26.2 点单独归因为“考场难度”；旧 E13 与当前模型不可混为一谈。

本次新增的更正仅限当前文件可见性：

1. 旧 `camera_b0` 不是不存在，而是位于研究根 `D:\agent_workspace\水下\声呐目标检测\results\...`，不是 code 仓的 `results`。
2. `ours_letterbox_test` 的 JSON 已复制到本机，并有两份内容相同的目录；这不是本地运行，也不解除 test 禁用。

可交付的稳妥结论是：**本地 `t_camera_s` 具有完整的同录音 val 基线产物，聚合分类在该 val 的 AP50 上几乎无损，严格 IoU 指标有可见下降；几何不匹配可导致严重失败，而自洽的 stretch 训练仅使该 val 的 AP 下降 2.8129 点。未见录音泛化与对论文差距的归因仍未由本次本地、test-free 证据建立。**
