# grenade 七条剩余录音的相机—声呐逐页审核

2026-11-13。当前七条合计 **687 个唯一助手接受配对**，其中保留旧124915的22个，新增665个。五条达到每录音100对；124915和125048分别缺19、44对，全部允许库存已看完，不能声称七条均已完成100对目标。

| recording | 唯一已看身份 | 允许来源库存 | 唯一接受 | 至100缺额 |
|---|---:|---:|---:|---:|
| 2023-09-21_121124 | 203 | 697 | 117 | 0 |
| 2023-09-21_121327 | 266 | 739 | 130 | 0 |
| 2023-09-21_121539 | 203 | 776 | 102 | 0 |
| 2023-09-21_122608 | 203 | 757 | 100 | 0 |
| 2023-09-21_122855 | 201 | 809 | 101 | 0 |
| 2023-09-21_124915 | 169 | 169 | 81 | 19 |
| 2023-09-21_125048 | 251 | 251 | 56 | 44 |

“已看”按保存逐页判断的唯一sample计数，含原strong根对应本范围的历史审核。并非所有生成页面都审核了；没有决策的页面不算已看。补充清单与原候选身份交集为零。超100的接受身份保留，让主任务按冻结的导出规则选取，不在这里伪造每条精确100。

## 范围与证据

使用既有SD相机图及原框、原始ARIS图。12对一页，逐项查看相机主体、声呐全图与候选框放大图，之后记录接受或未决。类别为incindiary_grenade。没有翻转原图、改时间对应、改gantry、拟合注册、改相机框、使用test或启动训练。单帧“双端可见目标一致”仅为视觉审核状态，不证明精密同步、三维姿态或物理回波归属；这些框不是专家GT或用户正式验收。

预先登记及版本说明见[计划](../../experiment/archive/paired-grenade-remaining-plan.md)。B/F控制混入下方支架或多余反射，G保留完整连通分量，H提高阈值，J增加下边界padding；每个提案依旧需要实际看图，算法产出不自动接受。各失败根和未决原图不删除。相邻帧高度相关，接受比例不能当作随机数据质量估计。

124915的后半段存在下方反射并入候选、相机目标底部出界；125048前段声呐目标弱或仅局部环缘，中段短时间内双端清楚，后段框扩入横向背景且相机出界。这些帧保留未决，不作负样本，不为达配额放行。库存已穷尽仅指允许来源身份已看，不证明任何更好的人工标注方法都无法挽救；进一步修改未决框须另存版本并重审。

## 文件与合并规则

有接受结果的根均在DataSet下，其decisions.json与review-events.jsonl是逐项记录，page JSON/JPG保留提案和hash：

- paired_assistant_remaining_strong：只沿用本范围124915的旧22个，原框不替换。
- paired_assistant_grenade_remaining_body：192个新接受，G。
- paired_assistant_grenade_remaining_high：47个新接受，H。
- paired_assistant_grenade_remaining_padded：349个新接受，J。
- paired_assistant_grenade_remaining_supplement：77个新接受，J；121327为65、125048为12。

原候选清单为DataSet/paired_visible_expansion/candidates.json。额外清单为[paired_grenade_remaining_supplement/candidates.json（本地产物说明）](../../ARTIFACTS.md#artifact-e75be09ae97a)，共115个来源身份，121327为65、125048为50。由source-inventory的无camera_issues且eligible_for_review来源与camera_temporal_all/manifest-resolved.json连接，排除现有候选，保留原source、reference_sd、SD时间索引和source_paired_role。准备目的和来源hash已记于[preparation.json（本地产物说明）](../../ARTIFACTS.md#artifact-f061e3cdf772)。121327选择早期65帧是我方开发策划选择，非论文或随机抽样协议。

合并时将补充清单加入candidate lookup，只导出accepted，按sample去重；不要将其他根的unresolved覆盖已有接受，也不要把未决写成无目标标签。没有跨根重复接受身份，也没有同身份不同接受框。

## 核验

[verification.json](../../DataSet/paired_grenade_remaining_supplement/verification.json)复核本范围2024条跨版本决策，8096次hash比较涉及4660个唯一文件：每条决策的审核图、原声呐、SD图和相机标注均与spec/hash一致；接受框等于实际展示提案；所有precision_sync_certified和expert_verified均为false。旧22个与新增框无冲突，源manifest hash与准备时一致。以上是文件一致性检查，不替代视觉或专家准确性评价。

共享handoff/results/evaluation/dataset及正式总导出由主任务汇总，本子任务未修改它们。下一步可汇总五条达标与两条缺额；若仍要求这两条各100，需进一步独立人工边界审核或补充来源，不能复用重复身份填数。

## 后续更正：手工边界复审完成

主任务要求继续区分“camera完整但声呐提案失败”和“真实不可辨/出界”。另存M、N手工提案并逐页重新查看后，125048新增44个接受，由56增至 **100**。最终本七条合计 **731个唯一接受**（旧22、新709）；六条达到100，只有124915仍81、缺19。上方表格及verification.json保留为第一阶段快照，不静默覆盖历史。

- `paired_assistant_grenade_remaining_manual`：48个已看身份，33接受。根据实际可见环/主体设置手工外包范围，排除独立下方反射；早期M下边界过紧没有接受。
- `paired_assistant_grenade_remaining_manual_ring`：14个早期身份重新留出完整下环边，11接受，236–238仍因边界弱且断裂未决。
- `paired_assistant_grenade_remaining_manual_124915`：143–163共21个身份，0接受。缩短到236的下边界会截掉可能关联的下缘；旧H边界又与横向反射交织，不能依靠裁最亮区域替代主体边界判断。

最终125048的接受ARIS窗口为 **239–339，除296，共100个唯一身份**。239前有弱环/不明确边界；340开始相机原框底边为360，实际序列中目标随后出界。124915已接受窗口为 **62–142，共81个身份**；143–169声呐下边界仍待判断，170起原相机框底边首次达360。框坐标触边本身只是检查提示，这里同时结合已经看的配对页面判断；不把数值筛查自动当成图像截断真值。

示例：124915的[手工复审页面0（本地产物说明）](../../ARTIFACTS.md#artifact-d67a7d651398)同时展示完整camera与下缘歧义；125048的[早期环复审（本地产物说明）](../../ARTIFACTS.md#artifact-bad192ecaccf)包含弱环未决和完整环接受，[后期主体复审（本地产物说明）](../../ARTIFACTS.md#artifact-3b9550a46c84)展示旧宽框失败被手工边界修复的完整camera区间。

新增提案清单manual-candidates.json、manual-ring-candidates.json、manual-124915-candidates.json都在paired_grenade_remaining_supplement下，使用已经存在于原/补充清单的身份，不扩大来源，不应重复加入导出candidate lookup。手工框以各新审核页spec和decisions为准。M失败版本、N重审及全部旧框保留。新增83条跨版本决策、332次hash比较通过，接受身份无重叠，见[manual-verification.json（本地产物说明）](../../ARTIFACTS.md#artifact-f49fec33f03b)。

补充过程失败留痕：一次临时清单读取未指定UTF-8触发GBK解码错误，随后显式UTF-8重试成功；诊断拼图124915-mid.jpg出现纵向覆盖，仅作失败草图保留，没有据其接受任何身份。正式双端审核页布局正常并逐页看过。无时间、gantry、原标注、split、训练或test变更。
