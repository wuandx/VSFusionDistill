# paired_assistant_full_review：2931对选入、352对备用，按用户决定保留缺额

2026-11-13。按[事前计划](../../experiment/archive/paired-assistant-mortar-plan.md)完成持续双端审核、并行补充、独立库存核查和累计导出。**本版3283对助手接受：2931对选入，352对备用；29条各100，最后一条bomb为31，缺69。** 用户已明确选择“保留现有数量，明确报告缺额（推荐）”，不再以3000配额推动扩库、改时间或降低边界要求。这一决定仅接受数量缺额，不代表用户已逐框验收全部标注。

[浏览入口（本地产物说明）](../../ARTIFACTS.md#artifact-7842e0e73cac) · [使用说明（本地产物说明）](../../ARTIFACTS.md#artifact-b473334d4b1f) · [manifest（本地产物说明）](../../ARTIFACTS.md#artifact-61eb1a6d889c) · [数量（本地产物说明）](../../ARTIFACTS.md#artifact-39799e41ad0d) · [完整性核验（本地产物说明）](../../ARTIFACTS.md#artifact-7c5cf6ca52ab) · [血缘核验（本地产物说明）](../../ARTIFACTS.md#artifact-96f48a687b38)。

## 实际数量

| 类别 | 助手接受 | 选入 | 备用 | 满100条数 | 距每类1000缺额 |
|---|---:|---:|---:|---:|---:|
| 100lbs_aircraft_bomb | 994 | 931 | 63 | 9 | 69 |
| mortar_shell | 1204 | 1000 | 204 | 10 | 0 |
| incindiary_grenade | 1085 | 1000 | 85 | 10 | 0 |
| 合计 | 3283 | 2931 | 352 | 29 | 69 |

接受总数超过3000，仍不能用其他录音的备用替代182317的69个缺额。选入成员是在每条已接受序列上均匀取最多100，不是新增正式split。两侧同名图像、原相机JSON、两侧YOLO与COCO均已导出；没有只交声呐单边。

39个命名审核根中累计有8260条当前候选决定，去重后实际查看6273个sample身份；不同提案的重复审核不计新增样本。3283个接受身份全部有对应实际审核图及决定。相比旧885包，新增2398个接受身份。审核覆盖34条录音，接受分布在30条；另外4条mortar的全部允许来源候选已看但当前0接受，保留未决，不作为负样本或声称在所有新标注方法下都不可能可用。

| recording | 类别 | 助手接受 | 选入 | 备用 | 缺额 |
|---|---|---:|---:|---:|---:|
| 2023-09-20_171105 | 100lbs_aircraft_bomb | 116 | 100 | 16 | 0 |
| 2023-09-20_174439 | 100lbs_aircraft_bomb | 105 | 100 | 5 | 0 |
| 2023-09-20_175000 | 100lbs_aircraft_bomb | 107 | 100 | 7 | 0 |
| 2023-09-20_175506 | 100lbs_aircraft_bomb | 100 | 100 | 0 | 0 |
| 2023-09-20_175905 | 100lbs_aircraft_bomb | 107 | 100 | 7 | 0 |
| 2023-09-20_180506 | 100lbs_aircraft_bomb | 109 | 100 | 9 | 0 |
| 2023-09-20_180722 | 100lbs_aircraft_bomb | 101 | 100 | 1 | 0 |
| 2023-09-20_181139 | 100lbs_aircraft_bomb | 111 | 100 | 11 | 0 |
| 2023-09-20_182317 | 100lbs_aircraft_bomb | 31 | 31 | 0 | 69 |
| 2023-09-21_101416 | mortar_shell | 120 | 100 | 20 | 0 |
| 2023-09-21_101622 | mortar_shell | 123 | 100 | 23 | 0 |
| 2023-09-21_101840 | mortar_shell | 108 | 100 | 8 | 0 |
| 2023-09-21_102500 | mortar_shell | 126 | 100 | 26 | 0 |
| 2023-09-21_103140 | mortar_shell | 128 | 100 | 28 | 0 |
| 2023-09-21_103728 | mortar_shell | 139 | 100 | 39 | 0 |
| 2023-09-21_103927 | mortar_shell | 119 | 100 | 19 | 0 |
| 2023-09-21_104749 | mortar_shell | 118 | 100 | 18 | 0 |
| 2023-09-21_105017 | mortar_shell | 107 | 100 | 7 | 0 |
| 2023-09-21_105230 | mortar_shell | 116 | 100 | 16 | 0 |
| 2023-09-21_121124 | incindiary_grenade | 117 | 100 | 17 | 0 |
| 2023-09-21_121327 | incindiary_grenade | 130 | 100 | 30 | 0 |
| 2023-09-21_121539 | incindiary_grenade | 102 | 100 | 2 | 0 |
| 2023-09-21_122608 | incindiary_grenade | 100 | 100 | 0 | 0 |
| 2023-09-21_122855 | incindiary_grenade | 101 | 100 | 1 | 0 |
| 2023-09-21_123500 | incindiary_grenade | 115 | 100 | 15 | 0 |
| 2023-09-21_123841 | incindiary_grenade | 106 | 100 | 6 | 0 |
| 2023-09-21_124039 | incindiary_grenade | 106 | 100 | 6 | 0 |
| 2023-09-21_124915 | incindiary_grenade | 108 | 100 | 8 | 0 |
| 2023-09-21_125048 | incindiary_grenade | 100 | 100 | 0 | 0 |
| 2023-09-21_160551 | 100lbs_aircraft_bomb | 107 | 100 | 7 | 0 |

## 182317为什么只有31

[独立库存报告](bomb182317-camera-coverage-audit.md)复核本地与已保存官方归档catalog：gopro与ARIS各501张（140–640），原camera JSON仅146个（140–285），恰好覆盖现有temporal/source-inventory全部身份；292个原图和JSON的大小/CRC与归档目录一致，SHA与temporal输入记录一致。未重新下载整个归档。

现行时间关联下0–139映射为负SD索引，原归档也没有这些原camera导出与标签；286–640虽有图但缺原camera框，不能记作已标注库存遗漏。已有146张SD图全部实际看过，176以后明显截断且未重新完整进入画面；即使宽松纳入140–175，完整相机候选上界仍只有36。36是上界，实际双端接受31。原matches注明`incorrect gopro offset`，本轮未据数量擅改时间，也没有用注册补偿。结论只适用于现行对应、原标签和完整相机条件。

## 标注方法、方向和配对边界

保留原SD相机图与原框，声呐直接在raw坐标审阅可见目标回波框。B/E/G/K等算法与手工边界只是候选，必须实际查看两侧审核图后才接受；失败候选、撤销事件和替代提案均保存。K用于避免中央支架的外部延伸主导端点；grenade完整环P修订先前裁掉下环的候选，保留旧失败。轴对齐框内部支架交叠不能自动等同于框向外多扩，仍按可见边界逐帧判断。

声呐raw不翻转；相机640×360，声呐128×441/603/780；导出坐标按各模态自身尺寸归一化。用户提出的左右看似相反已作为显示方向说明保留，不靠翻图改标签或伪造几何一致。

沿现有ARIS—SD配对关联图像并做可见目标一致性审阅，不等于独立时间认证。116对保留既有checked window支持；3167对仍为`not_independently_checked`。所有样本`precision_sync_certified=false`、`expert_verified=false`、`training_ready=false`。原时间、gantry、3D注册、相机框、原研究目录和原test均未修改或用于新测评。

## 论文规模对照

| 论文/来源 | 数量事实 | 证据与限制 |
|---|---|---|
| CMHD §3.1 | 3000对；3类各10轨迹×100；按轨迹6:2:2为1800/600/600 | [原JATS XML（本地产物说明）](../../ARTIFACTS.md#artifact-835631a6a819)，不是LaTeX；具体录音/帧号/seed未公开 |
| CMOLD §IV-A | 约4700对训练和验证合计 | [保存的PDF正文抽取（本地产物说明）](../../ARTIFACTS.md#artifact-109cd67ccf39)第575行；不是4700训练对，不能套用CMHD划分 |
| 原UXO，CMHD §3.1转述 | 95轨迹、74437声呐帧、48462配相机、37278相机帧有框 | 全集口径，不是本版允许开发录音或已接受数量 |

CMHD声呐框来自3D投影与人工异常检查；本版为可见回波直接审阅，且在质量筛选后的接受序列取样。两者标注方法、可见性偏向与录音选择不相同。论文允许残余误差不能为系统性错位开脱，本版没有以该描述追认时间或几何链。相关原文与先前数量审计见[paired-paper-scale.md](paired-paper-scale.md)。

## 验证结果及失败留痕

- 全3283对源/输出/审核图hash通过，声呐原像素精确，相机与原JSON字节精确；3283个不同SD帧，两模态均无完全重复像素。
- 6566个模态框的COCO/YOLO往返通过，两侧COCO身份一致。
- 旧885对的图像、框和源字段全部保留。添加新接受帧后重新均匀取样，使其中10个sample的选入/备用标志变化；这不改变旧框，旧导出原样保留。
- 对全部决定（含未决）核对审核图及原图/相机标签hash。260条旧审核项未在spec内保存相机label hash，改对权威temporal原标签hash核验，通过；不是补造旧hash字段。
- 第一次追加审计因假定旧spec都有`camera_label_sha256`而抛KeyError，修正审计读取后通过。失败记在[provenance-audit-attempts.jsonl（本地产物说明）](../../ARTIFACTS.md#artifact-bc278083b6d2)，未改图、框或决定。
- 20条新增录音各一个实际导出预览，组成5页，全部实际查看，未见明显导出方向/坐标问题；[QA记录（本地产物说明）](../../ARTIFACTS.md#artifact-5f46ff0c24ec)。这是导出QA，不是独立准确率估计。HTML静态链接另核对，实际浏览器渲染未作为通过证据。

manifest SHA256：`07f27fe807d1e4ed90593b6825f6fbe595d156c69cd8a6d365e62bb2728e7d93`。

与旧825待双端候选重叠334，唯一并集3774=3283双端已审+491仅旧声呐待双端；不能合并为3774已接受。所有助手接受仍非专家真值。冻结的是本次交付清单和来源，不是正式训练/测评准入。

## 模型复核与交接

用户换用6.1-sol后，同12对旧G提案的当前判断与旧决定12/12一致；这是非盲局部复核，没有独立专家真值，不能断言视觉整体变好。更多接受量来自继续查看及候选边界修订，不能归因于模型升级。[同提案记录（本地产物说明）](../../ARTIFACTS.md#artifact-c83d3986d18a)。

细分报告：[root mortar](paired-assistant-mortar-results.md)、[bomb](paired-bomb-remaining-review.md)、[grenade](paired-grenade-remaining-review.md)、[grenade完整环](paired-grenade-complete-ring.md)、[后段mortar](paired-mortar-late-review.md)、[mortar独立QA](paired-mortar-independent-qa.md)。所有并行审核已结束，本轮未调用DS。导出脚本`tools/export_paired_assistant_full_review.py --verify-only`可重验；血缘脚本`tools/audit_paired_assistant_full_review.py`；说明脚本`tools/document_paired_assistant_full_review.py`只补交付文档及成员清单。

本次数据交付按用户数量决定收口。后续若开展训练，应单独冻结标签语义、配对准入、recording-level split与历史开发使用边界；当前未启动训练、未新划分、未读原test，不自动分出600对称未触碰test。
