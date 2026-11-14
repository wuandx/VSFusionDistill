## 2026-11-14 camera-M已迁移5090正式训练，本地尝试已停止

用户授权部署192.168.10.100的WSL wzl目录。[部署报告](复现/camera-baseline/weak-coverage-camera-m-5090-deployment.md)、[独立核验](DataSet/weak_coverage_camera_m_5090_deployment/startup-verification.json)。远端根/root/wzl/weak_coverage_camera_m_teacher，独立source/数据/模型；实际GPU RTX5090D v2。全部9525文件hash、4711图与标注/组、GPU batch8/末batch2/推理/几何/rawEMA预检通过；源/数据/实现/初始化与本地相同、15配置字段路径归一后相同、8主要依赖版本一致。

保持camera4138train/573val、COCO fresh、seed0/batch8/200epoch/103600更新/无增广、固定epoch200 actual raw、每10epoch仅val。远端从COCO重新开始；主机改变及浮点差异披露，不拼接本地迭代。18:09:53远端epoch2的200/518，loss5.8408、约.196秒/步、剩余ETA5:37:26，估总约6h；此前3–5h粗估由实测更正。尚无新AP或完成结果。

Windows一次性任务WeakCoverageCameraMTeacher持久前台托管WSL，断开SSH后已继续；RestartCount0、24h上限，无周期。首次nohup随SSH退出未进入训练，记录保留。确认远端健康后18:09:31仅停止本地weak-coverage-camera-m-teacher.service，inactive/dead/MainPID0；最后epoch7的340/518，尚无epoch10 checkpoint，日志/状态历史保留于[migration](runs/weak_coverage_camera_m_teacher/migration-to5090.json)。原研究只读、旧远端run保持；test/sonar图未上传，无test评价、声呐或KD训练；原开发史/标签/留出边界不变。

后续进度读远端runs/weak_coverage_camera_m_teacher/train.log和train/status.json；本地旧train/status现stopped_deployed_to5090，不再当运行中。完成后须确认epoch200/103600、actual raw/EMA身份、最终val及失败状态，再登记指标；不得重复注册/启动已有任务。

## 2026-11-14 用户确认后仅camera YOLOX-M教师正式训练已启动

用户“确定好数据集就开始训练吧先只训练教师模型的相机，yoloxm”，按[预登记](experiment/archive/weak-coverage-camera-m-training-plan.md)冻结已交付paired_weak_scene_coverage_pan_split，camera-only teacher新run [weak_coverage_camera_m_teacher](runs/weak_coverage_camera_m_teacher/README.md)。camera4138train/573val（33/5录音、27/5组），COCO-M fresh backbone/neck、随机3类head、seed0/batch8/200epoch、518更新/epoch共103600，无增广、keep_ratio fixed640右底114。SGD/LR/epoch schedule沿用原camera-M；数据与总更新数变动必须披露。新增393助手标注血缘单列，原图/框/角色不变，test不复制或载入，无sonar或KD启动。

4711相机图+血缘JSON/hash/解码/原框/COCO身份/组互斥通过，GPU预检batch8前后向/推理/逆几何/COCO张量严格载入/raw–EMA往返与最后batch2 loss/梯度有限；preflight和train实现/源/输入/初始化/配置语义hash相同。持久WSL服务weak-coverage-camera-m-teacher.service (Restart=no)已产生真实Epoch(train)迭代、有限loss，见[startup-verification](runs/weak_coverage_camera_m_teacher/startup-verification.json)。当前实际日志位置1epoch内320/518；这是启动快照，后续进度读取train.log及train/status.json，未称完成或有新AP。

主结果固定epoch200实际raw；每10epoch监测val，EMA单独导出，沿用score.01/NMS.65/max100，不选best或切EMA。旧val/test开发使用史保持，val5组、floor ellipse/两bomb flyby缺留出，原研究10test仍关闭。原研究目录只读，旧run/队列不修改或恢复；本授权替代此前审计阶段禁启动训练，范围只本camera-M。当前启动不代表收敛或覆盖收益。


## 2026-11-14 用户允许弱场景优先重分：train4138/val573/test518

