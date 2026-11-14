> 这是早期审计总报告，后续训练和数据版本已经推进；最新进展见[研究入口](../../README.md)。

# Camera-only teacher：复现审计总报告

**2026-11-11增量：**40条允许camera录音的全量时间对应重建与核验已完成；26761原生样本中26139有候选图、622保留未恢复状态。原GT未改，无训练或test访问。原框范围/截断仍需QA，173615与175000共1117个越界几何提示不能当已判坏标签数。见[全量结果与证据](annotation-issues/camera-temporal-all-results.md)及[对照浏览页（本地产物说明）](../../ARTIFACTS.md#artifact-509c66e4b095)。下文保留此前教师复现审计，旧AP不因数据重建而更新。

2026-11-10。状态：审计完成，未启动训练。本文汇总三路并行复核，覆盖其他 agent 已完成的报告、原研究近期工作、论文可获得原文、配置与非 test 产物。原研究只读；详细证据按“论文原文 / 原始产物复算 / 仓库历史记录 / 推断”区分。

## 1. 现在的基线能不能用

**可以保留为教师候选，不能认证为已验证的未见录音教师，也不能称 CMOLD 数字复现。**

现有 `t_camera_s` 在本地 830 帧 val 的 mAP@[.5:.95] 为 **0.902487**，AP50 为 **0.989715**，seed=0、epoch_200、camera/d0/GT=all、pooled COCOeval。配置、训练日志、权重和评测 JSON 可追溯，是已经做成的工作，不应丢弃。但 train 3,322 与 val 830 共享全部 **37 条 recording**；帧 ID 不重复不能消除录音内时间相关性。这个高分主要回答同录音留出的检测表现，不能验证未见录音能力。

本轮重新检查的是非 test 缓存产物及内部一致性，没有重新运行模型或 COCOeval。安全 split 检查只确认既有 artifact；旧审计的近邻帧统计仍按历史复算引用，没有重读混合 test 标注。详见 [实现复核](implementation-evidence-review.md)、[数据复核](data-protocol-evidence-review.md) 与 [结果登记](../../experiment/results.md)。

现阶段“泛化不强”是有历史现象支持的研究问题，**尚不能被本轮 test-free 证据定量认证或归因**。这与宣称模型没有问题同样不同：缺的是对应权重、对应数据版本下有效的 recording-disjoint 开发结果。

## 2. 两版基线和论文到底差在哪

这里的早期工作至少有三种身份，不能统称“原基线”：历史 `s0_c0/B0-cam` 默认退化训练，`e11_bcam` 清晰 d0 训练，以及 dense 平台的 `E13-cam`。当前 checkout 已没有 s0_c0 配置文件，不能声称重新核实了它的完整 resolved config。

| 项目 | 早期本地工作 | 新分支 t_camera_s | CMOLD 论文能确认什么 |
|---|---|---|---|
| 模型/模态 | e11/E13 为 YOLOX-S 相机支路；s0_c0 仅有历史身份链 | YOLOX-S，相机监督；容器仍构造无用 sonar 参数但 forward 跳过 | camera teacher、sonar student，共享 YOLOX architecture/input resolution；具体 S/M/L 容量未确定 |
| 数据组织 | uxo_full 与 dense 等多个转换，数字不能混用；相机池受 paired 转换约束 | 原 train+val 合为 4,152 池，按帧分 3,322/830，共享37录音 | 约4,700对用于 training **and validation**；比例、单位、seed与评测集身份未披露 |
| 相机 GT | 声称原生标注，但旧新转换逐框一致性未完整认证 | 读取 camera annotation，不使用 sonar blob/projected 作为相机标签 | camera fully labeled；sonar 有人工/伪标签过程。不同标签问题不能混为相机缺陷 |
| 几何 | e11/E13 非等比 squeeze 到640×640 | keep_ratio 后1920×1080→640×360，再由预处理 pad；不是固定640×640 canvas | 输入数值与 resize/pad 未披露，不能写“与论文不同”或“已对齐” |
| 退化/增广 | s0_c0 历史为默认退化分布；e11/E13 为 d0=1 | 不做该退化分叉；无 Mosaic/HSV/多尺度等 | 完整增强未知。YOLOX-S 原始 LaTeX 明确去 MixUp，不应盲目补回 |
| 预算/优化 | e11为304 epoch；E13为63；数据规模/曝光不同 | 200 epoch、batch8、SGD、初始lr .00125、配置eta_min .0000625，日志尾值 .000064641、momentum .9、wd .0005 | Table2披露200epoch等及final LR .0000625；当前实际尾值并非完全相同，各阶段完整scheduler/初始化/checkpoint规则未知 |
| 初始化/EMA | camera backbone/neck 的配置同属COCO家族；旧实际日志链不完整 | COCO backbone/neck；日志、MMEngine0.10.7代码和checkpoint静态证据支持加载保存时EMA | 初始化、EMA、final/best未知，不能推为论文差异 |
| 测评 | 不同平台的 val、val_id 和历史 test；有单/多 seed混杂 | 830同录音val；单seed、final epoch | Table3相机 mAP=.958/AP50=.997/AP75=.997；集合与评测代码未公开，不能当同协议差值 |

论文披露项以 [文献复核](../../related_work/paper-evidence-review.md) 为准。CMOLD 的 YOLOX-M 25.3M 属于 **sonar-only 同模态 KD 对照**，CMHD 本体的 YOLOX-M 也不是 CMOLD 相机教师容量证据。200 epoch 等超参是表图证据，不能因为正文文本抽取漏表而写成论文未述。

**规模比较必须同分母：**我方 4,152 train+val 对论文约4,700 train+validation；论文单独 train 数未知。不能写“少了1,378训练帧”并据此解释差距。即使规模接近，也不证明样本、条件或标注相同。

## 3. 哪些原因有证据，哪些仍只是候选

| 因素 | 当前证据强度 | 能得出的结论 / 下一步 |
|---|---|---|
| 同录音近邻 val | artifact复核：37/37共享；旧独立审计有近邻统计 | 当前val不足以验收未见录音。不能倒推CMOLD也用了帧级划分，也不能量化它占绝对差距多少 |
| train/eval 几何不匹配 | 同权重同830val，仅eval改squeeze，AP .9025→.2712 | 是已实测的严重失败机制；只能用于该条件，不是跨录音掉分的完整解释 |
| 自洽的几何选择 | P2 train/eval均squeeze，AP .8744，差−2.8129点；一个recording AP=0 | 旧同录音平台的一次受控观测；既不能把几何排除为所有问题的主因，也不能把P1的63点归给squeeze训练 |
| 数据筛选/标注平台 | 代码存在sonar calibration gate、配对/gantry可用性、cap/trim等过滤 | camera-only虽不用sonar GT，仍可能继承采样限制；方向/幅度未知，应先固定血缘和准入 |
| 增广与预算 | 本地配方和YOLOX原始配方有差异，旧新平台同时变化多项 | 合理候选，未有当前未见录音的单变量对照；不盲加MixUp/加容量/多跑seed |
| 定位/分类/置信排序 | 本地val的类无关AP50几乎不变，严格IoU指标下降 | 只说明该val/AP50上分类不是主要损失轴；不能断言论文差距仅是定位、也不能泛化到其他录音 |
| EMA漏用/容量不足 | EMA链已补核实；教师具体容量比较缺乏公平对照 | 不列为已查明缺陷；声呐/KD新seed结果不能替代相机教师证据 |

不做“26点全是测试集难度”“几何已排除”“大模型无用”等单因素归因。数据、标注、split、配方同时变化时，绝对差只描述两个条件的结果，不能自动分解因果。

## 4. 正常 test 应该怎样设计

测试集不是越难或越简单越正常，而是要代表**预先声明的目标分布**，并且不参与训练与选择。本项目近期主张应收缩为受控 UXO 来源内的跨 recording 检测：train、dev、final test 的 recording 互斥，三类及主要采集条件有覆盖，先冻结标注、采样、阈值与指标，再训练和选择。CMHD 的 trajectory-level 6:2:2 是参考，不是 CMOLD 隐藏协议，也不是必须照抄的比例。[CMHD 原文](https://pmc.ncbi.nlm.nih.gov/articles/PMC13417324/)

旧 test 已有开发性模型间比较记录，不能靠改名变回 untouched final test。本轮不读取其样本、逐帧标签或预测，也不使用其分数选择模型。只做过格式转换本身不必然污染 test；相反，旧 manifest 标 excluded 也不能证明它历史未用。要查训练、诊断、人工查看和选型的完整历史。

已有未完成平台拟定的四条 test 仅 bomb，不能验收三类。若找不到足够且历史可证的三类未触碰 recording，合理选择是 **先报告 recording-disjoint 开发验证或 grouped CV，明确没有独立三类 final test**，之后等新增数据；不编造一个严格测试集。嵌套grouped CV可减少同轮选型偏差，但成本更高，也不消除整个研究已看过旧数据的历史。

尤其必须撤回旧阶段报告的下一步：**从已经训练过的37条录音里重新留出，再评原权重不重训，不能得到未见录音读数。** 新run必须按事先冻结split从COCO/独立初始化训练，不能从已见该留出录音的UXO checkpoint继续训练。

## 5. 取舍与推进顺序

| 优先级 | 动作 | 本轮状态 / 取舍 |
|---|---|---|
| P0 | 整理证据、纠正旧结论、固定访问边界 | 已完成；保留旧报告与读数，通过新报告明确更正 |
| P1 | 核实录音历史、camera标注版本和覆盖，形成可审查train/dev manifest | 下一步；新数据目录仍incomplete/HOLD，暂不续跑或宣称冻结 |
| P2 | 从COCO重新训练一条recording-disjoint camera-only YOLOX-S | 尚未运行；沿用最少配方，不同时加容量、改增广、改标注后归因 |
| P3 | 证据支持时，仅做一项几何/增广对照，必要时最少配对seeds | 尚未运行；现有同录音P1/P2保留，避免无目的重跑 |
| P4 | 方法选择完成，且具备合格封存数据后再最终test | 可行性未知；不以单类holdout替代三类测试 |
| 后续 | 教师验收后讨论蒸馏 | 暂缓CMOLD机制、融合、容量搜索和复杂蒸馏链 |

“去掉不必要的东西”在本轮落实为停止错误比较、暂停无依赖必要性的支线，不删除文件、权重或历史失败。现有sonar占位/死参数可将来单独工程简化，不是本轮泛化问题的优先修复项。

各实验已写目的、唯一改动、对照、判定标准和停止条件，见 [分阶段计划](../../experiment/archive/plan-camera-teacher.md)。当前没有预设“必须达到论文.997”或未经论证的跨录音AP门槛；先建立可审计的有效参照，再依据开发证据与使用要求决定验收目标。

## 6. 新增勘误与接续入口

本报告及三路复核明确覆盖旧结论的以下部分，不静默改写旧报告：

1. 论文未披露split，不能写帧级80/20；未披露test身份不等于没有test。
2. 37录音已全部训练，事后重分不重训的“严格留出”方案无效。
3. 3,322 train与约4,700 train+val分母不等；应比较4,152总池。
4. CMOLD Table2已有200epoch等超参，训练时长不能整体标未知。
5. YOLOX-S原始LaTeX明确去MixUp；旧“缺完整配方”表述需细化。
6. MMEngine保存/加载链支持当前使用EMA，不因eval脚本没写swap就判漏用。
7. 旧报告dirty/b005f41属于旧快照；本轮HEAD是4fadd06、工作树clean，新增三seed结果属于声呐。
8. 未完成数据脚本中的excluded≠历史未用、单类test、额外clipping、同size≠同内容等问题先登记，暂停运行。
9. 配置eta_min不等于实际训练尾值：cosine的begin/end与T_max不一致，日志尾LR为6.4641e-5，不能写成已精确达到论文final LR 6.25e-5。差别的性能影响未知，后续若修正单独登记，不混入split对照。

原始证据入口：[文献](../../related_work/paper-evidence-review.md)、[实现](implementation-evidence-review.md)、[数据](data-protocol-evidence-review.md)、[安全输入hash快照](evidence-snapshot-2026-11-10.json)。接续时读 [handoff](../../handoff.md)，不要再从旧总报告直接摘结论。

本轮结束前已完成独立红队复核及[工作流验证](workflow-verification.json)：本地链接、当前文档占位符、工具语法、明确白名单输入hash与原仓HEAD/status均通过。该验证不运行模型、不重算AP、不读取test，也不声称对整个原研究做了逐文件hash。
