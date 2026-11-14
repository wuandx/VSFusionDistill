# 固定 mesh→target：直接声呐投影、符号核验与跨轨迹 QA

2026-11-11。两版投影和逐图复核已完成：3 类各 1 套固定变换、每类 2 条录音首/中/末，共 18 个固定身份。**三类均未取得可直接用于训练的声呐框。** 初版出现跨 beam 走向相反；依据原始 beam 编号和轴关系另存一个仅改变方位符号的候选版，方向改善，但位置、边界与可见性仍有未解问题。没有逐帧移动模型，没有据回波优化 s/R/t。

入口：[两版 18 帧完整对照（本地产物说明）](../../ARTIFACTS.md#artifact-8f0a04b6ace9)、[冻结变换（本地产物说明）](../../ARTIFACTS.md#artifact-fbc529ae2c21)、[数值附表（本地产物说明）](../../ARTIFACTS.md#artifact-e97e0e7632d9)、[最终汇总（本地产物说明）](../../ARTIFACTS.md#artifact-9d8f0f1fe563)、[修订记录（本地产物说明）](../../ARTIFACTS.md#artifact-c5389c21ffea)。

## 固定了什么，以及哪些只是我方假设

列向量约定：`p_target = s R p_mesh + t`，其中 R 不含尺度，t 单位为 m。完整精度 R、t、4×4 相似矩阵、OBJ hash、来源、目标世界位姿全部写入冻结 JSON；[数值附表（本地产物说明）](../../ARTIFACTS.md#artifact-e97e0e7632d9)也列出三个 R。

| 类别 / OBJ | 名义全长 m | s（m / OBJ unit） | t（m，target 坐标） | 变换后长/宽/高 m |
|---|---:|---:|---|---|
| bomb / 100lbs | 0.737 | 0.15320899998014 | −0.0693598303, 0.5280783223, 0.1302566069 | 0.737, 0.209646, 0.230058 |
| grenade / incindiary | 0.442 | 0.08265357940475 | −0.0454272213, −0.2177743181, 0.2972349905 | 0.442, 0.153636, 0.122544 |
| mortar / mortar_shell | 0.580 | 0.06174505067109 | 0.0966954400, −0.1913571275, 0.1711986135 | 0.580, 0.129746, 0.122015 |

依据层级必须分开：

- **仓库历史记录**：[historical-README.md](../../related_work/model-registration-sources/historical-README.md)提供名义全长 737/442/580 mm 及直径 208/127/120 mm；这是名义尺寸，不证明腐蚀/变形扫描的实长恰好相同。只用全长做等比例尺度，没有强行分别匹配直径。
- **原始产物复算**：对全部 OBJ 顶点中心化后求 PCA，奇异值降序；前两轴各自对应的对角分量取正，第三轴用叉积保证右手系。s=名义全长/PCA 长轴极差；PCA 各轴极值中点映射到 target 原点。独立协方差特征分解复算 s/R/t 最大差 7.14×10⁻¹⁵。
- **我方假设**：长轴就是 target +x；第二主轴定义 roll；target 原点是几何包围中点；公开同类静态 target 位姿适用于所取两条录音。这些不是官方 mesh 注册事实，OBJ 头尾/roll 也未得到实测认证。

包含三类变换的固定 JSON，其 SHA256 为 `31e18b860fbbb6ac489156d9d2f4f3ffa57953301e95ab35f1e9fa0bcc8722c7`。修订版直接读取并逐字节复制同一文件，不重估 PCA、不改变目标世界位姿。

## 直接投影链与范围

预登记：[初版](../../experiment/archive/sonar-fixed-mesh-plan.md)、[beam 符号候选](../../experiment/archive/sonar-fixed-mesh-beam-sign-plan.md)。18 个身份沿用 [selection.json（本地产物说明）](../../ARTIFACTS.md#artifact-d2fbf44d730b)，在允许 manifest 中逐个核对 `train/val/val_id`、ARIS 帧号与 FrameTime；没有读取 test。旧 registration_fit/holdout 只是历史角色，本轮没有拟合，也不称新的留出集。

静态链来自当前公开 calibration；逐帧用 gantry xyz 与 ARIS Roll/Tilt/Pan：

```text
R_world_from_ar3 = R_setup_ar3 · Euler_xyz(Roll, Tilt, Pan)
t_world_from_ar3 = gantry_xyz + t_setup_ar3
T_world_from_sonar = T_world_from_ar3 · T_ar3_from_aris · T_aris_from_sonar
p_sonar = inverse(T_world_from_sonar) · T_world_from_target · [sR, t] · p_mesh
r = ||p_sonar||
elevation = atan2(y, sqrt(x²+z²))
```

由每帧 `SampleStartDelay × SoundSpeed / 2` 得起始距离（时间单位转秒），`SamplePeriod × SoundSpeed / 2` 得 bin 宽，实测图高 h 给有效区间 `[r0, r0+h·dr]`。18 帧复算与 `WindowStart` 最大差 2.63×10⁻⁸ m，不能解释明显错位。用对应 PingMode 的官方非均匀 beam 表，beam 中心映射到列 `i+0.5`；原图向下距离增加。初版和候选的距离、俯仰、逐帧位姿完全相同。

采样包含全部顶点、三角形重心及三条边中点，三类分别 856136/810049/568648 个点，存在重复且不是均匀面积采样。绿色要求前向、有效距离、有效 beam 和假设 `|elevation|≤7°`；另报告 ±7.5° 的敏感性。绿色框取采样点包围并外扩 1 bin/beam，再裁到图像；无可见点时保留空框。**点数占比不是表面积可见比例；采样+padding 也不是严格的连续 mesh/FOV 交界包络证明。** 没有声学散射、遮挡或阴影预测。

18 帧每版均有 17 个非空候选、1 个空候选；6 帧有 range/beam 截断，9 帧被垂直门限移除采样点。具体距离、方位、俯仰、两种 FOV 比例及 raw/fan 框均在两版 `results.json` 和逐帧附表，不用总计掩盖空框。

## 发现并隔离了 beam 符号问题

初版使用 `beam = degrees(atan2(x,z))`。独立审核最初只证明 raw beam 表→fan 的左右显示与官方一致；**这不足以证明三维 sonar +x→beam 列的物理符号。** 随后进一步检查：

1. 官方 [view_recording.py（本地产物说明）](../../ARTIFACTS.md#artifact-f518715eec11) 第 178–180 行说明 raw beams right-to-left，并水平翻转显示。
2. [prep_2_aris_to_polar.py（本地产物说明）](../../ARTIFACTS.md#artifact-78fba5f843d4) 第 174–207 行的角度反号、`cos(angle+90)` 和最后水平翻转，使表中正角落在显示左侧；合成单 beam 脉冲复核这一点。
3. SoundMetrics [官方 SDK 说明](https://github.com/SoundMetrics/aris-file-sdk/blob/master/docs/understanding-aris-data.md#L134)明确：“beam 0 is the right-most beam, and beams are numbered from right-to-left.”
4. 公开 transforms.yaml 中当前 sonar 与 camera 的相对旋转为零。**若** sonar 使用相机 optical x 向右的轴解释，应使用 `beam = -degrees(atan2(x,z))`。仍缺已知三维点到真实 beam 的物理控制，不能把这一推断升级成无歧义的实测轴认证。target +x 的 PCA 假设是另外一层，不因反号得到认证。

因此先登记 `sonar_fixed_mesh_beam_sign`，只改这一符号。初版全部产物和失败保留。两段逐帧循环在移除 az 前的一元负号后 AST 完全一致；s/R/t 文件、全部位姿/range/elevation 与 raw/fan 原图 hash 不变。非均匀 beam 表的左右端不完全对称，因此反号会轻微改变边缘点准入；最大可见点比例差 0.00083004，已在独立复核逐帧记录，并非新增调整。

修订方向由轴证据提出；两版图都在开发帧上检查，视觉改善不是独立盲验。没有继续扫描角度、平移、尺度或其他方位公式。

## 跨帧、跨轨迹逐图 QA

执行了主 assistant 与独立 assistant 两份目视检查，逐帧分别记录距离、方位、可见性、候选框和理由。**这是 assistant 目视 QA，不冒充人工专家标注或真实框评测。** 未创建参考 GT，未计算 IoU/AP；`partial` 不代表可训练。原图与叠图并排、全高度显示，所有帧保留。

| 版本 / 复核者 | aligned | partial | misaligned | uncertain |
|---|---:|---:|---:|---:|
| 初版 / 主复核 | 0 | 5 | 11 | 2 |
| 初版 / 独立复核 | 0 | 6 | 10 | 2 |
| 反号候选 / 主复核 | 0 | 14 | 2 | 2 |
| 反号候选 / 独立复核 | 0 | 13 | 3 | 2 |

不把这些主观分级当精度提升数值。初版有 3 帧复核分歧，候选有 1 帧；两份记录和分歧原样保存在 [run-summary.json（本地产物说明）](../../ARTIFACTS.md#artifact-9d8f0f1fe563)。候选 `120912_0802` 主复核为 partial，独立复核为 misaligned，两者都不准入。

| 类别 / 录音 | 跨帧观察（反号候选） | 结论 |
|---|---|---|
| bomb / 171105 | 首末帧走向改善，但投影被压到低 beam 侧，大段连贯回波在框外；中帧距离带接近、覆盖不足 | 明确失败保留，单一符号不能解决位置差 |
| bomb / 173329 | 首末帧方向较可解释，仍漏近端或受垂直门限影响；0456 无清晰目标回波，几何空框 | partial / uncertain，不把空框认证为负样本 |
| grenade / 120653 | 首末帧方向更接近，弱回波位置与远端范围仍不确定；横向0551低beam端遗漏 | 三帧未通过完整框验收 |
| grenade / 120912 | 首帧残余偏右，中帧遗漏低beam端，末帧方向改善但主体仍偏位 | 两位复核者对末帧程度有分歧，均未准入 |
| mortar / 100927 | 首末帧走向改善；尾部/弱亮点与mesh远端边界不等同，中帧仅距离带接近 | 三帧为部分吻合 |
| mortar / 101131 | 首帧仍有位置/远端疑点，中帧横向亮弧大体覆盖；0909无可靠目标回波 | partial / uncertain，不能认证有框即有目标 |

初始无框记录曾把 bomb `173329_0456` 写成“较弱宽弧主体”，把 mortar `101131_0909` 写成右侧弱目标候选。完整原图及独立复核不足以支持这两项归属，现显式更正为 uncertain。初始记录不删除，不以其作为“有回波却被FOV裁掉”的证据。

## 软件核验与解释边界

[初版独立验证](../../DataSet/sonar_fixed_mesh/independent-verification.json)从原始 YAML、手写 quaternion / Rz·Ry·Rx、解析刚体逆、全采样点齐次坐标和独立插值重放 18 帧，保存数值分量最大差 6.25×10⁻¹³；[候选独立验证](../../DataSet/sonar_fixed_mesh_beam_sign/independent-verification.json)最大差 2.27×10⁻¹³。这里包含矩阵、m、度、像素等不同字段，不能统称空间误差。它说明实现重放自洽，不认证实测标定或同步。

本地 fan 图使用 200 px/m 和最近邻重采样，与官方 polar2 的 h+1 canvas、角度半宽、像素中心/最后 flip 的约 1 px 约定、polygon rasterizer 不同。因此 **raw 候选框只对应本轮原始距离×beam 图；fan 候选框只对应本轮 fan 图**，不能互换或套在官方导出图上。本轮没有扩展到训练图坐标。

当前证据支持：初版直接将 atan2 当 beam 表角存在坐标约定疑点，反号候选改善多帧方向。它**不能**证明剩余误差只来自 mesh，不能证明同步/gantry/外参已实测准确，也不能用 camera 失败替 sonar 作否定判断。最需要区分的剩余量是：target 原点与头尾/roll 的真实对应、各录音 target 是否同位、三维轴到 beam 的物理符号、sonar 实测姿态/同步与声束可见性。仅放宽 FOV 或逐帧平移不能解决这些证据缺口。

## 交付与复现

- 生成器：[初版](../../tools/project_fixed_mesh_to_sonar.py)、[反号候选](../../tools/project_fixed_mesh_beam_sign.py)。已存在结果时拒绝覆盖，不应为浏览再运行。
- 核验器：[初版](../../tools/verify_sonar_fixed_mesh.py)、[候选](../../tools/verify_sonar_fixed_mesh_beam_sign.py)。独立 verifier 的一次 PingMode fallback 修正有记录，未影响18帧结果。
- 展示生成：[build_sonar_fixed_mesh_review.py](../../tools/build_sonar_fixed_mesh_review.py)只读取已保存数值及QA，生成浏览页、候选CSV、汇总、数值附表；不调用投影或拟合。
- 两版 `results.json` 的 awaiting-QA 文本属于生成时状态，保持原字节；最终完成状态由 `run-summary.json` 记录。
- 原始输入、冻结变换、两版图片与QA证据已核对 hash；原研究 Git HEAD 为 `4fadd06829c6c738977639a55b6e44ad0e35ac44` 且 clean。最终文件/链接检查见 [delivery-verification.json（本地产物说明）](../../ARTIFACTS.md#artifact-c28863b1ddfb)。

本轮已完成用户要求的固定假设、直接投影及跨帧/跨轨迹检查，并保留了失败与修订。正式 GT 准入为 0；原注册、原 GT、划分和源数据保留，无训练和 test 访问。下一轮如改变全局 mesh 注册或 target 位姿，应另立有依据的版本并保留这两版，不能将逐帧追踪回波的结果写作物理投影真值。
