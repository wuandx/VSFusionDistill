# 已确认配对划分的camera-only YOLOX-M教师训练

2026-11-14。用户明确“确定好数据集就开始训练吧先只训练教师模型的相机，yoloxm”，并调用research-workflow。这授权本次确认并冻结刚交付的paired_weak_scene_coverage_pan_split、预检和正式单相机训练；更新旧阶段的仅审计/尚需训练授权状态。只启动camera-only teacher，不启动sonar或蒸馏，不恢复旧camera-only扩充队列。

实验名：weak_coverage_camera_m_teacher。目的：在覆盖优先的已接受配对数据上训练可审计的camera teacher。唯一相对上次camera-M基线的预期研究改动是训练与验证数据版本；模型、初始化来源、种子、图像几何、优化器与按epoch配方保持。旧2472/894与本次4138/573成员和迭代总数不同，不能将新旧AP差全部归因覆盖收益。

冻结输入：DataSet/paired_weak_scene_coverage_pan_split/，5229对、42录音35保守组；train4138/33录音27组，val573/5录音5组。7未决不进入；test518/4录音3组不复制、不装载、不评价，本轮不读取其图像或COCO。只从已确认manifest过滤相机train/val，单独生成独立图像副本、dataset/COCO和血缘/hash/成员清单。原始研究目录只读，10原研究test关闭。保留助手标注与原标签区别，不提升专家GT/精密同步认证。

配方：YOLOX-M camera分支deepen=.67/widen=.75、PAFPN 192channels/2blocks、3类别head随机；使用现有assets/checkpoints/yolox_m_coco_backbone_neck.pth的COCO backbone/neck，严格全张量核验；不从任何UXO旧checkpoint或optimizer续训。类别顺序bomb/mortar/grenade（实际类名沿用原项目），seed0、batch8、200epoch、每epoch完整4138样本（最后batch2），ceil(4138/8)=518更新/epoch、总103600更新。保留原SGD lr.00125、momentum.9/nesterov、wd.0005、clip35、5epoch warmup与原cosine/constant安排、EMAHook。

预处理沿用上次：原SD640×360、keep_ratio fixed640、右底pad114到640×640、BGR0–255，无增广（不恢复此前augmentation队列），无相机/声呐双支输入。现有实现为单相机监督，未使用的sonar backbone由模型接口要求保留但无输入/头/梯度，不作为sonar训练。无test loader。

测量与主权重：每10epoch监测val actual raw；主结果固定epoch200实际raw，对照EMA单独导出不混报。score.01/NMS.65/maxDets100，报告pooled/每类AP与AR1、完整COCO AP50/AP75/AR10/100和逐录音；不按中间val峰值或EMA换主权重。新split受旧val/test诊断启发，属于开发协议；val只有5组、无floor ellipse及两种bomb flyby，test不进入训练流程，新成绩不称外部盲测。

启动判定：冻结输入/hash和4711相机图解码/框/类别/角色/组互斥，训练身份与上游一致；COCO初始化严格相同；真实GPU batch8前后向有限、类别/逆几何一致、仅相机输入、raw/EMA checkpoint往返，以及最后batch2 loss/梯度有限。功能预检只作控制不报AP。使用持久WSL user service、独立runs/weak_coverage_camera_m_teacher/，不覆盖旧run，automatic restart=no。必须看到真实optimizer迭代日志后才能登记training_started，配置/预检不等于训练。

停止条件：hash/成员/类别不符、非有限loss/梯度、OOM、权重身份不明即失败停止，保留日志，不偷偷改batch或数据、不自动重启。训练正常启动后可后台持续；后续用户查进度读本run真实status/log，主结果完成前不宣称收敛或改善。
