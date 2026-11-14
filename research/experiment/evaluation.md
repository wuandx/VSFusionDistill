## 2026-11-14 camera-M已迁移5090正式训练，本地尝试已停止

用户授权部署192.168.10.100的WSL wzl目录。[部署报告](../复现/camera-baseline/weak-coverage-camera-m-5090-deployment.md)、[独立核验](../DataSet/weak_coverage_camera_m_5090_deployment/startup-verification.json)。远端根/root/wzl/weak_coverage_camera_m_teacher，独立source/数据/模型；实际GPU RTX5090D v2。全部9525文件hash、4711图与标注/组、GPU batch8/末batch2/推理/几何/rawEMA预检通过；源/数据/实现/初始化与本地相同、15配置字段路径归一后相同、8主要依赖版本一致。

保持camera4138train/573val、COCO fresh、seed0/batch8/200epoch/103600更新/无增广、固定epoch200 actual raw、每10epoch仅val。远端从COCO重新开始；主机改变及浮点差异披露，不拼接本地迭代。18:09:53远端epoch2的200/518，loss5.8408、约.196秒/步、剩余ETA5:37:26，估总约6h；此前3–5h粗估由实测更正。尚无新AP或完成结果。

Windows一次性任务WeakCoverageCameraMTeacher持久前台托管WSL，断开SSH后已继续；RestartCount0、24h上限，无周期。首次nohup随SSH退出未进入训练，记录保留。确认远端健康后18:09:31仅停止本地weak-coverage-camera-m-teacher.service，inactive/dead/MainPID0；最后epoch7的340/518，尚无epoch10 checkpoint，日志/状态历史保留于[migration](../runs/weak_coverage_camera_m_teacher/migration-to5090.json)。原研究只读、旧远端run保持；test/sonar图未上传，无test评价、声呐或KD训练；原开发史/标签/留出边界不变。

后续进度读远端runs/weak_coverage_camera_m_teacher/train.log和train/status.json；本地旧train/status现stopped_deployed_to5090，不再当运行中。完成后须确认epoch200/103600、actual raw/EMA身份、最终val及失败状态，再登记指标；不得重复注册/启动已有任务。

## 2026-11-14 用户确认数据并授权camera-M教师训练

冻结paired_weak_scene_coverage_pan_split的camera4138train/573val，在独立train/val副本训练；来源身份与配对集一致，[冻结](../runs/weak_coverage_camera_m_teacher/dataset-freeze.json)、[预登记](archive/weak-coverage-camera-m-training-plan.md)、[启动证据](../runs/weak_coverage_camera_m_teacher/startup-verification.json)。授权仅camera-only YOLOX-M，COCO fresh初始化、200epoch/batch8/seed0、每epoch完整4138样本/518更新共103600，无增广，主权重固定epoch200 actual raw；每10epoch监测raw val，EMA单列，不依据中间峰值换主权重。沿用原score.01/NMS.65/max100、各类AP/AR1和完整pooled/逐录音指标。

这更新旧“尚未授权训练”阶段；不恢复sonar/旧camera扩充队列，不授权test模型评价。仅相机train/val图像装载，test未复制或评价，原研究test关闭。新成员/迭代预算与旧版不同，旧AP不当单因素对照；旧开发使用、助手标注、来源少及场景缺留出的边界保持。


## 2026-11-14 弱场景覆盖优先的开发重划分

