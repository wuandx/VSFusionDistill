# sonar_fixed_registration_refinement：实际改进普通录音初始框

2026-11-12，用户要求继续执行，不再止于诊断。目的：利用连续开发观察给固定模型注册补充可见范围约束，实际生成新候选并跨录音检查。原版本全部保留，不训练、不访问原test、不改原GT/正式审阅。

## 本轮唯一方法变化

原先只有稀疏亮点“落在模型内”的单向包含损失，无法限定检测框。新版本先无叠框观察第一条允许录音的局部序列，明确可见本体范围、端部可信度和unknown，再冻结约束。模型尺度、beam符号、时间、官方sensor位姿与外参固定，仍每类只求一个跨帧刚体变换。完整物理边界unknown时，不将可见亮段边缘伪装为3D端点；若使用可见回波框来改善人工整理初始化，必须单独标明为检测框近似约束，不能称物理注册真值或正式GT。

fit开发录音：bomb 2023-09-20_171105，mortar 2023-09-21_100927，grenade 2023-09-21_120653。首中末中心依次为0622/0981/1336、0087/0451/0811、0163/0551/0933；每中心±8 ARIS、步长4，最多15图/类，仅访问resolved manifest内身份。超界不读、不替补。配对SD只作本体身份/支架辅助，不用camera投影产生声呐框。全部曾用于研究的角色保留，本轮不称盲验。

三个观察包分别落在sonar_bomb_sequence_observations、sonar_mortar_sequence_observations、sonar_grenade_sequence_observations。观察冻结前不查看本轮模型投影。优化器合成控制在独立登记中先执行，已知对应恢复与未知表面匹配分别报告。

## 对照与评价

对照为旧PCA同beam/同官方成像接口，mortar还保留旧start00。根据fit观察选择与冻结模型，冻结后才用于第二条录音和更多允许录音的检查；检查不反拟合。新版本首先检验首中末跨帧检测框，而不要求所有三维自由度唯一。自动可保留、需人工修订、无法判断/排除分别记录，assistant QA不冒充用户验收。

具体新增损失、容差与优化预算在观察冻结后、真实优化前追加到本登记；不能根据check表现改。拟合不成功也必须交付真实运行结果与叠图，不以“未知”代替执行。源hash/允许身份失败即停该步骤，修正实现需保留失败记录。

后续批量展示仍以全部40允许录音为用户目标；未通过基本跨帧检查的新候选不替换默认。人工接受不要求唯一3D姿态或等待GoPro完整重标定/作者回复。

## 优化前冻结：near_surface_range版本

2026-11-12，在真实优化开始前登记以下实现。三类均复用旧fixed-mesh-transforms中的固定mesh_to_target_similarity作为模型参数化（名义长0.737/0.442/0.580m），不更改尺度；求一个T_world_from_model。官方普通target平移为参数中心，dx/dy/dz各限±0.25m，yaw/roll各[-180,180]°、pitch[-75,75]°。输入只含每类首条fit录音中心观察，check观察不加载。每类12,000固定面积分层采样点加6轴极值顶点，采样seed20261112；最终用全部顶点、三角形中心和三边中点复算。

每个冻结观察beam中心±1.5范围内，取当前可见模型采样投影的最小raw range bin为预测近表面。可见性固定为前方z>0、官方range/beam范围及±7° elevation。没有该beam窗口支持时，取最近beam支持点的range，并另罚超出±1.5的beam差/1.5；全无可见支持时两个归一化残差均100。range残差以4bin归一化，使用delta=1 Huber；每帧先对点取均值，再跨帧等权。该min-range模型只是近表面几何近似，不等于最强回波或精确声学仿真；beam窗口可带来几何前移，采样/密集差异均保留。

grenade冻结front-observations中的峰值位置仅作近回波ridge代理，用有符号range差/4bin；不宣称与mesh点精确对应。mortar仅用eligible_for_main_curve=true的18点；beam窗使用observation_box_raw_edges的左右界，range用该box的上下区间，区间内残差0、区间外最近边界距离/4bin；raw_uv_edge只保留为强度见证。其余9点不用于目标。mortar来源observations-freeze及两个观察JSON的hash核对后冻结适配。

可见左右消退区间仅作为弱检测初始化项：预测可见模型raw bbox左右边缘超出观察区间的距离/4beam，delta=1 Huber均值乘0.1；不赋予物理端点意义。标记possible_horizontal_fov_censoring=true的mortar帧左右项全部关闭，不能把FOV边缘当物体端点。没有可靠远端/阴影边界约束。所有系数不根据check修改。

固定3个DE seed=20261112/20261113/20261114，每个popsize8（6维共48个体）、maxiter120、tol1e-7、polish=false、best1bin、mutation=(0.5,1)、recombination=.7、latin hypercube初始化并含旧PCA零参数点。随后对各自DE最优点以归一化参数进行有界Powell，maxfev2000、xtol1e-4、ftol1e-6；保留DE及Powell全部终值、改进轨迹与最终population，不因success=false丢弃已经运行的有限候选。各seed最终取DE/Powell中fit目标较低者，类内仅按采样fit cost选优；记录密集重放但不据其或check另选模型。输出所有3个固定候选及采样/密集框，框padding0；多解不阻止输出检测候选。

首次运行产物写sonar_fixed_registration_refinement/<model_name>，包含源hash、适配后观察、模型参数化、每seed结果、fit-results与freeze-model。旧源码/输入/正式审阅不改，主登记的执行前快照随每类保存。bomb schema到达后只作已说明点/区间字段适配，若语义不同须先追加说明再运行。

## bomb优化前字段适配冻结

观察源为sonar_bomb_sequence_observations/observations.json，SHA256=`3c4ef2bec5bd216880f778a54fd18bdb2ec2f3c880174e9cc023b442317df257`。只用0622/0981/1336三个中心的12/14/11点，邻近8帧没有数字曲线点，不代入优化。每个点的near_range_bin_interval作为range区间，raw_uv_edge仅定位beam中心/保存见证，beam窗仍±1.5，区间外距离除4bin。lateral_visible_echo_edge_intervals_raw_u映射为同权重0.1的弱左右项；0981的possible_fov_truncation非空且边缘null，两项关闭。可见回波bbox不作完整物理框约束。其余采样、尺度、参数边界、DE/Powell预算、fit-only选择规则完全沿用。此追加发生在bomb真实优化前，不改变已完成grenade/mortar结果；各自执行前计划与代码快照保留。

## 冻结后的跨录音检查范围（拟合结果产生前登记）

每个允许录音检查native首/中/末共3帧，总40×3=120；三个fit录音固定用上述既有3中心，因此包含9个fit身份，另111身份仅作本轮开发检查。先写selection并保留SHA256，不根据框好坏替换。floor使用已修正的官方target映射；相同类别注册迁移到floor只是外推，必须单独标明。每类freeze-model落盘后才生成该类评价图。

评价保存全高raw原图、旧PCA（相同成像、零padding）和新固定注册对照、两套raw框、source hash与SD身份参考。新旧都不逐帧移动。assistant逐帧分类为可供用户保留审阅、需修订、明显错位、无法判断；不把这些分类写为用户接受或专家真值。统计每录音分母3和全类分母，不省略失败。没有数量/质量提升也保留图与结果。本轮该检查不启动训练、不生成正式GT。
