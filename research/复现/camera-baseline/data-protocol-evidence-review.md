# 数据、划分与 test 设计的证据复核

日期：2026-11-10。原研究根目录记作 `R = D:\agent_workspace\水下\声呐目标检测`，代码根目录记作 `C = R\code\VSFusionDistill`。本文是对既有审计的增量复核，不覆盖旧记录；没有训练、推理或 test 指标计算，没有打开 test 图像、逐条标注或预测。

## 1. 当前能验收什么

`t_camera_s` 的 830 帧 val 应保留为同录音诊断。现有产物足以说明它在该集合上工作良好，不能说明未见录音泛化已经合格。正常 test 的要求取决于要声称的泛化范围；当前最合适的第一层是**同一受控 UXO 数据来源内、未见 recording 的相机检测**，因此 train/dev/test 至少按完整 recording 互斥。recording-level split 仍不自动证明新物体实例、新水域或真实海底部署能力。

另一 agent 已启动的 `DataSet/camera_recording_disjoint_v1` **维持 HOLD，不继续转换、不训练、不读其 test**。截至本次核查，它仍是未完成准备；其拟定 final test 仅覆盖 aircraft bomb，且“从未用于任何旧模型”的证明不足，不能充当三类 camera-only teacher 的最终 test。

## 2. 证据分层与本轮访问边界

| 层级 | 本轮实际核查 | 可以支撑的结论 | 不能支撑的结论 |
|---|---|---|---|
| 论文原文 | 直接解析 CMHD 出版方 XML 的 `sec3dot1-sensors-26-04340`，与并行文献审计一致；CMOLD 来源限制见文献复核 | CMHD 明确 trajectory-level 划分；CMOLD 划分仍未知 | 不能把 CMHD 协议补成 CMOLD 协议 |
| 原始产物复算 | **仅** `D:\pby\uxo-full\repro\frame_split.json`，以及已确认只含 train/val 的未完成 `recording_manifest.csv` | artifact 内部数量、ID 交集和已记录 recording 列表 | 未重新验证这些 ID 对应的原图、标注、原始 recording 身份 |
| 当前代码 | split、converter、dataset 类与未完成 preparation 脚本 | 当前代码选择、过滤和加载逻辑 | 不自动证明旧 run 实际用了同一代码 |
| 仓库历史记录/旧审计 | `data-and-split-audit.md`、`dataset.md`、`C\doc\reviews\2026-11-09-audit-c-data.md`、stage-review | 旧审计所述近邻统计、历史 test 被用于模型比较的过程 | 不能标成本文重新从原始数据复算 |
| 推断/我方选择 | 后文协议与实验准入建议 | 可审查的后续研究设计 | 不是论文事实，也不是已经完成的新实验 |

本轮没有全量解析已知混合 train/val/test 的 `paired/frame_meta.csv`、`camera.json`、`sonar.json`，也没有运行现有 `make_frame_split.py --check` 或初始化 dataset。原因是当前工具会先读全量混合内容，再在内存中过滤：`C\tools\make_frame_split.py:116–153,223–229,296–305`，`C\aodet\datasets\paired_dataset.py:93–105`，`repro_frame_split.py:118–140`。构造 reader 并非天然的 test 隔离读取操作。

旧 `data-and-split-audit.md` 已声明解析全量 `frame_meta.csv`；旧配置审计还声明比较完整 annotation 副本。因此“未看 test 图像、未运行 test 评价”可以成立，**“从未读取任何 test 相关元数据/标注”不能由这些声明推出**。这不等于证明模型用 test 学习；应把访问范围写清，避免把元数据检查、图像查看和模型选型混成同一件事。本文不重复那次混合解析。

## 3. 安全 train/val artifact 的独立检查

运行 `python -I tools/audit_frame_split_only.py`。脚本只打开既有 train/val `frame_split.json`，不 import 模型或 dataset，不读取原始混合标注；输出为同目录 `frame-split-artifact-check.json`。

该 artifact 的 SHA-256 是 `7192a5f3541f20e46b493a7a94ce1503dc71c09e94e93f63432451accc4ad4c8`。重新检查得到：

