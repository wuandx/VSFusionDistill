## 2026-11-14 camera-M已迁移5090正式训练，本地尝试已停止

用户授权部署192.168.10.100的WSL wzl目录。[部署报告](../复现/camera-baseline/weak-coverage-camera-m-5090-deployment.md)、[独立核验](../DataSet/weak_coverage_camera_m_5090_deployment/startup-verification.json)。远端根/root/wzl/weak_coverage_camera_m_teacher，独立source/数据/模型；实际GPU RTX5090D v2。全部9525文件hash、4711图与标注/组、GPU batch8/末batch2/推理/几何/rawEMA预检通过；源/数据/实现/初始化与本地相同、15配置字段路径归一后相同、8主要依赖版本一致。

保持camera4138train/573val、COCO fresh、seed0/batch8/200epoch/103600更新/无增广、固定epoch200 actual raw、每10epoch仅val。远端从COCO重新开始；主机改变及浮点差异披露，不拼接本地迭代。18:09:53远端epoch2的200/518，loss5.8408、约.196秒/步、剩余ETA5:37:26，估总约6h；此前3–5h粗估由实测更正。尚无新AP或完成结果。

Windows一次性任务WeakCoverageCameraMTeacher持久前台托管WSL，断开SSH后已继续；RestartCount0、24h上限，无周期。首次nohup随SSH退出未进入训练，记录保留。确认远端健康后18:09:31仅停止本地weak-coverage-camera-m-teacher.service，inactive/dead/MainPID0；最后epoch7的340/518，尚无epoch10 checkpoint，日志/状态历史保留于[migration](../runs/weak_coverage_camera_m_teacher/migration-to5090.json)。原研究只读、旧远端run保持；test/sonar图未上传，无test评价、声呐或KD训练；原开发史/标签/留出边界不变。

后续进度读远端runs/weak_coverage_camera_m_teacher/train.log和train/status.json；本地旧train/status现stopped_deployed_to5090，不再当运行中。完成后须确认epoch200/103600、actual raw/EMA身份、最终val及失败状态，再登记指标；不得重复注册/启动已有任务。

## 2026-11-14 用户确认后仅camera YOLOX-M教师正式训练已启动

用户“确定好数据集就开始训练吧先只训练教师模型的相机，yoloxm”，按[预登记](../experiment/archive/weak-coverage-camera-m-training-plan.md)冻结已交付paired_weak_scene_coverage_pan_split，camera-only teacher新run [weak_coverage_camera_m_teacher](../runs/weak_coverage_camera_m_teacher/README.md)。camera4138train/573val（33/5录音、27/5组），COCO-M fresh backbone/neck、随机3类head、seed0/batch8/200epoch、518更新/epoch共103600，无增广、keep_ratio fixed640右底114。SGD/LR/epoch schedule沿用原camera-M；数据与总更新数变动必须披露。新增393助手标注血缘单列，原图/框/角色不变，test不复制或载入，无sonar或KD启动。

4711相机图+血缘JSON/hash/解码/原框/COCO身份/组互斥通过，GPU预检batch8前后向/推理/逆几何/COCO张量严格载入/raw–EMA往返与最后batch2 loss/梯度有限；preflight和train实现/源/输入/初始化/配置语义hash相同。持久WSL服务weak-coverage-camera-m-teacher.service (Restart=no)已产生真实Epoch(train)迭代、有限loss，见[startup-verification](../runs/weak_coverage_camera_m_teacher/startup-verification.json)。当前实际日志位置1epoch内320/518；这是启动快照，后续进度读取train.log及train/status.json，未称完成或有新AP。

主结果固定epoch200实际raw；每10epoch监测val，EMA单独导出，沿用score.01/NMS.65/max100，不选best或切EMA。旧val/test开发使用史保持，val5组、floor ellipse/两bomb flyby缺留出，原研究10test仍关闭。原研究目录只读，旧run/队列不修改或恢复；本授权替代此前审计阶段禁启动训练，范围只本camera-M。当前启动不代表收敛或覆盖收益。


## 2026-11-14 用户允许弱场景优先重分：train4138/val573/test518

