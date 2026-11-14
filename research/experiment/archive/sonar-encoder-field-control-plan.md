# sonar_encoder_field_control：姿态字段单因素诊断

2026-11-12。来源审计发现五录音PanAbsPosition−SonarPan中位1.16–1.33°，个别达6.28°。SoundMetrics官方FrameHeader.h将AbsPosition定义为low-resolution magnetic encoder，将SonarPan称X2 pan output；不支持直接将前者当更精确真值。两种字段均保存于同帧。

唯一改动：使用SonarRoll/Tilt/Pan构造AR3的姿态替换为Roll/Tilt/PanAbsPosition，其他固定，尤其不重新拟合模型、不改时钟。对上一轮完整轨迹冻结模型505身份，输出原投影和编码器投影框、中心差、IoU；每录音前中后分开。该实验隔离字段差异对现有残差的影响，不认证物理姿态。

若稳定改善才考虑另登记重拟合；若不稳定则保留字段差异为不确定来源，不使用该替换。停止于全部505帧与每条录音首中末对照，不能逐帧选用字段。