| 项目 | 结果 |
|---|---:|
| seed / val fraction | 0 / 0.2 |
| train / val | 3,322 / 830 |
| train/val ID 交集 | 0 |
| 各侧重复 ID | 0 / 0 |
| train / val / shared recordings | 37 / 37 / 37 |
| 两侧 recording 集合相同 | 是 |
| artifact 所列三类 val 数 | 228 / 265 / 337 |

这里只独立确认 **artifact 的内部一致性**。artifact 中记录了被排除 test=1,500 与 val_id=594，但没有去读取这些样本。其 `source.frame_meta_sha256` 是生成时登记值，本文未重新 hash 混合 metadata，不能把它写作当前数据文件已重新比对通过。

旧审计的最近 train `frame_idx` 距离中位数 5、最大 19、766/830 不超过 5，本轮仅作为旧审计结果引用。它与 37/37 shared recordings 相符；本轮未重算帧距或像素相似度。frame ID 互斥只证明没有同一 ID，不能消除同 recording 时间相关性。

## 4. 标注血缘和采样偏差

官方 UXO 仓库说明 camera 标注坐标须乘 3，数据来自受控环境。因此这个缩放有官方依据；它不能证明旧/新平台逐框相同。[UXO 官方仓库 README](https://github.com/dfki-ric/uxo-dataset2024#about)

当前代码 `C\aodet\datasets\paired_dataset.py:114–129` 单独筛 sonar annotation 的 source，camera boxes/labels 直接取 camera annotations。因此 `blob/projected` 是声呐标签口径，不能直接当成相机 GT 的来源或过滤规则。但**不使用 sonar GT，不等于相机样本没有被声呐流程预筛选**：

| 代码机制 | 当前可证事实 | 对 camera-only 的含义 |
|---|---|---|
| `C\tools\split_uxo_recordings.py:66–89,102–119` | 按 blob 帧数、row residual、bearing residual 决定 recording excluded | 若相机沿用该 manifest，camera 分布继承 sonar calibration gate；效果方向和幅度未知 |
| converter `:349–355` | excluded recording 整条跳过 | 纯相机原本可用的录音也可能未进入 paired 平台 |
| converter `:374–394` | 候选要求 GoPro 与 ARIS 都存在，且要求 gantry 对应行；默认不含无标签帧 | 配对可用性和 gantry 完整性也限制相机样本池，不仅是 gate |
| converter `:396–405` | 先 cap，再可选 trim 两端 | 轨迹端点和时间覆盖可能变化；具体旧 run 参数需看落盘命令，不能由默认值代替 |
| converter `:244–271,406–413` | train 录音里切 val_id 块与 gap | val_id 是同录音留出，不是新的 recording-disjoint val |

上述是代码机制；本文没有通过 test 内容估计其选择偏差。也不能断言去除 sonar gate 必然提高 AP。对 camera-only，合理的准入依据是 camera 图像与标注的有效性，并对缺失配对、遮挡、截断目标等记录原因。默认无 label 的帧不能自动写成“无目标负样本”：旧 converter `:41–44` 已正确说明该歧义。

## 5. 对未完成新平台的具体裁决

读取状态文件 `DataSet/camera_recording_disjoint_v1/progress.json`：`status=incomplete`，最近完成的 recording 为 `2023-09-20_173329`，role=val，累计 3,446 帧。已确认其 `recording_manifest.csv` 当前仅包含 22 条 train（3,296 帧）和 1 条 val（150 帧），没有 test 行。未打开任何图像。当前 progress 与 preparation 的 train→val→test 循环顺序一致；不能仅由一个进度快照证明所有历史进程从未处理 test。

`experiment/tools/prepare_camera_dataset.py` 是先前 agent 的准备代码，本轮未运行。需保留并登记以下问题：

1. **test 覆盖不足。** `:52–73` 硬编码 22/9/4 条 recording，`:163` 明确要求拟定 test 全属于 `CATEGORIES[0]`，`:296–298` 也承认只含 bomb。它最多支持该类及该采集条件的局部封存评价；不能作为三类教师的主最终 test，也不能用其聚合 AP 代表其他两类。
2. **历史使用推断越界。** `:11–14,157–163,293–295` 从旧 manifest 的 `excluded` 推出 never converted / never trained / never evaluated。旧 manifest 只覆盖某次转换；需要逐 run 历史与数据平台清单才能证明更强命题。缺日志时填写 `unknown`，不能由 excluded 补成未见。
3. **转换本身不是污染的充分条件。** 仅格式转换、哈希或预先规定的完整性检查，不必然产生模型选择偏差。真正关键是训练暴露，以及结果、失败样例或人工选型是否利用过该集合。因此 `evaluation.md` 的“从未进入旧 paired 转换”过严，且可能把 final test 限成 sonar gate 所排除的特定条件。建议改为“历史训练/选型使用状态可证、协议冻结后封存”；这是协议修订建议，不是本文已修改的要求。
4. **GT 已有额外变更。** `:216–249` 在 x3 之后 clip bbox 到 1920×1080，保留了 native box 和 clipped flag，这利于追溯；仍不能称为与旧原生 GT 逐框等值。应先在 train/dev 登记超界数量、决定是否统一 clip、冻结成新 annotation 版本，再做公平对照，不能靠 test 表现选策略。
5. **hash 与复用检查不足。** `copy_verified :125–133` 只比较文件大小，不能证明字节一致；`:236–239` 只对 test 图片记 SHA-256、对所有 labels 记 hash。后续版本应固定所有 role 的身份校验标准，现阶段不据此复制更多 test。
6. **元数据有未经证明的值。** `:255` 把所有帧 `moving_target=false`；`:299–302` 声称每类仅一个物理实例。前者需来自来源记录，后者需原始数据文献或对象清单支撑，未知就记 unknown，不能把注释变成事实。

不删除、归档或续跑这些文件。它们是已有工作的证据，但尚未满足数据冻结和三类 test 的准入条件。

## 6. 正常 test 应满足的具体条件

以下是我方研究设计，CMOLD 没有提供可直接复用的 split 身份。CMHD 的 XML §3.1 明确采用每类 10 条轨迹、每轨 100 帧，trajectory-level 6:2:2；它是可参考的其他工作，不是 CMOLD 隐藏协议。[CMHD 出版方正文](https://www.mdpi.com/1424-8220/26/14/4340)

一般 grouped evaluation 的核心是：验证 recording 必须没有出现在对应训练 run 中。仅在当前模型已经训练过的 37 条里重新选一部分“留出”，无法创建未见 recording。[scikit-learn grouped CV 文档](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-iterators-for-grouped-data)

在未来运行之前，应依次通过这些准入门槛：

| 门槛 | 所需证据 | 不满足时 |
|---|---|---|
| A：数据角色可追溯 | recording、来源路径、旧角色、各旧 run 训练/评价/人工查看状态、unknown 明列 | 不声称全新 test；先以开发数据处理 |
| B：覆盖与独立性 | 全部三类都有若干独立 recordings；train/dev/test recording 互斥；列 class×geometry×采集条件覆盖缺口 | 不用帧级随机补齐；缩小主张或使用 grouped CV |
| C：标注冻结 | camera GT 来源、x3/clip政策、类别映射、无标签帧处理、有效框规则与 hash | 不训练；在 train/dev 解决，保留旧标注 |
| D：采样冻结 | 每 recording 的选帧规则、cap、时间范围、是否保留端点和排除理由 | 不根据模型分数挑清晰帧、删难帧或重抽 seed |
| E：测评冻结 | resolved config、checkpoint/EMA、score/NMS、resize/pad、COCOeval 参数、主指标与 breakdown | 不跨版本相减，不进入 final test |
| F：最终使用冻结 | 方法/超参/模型选择结束；一次预定 test 批次，失败也保留 | 如查看结果后再改模型，该集合转为开发性证据，需明确披露 |

不必机械套用 80/20 或 6:2:2；独立 recording 数和类别/条件覆盖比帧数比例重要。原脚本“每类 val/test 至少 3 条”是我方工程下限，不是统计充分性保证。多帧来自同一 recording，不能把它们全当独立样本形成很窄置信区间。有限预算下先报告每 recording/per class 和 pooled AP；若做不确定性分析，以 recording 为重采样单位并注明 recording 数，seed 方差另报。

测试集不需要刻意简单或困难。它要符合所声称的目标分布，完整呈现覆盖缺口；如果 deployment 需要无目标背景，而当前没有经人工确认的负帧，则不能把本数据的 AP 扩大为完整部署虚警表现。recording-disjoint 也不能解决同一物理 UXO、同一水池和重复轨迹条件造成的外推限制。

## 7. 旧 test 已参与开发后的有限预算选择

旧 900 帧集合已有开发性模型间比较记录。本文不读取其预测、逐帧标注或新算分，也不根据其结果选模型。保留历史结果和使用痕迹，不能事后改名恢复成 untouched test。

优先顺序是：

1. **若能证明尚有覆盖三类且与开发使用隔离的 recording**：先形成 metadata-only 角色 manifest，经固定规则分配；封存 test 的图像/标签，先只构建 train/dev。该可行性目前未知，不能承诺现成存在。
2. **若未触碰的 recording 仅有 bomb**：可保留为该类、该条件的辅助封存集合；三类主结论仍来自新的 recording-disjoint 开发验证，声明没有三类独立 final test。不要把两个未测类别写成已验收。
3. **若没有足够可封存 recording**：在明确的开发池内做 recording-level grouped CV。若用 CV 同时选超参又报最佳分数，会乐观；需要外层 recording folds 评价、内层 grouped folds/holdout 选择，并在每外层从初始化重新训练。嵌套 CV 的计算成本高，不能假装它恢复了所有历史选型独立性；更低预算的选择是冻结单一 recipe、有限 grouped folds，仅报告内部跨录音验证，等待后续独立数据。[嵌套 CV 方法说明](https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html)

当前最优的近期选择是先建立可信的 recording-disjoint **开发**基线，暂缓 final-test 资格宣称。不要为了“必须有 test”选出单类 gate-excluded 录音，也不要为省一次训练给旧权重换一个 split 名称。

## 8. 应撤回的下一步与未来实验登记建议

`C\doc\logs\2026-11-09-stage-review-camera-baseline.md:83` 提议“用自家 37 条录音做录音级留出，评测现有相机权重；不重训”。**该计划不能产生 unseen-recording 证据**：现有 `t_camera_s` 已训练全部 37 条 recording。新 split 的对应模型必须从预先登记的初始化重新训练，不能从该教师权重继续训练后把新 dev 称为未见。

所有下列项当前均为未运行计划，名称可由总台账分配连续版本号：

| 工作 | 目的 / 唯一改动 | 对照与判定 | 停止条件 |
|---|---|---|---|
| recording-disjoint camera baseline | 建立新 run 的跨 recording 参照；固定原生 camera annotation 版本、几何、recipe，仅把验证组织改为 recording 互斥 | 保留 830-val 作历史诊断；新主读数仅按新 manifest 报，不能把差值解释为 split 单一因果效应，因为训练/评价样本组成也变了 | A–E 任一门槛失败；空类别；未能排除 recording 重叠 |
| camera augmentation 对照 | 在同一新 train/dev 和 annotation 版本上，仅改变一种已登记增广 | 相同 seed/初始化/训练更新预算和 evaluator；主看 dev mAP@[.5:.95]，同时报 AP50、每类和最差 recordings，保留下降结果 | 不改 split、不以 test 调强度；几何或标注变化则另起版本 |
| camera sampling 对照 | 在已经冻结的开发 recording 角色内，独立研究 sonar gate/paired 可用性导致的采样范围 | 固定 dev evaluator、标注与 recipe，仅扩展 train 的 camera-valid 样本；记录增加数量和条件，不把额外数据收益说成模型改进 | 需要更改 dev/test 身份或重新挑录音时停止并重新登记协议 |

epoch 与更新次数不能在训练集规模变化时同时等价；未来预算要选定一种主约束并记录曝光次数。第一步的目的在于建立可用参照，不是强行解释 CMOLD 绝对分数差。是否采用新相机平台、annotation clipping 或完整 YOLOX recipe，都应在基线可审计之后分别决定。
