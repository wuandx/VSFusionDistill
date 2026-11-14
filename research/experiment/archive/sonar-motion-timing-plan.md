# sonar_motion_timing：独立运动记录与论文边界

2026-11-12。目的：区分源时间对应问题与mesh/回波对应问题，并对齐CMHD§3.1公开流程。

- 固定六条既有开发录音171105/173329、120653/120912、100927/101131；只读取其processed ARIS元数据/marks/flow和gantry CSV，matches/gantry_metadata只读取录音级映射。不得读取test图像/标签。
- 不改变参数、不拟合目标回波。比较match的gantry_offset与原gantry首运动时刻；同时复算官方dx+dy判据和独立XY向量运动判据，检查抵消、零运动、单位、插值外推、时间跳变。检查允许录音的ARIS marks与matches onset一致性。
- 对原gantry轨迹拟合水平圆仅用于描述运动中心/半径及计算相位，不更新target；将源pan对准轨迹中心的角度与实际记录对照，偏差非零不自动当yaw校准错误（手动跟踪目标）。
- 判定：来源时间字段相同只认证文件/公式一致；需要跨传感器独立运动证据才能认证物理同步。若仅gantry运动起点与match相同，不声称已排除时偏。
- 保存CMHD原始JATS§3.1与论文/我方假设对照；UXO最终PDF取得失败就如实保留，不把摘要/README当全文。
- 输出报告、JSON、源hash；不改GT/标定/生产页/split，不训练。