[新划分浏览（本地产物说明）](../ARTIFACTS.md#artifact-7b6b78ded1da)、[弱项对应与限制](../复现/camera-baseline/weak-scene-coverage-resplit-5229.md)、[独立核验](../DataSet/paired_weak_scene_coverage_pan_split/independent-verification.json)。既有5229对/42录音/35组只变角色，train4138/33录音27组、val573/5录音5组、test518/4录音3组；全部27种已登记scene×z×tilt×roll联合条件进train。上次弱项10585620、121539102、125048100、123841/124039212、15560957进入train，101416/104749原已train继续；新增四录音393仍全train。

用户本轮明确允许重新划分，覆盖优先替代此前固定5229版val/test约束；旧版保持。全组不可拆，原图/框/血缘不变，7未决不放行，无新训练/推理/AP。新方案受旧val/test诊断启发，属于开发协议，不能称未触碰盲测。floor ellipse与两种bomb flyby无留出，两类其余flyby只有val；test只3场景/3组、bomb仅30对。mortar flyby train只有10585620对，不含Min15；grenade左右gain5仍缺。实际留出pan支持7条100%、1条95%、105230为92.42%。名义联合覆盖不等于全部视图/设置或能力改善。

独立10458图像hash/解码、全COCO/YOLO、身份/录音/组、27联合与最少组独立枚举、pan复算、旧输入保持通过，跨角色编码/像素hash重复0。首版joint_only草稿paired_weak_scene_coverage_split因mortar pan28.4/30.1不推荐，标superseded保留；推荐paired_weak_scene_coverage_pan_split。原研究10条test关闭，旧评价史保持，后续需fresh COCO；优先恢复110411/110229、100927/101131、162055与11未登记相机对应，以补独立来源。


## 2026-11-14 paired_four_recording_expanded_5229：新增393配对，无新AP

[交付（本地产物说明）](../ARTIFACTS.md#artifact-9940a746ec7f)、[报告与过早登记更正](../复现/camera-baseline/four-recording-paired-expansion-5229.md)。按[计划及导出前补充](archive/four-recording-paired-annotation-plan.md)，400候选实际双端审阅，393接受+7未决，24项修框后复看。新增4录音/3保守组，全进train；train3433/val961/test835，总5229对/42录音35组。旧4836行/图/框/角色与val/test文件字节保持，独立解码/hash/标注往返/raw像素/时间身份及12帧重提取通过。早期400/400接受说法撤回，不把几何有效当目视准入；最终事件与历史错误均保留。新增助手标注非专家GT/精密同步，无训练、模型推理或新AP；旧test和开发史继续披露，原研究10条test关闭。

## 2026-11-14 all94_recording_coverage_audit：来源审计完成，无新AP

[报告](../复现/camera-baseline/all94-recording-coverage-audit.md) / [逐录音图和清单（本地产物说明）](../ARTIFACTS.md#artifact-ef26c73164e5)：94条metadata、84非原研究test×3帧及11未分配相机视频×5帧实际查看，hash/身份核验通过。4条无原标签来源优先双端补标，未分配flyby样视频需恢复具体对应；122115 notes与原ARIS轨迹metadata冲突已更正其弱场景优先级。新准入0、4836版保持，无训练/推理/test内容访问，不报告模型增益。

## 2026-11-14 paired_expanded_resplit_4836：数据建设完成，无新模型成绩

按用户新增配对与重分授权，完成[4836对/38录音数据产物（本地产物说明）](../ARTIFACTS.md#artifact-4f30fc00fd8b)：train3040/val961/test835，原4081不变+755助手接受对，只有174711是新增录音（30对），其余725来自19条已有录音。两端逐对审核与独立导出/组/hash/框往返核验通过；非专家GT或精密同步。目的/规则/停止条件见[预登记](archive/paired-expanded-resplit-plan.md)，[结果与未决边界](../复现/camera-baseline/paired-expanded-resplit-4836.md)。本轮未训练/推理/评价test，无AP可报告；重分与扩样同时变化，旧AP不可直接归因增益。旧715test使用史保留，新test非未接触盲测，原研究10条test仍关闭。后续两模态fresh COCO训练，增广只用本版固定train/val比较。

## 2026-11-14 scene_baselines_test715：用户授权固定epoch200 raw的test评价

按[事前冻结](archive/scene-baselines-test715-evaluation-plan.md)评价当前715对/7录音7组，不扩大其他原研究test来源。**camera-M test pooled mAP85.5357%、AP5098.6799%、AP7597.6320%、AR187.9359%**；**sonar-S test mAP67.7347%、AP5090.7444%、AP7576.6512%、AR174.2193%**。模型均固定epoch200 actual raw，与val同原几何/score/NMS/maxDets，无训练/选权重/改数据。[完整逐类/录音/场景报告](../复现/camera-baseline/scene-baselines-test715-results.md)、[汇总JSON](../runs/scene_baselines_test715_review/results.json)。

test三类各308/246/161，mAP camera87.34/92.92/76.34、sonar80.69/59.24/63.27（bomb/mortar/grenade）。test无mortar flyby及两种bomb flyby，不能评价这些场景独立泛化；声呐test高于val不意味着泛化落差消失。独立1430图准备核验及1435文件hash复核通过，每模型715身份输出完整且有限。当前test自此登记模型评价使用，既有开发史保持，不用于调参或继续宣称untouched盲测。
## 2026-11-14 scene_camera_m_baseline / scene_sonar_s_baseline after_pilot完成：epoch200 actual raw主结果

两项200epoch/61800更新完成，固定seed0/train2472/val894、无增广、keep_ratio fixed640。**camera val pooled mAP89.3709%、AP5097.3525%、AP7595.6811%、AR191.1680%**；**sonar val pooled mAP51.3790%、AP5084.3017%、AP7548.2690%、AR158.3007%**。同权重train自评两项mAP/AP50/AP75均100%。[检查预登记](archive/scene-baselines-final-results-review-plan.md)、[完整报告](../复现/camera-baseline/scene-expanded-baselines-final-results.md)、[原始汇总/场景/诊断](../runs/scene_baselines_after_pilot_review/results.json)。

camera各类mAP94.28/85.75/88.08（bomb/mortar/grenade），sonar78.59/34.27/41.28。两者GT任务不同，AP差不作为方法增益。camera多数场景较好但flyby仍低（grenade68.85、mortar47.15）；sonar问题更明显（mortar1014169.36、flyby1058560.59），训练充分拟合而val落差较大。固定score.25诊断与AP分列，未唯一归因。保持epoch200 raw，不换中间峰值/EMA，无test评价或新训练；两个服务均退出。10epoch pilot为独立诊断，不能与完整run拼成训练曲线。
## 2026-11-14 scene_camera_m_baseline / scene_sonar_s_baseline after_pilot：重新授权并行正式训练

用户要求按原方案两项同时开，按[预登记](archive/scene-baselines-after-pilot-launch-plan.md)启动独立after_pilot attempt；两项均COCO fresh train，原2472/894、200epoch/batch8/seed0/61800更新、无增广、keep_ratio fixed640、epoch200 raw主结果/EMA另列。旧停止run及10epoch pilot不覆盖。两新服务已产生真实epoch1 optimizer日志，loss/梯度有限，无OOM；[启动核验](../runs/scene-baselines-after-pilot-startup-verification.json)、[命令/服务](../runs/scene-baselines-parallel-launch-after_pilot.json)。原GPU预检证明仅在hash一致下复用并登记来源，未宣称重做预检。暂无新AP或完成结果，无test访问。
## 2026-11-14 scene_camera_m_pilot完成与分布诊断

10epoch/3090更新camera-M已完成；actual raw val mAP68.3100%、AP5089.9106%、AP7587.9167%、AR171.6084%，epoch5 val60.6116%。按[预登记](archive/camera-m-pilot-distribution-analysis-plan.md)同权重train自评mAP78.46%、AP50~100%、AP7599.67%；[完整报告与逐类/场景/录音](../复现/camera-baseline/camera-m-pilot-distribution.md)、[原始JSON](../runs/scene_camera_m_pilot/train/distribution_analysis/results.json)。普通左右与地面ellipse train/val较接近；grenade flyby75.68→15.78、mortar flyby78.37→33.97，分别表现为错分bomb与框偏差。固定score.25诊断及全部COCO指标分列，不以候选IoU替代AP。10epoch尚不能认证收敛或唯一根因；两种bomb flyby无val。三服务均已停止，无新训练/阈值调优/标注更改或test访问。
## 2026-11-13 scene_camera_m_pilot：用户停止长跑后启动10epoch单相机检查

用户要求先停两项长跑并只跑少轮camera-M。两旧服务已停止于epoch2（camera最后日志100/309、sonar200/309），无epoch10checkpoint，状态stopped_by_user，保留日志不作训练完成。按[预登记](archive/scene-camera-m-short-pilot-plan.md)从同COCO起点新跑camera-M10epoch/3090更新，原200epoch LR方案前缀保持，其余数据/配方不变；5/10epoch验证保存，最终raw与EMA分列，自动生成固定val图与曲线。单服务scene-camera-m-pilot已进入实际epoch1且loss有限，[启动快照](../runs/scene_camera_m_pilot/startup-verification.json)；暂无AP。sonar和两200epoch不会自动重启，test仍关闭。
## 2026-11-13 scene_camera_m_baseline / scene_sonar_s_baseline：正式并行训练已启动

用户授权后按[预登记](archive/scene-expanded-baseline-parallel-launch.md)在本机RTX5060Ti16GB以WSL用户服务并行启动新版camera-M/sonar-S，配方与数据hash保持最终预检版本；每项2472/894、200epoch/batch8/seed0/61800更新，无增广、keep_ratio fixed640、epoch200 raw主结果。两边已有epoch1真实optimizer iteration日志且loss/grad_norm有限，未见OOM；[启动核验快照](../runs/scene-baselines-startup-verification.json)、[命令/服务](../runs/scene-baselines-parallel-launch.json)。尚无训练完成或AP读数，不读取test，不把预检合成AP当模型结果。
## 2026-11-13 scene_expanded_baseline_preflight：五项新版适配通过，非训练结果

按[预登记](archive/scene-expanded-baseline-implementation-plan.md)完成新版2472/894两模态独立执行副本与camera-M/sonar-S入口，[实现及证据](../复现/camera-baseline/scene-expanded-baseline-implementation.md)。6732图解码/hash/框/双端/来源组核验、6741文件独立hash复核通过；M/S真实batch8×3×640×640、COCO载入、前后向/推理、类别与框逆变换、真实raw/EMA checkpoint往返通过，误差0/3.052e-5px。309step/epoch、200epoch共61800更新按实际长度计算。功能控制：两模态各894val完美GT mAP1/错类别mAP0，缺图与未认证权重拒绝；这些是合成控制而非模型检测结果。原入口与结果保留，未启动正式训练、未读test逐帧内容、未改标注或划分。
## 2026-11-13 scene_stratified_recording_split：每场景分层的具体候选，无模型读数

按用户明确意图和[预登记](archive/scene-stratified-recording-split-plan.md)，仅重分现36录音30组；train21/1985、val8/749、test7/584，备用286/53/59，原3716身份/框/hash/选入备用不变。5场景三集合均覆盖：三类非地面左右运动、燃烧弹flyby、地面炸弹ellipse；3种flyby各仅1已接受组，留出缺失。场景优先于pan硬覆盖，地面val/test pan43.4/57.1%与高度倾角差异披露。此方向替代旧28/4/4推荐，旧版本保留。独立核验7432图像、6 COCO、组互斥/跨角色hash重复0、113链接通过；新6预览实际看过，未验证浏览器渲染。额外15非test录音级来源核查未找到能直接填齐flyby的已接受共用来源。未激活/训练/推理/新接受框，新增318仍待用户验收，新test有开发审阅历史。[新浏览页（本地产物说明）](../ARTIFACTS.md#artifact-0fc3a69c3703)、[报告与缺口](../复现/camera-baseline/scene-stratified-recording-split.md)。

## 2026-11-13 expanded_paired_recordings / expanded_paired_coverage_split：扩录音联合划分候选

按[事前规则及覆盖优先补充](archive/expanded-paired-recordings-plan.md)，47非原test来源审计，新增6录音318对助手双端接受；旧3398对不变，共3318选入/398备用、36录音30来源组。推荐train28/2634、val4/284、test4/400；所有宽条件进train，holdout记录pan同宽条件±5°覆盖95%–100%。floor ellipse160146/160551进train、155609进val，明确其z1250与训练z1000差异；124735电子设置缺口分列。比例优先22/7/7草案保留不推荐，pan不足后另名修订。700新提案逐帧实际查看、110049重看28接受16；剩11录音未准入。7432图像/源hash/旧身份与框/六COCO/YOLO往返/组互斥与跨集合hash/静态链接核验通过。无模型读数、AP选取、原test内容读取、旧split修改或新训练；新增用户/专家验收0、精密同步未认证。[报告](../复现/camera-baseline/expanded-paired-recordings.md)、[推荐带图候选（本地产物说明）](../ARTIFACTS.md#artifact-adc723e0ca52)。

## 2026-11-13 condition_aware_recording_split：覆盖审计及候选，无训练读数

按[事前规则](archive/condition-aware-split-plan.md)检查30录音，生成[最终候选](../DataSet/paired_recording_condition_coverage_candidate/README.md)。22/4/4条=2200/400/400对，类别8/1/1、6/2/2、8/1/1。21精确主条件均在train，14种single-group为train-only；所有holdout同主条件在train，记录pan支持99–100/100 within5deg，次级电子设置边际值覆盖。身份/组/图像hash/原metadata/旧split不变核验通过。仅名义条件初稿保留，因动态pan范围覆盖不足在最终候选前补约束。未按AP搜索、未激活或重训；旧test已看使本候选不是untouched最终test，新版必须COCO重训。来源/算法/限制及30条首中末预览已交用户审阅。

## 2026-11-13 camera_s_test_evaluation：用户授权冻结test评价

按[预登记](archive/camera-s-test-evaluation-plan.md)测试camera S640×384 epoch200 actual raw，同train/val权重与协议。test600 pooled mAP78.6456%、AP50 89.2739%、AP75 84.6866%、AR1 79.3667%。[逐类/逐录音](../复现/camera-baseline/camera-s-test-results.md)。bomb/mortar/grenade AP分别58.62/78.32/99.00%；floor bomb17.23、另bomb97.59。只用已冻结600test，不扩原研究test访问；本次后该test已用于模型评价，不能据其调参后仍声称untouched。未重训或变更数据。

## 2026-11-13 camera_train_self_evaluation：训练拟合充分，val落差确认

按[预登记](archive/camera-train-self-evaluation-plan.md)，同camera S640×384/epoch200 actual raw无训练自评。train1800 pooled及逐类/18逐录音mAP/AP50/AP75/AR1=100%；对照val600 mAP64.5760%、AP50 80.4111%、AP75 75.6661%、AR1 69.4%。[完整train读数](../runs/camera_recording_baseline/train/train_actual_raw_epoch200/metrics.json)、[排查报告](../复现/camera-baseline/camera-train-val-gap.md)。1800原标签hash/映射核对通过，24张清GT控制预测不变，176次同类train近邻引用实际均匹配。排除所查全局映射/推理GT使用问题；支持泛化落差，不将其唯一归因于训练轮数/背景或GT，无test或训练修改。

## 2026-11-13 camera_recording_baseline完成：raw主结果与EMA分列

本地相机YOLOX-S640×384、seed0、200epoch、train1800/val600。**raw pooled mAP@[.5:.95]=64.5760%、AP50=80.4111%、AP75=75.6661%、AR1=69.4000%、AR10/100=69.4333%**；[raw完整逐类/逐录音与计数](../runs/camera_recording_baseline/train/val_actual_raw_epoch200/metrics.json)。EMA另列mAP64.8878%、AP50=81.0092%、AP75=75.8772%；[旧目录实际EMA结果](../runs/camera_recording_baseline/train/val_raw_epoch200/metrics.json)保留，[身份更正](../runs/camera_recording_baseline/train/evaluation-weight-correction.json)已落盘。训练不重跑，raw从ema_state_dict.module.*严格加载后补评。无test，不按权重版本挑最好结果。单seed及数据历史边界保持，M及远端尚未在此登记完成。

## 2026-11-13 工作站两run恢复

用户授权继续，sonar_s/camera_s_fixed640从已保存epoch50/iter11250完整resume（模型/优化器/scheduler/EMA），未改数据或训练配方，目标仍epoch200。原中断日志保留，新增camera-resume.log/sonar-resume.log；checkpoint完整性断言通过。恢复并不证明原中断根因解决，未产出新AP。

## 2026-11-13 sonar_ray_visibility：自遮挡只收缩远边，未修注册

按[预登记](archive/sonar-ray-visibility-plan.md)完成[报告](../复现/camera-baseline/sonar-ray-visibility.md)及[图/数值（本地产物说明）](../ARTIFACTS.md#artifact-9c4e3205ed51)。当前train103728/123500各3帧、两套既有固定姿态，12组无fit；raw左/近/右边差全部0，远边收缩，10组分辨率检查通过（0.867–6.313cm），2组未通过保留。解析控制≤4.44e-16m，84真实资产射线独立求交≤4.89e-15m，源hash不变；六图解码/总览目视，浏览器未验。仅自遮挡支持、无强度/场景/回波框IoU；不能修tag角差或认证物理注册。六RGB与模型视图库重看仍未形成可靠新物理对应，AnP/PnP未执行。原研究/标签/当前split/训练不变，无新旧test图像或逐帧标签读取/模型测评。

## 2026-11-13 baseline_integrity_audit：审查，无新增训练结果

[报告](../复现/camera-baseline/current-experiment-integrity-audit.md)、[控制结果](../复现/camera-baseline/integrity-audit/checks.json)。4800框往返/跨机camera标注一致/来源组隔离与实际评测器AP1/AP0控制通过。发现类别—声呐尺寸完全关联、分组枚举非均匀随机；确认实际checkpoint raw/EMA不同，统一权重补评待执行。审查不改现有训练或数据，不读test，不把已通过控制升级为GT/同步/部署认证。

## 2026-11-13 workstation_sonar_s / workstation_camera_s_fixed640：远端预检通过，正式启动

按[预登记](archive/workstation-baselines-plan.md)在AMHS5090工作站运行，[部署与证据](../DataSet/workstation_baselines/README.md)。同1800/600、COCO S起点、200epoch/batch8/seed0，无增广、fixed640；声呐为当前可见回波GT，camera为原SD框。9609文件远端hash及4800图解码、源码hash、组互斥、真实batch8GPU前后向/推理通过。14:20两项epoch1第100/225步且loss有限，尚无AP。test/备用未传，原项目与旧远端结果不改。

权重口径更正：直接核对mmengine0.10.7 EMAHook，启用时state_dict为EMA，raw在ema_state_dict.module.*。先前本地S/M将state_dict称raw错误；自动输出文件名不改变实际加载。远端已采用真实raw字段，后续需对本地S/M真实raw补评（尚未执行）再做相同权重口径比较。训练本身不受影响。

## 2026-11-13 camera_recording_m：预检通过，并行启动

按用户要求新增[YOLOX-M](../runs/camera_recording_m/README.md)，[事前规则](archive/camera-recording-m-plan.md)。train1800/val600、200epoch、batch8、seed0与S同数据hash/预算。作者COCO M转换516张量、数值前向差≤9.03e-6、真实GPU batch8前后向/推理通过。首次参考BN设置控制失败及修正保留说明，未训练错误候选。S/M预训练来源不同，非纯容量归因。独立后台提交，当前无模型指标；test关闭、原研究不改。

## 2026-11-13 camera_recording_baseline：预检通过，训练启动

按[预登记](archive/camera-recording-baseline-plan.md)启动[首轮camera-only teacher](../runs/camera_recording_baseline/README.md)。1800train/600val均为原SD相机标签，2400张全量图像hash/解码/坐标通过，6图几何目视；GPU前后向/推理和COCO加载通过。YOLOX-S，200epoch/batch8/seed0，45000iter、固定epoch200 raw权重，仅val最终评测；无test/旧UXO权重/声呐图像/备用。当前无AP读数，启动不等于训练成功，运行状态见产物；原研究只读。

## 2026-11-13 paired_recording_split：冻结成员，无训练读数

按[事前规则](archive/paired-recording-split-plan.md)落实用户确认6:2:2：[产物及核验](../DataSet/paired_recording_split/README.md)。每类6/2/2录音，1800/600/600对；398备用按来源归属243/113/42。录音/保守来源组互斥、两侧hash无跨角色重复、全量成员一致与独立复核通过，输入hash不变。122608/122855合组，grenade test来源组数为1；已有开发历史与稀有条件限制保留。无训练、模型指标、原test内容读取或数据修改。

## 2026-11-13 相机—声呐数据集阶段结项

用户确认以 [paired_assistant_truncated_review（本地产物说明）](../ARTIFACTS.md#artifact-387067fb2f13) 结项：3000 对选入（30 条各 100 对，三类各 1000 对）、398 对备用；双侧标注和完整性核验已交付。[中英双语数据集正文](../paper/dataset.md)已完成。本条记录数据交付，没有新增训练或测评读数。

## 2026-11-13 paired_bomb_truncated：新增115，数量达到3000选入

用户明确允许可辨认的截断目标，纠正旧完整相机门槛。[新浏览页（本地产物说明）](../ARTIFACTS.md#artifact-a14061aa6c51)、[结果](../复现/camera-baseline/paired-bomb-truncated-results.md)。182317全146身份/13页本轮实际重看，新增115接受（110明确底部截断、5触底过渡），原31图/框/来源不变；该条146=100选入+46备用。累计3398=3000选入+398备用，30条各100、三类各1000；旧3283包保留，旧69缺额是旧准入历史，不再是当前数量。

新增camera_visibility与COCO attributes、YOLO关联sidecar；原相机JSON/框不动，旧样本缺新状态不表示全部未截断。全量3398原像素/字节/hash、6796框往返与去重通过；旧3283图/框/review/时间/来源全保留，仅182317旧10个选入标志转备用。4导出预览实际查看，HTML静态链接核验，未认证真实浏览器渲染。全部原标签只覆盖播放器0–9.94秒；14秒处无原camera框，本轮未新造框。精密同步疑点未解决（116窗口支持/3282未独立精密同步），非专家GT/CMHD标注方法复现/正式训练版本；无DS/test/训练/split/时间注册/原研究变更。

## 2026-11-13 paired_assistant_full_review：3283接受，2931选入，缺69按用户决定保留

按[事前计划](archive/paired-assistant-mortar-plan.md)持续双端审核与并行补充，累计6273唯一身份实际查看、8260候选决定、3283接受；新增2398，bomb994/mortar1204/grenade1085。29条各100另182317为31，选2931/备用352；用户选择保留现有数量并报告69缺额。全3283对完整性、6566框往返、两侧无重复像素和旧885图/框/来源保留通过；10个旧身份重采样改变选入标志，旧包未改。20新增录音导出预览全看。追加审计旧spec缺hash的KeyError已修正读取并留失败记录。无DS/时间注册/正式split/test/训练；配对精密同步与专家GT未认证。[完整结果](../复现/camera-baseline/paired-assistant-full-review-results.md)。

## 2026-11-12 paired_assistant_remaining：新增270对，累计885对

按[计划](archive/paired-assistant-remaining-plan.md)新增双端查看624唯一身份，270接受/354未决；累计1388已看、885接受，793选入/92备用、6条足100，距3000缺2207。B/F/E重复身份不重计，误批174439 B page12已追加撤销事件且未曾导出。885对全量完整性、1770框往返、无重复像素通过，旧615框/来源不变，四新增录音导出预览已看。没有DS/训练/test/新split/时间注册；精密同步与专家GT未认证。[结果](../复现/camera-baseline/paired-assistant-remaining-results.md)。

## 2026-11-12 paired_assistant_expansion：615对累积双端审核

按[计划](archive/paired-assistant-expansion-plan.md)由助手直接审核，新增356唯一身份中277接受；累积764已看、615接受，五条各100另bomb23，共523选入/92备用，距3000缺2477。bomb E/A截端、部分B含下方散射失败均留档，替代候选不重复计身份。615对全量源/输出/审核图hash、原像素/相机标签、1230框往返、无重复像素验证通过，三新增录音预览已看。本轮0DS调用、无时间注册/训练/split/test；未认证精密同步或专家GT。[详细结果](../复现/camera-baseline/paired-assistant-expansion-results.md)。

## 2026-11-12 paired_visible_expansion：DS 控制未通过，338 对助手双端复核

[计划](archive/paired-visible-expansion-plan.md)后完成v1 102对/39 high、v2同102对/45 high、v3 12控制/6 high；三版均发现系统误框，不自动扩批。v3恢复429后低并发完成，无运行批次。另实际逐帧看408唯一身份，338接受（mortar126、grenade212），独立导出两侧图/框，各100选入300、备用38；源/输出全量完整性、676框格式往返、两侧重复像素检查通过。原825待审与新338重叠42，并集1121但层级分开。没有精密同步/专家GT/新split/test/训练/时间或模型注册，距3000仍缺2700。[结果及失败证据](../复现/camera-baseline/paired-visible-expansion-results.md)。

## 2026-11-12 paired_paper_scale：纠正声呐单边交付

[预登记](archive/paired-paper-scale-plan.md)后完成1120对声呐—SD相机及双边标注副本；134原相机框越界，986对格式有效，扣除既有161对配对不足项后825对仍待核（620/155/50）。正式训练准入0，3000对目标未完成。40录音26761身份清点，21867来源候选、4000唯一均匀待审身份，不计作新标签。1120对文件/hash/身份/COCO-YOLO往返通过（最大5.700002247976954e-08px），无重复相机帧；目视三类各1对。无新DS/训练/test/注册/时间拟合/split。[报告](../复现/camera-baseline/paired-paper-scale.md)。

## 2026-11-12 sonar_visible_annotation / DS Flash

按[计划](archive/sonar-visible-annotation-plan.md)完成40录音120概览、20录音2000候选和Flash全部有效审核；导出16录音1120张（706助手逐帧/414 Flash high+录音抽查），690低置信或不确定+190录音QA失败候选不导出。全部1120像素/hash/COCO-YOLO往返通过，最大差5.7001e-8px。不是模型AP实验或专家GT验收，无训练/test/新split。[报告](../复现/camera-baseline/sonar-visible-annotation-results.md)。

# Camera-only teacher：结果登记

## 2026-11-12 实际固定注册改进：sonar_fixed_registration_refinement

按[登记](archive/sonar-fixed-registration-refinement-plan.md)完成三类各3中心near_surface_range拟合，9候选/53,340调用，固定尺度与sensor链、不逐帧移动。全部40录音120帧实际投影+目视QA：旧13可审/76需修/22错位/9不确定，新12/71/28/9；111开发check中旧11/71/20/9、新10/66/26/9，整体失败，不替换默认。mortar错位减少但整体可审数量未升。子agent完成bomb36和mortar36比较，root完成grenade36及mortar剩余12（子agent中断后），观察身份与操作者留痕，不称全量互盲。独立120元数据+21帧42框重放通过，差≤2.84e−13px、338源hash一致；仅认证软件。另固定模型比较去elevation裁剪：空框10→0、74边界变，但抽查仍有错位，主QA不混计第三版。240图、JS语法/链接通过，实际浏览器预览受自动审批/协议限制未验。正式接受0/训练0/test0/新split0。见[报告](../复现/camera-baseline/sonar-fixed-registration-refinement.md)、[完整对照（本地产物说明）](../ARTIFACTS.md#artifact-2d05d5aadf17)、[汇总（本地产物说明）](../ARTIFACTS.md#artifact-f95805ac1c9c)。

## 2026-11-12 初始候选核查与限定修复：sonar_initial_candidate_audit

按[预登记](archive/sonar-initial-candidate-audit-plan.md)定位默认框来自未通过的old_pca_fixed，扩至40录音没有修复注册；更正先前过早让用户承担批量修框的流程。另修复floor160551错用悬置target，新ID floor_target_pca_fixed，保留旧代码和来源hash。12后端测试通过；39普通录音映射不变、8既有帧14候选与旧代码完全相同、19输入hash未变。独立源码复核通过；8765实际服务重启后floor官方矩阵生效、当前普通175000_0887候选/血缘不变、审阅日志保留状态通过（仍0已审0接受）。这是实现错误修复，不是物理注册通过或自动框接受率实验；普通录音错位未解决，无新拟合/训练/正式GT/test/split。见[报告](../复现/camera-baseline/sonar-initial-candidate-audit.md)、[数值验证（本地产物说明）](../ARTIFACTS.md#artifact-3a7f803c0a37)、[部署检查（本地产物说明）](../ARTIFACTS.md#artifact-289c6ff74772)。

## 2026-11-12 数据整理工具：sonar_manual_curation

用户选择全部允许录音并要求亲自筛选，已实际提供40录音26761身份的[人工修框入口](http://127.0.0.1:8765)。每录音均匀100建议队列共4000，全序列可补选；保存用户原框接受/修订/不确定/排除与全部历史，按录音计缺额。10项后端测试通过，3类图像/SD来源核验及6帧两候选重放通过（raw1.71e−13px、polar4.55e−13px），实际UI画框/保存/刷新/导出/改判统计通过；4测试事件仅隔离目录，正式交付0已审0接受。无优化新fit/模型训练/AP评价/test/正式split。助手旧QA不作用户人工接受的自动否决；未静默改旧失败。见[方案](archive/sonar-manual-curation-plan.md)与[完整说明](../复现/camera-baseline/sonar-manual-curation.md)。

## 2026-11-11 固定声呐注册实测：mortar_fixed_registration

按[预登记](archive/mortar-fixed-registration-plan.md)完成mortar首轨迹3帧19支持点、24初值固定6参数姿态拟合，15候选合格，start-00仅据fit选择并冻结。第二轨迹3帧check支持点4/8/0，0103的归一化容许带外p95从旧PCA1.985到0，0509新旧均0；0909无可靠回波，所有观测指标null。6帧候选框稳定性全部未通过：fit最小两两IoU=.485/.621/.605，check=.504/.658/.541。仅2个粗密严格零损失解的fit框IoU也只有.680/.791/.877，低损失不唯一限定完整框。合成近邻恢复cost2.067→1.214未归零，保留优化方法限制。主/独立assistant目视5 unresolved/1 uncertain，非专家真值，正式GT准入0。独立两阶段数值复算最大分量差9.095e−13、输入hash一致；旧注册/源数据/GT/split未改，0训练/test/模型推理。全部为既往开发帧，未建立盲验。详见[报告](../复现/camera-baseline/mortar-fixed-registration.md)、[六帧对照（本地产物说明）](../ARTIFACTS.md#artifact-6e4b4b92b25f)、[冻结模型（本地产物说明）](../ARTIFACTS.md#artifact-ab6dd4daa0c6)。更正：早期“4零cost”实际为<1e−12，严格粗零2、密零7，另存分析不改历史。

## 2026-11-11 方法诊断：sonar_registration_methods

预登记后完成官方坐标、mesh几何和理想可观测性3项诊断。12组合成输入及18已有开发raw帧，独立polar2几何实现与官方函数逐像素相同；32输入hash未变，本地对应发布polar缺失故只验证源码兼容。3个OBJ比较顶点/表面积PCA：长轴差0.12–1.96°，100lbs第二轴差70.69°，不是实际姿态误差，说明PCA不能直接认证roll。既有18位姿/每模型6理想对应极值点的7参数导数检查通过（最大归一化差<4.8e−9），多视角改善局部约束，但不认证真实回波对应；未进行回波拟合。六notes复查与框QA草案完成；首轮OpenCV非连续数组失败及文案更正留存。原GT、两版候选、split不变，训练0、test0、新正式标签0。见[方法报告](../复现/camera-baseline/sonar-registration-methods.md)、[预登记](archive/sonar-registration-methods-plan.md)、[浏览（本地产物说明）](../ARTIFACTS.md#artifact-2add25c39be5)、[框规则草案](archive/sonar-box-curation-protocol-draft.md)。

## 2026-11-11 几何诊断：sonar_fixed_mesh / sonar_fixed_mesh_beam_sign

3类各1套固定s/R/t（名义长度+PCA+极值中点），6允许录音18身份直接sonar投影；不依赖GoPro、不逐帧移动。初版依据beam轴审计追加一个预登记反号候选，mesh文件字节不变、原图/位姿/range/el不变，独立AST确认逐帧仅az负号不同。两版软件重放最大分量差6.25e-13/2.27e-13；不等于物理标定通过。独立目视初版0 aligned/6 partial/10 misaligned/2 uncertain，候选0/13/3/2；主复核0/5/11/2与0/14/2/2，全部分歧留存。方向改善但三类均无完整通过，正式GT准入0；两帧目标不可辨认，不认证负样本。源输入/冻结hash及原仓不变，0训练/模型推理/test/新split。见[报告](../复现/camera-baseline/sonar-fixed-mesh.md)、[初版预登记](archive/sonar-fixed-mesh-plan.md)、[符号预登记](archive/sonar-fixed-mesh-beam-sign-plan.md)、[18帧对照与完整失败（本地产物说明）](../ARTIFACTS.md#artifact-8f0a04b6ace9)。这是同开发帧上的诊断，不是独立盲验或AP实验。


## 2026-11-11 静态来源审计：gopro_control_records

原包198915项仅成员目录核查、官方Git/发布包目录及有限相关仓库搜索，未取得原始设置/水下标定/tag尺寸布局。部分Github路线速率限制，边界明确；作者询问草稿已写未发送，不运行无依据PnP/同步姿态优化。原控制hash/视频stat及原仓clean通过；新增图像/标签内容访问0，0训练/推理/test/新GT/split。见[报告](../复现/camera-baseline/gopro-control-records.md)、[来源验证](../related_work/gopro-control-records/verification.json)。


## 2026-11-11 数据诊断：gopro_imaging_model

6开发录音18份容器元数据未提供模式遥测；官方历史/当前参数缺调用及水下标定证据，模式和畸变模型未认证。31既有副本AprilTag检测，6身份各SD/FHD阳性、保存四角与阴性；缺实测边长/布局，未执行物理PnP/同步姿态验收。发现官方历史camera_tilt主点索引等问题，但未证明本地旧注册使用它。原注册/源数据保留，hash/stat与原仓clean通过，0训练/推理/test/正式GT/split。见[预登记](archive/gopro-imaging-model-plan.md)、[报告](../复现/camera-baseline/gopro-imaging-model.md)、[验证](../DataSet/gopro_imaging_model/verification.json)。


## 2026-11-11 数据诊断：sonar_view_consistency

18身份源时间/索引/姿态复算通过，gantry差≤1.1991e-8m；局部34计划对=26可用+8越界，43次开发图像解码。排除目标后17对≥24点；部分点对固定位姿预测误差大于图像F内部检查，但22/26对homography高支持，非退化验收未过，不能唯一定位根因。仅焦距扫描未解决端点跨视角失配；无新K或GT准入。合成/独立数值控制通过，旧注册和源数据不变；0训练/推理/test评价/正式GT/新split，无AP。见[预登记](archive/sonar-view-consistency-plan.md)、[完整报告](../复现/camera-baseline/sonar-view-consistency.md)、[浏览页（本地产物说明）](../ARTIFACTS.md#artifact-a78fd6f9c5d4)。

## 2026-11-11 几何试点：sonar_independent_registration（未通过）

用户授权后执行我方SD轮廓约束相似变换注册，6条允许录音18身份/17SD，6fit/11检查；3类×2标定×8初值共48次求解。当前主版本fit RMS分别bomb20.88/30.02、grenade3.69/3.58、mortar2.90/2.48 SD px；检查RMS范围86.03–222.86、8.57–36.22、6.62–45.05px，三类均姿态多解，全部未准入。端部射线追加诊断/全部顶点独立重放已保存；不是AP/模型实验。0训练/模型推理/test访问/正式GT/新教师split，源数据及原仓不变。见[报告](../复现/camera-baseline/sonar-independent-registration.md)、[预登记](archive/sonar-independent-registration-plan.md)、[对照页（本地产物说明）](../ARTIFACTS.md#artifact-c45b6223b81c)。

## 2026-11-11 数据审计追加：sonar_model_registration_consistency

状态：标定版本差异解决，mesh注册仍HOLD。官方历史camera pitch −4°→0°解释此前控制差异；历史notebook矩阵最大误差6.2358e-7，独立库通过；sonar静态链相同。恢复三类名义尺寸并做PCA尺度诊断，但无完整mesh→target，未生成新GT。160个原始metadata hash与上轮/前后相同，原仓HEAD/status不变；0训练/推理/test访问、新split为0，无AP。见[报告](../复现/camera-baseline/sonar-model-registration-consistency.md)、[预登记](archive/sonar-model-registration-plan.md)与[验证](../DataSet/sonar_model_registration_consistency/verification.json)。

## 2026-11-11 数据审计追加：sonar_projection_chain_audit

状态：审计完成，CMHD物理投影GT准入HOLD；非模型实验。固定三类3录音9帧，独立复算通过，3 blob/6 projected，1缺SD保留deferred；52个试点输入及160个录音metadata文件hash未变。现有框链非3D模型投影；官方模型与标定包已MD5核验，OBJ注册/标定控制缺口未解决，未写新训练GT。0次训练/模型推理/test评价，无AP结果。详见[审计报告](../复现/camera-baseline/sonar-projection-chain-audit.md)与[预登记](archive/sonar-projection-chain-audit-plan.md)。下方2026-11-10与历史读数保留。

2026-11-10。本轮 **0 次新训练、0 次新模型推理、0 次 test 评价**。下表登记现有非 test JSON，不是本轮重新运行 COCOeval。原占位模板保存在 [results-template-original.md](archive/results-template-original.md)，不是已执行实验。

## 已有产物

均为 camera、d0、GT=all、pooled COCOeval；本地 830-val，train/val 共享 37 条录音。保留原 run 名，不改名伪装成新平台实验。

| 原 run / 条件 | seed / checkpoint | mAP@[.5:.95] | AP50 | AP75 | AR@100 | 结论边界 |
|---|---|---:|---:|---:|---:|---|
| t_camera_s / keep_ratio | 0 / epoch_200 | 0.9024874436 | 0.9897153654 | 0.9574760309 | 0.9316866193 | 同录音教师候选 |
| t_camera_s_stretch / squeeze train+eval | 0 / epoch_200 | 0.8743583982 | 0.9603439800 | 0.9287505769 | 0.8996476593 | 同平台几何对照；单 seed |
| t_camera_s / 仅 eval squeeze | 0 / 同一 epoch_200 | 0.2712356471 | 0.7215974336 | 0.1625384394 | 0.3668767097 | mismatch 诊断，不是 squeeze 训练能力 |

来源均在 D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\results\repro_cmold 下各 run 的 eval_val/ap_summary.json；第三行是 t_camera_s/eval_val_stretch/ap_summary.json。文件身份见 [evidence snapshot](../复现/camera-baseline/evidence-snapshot-2026-11-10.json)。t_camera_s 的图像/GT/预测数为 830/830/836，P2 为 830/830/849。未重复计算 AP，不把 hash 相符称作重跑验证。

P2−t_camera_s 的 AP = −0.0281290454（−2.8129 个百分点），不能解释旧平台或论文差距。t_camera_s 三类 pooled AP 为 0.9403552831/0.8950623037/0.8720447441，均值与 summary 闭合；逐录音均值为 0.9051461114，不能替换 pooled 0.9024874436。

## 历史平台与 test

早期 s0_c0、e11_bcam、E13-cam 见 [实现复核](../复现/camera-baseline/implementation-evidence-review.md)。它们的数据/配方/证据完整度不同，不与上表作受控增益相减。本表不迁入旧 test 读数，不依据旧 test 选后续模型。

## 计划但未运行

| 名称 | 状态 | 先决条件 |
|---|---|---|
| v1_camera_recording_split | 未运行 | 数据准入、录音级 manifest、COCO 重新初始化 |
| v2_camera_geometry | 可选，未运行 | v1 合格且需要新平台几何诊断 |
| v3_camera_augmentation | 可选，未运行 | 先冻结单一增广、对照与预算 |

下一轮按 [实验计划](archive/plan-camera-teacher.md) 先登记再执行，不覆盖历史读数。失败、协议偏离与停止原因也必须追加。
# 2026-11-12 追加：sonar_origin_envelope（几何诊断，非AP实验）

[报告](../复现/camera-baseline/sonar-origin-envelope.md)。120旧开发身份原点投影；9旧fit帧82助手观察保留beam/range误差区间后，bomb8/37、grenade2/27、mortar0/18超出旧mesh居中保守球，即仅旋转不可满足当前假设。不限elevation与±7°计数相同；不能据此唯一判定官方标定错。共同球控制为12候选，不是mesh注册或GT，不部署。24合成点、82独立区间网格、12候选可行性检查通过，输入hash不变。全部9图目视；120仅数值非新全量QA。无test/训练/正式GT/split变更。原历史内容如下保留。



## 2026-11-12 sonar_endpoint_registration / sonar_endpoint_pan_control

按预登记实际运行bomb端部两帧固定注册12初值，0通过；另固定pan常量诊断12初值仍0通过。+12.93°使首录音完整投影观察支持50/71/0%→92/100/100%，但第二录音失败，旧camera跨模态控制其他两类恶化，不能部署。源笔记解释bomb target测量组合，未恢复OBJ注册。24候选、12图/端点重放与源hash通过，无test/训练/GT/split/review；第三步粗定位条件未过。[完整报告](../复现/camera-baseline/sonar-endpoint-registration.md)。


## 2026-11-12 sonar_motion_timing / sonar_source_onset_control

六开发录音源运动审计发现两bomb matches偏移比gantry首运动早6.139467/1.75175s；另四一致。固定其他输入的源onset对照使首bomb三帧旧PCA支持0/71/0%→50/100/82%，camera同录音check端点中位34.29→10.17px；B端部区域相容性.473m→<1.3e−8m。第二录音/圆头仍失败，跨录音camera最大误差反增，不认证同步/GT。18独立位姿、6图、hash和负对照通过。[报告](../复现/camera-baseline/sonar-motion-paper-alignment.md)。


## 2026-11-12 sonar_translation_onset_human_review（已有诊断审计）

第二段173329用户判断“在t=3s左右开始持续移动”；画面t与播放器时间口径尚待确认，未登记精确onset。原自动触发.666126秒只表示对参考图累计位移连续五帧过门槛，撤回把它直接解释为确认平移的表述。0–4秒角度元数据稳定、hash与原run一致，但不能单独认证平移。保留旧结果/短片，时间未冻结，不注册。见[人工判断与复核](../复现/camera-baseline/sonar-translation-onset-human-review.md)。无新图像解码/训练/test/GT/split。


## 2026-11-12 sonar_gantry_onset_sampling_audit（元数据审计更正）

用户澄清173329的约3秒为播放器00:03，即画面t约+1秒。六条既有开发gantry首位置变化记录前均有2.09–2.19秒空档；173329旧映射边界[−.43625,+1.75175]秒覆盖用户观察。撤回以首次变化记录直接认证真实首运动/1.75175秒同步误差的解释；源onset控制仍为假设，时间未冻结、不注册。六CSV hash与原审计一致，无新图像解码/test/训练/GT/split。[报告](../复现/camera-baseline/sonar-gantry-onset-sampling-audit.md)。


## 2026-11-12 sonar_gantry_gap_origin（来源审计，非注册实验）

按[登记](archive/sonar-gantry-gap-origin-plan.md)核对六开发CSV与官方归档size/CRC，全通过；每条唯一>1s间隔均在首位置变化前，范围2.093999–2.188s。官方抽取逐/odom导出header时间、忽略bag接收时间，没有静止去重/降采样；未改写函数AST合成4消息控制通过，不能替代真实bag。2023-10-19官方7e60aea已因considerable delay把onset从前一行改首变化行，metadata与首变化一致不是独立物理证据。两bomb旧offset精确符合GoPro/gantry联动公式（−184@30000/1001，−105@60000/1001），不能直接称6.139467/1.75175s时间错误。源码main/config入口缺陷、网络失败与证据边界留档。未取得原bag/控制日志，精确采集原因仍未知、时间不冻结/不注册。Decimal/Fraction复核和hash通过，0图像解码/训练/test/GT/split。[报告](../复现/camera-baseline/sonar-gantry-gap-origin.md)。


## 2026-11-12 sonar_camera_continuous_timing

171105 的 SD—ARIS 连续配对在所查 +6.20 至 +55.95 秒通过，保留图像配对证据；173329 未通过，按用户意见移出本轮可靠配对候选。两条 gantry 末段平移时刻都未获得独立验证，均不进入几何投影候选集。仅针对本轮两条开发录音，不删除原数据，不改变正式 split 或原 matches。 [核对报告](../复现/camera-baseline/sonar-camera-continuous-timing.md)。


## 2026-11-12 sonar_four_recording_timing

四条新增开发录音均未通过现有相机—ARIS连续配对检查，按预登记跳过独立 gantry 核对；没有冻结时间或启动注册。合计六条仅171105在已查范围有图像配对支持，无一条同时通过两项。 [报告](../复现/camera-baseline/sonar-four-recording-timing.md)。


## 2026-11-12 sonar_box_guided_registration / sonar_box_guided_full_trajectory

用已有助手框反求两类固定6DOF注册，14初值/类/轮，共56候选。首轮413、全轨迹控制505帧，均非独立最终test。全轨迹grenade75未fit中位IoU旧PCA0.564→0.736，跨录音212中位0.532→0.550但IoU≥0.5比例下降69.8%→67.5%；mortar跨126中位0.476→0.454未改善。首轮mortar跨录音改善伴同录音后段失败，不能选择性拼接。模型投影凸包检查存在框好而轮廓方向不合；物理注册、同步、GT未认证。尺度/时间/外参不改，无训练/test/split/原标注变更。[报告](../复现/camera-baseline/sonar-box-guided-registration.md)。918运行内图片/2754 IoU核对、42帧密集投影重放误差≤3.98e-13px；所有候选及失败保留。


## 2026-11-12 sonar_projection_root_cause / curve_control / encoder_control / return_envelope_control

[报告](../复现/camera-baseline/sonar-projection-root-cause.md)。相同505开发身份，24 fit，143同录音/338跨录音check。五录音旧→曲线IoU中位 .454→.442/.452→.468/.736→.705/.555→.565/.547→.565；编码器与近表面控制也无稳定改善，不采用新模型。近表面与完整模型同时保留同padding对照，未挑录音拼接。已达预登记低边际收益停止。源gantry重放一致但不认证同步。58高回波帧全部候选精确重放，两个可见横向扩展通过E的仅range裁剪进入已接受框；物理回波来源未知，两例只是check，不声称改变了旧fit。42宽比筛查提示待复核，不是42错框。1010图/5050 IoU比较/63投影/21近表面重放通过，15当前检查帧目视仍见失败。无test/训练/正式GT/split变更。


## 2026-11-13 sonar_rgb_pose_pilot / sonar_rgb_pose_pooled / sonar_rgb_tag_rotation

[报告](../复现/camera-baseline/sonar-rgb-pose-pilot.md)。两类6帧、96纹理视图；合成控制check中位.926/1.149px、旋转1.25/1.81°；真实单视图5–7候选，合并35–61候选但最多5个RANSAC内点，全部未准入，不执行声呐转投影。3/6帧检测tag，123500两帧tag141条件相对旋转与发布链差21.60°/15.23°（两相机假设）；未知标记静止/相机模式，不归因或修正。用户无额外标定资料。源hash、96渲染映射、合成误差、tag尺度不变/trace验证与137图解码通过；无训练/test/split/GT改动。两次准备/序列化代码失败保留，完成run无后台进程。

## 2026-11-13 sonar_tag_continuous_camera / sonar_tag_camera_solver_control / sonar_tag_multiface / sonar_tag_clip_metadata

[报告](../复现/camera-baseline/sonar-tag-continuous-camera.md)。123500的276帧/196 tag141/149三面；旧锚点精确重放；固定三模型角差21.60/15.23/13.91°，五模型图像首解与时间连续分支一致。25fit/31check单面稠密全量pinhole/Brown角差19.82/29.05°，删块不稳定、保留一个未收敛控制。232背景对原锚点仅4匹配，三模型未证实标记动/静；三分辨率剪辑无可解释镜头/防抖字段。三面18fit/16check，固定模型独立留面均未达2/4px，Brown 1.19/2.42px但cx触界，原角差19.03°，不认证。共同±12帧发布角幅值77.124–78.482°，不足以解释至少5.49°幅值差。768留面点/290图片和693背景估计验证；失败对照保留。没有新注册、test、训练、正式GT或split。
## 2026-11-13 camera_recording_m完成：epoch200 actual raw补评

日志16:35:32保存epoch200，200epoch/45000iter训练及自动EMA评价完成。本轮按既定协议补actual raw的600张val：pooled mAP@[.5:.95]=67.3687%、AP50=86.8468%、AP75=79.5125%、AR1/10/100=70.2500%。[完整结果](../runs/camera_recording_m/train/val_actual_raw_epoch200/metrics.json)、[身份/hash](../runs/camera_recording_m/train/val_actual_raw_epoch200/weight-identity.json)、[逐类表](../复现/camera-baseline/per-class-baseline-results.md)。raw严格来自ema_state_dict.module.*；旧val_raw_epoch200实际EMA，mAP67.2733%/AP50=86.7859%/AP75=79.0712%，原样保留，身份更正另存。与S同raw口径mAP增加2.79个百分点，AP50增加6.44个百分点；grenade AR1下降4.10个百分点。仅单seed开发结果，预训练来源差异不支持纯容量归因；test未用，训练/数据/划分未改。



## 2026-11-13 scene_stratified_paired_expansion：4061对候选，无模型实验

[报告](../复现/camera-baseline/scene-stratified-paired-expansion.md)、[浏览（本地产物说明）](../ARTIFACTS.md#artifact-dcdb7635c6e3)、[核验](../DataSet/scene_stratified_paired_expansion/verification.json)。取消3000/每录音100配额；3318原选入+398原备用+345本批新接受=4061对，train/val/test=2472/874/715，录音21/8/7与30来源组不变。本批640全部双端实际审阅，295待修不入COCO；旧3716本轮未全部重做视觉审核。5场景三集合覆盖、3flyby仍缺独立留出来源。8122图hash/解码、345raw像素、旧身份/框/角色、6COCO/3清单、跨角色重复0与12328静态链接通过，浏览器未验。仅助手接受，用户/专家/精密同步未认证；未激活重训、无推理/AP，原test关闭，新候选test有开发史。


## 2026-11-13 mortar_flyby_recovery：新增独立val录音，无AP实验

[报告](../复现/camera-baseline/mortar-flyby-recovery.md)、[来源复核（本地产物说明）](../ARTIFACTS.md#artifact-9ab93db696df)、[4081对候选（本地产物说明）](../ARTIFACTS.md#artifact-318e1cce8c85)。105856的60修框提案实际双端审核，20接受/40未决，新录音整条val；110229主体不可辨、110411配对警告未解，均不准入。37录音31组，train2472/val894/test715，原4061身份/框/角色保持。mortar flyby train16/val20/test0，未补齐第三来源。723原JSON/索引/hash、36SD像素、195timeline raw、8162导出hash/解码、20raw像素、6COCO/3清单及隔离/链接核验通过。仅助手有限视觉兼容/回波审核，非精密同步/用户专家验收；未训练/推理/原test访问，浏览器未认证。


## 2026-11-13 train_scene_coverage_confirmation：覆盖审计，无模型实验

[报告](../复现/camera-baseline/train-scene-coverage-confirmation.md)、[独立复算（本地产物说明）](../ARTIFACTS.md#artifact-2d6be42a11f9)。当前4081对中的train2472/21录音覆盖8/8类别×摆放×运动场景，已核查62非原test库存同为8种；val/test无train未见场景。manifest/6COCO/3清单/官方notes一致、31来源组隔离与输入hash保持。精确名义条件train17/当前25，5条留出有同场景倾角/高度或电子设置缺口；mortar flyby16train仍少。不得称全部条件或姿态最大覆盖。成员/框/角色未改，无训练/推理/原test内容访问。







# 2026-11-14 四条优先录音双端候选复核：400个待准入样本

> 本条初稿已作废：400全部接受的说法错误，最终393接受、7未决；见本文顶部5229版更正。下文原样保留历史。

全94录音审计后，独立处理180126、124241、124440、125924。每条100个共同可映射身份，四条合计400；相机和raw声呐框均由本轮候选标注并逐对总览复核，400/400登记为`accepted_candidate`。这些不是原始GT或专家GT，未认证精密同步；未加入当前4836对及任何split，未训练、推理或访问新的test。报告：[复核](../复现/camera-baseline/four-recording-paired-annotation-review.md)。

