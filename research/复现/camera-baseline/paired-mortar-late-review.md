# 六条后期 mortar 配对审核

本轮直接逐页查看相机及声呐，得到 **223 个唯一接受配对**：105017 为 107，105230 为 116；各可选 100，备用合计 23。其余四条完整允许库存均已看完，当前没有接受框。此处 accepted 是助手可见回波和相机框审核，不是专家 GT 或精密同步认证。

## 范围与核对结果

| recording | source-inventory 库存 | 实际已看唯一身份 | 接受 | 尚未看 |
|---|---:|---:|---:|---:|
| 2023-09-21_105017 | 677 | 167 | 107 | 510 |
| 2023-09-21_105230 | 766 | 268 | 116 | 498 |
| 2023-09-21_105856 | 206 | 206 | 0 | 0 |
| 2023-09-21_110049 | 193 | 193 | 0 | 0 |
| 2023-09-21_110229 | 226 | 226 | 0 | 0 |
| 2023-09-21_110411 | 291 | 291 | 0 | 0 |
| 合计 | 2359 | 1351 | 223 | 1008 |

已满足每录音 100 的前两条停止扩充；它们未看完完整库存。后四条完成的是所有允许身份的视觉检查，不意味着数学上证明任何专家手工框都不可能成立。未决身份不转为负样本，不以库存帧数充当标注数量。

## 方法及失败保留

B 为既有宽边界候选，E 为更强回波候选，G 为强连通分量。105017 的 B 包进长斜支撑/横纹，E 又裁去连续端部，故均保留失败结果。G 接受 25 个清晰早晚帧；H 按可见边界锚点插值得到待审框，每个接受帧仍逐页实际查看，H 再接受 82 个不同身份。没有以插值代替审核。人工方案见 [plan](../../experiment/archive/paired-assistant-mortar-late-manual-plan.md) 与 tools/review_mortar_late_manual.py。

105230 的细长弱回波在部分早中段仍连贯可辨：默认候选池 B 接受 55，随后从完整允许库存补采 source frame 246–424 中未审身份 65 个，接受 61。剩余 4 个边界不清；默认池全部 203 身份都已看，不能将其误写为完整 766 库存耗尽。

后四条补查依据 [exhaustion plan](../../experiment/archive/paired-assistant-mortar-late-exhaustion-plan.md)，共补查 483 个此前未审身份：105856 106、110049 93、110229 117、110411 167，均实际查看且逐帧保留 unresolved 决策。

- 105856：source frame 150–231 约 82 帧相机目标完整或临界，之后右端逐渐截断。前段声呐的横向反射和下方连续回波边界无法可靠分开；B 太宽，E 的下缘存在裁端疑点。即使早段全部可修，也不足 100 个完整相机配对。
- 110049：早期完整相机窗口声呐接近背景噪声，之后出现的水平反射与下方亮点仍难明确目标边界。source frame 133 附近相机尾部已触底，后续逐渐截断；清楚回波出现时相机已不完整。没有为凑配额接受弱噪声框。
- 110229：早期相机完整，但声呐主要只见底部孤立水平反射，不能把它自动认作目标。直到后期另一组回波变得连贯时，相机尾部已经被底边截断。完整 226 身份均保留未决。
- 110411：早期相机上端截断，中段有完整相机窗口，但声呐强回波同时混入贯穿画面的横纹和很长的竖向延伸；B/G 都过宽。原亮度控制仍不能证明应在哪个高度裁去下方连续回波。晚期相机下端又截断。未据相机形状硬裁声呐或把亮核心任意缩为全目标框。

原亮度对照实际已查看：DataSet/paired_assistant_mortar_late_supplement/raw-boundary-control.jpg（105856 frame 150、110411 主队列 ordinal 36）。此为边界诊断，不是配对时间认证。

## 可合并审核根

均在 DataSet/ 下，decisions.json 为当前决策，review-events.jsonl 保留事件：

| 审核根 | 决策记录数（含跨根重复身份） | 接受 |
|---|---:|---:|
| paired_assistant_mortar_late_review | 703 | 55 |
| paired_assistant_mortar_late_strong | 48 | 0 |
| paired_assistant_mortar_late_component | 100 | 25 |
| paired_assistant_mortar_late_manual | 131 | 82 |
| paired_assistant_mortar_late_supplement | 98 | 61 |
| paired_assistant_mortar_late_exhaustion | 483 | 0 |

合并候选来源：既有 DataSet/paired_visible_expansion/candidates.json，新增 DataSet/paired_assistant_mortar_late_supplement/candidates.json（98），DataSet/paired_assistant_mortar_late_exhaustion/candidates.json（483）。新增候选均沿用 source-inventory 与 camera_temporal_all 已允许身份及原配对。

H 虽构建 203 个候选，但只查看/决策页 0、12、24、36、84、96、108、120、132、180、192，共 131；页 48、60、72、144、156、168 没有审核，不计已看。其他版本重看的相同 sample 只算一次，1351 为跨根唯一身份总数。

## 验证与边界

[verification.json](../../DataSet/paired_assistant_mortar_late_exhaustion/verification.json) 对全部 223 accepted 复核：声呐源、相机图、原相机标签及审核图 SHA256 均匹配；声呐坐标有效；相机框和 source-inventory 原坐标/引用一致；身份允许且 pairing eligible；跨审核根接受身份无重复。图像审核已逐页完成上述计数，网页浏览器渲染不在本子任务中验证。累计导出由主任务负责。

此轮零 DS 调用，未改变相机框、配对时间、gantry、注册、正式 split、训练及原研究；未访问原 test 图像。框表达可见目标回波，矩形不可避免覆盖的支撑交叉不等于允许主动扩框追长支撑。所有 accepted 的 precision_sync_certified=false、expert_verified=false 保持不变；不将相机目标可见升级为两端精密时间已验证。
