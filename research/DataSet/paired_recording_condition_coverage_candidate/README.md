# 按采集条件覆盖制定的新划分候选

2026-11-13。**candidate_pending_user_review：用户审阅前不激活，不重训，不覆盖旧split。** [逐录音照片与覆盖浏览页（本地产物说明）](../../ARTIFACTS.md#artifact-d0e2c45d2060) · [录音表](recordings.csv) · [条件覆盖（本地产物说明）](../../ARTIFACTS.md#artifact-5790755451b4) · [规则与输入hash](protocol.json) · [核验](verification.json)。

| 类别 | train | val | test |
|---|---:|---:|---:|
| bomb | 8条/800对 | 1条/100对 | 1条/100对 |
| mortar | 6条/600对 | 2条/200对 | 2条/200对 |
| grenade | 8条/800对 | 1条/100对 | 1条/100对 |
| 总计 | **22条/2200对** | **4条/400对** | **4条/400对** |

398备用仍不参加主实验，按来源角色分为265/87/46。所有3398身份及3000选入成员不变，类别/框/图像未改。

## 全部录音角色

短编号下方均在浏览页对应完整日期身份。

| 类别 | train | val | test |
|---|---|---|---|
| bomb | 171105、174439、175000、175905、180506、181139、182317、160551 | 175506 | 180722 |
| mortar | 101416、101840、102500、103140、103927、105017 | 103728、104749 | 101622、105230 |
| grenade | 121124、121539、122608、122855、123500、124039、124915、125048 | 121327 | 123841 |

## 规则与它能保证的内容

主条件按类别内摆放（floor/普通未标floor）、运动（L to R/flyby/ellipse）、notes名义z/tilt/roll/pan精确组合。725与750、60°与90°不混为同一条件。notes未记pan保留unknown，不当0；standard不额外认证每帧是否支架。共有21种主条件，14种仅一个来源组。每种至少一个来源组留train；保守的122608/122855同组，不拆相邻帧。

为避免同名义条件但不同运动片段造成漏覆盖，留出每条100帧至少95帧的记录SonarPan能在同主条件train帧中找到圆周距离≤5°的值；本候选实际99–100/100。每类出现过的电子设置边际值（ReceiverGain、SamplesPerBeam、SamplePeriod、FrequencyHiLow、Enable150V）与Min/Max Transmit也在train出现。**不保证每一种电子设置的联合组合在train都有。**先枚举满足以上约束的train来源组子集，取最少train录音、最少pan未支持样本数，再seed42 hash打破平局；其余组按类hash排序平分val/test。没有用模型成绩在候选间选优。

这些约束描述原始采集元数据和选入片段，不是物理3D姿态、实际RGB视角、精密同步或完整运动轨迹的认证。window start/length是声呐量程窗口，不是目标距离。相机原框触边是提示，不自动判真截断。参考日期并不代表独立session或物体实例。

## 相比旧版本的重要变化与限制

- 唯一floor bomb160551进入train；唯一bomb flyby182317、grenade高处roll90的121539及两个不同tilt的flyby均进入train。不是因它们分数低而移入，而是当前每种主条件只有一个来源组；但修订动机确实受旧test/val诊断启发，必须披露。
- mortar105017与105230名义条件相同，但所选pan范围约28–165°与110–160°；本候选将前者train、后者test，后者记录pan被训练覆盖。只按名义分组的初始草案未发现此问题，该草案保留在paired_recording_condition_candidate，不是本次推荐版本。
- train覆盖全部21个名义主条件，不代表val/test也覆盖21种。14种单来源组条件无法独立评价；floor训练成功不能说明独立floor泛化成功。val/test仅各4录音，bomb/grenade各只有1条，结果仍有很强来源依赖，不能把400帧当400独立条件。
- 新val/test很多录音已在旧模型train或开发中出现。**旧权重不能用来声称新划分的留出表现，必须从固定COCO起点重新训练。**所有新模型共用同一角色表、同一起点家族与数据版本，raw/EMA分开。
- 旧test已被查看，本候选不能重命名成全研究untouched final test。改进覆盖不保证更高AP，也不能把新旧AP差归因于模型能力；新旧数据平台结果分别报告。
- 182317等原配对/精密同步疑点继续存在，不因移入train就认证适合任何跨模态蒸馏。后续按实际方法需要另做准入；相机/声呐单模态不自动要求几何同步认证。

## 核验和浏览范围

当前matches.csv的30条notes与审计输入逐项相等；每条100选入身份对应原ARIS FrameIndex，共3000帧原metadata参与条件统计。输入源/旧split hash未改；新角色组互斥，跨角色图像hash重复0；所有3398身份、3000选入和398备用完整保留。独立复核新清单与manifest、留出主条件与pan支持、HTML所有链接通过。90张首/中/末预览源hash及解码通过。实际目视查看floor160551与大pan范围105017两条预览，不冒称全30条/3000帧视觉条件已认证；浏览器渲染未验。

来源：[完整原始元数据审计（本地产物说明）](../../ARTIFACTS.md#artifact-52a65a8a9b32)；[事前规则](../../experiment/archive/condition-aware-split-plan.md)；[生成脚本](../../tools/build_condition_split_candidate.py)；[浏览页生成](../../tools/render_condition_split_review.py)。最终输出hash索引见artifact-sha256.json。
