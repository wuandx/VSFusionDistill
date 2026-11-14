## 2026-11-14 已确认camera-M教师训练输入

用户确认数据并授权仅相机YOLOX-M教师训练。采用paired_weak_scene_coverage_pan_split，独立相机train4138/val573输入在[训练副本](DataSet/camera_weak_coverage_trainval/README.md)，4711图/hash/框/类别/组互斥与血缘核验通过；[冻结](runs/weak_coverage_camera_m_teacher/dataset-freeze.json)。test/sonar未复制或载入，7未决不纳入，原配对数据/角色/标注保持。新增393相机助手标注单列；旧val/test开发历史及专家/同步边界不变。仅camera-M已启动，[启动证据](runs/weak_coverage_camera_m_teacher/startup-verification.json)。

## 2026-11-14 用户允许弱场景优先重分：train4138/val573/test518

[新划分浏览（本地产物说明）](ARTIFACTS.md#artifact-7b6b78ded1da)、[弱项对应与限制](复现/camera-baseline/weak-scene-coverage-resplit-5229.md)、[独立核验](DataSet/paired_weak_scene_coverage_pan_split/independent-verification.json)。既有5229对/42录音/35组只变角色，train4138/33录音27组、val573/5录音5组、test518/4录音3组；全部27种已登记scene×z×tilt×roll联合条件进train。上次弱项10585620、121539102、125048100、123841/124039212、15560957进入train，101416/104749原已train继续；新增四录音393仍全train。

用户本轮明确允许重新划分，覆盖优先替代此前固定5229版val/test约束；旧版保持。全组不可拆，原图/框/血缘不变，7未决不放行，无新训练/推理/AP。新方案受旧val/test诊断启发，属于开发协议，不能称未触碰盲测。floor ellipse与两种bomb flyby无留出，两类其余flyby只有val；test只3场景/3组、bomb仅30对。mortar flyby train只有10585620对，不含Min15；grenade左右gain5仍缺。实际留出pan支持7条100%、1条95%、105230为92.42%。名义联合覆盖不等于全部视图/设置或能力改善。

独立10458图像hash/解码、全COCO/YOLO、身份/录音/组、27联合与最少组独立枚举、pan复算、旧输入保持通过，跨角色编码/像素hash重复0。首版joint_only草稿paired_weak_scene_coverage_split因mortar pan28.4/30.1不推荐，标superseded保留；推荐paired_weak_scene_coverage_pan_split。原研究10条test关闭，旧评价史保持，后续需fresh COCO；优先恢复110411/110229、100927/101131、162055与11未登记相机对应，以补独立来源。


## 2026-11-14 四条新增录音双端扩充完成：5229对

[浏览（本地产物说明）](ARTIFACTS.md#artifact-9940a746ec7f) / [报告及更正](复现/camera-baseline/four-recording-paired-expansion-5229.md) / [独立核验](DataSet/paired_four_recording_expanded/independent-verification.json)。新增393对：180126/124241/124440/125924=100/100/93/100，全部train；124440另7项声呐弱回波未决，不当负样本。新增4录音、3保守组（124241/124440同组），合计42录音35组，train3433/val961/test835。旧4836身份/图/框/角色保持，val/test索引与COCO字节不变；独立两端副本可复制。新增相机JSON明确助手标注，非原标签/专家GT；未认证精密同步。

实际400项双端逐对审阅，24项显式修框后复看。此前“400个全部接受”是过早几何登记，已撤回，历史保留；最终393+7，以final记录为准。全图像/hash/坐标往返、raw像素、独立12帧提取和400时间映射复核通过，跨角色编码/像素hash重复0。新四条仅补左右运动联合条件及采集来源，未补flyby缺口。无训练或模型推理；既有test仅副本完整性检查，原研究10条test关闭，旧开发/评价史保持。

## 2026-11-14 全94来源审计与新增录音方向

[94条逐项结果和图（本地产物说明）](ARTIFACTS.md#artifact-ef26c73164e5)、[完整报告](复现/camera-baseline/all94-recording-coverage-audit.md)。94=38当前+13三类有相机待恢复/标注+11三类缺公开相机映射+10原研究test+22其他test_cylinder。已实际抽查84非test各3帧及11个未匹配相机片段各5帧；非全帧验收、新准入0，当前4836不变。优先补180126/124241/124440/125924双端框，再恢复162055共同可见窗口；11个未分配视频中有地面/mortar/grenade flyby样素材，ARIS身份未知，不能直接当新增录音。122115 notes飞越−90与原metadata倾角−34/pan149°扫掠冲突，更正此前将其视为已证实−90来源的判断。原研究test内容仍关闭。

## 2026-11-14 当前配对扩充与新划分：4836对（完整副本）

用户授权“加，可以重新划分”。[浏览页（本地产物说明）](ARTIFACTS.md#artifact-4f30fc00fd8b) / [逐录音表](DataSet/paired_expanded_resplit_candidate/recordings.csv) / [报告](复现/camera-baseline/paired-expanded-resplit-4836.md)：train3040、val961、test835，总38录音/32保守组。原4081身份/两端原图/原JSON/框全保留，新增755（19已有录音725+新17471130）；助手双端审阅非专家GT/精密同步认证。新目录完整两端实际图像及标签，可独立复制，COCO路径相对数据根，类别bomb/mortar/grenade。

组整体重分、hash跨集合重复0、原图框保持/raw像素/COCO与YOLO往返独立核验通过。8场景train、5场景三集合覆盖；mortar flyby仍仅110049训练38/105856验证20、采集设置缺口未补；grenade−90 flyby仍缺训练覆盖。旧test已用，新split有开发历史；原研究其余test未开。未训练，后续须fresh COCO；旧版及结果保留，不能直接比较跨split的AP。

## 2026-11-13 条件覆盖新划分候选供审阅

[30录音条件、照片及旧新角色（本地产物说明）](ARTIFACTS.md#artifact-d0e2c45d2060)、[候选说明](DataSet/paired_recording_condition_coverage_candidate/README.md)。原3000选入+398备用不变；新候选train2200/val400/test400，尚未激活。按名义运动/摆放/旋转等条件及记录pan支持制定，不按成绩择优；14种单来源组条件只在train，后续评价范围需限制。原交付包/旧split/现有结果保留，未重训；候选若采用需重新COCO初始化训练，不能重命名旧模型评价。

## 2026-11-13 工作站train/val副本已交付

[部署与核验](DataSet/workstation_baselines/README.md)：/root/wzl/dataset/paired_recording_trainval含冻结1800train/600val双侧图像及标注，源图/标注保留，仅增加分角色加载索引与COCO转换。远端9609文件hash、4800图像解码核对通过；test和备用未上传。原3000选入/398备用交付不变。用于用户授权的sonar-only S与fixed640 camera S训练，未改数据角色或原框。

## 2026-11-13 已冻结训练、验证和测试成员

用户确认按recording-level 6:2:2：[划分入口](DataSet/paired_recording_split/README.md)、[录音角色表](DataSet/paired_recording_split/recordings.csv)。3000选入对应train/val/test=1800/600/600对，各类600/200/200；398备用继承录音角色，默认不使用。独立角色索引与清单已核验，原交付包和标注不变。历史开发使用及来源组限制见划分说明，训练准入见[测评协议](experiment/evaluation.md)。

## 2026-11-13 当前交付：数据集构建与标注已结项

[交付包（本地产物说明）](ARTIFACTS.md#artifact-387067fb2f13)包含 3398 对相机—声呐图像及两侧 COCO/YOLO 标注，保留原相机 JSON。[选入清单（本地产物说明）](ARTIFACTS.md#artifact-415815fc6be4)为 3000 对（30 条录音各 100 对，三类各 1000 对）；[备用清单（本地产物说明）](ARTIFACTS.md#artifact-48f54bdd637e)的 398 对不计入选入子集。以本版 [manifest（本地产物说明）](ARTIFACTS.md#artifact-ba71e56ae039) 为准，文件、来源及标注格式的[完整性核验（本地产物说明）](ARTIFACTS.md#artifact-b4dd603aed73)已通过。

[论文数据集小节](paper/dataset.md)记录配对、标注和取样方法。阶段结项后不再补帧或改框；训练前的划分和配对准入见[测评协议](experiment/evaluation.md)。下方为历史版本记录。

## 2026-11-13 截断目标复核后累计3398对，选入3000对

用户明确允许可辨认的截断目标，纠正旧完整相机门槛。[新浏览页（本地产物说明）](ARTIFACTS.md#artifact-a14061aa6c51)、[结果](复现/camera-baseline/paired-bomb-truncated-results.md)。182317全146身份/13页本轮实际重看，新增115接受（110明确底部截断、5触底过渡），原31图/框/来源不变；该条146=100选入+46备用。累计3398=3000选入+398备用，30条各100、三类各1000；旧3283包保留，旧69缺额是旧准入历史，不再是当前数量。

新增camera_visibility与COCO attributes、YOLO关联sidecar；原相机JSON/框不动，旧样本缺新状态不表示全部未截断。全量3398原像素/字节/hash、6796框往返与去重通过；旧3283图/框/review/时间/来源全保留，仅182317旧10个选入标志转备用。4导出预览实际查看，HTML静态链接核验，未认证真实浏览器渲染。全部原标签只覆盖播放器0–9.94秒；14秒处无原camera框，本轮未新造框。精密同步疑点未解决（116窗口支持/3282未独立精密同步），非专家GT/CMHD标注方法复现/正式训练版本；无DS/test/训练/split/时间注册/原研究变更。

## 2026-11-13 最新双模态标注交付：2931选入，352备用

[paired_assistant_full_review（本地产物说明）](ARTIFACTS.md#artifact-7842e0e73cac)含3283对同名相机/声呐图、原相机JSON、两侧COCO/YOLO、逐帧血缘和全量验证。[使用说明（本地产物说明）](ARTIFACTS.md#artifact-b473334d4b1f)及selected/reserve成员清单均已提供。bomb994/mortar1204/grenade1085接受；选931/1000/1000，共2931，另352备用。29条足100，182317仅31，用户已选择保留69缺额。旧885图/框/来源保留，旧包未动；重选样令10个旧身份成员标志变化。

6273唯一身份实际看过；3283不同SD帧、6566框往返、原像素/原相机图JSON字节及血缘核验通过，两侧无完全重复像素。20条新增录音实际预览全看。相机640×360，声呐128×441/603/780不翻转；116沿用窗口支持、3167未独立精密同步认证，全包非专家GT/正式训练版本。与旧825并集3774中491仍待双端复核。原时间/gantry/注册/相机标签/正式split/test/训练未变。[累计报告](复现/camera-baseline/paired-assistant-full-review-results.md)含官方库存核查、论文数量原文和全部30条统计。

## 2026-11-12 新累计885对双端审核包

[paired_assistant_remaining（本地产物说明）](ARTIFACTS.md#artifact-72ad1ea7bf7b)保留两侧同名图像、原相机JSON、COCO/YOLO与来源；新270对，累计bomb271/mortar265/grenade349。793选入/92备用，6条达到100，3000目标未完成。885对全量完整性与1770框往返通过、两侧无完全重复像素；旧615包保留且旧身份/框/来源不变。862未独立同步核对、23沿用既有窗口支持，全包非专家GT/训练版本。与旧825的并集1532仅885双端已审，647仍待复核。[完整报告](复现/camera-baseline/paired-assistant-remaining-results.md)。

## 2026-11-12 助手直接审核的新累计配对包

[paired_assistant_expansion（本地产物说明）](ARTIFACTS.md#artifact-5f72a4eb1558)累计615对，两侧图像和COCO/YOLO齐全，原相机JSON保留；新增277对，bomb23/mortar265/grenade327。五条各100另bomb23，选入523、备用92；3000目标未完成。615对全量完整性与1230框往返验证通过，两侧无完全重复像素。旧338包原样保留，未读原test/改时间注册/split/训练。配对精密同步仍未认证；与旧825的唯一并集1327分615双端已审与712待复核。[报告与来源](复现/camera-baseline/paired-assistant-expansion-results.md)。

## 2026-11-12 双端逐帧复核阶段包

[新配对包（本地产物说明）](ARTIFACTS.md#artifact-9eebbc22ffa1)：338 对双端助手逐帧复核（mortar126、grenade212），三条各100选入300、备用38；双端图像、原相机JSON、COCO/YOLO和来源完整，全量独立完整性核验通过，无完全重复图像。与旧825待审身份重叠42，唯一并集1121，审核层级不可混同。实际408个唯一身份已看，不以重复审核计新样本。全部仍未独立精密同步认证，非专家GT/正式split，3000目标未完成。质量筛选偏向及DS三版失败见[阶段报告](复现/camera-baseline/paired-visible-expansion-results.md)。

## 2026-11-12 论文规模与双模态配对纠正

当前目标CMHD为3000对，3类各10轨迹×100；CMOLD另为约4700对训练+验证。新[双模态候选入口（本地产物说明）](ARTIFACTS.md#artifact-d98db18ebd09)恢复已有1120张声呐标注的SD相机图与原SD框：1120关联、986框格式有效、825扣除已知配对不足后待核，正式准入0。声呐单边1120不是目标完成。全允许池26761身份清点与4000均匀待审任务另存，不计作新标注。相机原框、时间对应、原数据与split不改；完整差额、来源与限制见[报告](复现/camera-baseline/paired-paper-scale.md)。

## 2026-11-12 新副本：直接声呐可见目标标注

`DataSet/sonar_visible_annotation/export/`含1120原像素PNG、YOLO、COCO、带框预览、逐帧来源和验证；16开发录音、三类822/199/99。706助手逐帧与414 deepseek-v4.1-flash高置信选框+抽查分开记账；不是专家GT。raw未翻转，预览增益仅显示；原标注/划分不覆盖，无test。已配对相机路径保留但不认证同步，训练版本未冻结。[报告](复现/camera-baseline/sonar-visible-annotation-results.md)。

# 数据说明与血缘

## 新固定注册与全允许录音开发检查（2026-11-12）

[sonar_fixed_registration_refinement（本地产物说明）](ARTIFACTS.md#artifact-2d05d5aadf17)包含每类首录音11张无框序列观察、3类9中心fit、40录音各3帧共120新旧投影检查。每类一套冻结6DOF和旧固定尺度，来源hash及全部候选保存；floor应用官方相对target迁移，未单独调帧。主助手QA新12可审/71需修/28错位/9不确定，旧13/76/22/9，不能替换默认或升级正式GT；“可审”非用户接受。去elevation完整投影作为第三诊断列，120数值投影但仅6例目视抽查，不混主QA。所有用户审阅仍0，原GT/split/test限制不变；新数据均来自既有允许manifest，新增观察超界身份未读取。详见[报告与操作者边界](复现/camera-baseline/sonar-fixed-registration-refinement.md)。

## 初始候选来源纠正与floor映射修复（2026-11-12）

人工页默认旧PCA是未通过注册假设，扩到40录音不代表自动标注可用；应先改善自动框质量，不能用用户大面积重画代替。现仅对明确floor录音2023-09-21_160551（1385 native）从普通target/100lbs改为官方target/100lbs_floor，候选改名floor_target_pca_fixed；保留原mesh→target、旧代码/hash及所有历史，候选携带新旧ID、官方矩阵、notes/YAML/模型来源hash。其余39录音候选未改，未新增正式GT或接受记录。12测试、普通候选回归和正式服务加载检查通过；不表示floor框物理质量通过。全部40覆盖与人工接受/修订留痕目标保留，不要求唯一3D姿态才允许用户接受。详见[来源核查](复现/camera-baseline/sonar-initial-candidate-audit.md)。

## 全部允许录音的用户人工整理（2026-11-12）

已建立 [人工筛选页](http://127.0.0.1:8765)与[处理说明](复现/camera-baseline/sonar-manual-curation.md)。使用resolved manifest的全部40允许native录音/26761身份，paired_role=null仍是允许native，不能只保留4746旧paired。三类12/12/16条，每条以100合格配对为目标，共4000；初始均匀100只是建议，全序列可补选。SD缺8、可用26753，全部录音候选仍≥100，未预言QA后数量。

用户保留候选、人工修订、暂不确定、排除分别保存；声呐为raw边缘xyxy，相机为640×360 SD边缘xyxy，polar参考图不是标签坐标。保存每个候选与最终框、原图及原标注hash、原因/操作者/时间/历史版本；不覆盖原GT。正式日志在DataSet/sonar_manual_curation，UI自动测试另在sonar_manual_curation_validation/ui-test并标automation_test。交付时实际人工接受0，后续以正式用户日志为准。旧几何失败限制自动标签，不能替代用户框验收；人接受不认证原3D注册。无新split/test/训练，论文3000与本次40录音覆盖分别标记。

## mortar固定注册与跨轨迹开发检查（2026-11-11）

[mortar_fixed_registration（本地产物说明）](ARTIFACTS.md#artifact-6e4b4b92b25f)保存两条既有允许开发轨迹六身份，首条100927的0087/0451/0811为fit、第二条101131的0103/0509/0909为check；此角色不产生新的教师split或盲验。独立无框assistant观察为fit19点、check12点，0909空观察，完整物理边界均unknown。0.580m固定尺度及官方声呐链下运行24组固定姿态拟合，15合格候选和所有失败保留；每个候选跨六帧只用一套变换，check不调参。freeze模型SHA e3e4e61835655c52ebb2e6c32df08751df69b8e5c2f54f0aeb013d6ba6279a8b；check观察SHA136bc6530a8f2914fec0e870dff5eb808d9f718d2f5bd50fc8d1777e7034cf9b。

两可辨check帧支持距离为零，所有六帧候选框仍不稳定；5 unresolved/1 uncertain，无正式GT准入。保存未加elevation、±7°/7.5°几何、raw/polar2框、旧PCA同成像对照、观察与输入hash、主/独立目视记录及独立数值复算；无人工修订框，不将unknown当负样本。图中凸包仅为显示，损失仍使用表面离散支持。原GT/源数据/旧注册/split未改，0训练/test，细节见[结果报告](复现/camera-baseline/mortar-fixed-registration.md)。

## 固定mesh直接sonar诊断（2026-11-11）

[sonar_fixed_mesh（本地产物说明）](ARTIFACTS.md#artifact-8f0a04b6ace9)保留3类固定s/R/t、18个允许身份的原图/投影/候选框与双assistant目视QA。另命名sonar_fixed_mesh_beam_sign只改beam方位符号，mesh JSON字节相同，两版原始图/位姿/距离不变；轴证据、预登记和失败全部保存。反号后方向改善，但独立QA仍0 aligned/13 partial/3 misaligned/2 uncertain，主QA有1帧程度分歧，均未准入。两帧无可靠回波不直接判负样本。JSON/CSV框为诊断候选，不能当正式GT；raw和本地fan框不能互换，也不能移植到官方polar2图。原数据/注册/GT/split未改，0test/训练；见[完整报告](复现/camera-baseline/sonar-fixed-mesh.md)。

## 我方独立几何注册试点未通过（2026-11-11）

已实际运行[独立注册](复现/camera-baseline/sonar-independent-registration.md)：公开来源未获原始metric注册后，用固定6条允许开发录音18身份（17SD）的独立assistant轮廓拟合相似变换，6图fit/11图检查，未用旧框/blob/cache。三类当前/历史标定共48次起点求解，均因检查误差/旋转多解未通过；输出位于`DataSet/sonar_independent_registration/`，全部`approved_for_sonar_gt=false`，不得作为正式GT来源。轮廓/近似端部为未专家审核的我方诊断参考，camera K/畸变和逐帧几何未认证。源数据未变，无新教师split/训练/test访问；1缺SD保留，没有替换样本。下一步先排查相机实测几何或取得独立metric对应，不能把本轮候选升级成CMHD官方注册。

## 3D注册与标定版本更正（2026-11-11）

[本轮核查](复现/camera-baseline/sonar-model-registration-consistency.md)已解释上一轮4°差异：官方7月26日修改camera安装pitch，早于此的notebook结果需搭配历史标定；历史控制误差6.24e-7，独立库通过。两版sonar链相同，不因camera版本差异修改声呐坐标。版本矩阵保存在`DataSet/sonar_model_registration_consistency/calibration-versions.json`。作者明确camera–sonar外参精度有限，尚未认证逐录音准确。模型登记保留官方历史名义尺寸/PCA尺度候选，但`mesh_to_target=null`、`approved_for_gt=false`；缺完整尺度/朝向/原点对应，不能按候选量产框。160原始metadata hash及原仓不变，无新split、GT、训练或test访问。下方“标定一致性未验收”中的版本原因已解决，物理精度/模型注册仍HOLD。

## CMHD式sonar投影输入核查（2026-11-11）

用户授权后已完成[现有链与9帧试点审计](复现/camera-baseline/sonar-projection-chain-audit.md)：本地blob/projected不是3D网格投影，不能直接作为CMHD标签。官方3D模型与标定包已按MD5核验并保存在工作流related_work/sonar-projection-audit-assets；40条允许录音均有原始Pan/Tilt/Roll，可重建AR3位姿，但OBJ到target坐标的metric注册和标定版本一致性仍未验收。当前HOLD，不生成正式sonar GT/新split，不训练，不访问旧test。见[9帧图与数据（本地产物说明）](ARTIFACTS.md#artifact-3db267dd4f52)。

## 用户选择：训练优先SD（2026-11-11）

后续camera-only teacher优先准备原生640×360 SD数据版本。按已核验ARIS时间/匹配关系取SD帧，使用原始SD坐标框，不乘3；类别与原始标签不改。已有FHD重建及核验保留供对照。此项是用户的数据版本选择，不是CMOLD披露的协议，也不是SD性能优于FHD的实验结论。

SD版本需独立登记覆盖、样本身份、hash与原框QA；不能直接继承FHD的622未恢复名单或其候选计数。原框范围疑点在SD上仍存在，须继续复核。当前仅记录优先级，尚未生成新的冻结SD训练集或启动训练。

## 全部允许camera录音重建完成（2026-11-11）

`DataSet/camera_temporal_all/manifest-resolved.json`为最新候选数据清单：40条、26761原生身份、26139候选FHD、609缺FHD覆盖、5时间待核、8缺SD参考。4746个paired身份全部映射，4566候选、180未恢复。7个EOF缓存血缘补充有独立预登记和证据，base清单及原状态保留。类别/原框/原标签字节不改，原图及源输入hash前后一致；121个processed源及53522个原JPG/标签size/CRC与官方归档全匹配。

全部候选实际JPEG做内容核验，130张独立全分辨率单帧抽查，40条120个固定概览目视。无test、无训练、新split。1117个原框越界几何提示另列，不自动判坏：173615为797、175000为320；框QA与时间处理状态分开。原生26761不能当旧训练池新规模直接混入。见[全量报告](复现/camera-baseline/annotation-issues/camera-temporal-all-results.md)及[浏览页（本地产物说明）](ARTIFACTS.md#artifact-509c66e4b095)。

## 两录音重建试点完成（2026-11-10）

用户授权试做与核验。独立副本`DataSet/camera_temporal_pilot_rebuilt`保留101622/103140全部1482个native样本身份，其中1449有候选FHD图、33在101622开头缺覆盖；含268个paired身份，261候选、7缺覆盖。原生标签字节副本全等，FHD框与旧gallery全等，无框平移。用完整ARIS精确onset、实际SD/FHD PTS重建；全部状态独立复算和9张单帧解码抽查通过。原始输入hash不变，无test访问、无训练、未改split。候选仅为时间/内容筛查，仍待逐框QA。详见[结果](复现/camera-baseline/annotation-issues/camera-temporal-pilot-results.md)。

## 完整源时间审计更新（2026-11-10）

已检查gallery允许的40条开发录音：120段SD/FHD/UHD元数据、80段SD/FHD内容；未打开test。38条SD/FHD有非零时间偏移，40条fps均相同，结束时间近同，起点差折算帧数与帧数差一致。固定2,992对灰度抽样支持38条的时间对应优于同序号，解码计数全部通过；这不是38条逐框验收，更不是坏标签率。见[完整源原因审计](复现/camera-baseline/annotation-issues/full-source-timing-cause-audit.md)。

已确认的导出帧号复用机制会把源视频起点差带到图—GT组合。独立裁剪是有控制支持的候选历史解释，具体生产命令未知；公开脚本不能代替历史日志。源图、GT、split均未更改，当前数据不因此自动成为合格新基线。

## 当前完整源目录（2026-11-10用户解压完成）

`D:/pby/data_processed/`包含aris、gantry、gopro、matches.csv，SD/FHD/UHD视频目录各76段。本轮复核两条允许开发录音的四段源视频size/CRC均与官方归档一致，matches.csv与此前取到的官方副本一致；检查记录为`related_work/uxo/sd-fhd-trace/local-extracted-source-check.json`。这是来源可用性检查，不是全目录逐文件内容校验，也不代表已修好SD/FHD时间对应。

压缩包保存在`D:/pby/data_processed.7z`；已有certutil记录官方MD5匹配，本轮未重复全包哈希。后续优先使用这一解压目录，不重复下载或复制外盘。原研究仍只读，test样本不进入当前审计。

当前阶段只审计 camera-only teacher。原始 UXO 来源为 Dahn et al., OCEANS 2024，DOI `10.1109/OCEANS55160.2024.10754316`；公开数据入口为 Zenodo `13778485` 和 `https://github.com/dfki-ric/uxo-dataset2024`。官方说明为近 100 条轨迹、超过 74,000 帧、三类 UXO、ARIS 3000 + GoPro Hero 8；GoPro 标注坐标需乘 3。

## 本地数据平台

主要配对数据为 `D:\pby\uxo-full\paired\`，包括 `camera.json`、`sonar.json`、`frame_meta.csv`、图像与标定信息。相机原生标注与声呐 blob/projected 框必须分开：camera-only 训练不依赖 sonar GT，不得把声呐 blob-only 的筛选规则套到相机评测。

当前 `frame_meta.csv` 的 train/val/test/val_id 分别为 2,652/1,500/1,500/594 帧，对应 27/10/10/27 条录音。val_id 是 train 录音内的缓冲留出，不是额外 27 条录音。历史文档中的 900/1,650/1,798/7,960 等数字属于其他转换或 dense 采样版本，必须同时记录版本，不可互相补全。

`D:\pby\uxo-full\repro\frame_split.json` 是 seed 0 的帧级 8:2 划分：train 3,322、val 830，三类分布均衡。它合并原 train+val 的 4,152 帧、37 条录音，再随机按帧拆分。train 和 val 共享全部 37 条录音，仅 image id 不重复不等于 recording-level 无泄漏。排除原 test 1,500 与 val_id 594，不代表原 test 从未被旧模型评价。

## 采用的角色

同录音帧级 val 用于管线与同分布诊断，主验证和最终测试应按 recording 隔离。旧原 test 已用于模型间交叉比较，降级为开发对照。下一轮重建的 recording-level manifest 必须记录数据版本、标注 hash、逐 recording 清单、类别/几何/采集条件、排除理由与历史使用情况。

本轮不生成新 split、不训练、不评价 test。先冻结协议并核实是否存在合格的历史 test 替代，不为提升分数事后挑选录音。完整计划见 `experiment/evaluation.md` 与 `复现/camera-baseline/README.md`；已有其他 agent 留下的未完成准备见下方更正。

## 数据访问边界

本轮未读取 test 图像或重新计算 test 指标。已有的 test 输出仅用于追踪旧报告的来源，不能用于选择下一个模型。原始数据与原研究未修改。

## 2026-11-10 增量复核与更正

后续SD/FHD源追查已找到两个mortar录音的时间对应问题：101622的FHD晚于SD64帧，103140的FHD早于SD194帧。原生标签x3无法补偿时间起点差；camera数据准入除坐标/框QA外还需逐recording核对母视频、start_time、fps、帧数与实际画面对应。未变更任何标签、图像或split。三个问题例子原框在正确时刻的SD/FHD上合理，不能简单认定人工画框错误。详见[视频时序核查](复现/camera-baseline/annotation-issues/sd-fhd-temporal-mismatch-findings.md)。

以上数据计数和帧距若来自混合 frame_meta/annotation 的旧审计，均为历史复算记录；本轮没有重新全量解析这些文件。安全 train/val split artifact 独立核对见 [数据复核](复现/camera-baseline/data-protocol-evidence-review.md) 与 `frame-split-artifact-check.json`，确认3,322/830、ID交集0、37/37共享录音，但不声称重新验证了每个ID对应的原图和原始标签。

其他 agent 已留下 `DataSet/camera_recording_disjoint_v1`：当前仍 incomplete、3,446帧，partial manifest只有22条train/3,296帧和1条val/150帧。本轮未续跑、未打开其图片，维持HOLD。准备脚本拟定4条test均为bomb，不能作三类最终验收；旧excluded角色也不能证明完整历史未训练/未选型。脚本还进行了bbox clipping，不能称与原生标签逐框等值。

仅拷贝或格式转换不是开发污染的充分条件；真正要查训练、诊断与选择历史。相反，未转换也不能自动证明未使用。新final test若无法覆盖三类或无法证明历史隔离，应先做recording-disjoint开发验证/CV并承认独立final test未建立，不能强造封存集。

camera-only虽不使用sonar GT，旧paired转换仍有calibration gate、配对/gantry可用性和cap/trim选择。放宽这些条件是新数据版本，不等于模型改进；无标签帧也不能自动当成确认负样本。官方坐标乘3的依据可核，但旧新平台的完整逐框一致性仍未知。
# 2026-11-12 追加：原点包络诊断产物

`DataSet/sonar_origin_envelope/`仅复用既有120开发投影记录、9fit帧raw副本和82助手观察。包含官方原点投影、误差区间反投影、保守包围球条件及共同球控制，不是新标注版本；无正式GT、人工review、split或原数据修改。[证据与限制](复现/camera-baseline/sonar-origin-envelope.md)。



## 2026-11-12 端部固定注册诊断副本

`DataSet/sonar_endpoint_registration/`与`DataSet/sonar_endpoint_pan_control/`复用6既有bomb开发身份；后者另复用旧17camera端部观察。两个run均未通过，固定pan不是正式标定；无正式标签/划分变更。来源在`related_work/sonar-origin-anchor-sources/`。[报告](复现/camera-baseline/sonar-endpoint-registration.md)。


## 2026-11-12 源运动时间对照

DataSet/sonar_motion_timing与sonar_source_onset_control仅开发诊断，源offset替代假设未部署、不是新的标注/时间权威版本；正式matches/GT/split/review未改。[报告](复现/camera-baseline/sonar-motion-paper-alignment.md)。


## 2026-11-12 ARIS运动起点人工反馈

`DataSet/sonar_translation_onset/human-review.json`独立保存第二段173329的用户原话与时间口径歧义，不覆盖原results.json。用户约3秒尚未确认为画面时间或播放器进度，不改matches/原数据，不作为精确同步值。自动.666126秒阈值触发不等于物理首运动；时间版本仍未冻结、未授权进入注册。见[复核报告](复现/camera-baseline/sonar-translation-onset-human-review.md)。


## 2026-11-12 时间口径已确认，gantry取样空档待查

`human-review-confirmed.json`保存用户“播放器进度约00:03”澄清，即画面t约+1秒；原`human-review.json`保留。`gantry-sampling-audit.json`保存六开发录音首变化样本前2.09–2.19秒空档。不能把首变化样本或人工约1秒当精确同步offset；生产matches及数据不变。见[取样审计](复现/camera-baseline/sonar-gantry-onset-sampling-audit.md)。


## 2026-11-12 gantry空档来源与时间准入

[来源审计](复现/camera-baseline/sonar-gantry-gap-origin.md)确认六CSV与官方processed归档size/CRC一致，首变化前约2.1s空档非本地新增；但processed CSV不能冒称原bag。官方导出仅保留/odom header时间，原bag接收时间/序号/控制状态未保留；当前未取得这些记录，不能区分发布暂停、漏包与header时钟问题。两bomb matches偏移与公开GoPro/gantry联动公式精确一致，不能用首变化样本之差直接认定同步误差。所有旧matches、数据、GT、split保留，时间未冻结。证据与合成控制存`DataSet/sonar_gantry_gap_origin/`。


## 2026-11-12 sonar_camera_continuous_timing

171105 的 SD—ARIS 连续配对在所查 +6.20 至 +55.95 秒通过，保留图像配对证据；173329 未通过，按用户意见移出本轮可靠配对候选。两条 gantry 末段平移时刻都未获得独立验证，均不进入几何投影候选集。仅针对本轮两条开发录音，不删除原数据，不改变正式 split 或原 matches。 [核对报告](复现/camera-baseline/sonar-camera-continuous-timing.md)。


## 2026-11-12 sonar_four_recording_timing

四条新增开发录音均未通过现有相机—ARIS连续配对检查，按预登记跳过独立 gantry 核对；没有冻结时间或启动注册。合计六条仅171105在已查范围有图像配对支持，无一条同时通过两项。 [报告](复现/camera-baseline/sonar-four-recording-timing.md)。

## 2026-11-13 连续方块诊断副本

`DataSet/sonar_tag_continuous_camera`只含允许录音123500的276个重建FHD来源引用、检测叠图和条件姿态诊断，保留80无标记帧；其中149帧三面共视，另冻18fit/16check用于留面预测。该结果不是新的相机标定、声呐标签、配对时间或正式数据版本。见[报告](复现/camera-baseline/sonar-tag-continuous-camera.md)。


## 2026-11-13 场景分层扩充候选4061对

[候选清单与浏览](DataSet/scene_stratified_paired_expansion/README.md)：36录音/30来源组，train2472/val874/test715。取消3k及每录音100帧配额，旧3318选入+398备用+345新增助手接受，640新提案另295待修未纳入。沿用整录音/来源组角色与5完整场景/3独立来源缺口；本版未激活、未重训，用户/专家及精密同步未认证。旧数据和实验保持。详见[报告](复现/camera-baseline/scene-stratified-paired-expansion.md)。


## 2026-11-13 迫击炮flyby补来源后的4081对候选

[新版清单/浏览](DataSet/scene_stratified_mortar_recovered_candidate/README.md)新增105856的20对val，37录音31组，train2472/val894/test715。旧4061身份/框/角色保留，旧版不改。mortar flyby有train16/val20、test仍缺；110229/110411未决不纳入。仅助手审核，未激活训练或认证精密同步/用户专家验收；原test关闭。详见[复核报告](复现/camera-baseline/mortar-flyby-recovery.md)。
# 2026-11-14 四条录音双端候选：400个待准入样本

> 本条初稿已作废：400全部接受的说法错误，最终393接受、7未决；见本文顶部5229版更正。下文原样保留历史。

全94录音审计后，四条优先来源180126、124241、124440、125924各取100个共同可映射身份，形成400个相机—raw声呐候选。全程逐对总览复核后400个通过候选框几何与同类可见性登记；框为助手新增候选标注，非原始GT/专家GT，未认证精密同步。当前4836对、录音角色和split不变，400个保持`dataset_admission=pending_user_split_review`。[复核报告](复现/camera-baseline/four-recording-paired-annotation-review.md)。

