# sonar_fixed_mesh：固定模型直接声呐投影试点

2026-11-11。用户明确授权：每类固定mesh→target假设，经gantry/ARIS姿态和sonar外参直接投影，跨帧/跨轨迹人工QA；不逐帧移动模型。research-workflow；原仓/数据只读，test关闭，不训练。

- 固定18身份：沿用sonar_independent_registration/selection.json的3类各2开发录音首中末。全部核对允许manifest的train/val/val_id。原有fit/holdout仅记历史角色，本轮不拟合参数。
- 每类唯一假设：OBJ顶点PCA长轴→target +x，第二轴→+y、第三轴→+z；轴号按奇异值降序，第一/第二轴各自与OBJ同序坐标正向点积为正，第三轴取叉积保证右手。尺度为历史名义全长737/442/580mm除PCA长轴极差；各PCA极值中点→target原点（不是重心）。旋转/原点/roll为我方约定，不是已知官方注册；名义长度与腐蚀扫描实长也可能不同。保存完整s/R/t/4×4矩阵、extent、来源/hash。模型冻结后不据回波修改本轮参数。
- 唯一变动：绕开camera拟合，按此固定几何直接走sonar链。对照为各帧无框原sonar与投影叠图；不混用旧blob/projected框或先前相机拟合矩阵，不优化echo。
- 位姿：当前公开静态target姿态，ARIS Roll/Tilt/Pan按官方xyz度序、gantry xyz与setup/ar3静态位移组合，接AR3→ARIS→sonar；保存每帧world/sonar矩阵。源索引/FrameTime/hash复核。公式数值控制不等于实测标定通过。
- 成像：读取每帧SamplesPerBeam/PingMode，SDK来源非均匀beam表；距离起点采用SampleStartDelay×SoundSpeed/2，与公开polar2一致，另报WindowStart差；bin宽SamplePeriod×SoundSpeed/2。列为beam表正序、行随range增加。同时显示全高range×beam原图和明确坐标的扇形重采样（beam正向在扇形左侧，与官方最终flip一致），不混同两种框。
- mesh表面采样含所有顶点/三角形重心/边中点；计算全表面范围，另计算前向且在实测range/beam范围、假设±7°垂直视场内的样本范围（±7°仍未认证，额外±7.5°仅敏感性）。无声学散射/遮挡/阴影建模。框为采样几何包围并外扩1bin/1beam的候选，明确不是精确声学mask或正式GT。无可见样本为空，不生成假框；图像裁剪与FOV截断分别记录。
- QA：先看18帧无投影图并登记主要目标回波候选范围/不确定性，再看叠图，逐帧给aligned/partial/misaligned/uncertain及原因。assistant目视QA不是专家GT，回波可能混含支架/阴影；不用其修改本轮模型。每录音3帧以及同类第二轨迹全部保留，失败不换样。逐类汇总，不把视觉通过当metric注册认证。
- 判定：无非有限值/源变动/非法身份，矩阵/坐标独立复算通过；几何可见性与目视回波不相容则本固定假设未通过。部分看起来吻合不准替其他帧签字。下一版若改全局注册，另立名字和理由，旧假设/投影/QA保留。
- 停止：上述完整性失败即停对应分支；本轮最多这一套三类固定假设，不逐帧调参、不自动扩大样本、不写正式训练标签。