用户明确允许重分后，采用[新开发方案（本地产物说明）](../ARTIFACTS.md#artifact-7b6b78ded1da)：5229对保持，train4138/val573/test518，33/5/4录音、27/5/3保守组。全部27现有scene内z/tilt/roll联合条件进train，旧弱val/test录音可进入训练；因此本版受已使用val/test启发，不可称新未接触盲测，旧分数不套用。[报告](../复现/camera-baseline/weak-scene-coverage-resplit-5229.md)、[协议](../DataSet/paired_weak_scene_coverage_pan_split/protocol.json)、[核验](../DataSet/paired_weak_scene_coverage_pan_split/independent-verification.json)。旧版和数据保持；用户本次授权更新此前固定val/test成员约束。

组整体、模态身份共同、各模态原框、类ID与COCO根保持。train8scene、val5scene、test3scene；floor ellipse和两种bomb flyby无独立留出，mortar/grenade flyby仅val，test仅每类1保守组（bomb30对），N/A必须明确，不拼接旧场景结果。pan仅metadata诊断，10523092.42%仍有差异，电子边际/相机视图非全覆盖。原研究10test关闭，7未决不准入。后续fresh COCO训练并冻结模型/评价后才有本版成绩；不能将困难样本移出留出造成的AP变化当模型能力增益，若要验证这些弱项的泛化，需额外独立来源或独立分组对照。


## 2026-11-14 新增393配对后的固定评价成员

当前数据版本[paired_four_recording_expanded（本地产物说明）](../ARTIFACTS.md#artifact-9940a746ec7f)：5229对，train3433/val961/test835，42录音35保守组。新增393来自4录音/3组，全train；原4836角色/图/框保持，val/test索引和两端COCO与4836版字节相同。[协议](../DataSet/paired_four_recording_expanded/protocol.json)、[核验](../DataSet/paired_four_recording_expanded/independent-verification.json)、[报告](../复现/camera-baseline/four-recording-paired-expansion-5229.md)。COCO根与类别语义不变；新增相机框是助手新标注，声呐是助手可见回波框，非官方相机原标签/专家GT或精密同步认证。7未决无负样本标签且不在任何训练或COCO中。

保持4836版留出便于后续比较训练来源扩充；若研究覆盖效应，固定模型/初始化/训练预算/增广与评价成员，并同时报告样本数和来源数变化，不能把联合扩样差异说成单因素因果。旧4081/4836及旧模型结果保留，旧权重与当前留出的历史暴露边界不变，后续需fresh COCO。旧test评价及开发使用史保持，新test不称未触碰盲测；未授权新训练/模型test评价，原研究10test关闭。

## 2026-11-14 配对扩充与重新划分后的评价边界

用户允许扩充与重分后，当前新数据产物[paired_expanded_resplit_candidate（本地产物说明）](../ARTIFACTS.md#artifact-4f30fc00fd8b)为4836对：train3040/val961/test835、38录音32组；[协议](../DataSet/paired_expanded_resplit_candidate/protocol.json)、[核验](../DataSet/paired_expanded_resplit_candidate/independent-verification.json)、[数据报告](../复现/camera-baseline/paired-expanded-resplit-4836.md)。两端共用样本身份，各读各模态框，COCO类别1/2/3=bomb/mortar/grenade，file_name相对数据集根。8场景train，5场景三集合，mortar flyby无test，两种bomb flyby无val/test；缺口N/A，不补造独立来源。

旧4081及指标保留；旧权重接触过新留出的一些录音，后续须fresh COCO，不可直接用旧权重认证泛化。新split同时扩样/重分，不把新旧AP差归因单个因素；控制增广在本版固定train/val，若控制样本数量也须固定同版留出成员。125048旧val变新test、101416旧val变train等变化必须披露。已有旧715test评价/开发审阅史无法通过重分消除，新test不称untouched外部盲测；原研究另外10条test仍关闭。本轮仅数据建设，未新增训练或模型test评价；后续使用新test前冻结模型与评价方案。

## 2026-11-13 按用户要求制定条件覆盖新划分候选，尚未替换执行版

[新候选](../DataSet/paired_recording_condition_coverage_candidate/README.md)为22/4/4条、2200/400/400对，覆盖规则/精确名单/来源/限制与hash已保存，状态candidate_pending_user_review。当前所有既有训练结果仍对应旧6:2:2，不能混用新角色表；本次不改在跑任务。候选将每类21种精确名义主条件及次级电子边际值覆盖在train，并要求留出记录pan有同条件train支持；不认证真实姿态或让val/test覆盖所有条件。14种单组train-only没有独立评价，floor等仅训练不证明泛化。候选修订已受旧test使用启发，须披露开发历史；若采用，必须从固定COCO重新训练，禁止旧UXO权重作未见新val/test起点。[事前规则](archive/condition-aware-split-plan.md)。

## 2026-11-13 当前冻结test访问授权与使用登记

用户明确要求查看test，已按[预登记](archive/camera-s-test-evaluation-plan.md)仅评价camera S640×384 epoch200 actual raw，不据test选择权重/epoch/阈值或改split。[首次test结果](../复现/camera-baseline/camera-s-test-results.md)。访问仅当前paired_recording_split的600张相机test；原研究其余test仍关闭。此次之后当前test为已使用测试集，后续开发必须披露，不将其作为未查看最终评价或用于调参后报无偏成绩。其余模型test评价须预先确定并明确任务授权，不自动扩大此次范围。train/val结果与test分开列。

## 2026-11-13 用户指定逐类AP/AR表格

用户确认仅采用CMHD表2的指标列，不是新增教师消融实验。后续四项单模态baseline统一按bomb/mortar/grenade顺序报告每类AP@[.5:.95]与AR(maxDets=1)，整体pooled mAP与mAR(maxDets=1)，百分数；原AP50/AP75/AR10/100等完整结果继续保留。权重先统一actual raw，val与test分开。[汇总表](../复现/camera-baseline/per-class-baseline-results.md)已填已完成camera S；不把相机自身指标冒称蒸馏学生结果。

## 2026-11-13 三维首交点诊断边界

[sonar_ray_visibility](../复现/camera-baseline/sonar-ray-visibility.md)仅使用当前train两条录音六个既有开发身份，无拟合、模型指标或test。完整/直接可见表面同射线对照的raw左右/最近边不变，仅远边可减；这是无强度/外部场景遮挡的几何支持。10组分辨率通过、2组未通过，不以远边收缩认证真实框、姿态或15–22°条件角差修复。未改变当前训练/测评准入、GT、冻结split或既有注册。

## 2026-11-13 AMHS远端baseline与EMA权重更正

用户授权运行[声呐S与fixed640相机S](../DataSet/workstation_baselines/README.md)，[事前规则](archive/workstation-baselines-plan.md)。冻结train1800/val600，仅该两角色上传，test和备用关闭。两项COCO S backbone/neck、200epoch/batch8/seed0、固定640×640、等比缩放+右底pad114、无增广；声呐raw三通道与当前可见回波标签，camera原SD框不缩放不拉伸。工作站环境/权重hash一致，硬件不同须披露。最终raw epoch200只评val，pooled/逐类/逐录音完整AP/AR按既定口径。

更正旧记录：mmengine0.10.7 EMAHook.before_save_checkpoint会交换checkpoint字段，state_dict是EMA而非raw；raw应提取ema_state_dict中module.*。本地S/M当前脚本与文档称state_dict为raw有误，不能按目录名认权重；结束时自动val属于EMA，须另补实际raw的val评价。远端新脚本已按实际raw提取；未修改或追认旧读数。所有模型比较必须先统一权重身份。

## 2026-11-13 YOLOX-M同协议对照

用户授权与S同时运行[YOLOX-M](../runs/camera_recording_m/README.md)。沿用首轮相机数据/测量/预算/epoch200 raw选择；只增加M规模和对应COCO初始化。M使用作者发布并经全张量/数值前向验证的转换backbone/neck，S为mmdet发布COCO S，两者来源差异必须披露，不能把绝对差全部归因于规模。共享GPU时长不作独立吞吐比较；原test继续关闭。预登记、转换记录、预检与独立日志均已保存。

## 2026-11-13 首轮camera baseline执行准入

用户要求开始camera-only teacher baseline，[预登记](archive/camera-recording-baseline-plan.md)及[运行入口](../runs/camera_recording_baseline/README.md)已落实。1800train/600val相机图像与原SD框完成全量hash/解码/坐标检查，允许可辨认截断，不乘3不clip，不加载sonar，不要求精密跨模态同步作为本相机run的额外门槛。沿用已结项数据的筛选范围；不声称专家GT或消除选择偏向。YOLOX-S/COCO backbone-neck、seed0、200epoch、batch8、无增广、keep_ratio/native SD→640×384 pad114。epoch200 raw state_dict为主，EMA另存不混报；仅最终val，score0.01/NMS0.65/max100，完整COCO AP50/AP75/mAP/AR1/10/100与逐类/逐录音由workflow-local评测导出。原项目不改。此授权与执行记录更新旧“本次先审计不训练”阶段状态，不授权test评价；历史隔离限制仍在。

## 2026-11-13 用户确认并冻结recording-level 6:2:2

[划分入口](../DataSet/paired_recording_split/README.md)与[录音表](../DataSet/paired_recording_split/recordings.csv)现为当前3000对的角色依据：每类6/2/2条，合计train/val/test=18/6/6条、1800/600/600对。seed=42及完整算法见protocol.json；122608/122855保守同组。398备用不进入主实验，继承来源角色（243/113/42）。teacher、sonar-only及蒸馏共用；train拟合、val选择，test不参与拟合/选择。源图、框、时间与原manifest不变；逐样本清单和hash核验通过。

这替代下方历史记录中“当前尚未建立具体划分”的状态描述，不改历史事实。当前test仅为新run隔离，已有开发使用须披露；不认证全研究untouched final test。grenade test两条仅一个保守来源组，floor bomb单条仅在test；不按后续成绩重洗。原test访问限制继续生效，此次未启动训练或test评价。后续从固定COCO起点重训，不能沿用旧UXO教师权重。成员冻结不提升原精密同步/专家复核状态，训练其余准入与测量口径仍按下文执行。

## 2026-11-13 数据交付与训练准入

[当前数据包（本地产物说明）](../ARTIFACTS.md#artifact-387067fb2f13)已完成构建与标注交付。3000 对选入清单是数据集成员清单；398 对备用另计。启动训练或测评前，须单独冻结按录音划分的 train/val/test 成员及配对准入规则，原 test 访问约束继续适用。若实验依赖精密同步，应先按已记录的配对状态和时间偏移疑点做独立核对，再决定对应样本是否纳入。本次未建立划分或启动训练。

## 2026-11-13 截断准入更正及数量边界

用户明确允许可辨认的截断目标，纠正旧完整相机门槛。[新浏览页（本地产物说明）](../ARTIFACTS.md#artifact-a14061aa6c51)、[结果](../复现/camera-baseline/paired-bomb-truncated-results.md)。182317全146身份/13页本轮实际重看，新增115接受（110明确底部截断、5触底过渡），原31图/框/来源不变；该条146=100选入+46备用。累计3398=3000选入+398备用，30条各100、三类各1000；旧3283包保留，旧69缺额是旧准入历史，不再是当前数量。

新增camera_visibility与COCO attributes、YOLO关联sidecar；原相机JSON/框不动，旧样本缺新状态不表示全部未截断。全量3398原像素/字节/hash、6796框往返与去重通过；旧3283图/框/review/时间/来源全保留，仅182317旧10个选入标志转备用。4导出预览实际查看，HTML静态链接核验，未认证真实浏览器渲染。全部原标签只覆盖播放器0–9.94秒；14秒处无原camera框，本轮未新造框。精密同步疑点未解决（116窗口支持/3282未独立精密同步），非专家GT/CMHD标注方法复现/正式训练版本；无DS/test/训练/split/时间注册/原研究变更。

## 2026-11-13 paired_assistant_full_review 交付边界

本次固定交付3283对助手双端接受、2931选入/352备用：29条各100，182317为31，用户明确接受数量缺额69。不是CMHD严格3000/完整轨迹抽样或几何标注复现；保留缺额不等于专家GT或正式训练准入。116对沿用checked_window支持、3167未独立精密同步认证，所有precision_sync_certified/expert_verified/training_ready均false。未决不作负样本；相机原SD框与声呐raw方向保留，边界语义为可见回波。旧885接受/框/来源保留，但重新均匀取样改变10个旧身份选入/备用标志，必须使用本版成员清单。未建正式recording-level split、未训练/读原test/改时间gantry注册。数量收口不解决其他物理注册疑点。[报告](../复现/camera-baseline/paired-assistant-full-review-results.md)。

## 2026-11-12 paired_assistant_remaining 边界

累计885对助手双端视觉审核，按每录音最多100选793/备用92，六条足100；未冻结正式训练版本。862对not_independently_checked、23对沿用supported_in_checked_window；本轮不提升同步/gantry认证。可见回波框不等同整件物体几何框，旧注册工作揭示的边界语义疑点仍有效。未决不作负样本，不以3000配额降低质量门槛。无时间/注册/正式split/test/训练变更。[报告](../复现/camera-baseline/paired-assistant-remaining-results.md)。

## 2026-11-12 paired_assistant_expansion 边界

新累计615对由助手双端逐帧审核，523选入/92备用（仅五条足100，bomb23）；非专家GT，训练版本仍未冻结。592保持not_independently_checked，23沿用既有supported_in_checked_window，不将视觉目标一致升级精密同步/gantry验证。沿用可见回波框语义、质量筛选偏向与原SD框，不改时间/注册/正式split/test限制。旧825待审唯一并集1327仅615为双端已审，另712待复核。[报告](../复现/camera-baseline/paired-assistant-expansion-results.md)。

## 2026-11-12 paired_visible_reviewed 边界

338对为助手双端可见目标逐帧复核，三条各100选入300，备用38；原数据/时间/相机框不改。由已接受帧均匀取样含可见性选择偏向，不等同CMHD完整轨迹抽样，不能借3000目标改变准入。所有338的精密同步状态仍not_independently_checked，未冻结训练/正式split；DS high不能代替叠图审核。与原825待审身份重叠42，唯一并集1121不等于1121全部双端通过，更非专家GT。详情见[报告](../复现/camera-baseline/paired-visible-expansion-results.md)。

## 2026-11-12 配对交付纠正

用户目标为论文规模与声呐—相机共同配对。`DataSet/paired_paper_scale`是1120对来源关联候选，986框格式有效、825扣除既有配对不足后待核，正式训练准入0；COCO中包含161既有配对不足样本，禁止将格式通过等同准入。前版1120张声呐“完成”不表示任务整体完成。CMHD目标3000对/每类10轨迹×100，与CMOLD约4700对train+validation分开；4000待审队列非标注成果。既有同步排除与未验证状态保持，原SD框越界不自动裁切。详见[报告](../复现/camera-baseline/paired-paper-scale.md)。

2026-11-12直接声呐副本注记：1120可见回波框采用助手逐帧审阅与DS Flash高置信选框加录音抽查，作者分列，非全量人工专家GT。40录音概览后仅16录音导出，偏向可辨场景且类别失衡，不可当全部数据分布或CMHD几何框复现。没有新split/训练/test执行；未来训练冻结必须声明此标签语义、筛选条件和历史开发使用。见[报告](../复现/camera-baseline/sonar-visible-annotation-results.md)。

# Camera-only teacher：测评协议

2026-11-13场景分层更正：用户明确各集合分别选独立录音覆盖地面、支架、flyby等场景。最新供审候选为[scene_stratified_recording_candidate](../DataSet/scene_stratified_recording_candidate/README.md)，36录音30来源组，train/val/test为21/8/7条、1985/749/584选入对；原3318选入与398备用、框和图像不变。5种场景三集合都有，3种单组flyby仅train补充且val/test缺失；不能称全场景覆盖。z/tilt/roll/设置/pan为场景内平衡和差异披露，不再以pan≥95%硬门槛取代用户要求。旧28/4/4候选保留，推荐方向已替换。仅候选角色修订，旧训练协议不自动切换，未新训练/推理；采用须冻结并COCO重训。助手接受、用户/专家验收和精密同步分开，新test有开发历史。[报告](../复现/camera-baseline/scene-stratified-recording-split.md)。

2026-11-13扩录音候选注记：[expanded_paired_coverage_candidate](../DataSet/expanded_paired_coverage_candidate/README.md)36录音/3318选入+398备用供用户审阅，未激活。新增6录音318对助手接受不等于用户验收或精密同步；旧3000选入与398备用不变。候选按来源组互斥、宽条件与记录pan覆盖分配28/4/4，比例优先草案另存。floor155609仍是跨高度val、124735仍有电子设置差异、燃烧弹test两录音一来源组，不能宣称全条件充分或独立最终test。旧训练/协议不因此自动切换，新版本采用须另冻结并COCO重训。[完整报告](../复现/camera-baseline/expanded-paired-recordings.md)。

2026-11-12新固定注册实测注记：[120帧开发检查](../复现/camera-baseline/sonar-fixed-registration-refinement.md)已完成，其中9fit/111development_check，全部来自40允许录音，不是最终test。主QA新12可审/71需修/28错位/9不确定，不认证训练框或自动接受；操作者及mortar末12帧root接续边界见报告。完整投影无elevation门限诊断与主±7°框的QA分别记账；框非空不证明目标存在，候选间IoU不是GT IoU。正式split/训练协议未冻结到执行阶段，原test限制不变。

2026-11-12初始候选质量纠正：[来源核查](../复现/camera-baseline/sonar-initial-candidate-audit.md)确认未通过的PCA自动候选被直接扩大覆盖。人工接受权限仍保留；但不能把系统性错位交给用户批量重画后称自动投影复现成功。自动保留、人工修订、排除须分别统计并给出分母，当前没有40录音通过率。floor target修复的代码/数值测试通过仅认证映射实现，不追认注册或GT；唯一3D姿态仍不是用户框验收前置。全部允许录音覆盖、原test关闭和正式split/训练冻结要求不变。

2026-11-12人工整理补充：[用户筛选入口](../复现/camera-baseline/sonar-manual-curation.md)覆盖全部40允许开发录音，目标每录音100合格配对。旧“partial不准入”限定未经人工确认的自动几何标签，不能据此阻止用户保留或修订后接受；人工框与几何可信度分别记录。每条最终接受须身份/坐标/框范围有效、用户确认目标可见与SD配对，修订原因/历史可追溯。不设置唯一真实3D姿态、候选IoU稳定性或助手QA通过的额外人工门槛。论文为每类10轨迹×100/按轨迹6:2:2；当前40录音覆盖不是该随机抽样的完全复现，不自动建立新split或开启原test。数量合格与最终训练版本冻结分别记录。

2026-11-11固定注册实测注记：[mortar试验](../复现/camera-baseline/mortar-fixed-registration.md)已完成24组fit、冻结后第二轨迹check和独立重放。fit/check均为已观察开发身份，不是教师split或最终test；支持点带外距离0不等于完整框正确，候选框互相比IoU不是真值IoU。六帧框均不稳定、5 unresolved/1 uncertain，正式GT0；空观察帧不记0误差或负样本。本试验不改变下方测评协议和准入状态。

2026-11-11固定mesh诊断注记：[直接sonar试点](../复现/camera-baseline/sonar-fixed-mesh.md)已完成18身份两版投影/目视QA，固定s/R/t和单一beam符号候选均为我方明确假设，三类仍未取得正式GT。partial不准入、uncertain不自动当负样本；两版使用相同已观察开发帧，不是盲验。原测评/划分/训练准入未改变。

2026-11-11独立注册注记：我方`sonar_independent_registration`已实际求解但三类均未通过，候选矩阵不准进入正式GT。fit/holdout是几何开发诊断角色，不是新教师数据划分；这些开发录音不因holdout名称变成untouched test。camera pinhole近似、assistant轮廓及beam/elevation假设的边界见[报告](../复现/camera-baseline/sonar-independent-registration.md)。

2026-11-11审计注记（不改变下方测评协议）：[注册/标定核查](../复现/camera-baseline/sonar-model-registration-consistency.md)已通过历史notebook的软件数值控制，未通过物理mesh注册/逐录音精度验收。两版camera安装角不可混用；该差异不改sonar链。`mesh-registration.json`中的名义长度尺度候选不准作为正式GT来源；新训练、数据划分与最终test仍未准入。

2026-11-10，v2。原则冻结；**manifest、逐录音历史使用清单与具体数据版本尚未完成准入，未到训练或最终 test 执行阶段**。v1 原文保存在 [evaluation-v1-2026-11-10.md](archive/evaluation-v1-2026-11-10.md)。本版更正它把“从未被格式转换”当作测试隔离条件、默认新 test 可获得、以及没有区分原则冻结与实例冻结的问题。

## 研究问题

在固定数据、原生 camera GT、recording-level split 下验证 camera-only teacher。主开发结果回答新训练 run 对未进入该 run 训练的 recording 的表现。同录音 val/val_id 只作诊断。CMOLD 未披露评测集身份，本地 AP 与论文表 3 仅并列参考，不作能力差值或硬验收线。

recording-disjoint 只支持相应分布内的跨录音主张。UXO 为受控采集；不能据此称真实海域、未见实例或跨设备泛化。更强主张需要新的独立分组与覆盖证明。

## 数据角色与访问

train 用于拟合，dev/val 用于诊断和选择，final test 用于方案冻结后的最终评价。三个角色的 recording 必须互斥；相邻帧不能跨角色。每类和主要采集条件覆盖须登记，缺失就限制主张，不能按模型表现挑简单或困难录音。

历史用于比较模型或指导选择的旧 test 不再是未触碰 final test。本阶段保持原研究所标 test 的图像、逐帧标注、预测与新评价全部关闭；旧汇总只登记为历史，不能据之挑新方案。

**格式转换不是开发使用的充分条件，也不是未使用的证明。** 无须要求 test 从未拷贝或转换，但要核对是否进入训练、模型选择、诊断、阈值调整或基于结果的决策。旧 manifest 的 excluded 只说明那次转换排除，不能证明整个研究历史未使用。只看录音级来源元数据，不读取 test 内容以“找合适的测试集”。

不承诺 UXO 必有覆盖三类且完全未触碰的 final test。若不足，先做 recording-disjoint development 或 grouped CV，并声明开发历史；新增独立数据后再做最终外部验证。单类 bomb holdout 不能替代三类测试。继承的 DataSet/camera_recording_disjoint_v1 未完成且暂停使用。

## 数据准入

固定数据版本、recording 角色、类别/几何覆盖、历史使用、抽帧规则和理由；只在获准的 train/dev 上做图像与框 QA。记录 source release、标签坐标乘 3 的依据、是否 clip、排除规则、转换与标注 hash、逐帧 manifest。camera监督不使用sonar blob/projected；新camera-only准入应以camera有效性为依据。当前paired池仍可能继承sonar calibration gate，移除gate或扩大数据域须单列版本，不可混入配方消融。

新 split 需要从固定 COCO 起点重新训练。现有 t_camera_s 已见全部 37 条 recording，事后留出再评价原权重不是未见录音验证。旧 UXO 权重不能 warm-start 后仍宣称对该数据历史未见。

## 固定测量口径

camera、d0、GT=all、pooled COCOeval。主指标 mAP@[.5:.95]，同报 AP50、AP75、AR@1/10/100。附每类和每 recording 的相同指标、图像/GT/预测数。逐 recording 均值不能替代 pooled AP。无 GT 的面积桶标 −1/不可用。

工具准入仍有缺口：当前per_branch_metric及breakdown只导出AR@100，现存summary不能补造AR@1/10。未来非test评测器需显式导出COCO stats[6]/[7]与相应逐类/逐录音读数，或在发车前明确登记可执行的指标子集；本轮不改原代码。验收时不得把尚未支持的输出写成已完成。

记录 seed、初始化、epoch/iteration/曝光、输入尺寸与实际 pad、score/NMS/maxDets、类别映射、坐标还原、final/best、EMA 实际加载、resolved config、命令、依赖与 checkpoint hash。先固定 final-epoch；以后若改 best-val，预先登记且所有对照一致。

训练/评测几何必须自洽。几何实验同时改变 train/eval 的同一几何；仅 eval 改比例称 mismatch 诊断。增广一次只检验明确登记的一项变化。单 seed 可建立运行基准，不能支持稳定性或显著性；需要时对最少候选做配对 seeds。

## 失败分析与不确定性

只在 train/dev 检查错误、可视化，按固定类别/recording 报漏检、假阳性、类别混淆、IoU 与覆盖。保留整录音失败，不删除困难录音改善平均分。AP50/AP75 差不能单独分离定位、漏检、分类与排序原因；类无关 AP50 只提供局部证据。

条件允许时以 recording 为重采样单位报告不确定性；不得把相邻帧当独立样本。组数不足或单 seed 时明确限制。CV 各折独立初始化；若同一折同时用于方案选择和结果报告，称开发结果，或采用嵌套分组选择。CV 不自动消除整个研究的开发历史影响。

## 输出、验收与停止

每个新 run 保存预登记、manifest、resolved config、日志、checkpoint 身份、metrics、逐录音表和失败分析；结果追加到 [results.md](results.md)。数据/加载/坐标检查失败或非有限 loss 即停止，失败与偏离保留，不自动换方案继续搜。

进入后续蒸馏前至少有无 recording 重叠证明、可复核的开发读数、逐类/逐录音失败解释、教师在蒸馏训练集的预测来源。只有同录音高分时称“教师候选”。无独立 final test 时可称“开发协议下的教师基线”，同时声明外部能力未验证，不虚构 AP 验收线。

执行顺序及各实验的目的、唯一改动、对照、判定与停止条件见 [plan-camera-teacher.md](archive/plan-camera-teacher.md)。本轮只审计，未执行训练或最终测试。


## 2026-11-12 端部注册控制边界

新端部注册及固定pan控制均为既有开发身份，两个fit帧、一个同录音检查与三个跨录音检查，不是盲验或test。端部区间是助手假设；观察凸包覆盖不是GT IoU/可接受框比例。两run均未准入；固定pan控制不能改正式标定或训练GT。详见[报告](../复现/camera-baseline/sonar-endpoint-registration.md)。


## 2026-11-12 源运动时间控制边界

源onset版本是六既有开发录音的诊断，未通过全量物理同步准入。首录音改善不能部署/追认训练GT；旧fit矩阵基于旧时间，不能直接转为新版本注册。CMHD公开流程与我方诊断严格分开，自动框人工保留/修订/排除单独记账，原test关闭。[报告](../复现/camera-baseline/sonar-motion-paper-alignment.md)。


## 2026-11-12 时间对应准入补充

[gantry取样审计](../复现/camera-baseline/sonar-gantry-onset-sampling-audit.md)发现六开发录音运动首变化记录前均有约2.1秒空档，首次记录改变不等于真实首运动。第二段人工确认画面t约+1秒可见持续移动，不给出精确offset。源onset版本仍未通过同步准入，不以投影变好、论文残余误差或旧软件验证替代物理时间验证；先冻结可信时间对应再重新注册。


## 2026-11-12 gantry起点证据依赖更正

[来源审计](../复现/camera-baseline/sonar-gantry-gap-origin.md)：gantry_metadata的onset由首变化CSV行计算，二者一致不属于两份独立物理证据；公开ARIS标记为人工选帧，代码没有自动区分pan/平移。跨空档np.interp生成的位置不作为实测点认证。两bomb旧offset与公开GoPro联动公式一致不等于同步正确或错误。真实采集空档原因和可信时间仍未解决，不重新注册/训练，不以论文残余误差、拟合改善或模型旋转补偿代替同步验证。


## 2026-11-12 sonar_camera_continuous_timing

171105 的 SD—ARIS 连续配对在所查 +6.20 至 +55.95 秒通过，保留图像配对证据；173329 未通过，按用户意见移出本轮可靠配对候选。两条 gantry 末段平移时刻都未获得独立验证，均不进入几何投影候选集。仅针对本轮两条开发录音，不删除原数据，不改变正式 split 或原 matches。 [核对报告](../复现/camera-baseline/sonar-camera-continuous-timing.md)。


## 2026-11-12 已审核框辅助注册的测量边界

sonar_box_guided_registration与sonar_box_guided_full_trajectory中的IoU是3D投影框与助手可见回波框的一致度，不是AP或专家GT准确率。两轮使用相同开发录音，第二轮受第一轮结果启发，不能称盲测。主框是完整模型无elevation裁剪外包框，新旧按相同定义重算；±7°另列诊断。固定参数拟合成功不认证真实姿态/同步，原test仍关闭。正式split和训练数据未冻结。[报告](../复现/camera-baseline/sonar-box-guided-registration.md)。


## 2026-11-12 参考边界与几何准确度必须分开

sonar_projection_root_cause沿用505开发身份；42个宽比提示仅是探索性筛查，2个needs_boundary_review亦非用户已接受修订。不能将投影框直接替换助手框后据IoU提升声称几何改进。原始模型完整框、近表面框与padding控制分别报告；凸包不是声学轮廓预测。源代码/插值重放一致不认证物理时间或注册。三组控制无稳定收益，停止继续拟合；后续新增语义/同步/尺寸证据后重新预登记。见[报告](../复现/camera-baseline/sonar-projection-root-cause.md)。


## 2026-11-13 RGB估姿和无尺寸tag的诊断边界

RGB纹理对应的合成控制不能代表水下实物精度；真实6帧未过独立对应门槛，因此不生成声呐框。tag尺寸未知仍可有条件估相对旋转，但必须明确静止/相机模型假设、平面多解；角点噪声分位不含系统误差，不能据旋转差直接修gantry或时间。与原声呐框无关的观测也不自动成为物理GT。[试验](../复现/camera-baseline/sonar-rgb-pose-pilot.md)。

## 2026-11-13 连续方块及成像模型的诊断边界

[报告](../复现/camera-baseline/sonar-tag-continuous-camera.md)。单面留出视图仍用该帧四角估姿，不能称独立留出角点；三面留面只用另两面估姿才是独立预测。两种结果均是同录音开发诊断，不是最终test或物理标定。三固定模型未过留面阈值；自由模型低残差且内参触界，不能晋升为真镜头模型。绝对静止、米制位置与跨模态时间仍需独立证据；发布角差不得作相机选型或生产外参补偿目标。


## 2026-11-13 场景分层扩量候选，尚未替换执行协议

[scene_stratified_paired_expansion](../DataSet/scene_stratified_paired_expansion/README.md)为4061对（train2472/val874/test715），继承上一场景候选36录音/30来源组角色；旧3318选入与398备用均纳入selected，新增345/640提案由助手逐项双端接受，295未决排除、不作负样本。总数/每录音帧数不设3000/100上限；新增时间分层、距旧接受帧ARIS与SD index均至少2，按既定可辨截断规则与原SD框/raw声呐。5完整场景、3flyby独立来源缺口仍在，成员pan与设置重算，覆盖非全采集条件一致。尚未冻结用于训练，未改任何现有执行版或模型结果；若采用须冻结后固定COCO起点重训，旧UXO权重不可当作新版未见录音起点。新增助手判断、用户/专家验收与精密同步分别披露，候选test有开发史，原研究test关闭。[扩量预登记](archive/scene-stratified-paired-expansion-plan.md)、[核验](../DataSet/scene_stratified_paired_expansion/verification.json)。


## 2026-11-13 迫击炮flyby恢复候选边界

[scene_stratified_mortar_recovered_candidate](../DataSet/scene_stratified_mortar_recovered_candidate/README.md)为4081对，原4061保持，新增105856整条val20对。来源文件与原JSON存在不等于同步可用：110229/110411未决不纳入；105856只有发布映射下有限视觉兼容和20项明确助手接受，精密同步/物理注册/用户专家验收未认证。60提案中40未决排除、不作负样本。mortar flyby train11004916/val10585620/test仍0，不能报告全场景泛化或独立mortar flyby test。新增/旧成员与原SD/raw、组隔离及六COCO均核验，尚未替换当前执行版或启动训练。若采用先冻结并固定COCO重训，旧模型不当新版未见录音起点；新test有开发史，原研究test继续关闭。[事前规则](archive/mortar-flyby-recovery-plan.md)。


## 2026-11-13 训练场景完整性已复核，仍有条件外推

[复核](../复现/camera-baseline/train-scene-coverage-confirmation.md)确认4081候选的train2472涵盖已核查62来源全部8种类别×摆放×运动场景，val/test无缺场景。但当前25精确名义组合仅17在train；125048倾角、155609高度、160146倾角和124735/155609/160146/105856的部分电子设置在同场景train缺失。仍须披露这些条件差异，不能把成绩解释成严格相同采集条件下只换录音。mortar flyby16train/20val/0test和两train-only缺口保持；本轮未改执行版、未启动训练。用户方向认可不代替逐框/同步认证。


## 2026-11-13 用户确认4081对划分的场景准则

用户明确“可以只要训练集里有就可以了”，接受当前4081对的划分方案：train2472/val894/test715，训练集含全部8种类别×摆放×运动场景即可，不要求所有高度/倾角/电子设置组合均进train。已披露条件差异和独立留出缺口保留；成员/框/角色不变。[用户确认及文件hash](../DataSet/scene_stratified_mortar_recovered_candidate/user-split-confirmation.json)。这是划分方案确认，不升级为逐框专家/精密同步认证，也未授权或启动新训练。

## 2026-11-13 新版scene_camera_m_baseline / scene_sonar_s_baseline执行实例

用户要求修复新版数据执行兼容，现独立train/val副本为DataSet/scene_expanded_baseline_trainval（2472/894对，COCO类别1bomb/2mortar/3grenade）；固定候选角色与框不变，test715不进入包。files-sha256.json的SHA256为57104b3cf4344408970a6af9d010f1ec1847d74db89519190ea6e8e7981494f1。新版命名run使用tools/run_scene_baseline.py：camera-M/sonar-S、COCO backbone/neck、随机3类head、keep_ratio/右底pad114 fixed640、200epoch/batch8/seed0、无增广、309step/epoch与61800更新；每10epoch监测val raw而不选best，主结果epoch200真实raw，EMA显式另列。保存hook与live模型逐项核验raw/EMA身份，未来不再凭state_dict名称判定。评测只允许train/val，pooled与逐类/录音AP/AR由同一评价器输出，逐scene分析仍按总方案执行。

两项最终GPU预检与功能控制已通过，正式训练未启动、长时resume未验证。本条仅绑定这两个新版run，不追改旧run的输入、标签或结果；旧入口不再用于新版。尺寸类别关联、正样本筛选、场景留出不足和test开发历史保持披露。[实现报告与命令](../复现/camera-baseline/scene-expanded-baseline-implementation.md)、[文献尺寸证据](../复现/camera-baseline/sonar-input-size-literature.md)。

2026-11-13执行状态追加：用户明确授权上述两项正式并行训练，已进入实际epoch1迭代；此前仅预检的历史描述不再限制本次已授权执行。数据/配方/最终raw选择保持，test仍关闭；启动证据见runs/scene-baselines-startup-verification.json。

2026-11-13用户转向：停止两个200epoch并行run，单独执行scene_camera_m_pilot，10epoch/3090更新，保留原200epoch LR计划前缀，第5/10轮验证/保存，epoch10实际raw作为诊断读数。不是最终200epoch baseline；原train/val、GT和test限制不变，不自动恢复长跑。见archive/scene-camera-m-short-pilot-plan.md。

2026-11-14用户再次授权两项完整baseline并行。新attempt为各baseline/after_pilot/train，两者从COCO fresh train，预算恢复原200epoch/61800更新，其余协议不变；pilot10继续作为独立诊断、旧停止run保留。test未授权。见archive/scene-baselines-after-pilot-launch-plan.md。

2026-11-14结果核对：两项after_pilot 200epoch均完成，固定epoch200 actual raw val与同权重train自评已登记，未改用best/EMA。分组复算与诊断按archive/scene-baselines-final-results-review-plan.md执行，test仍未评价；报告复现/camera-baseline/scene-expanded-baselines-final-results.md。

## 2026-11-14 当前715对test的明确授权与评价记录

用户“看看测试集”授权scene_stratified_mortar_recovered_candidate内当前715对/7录音7组test；不扩大另有原研究test来源。固定after_pilot epoch200 actual raw两模型、现有成员/GT/输入几何/score.01/NMS.65/maxDets100，完成总体与逐类/录音/场景评价；未训练、选EMA/其他epoch或改数据。事前冻结输入/权重/config hash、复制与身份/坐标/类别/组互斥检查见DataSet/scene_baseline_test715，结果见复现/camera-baseline/scene-baselines-test715-results.md。此条更新此前“test关闭”的执行状态，仅对当前715身份成立。

本次后715test明确已有模型评价使用；保留其数据建设/开发审阅历史，不能称全研究未触碰外部盲测，不能按本次结果调参后仍声称保持独立。test五场景，mortar flyby与两种bomb flyby无test，保持N/A。
