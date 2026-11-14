# 普通 bomb 短序列独立观察

2026-11-12。预登记：`experiment/sonar-bomb-sequence-observation-plan.md`。新工具：`tools/prepare_bomb_sequence_observations.py`、`tools/freeze_bomb_sequence_observations.py`。

本轮仅使用普通 bomb 开发录音 `2023-09-20_171105` 的 11 个允许 native 身份，未读取检查录音 173329、旧候选框、新拟合或 test。既有三个中心帧曾在前期开发中查看，因此不是盲验。观察是助手目视判断，不是专家真值。

## 已冻结的观察

[observations.json（本地产物说明）](../../ARTIFACTS.md#artifact-a53d48088fcd) 的 SHA256 为 `3c4ef2bec5bd216880f778a54fd18bdb2ec2f3c880174e9cc023b442317df257`。

- 622/626/630：斜向相干本体回波在相邻帧稳定；小 raw 列处的远距离细尾较弱，不能确认是完整物理端点。
- 973/977/981/985/989：主回波横贯几乎全 beam 宽，右侧到达 FOV 边界，左侧接近画幅且信号较弱。**不能把画幅左右边缘当模型头尾**。更远距离的分离亮斑不纳入主回波框，未强断言其物理归属。
- 1328/1332/1336：近距离圆弧和弯曲渐弱的远距离段持续；弱尾端范围给宽区间，未认证完整轮廓。

每帧提供 `visible_echo_bbox_raw_xyxy_edge`，只包围可见相干回波候选范围；它不是训练 GT，也不等于完整物理模型的声呐包围框。逐帧的边界不确定性、可能视场截断、弱信号区域均另存。

三个中心帧分别提供 12、14、11 个近侧主回波采样区间，共 37 个。`near_echo_curve_points` 与 `points` 字段是同一组数据，包含：

- 原生 raw 像素 edge 坐标和观察容差；实际图高 **780**、宽 **128**，不是旧的 441 行常数。
- `near_range_bin_interval`：目视的近侧相干回波区间，而不是自动选全图最亮点。
- `range_m`/`range_interval_m`、`beam_table_angle_deg`/`beam_interval_deg`：由该帧公开 metadata 和官方 beam 表换算，不改变物理方位假设。

将这些曲线视为“最近网格表面”是后续求解器的声学近似，不是本轮已验证的事实。没有逐点 mesh 对应，不把亮脊当长轴；暗区/弱后方散射不生成排除约束。完整物理边界和头尾身份均保留 unknown。

## 图像与追溯

[浏览页（本地产物说明）](../../ARTIFACTS.md#artifact-ea119bac3740)提供三组完整 polar2/contact sheet、中心观察标记、11 个独立 raw/SD/polar2 文件。每帧 raw-review 含原始强度及固定 gain=3，所有 780 行都保留。相机仅确认本体/支架语义，不读取相机标签或作标定投影。

polar2 来自已验证的官方源码兼容渲染器，1000 px/m；不是声称找到了原发布 polar 文件。图像前后源 SHA256、对应 FrameTime、记录身份见 [source-provenance.json（本地产物说明）](../../ARTIFACTS.md#artifact-e3052cdbc47c)，最终 [delivery-verification.json（本地产物说明）](../../ARTIFACTS.md#artifact-8050cd664963) 复核全部 29 个输入 hash 不变。

计划共 15 身份，614/618/1340/1344 不在允许 native 清单，未读取；实际 11 帧全部在允许清单。首次 raw contact 的固定画布未容纳完整 780 行，个人 raw-review 和源图始终完整；旧 contact 保留，改用 `window-*-raw-full-contact.png`，更正见 [display-revision.json（本地产物说明）](../../ARTIFACTS.md#artifact-83190a84e520)。此为显示版式修订，不改观察数据或原图。

本轮没有运行注册/训练、修改服务或正式审阅状态，也没有写训练 GT。冻结后不依据新投影反改这些观察；必要修订必须另存版本并解释来源。