[新划分浏览（本地产物说明）](ARTIFACTS.md#artifact-7b6b78ded1da)、[弱项对应与限制](复现/camera-baseline/weak-scene-coverage-resplit-5229.md)、[独立核验](DataSet/paired_weak_scene_coverage_pan_split/independent-verification.json)。既有5229对/42录音/35组只变角色，train4138/33录音27组、val573/5录音5组、test518/4录音3组；全部27种已登记scene×z×tilt×roll联合条件进train。上次弱项10585620、121539102、125048100、123841/124039212、15560957进入train，101416/104749原已train继续；新增四录音393仍全train。

用户本轮明确允许重新划分，覆盖优先替代此前固定5229版val/test约束；旧版保持。全组不可拆，原图/框/血缘不变，7未决不放行，无新训练/推理/AP。新方案受旧val/test诊断启发，属于开发协议，不能称未触碰盲测。floor ellipse与两种bomb flyby无留出，两类其余flyby只有val；test只3场景/3组、bomb仅30对。mortar flyby train只有10585620对，不含Min15；grenade左右gain5仍缺。实际留出pan支持7条100%、1条95%、105230为92.42%。名义联合覆盖不等于全部视图/设置或能力改善。

独立10458图像hash/解码、全COCO/YOLO、身份/录音/组、27联合与最少组独立枚举、pan复算、旧输入保持通过，跨角色编码/像素hash重复0。首版joint_only草稿paired_weak_scene_coverage_split因mortar pan28.4/30.1不推荐，标superseded保留；推荐paired_weak_scene_coverage_pan_split。原研究10条test关闭，旧评价史保持，后续需fresh COCO；优先恢复110411/110229、100927/101131、162055与11未登记相机对应，以补独立来源。


工具resplit_weak_scene_coverage.py枚举分配与导出，verify_weak_scene_coverage_split.py独立校验，document_weak_scene_coverage_split.py登记。完成目录不可重跑覆盖；无训练服务启动。

## 2026-11-14 四条新增录音双端扩充已交付：5229对/42录音

用户在全94审计后要求“继续”。本轮完成180126/124241/124440/125924各100个跨全程公开映射SD/raw候选的实际双端审阅，24项修框后相应页复看。最终100/100/93/100=393接受，124440序号17–23共7项声呐弱/破碎/空提案未决，不作负样本。新4录音/3保守组全train（124241/124440同组），DataSet/paired_four_recording_expanded/完整两端副本5229对，train3433/26录音22组、val961/9录音6组、test835/7录音7组；旧4836行manifest/图/框/角色全保留，val/test索引+COCO字节相同。新增相机assistant_labels是新助手标注，不误称original_labels或专家GT；精密同步未认证。报告复现/camera-baseline/four-recording-paired-expansion-5229.md，index.html有400身份逐对带框浏览和7未决。

重要错误留痕：早期finalizer把几何有效当目视接受，实际399+1但初稿称400/400且打印NameError；已撤回并保留premature-geometric-registration文件，旧脚本main现在阻止执行。review-decisions-final.json、review-summary-final.json权威393+7，普通入口已复制最终记录；旧报告及dataset/results末尾初稿标明作废。中间explicit-corrections因list别名漏4声呐修改，独立v2/v3差分重建explicit-corrections-final.json共24。勿再跑旧finalizer或把400当已接受。

独立核验：全部10458准入图像解码/hash、旧4836保持、393raw用PIL独立像素解码、COCO/YOLO全往返、组互斥、跨角色编码及像素hash重复0；400映射Decimal时间/精确fps复算、12固定首中末源SD独立重提取JPEG hash完全一致、源/旧输入不变。计划因导出补充有显式版本变更，旧hash由plan-before-export-amendment.md复核。HTML静态链接通过，真实浏览器未验证。tools/register_four_recording_final_decisions.py、export_four_recording_paired_expansion.py、verify_four_recording_paired_expansion.py、document_four_recording_paired_expansion.py可追踪全过程；完成产物不可直接重跑覆盖。

四条均L_to_R，只补bomb500/−34/roll90、grenade250/−42/roll90联合条件和grenade750/−22/roll0 Min15来源，未补mortar flyby/grenade−90 flyby。2897候选容量仅400实际审，其他未审。没有训练/模型推理/新AP；既有835test只副本及完整性访问，原研究10test关闭，旧评价/开发史不消除。后续若训练仍需授权和fresh COCO、固定本版train/val；下一步数据恢复162055有效共同窗口及11未登记视频具体ARIS对应，未计入本版。


## 2026-11-14 全94录音审计完成：4条优先双端补标，11个未分配相机片段需恢复对应

用户要求找更广场景并审查所有录音。按experiment/archive/all94-recording-coverage-audit-plan.md执行，DataSet/all94_recording_coverage_audit/保存94条metadata、84非原研究test各3帧抽查（55双端/29仅声呐，共252）、11未分配SD视频各5帧（55），全部21张录音页/11张视频页实际查看，10原研究test仍metadata only。报告复现/camera-baseline/all94-recording-coverage-audit.md，入口index.html、inventory-reviewed.csv、decisions.json、verification.json；当前4836图/框/split/manifest hash未变、无训练/推理、新准入0。

94=38已用+13三类有公开匹配相机未准入+11三类缺公开相机映射+10原研究test+22其他test_cylinder；后者是目标名不是测试集。13中4条180126/124241/124440/125924三帧双端清楚但无原相机标签，应优先补两端框（约2897路径/SD序号候选，不是GT），前者补bomb z500/−34/roll90，124241/124440补grenade z250/−42/roll90两种设置，125924补z750/−22/roll0 Min15独立来源。另7历史连续配对待恢复、173615相机原825框全越界且包含大片支架需重标、162055首段可辨而后段目标退出/地面混合，仅恢复共同可见窗口。

重要新入口：SD/FHD/UHD各76视频，有同名11段未被matches引用（非33独立段），均已实看；GX010018_05/_07地面flyby样，GX030012_04/_05 mortar flyby样，GX020014_12/_13 grenade flyby样，其余左右/过渡。具体ARIS ID未定，可能往返/子片段，不能直接认定新增录音；此前无匹配相机只限matches/native，不能当本地素材必然不存在。gopro_metadata.csv59行、UHD父片段timecode复核不能唯一确定对应，保存unassigned-timing-metadata.json。

更正122115：旧notes写grenade flyby−90，但原ARIS metadata全段tilt−34、pan span149.029°、roll0，三帧外观为扫视式变化；不能再作为已证实−90 flyby补充来源，轨迹/身份待核。不在当前4836内。84条按flyby且metadata pan展开span>30诊断仅该条触发。已保存原始metadata hash，不改notes。下一步优先四条补标+162055有效窗口，同时恢复未分配视频连续事件对应；阻断不是永久报废，未知不作GT。新增需保守repeat分组，额外173329/173615、100927/101131、120653/120912明确同组。

## 2026-11-14 用户授权配对扩充与重分完成：4836对/38录音

用户“加，可以重新划分”更新先前固定当前val/test的约束。已交付DataSet/paired_expanded_resplit_candidate/独立两端副本：原4081不变+755新接受对（19已有录音725、174711新录音30，另10未决），总38录音32保守组；train3040/22录音19组、val961/9录音6组、test835/7录音7组。8场景train覆盖，5场景三集合覆盖；mortar flyby train110049由16→38、val10585620，仍Min15 vs Max5；grenade flyby−90的125048从旧val变新test，训练细条件仍缺，不宣称泛化已解决。101416移入train补z750/−22/roll0，但新旧指标不可直接比较扩充收益。

[报告](复现/camera-baseline/paired-expanded-resplit-4836.md)、[双端浏览（本地产物说明）](ARTIFACTS.md#artifact-4f30fc00fd8b)、[独立核验](DataSet/paired_expanded_resplit_candidate/independent-verification.json)。755对实际双端逐对助手审阅；非专家GT/精密同步。174711第一版支架尾过长失败保留，revision2前30接受后10未决。两端解码/hash、原4081身份/原JSON/框、raw→PNG像素、COCO/YOLO往返、角色身份、组互斥、跨角色图像hash重复0通过。旧split与结果不覆盖；新目录完整实际图像无需引用此前图像目录，审阅血缘仍外链原源材料。COCO file_name相对数据根解析，类别bomb/mortar/grenade。

重要更正：110229/110411同样有历史unresolved_not_admitted配对阻断，不是只需回波框；397/1482/16412皆候选容量不是准入。未将上述来源或162055/四条待相机标注来源加入。原研究10条test仍关闭；旧715test已评价，新test有开发历史不称盲测。没有新训练/推理；旧模型接触过新留出，后续两模型均需fresh COCO重新训练。本轮只数据扩充与重分，camera-only队列不恢复。下一步如验证增广用本版固定train/val作对照；不可把移动困难录音后的val变化当泛化增益。

## 2026-11-14 继续扩充容量清点：397仅抽样，完整帧候选更多

用户再问还能否增加。执行tools/audit_paired_expansion_capacity.py，结果DataSet/paired_expansion_capacity_audit/；[容量报告](复现/camera-baseline/paired-expansion-capacity.md)。当前train21条除已有2472对之外，11161帧满足原相机框数值/正确SD文件或公开SD序号范围/同ARIS raw存在及成员去重；另外9条有原标签来源共5251帧，其中五条历史配对不足3769、四条声呐待审核1482（174711710、110229226、110411291、162055255）。共16412是路径和metadata候选，不是已配对GT；新增准入仍0，无训练或test新增内容访问。4条无相机框来源及173615797越界框未算入。

弱场景优先：110411可审291、110229226；已有train110049193总帧仅16接受，余177待复核（不能抹除既有未决）。100927725+101131828=1553可补名义弱条件但历史配对不足仍阻断；燃烧弹train124915余61只能加同来源，不补tilt−90独立训练来源。前397是每条约100帧的本地预审上限，不是素材上限；下一步扩完整有效窗口，控制相邻帧冗余，不能把数量大当新增场景或独立来源。未对这些候选全解码/hash/双端目视认证。

## 2026-11-14 新配对候选与上次弱场景对照：仅部分覆盖

用户要求先看能否补上次模型弱场景。已对照固定val读数、全94条metadata/当前train条件和新897双端映射，[报告](复现/camera-baseline/paired-expansion-weak-scene-coverage.md)，工具audit_weak_scene_candidate_coverage.py与DataSet/paired_weak_scene_coverage_audit/保存结构化coverage及12个固定双端视图和hash，无推理/训练/test新增访问。

397待审=迫击炮flyby200+普通bomb左右97+地面bomb flyby100，仅前200直接涉及最弱场景，但110229/110411 tilt−90而val105856 −60；110411 Max/5dB与val一致，优先中后段清楚团块/横向回波逐帧核框和对应，首帧不可辨，不能接收全100。实际查看train110049、val105856、候选110229/110411各首中末共12视图：val相机横向右截断、当前train及新候选相机主要竖向，不能宣称相机视图缺口已补齐。

101416声呐val9.36的名义z750/tilt−22/roll0可由100927/101131最针对性补充，但其历史跨模态配对不足未解除（Min/15dB vs val Max/5dB）；这200属于原500阻断候选而非397可推进池。燃烧弹flyby125048 camera68.85/sonar51.84当前无额外可直接配对来源：122115缺相机、125236原研究test不动。待标注124241/124440是z250/tilt−42/roll90左右运动，只能增加相邻条件，val123841/124039为roll0且已有train123500同名义条件，不能把定位问题全归没见过场景。下一步优先110411和100927/101131核配对，再追122115相机来源；当前新增准入0，val/test成员不改。

## 2026-11-14 用户纠正扩充目标为双模态配对，camera-only队列已停止

用户明确要相机和声呐配对数据集，不是camera-only扩展。此前prepare_camera_more_recordings.py已生成9条×100=900张相机候选，36页900帧全部助手查看；finalize_camera_more_recordings.py导出camera_more_recordings_trainval_verified（3372train/30条/26组，val894字节不变，hash/解码/原train保留检查通过），这只是单端中间产物，不能计入新增配对数据或替换当前4081对。

曾启动camera-only coverage队列，用户纠正时仍在expanded_plain GPU preflight，未进入正式训练；已停止camera-coverage-controls.service和camera-coverage-controls-validated.service，后者实际inactive/dead，两队列status标stopped_scope_corrected_to_paired。先前expanded_aug独立GPU预检通过，不是训练或AP。旧预检和首个JSON重序列化造成val字节hash不同的失败包均保留，不将旧status configured称训练中。原M/S完成结果不变。

按[新配对计划](experiment/archive/paired-more-recordings-augmentation-plan.md)增加tools/prepare_paired_more_recordings.py，生成[双端审核页（本地产物说明）](ARTIFACTS.md#artifact-0313dcaecaca)和manifest：900相机候选中897找到同ARIS帧raw，174711有3帧缺raw明确登记；五条历史camera–ARIS配对不足来源共500候选保留阻断（173329/100927/101131/120653/120912），另174711/110229/110411/162055共397候选待声呐框及双端审核。已重新看174711旧12帧pilot、110229新前12帧双端页，不升级为新配对准入。**新增接受配对0**，声呐框均未自动生成GT；当前4081对未改。SD/FHD图框修复与camera–ARIS精密同步是不同检查，不自动解除历史配对不足。

下一步应围绕双端有效回波框和配对证据继续扩录音，4条无原相机标签也需两端标注；teacher/sonar-only共用新增身份，在新配对train与固定val上验证覆盖/增广。禁止继续仅相机扩展实验或报告“新增900对”。94条范围：22其他test_cylinder、三类72；其中原研究test10关闭、11缺匹配相机片段、当前37已用、另外14有相机（10有标签、4缺标签）。本轮未新增test内容访问。

## 2026-11-14 新增录音审核：撤回遗漏时间映射导致的偏移判断

用户要求增加录音验证train/val覆盖与增广，随后指出图框时间对齐早已解决。首次94条存量审核预览漏用了已有修复：原生FHD JPG缩放后直接配SD框，不能作为录音偏移/不可用证据，相关判断已撤回，原预览保留作错误对照。现用tools/correct_recording_expansion94_previews.py复用camera_temporal_all的reference_sd及既有SD pilot，120有标签抽样映射118、缺SD2，原标签不改；已实际重看110229/110411/120912各12帧，修正后目标与框对齐。其他录音待修正视图审核，173615坐标数值越界另查，不自动裁框或排除整录音。[更正和存量报告](复现/camera-baseline/recording-expansion-94-audit.md)，[修正浏览页（本地产物说明）](ARTIFACTS.md#artifact-0c9333431c79)。

94条中三类72、其他test_cylinder22；排除原研究test10后62条，51条有相机，当前使用37条（train21/val9/test7），另14条相机候选（10有原标签、4需标注）。不能把素材数n_gopro当GT数。camera-only新增来源不应仅受声呐配对问题阻挡，但尚未批准全量标签或认证跨模态配对。下一步修正SD审核、source group核验和扩充候选；现有4081对/训练输入/模型结果均未改，无新训练或新增test访问。

## 2026-11-14 相机test原因解释：精细定位+局部视图/分类差异，不能唯一归为场景不足

用户问相机为何仍这样/训练场景是否不够。按[解释复算](experiment/archive/camera-test-error-explanation-plan.md)仅用保存预测做固定score≥.25候选统计与9帧train/test固定对照，无新推理/训练或调参。[报告](复现/camera-baseline/camera-test-generalization-explanation.md)，counts与图在runs/scene_baselines_test715_review/camera_explanation/。

test相机AP5098.68/AP7597.63，不是14.46%图没检测；715图无预测0，最高分错类15（12153914、1247351）。有正确类别候选IoU≥.5/.75/.9/.95的图数为705/699/549/250，明确是候选覆盖计数非AP。121539 mAP66.85、AP5094.06、AP7592.96；其名义z750/tilt−22/roll90组合train缺，但train122855已有roll90(z500/tilt−34)，不能说train完全没见roll90。实际看121124、122855 train与121539 test各首中末9图，画面/背景朝向与呈现有差异，仅支持场景内分布差异假设，不认证物理pose或单因素因果。

八宽场景train覆盖实际已达成；不等于联合细条件/独立来源充分。train100、val89.37/test85.54有跨录音落差，无增广可能相关但未受控验证；高IoU框误差不能全部归标签。当前没有证据要求推翻数据集或重分；后续若做泛化/覆盖对照仅train/val，不据此test挑方案或挪成员。仅解释，无训练继续。
## 2026-11-14 用户授权715对test评价完成：camera85.54/sonar67.73，已登记test使用

用户明确“看看测试集”，按[评价前登记](experiment/archive/scene-baselines-test715-evaluation-plan.md)对当前候选715对/7录音7组test评价，固定两个after_pilot epoch200 actual raw、原几何/score.01/NMS.65/max100，不比较EMA/epoch、不训练/重分/修框。未扩大至其他原研究test来源。[报告](复现/camera-baseline/scene-baselines-test715-results.md)；DataSet/scene_baseline_test715包含独立副本/冻结输入和权重配置hash，1430图解码/复制hash/框/类别/身份/组互斥通过，跨trainval图像hash重复0；独立1435文件hash/源输入/训练数据清单核验通过。每模型715身份输出无重复遗漏且预测有限。

主test结果（%）：camera mAP85.5357/AP5098.6799/AP7597.6320/AR187.9359；sonar67.7347/90.7444/76.6512/74.2193。各类test mAP camera bomb87.34/mortar92.92/grenade76.34；sonar80.69/59.24/63.27。五场景test mAP(camera/sonar)：bomb左右88.88/87.06，地面ellipse81.11/48.70，mortar左右92.92/63.51，grenade左右66.85/73.04，grenade flyby90.98/56.09；普通/地面bomb flyby与mortar flyby无test N/A。逐类在全test上评价而场景只在子集评价，其他图上的FP使类AP与同类场景AP不必相同。

声呐test较val51.38高，但来源/场景构成不同，不能据此认证泛化已解决；mortar test10314082.32 vs10474935.89差异仍大，地面15560948.70。完整metrics/predictions/weight-identity在各after_pilot/train/test_actual_raw_epoch200，汇总JSON/场景CSV在runs/scene_baselines_test715_review/。工具evaluate_scene_test715.py（独立prepare/evaluate）与report_scene_test715.py；不修改原trainval-only入口。

本次后当前715test已明确用于模型评价；原有数据建设/开发审阅历史保留，不称全研究untouched外部盲测，不据本次test调参后仍称独立。无test逐框专家复审或新增训练。
## 2026-11-14 两项200epoch完成并核对最终raw：camera89.37/sonar51.38，train均100

用户要求看结果，两项after_pilot状态completed，200epoch/61800更新、权重已导出、服务inactive/dead。按[结果检查预登记](experiment/archive/scene-baselines-final-results-review-plan.md)补同epoch200 actual raw train2472自评并复用val894预测按场景复算；数据/导出权重身份/父checkpoint hash核验通过，无新训练或test评价。[报告](复现/camera-baseline/scene-expanded-baselines-final-results.md)，完整JSON/逐录音与场景CSV/曲线/固定图在runs/scene_baselines_after_pilot_review/；各run/train_actual_raw_epoch200保存train指标与权重身份。

主结果（%）：camera train mAP100，val mAP89.3709/AP5097.3525/AP7595.6811/AR191.1680；sonar train100，val51.3790/84.3017/48.2690/58.3007。每类val mAP camera bomb94.28/mortar85.75/grenade88.08；sonar78.59/34.27/41.28。epoch200 raw主结果不按中间val峰值换best/EMA。完整run自身epoch10→200 camera76.35→89.37、sonar37.73→51.38；pilot是独立run，不拼接其68.31作为完整run早期轨迹。

六场景val mAP(camera/sonar)：bomb左右94.26/80.64、地面ellipse94.34/71.87；mortar左右88.74/38.56、flyby47.15/0.59；grenade左右97.36/42.82、flyby68.85/51.84。两种bomb flyby无val N/A。camera两flyby仍有局部泛化落差；sonar存在很大train-val落差且60epoch后平台，非仅短跑拟合不足。

固定score≥.25诊断与AP分开：sonar10585620/20 top1均grenade错类；10141693/120 top1错类，mAP9.36%；grenade左右top1类均正确但框不准，场景AP50100/AP7522.59。camera125048 top1错类46/100（不是短跑时100/100），105856类对20/20但框/重复预测仍差，AP5097.77/AP7515.70。实际看相机125048/105856与声呐101416/105856/123841/124039各首中末共18图及val曲线；生成54固定视图不升级全部目视审查。声呐显示扩宽不改训练几何。

两最终模型均能充分拟合当前训练标签，但不同模态/GT的AP不能直接作方法增益或蒸馏空间。保留类别—声呐尺寸关联、少来源、标注语义与无背景图边界，单seed与val开发历史不变。未评价test、未选EMA、未恢复训练。
## 2026-11-14 用户短跑诊断后重新授权两项200epoch并行，after_pilot已启动

用户明确“训练吧按照之前的两轮同时开”，按[登记](experiment/archive/scene-baselines-after-pilot-launch-plan.md)启动两个新attempt，camera-M与sonar-S均从各自COCO起点fresh train，不使用pilot10权重warm-start。原2472/894、200epoch/batch8/seed0/61800更新、无增广、keep_ratio fixed640、每10epoch验证保存、epoch200真实raw主结果与EMA另列保持，test关闭。

新输出为runs/scene_camera_m_baseline/after_pilot/train及独立train.log、runs/scene_sonar_s_baseline/after_pilot/train及train.log。服务scene-camera-m-baseline-after-pilot.service(PID9471)与scene-sonar-s-baseline-after-pilot.service(PID9474)；两边已至少epoch1第50/309及100/309，loss/梯度有限，无OOM，本机RTX5060Ti16GB并发显存约15.3GB。最新[启动快照](runs/scene-baselines-after-pilot-startup-verification.json)，[命令/服务](runs/scene-baselines-parallel-launch-after_pilot.json)。未完成、暂无新AP。

旧停止run与pilot不移动/覆盖，全部保留。仅增强launcher的--attempt输出隔离，原baseline训练/评测实现hash和原研究源码不变；新attempt原样复用此前GPU预检status，preflight/provenance.json明确原文件路径/hash及并未重新GPU预检，启动器和runner重新比对数据/初始化/实现/源码hash后启动。后续状态请查看新after_pilot目录和新服务，不能误读旧stopped_by_user目录或已完成pilot。无自动重启/自动提醒任务。
## 2026-11-14 camera-M10轮完成，train/val分布诊断：两类flyby落差突出

用户要求看各分布是否仍泛化问题。pilot已00:01完成，全部3服务inactive/dead，无长跑恢复。按[诊断预登记](experiment/archive/camera-m-pilot-distribution-analysis-plan.md)对epoch10 actual raw新增train2472自评，并复用val5/10预测按场景重新pooled COCOeval；源码/数据/父checkpoint身份hash核验通过，无训练/test。工具analyze_camera_m_pilot.py、report_camera_m_pilot_distribution.py；[报告](复现/camera-baseline/camera-m-pilot-distribution.md)，原始results/CSV/权重身份在runs/scene_camera_m_pilot/train/distribution_analysis/。

总体train mAP78.46/AP50~100/AP7599.67，val68.31/89.91/87.92；val5 mAP60.61→10 68.31仍改善，高IoU定位尚非完全拟合。三类train/val mAP：bomb75.67/71.91、mortar80.08/73.04、grenade79.62/59.98。场景train→val mAP：bomb普通左右79.28→77.53，地面ellipse70.81→68.87，mortar左右80.09→75.51，grenade左右80.31→81.28；grenade flyby75.68→15.78，mortar flyby78.37→33.97。bomb普通/地面flyby无val，保持N/A。

失败量化（固定score≥.25诊断，AP仍score.01）：125048燃烧弹100帧top1全bomb，任意类别IoU≥.75候选100/100，最高分框IoU中位0.874，支持分类混淆；105856迫击炮20帧top1均正确类、IoU≥.5候选20/20而≥.75仅9/20，top1框IoU中位0.649，val AP5096.04/AP7517.32，支持框偏差与排序问题。两flyby各仅一val来源；泛化落差不是所有场景失败，也不能从10epoch排除未收敛或唯一归因。固定27val图、曲线及2组train/val对照实际看过（非全量专家审查）；mortar train所看3帧竖直/截断、val3帧横向，名义z/tilt相同不认证RGB视图一致。grenade train nominal tilt−60/val−90只是记录差异，不直接证明因果。原图/框/划分/阈值保持，无新训练。
## 2026-11-13 用户中止并行长跑，改为单camera-M 10epoch短跑

用户明确“先停…先跑一个camera-only YOLOX-M，少轮…先看看有没有问题”。已立即停止scene-camera-m-baseline与scene-sonar-s-baseline两服务，均inactive/dead，原train/status.json标stopped_by_user并保留最后迭代与日志；分别epoch2第100/309及200/309，均无正式checkpoint，不能完整resume。原两项200epoch不自动重启。

按[短跑预登记](experiment/archive/scene-camera-m-short-pilot-plan.md)增加tools/run_camera_m_pilot.py与render_camera_pilot.py，camera-M单独从相同COCO起点重训10epoch/3090更新，batch8/seed0、原2472/894、无增广/keep_ratio fixed640不变；学习率保留200epoch方案前10epoch（warmup5、cosine T_max185/end185），不压缩退火到10epoch。第5/10轮验证与保存权重，epoch10实际raw主读数、EMA另导出；自动生成loss/LR/val曲线及9val录音首中末共27固定预测图到review，结束退出，不启动声呐/长跑。

WSL用户服务scene-camera-m-pilot.service(PID8966)已进入epoch1至少100/309，loss/grad_norm有限，无OOM，日志runs/scene_camera_m_pilot/train.log；数据与原baseline预检实现hash一致，仅新预算/监测频次入口不同。startup-verification.json记录当前唯一运行的pilot与两旧服务停止。初始ETA约18分钟，另有两次val/保存，供参考非保证。尚无新AP或短跑完成结果；下一步等5/10epoch的metrics与review产物再判断，不把10轮未收敛当最终能力。
## 2026-11-13 用户授权新版两项并行正式训练，已进入实际迭代

用户明确“可以没问题就开始跑吧两个可以同时跑”。按[启动登记](experiment/archive/scene-expanded-baseline-parallel-launch.md)通过tools/launch_scene_baselines.py在本机WSL Ubuntu-22.04 / RTX5060Ti 16GB并行启动scene_camera_m_baseline与scene_sonar_s_baseline，systemd用户服务scene-camera-m-baseline.service(PID8680)与scene-sonar-s-baseline.service(PID8683)，无自动restart。独立train.log与launch.json在各runs/scene_*_baseline下；工具调用退出后服务仍运行。

确认两项实际进入epoch1：camera至少50/309、sonar至少100/309，loss/grad_norm有限，无OOM/Traceback；并发GPU约15184MiB已用/867MiB空闲。状态与最新迭代见runs/scene-baselines-startup-verification.json（比本文起步数字更新），启动命令见runs/scene-baselines-parallel-launch.json。每项2472train/894val、200epoch/batch8/seed0、61800更新、无增广、fixed640 keep_ratio；每10epoch监测val raw并保存，final200真实raw主结果/EMA另导出。暂无模型AP，不扩大test访问，不改原研究或历史run。后续查systemctl --user show和两train.log；有OOM/非有限loss等异常保留失败，不自动改batch/几何。当前没有长期监控承诺或自动提醒。
## 2026-11-13 新版执行五项修复及实际GPU预检完成，未正式训练

用户授权解决旧1800/600、旧类别、M画布、raw/EMA身份及45000iter五项，并问论文如何处理尺寸。按[预登记](experiment/archive/scene-expanded-baseline-implementation-plan.md)增加tools/prepare_scene_baselines.py、scene_baseline_runtime.py、run_scene_baseline.py、evaluate_scene_baseline.py与功能控制脚本；[实现/命令](复现/camera-baseline/scene-expanded-baseline-implementation.md)。独立数据副本DataSet/scene_expanded_baseline_trainval已准备，两模态各2472train/894val，6732图全解码/源副本hash、框/类别/成员/17与7组隔离通过；另6741文件独立hash复核通过。新版COCO类别bomb/mortar/grenade=1/2/3，单模态相对路径可迁移，旧入口/候选/原研究不改。

最终M/S真实batch8×3×640×640、COCO逐参数载入、三类/全部尺寸前后向和val推理、框逆变换及实际checkpoint往返均通过，证据runs/scene_camera_m_baseline/preflight/status.json与runs/scene_sonar_s_baseline/preflight/status.json；最大误差0/3.052e-5像素。raw/EMA按每次保存时live模型核验并记录字段身份，本环境raw=ema_state_dict、EMA=state_dict；不能把preflight_identity当训练权重。初次预检保留preflight_initial，最终代码重检通过，源码hash一致。两模态894val评测器完美GT mAP1/错类别mAP0、缺图拒绝/未认证raw拒绝控制通过，非模型AP。正式训练必须显式--train并有同数据/权重/源码hash的预检证明；每10epoch监测raw val、最终epoch200 raw主结果，EMA明确另导出。实际样本和配置计算309step/epoch、61800更新。未启动正式优化器训练循环/未读test内容/未重新标注；长时resume未验证。

[文献记录](复现/camera-baseline/sonar-input-size-literature.md)：CMHD HTML/XML只明确resize640，不能推成stretch/letterbox；CMOLD PDF具体resize未知；UATD LaTeX明确高512宽按比例；YOLOX官方preproc确实等比例+114右底补边（其取整与我方有最多约1px区别）。补边是常规处理，不认证消除类别—尺寸/采集设置混杂；本轮保留keep_ratio，不擅自改stretch。
## 2026-11-13 新版两臂方案严重问题审查

用户要求检查camera-M/sonar-S的200epoch/batch8/seed0/无增广/final raw方案。[报告](复现/camera-baseline/scene-expanded-baseline-plan-review.md)确认当前train/val仍存在尺寸完全区分bomb/非bomb的关联，fixed640后条带宽105/136/106对186，不能把高AP直接解释成目标语义泛化。四COCO每图1框，不能估无目标水域误报；mortar flyby train16占0.65%，两种bomb flyby无val。旧转换/训练脚本硬编码旧数据、旧类别顺序、384画布/45000iter及M的state_dict raw误名，须另实现新版，未证明新版run已出错。保持现有划分与首轮配方，先补实际加载/权重/几何预检。

本轮只读复算四train/val COCO：路径缺失0、越界框0、train/val来源组交集0；未全量解码/hash/视觉复审或执行训练。无增广与final raw可作受控baseline，不是官方优化配方或最佳性能；LR区间180而T_max185仅需如实登记，非致命故障。未训练/推理/读test内容、未修改原研究或已有方案。
## 2026-11-13 不蒸馏的论文相关baseline建议

用户进一步询问可做哪些论文级别baseline，暂不考虑蒸馏。已核对CMHD本地XML/发布商HTML、UATD本地LaTeX及YOLO-SONAR论文与RT-DETR官方实现，写[候选与实验建议](experiment/archive/scene-expanded-detector-comparison-options.md)。建议主声呐五模型YOLOX-S/M、YOLOv8s、Faster R-CNN R50-FPN、RT-DETR-R18；可选Nano和核验实现后的未蒸馏S-Ghost。优先补固定val的扩量/场景多样性对照、逐场景分析、实际推理效率，避免仅堆模型。跨家族保留合理优化器和同调参预算，不强套YOLOX LR；注明配方组合比较。已有主两臂方案不变，未训练/推理/读取test内容。
## 2026-11-13 4081对单模态baseline方案，未执行

用户确认数据准备完成，要求先给camera-only YOLOX-M教师与单声呐学生baseline方案。已写[方案](experiment/archive/scene-expanded-single-modal-baselines-plan.md)：沿用2472/894/715及21/9/7录音（17/7/7来源组），建议教师M/学生S、COCO起点、fixed640 keep_ratio、200epoch/batch8/seed0、无增广、epoch200真实raw，train/val评估含逐场景诊断，test封存。两臂各61800更新，不能沿用旧45000元数据；新旧数据/容量/val共同变化不能作单因素因果比较。执行前从引用清单构建独立train/val副本，不覆盖候选或原研究。

本轮只读核对当前train/val COCO各2472/894图且每图1框；新版category id为bomb1/mortar2/grenade3，raw声呐train四尺寸（128×780/441/603/771），val前三种，不可沿用旧编号或旧两尺寸统计。M转换报告已有516张量前向控制通过，运行前仍核对实际hash与加载。方案保留细条件差异及flyby独立留出缺口，不重分、不要求新同步认证才能做单模态baseline。未训练/推理/激活数据、未读test逐帧内容、未改旧执行协议；下一步按用户后续指令实施。
## 2026-11-13 用户确认采用4081对划分方案：train含全部场景即可

用户明确“可以只要训练集里有就可以了”。当前4081对/37录音方案获划分层面确认：train2472/val894/test715，train覆盖全部8种类别×摆放×运动场景即可；不要求所有高度/倾角/电子设置组合均进入train。不要为已披露的细条件缺口反复重分或再次请求同项确认。[确认及成员hash](DataSet/scene_stratified_mortar_recovered_candidate/user-split-confirmation.json)。原候选文件、成员、框、角色不改，原有条件差异与独立留出缺口继续披露。此次不是逐框专家验收、精密同步认证或新训练授权，尚未启动新训练。

## 2026-11-13 用户要求再确认train场景覆盖：8/8通过，细条件非全覆盖

用户认可候选方向，以训练集覆盖场景为重点，要求再核对。按[计划](experiment/archive/train-scene-coverage-confirmation-plan.md)独立复算当前4081候选manifest/recordings/6COCO/3清单及官方notes，范围47库存+15额外=62非原test来源。train21录音/17组/2472对，类别×摆放×运动共8场景全部出现；当前37与库存62场景均8，val/test无train未见场景。[报告](复现/camera-baseline/train-scene-coverage-confirmation.md)、[JSON（本地产物说明）](ARTIFACTS.md#artifact-2d6be42a11f9)、[CSV（本地产物说明）](ARTIFACTS.md#artifact-8a2e3d2111f5)。

细条件不可夸大：当前25精确名义组合train17；库存34（含不可用来源）。5条holdout有同场景单项/设置缺口：125048倾角−90(train−60)、124735 Min/gain15/Enable150V0；地面155609 z1250(train1000)、160146 tilt−38(train−32)，两者Min/gain15/Enable150V0；mortar105856 Max/gain5/Enable150V1不在train110049。全部列表见报告。mortar flyby train只有16对，出现不等充分；2train-only/1部分留出缺口保持。未重分成员/框/角色，无训练/推理/原test内容访问。用户“可以”是方向认可，不升级逐框/专家/同步验收或训练授权。后续沿4081候选沟通，若用户要求细条件全覆盖再另版，不能静默挪留出。

## 2026-11-13 用户授权迫击炮flyby处理，恢复105856的20对val候选

按[预登记](experiment/archive/mortar-flyby-recovery-plan.md)处理105856/110229/110411三条非原test来源。[报告](复现/camera-baseline/mortar-flyby-recovery.md)、[三条来源时间对照（本地产物说明）](ARTIFACTS.md#artifact-9ab93db696df)、[4081对新版场景浏览（本地产物说明）](ARTIFACTS.md#artifact-318e1cce8c85)。105856修框60项实际双端看完，接受序号40–59共20，0–39边界/拖尾未决；新录音整条val。37录音31组，train2472/val894/test715，旧4061身份/图/框/审核/角色保持。mortar flyby train11004916/val10585620/test0，仍缺第三合格来源；5完整/1部分/2train-only，不称全场景完成。

110229所查声呐主体不可辨、110411发布impossible-to-match仍未解决，两条不准入，不因有SD/框就认证配对。723身份数值映射/JSON/hash、36SD重解像素核对；三条各12固定概览实际查看，时间接触图实际看10585615/11022916/11041121时刻，未称看完195×4Hz或所有723视觉。105856仅发布映射下有限视觉兼容，不精密同步/专家认证；人工若推进只看来源页具体问题，不批量重标。20帧约9.28–13.67秒，允许可辨截断。源码及全部未决/追加事件保存。

独立核验旧4061保持、723源、195timeline raw hash、8162导出hash解码、20raw像素、6COCO/3清单、31组互斥/跨角色hash重复0与3静态页166链接通过；浏览器未认证。新候选未激活、未训练/推理/读原test。下一步用户看20对与两条未决对照；若采用再冻结固定COCO重训，不使用旧模型当新版未见录音。旧4061候选不改。

## 2026-11-13 解除3k/每录音100帧限制，场景分层扩充至4061对候选

用户允许4000多或更多，优先共用录音与各集合场景覆盖。按[事前计划](experiment/archive/scene-stratified-paired-expansion-plan.md)继承36录音/30来源组角色，旧3318选入+398已接受备用全部纳入，首批32录音×20新提案实际双端审阅640，接受345/待修295，共4061对；train2472(21录音/17组)、val874(8/6)、test715(7/7)。总量和每录音配额均无上限，20仅审阅批量。[分场景浏览/全部配对（本地产物说明）](ARTIFACTS.md#artifact-dcdb7635c6e3)、[报告](复现/camera-baseline/scene-stratified-paired-expansion.md)、[核验](DataSet/scene_stratified_paired_expansion/verification.json)。

5场景三集合覆盖，3种flyby仍各一接受来源组，val/test缺口不因增帧消失。原3716只完整性复核，非本轮新目视/用户验收；新增345助手判断、精密同步未认证。新成员pan/设置重算，同场景train pan±5°支持最低56.52%，仅诊断。旧membership及100帧标志另存历史字段，原图/框/审核/角色不改。早期decide覆写快照已修追加事件，3次收回依工具历史重建且原时间未知；首次export的frame字段KeyError修正后成功，见报告。工具expand_scene_stratified_pairs.py/export_scene_paired_expansion.py/verify_scene_paired_expansion.py。

独立核验3716保持、640提案源hash、8122导出hash解码、345raw像素、全部原相机框、6COCO/3清单、组隔离/跨角色hash重复0、36预览/37静态页12328链接通过。实际看160146/124735新版概览，浏览器未认证。未激活/训练/推理，原研究test内容仍关闭；候选test有开发史。下一步用户看新版，若采用再冻结并固定COCO重训；还有未审池可扩，不能把数量当作独立场景来源补齐。

## 2026-11-13 用户明确按场景分层，新候选21/8/7待审

用户明确“各集合都覆盖不同场景：例如地面、支架、flyby等场景分别选录音进train、val、test”，优先相机与声呐共用。已按[事前规则](experiment/archive/scene-stratified-recording-split-plan.md)生成[新浏览页（本地产物说明）](ARTIFACTS.md#artifact-0fc3a69c3703)、[报告](复现/camera-baseline/scene-stratified-recording-split.md)。此方向替代下方28/4/4旧推荐，历史不覆盖。场景=类别×摆放×运动，z/tilt/roll/pan/设置作场景内平衡和差异披露，不再以pan硬门槛把场景挤进train。

原36录音/30组及3716身份不变，train21条/1985选入+286备用，val8/749+53，test7/584+59。5场景三集合都有：三类非地面左右运动、燃烧弹flyby、地面炸弹ellipse。地面160551 train/160146 val/155609 test，燃烧弹flyby124915 train/125048 val/124735 test。普通炸弹flyby182317、迫击炮flyby110049、地面炸弹flyby161916各仅1已接受组，暂train补充，val/test缺口明确，不称全场景完成。地面高度/倾角/设置和pan43.4/57.1%差异保留。

47库存外另核15条非test录音级来源：bomb flyby182600/182843 notes为gopro footage lost；floor flyby162251/162428无匹配相机；4条有SD但无原相机框是左右运动，不能补flyby。mortar105856/110229/110411待定点复核/修框、floor162055需修框，恢复后floor仍需第三来源。详细缺口见新报告/source-shortfalls.json，不扩大原test内容访问。

独立核验3716原身份/框/hash/选入备用、7432图像、6 COCO、组互斥/跨角色内容hash重复0、113链接通过；实际看新地面3+燃烧弹flyby3张首中末预览，浏览器渲染未验证。未激活、未重训、无新推理/新接受框，新增318仍待用户/专家验收，精密同步未认证。下一步用户看分场景候选；全覆盖仍需修框/补录音，不能拆帧凑来源。若采用须冻结并COCO重训，新test有开发历史。

## 2026-11-13 按用户要求扩充共用录音并联合划分，36录音候选待审

用户指出原30条上限不合理，明确优先相机与声呐共用以便蒸馏。已按research-workflow审计47非原test来源（原40+7旧投影残差排除来源），[报告](复现/camera-baseline/expanded-paired-recordings.md)、[推荐浏览（本地产物说明）](ARTIFACTS.md#artifact-adc723e0ca52)、[清单](DataSet/expanded_paired_coverage_candidate/README.md)。36录音30来源组，3318选入+398备用；新增6录音318对助手双端接受：17420096、11004916、12473542、15560942、16014653、16191669。7新来源700提案全部实际看过，旧110049只重看28接受16；旧另3条mortar只抽页复核，不称全序列重审。新增174711/162055声呐框混回波需修，5历史配对不足/173615相机越界保留；剩11条未准入，不作负样本。

推荐train28/2634、val4/284、test4/400；每类录音train12/8/8、val1/2/1、test1/1/2。val104749/105230/124735/155609；test175506/101622/123841/124039（末两同组）。floor ellipse160146+160551训练，155609验证，后者z1250而train1000，明确跨高度；floor flyby161916仅train。所有宽条件train覆盖，holdout记录pan同宽条件±5°支持95%–100%，不认证姿态；124735同宽条件train缺ReceiverGain15/Enable150V0。val bomb/grenade各42，样本与录音数不均衡，不能说全条件/全轨迹充分。

比例优先expanded_paired_split_candidate草案22/7/7保留不推荐（floor pan仅43/57%）；追加覆盖优先预登记后另建coverage_candidate。保守同组174200/174439、180506/180722、103728/103927、121124/121327、123841/124039、122608/122855。旧3398身份/框/选入完整，7432导出图像hash解码、700提案源hash、六COCO、YOLO坐标、组互斥/跨角色hash无重复/源clip与旧split hash不变独立核验通过。新增6导出首中末已实际查看，36预览解码/静态链接通过，浏览器渲染未验证（open_in_codex queued）。

旧split/运行中训练/源数据不改，新候选未激活未重训，新增用户验收/专家确认/精密同步认证均0。用户接下来审阅具体候选；若采用再冻结新manifest并从COCO重训，不能将旧模型用于新版未见录音验证。旧test开发历史披露，不称untouched final。工具expand_paired_recording_pool.py、prepare_expanded_paired_review.py、build_expanded_paired_split.py、verify_expanded_paired_candidate.py、finish_expanded_paired_delivery.py，全部命名产物保留。

## 2026-11-13 全30录音条件审计与新split候选已交付，待用户审阅

推荐候选[入口](DataSet/paired_recording_condition_coverage_candidate/README.md)、[30条照片/旧新角色/条件浏览页（本地产物说明）](ARTIFACTS.md#artifact-d0e2c45d2060)。22train/4val/4test=2200/400/400；bomb8/1/1、mortar6/2/2、grenade8/1/1。原3000选入/398备用完整，备用265/87/46不使用。21种精确主条件（摆放/运动/notes z/tilt/roll/pan），14种仅一来源组均train-only；每类电子设置边际值/MinMax Transmit覆盖train。每条holdout≥95/100帧pan可在同主条件train找到圆周≤5°样本，实际99–100；不冒称物理/RGB姿态或联合全部设置覆盖。floor160551、bomb flyby182317、grenade高zroll90 121539及两个flyby等因唯一主条件进train，不以AP选候选，但历史分析已看test需披露。旧模型不能当新划分留出，需固定COCO重训；本轮未激活/未重训/未改旧split/源数据。

最终val：175506、103728、104749、121327；test：180722、101622、105230、123841。训练名单见README。所有3398身份/组互斥/图像hash跨角色不重复/源及旧split hash/当前matches notes/源metadata100帧每条核对通过；90预览源hash解码通过，全链接核验，实际看160551与105017首中末预览，非全部30视觉认证。所有14个train-only条件没有独立同条件评价，需如实限制，不能因train覆盖就声称floor泛化已验证。

先生成的仅名义条件草案paired_recording_condition_candidate（21/4/5）保留，不推荐激活；发现mortar105230短pan不能覆盖105017后，在最终候选前追加元数据覆盖约束并重算，所有模型AP未进入算法。最终脚本tools/build_condition_split_candidate.py写coverage_candidate，已有manifest拒绝覆盖。用户要求“分好给我看”，故停在具体候选供审阅，不启动新训练，不覆盖工作站在跑旧版。后续确认新方案再更新执行协议。

## 2026-11-13 test普通/地面炸弹叠图交付

[200帧浏览（本地产物说明）](ARTIFACTS.md#artifact-b8d483cf5f2c)、[统计说明](复现/camera-baseline/camera-test-bomb-review.md)。复用已授权camera S实际raw test预测，175506/160551各100。score.25/IoU.5：175506100匹配；16055127匹配/61错类（错类组最高分均grenade）/1定位不足/11其余未匹配。各12帧等距概览实际查看，前者支架、后者地面/孔洞/视角背景差异仅描述不因果认证；未全200人工验收。静态链接通过，无新推理/训练/label/split修改，不据test调参。

## 2026-11-13 用户授权camera S test评价已完成

[报告](复现/camera-baseline/camera-s-test-results.md)。当前冻结test600首次模型评价，和train/val同epoch200 actual raw checkpoint/hash，不读原研究其它test。mAP78.6456/AP50 89.2739/AP75 84.6866/AR1 79.3667%，三类AP/AR1：bomb58.62/59.10、mortar78.32/79.75、grenade99.00/99.25。6录音mAP：17550697.59、16055117.23（floor）、10184079.84、10250076.81、12260899.27、12285598.87。test高于val说明录音/条件差异明显，不能概括所有跨录音失败，不能单一归因或把本相机结果当论文声呐学生。test已开封，后续不得据其调参后称untouched最终评价。600图hash/解码/标签坐标通过，3类代表GT概览已看；无新训练/label/split变化。

## 2026-11-13 camera S train/val自评排查完成

[报告](复现/camera-baseline/camera-train-val-gap.md)、[真实预测对照（本地产物说明）](ARTIFACTS.md#artifact-a7247ef120f7)。同epoch200 actual raw：1800train pooled/逐类/18逐录音mAP/AP50/AP75/AR1均100%，val mAP64.576/AP50 80.411/AP75 75.666/AR1 69.4。train0.01/.25/.5门槛均1800匹配/0额外框；val.25匹配502/错类88/未匹配10，FP142。1800原相机JSON hash/类别/框/加载ID逐项核对通过；18train+6val各首张清空GT后预测逐项完全相同，排除所查推理GT依赖。先前176次同类train近邻引用全部真实预测匹配；两组新增对照已实际查看，6组页面和静态链接已保存。支持训练拟合充分、跨录音落差，不独立认定背景/截断/200epoch为原因，不认证所有原GT语义或所有代码。无新训练/改label/split/test。下一步现有四run统一权重出数，需要时再登记背景/标记/尺度控制；无需用户盲查代码或批量重标。

## 2026-11-13 当前相机教师与论文baseline并列已核对

用户要求同级baseline比较，[报告](复现/camera-baseline/current-teacher-paper-comparison.md)。原始CMOLD PDF表3相机teacher mAP95.8/AP50/AP75=99.7/mAR1=96.9，本地M raw为67.37/86.85/79.51/70.25；mAP数值差28.43pp，但CMOLD相机具体规模/评价集身份未定，不作严格同级能力差。CMHD官方HTML/本地JATS确认RGB教师为M，但表2的M79.6/82.6和S78.5/81.5都是声呐学生成绩，不能当相机教师本体分数。无新增训练/test/数据变化。

## 2026-11-13 错分val与train近邻并排已交付

[全88查询页（本地产物说明）](ARTIFACTS.md#artifact-aa29eaebd5a4)、[方法/观察](复现/camera-baseline/camera-train-neighbor-review.md)。182317 54、121539 34错类帧，1800train的GT裁剪HOG+aspect检索；每行val+同类train2+预测类train2，train近邻跨录音。全身份/成员/静态链接核验，6组代表实际查看。182317部分大特写/截断与训练近邻存在可见外观差异；121539_0088已有同类近似视角训练帧121124_0714/121327_0791，因此不能简单归因“完全缺类似训练图”。非3D姿态/因果证据，未看全88、未认证浏览器；无新增训练/标签/split/AP/test变更。

## 2026-11-13 camera S两录音预测复核已交付

用户要求查看182317/121539：[200帧浏览页（本地产物说明）](ARTIFACTS.md#artifact-230fe696b83a)、[统计与解释](复现/camera-baseline/camera-two-recording-review.md)。actual raw epoch200原预测，绿GT红预测，score≥.25/IoU≥.5时各100帧中匹配44/58、错类54/34、其余未匹配2/8；0.01及0.5阈值统计分列，AP不改。182317错类主要bomb→grenade，121539错类21 mortar/13 bomb（按错类组最高分）。各12帧等距概览实际查看，未称全200人工审阅；全量叠图/CSV/JSON和HTML静态链接核验通过，不认证浏览器。没有新训练/推理/test/标签变更，不把现象直接归因某单一因素。

## 2026-11-13 用户澄清表2仅要指标列

不新增蒸馏或L教师实验。四baseline按每类AP@[.5:.95]/AR1与整体mAP/mAR1百分数汇总，bomb/mortar/grenade顺序，[汇总](复现/camera-baseline/per-class-baseline-results.md)。camera S实际raw已填：63.01/64.05、82.43/84.65、48.28/59.50，整体64.58/69.40。其余完成后同权重/同val口径补齐；完整AP50等不删，不使用论文型号文字认证当前实物。

## 2026-11-13 本地camera S训练及raw/EMA评价完成

camera_recording_baseline已完成200epoch，600张val自动EMA评价与实际raw补评均结束。raw pooled mAP=.64576048/AP50=.80411118/AP75=.75666140；EMA pooled mAP=.64887771/AP50=.81009221/AP75=.75877228。主raw结果runs/camera_recording_baseline/train/val_actual_raw_epoch200/metrics.json，权重身份记录weight-identity.json；旧val_raw_epoch200实EMA原样保留，evaluation-weight-correction.json明确映射，不再混称。epoch200 checkpoint sha256 edff61c275274a58112e8e408a25a9a76dd308c79de8cfaba3e6474dbdc974a0。未用test；本地M的raw补评仍待其训练结束。可复用tools/evaluate_local_raw_baseline.py --run camera_recording_m，已有metrics拒绝覆盖。

## 2026-11-13 16:00远端恢复启动方式修正

普通SSH内分离会话启动仍在短暂推进后无报错消失，不能视为成功恢复。随后改为Windows WMI Win32_Process.Create启动独立wsl.exe（Windows PID27276，ReturnValue0），WSL supervisor保持等待两项训练，远离SSH父会话；脚本tools/workstation_persistent_resume.sh、tools/start_workstation_persistent.ps1。真实模型仍完整resume epoch50，配置不变；独立WSL当前camera400/sonar401（PID跨WSL会话可能复用，始终核对命令）。断开SSH后间隔重连检查，进程仍存活、GPU持续工作、epoch51迭代持续更新。普通启动失败日志均追加保留。先前15:06中断根因仍不能完全确认；新方式已通过短期断连存活检查，不保证主机休眠/重启下存活。状态查camera-resume.log/sonar-resume.log，supervisor保存camera-persistent.exit/sonar-persistent.exit。

## 2026-11-13 15:58用户授权恢复远端训练

两run从epoch50/iter11250恢复，保留原epoch53/55中断日志，未保存的51至中断部分重新计算。新增tools/run_workstation_resume.py在原脚本基础上仅增加resume=True/load_from=各自epoch50；检查checkpoint epoch/iter、optimizer/param_schedulers/EMA及steps11250后恢复，使用MMEngine完整resume而非只加载模型。checkpoint hash保存各run/train/status.json；原状态备份status_before_resume.json，配置resume_config.py。分离新会话后台camera403/sonar404，日志/root/wzl/workflow_baselines/runs/camera-resume.log和sonar-resume.log。数据/超参/200epoch目标/最终raw val不变，test关闭。旧中断原因仍未确认，不能称已修复根因。后续看resume日志，不再只看旧train.log。

## 2026-11-13 15:56状态更正：远端两run已中断

本轮应用户进度查询实查：本地camera S183/200、M161/200仍训练；远端camera_s_fixed640日志停15:06 epoch53第50/225，sonar_s停15:06 epoch55第150/225。pgrep无run_workstation_baseline进程，远端GPU0%/181MiB，status.json的training已经失真。两run最后可用checkpoint均epoch50（40也保留），last_checkpoint指50。远端WSL uptime6:24，dmesg未检出OOM记录，原因未确认；不能据此声称OOM、正常完成或WSL重启。此次未改训练/自动重启，后续先查中断原因与检查point身份，再按原配方resume，不从头覆盖旧run。

## 2026-11-13 三维首交点实测：排除自遮挡修正横向错位

按research-workflow继续[三维射线对照](复现/camera-baseline/sonar-ray-visibility.md)，[浏览页（本地产物说明）](ARTIFACTS.md#artifact-9c4e3205ed51)。仅当前train的103728/123500各3帧，旧PCA与首轮box_guided冻结姿态共12组，不fit。严格三维方向首交点与全部交点比较，raw左右/最近边全不变；远边收缩通过分辨率门槛的10组为0.867–6.313cm，2组未收敛留档。解析平面/cuboid误差≤4.44e-16m，84真实资产射线独立求交误差≤4.89e-15m，输入hash不变。此结论仅目标自遮挡、无强度/外部场景遮挡、相同射线与raw坐标；不能推广到polar横边，也不认证真实框准确度。

已重看六幅RGB及两类48视图总览，仍无足够可靠新物理对应，未运行新AnP/PnP。可复用的是首交点控制代码；尚无通过独立验证的注册修正。首交点不能消除15–22°的RGB条件姿态差。原研究/标签/冻结split/运行中训练/论文正文均不改，新旧test图像与逐帧标签未读。后续几何路线仍须少数可跨视角确认的物理点或独立测量；不能以远边收缩声称已修好注册。六张新图解码与总览目视通过，实际浏览器未验证。

## 2026-11-13 四项baseline只读有效性审查

[审查报告](复现/camera-baseline/current-experiment-integrity-audit.md)与[复算](复现/camera-baseline/integrity-audit/checks.json)：未发现需立刻停训的基础链路错误；4800框坐标往返≤5.684e-14，远端/本地camera COCO完全一致，实际评测器完美预测AP1/错类AP0，train/val来源组互斥。新发现train/val中bomb全128×780、其余两类全128×441，fixed640后内容宽度105/186可暴露bomb，限制语义/跨设置主张，未证明网络已利用。分组枚举按组数量先选，唯一双录音组导致grenade test固定，非全可行split均匀随机；不重洗，披露来源组有限。实际epoch110证实raw/EMA457个相机张量不同，本地自动val_raw实EMA，统一权重补评仍待训练后执行。GT审阅不等专家精度，全正样本不支持无目标误报率；配对/182317疑点仅在蒸馏依赖对应时准入，不否定单模态。S/M预训练不同源、跨机画布单seed比较及论文不同配置边界保留。四run未改/未停，未读test内容。下一步训练结束先核对权重身份再评价，勿以loss或高AP替代这些验证。

## 2026-11-13 AMHS工作站两项baseline已启动

用户授权在192.168.10.100执行sonar-only YOLOX-S和fixed640 camera YOLOX-S。[部署/连接/证据](DataSet/workstation_baselines/README.md)。连接为本地WSL id_5090→Administrator@IP:22→工作站WSL root，不是git2222。新数据/root/wzl/dataset/paired_recording_trainval仅1800train/600val，4800双端图像与标签，test/备用未传；远端9609文件hash/全图解码/组互斥/源代码快照核验通过。独立代码和结果/root/wzl/workflow_baselines；未覆盖远端旧repo。GPU5090D v2，环境版本/COCO S hash与本地一致。

两项200epoch/batch8/seed0/45000iter、FP32、COCO backbone-neck、无增广、固定640×640 pad114；camera原640×360不拉伸，sonar raw等比缩放。真实batch前后向/推理、初始化逐项相等通过，14:20两日志均epoch1第100/225步、loss有限、约3h估计，总显存约12GB。camera PID952/sonar953，日志runs/camera-train.log与sonar-train.log，状态各run/train/status.json；最新日志才是进度。独立source快照来自本地实际代码，避免远端旧commit差异。

重要更正：mmengine EMAHook保存state_dict为EMA、raw在ema_state_dict module.*；之前本地S/M称state_dict为raw有误。远端按实际raw字段提取与val。**本地S/M结束后自动val_raw_epoch200实为EMA，后续必须如实标EMA并补真正raw评价后比较；补评尚未执行。**保留历史不静默改写。当前训练均不因此中断。下一步查两机状态、保留退出状态，再核验最终权重身份和val输出，test继续关闭。

## 2026-11-13 YOLOX-M对照已提交，与S并行

用户要求同配方新增M并行。[运行入口](runs/camera_recording_m/README.md)、[预登记](experiment/archive/camera-recording-m-plan.md)。M为depth.67/width.75、neck192/CSP2；数据hash、seed0、200epoch、batch8、45000iter与S相同核验通过。mmdet未列M预训练包，使用作者官方COCO M转换516个backbone/neck张量，原/转换hash与映射保存assets/checkpoints/yolox_m_conversion.json；输出数值控制max9.03e-6、真实batch8GPU前后向/推理、加载逐项相等通过。首次参考BN默认eps错误导致数值控制失败，按作者Exp eps.001修正参考后通过；未训练失败候选。S用mmdet COCO、M用作者COCO，比较不能只归因容量。M日志runs/camera_recording_m/train.log，状态train/status.json；独立后台进程已提交，S保持运行，未读test/改原研究。两者完成后各自动val raw epoch200，下一步检查实际训练进展和最终产物。

## 2026-11-13 camera-only teacher baseline已启动

用户要求进入训练，沿用research-workflow登记并执行[camera_recording_baseline](runs/camera_recording_baseline/README.md)。原SD1800train/600val全量图像hash、解码、坐标与6图目视通过；GPU真实batch前后向和推理、COCO backbone/neck逐张量加载通过。YOLOX-S现有camera分支，COCO起点、200epoch/batch8/seed0，实际640×384 pad114，无增广；类映射按名称，sonar不加载。WSL既有GPU env/RTX5060Ti，未改原研究或环境包。日志runs/camera_recording_baseline/train.log，状态train/status.json，launcher.pid；后台启动已确认进程，结果以状态/日志为准。脚本结束后自动用epoch200 raw state_dict只评val并保存完整COCO AP/AR、逐类/逐录音，不读test。无结果前不得称完成；失败停止保留，不自动改参。下一步检查进度/退出状态，再审核最终val产物。

## 2026-11-13 用户确认划分已落实

[冻结入口](DataSet/paired_recording_split/README.md)：seed42、每类整录音6:2:2，train/val/test=18/6/6条、1800/600/600对；备用243/113/42不进入主实验。角色CSV、3398身份索引、六份成员清单、输入/输出hash与核验均已保存。122608/122855按原始ARIS双轨迹备注保守同组；grenade test仅一个来源组，floor bomb仅test，限制已披露，不按成绩重洗。独立复核通过，源包不变，无图像解码/原test读取/训练/模型测评。evaluation与dataset入口已更新，论文正文不变。后续按当前清单准备加载和COCO初始化，完成其余训练准入再训练；本test不宣称全研究untouched final test。

## 2026-11-13 结项后划分文献核对与建议

已核对CMHD出版页/JATS、CMOLD本地PDF段落、YOLOX-ViT侧扫声呐KD的LaTeX：[划分依据与建议](related_work/dataset-split-after-closure.md)。建议当前3000对按类别分层、整录音6:2:2（18/6/6条，1800/600/600对），仍需录音级关联与历史用途审计、固定seed后冻结名单。备用继承来源录音角色。已有开发历史使新run隔离不等于全研究未触碰final test；按现行协议如实限定。未生成正式split、未读取原test内容、未训练、未改数据包或论文正文。

## 2026-11-13 数据集构建与标注结项

用户确认按当前版本结项。[数据说明](dataset.md)为交付入口：[当前数据包（本地产物说明）](ARTIFACTS.md#artifact-387067fb2f13)选入 3000 对（30 条录音各 100 对，三类各 1000 对），另有 398 对备用；[中英双语正文](paper/dataset.md)已完成。此阶段不再补帧或改框，旧包及审核记录保留。

后续若启动训练，按[测评协议](experiment/evaluation.md)先冻结按录音划分及配对准入，再使用数据。已记录的时间偏移疑点仅在实验需要精密同步时单独核对。本次结项不启动训练或测试。

## 2026-11-13 论文正文入口与过程记录归档

论文正文在 [paper/dataset.md](paper/dataset.md)，按用户要求调整为中英各三段，只描述数据来源、实际配对与标注、筛选与取样规模。模型辅助标注照实交代；同步疑点、未验收事项与划分状态留在[测评协议](experiment/evaluation.md)及数据交付报告，正文不主动和CMHD比较。`experiment/`顶层仅留results.md/evaluation.md，56份过程文件移入experiment/archive，相关链接已更新；数据与标注不变。此目录与写作约定也已同步到research-workflow技能、项目初始化脚本和AGENTS模板。后续论文正文统一放paper/。

## 2026-11-13 投影文献原文复核：区分正向、注册和直接可见表面

[复现用途与写法更正](related_work/sonar-projection-reproduction-use.md)。FLS 已知点正向是唯一 `(r,β)`，固定 `(r,β)` 的圆弧是逆向；8角点可能漏近面极值。CMHD §3.1 已是直接先例，不写首次。2504.04445 的最优性只对应近似PtL，2503.16066 的90%为共面仿真（一般约80%）。2001.03539/OceanSim可借鉴先按3D方向取首交点、再聚合到range/azimuth，而非把旧近表面控制升级为真回波；2606.06130 当前为RTX LiDAR近似。优先补可留出验证的同名物理点，再做估姿；先以已知位姿小对照检验投影及遮挡。本轮仅原文/已有实现审阅，无新注册、标签、训练或test。

## 2026-11-13 文献面：相机→声呐 3D 投影框，新增 11 篇，库到 102/96

[清单与判断](related_work/sonar-projection-3d-box.md)。结论：没有公开论文把「相机侧 3D 框/网格 → 前视声呐 2D 框标签」当方法贡献；现有三条相邻线各自缺一环——A 声呐投影/PnP·AnP 只处理点（2504.04445 对偶全局最优 PnP、2503.16066 90% 外点剔除、2411.17521 BESTAnP、2507.05410 唯一显式做声呐↔声呐特征投影，含 `Π_fl(r,θ,φ)=[r,θ]`、`Π_ss=r`），B 仿真只求像真（2001.03539 光栅+光追、2503.01074 OceanSim、2606.06130 体积模型），C 共配准只到像素级（2608.23479 用 SfM 网格投到侧扫、明写免除人工声呐标注；2610.23759 HaCKRS 105k 配对帧）。φ 缺失 ⇒ 3D 框投出的是区域而非轮廓，故「完整投影框」与「可见表面框」必须分列并报告差值。新增 11 篇全部带 LaTeX：2504.04445 2503.16066 2411.17521 2507.05410 2001.03539 2503.01074 2208.00233 2307.16160 2402.03309 2610.01644 2608.23479；索引已重建（selected=102 acquired=102 latex=96）。未改投影实现、未新增标签、未动原研究目录。

## 2026-11-13 当前交付更新：允许截断，3000选入＋398备用

用户明确允许可辨认的截断目标，纠正旧完整相机门槛。[新浏览页（本地产物说明）](ARTIFACTS.md#artifact-a14061aa6c51)、[结果](复现/camera-baseline/paired-bomb-truncated-results.md)。182317全146身份/13页本轮实际重看，新增115接受（110明确底部截断、5触底过渡），原31图/框/来源不变；该条146=100选入+46备用。累计3398=3000选入+398备用，30条各100、三类各1000；旧3283包保留，旧69缺额是旧准入历史，不再是当前数量。

新增camera_visibility与COCO attributes、YOLO关联sidecar；原相机JSON/框不动，旧样本缺新状态不表示全部未截断。全量3398原像素/字节/hash、6796框往返与去重通过；旧3283图/框/review/时间/来源全保留，仅182317旧10个选入标志转备用。4导出预览实际查看，HTML静态链接核验，未认证真实浏览器渲染。全部原标签只覆盖播放器0–9.94秒；14秒处无原camera框，本轮未新造框。精密同步疑点未解决（116窗口支持/3282未独立精密同步），非专家GT/CMHD标注方法复现/正式训练版本；无DS/test/训练/split/时间注册/原研究变更。

## 2026-11-13 连续标记/相机审计完成，三面刚体对照未给出可注册修正

[报告](复现/camera-baseline/sonar-tag-continuous-camera.md)、[浏览页（本地产物说明）](ARTIFACTS.md#artifact-4e1b596ee152)。仅123500允许录音，276帧（196有tag141、149三面共视），原0392/0788角点0px差，五种模型196帧图像最优分支均与连续分支相同。固定pinhole/发布四数鱼眼假设/历史Wide鱼眼与发布链角差21.60/15.23/13.91°。历史README已见于旧来源审计，本轮是对本录音的新控制。SD/FHD/UHD容器均只有视频/时间码，未认证真实镜头或防抖。

单面25fit/31check，原稀疏超预算；新稠密全量两模型收敛，角差19.82/29.05°，收敛Brown删块20.13–41.03°，pinhole另有未收敛52.49°不能等价比较。三面18fit/16check，三固定模型留出角点中位/p90分别6.97/14.97、3.66/7.03、6.04/12.63px，时段几何不稳。自由Brown 1.19/2.42px但cx触1440px上界，原单面角差仍19.03°、用两面估0788仍20.16°；不批准用作标定。原锚点只有4背景互匹配；232对背景的三成像控制无足够证据认证方块动/静。

发布角幅值77.819°来自ARIS pan，gantry XYZ不影响该读数；共同移动±12帧仅77.124–78.482°，固定安装旋转只改相对轴；均不足以单独解释三固定模型至少5.49°幅值差。余下可能为成像、标记运动、姿态/帧对应的组合。现有方块控制已达低边际收益，未改注册/新投影框/原GT/正式split/训练/test；不重复要求已确认没有的标定资料。后续只有独立运动或可信RGB–OBJ物理对应才值得继续，不能将条件角差写回外参。768留面点复算、290图解码、源hash及693背景估计复核通过；代表图目视，浏览器渲染未验。当前试验均结束。

## 2026-11-13 最新累计配对交付：2931选入＋352备用，用户接受69缺额

按research-workflow收口本次双端标注交付。[浏览页（本地产物说明）](ARTIFACTS.md#artifact-7842e0e73cac)、[使用说明（本地产物说明）](ARTIFACTS.md#artifact-b473334d4b1f)、[累计报告](复现/camera-baseline/paired-assistant-full-review-results.md)。累计6273唯一身份实际看过、3283接受（bomb994/mortar1204/grenade1085），每录音最多100选2931、备用352。29条各100；182317为31，缺69，用户明确选择“保留现有数量，明确报告缺额”。不再默认追3000；接受该缺额不等于逐框专家验收。

新2398接受，旧885图像/框/来源全保留；重新均匀选样令旧10个身份选入/备用标志变化，旧包未改。3283对全量像素/字节/hash、6566框往返、无完全重复像素与血缘核验通过；20新增录音实际导出预览全看。追加审计先遇旧spec缺label hash的KeyError，改读权威temporal hash后通过，失败保留。manifest hash与核验在新包，源决定已冻结。39审核根、8260候选决定；四条0接受mortar的允许池全看，未决不作负样本。

182317全部146原标注身份与官方归档catalog一致，完整相机宽松上界36、实际双端31；matches已有incorrect gopro offset疑点，未据配额改时间。116对沿用checked_window支持、3167未独立精密同步核对；全包非专家GT/正式训练版本。与旧825并集3774只3283双端已审，491待双端。没有DS/时间注册/原框/正式split/test/训练变更；实际浏览器渲染未验。三并行任务和本次导出审计均结束，无待跑批次。6.1-sol同12旧G提案12/12同判，非盲不能证明整体更优。下列其他注册/RGB任务历史继续保留，未被本次直接标注交付解决。

## 2026-11-13 RGB估姿路线已实试：六帧0通过，新增无尺度tag旋转疑点

用户授权“试试”，已完成[RGB试验报告](复现/camera-baseline/sonar-rgb-pose-pilot.md)、[浏览页（本地产物说明）](ARTIFACTS.md#artifact-7cb9f7b14c08)。两类各三开发帧，96纹理渲染，单视图及固定视图库合并控制均失败；合成两类通过。单视图5–7候选，合并35–61但RANSAC最多5内点，真实姿态0，未进入声呐投影。所有进程结束；原模型/标注/正式split/test/训练不变。不能称RGB路线已修好或原则上不可行。

用户明确答复：没有AprilTag边长/布局或额外相机标定资料，不要再次要求相同材料。3/6帧检测到tag，123500_0392/0788同tag141无量纲IPPE相对旋转与发布姿态差pinhole21.60°、fisheye假设15.23°；双解/噪声控制保留。方块静止未证、图有悬挂线索，实际镜头与四系数含义未知，不能直接判gantry/时间错或补偿该角差。此项是增量旋转检查，tag存在已有历史。下一步若继续，应先在新计划下检查同录音标记稳定性/相机模型，或建立可靠人工3D对应；不得用失败姿态生产GT。

独立验证：输入hash、96视图映射、合成重投影、fit/check隔离、tag边长倍增旋转不变/trace复算通过，137图解码，5脚本语法通过，网页静态链接核对；浏览器未验。主plan、合并plan、tag-rotation-plan均事前登记。两次代码错误（标签格式、numpy整数JSON）的失败脚本/产物保留于sonar_rgb_pose_pilot_preparation_failed和pooled_serialization_failed，无源数据修改。

## 2026-11-13 换角度诊断：下一步需RGB物理对应，不继续声呐追框

[本轮核对及解决顺序](复现/camera-baseline/sonar-registration-alternative-diagnosis.md)。确认模型仍是名义长度+PCA初始坐标、声呐框/曲线不足以独立认证姿态。提出先明确RGB—OBJ多物理特征对应及相机模型，再以RGB估姿绕过gantry作诊断，最后恢复固定几何链；已有两端点/内参敏感性实验失败不能忽略，配对精度仍未认证。这是待新观测支持的路线，不是PnP已运行或新修复结果。当前sonar静态链已含[-0.108725,0,0]m偏移，不能根据历史README再补2.5/5cm。此次只读源码/冻结资产，无图像实验/训练/test/标签或矩阵变更。

## 2026-11-12 新累计配对包：885对，继续目标未完成

用户要求继续后，助手直接新增查看624唯一身份、接受270；累计1388已看、885接受。新包[浏览页（本地产物说明）](ARTIFACTS.md#artifact-72ad1ea7bf7b)、[报告](复现/camera-baseline/paired-assistant-remaining-results.md)。累计bomb271/mortar265/grenade349；每录音最多100，选793/备用92，6条足100，距3000缺2207。新增174439=53、175000=95、175506=100、124915=22；121124/121327/125048的首24当前候选均未决。不要把重复B/F/E审核计为新身份，详见报告。

885对全量源/输出/审核图hash、原像素/相机JSON、1770框往返与重复检查通过，四新增录音导出预览已看，旧615身份/框/来源/选择成员不变。862未独立核对精密同步、23沿用checked_window，均非专家GT/训练准入。与旧825重叠178，并集1532=885双端已审+647待复核。无DS/时间注册/训练/split/test。浏览器渲染未验，无后台批次。

审核根新增paired_assistant_remaining_review（168/8）、remaining_broad（432/240）、remaining_strong（168/22），完整前缀均paired_assistant_。174439 B page12误批全接受已立即全部撤销，历史保留，误标期间无导出；另根4个F仍保留。121124/121327的E截断连续端部，B含下方条纹，不自动扩批。124915仅22个分离亮环接受，后期相机截断/回波混合未决。脚本tools/export_paired_assistant_remaining.py固定八根，--verify-only重验。下一批优先未审mortar及类内缺额；不凑100或重复已失败提案。其他任务的注册诊断与旧框语义疑点仍保留下方，本次未消除或改写它们。

## 2026-11-12 声呐投影原因核查：停止无依据调参，已交付505帧四方案对照

[报告](复现/camera-baseline/sonar-projection-root-cause.md)、[505帧浏览页（本地产物说明）](ARTIFACTS.md#artifact-8091d8907ac2)、[58帧边界复核页（本地产物说明）](ARTIFACTS.md#artifact-701d764e2653)。原模型保留，新增曲线约束/编码器替换/近表面框三组控制均无稳定改善，已达用户授权的低边际收益停止条件。mortar方向与形状问题仍未解决，不能以参考标注问题洗掉几何失败。

来源链已重放：近似发布位姿64对涉及58个高回波身份，全部A–F候选坐标58/58精确匹配保存审核表。123841_0329、124039_0233的C/B实际均为shuffle前E分支，只沿range裁能量，保留相连横向回波→框变宽→助手接受。两帧仅check未参与fit，不能声称已导致旧模型拟合偏差；回波物理来源仍未知。58队列中42宽比提示不是42已错，两例needs_boundary_review、未来几何约束建议不准入；未改原框，未生成接受修订。

用户新给D:/pby/data_processed，已核为现用processed源，五条gantry官方映射重放最大差4.44e−16m；不认证同步。指定模式检索无新bag/calib/OBJ，勿再次把此路径当未提供。仍待主体/全部回波语义问题答复，以及如存在processed以外原始bag/独立同步/实物尺寸资料。不能把无回复当同意。

新run两类24 fit、143同录音+338跨录音检查；全505身份与原框不变。1010图解码、5050 IoU比较、63密集投影重放和21近表面重放通过，最大边误差3.98e−13px。已看当前15检查帧四方案和两例分量；非505全人工验收，浏览器渲染未验。没有原test/训练/新split/正式GT；所有进程结束。后续先解决明确证据缺口，不继续增大时间/尺度/逐帧自由度。旧历史如下保留。

## 2026-11-12 已有助手框辅助固定3D注册：交付两轮结果，尚未完成几何GT

用户纠正：不是仅比较LLM框与投影框的来源，而是用已有好标注帮助3D注册并交付成果。已完成两类两轮固定6DOF求解（每类14初值），报告[sonar-box-guided-registration.md](复现/camera-baseline/sonar-box-guided-registration.md)。主入口[505帧全轨迹对照（本地产物说明）](ARTIFACTS.md#artifact-d762b4eec970)、[3D表面投影抽查（本地产物说明）](ARTIFACTS.md#artifact-04c45d03627b)，首轮413帧失败控制在DataSet/sonar_box_guided_registration。所有运行结束。

本轮冻结时paired_assistant_review已更新为320决策，254 accepted=mortar139+grenade115；早先244/191统计不再是本轮输入，逐字快照在首轮input-snapshots。bomb24 unresolved未用于拟合。首轮每类前60%取12 fit，后20%检查；mortar跨录音IoU中位0.476→0.636，但本录音后段0.602→0.271失败。第二轮唯一改变为全轨迹12 fit；grenade75未fit帧0.564→0.736，跨123841/124039中位0.555/0.547仅小改善且尾段偏移；mortar仍失败。各轮检查身份不同需看共同身份比较，不能取最好跨录音结果拼作一版。

每类仅一套姿态，尺度/时间/外参/gantry不改。主框完整模型投影，不裁elevation；±7°另列诊断，新旧对照同定义。高框IoU也存在模型轮廓方向不合，不认证物理注册/GT；全部原test关闭。两轮各21帧投影抽查、第二轮15检查帧详细对照已看；918运行内图像解码、2754项IoU与每轮21密集投影独立复算通过，边差≤3.98e-13px；网页链接通过、真实浏览器渲染未验。下一步应利用好标注补可辨端部/长轴/曲线约束并独立核对gantry，而非重复只用四边或逐帧追框。用户未接受正式GT，未训练/改split/原标注。

## 2026-11-12 最新配对进度：助手接手，615对双端审核导出

用户认为DS慢并授权助手直接做。本轮0次DS调用，实际新增查看356唯一身份、接受277；累积764已看、615接受。新包[浏览页（本地产物说明）](ARTIFACTS.md#artifact-5f72a4eb1558)，[报告](复现/camera-baseline/paired-assistant-expansion-results.md)。bomb171105为23；mortar102500/103728为126/139；grenade123500/123841/124039为115/106/106。五条各100加bomb23，共选523、备用92，距3000仍缺2477。旧338包保留。

615对两侧图像、原相机标签、COCO/YOLO与来源全量验证通过，1230框往返、615不同SD帧、两侧无完全重复像素；三个新增录音导出预览实际查看。592未独立核对精密同步、23沿用既有checked_window支持，全包未认证精密同步/专家GT/训练准入。与旧825重叠113，并集1327=615双端+712旧声呐待双端，不混计。无时间/注册/正式split/test/训练。

审核根：paired_assistant_review（320已看/254接受），paired_assistant_review_broad（bomb60/23），paired_assistant_review_arc（同首24替代A控制/0，重复身份不加分母）。bomb E截左端、A部分截右端，B24–59过宽含下方散射均未决；B60之后图已生成但未看。脚本tools/export_paired_assistant_expansion.py固定审核根，--verify-only重验。下一批继续剩余可辨录音，优先bomb与类内轨迹缺额；不等DS，不复用未审核框。论文与标定工具的其他工作记录保留在下方。

## 2026-11-12 文献面：91 篇入库，85 篇带作者 LaTeX

用户要求搜与本文相关的论文并尽量拿 LaTeX。结果落在 [related_work/lit-2026-11-12/](related_work/lit-2026-11-12/)：[README.md](related_work/lit-2026-11-12/README.md)（逐篇登记：标题/日期/章节/LaTeX 状态）、[index.md](related_work/lit-2026-11-12/index.md)（平表）、[SURVEY.md](related_work/lit-2026-11-12/SURVEY.md)（综述与定位判断）、[CODE.md](related_work/lit-2026-11-12/CODE.md)（代码可得性：**27 篇仓里真有代码 / 4 篇只放数据权重 / 3 篇宣称但空壳 / 57 篇未找到**）、`notes/`（两条轴的原始检索记录）、`queries/`（脚本与 `selected.json` 单一事实源）。91 篇 A23/B45/C23；每篇 `related_work/<slug>/{paper.pdf,source/,meta.json}`，SHA-256、arXiv 版本、来源 URL、抓取时间在 `meta.json`；`acquisition-log.jsonl` 记每次尝试，本轮 0 失败。

口径：arXiv HTML 18 组 abstract 字段查询 → 592 候选、339 过主题门槛 → 91 收录；每条经 `id_list` API 返回 200 且标题逐字比对；`search_query` 端点与 Semantic Scholar 均 429，已留档。**更正一条旧记录：JOE 2025 声呐综述是 2412.11840，不是 2411.05863。**

6 篇无 LaTeX 源：2304.11875、2404.18663、2405.13571、2607.23770、2609.01738（作者只投 PDF）、2108.03619；2303.12946 的 `.tex` 仅 6 KB，疑为骨架，未核。CMOLD 本轮复查仍无公开 LaTeX（IEEE 202/WAF + 无 arXiv 预印本）；CMHD 只有 Europe PMC JATS XML；AOPQ-Net（RS 18(16):2703，CC-BY，DFKI UXO 的近期引用者）未取全文，需浏览器过 MDPI。

判断（论证依据见 SURVEY.md，勿越级）：可写「推理期只留声呐」「object-level 蒸馏作用在光学→声呐这一步」「recording-level split 下 fusion 与 distillation 首次可比」；**不可**写「首个跨模态/首个声呐 UXO」（2603.21071 CTFS 已做 FLS 教师-学生、2403.09313/2410.10554 已做 SSS+KD）、不可写「文献用帧级随机划分」、不可写「KD 对弱模态普遍有效」。撞车排查：CrossFusionKD（TechRxiv 2025-11-17，`10.36227/techrxiv.176341538.86857924/v1`）为 RGB+IR 教师→RGB-only 学生，非声呐非 UXO，判定不撞车；其 `STUJ-SMOD` 数据集名未核（站点 Cloudflare 403），若实为声呐数据集需重估。反证四篇（2609.31785 只移动工作点、2409.05564 +3.9<+4.2、2609.03378 辅助模态有害、2405.03355 模态距离泛化界）要求把增益拆成 KD/初始化/伪标签三项分别报告。

代码面（2026-11-12 逐个查仓，见 [CODE.md](related_work/lit-2026-11-12/CODE.md)）：与本文直接相邻且能跑起来只有 3 个——`remaro-network/KD-YOLOX-ViT`（2403.09313，★98，声呐+YOLOX+KD）、`pingggg516/CTFS`（2603.21071，★15，FLS 教师-学生，2026-11-06 仍在推）、`wzyii/M2SDF`（2503.01655，光学去噪器迁声呐×4 检测器含 YOLOX）；fusion 对照用 `LiYunfengLYF/SCANet`+`RGBS50`。**`weirl-922/ACKD`、`Ruoyu-Xu/SCKD`、`thenukan/xModel-KD` 三个仓只有 README，不能把「论文宣称开源」写成「代码可用」**；RadarDistill 仓由作者自标 official，论文源包无此链接，按「仓库自述」标注。

本轮未做：未读 AOPQ-Net 正文；未训练、未改 split、未触 test、未改动原研究目录。

## 2026-11-12 相机—声呐标定工具：没有「读配对数据自动标定」的现成工具

查了 GitHub/GitLab 上所有能找到的相机-声呐标定代码，结论与清单落 [related_work/calibration-tools.md](related_work/calibration-tools.md)。要点：
原版是 APL-UW 的 [imaging_sonar_calibration](https://gitlab.com/apl-ocean-engineering/imaging_sonar_calibration)（BSD，ROS1+rosbag+PyQt，charuco 板+螺栓，Nelder-Mead 两段优化；论文 Lindzey & Marburg OCEANS 2021, DOI 10.23919/oceans44145.2021.9705956）；
更好读的独立复现是 `yeetina/camera_sonar_calibration`（★5，全部 Python+MATLAB，带 GUI 和重投影误差，`SonarInfo` 针对 Oculus M3000d）。
免靶标的只有 `bachzz/AutoCalib_Sonar_Camera`（互信息+声呐伪点云，实测脚本只对 x、yaw 做网格搜索）与 Pecheux 2023 Sensors 的运动自标定（**无代码**）。
`Steven-Yang-YDS/Camera-Sonar-calibration` 是空仓（只有 README+LICENSE），不能当实现引用。

**共同前提：场景里必须有第三样信息**（靶标 / 动捕 / 可比较运动），我们的 338 对静帧都不满足 → 直接跑任何一个都得不到唯一解。
可行路径按成本排：(1) 放 charuco 靶标走 APL/yeetina；(2) 拿已知几何的 UXO 目标当靶标，移植 `calibrate_sonar` 的误差函数，只解 3 平移+yaw/pitch（roll 与内参固定，否则欠定）；(3) 只有单帧时只能做声呐内参自检（range scale / 角度零点），无现成工具。

## 2026-11-12 最新：338 对双端逐帧复核导出，选入 300 对，整体未完成

[阶段报告](复现/camera-baseline/paired-visible-expansion-results.md)与[配对浏览页（本地产物说明）](ARTIFACTS.md#artifact-9eebbc22ffa1)。新包有两侧图像、原相机 JSON、两侧 COCO/YOLO、来源/审核记录和独立 verification。mortar 102500 接受 126、grenade 123841/124039 各 106，共 338；每条选 100，备用 38。实际查看 408 个唯一身份（grenade 224、mortar 184）；mortar 最初 36 的强阈值失败与低阈值复核分开留痕。338 对全量像素/字节/hash/身份/格式验证通过，无两侧完全重复像素；每录音一个导出预览另已查看，浏览器渲染未验。

与旧 825 待审身份重叠 42，唯一并集 1121=338 双端助手审核+783 仅旧声呐审核待双端复核，不能相加为1163或全部称GT。338 都保留 not_independently_checked；没有认证精密同步/gantry，未训练/正式split/test/注册/时间修改。按当前双端逐帧结果仅 3 条各100，距目标仍缺2700，含bomb10、mortar9、grenade8条。质量筛选后的均匀取样不是CMHD完整原轨迹均匀取样。

DS Flash v1 102/39 high、v2 102/45 high、v3控制12/6 high；v3全12叠图查看仍发现124039_0454 high含下方多径、175905_0509 medium选主体下方回波，不批准自动扩批。429窗口09:20:56 UTC恢复后用2 workers跑完12控制；所有进程结束，无运行批次/自动任务。`tools/expand_paired_visible.py`现在首个429触发共享停止并保存Retry-After；密钥只走stdin，不写项目。控制审核在`DataSet/paired_visible_expansion_zoom/control-qa/assistant-review.json`。

后续继续可辨录音的逐帧双端复核，优先补类别/轨迹缺额。7317扩展身份已备在`DataSet/paired_visible_expansion/candidates.json`（34条10/14/10），不是完成标签。`review_paired_local.py`支持`--proposal B/E --review-root 名称`，旧审核图不覆盖；选择proposal后必须实际看图再决定。`export_paired_reviewed.py`与`verify_paired_reviewed.py`可追溯本包，导出拒绝覆盖，新增应另命名版本。不能只因DS high就放行，不靠改时间/模型旋转凑数。

## 2026-11-12 最新纠正：目标为论文规模的声呐—相机配对，尚未完成

用户明确要求论文数量及双模态配对，不能以1120张声呐单边导出代替完成。CMHD为3000对（每类10轨迹×100、轨迹级1800/600/600）；CMOLD为约4700对train+validation，不能混用。[本轮报告](复现/camera-baseline/paired-paper-scale.md)。

已实际恢复1120对双模态图/标注/来源，入口`DataSet/paired_paper_scale/index.html`；其中134原相机框越界、161对既有配对检查不足，层级计数为1120关联→986框格式有效→825可继续审核（bomb620/mortar155/grenade50），均非正式训练GT。既有171105检查窗口支持100对；未检查录音不追认同步。COCO/YOLO为986格式有效候选，包含161配对不足项，使用时须看manifest状态；尚未冻结训练集。

全40允许录音26761身份已清点：26753有SD，1117相机框越界，排除已知问题/配对不足后的来源候选21867（7116/8275/6476），至少100来源候选的轨迹10/14/10；不是声呐质量合格数。另有4000唯一均匀待审身份（每录音100），sonar_bbox=null，不能计作标签。1120对全量hash/身份/格式往返通过，无重复相机帧；三类各1对并排预览实际查看。源清单及旧结果保留，无新DS调用/训练/test/时间调整/注册/split。

下一步优先补mortar/grenade双模态审阅与声呐框，再补bomb；用用户指定Flash，质量不足保留排除，不复制帧或改统计口径凑3000。需每类10条各100并通过质量核查才冻结正式数据版本。4000队列按已有允许标注身份均匀，不等于论文完整原轨迹覆盖。当前没有运行中的标注批次。脚本`tools/build_paired_paper_scale.py`拒绝覆盖本轮输出；验证`tools/verify_paired_paper_scale.py`。

## 最新：DS Flash声呐标注副本已完成（2026-11-12）

已收齐2000个deepseek-v4.1-flash有效判断，所有进程结束。导出16录音1120张（bomb822/mortar199/grenade99），其中706助手逐帧框、414 Flash high加录音抽查。其余880排除；全部40概览，20条未进入候选，4条QA不通过。每录音100目标未达，不凑数。入口`DataSet/sonar_visible_annotation/export/index.html`；COCO/YOLO/PNG/manifest/verification齐全，[报告](复现/camera-baseline/sonar-visible-annotation-results.md)。完整数值/来源验证通过，非专家GT，未训练/新split/test/时间注册。后续如冻结训练版本，应明确该可见回波框语义、选择偏向/类别失衡、历史使用与recording-level split；不能沿用下方“批次进行中”的旧状态。

# 最新：直接声呐标注改用DS Flash（2026-11-12）

用户授权助手自主整理声呐标注，并指定本机DS视觉接口，后明确改用Flash。实际模型ID为`deepseek-v4.1-flash`。Pro批处理已停止，旧响应保留。Flash批处理由`tools/select_sonar_ds.py --model deepseek-v4.1-flash --batch --batch-size 5 --workers 6`执行，进程状态需实时检查；日志`DataSet/sonar_visible_annotation/ds-flash-batch.stdout.log`与stderr，结果`ds_selection_batch_deepseek-v4.1-flash/`。API key不得写项目文件。

已完成40录音120概览筛选，20录音各100帧共2000候选；另20本版暂跳过并保存原因，不能说整条无可用帧。助手已实际目视录音索引0/1/2/3/4/5/7全100帧以及18/34各20帧，决策`review/decisions.json`及追加events与hash命名审阅图归档；约706接受，未正式导出。直接DS坐标试点失败（缩放/坐标错）；改成图上A-E候选选择、程序取坐标。Flash初次试点存在截断JSON/样本OCR错误，批次已增加token并正文传精确身份，必须严格检查响应完整性/身份，失败不能接受。下一步检查Flash结果、重试无效响应、对新增录音做代表帧/异常框叠图QA，再导出无损PNG+COCO+YOLO+来源记录及浏览页；不能把DS审核冒称助手全量目视或专家GT。计划见`experiment/archive/sonar-visible-annotation-plan.md`。不训练、不改split/原GT、不读test；不再靠时间或注册模型补框。

# Handoff

## 2026-11-12 补充：并排raw方向与相机不同

用户指出101131/frame501左右似乎反向。已核源码：raw波束右到左，工具未flip；官方viewer flip(-1)双向翻转。已生成同帧水平镜像对照并给两个浏览页加说明，原视频未变。幅值光流相关理论上不受水平反号影响，不能据此推翻或追认同步；未过门槛仅证据不足，不是证明错配。见[说明](复现/camera-baseline/sonar-display-direction-clarification.md)。

## 2026-11-12 当前：六条开发录音时间核对已结束

四条新增开发录音均未通过现有相机—ARIS连续配对检查，按预登记跳过独立 gantry 核对；没有冻结时间或启动注册。合计六条仅171105在已查范围有图像配对支持，无一条同时通过两项。 [四条报告](复现/camera-baseline/sonar-four-recording-timing.md)。100927 的 −4 s 与101131的约 −1.6 s仅保留为开发诊断，不写回 matches。

## 2026-11-12 当前：连续配对已核对，按用途舍弃未通过录音

171105 的 SD—ARIS 连续配对在所查 +6.20 至 +55.95 秒通过，保留图像配对证据；173329 未通过，按用户意见移出本轮可靠配对候选。两条 gantry 末段平移时刻都未获得独立验证，均不进入几何投影候选集。仅针对本轮两条开发录音，不删除原数据，不改变正式 split 或原 matches。 [报告](复现/camera-baseline/sonar-camera-continuous-timing.md)；后续以 [逐录音决定（本地产物说明）](ARTIFACTS.md#artifact-e63a76537bbf)为准，不再调这两条的偏移来挽救注册。

## 2026-11-12 当前：gantry空档已追到官方数据，采集原因未唯一确定

用户明确要求先查清空档、不靠模型旋转补偿。完成[来源审计](复现/camera-baseline/sonar-gantry-gap-origin.md)，预登记`experiment/archive/sonar-gantry-gap-origin-plan.md`，数值/验证/来源在`DataSet/sonar_gantry_gap_origin/`，脚本`tools/audit_gantry_gap_origin.py`拒绝覆盖。六开发CSV官方size/CRC全同，每条唯一>1s间隔都在首次位置变化前(2.093999–2.188s)，不是本地新增。官方extract逐/odom导出header时间，丢弃bag记录时间；合成未改写函数AST4消息保留静止与header空档、+2h不改间隔，但不是真实bag重放。当前main脚本gantry_output/config gantry_extract不一致且str time_adjust TypeError，历史CLI float；不把当前源码直接当发布执行日志。

关键历史：2023-10-19官方7e60aea因considerable delay将onset从前一行改首变化行，metadata与首变化同源，非独立物理验证。2023-12-18官方866ab60新增GoPro/gantry偏移联动；两bomb旧offset精确等于首变化时刻+GoPro帧偏移/fps（171105:10.390999−184/(30000/1001)=4.251532333；173329:6−105/(60000/1001)=4.24825），不能把6.139467/1.75175差值直接称同步错误，也不凭算式认证同步。用户第二段仍为播放器00:03/画面约+1秒，已确认无需再问。

在线Zenodo清单/当前GitHub main均核对；主processed和recordings目录无bag，D:/pby文件名搜索无bag/mcap/db3；sample包内部未查，不能断言全网无原bag。未取得原bag的header序号/接收时间或发布端控制状态，无法唯一分辨暂停、漏包、时钟跳变，禁止一律减2秒。当前时间不冻结、不重新注册。若继续在现有材料推进，应另预登记空档之后角度稳定的连续运动跨传感器核对，避免仅靠起步单锚点；不要让mesh吸收时间。六CSV Decimal时差、两联动Fraction、输入hash复核通过；本轮0新图像解码/训练/test/GT/split。报告更正旧强表述，失败保留。

## 2026-11-12 当前：用户时间口径已确认，发现gantry起点取样空档

用户确认第二段173329为“播放器进度约00:03”，即画面t约+1秒（最近源帧142/t=.984146）；不是画面+3秒。确认版`DataSet/sonar_translation_onset/human-review-confirmed.json`保留原话与旧歧义记录，不赋予人工精确帧精度。新[gantry取样审计](复现/camera-baseline/sonar-gantry-onset-sampling-audit.md)发现六开发录音首位置变化记录前均缺约2.09–2.19秒采样：第二段最后未变化3.812s/首变化6s，旧映射ARIS边界[−.43625,+1.75175]覆盖用户约+1秒。此前将“首变化样本”当物理首运动、据此认定第二段时间错1.75175秒的解释过强，明确更正；源onset控制改善不认证同步，另四条offset与样本相同也不证明同步。首段旧映射空档[4.04547,6.13947]、无用户判断，仍单独待核。下一步追查采集日志空档语义与ARIS标记/pan，结合连续场景多区域运动给出可信起点区间；不再询问已解决的第二段时间口径。时间不冻结、不注册。六源CSV hash一致，无新图像解码/训练/test/GT/split。下方均为历史。

## 2026-11-12 当前：ARIS平移起点人工反馈，时间对应仍未冻结

用户对第二段173329原话“在t=3s左右开始持续移动”。已保存[人工判断与复核](复现/camera-baseline/sonar-translation-onset-human-review.md)及`DataSet/sonar_translation_onset/human-review.json`。短片从画面t=−2秒开始，画面+3秒与播放器00:03分别对应源帧171/t=2.984354与142/t=.984146；已问一次时间口径，尚待用户确认，不自动选解释。第一段无用户判断。撤回此前将自动.666126秒触发当作已确认持续平移的强表述：它只是对固定参考图累计位移连续五帧过阈值，无相邻速度/多区域一致性验证。第二段0–4秒角度与绝对编码器稳定，不支持明显已记录pan，但不足以单独证明平移。旧数值/视频不变；不把用户约3秒直接当同步真值、不调门槛迎合、不重新注册。下一步确认时间口径后核对局部连续场景运动与独立gantry轨迹，冻结可信区间后才注册。本轮仅复读诊断结果/源码/第二段角度CSV/视频容器，无新图像解码/test/训练/GT/split。

## 2026-11-12 当前：找到bomb源运动起点与matches偏移差，部分解释注册失败

用户要求探究原因/对齐论文，完成[运动与论文对齐报告](复现/camera-baseline/sonar-motion-paper-alignment.md)。六既有开发录音独立源gantry首运动、官方dx+dy、metadata一致，ARIS marks/matches onset一致；但bomb171105 matches gantry_offset4.251532s vs首运动10.390999s（提前6.139467s），1733294.24825 vs6s（提前1.75175s），另四录音一致。新源onset对照只换gantry时间、不改mesh/角度/图像/观察；171105三帧平移改.294/.306/.253m，相位14.36/15.43/12.27°，可解释旧拟合约13°可能在补偿时间。旧PCA完整投影支持0/71/0%→50/100/82%；camera同录音未拟合中帧端点中位34.29→10.17px；尾颈B同区域两视角距离.473m→显式可行<1.3e−8m。圆头A仍.160m/截断，第二录音仍失败；camera跨录音最大误差反增，不能部署或认证全部同步。

CMHD原始JATS§3.1重新摘录与对照表已保存；明确几何自动框→人工异常整理，未知完整注册/裁剪/通过率，PCA/端部fit/13°均非论文实现。UXO最终PDF再取403/内容过大，未拿全文。18位姿独立插值≤1.11e−16、源hash/6图/四未改录音负对照通过。未读test/训练/GT/split/review，旧时间与生产页不改。下一项独立核实ARIS onset附近平移与手动pan，冻结通过的同步版本后再注册；不要重用旧时间下fit矩阵直接追认。此前“软件链复算一致”不认证物理同步，旧47cm端部不相容已有时间机制解释但未唯一归因。下方历史保留。

## 2026-11-12 当前：端部注册失败，固定pan不能跨录音推广

用户确认原点→端部固定注册→框边界三步，已实际执行[来源与注册试点](复现/camera-baseline/sonar-endpoint-registration.md)。官方object_notes明确bomb Object point(1.251079,1.418704,-1.151828)+安装offset精确等于发布target；README混用前方y不应当笔误减22.8cm。STL引用commit仅改notebook，本地全Git无mesh提交，原点到OBJ仍缺。三类形状头尾核对；新mesh拟合仅bomb。171105首末端部宽区间（助手假设，末帧A截断），0981同录音check，173329三帧跨录音check；12刚体候选0通过，最佳max残差16.28，完整凸包支持50/71/0%。不含mesh/target的两帧同名端部区域最近距离约A.147m/B.473m，DE两seed到代数上限但独立网格近同，不严格证明全局最小、更不能认证端部对应。

另预登记固定pan常量敏感性控制12候选，选δ+12.9319°但fit仍0通过（max5.524）；首录音完整凸包支持92/100/100%，第二录音两可辨帧仍明显错位/中帧uncertain。固定δ对旧17camera点跨模态控制不能推广：check中位数bomb143.7→113.7px仍大，grenade36→57.9、mortar21.1→84.7恶化；不部署δ，不当已恢复标定。两版12图/sourcehash/端点独立重放≤2.85e−13通过，原仓clean，test/GT/训练/split/review不动。第三步粗定位条件未过，未开始正式边界整理。下一项改查逐录音ARIS/gantry motion onset和时间对应的独立运动记录，并验证真实同一端部/背景静止性；禁止按目标回波逐录音调角/时偏。所有计划、失败和来源见报告。下方旧记录保留。

## 2026-11-12 当前：sonar_origin_envelope 定位粗几何矛盾

用户追问为何已知相对外参/内参仍错，要求探究解决。实际完成[原点诊断](复现/camera-baseline/sonar-origin-envelope.md)：120原点数值、原9fit帧82个既有助手观察反投影、全部9张诊断图复核，未新拟合mesh/部署。包括观察区间和任意elevation后，bomb8/37、grenade2/27、mortar0/18超出以官方target为中心的旧mesh保守包围球；bomb最大最短距离.55574m>半径.40001m，单转模型不能解决这一条件不相容。不能唯一归因官方标定：居中/尺度、回波归属和成像/位姿均有可能。共同最小球控制bomb可用移位.2261m、半径.399995m容纳，但不是实际注册，不应部署；mortar原本通过也会被优化移位，反证不可把优化位移当实测标定误差。区间网格82项、12球候选、24合成点检查通过；旧输入hash不变。优先恢复模型原点/端部实物对应，先粗range/beam轨迹后完整框，不继续盲扫mesh或转给用户重画。无test/训练/split/正式GT/review改动；下方旧状态保留。

> 最后更新：2026-11-12 · 三类新固定注册已实际拟合并检查40录音120帧；整体质量未改善，失败与新旧对照全部保留

## 当前结论

2026-11-12用户追问“做了吗，为什么不做”，已实际执行[新固定注册与40录音检查](复现/camera-baseline/sonar-fixed-registration-refinement.md)，[完整交互对照（本地产物说明）](ARTIFACTS.md#artifact-2d05d5aadf17)、[汇总（本地产物说明）](ARTIFACTS.md#artifact-f95805ac1c9c)。三类各11帧连续无框观察，9中心fit；新near_surface_range目标替代纯包含，固定尺度/beam/时间/外参，每类一套6DOF，3seed×DE120代+Powell，9候选53,340调用，全部冻结。fit cost bomb18.1425→10.5274、grenade6.4156→1.6696、mortar3.1836→.6434；不是GT精度。预先固定40录音×首中末120帧（9fit、111development_check），主QA旧13可审/76需修/22错位/9不确定，新12/71/28/9；整体未改善，不替换人工页默认。mortar错位8→4但可审11→9；bomb错位11→17；floor新3帧均错位。独立QA：bomb36、mortar前36；mortar剩余12由root在子agent运行中断后完成，grenade36由root，不能说全量互盲。全部逐帧理由和来源留存。

同轮追加固定规则诊断：新freeze/身份不变，仅去掉elevation裁剪，120帧空框10→0、74边界变/46不变，但仍有明显错位；不是无限声学FOV、不是已证实论文实现，完整投影仅6例目视抽查，不能混入主QA计数。原图/旧/新7deg/完整投影四列可在离线页筛选；240图解码与JS语法/链接通过。新本地预览服务启动遭自动审批blocked by policy，内置浏览器禁止file协议，未绕过，页面实际渲染未验。既有8765人工服务与用户导航未改，正式review仍0；test/训练/split/原GT不动。

独立数值已做：全部120身份/target链通过，21帧42框独立密集重放差≤2.84e−13px、338来源hash一致；完整投影另138hash通过。合成控制重现旧局部停滞，固定可见对应3/3恢复，完整边界2/3恢复；不能升级为真实注册成功。报告更正implementation-report“作者观察包”误写，实际grenade为助手观察。下一步不得再次把这版fit改善或候选框互相接近当成成功；现缺真实回波—表面对应与跨视角几何/框定义的可靠联系。全部40录音/每条100合格目标仍保留且尚未达到，用户人工接受权限不依赖唯一3D姿态，不恢复GoPro全标定/等待作者硬前置。

2026-11-12用户指出初始声呐框几乎不可用，完成[初始候选核查与纠正](复现/camera-baseline/sonar-initial-candidate-audit.md)。CMHD原始JATS§3.1明确以逐帧几何自动框为主、后做人工检查，未给通过率；用户期待大体可用的初始框合理。当前UI默认old_pca_fixed，是名义长度/PCA轴/极值中点的未通过假设，非官方注册；mortar start00仅可选且仍多解。之前扩到40录音只增加覆盖、没有提升框质量，不能把主体工作交给用户重画。确切新错误：floor录音160551误用悬置target/100lbs，已单独改官方target/100lbs_floor，新ID floor_target_pca_fixed，旧mesh注册不变；普通39条映射不变、8帧14候选精确回归、12测试通过、19输入hash未变。8765服务已加载修复，PID50492（以server-info.json为准）；[部署检查（本地产物说明）](ARTIFACTS.md#artifact-289c6ff74772)确认当前175000_0887完全不变、floor映射正确、正式已审/接受仍0。未刷新用户页面或写审阅。floor修复不能解释当前普通bomb错位、也不能认证新框。下一步重点回到自动候选质量：有依据固定注册+录音target核对，先在代表性跨帧证明检测框可保留/小幅修订，再全量；人工可继续验收确实好框，不要求唯一3D姿态，不重设GoPro完整标定/作者回复硬前置。全部40录音覆盖与每条100的用户目标保留；未训练/访问test/建split/改原GT。下方上一阶段“下一步直接读取人工结果”不再代表当前优先级，历史原文保留。

2026-11-12用户要求亲自筛选且明确选择“全部允许录音都筛选”。已创建并打开 [人工筛选入口](http://127.0.0.1:8765)，[说明与验证](复现/camera-baseline/sonar-manual-curation.md)。40录音26761native（bomb12/8997、grenade12/7932、mortar16/9832），SD26753/缺8；每条native扣缺SD仍≥100候选，但QA后数量未知。每条均匀100作为建议队列，共4000建议，全序列可补选；左侧按类/录音统计，不能把全部帧默认为接受。用户选择保留候选或手工重画/移动/缩放，核对相机后接受；人工修订保存前后坐标/原因/人/时间/hash/完整版本历史。声呐框raw原生xyxy，相机640×360 SD原坐标；polar只作参考。原PCA候选所有类、mortar frozen start00另可选，均不新拟合；旧助手未通过不自动阻止人工接受，旧失败不改写。CMHD原始JATS§3.1确认每类10轨迹×100、轨迹6:2:2、总3000；本页全部40覆盖属于我方版本，不称完全同采样，不自动split/test/训练。正式服务已启动PID48124（需以后以server-info.json当前值为准），`tools/start_sonar_manual_curation.ps1`可重启。10项后端测试、6帧候选重放、实际UI画框/保存/刷新/导出/改判统计均通过；测试4事件仅在隔离ui-test，正式交付0已审0接受，用户尚未筛选。下一步直接读取用户保存的reviews.jsonl/latest统计缺额并协助补选，不恢复唯一3D注册/GoPro全标定/作者回复的硬前置。

2026-11-11用户明确授权“做”后，已完成 [mortar_fixed_registration](复现/camera-baseline/mortar-fixed-registration.md)，[六帧对照（本地产物说明）](ARTIFACTS.md#artifact-6e4b4b92b25f)。首轨迹100927的0087/0451/0811先冻结19个assistant部分回波支持点，以0.580m固定尺度、固定声呐位姿/时间/beam约定，运行24个初值只拟合一套6参数T_world_from_model；15个通过fit候选规则。冻结start-00后检查101131的0103/0509/0909，独立无叠框观察为4/8/0点，两可辨帧容许带外p95均0（旧PCA为1.985/0），末帧无可靠目标、指标null，不能当负样本。全部6帧候选框不稳定：fit minIoU=.485/.621/.605，check=.504/.658/.541；仅两个粗密都严格零损失解的fit IoU也只有.680/.791/.877。因此低支持距离不足以认证完整框，不能继续挑最低cost宣称注册成功。原“4个零cost”计数实际是<1e-12，严格粗零2、密零7，纠正及旧记录均保留。合成近邻恢复2.067→1.214未归零，不能写成合成注册已通过；局部优化/硬门限限制与观测不足分别记录。独立fit/check数值重放及输入hash通过，主/独立assistant均5 unresolved+1 uncertain，非专家GT；正式GT0、训练0、test0、split不变。六身份均有既往开发观察，check不是盲验。下一版应新增有来源的可靠端部/头尾/本体范围信息，或明确人工框修订；先做优化恢复控制，不在本run重拟合check、反号或放开标定/尺度。无需等待作者或完整GoPro重标定。下方“真实echo拟合0”为前阶段状态，已由本条更新。

2026-11-11用户要求用research-workflow探究解决方法，已按[预登记](experiment/archive/sonar-registration-methods-plan.md)完成[方法诊断](复现/camera-baseline/sonar-registration-methods.md)，[统一浏览（本地产物说明）](ARTIFACTS.md#artifact-2add25c39be5)。官方polar2独立几何栅格器与AST原函数在12合成+18已有raw逐像素相同，raw往返≤2.28e−13px；保留h+1画布/非均匀beam/取整/覆盖/flip，18对应发布polar本地无文件，因此只认证源码兼容、不认证物理符号或GT。API不检查FOV且raw会外推，调用方必须检查真实range/beam/前向及elevation假设。公开模型顶点/面积PCA长轴差0.12–1.96°，100lbs横轴差70.69°；PCA不能定roll，模型语义锚点可定自身头尾但不直接给世界朝向。18旧位姿+6理想极值点的7参数敏感性显示多视角改善局部约束，解析差分通过；真实回波无已知对应，不能据此声称注册成功。6notes显示grenade/mortar第二轨迹repeat，bomb检查轨迹roll90°（已在SonarRoll里）且lost track；无目标重新摆放声明，也无同位保证。推荐定尺度/定标定后先mortar三帧拟合一套T_world_from_model、第二轨迹三帧开发检查，再换算我方mesh→target，避免同时自由优化两种分解。不要恢复等待作者/全GoPro标定硬前置，不逐帧追回波。框规则见[草案](experiment/archive/sonar-box-curation-protocol-draft.md)，不要求mask贴合亮像素，保留多解框稳定性/人工修订/unknown。实际echo拟合0、正式GT0、训练/test0；旧结果保留，坐标首轮数组连续性失败及可观测性文案更正留档。

2026-11-11用户质疑反号方向并追问UXO资料为何不能实现CMHD：[新增复核与更正](复现/camera-baseline/sonar-literature-recheck.md)。明确公开位姿/尺寸/模型可用，18帧失败只说明我方注册/投影尚未验证，不能推断数据不可用。CMHD原始JATS §3.1是直接sonar几何投影+人工QA/异常处理，承认残余误差；数据声明说新增声呐框需向作者申请，正文不提供完整mesh注册/beam公式/异常清单。官方历史README d713bed7第125–129行明确acoustic x右/y下/z前，结合raw beam编号支持所用表角=-atan2(x,z)，比此前“若同相机轴”证据更直接，但同README第138行right ear=-x有字面冲突，推导仍以采用该轴约定为条件，不能认证物理符号或完整对齐；viewer实际flip(-1)同时水平垂直翻转，纠正简称。当前PCA长轴/roll/头尾/极值中点仍我方假设；官方例用s=1的STL而所下载包为OBJ，衔接未核验。不能将固定假设、数值重放、13 partial当物理正确或论文路线失败。UXO正式全文本次仍403未取得，不声称读过或无更多说明；七项从官方README核实。下一步应围绕官方target定义建立可解释注册、统一raw/polar像素和框QA规则，不围绕反号继续试错，也不恢复GoPro完整标定/等待作者硬前置。本轮仅文献/源码与已有图浏览，无新投影/标签/训练/test，旧产物保留。

2026-11-11用户授权的固定mesh试点已完成：[报告](复现/camera-baseline/sonar-fixed-mesh.md)、[18帧两版对照（本地产物说明）](ARTIFACTS.md#artifact-8f0a04b6ace9)、[s/R/t与来源（本地产物说明）](ARTIFACTS.md#artifact-fbc529ae2c21)。每类唯一PCA/名义长度/极值中点假设，3类×2录音×首中末，直接gantry/ARIS/sonar投影；两版同18身份和同冻结mesh，未逐帧移动。初版多帧beam走向相反；官方raw beam从右向左、sonar/camera同旋转支持另登记beam=-atan2候选，但无实测三维控制，未宣称物理轴已认证。独立逐帧AST仅一个负号差异；两版位姿/range/el和原图不变，数值重放差≤6.25e-13/2.27e-13。初版独立目视0 aligned/6 partial/10 misaligned/2 uncertain，反号候选0/13/3/2；主复核分别0/5/11/2、0/14/2/2，分歧完整保留。反号改善走向，bomb171105首末仍明显方位偏移，其他框仍边界不明，三类均未准入。0456 bomb和0909 mortar原图无可靠目标，显式撤回初看弱弧归属，保留uncertain而非判错框/负样本。助手目视不冒充人工专家GT；fan自有像素坐标不能套到官方polar2。源hash/冻结hash与原仓clean通过，无test/训练/正式GT/split。下一步区分target原点/头尾/roll、各录音target同位假设、物理beam符号及姿态/同步，不能逐帧追回波；本轮不再扫参。旧results生成态保留，最终状态看run-summary.json。

2026-11-11关键路线更正：[CMHD声呐路线更正](复现/camera-baseline/cmhd-sonar-route-correction.md)。用户指出作者不回并引用§3.1；已重读原始JATS段落一致。此前把GoPro完整标定/AprilTag记录作为声呐推进硬前置过严，撤销该依赖：它只约束camera辅助mesh注册，不是sonar直接链必要输入。camera注册失败不能证明ARIS–gantry–target链失败。CMHD是几何投影+人工QA/异常处理，承认残余误差；未知其完整注册/可见性/异常细节，不能替作者臆造逐帧调模型等。可沿公开sonar链、显式固定mesh注册假设开展候选投影/人工QA试点，无需等作者；原GT正式准入仍HOLD，不把候选当认证真值。实际阻碍为mesh→target及其稳健性、sonar成像/FOV/坐标、逐轨迹QA；新生成前另预登记，旧test关闭/不训练/不逐帧移动模型。作者草稿可选保留未发送，不再作为唯一依赖。本轮只文献/路线澄清，无新实验。

2026-11-11原始记录追查：[报告](复现/camera-baseline/gopro-control-records.md)、[最小清单](related_work/gopro-control-records/required-records.md)、[作者询问英文草稿，未发送](related_work/gopro-control-records/author-request-draft.md)。仅7z成员目录读取198915项，210YAML全部ARIS路径，未发现专门标定/marker/layout/bag/GPMF命名记录；未提取内容、不读取其他录音/test。官方calibration/model包目录无cube/CAD；Git camera_tilt仅加入/移动、初始0.30与0.247已存在，无独立修订说明。DFKI公开仓库目录68条/ndahn24条未见明确关联的新入口；猜测mbandefirvida账户404不证明身份；UXO calibration与组织OCEANS仓库搜索0，contributors/proneetsharma/jmohrmann请求遇403速率限制，不能声称已查完或全网无资料。尚未取得原始设置/水下标定/marker有效边长及布局。已整理6录音clip精确表、区分黑边/白边/cube边长和录音间移动的询问草稿；用户尚未授权发送，未创建issue/邮件。0.30代0.247会使PnP平移尺度增加约21.46%，同点低重投影误差不能自证尺度；不跑无独立依据的同步/姿态拟合。下一步依赖取得资料；新补拍不能自动追认旧录音真值。旧31图控制hash/18视频stat、源目录/报告链接与原仓clean复核通过；本轮新图像访问0，0训练/新GT/split，继续HOLD。

2026-11-11 GoPro成像模型调查：[报告](复现/camera-baseline/gopro-imaging-model.md)、[控制浏览（本地产物说明）](ARTIFACTS.md#artifact-29aba4b05c63)。固定6开发录音18份SD/FHD/UHD元数据+moov探测，UHD均5312×2988/30000:1001、无gpmd遥测/模式字段；不据分辨率推翻作者Hero8记述。官方历史a52d22a为Hero8/wide fisheye，2d5f8de只加四模式数值，无调用/系数定义/水下标定证据；issue5本轮复查仍无回复。GEOMAR论文摘要也Hero8，全文restricted未取；Git恢复的oceans_abstract是早期动机草稿，不是最终论文LaTeX。官方camera_tilt示例有主点取K[2,0]/[2,1]=0和齐次最后行取平移问题，tag_size先0.30后0.247，不可把示例当实测真值，也不能直接归因旧投影（未证实旧注册调用它）。在17SD+14既有FHD上固定tag36h11检测，31张中12阳性=6身份各SD/FHD，tag20/21/141；3张FHD目视确认池内立方体，四角缩放差1–5FHD px。所有四角/阴性已存，但每图仅单面，无实测边长/三维布局、无同录音同tag多时刻控制，未估PnP/同步/姿态修正。当前mode/畸变/介质仍未认证；先补原始设置/标定实现或独立水下标定，再核实tag边长/布局，固定模型后用持续同tag多运动段常量偏移+独立后段检查。新访问为18容器及31既有开发图副本；源hash/视频stat和原仓clean通过，无test/训练/新GT/split。原注册保留。

2026-11-11继续换视角排查：[图像运动核查报告](复现/camera-baseline/sonar-view-consistency.md)、[全部34对浏览（本地产物说明）](ARTIFACTS.md#artifact-a78fd6f9c5d4)。既有source-check的18身份SD索引/ARIS时间/姿态复算通过，gantry最大差1.1991e-8m；17有SD。宽基线只有2对足够F内点。预登记追加同6开发录音局部±15SD帧，43次源图解码、34计划对=26可用+8越界，属于新增开发访问。继续复核已保存点对，轮廓外扩10px排目标后17对仍≥24点；173329/1265→1280检查点F中位0.142px、固定位姿8.994px，但22/26对homography支持≥90%，不满足3录音非退化证据门槛，不能唯一归因时间/内参/外参/姿态。±1SD帧不能消除部分差异，但更大同步误差未排除；单焦距扫描不能通过端点检查。当前linear K/3零畸变仍是假设，历史wide fisheye与当前四维distortion不能混套。合成F控制6.24e-14px、反向负控制6.00px；26对预测复算一致。新JSON核验旧源hash/视频stat不变，唯一历史hash差异是本轮追加预登记；首次因此停止后明确登记重跑。旧注册保留，原仓HEAD/status clean，无test/训练/推理/正式GT/split。下步先核实实际GoPro模式/畸变模型/水下标定，取非共面独立控制或持续背景轨迹核实同步/姿态，再验收固定mesh→target与sonar链；不能逐帧调模型补偿。

2026-11-11用户继续授权取原始注册/失败则我方独立注册，已实际执行[sonar_independent_registration](复现/camera-baseline/sonar-independent-registration.md)。补查Zenodo9资产、官方releases为空及5个fork默认分支，未获metric注册/STL；检索边界与网络hash见related_work/model-registration-retrieval。按事前规则每类前2录音首中末共18身份（17SD，1缺SD保留），assistant独立目视轮廓不使用旧框/blob/cache，6图fit/11图holdout；当前linear K/3+零畸变是未认证假设，当前camera外参主版本/历史−4°敏感性。3类×2版×8初值48次相似变换实际求解，全部未准入：主fit RMS bomb20.88/30.02、grenade3.69/3.58、mortar2.90/2.48px；holdout分别86–223、8.57–36.22、6.62–45.05px，三类均旋转多解。各模型JSON保存sR/t、所有初值/收敛/Jacobian与approved_for_sonar_gt=false，不能把优化器返回值称注册成功。追加近似端部射线诊断：bomb两fit图射线错开0.121/0.161m，mortar两fit可对齐而末帧仍大误差；不能单归因给mesh。独立全原顶点/齐次矩阵重放34控制误差<2.6e-13px、pytransform3d<7.3e-16，合成控制通过，但不验实测相机。`DataSet/sonar_independent_registration/index.html`有18投影对照；sonar显示前360行、beam/elevation仅假设，没反拟合echo。原仓/源数据不变，无test/训练/正式GT/split。下步应先确认camera成像/位姿/时间实测一致或取得独立sonar/target 3D测点；本轮未得到合格已注册模型。不要继续用同2图加参数强拟合，不能把holdout重拟合后仍称独立验证。

2026-11-11新增[3D注册/标定一致性核查](复现/camera-baseline/sonar-model-registration-consistency.md)：官方2024-07-26提交3aa12ec把camera mounting pitch约−4°改为0°，而notebook保存于7月23日；历史标定复算171105/frame1211的最大矩阵误差6.24e-7，独立库通过，已解释此前4°/0.07283m差异。只改camera安装链，sonar链与target姿态不变；不能因此回滚声呐。当前发布标定仍为诊断基线，未认证逐录音精度；作者公开回复明确camera–sonar外部测量外参精度有限。官方历史README恢复名义尺寸737/442/580mm；三个OBJ的PCA尺度候选已保存，但朝向/原点/完整mesh→target仍缺。所查公开git历史无模型文件，Zenodo v1模型/标定包MD5与当前相同；未合并第三方PR6也只单独显示未注册模型。新产物`DataSet/sonar_model_registration_consistency/`含双版本矩阵/模型登记/几何图/verification；160个metadata hash与前轮及前后相同，原仓HEAD/status clean，未读test、改GT/split或训练。正式sonar GT继续HOLD；下步取得官方注册/已注册STL，或用独立几何对应开展明确标记的我方重新注册，不能只按名义长度+PCA当作通过。下方“4°原因未知”为历史状态，本条更正。

2026-11-11用户授权后已执行[sonar投影链审计](复现/camera-baseline/sonar-projection-chain-audit.md)，[固定9帧浏览（本地产物说明）](ARTIFACTS.md#artifact-3db267dd4f52)。现有projected是camera框中心+blob拟合目标点后限40×60框，非CMHD的3D网格投影；3类首条允许录音首中尾9帧复算3 blob/6 projected，9/9源sonar与paired hash、FrameTime一致，公式独立通过，但未重拟合cache或认证GT。1帧120653_0933缺SD保持deferred。40条原始数据都有Pan/Tilt/Roll，旧转换未携带；形状28×441行、11×780、1×603，旧框硬编码441在本9帧未改变纯projected结果。官方calibration/3dmodels包已下载MD5通过至related_work/sonar-projection-audit-assets。缺OBJ到target的metric注册（demo用未公开在此包的STL）；官方AR3位姿1211控制重现，但当前标定与notebook保存camera变换差4°/0.07283m，独立库复核一致、原因未知。已达到预登记HOLD：不猜模型缩放、不批量生成训练GT。52个pilot输入+160个metadata hash未变，原仓HEAD/status clean；未读test、未改split、未训练。后续先追mesh注册/标定版本，再做物理框试点。

2026-11-11用户选择“按CMHD”，强调先做sonar标注。已核对§3.1：几何投影sonar框+人工QA，随后描述每类10完整轨迹/每轨迹100帧/轨迹6:2:2。应先核查投影链和足以确定共同样本成员资格的sonar/camera QA，再冻结配对清单、训练教师。无需先处理全部95轨迹。此前40条30/10只是我方建议，不能当成用户已采用或CMHD原方案；旧test访问限制未变。见[CMHD准备顺序澄清](复现/camera-baseline/cmhd-dataset-preparation-order.md)。本轮未生成框、改split或训练。

2026-11-11用户要求先调查同数据/同结构数据split再答复，未授权本轮直接生成正式归属。已完成[划分调查](related_work/recording-split-review-20261111/README.md)：CMHD §3.1明确每类10条完整轨迹、每条100帧、轨迹级6:2:2；CMOLD仍未知；UXO所查官方README/config/export脚本未定义标准split，UXO原论文下载403未读；UATD只明确7600/800/800，不支持宣称录音隔离。重新取CMHD JATS与旧XML hash一致。只读本地允许manifest复算40条类别数12/12/16、历史val为3/3/4条。建议本地开发train/val约3:1（若全合格为9/3、9/3、12/4，总30/10），优先审查保留现有10条val，新增3条需配对/标签/历史准入，不强凑数量；这是我方选择，不是CMOLD协议。要先排查同真实轨迹拆多个recording。尚未冻结split、未读test、未训练。

2026-11-11进一步澄清用户目标为论文教师数据条件对齐：上一轮“camera训练不依赖sonar伪标签”只说明技术依赖。若sonar QA影响共同样本准入，应先确定共同配对train/val清单，再训对应camera教师。论文§III-A(5)/§IV-A支持共同配对数据描述，但未披露教师各阶段精确样本清单，不能断言Table3教师只用该池或无额外camera。补充已追加至[配对准备说明](复现/camera-baseline/sd-pairing-and-sonar-preparation.md)，尚未筛选数据或训练。

2026-11-11补充核对：CMOLD本地PDF第11页明确约4700 **image pairs用于train+validation**，不能与26761个camera候选作同口径训练帧数比较。camera-only teacher无需等待sonar伪标签，但应先共用recording-level split并保留时间配对身份；以复现/受控KD为主的首条基线建议用共同配对池camera一侧，额外camera帧扩大数据另列实验。截图为sonar人工核心集→初始sonar检测器→伪标签/QA流程，不是camera教师训练前置。见[SD规模与配对准备](复现/camera-baseline/sd-pairing-and-sonar-preparation.md)。以上为建议，未冻结或开训。

2026-11-11直接复读CMOLD本地PDF确认：用户引用的YOLOX-M→YOLOX-S明确为sonar-only Conventional KD对照；相机教师型号仍未明确披露。camera基线参考Table3（AP0.958/AP50 0.997），不能混用Table5的0.661→0.671。见[型号与下一步澄清](复现/camera-baseline/cmold-camera-teacher-clarification.md)。SD训练清单/框QA/录音级划分尚未冻结，未启动训练。

**用户最新选择（2026-11-11）：训练优先使用SD。** 后续camera-only teacher数据优先640×360 SD、原始SD坐标框（不乘3），按已核验时间关系取帧并独立核验覆盖/身份/标注QA。FHD成果保留对照；FHD未恢复名单不能直接当SD排除名单。这是我方选择，未证明性能更好，尚未生成冻结SD训练集或训练。原框范围问题不会因使用SD自动消失。

t_camera_s 是值得保留的 camera-only teacher 候选，在同录音 830-val 上 mAP@[.5:.95]=0.902487、AP50=0.989715；train/val 共享全部37条recording。尚未建立当前权重/数据版本的有效未见录音基线，不能称 CMOLD 数字复现。论文未披露评测集，绝对AP无法作同协议归因。

本轮使用 research-workflow 幂等初始化；已有骨架全部保留。项目目标与术语已明确，会议/期刊/deadline未指定，保持未知。原研究只读、不训练、不推理、不读取test样本/逐帧标注/预测，不根据test分数选方案。

## 已完成

- 先阅读其他agent成果，再并行进行文献、实现、数据三路增量复核；根汇总与协议修订。
- 文献：YOLOX v2真正LaTeX源包已复取并hash一致；CMOLD/CMHD/UXO论文未找到公开LaTeX，检索范围与失败记录已保存。CMOLD用明确标记的既有PDF衍生正文/表图，CMHD读JATS XML，未把它们冒充tex。
- 实现：核对落盘配置、日志、checkpoint静态结构、实际MMEngine库与官方版本、非test指标内部闭合；没有重新运行COCOeval。
- 数据：只解析train/val split artifact及确认无test行的partial recording manifest；没有重新全量解析混合test metadata/annotations。旧审计的帧距统计按历史复算引用。
- 数据集：UXO `data_processed.7z`（61,513,277,947 B）已获取并通过官方 MD5 校验，归档未解压；来源为 Zenodo 记录 13778485（v1.1）。
- 建立总入口、总报告、证据hash快照、实际结果登记和分阶段实验预登记草案。v1协议及旧结果占位模板保留副本，旧审计不覆盖。
- 独立红队复核了新总报告与协议，修正实际尾LR、AR导出缺口和gate措辞。最终工作流检查通过：12份当前文档、57个本地链接，无未填占位符/断链/工具语法错误；明确白名单17个输入身份未变，原仓HEAD/status前后相同。检查不等于重跑模型或对整个研究目录逐文件取hash。

## 必须带走的更正

1. 现有权重见过全部37条recording，事后重划录音再评旧权重、且不重训，不能产生未见录音结果。下一run从固定COCO起点重训，不能warm-start已见留出录音的UXO权重。
2. 正确规模比较是我方4152 train+val vs论文约4700 train+validation；论文train数未知。
3. CMOLD Table2已披露200epoch、batch8、SGD和学习率等；不能整体标未知。各阶段完整配方仍未知。
4. YOLOX-S原始tex明确去MixUp；不盲目把它加回当论文标准。增强正文是§2.1/2.2。
5. MMEngine0.10.7保存链把EMA放进state_dict，现有eval链有证据支持使用EMA；不因脚本没swap就修错地方。
6. 原研究当前HEAD=4fadd06829c6c738977639a55b6e44ad0e35ac44，branch=exp/cmold-paper-repro，审计前后status clean。旧dirty/b005f41属于历史快照；最新三seed新增是声呐，不是相机跨录音证据。
7. 原test有开发性比较记录，不追认成untouched test；仅转换本身不必然污染，但excluded也不能证明历史未用。
8. 红队复核发现当前配置eta_min=6.25e-5但日志尾LR=6.4641e-5（cosine区间与T_max不一致），不能称精确匹配论文final LR。性能影响未知，不在split对照中静默修正。现有评测器只导出AR@100，AR@1/10是未来工具准入项，不能从旧summary补造。

## 继承的未完成数据准备

DataSet/camera_recording_disjoint_v1/progress.json 仍为 incomplete，3446帧，完成到首条val recording 2023-09-20_173329。partial manifest为22train/3296帧、1val/150帧。experiment/tools/prepare_camera_dataset.py 是先前agent已有代码，本轮未执行、未修改、未续跑。

维持 **HOLD**：拟定4条test全bomb，不能验收三类；excluded→never used推断不充分；另有clipping变更、同size跳过复用、moving_target=false等需核对。不要删、不当新冻结数据根、不读取拟定test内容来挑选方案。

## 下一步，按依赖顺序

### 最新：用户授权全量完成，40条重建及核验全部结束

入口为[全量对照页（本地产物说明）](ARTIFACTS.md#artifact-509c66e4b095)和[结果报告](复现/camera-baseline/annotation-issues/camera-temporal-all-results.md)。权威清单`DataSet/camera_temporal_all/manifest-resolved.json`：26761=26139candidate+609缺FHD覆盖+5时间待核+8缺SD；4746个paired身份中4566candidate、180未恢复。初始base为26132候选，7个EOF越界发布JPG与前native字节相同、血缘/真实PTS/内容过原门槛后补充，保留base及initial_status，未覆盖原记录。

全量独立核验包括每个样本集合/PTS/status/hash、实际26139张JPEG灰度内容、130张独立全分辨率单帧解码；40条录音120个首中尾三联目视未见新FHD–SD明显错配，另目视7个补充样例。26761份标签副本逐字节一致、FHD框与原gallery全等，原图/标签/视频不变。121个processed源文件及53522个native原JPG/标签size/CRC全部与官方归档匹配。无test、无模型推理/训练、新split。

**原框质量新待办**：173615三个概览例明显含大量支架背景；该录音797个框和175000的320个框延伸到图像外，总1117个几何提示（1062有候选图），不是已判坏标签数。浏览页“仅框范围需核对”和annotation-geometry-flags.csv可定位。原标注匹配官方版本，不能通过时间修复认证其边界；未自动clip/重标或删除难样本。部分出FOV目标的截断规则也待明确。

下步先做原框定义/截断QA，确定622个未恢复样本的版本规则，再冻结recording-level split和教师训练输入。26761是native完整序列，不能直接全部并入旧3322/830划分。原两录音试点继续保留；下方进度为历史。本轮viewer初次CSV换行转义静态语法错误已修，provenance保留脚本与诊断，data manifest不受影响。

### 最新：用户授权试做与核验，两录音副本已完成

`DataSet/camera_temporal_pilot_rebuilt/`：101622为768=735candidate+33缺FHD覆盖，103140为714全candidate，合计1482；paired身份268中261候选、7缺覆盖。1482标签副本逐字节一致、FHD框与gallery相同、原图/标签/固定源视频及元数据hash前后一致。使用完整ARIS精确onset和实际解码PTS；缺覆盖33条均在101622开头，不外推。独立状态复算全部通过；9张导出JPEG经独立单帧解码抽查并目视核对首中尾与三个问题帧。

查看[全部对照页（本地产物说明）](ARTIFACTS.md#artifact-0de86458421b)、[结果报告](复现/camera-baseline/annotation-issues/camera-temporal-pilot-results.md)、[核验JSON](DataSet/camera_temporal_pilot_rebuilt/verification.json)。候选不是全部GT验收通过；没有重划split、训练或test访问。`labels_sd_original`仍为SD原坐标，FHD框在manifest，不能误配。首次长select解析失败留在`DataSet/camera_temporal_pilot`，已标failed，成功副本另目录；工具使用平衡表达式，不覆盖失败产物。

后续先完成两录音框QA，再按相同规则扩展允许录音；明确缺覆盖规则与数据版本后冻结recording-level split。下方“尚未执行”是前一阶段状态，由本条覆盖。

### 最新：camera时间对应重建方案已登记，尚未批量执行

用户询问解决方法。推荐以经验证的SD时刻为参考，在FHD中找同一时刻，保持原GT、重新导出独立图像副本；先做101622/103140试点与并排验收，再扩展允许开发录音。原生坐标只缩放一次，已是FHD坐标不重复乘3。逐帧记录PTS/索引/hash及状态；时间覆盖缺失不外推，其他原框错误另行标注QA。见[重建方案](复现/camera-baseline/annotation-issues/camera-temporal-rebuild-plan.md)。本轮仅登记方案，未批量导出、改GT、重划split或训练；三个既有诊断例子为可行性证据，不能称全量修复完成。

### 最新：完整源时间错位原因审计已完成

已用本地完整源检查40条允许开发录音的120段SD/FHD/UHD元数据，并解码80段SD/FHD做固定内容抽样。38条有非零偏移，2,992对抽样中每条非零偏移录音的时间对应MSE中位数均优于同序号；40/40解码计数通过。全部SD/FHD fps相同，起点差换算帧数均等于帧数差、结束时间近同。因此问题并非只限两条mortar，也不只是元数据异常；38条不代表坏标签比例。

直接传播机制仍是公开导出链切换SD→FHD后复用帧号，没有补偿起点差。同源独立缩放8秒控制在两段均无分辨率间起点/帧数差；分别stream-copy裁剪可重现不同起点。支持“编码后独立裁剪/混用裁剪版本”这一候选机制，但没有历史日志证明具体命令。公开缩放脚本还存在引号拆词与循环闭合问题，不能视作历史可重放流水线。详见[完整源原因审计](复现/camera-baseline/annotation-issues/full-source-timing-cause-audit.md)。

本轮只读源、未读test视频/样本/标注、未修改GT或训练。下一步是先决定并验证统一时间基准的camera数据版本；不能平移整批框、只改offset后未经QA即当干净数据。原始LabelMe工程仍缺失；下方“两条已实测/其余未知”属于前一阶段，最新范围由本条覆盖。

### 最新：用户已完成解压，采用本地完整源目录

已确认`D:/pby/data_processed/`是解压目录，包含aris、gantry、gopro及matches.csv；gopro的clips_sd/clips_fhd/clips_uhd各76段。本轮仅核对结构、此前允许的两录音四段SD/FHD视频及matches.csv：四视频全部与官方归档size/CRC匹配，matches.csv与前轮官方副本逐字节一致；未解码test视频或改标签。后续源追查优先用此目录，不再远程分段下载或走移动硬盘复制。

原包`D:/pby/data_processed.7z`仍在，大小61,513,277,947；已有`D:/pby/.uxo-transfer/certutil_md5.txt`记录MD5为2b9ef16c763a6964c608ed99a9cd1edb，本轮未重复对61.5GB全包计算MD5。旧transfer/status.json是已弃用路线的过期状态，不得拿其50%进度推断当前下载未完成。核对结果见`related_work/uxo/sd-fhd-trace/local-extracted-source-check.json`。下方“未解压”的段落保留为前一阶段记录，已由本条更新。

### 最新：数据包已就绪（2026-11-10 21:30）

`D:/pby/data_processed.7z` 已下载并通过 MD5 `2b9ef16c763a6964c608ed99a9cd1edb`（61,513,277,947 B，与 Zenodo 元数据一致），尚未解压。下一步是解压到 `D:/pby/` 下的独立目录并核对成员结构；训练/评估前仍须冻结协议，且不读取 `test` 样本。

### 最新：camera GT 浏览材料已生成

**SD/FHD追查已找到直接机制，覆盖下方旧未知状态：**已取得官方matches.csv及两录音各SD/FHD源视频，全部按归档size/CRC核验。101622 SD起点3.551秒/1620帧，FHD5.687秒/1556帧（晚64帧）；103140 SD6.714秒/1450帧，FHD0.241秒/1644帧（早194帧），fps均30000/1001。公开链优先SD匹配，导出只替换FHD路径、继续同帧offset，未补偿起点差。27个固定JPG查询及视频重叠区间像素核查支持该机制；三个问题框在时间对应SD/FHD上可包住目标。已从“人工错框或帧错配皆未知”推进为“这两段已实测SD/FHD时间对应不一致”。**不是像素平移；未修标签/换图/改split或训练。** 原始LabelMe工程在当前公开树和两份归档目录未找到；最初哪次裁剪/转码造成起点差仍未知。详见[本轮结论与诊断图](复现/camera-baseline/annotation-issues/sd-fhd-temporal-mismatch-findings.md)。

本轮验证已通过：[trace-verification.json](related_work/uxo/sd-fhd-trace/trace-verification.json)记录4段视频CRC/size、时间差与帧数差相符、时间对应的像素检查、6个工具语法和报告链接；原仓HEAD/status仍为4fadd06/clean。解码使用fps_mode=passthrough并检查与nb_frames一致；初次默认vsync与解压尝试失败均留痕。只产生副本与诊断材料，原gallery和训练数据仍保留原状。

**原因追溯新增：**三个错位例子的JPG/JSON共6个文件，与Zenodo官方7z目录的size/CRC32全部匹配（只读933,860 bytes归档头，无成员提取）。结合268张paired/native核对，有力支持camera图—标签问题已存在于官方发布组合，不是本地转换/浏览页引入。官方x3已执行；最初画框错误还是标注帧对应错误仍未知，不能指定时间偏移或归咎sonar外参。证据与边界见[原因追溯](复现/camera-baseline/annotation-issues/mortar-camera-cause-review.md)。未改标签、未训练。

**用户首批确认问题已落档：**mortar_shell的`2023-09-21_103140`按整录音待复核，另有`2023-09-21_101622`明显错位帧。两条录音全部268张paired图与native图hash一致、paired框全部等于native标签x3；三个大图例子确认native图—标签组合已错位，非单纯gallery/padding问题。尚未核对官方原件，未确定最早原因或错误帧总数。当前t_camera_s中两录音包含train205/val41，这是待审范围不是坏标签计数。见[首批错位核查](复现/camera-baseline/annotation-issues/mortar-camera-misalignment.md)。不删录音、不改标签/旧分数，先解决标注质量再进入新训练。

按用户要求已完成[全量可视化导出](复现/camera-baseline/camera-annotation-export.md)：[浏览页（本地产物说明）](ARTIFACTS.md#artifact-c8be9f3fdccf)，当前paired非test 4,746张，以及40条允许检查录音的native完整标注序列26,761张，共31,507张带框图和缩略图；两套有重复帧。包含partial train/val副本额外3条录音的native序列，未续跑其数据准备，不改变HOLD。GT未修改、无推理、无训练，完整性缺失0/失败0。用户先逐张检查并导出问题CSV，之后再定位camera标签错误，不抢先下结论。

本轮新增访问记录必须保留：对单行camera.json做头部读取时实际读取了完整混合标注，不能沿用“本轮从未读test标注”。已在导出记录登记；test图像未打开或导出，没有test模型评价或据其调参。浏览页只包含明确允许的train/val/val_id和相关native开发录音。

用户最新补充：camera某一类框不合适，对应sonar框偏小；这是用户观察，尚未定位类别/recording/数据版本。当前先讨论camera，声呐人工/pseudo-label生成差异与小框问题待办。**camera原生标注来源不等于质量已通过**；在新训练前先定位并核查原始标签→FHD转换→实际训练输入三层，不能直接归因或修改标签。见[标注疑点登记](复现/camera-baseline/camera-annotation-pending.md)。

1. 在test内容关闭的前提下，核实录音历史使用与camera来源，冻结可审查的train/dev manifest、annotation版本、采样和覆盖。是否存在三类且历史可证的全新final test仍未知。
2. 从COCO起点重新训练一条recording-disjoint camera-only YOLOX-S；具体manifest未冻结前不发车。本轮按AGENTS只审计，零训练。
3. 同平台必要时只做一个几何或增广对照；种子复验服务于少量候选，暂不容量/KD/融合搜索。
4. 若缺三类未触碰录音，诚实报告grouped开发验证/CV，等待独立数据；单类bomb holdout只支持有限主张，不能制造final test。
5. 数据/协议合格后再讨论教师验收与蒸馏，不将声呐结果当相机证据。

## 阅读入口

- [总报告](复现/camera-baseline/README.md)
- [测评协议v2](experiment/evaluation.md) / [未来实验计划](experiment/archive/plan-camera-teacher.md)
- [已有非test结果](experiment/results.md)
- [文献复核](related_work/paper-evidence-review.md) / [来源获取记录](related_work/source-check-20261110/README.md)
- [实现复核](复现/camera-baseline/implementation-evidence-review.md) / [数据复核](复现/camera-baseline/data-protocol-evidence-review.md)
- [输入hash快照](复现/camera-baseline/evidence-snapshot-2026-11-10.json)
- [工作流验证记录](复现/camera-baseline/workflow-verification.json)

不要静默改写旧报告或原研究；有新证据就追加更正。数据格式转换、原图查看、模型评价与基于结果选型是不同层级，访问记录必须写清。没有paper源或历史run产物时保留未知。

## 2026-11-10 19:25 更正：放弃移动硬盘，改从 Zenodo 重新下载（用户决定）

- 用户 m01572 原话：“算了，你重新去网站上下载吧，吧之前的删了我不折腾硬盘里的了”。此前复制再次因整盘掉线中断（partial 停在 33,839,644,672 B / 54.6%，`[Errno 9] Bad file descriptor`，`Get-Disk` 里已看不到该盘）。
- 已删除旧 `D:/pby/data_processed.7z.partial`（33.8 GB）。旧的“从只读外盘复制”路线到此结束、partial 不可再续；WinBtrfs 与 `wincopy*` 脚本保留但不再运行。
- 新来源：Zenodo 记录 13778485（v1.1），官方 size **61,513,277,947**、`md5:2b9ef16c763a6964c608ed99a9cd1edb`，直链 `https://zenodo.org/api/records/13778485/files/data_processed.7z/content`。
- 网络实测（Windows 侧经本机代理 127.0.0.1:7897）：单连接 0.35–0.65 MB/s，8 连接 3.0 MB/s，16 连接 3.9 MB/s；WSL 内走不通该代理（Clash fake-ip DNS），故下载在 Windows 侧执行。
- 脚本 `tools/zenodo_dl_uxo_processed.py`（运行副本 `D:/pby/.uxo-transfer/zenodo_dl.py`，状态 `zenodo_dl_status.json`，检查点 `zenodo_dl_state.json`）：24 线程、8 MiB Range 分块、断点续传，写 `.partial`，末尾流式计算 MD5 通过才 `os.replace` 成正式文件。

## 2026-11-10 21:30 完成：`data_processed.7z` 已从 Zenodo 下载并通过 MD5

- 判据全部满足：`D:/pby/data_processed.7z` 存在，**61,513,277,947 字节**（与元数据一致）；MD5 `2b9ef16c763a6964c608ed99a9cd1edb` 由下载器自算与 `certutil -hashfile` 独立复核**两次一致**，等于官方 checksum。
- 过程：19:23:05 启动；21:20:41 因 6 个分块 `SSLEOFError` 与一次 `HTTP 429` 退出（当时 7327/7333 块，99.92%）；21:28:04 续跑补齐 6 块；21:28:24 完成下载；21:29:55 MD5 通过并改名。
- 文件头 `37 7a bc af 27 1c` = 7z 签名，归档格式正常。**未解压、未列目录**，未读取 `test` 相关样本。

## 附注：移动硬盘路线（已弃用，细节已归档）

原计划从只读 btrfs 移动硬盘（HIKSEMI MD202）直接复制 `data_processed.7z`，最终放弃。一句话结论：**该盘盒的 USB 桥在持续读下反复重置**——单次突发可达 362 MB/s，但连续读 1–8 分钟后整盘掉出总线（Windows 日志 `UASPStor` id=129 设备重置 38 次/40 分钟、`disk` id=153 重试 IO 51 次），一小时内掉两次；`wsl --mount`、btrfs、WinBtrfs 都不是原因。

- 影响：只损失时间。源盘全程只读、未写入，未解压；旧 partial 已按用户要求删除。
- 保留判断（证据强）：**该盘盒不适合作为本项目的持续读取来源**。
- 踩过的坑只有一条值得记：`pkill -f <脚本名>` 会匹配到自身 `bash -lc` 命令行而自杀。
- 完整过程（WSL 直通与挂载参数、extent 映射、WinBtrfs 编译与自签驱动、每次掉线的时序与读数）见[移动硬盘复制过程归档](related_work/uxo/external-drive-episode-2026-11-10.md)，本文件不再展开。
## 2026-11-13 本地camera M训练与actual raw评价完成

用户查询本地M进度，实查epoch200于16:35:32保存，200epoch/45000iter完成，自动评价实际EMA。已用既有tools/evaluate_local_raw_baseline.py --run camera_recording_m完成600val actual raw补评；metrics与weight-identity在runs/camera_recording_m/train/val_actual_raw_epoch200/，checkpoint sha256=53a2f8021c70b14ffbdce2b995858231eeabfa451f08da1fdd891abdd28d0300。raw pooled mAP67.3687/AP50=86.8468/AP75=79.5125/AR1=70.25（%）；EMA mAP67.2733，旧目录保留并另存evaluation-weight-correction.json。逐类表已补M；较S mAP+2.79pp但grenade AR1下降4.10pp，预训练来源不同及单seed边界保持。原研究/test/训练配方/划分均未改。此记录替代此前M仍训练/待补评状态；远端两run状态本轮未查询。


## 2026-11-13 续接核验与浏览入口再次交付

本轮复核推荐候选README、verification及artifact-sha256索引，索引46份文件当前SHA256全部一致。方案仍22/4/4条、2200/400/400对，candidate_pending_user_review；没有激活或重训。已请求Codex打开候选index.html，工具返回queued，未据此认证浏览器渲染。再次向用户提供浏览页、每类数量和地面条件只能train、缺独立评价的限制；具体名单沿用上述记录。











