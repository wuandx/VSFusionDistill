# 新版两项baseline并行正式训练

2026-11-13。用户明确“可以没问题就开始跑吧两个可以同时跑”，授权正式启动scene_camera_m_baseline与scene_sonar_s_baseline，覆盖前述仅准备/预检限制。

目的：执行已经预登记并通过预检的camera-only YOLOX-M与sonar-only YOLOX-S两项baseline。不新增配方变量；同2472train/894val、各模态原图原框、keep_ratio fixed640、200epoch/batch8/seed0、无增广、COCO backbone/neck起点、epoch200真实raw主结果与EMA另列。每项309step/epoch，共61800更新，test不进入训练或评测。

并行只改变资源调度，不用于模型效率比较。启动前检查预检状态/实现和数据hash、空闲显存及目标run目录不存在；两进程均使用显式--train。使用WSL用户服务托管并记录独立日志及服务状态，避免工具调用结束导致训练随父shell退出。

判定：两项均实际进入训练循环，至少完成若干有日志的optimizer iteration，loss与梯度有限，显存可承载并行；持续状态与checkpoint可追溯。不能只凭launcher返回PID声称训练已成功启动。

停止条件：OOM、非有限loss、数据/权重/源码hash不匹配或其他运行时异常时保留日志与状态并停止该run，不自动改batch/输入/学习率，不终止其他既有任务。无错误时按既定200epoch执行；无新test授权。
