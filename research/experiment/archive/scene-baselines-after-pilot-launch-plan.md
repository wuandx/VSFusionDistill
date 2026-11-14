# 短跑诊断后重新启动两项200epoch baseline

2026-11-14。用户明确“训练吧按照之前的两轮同时开”，授权恢复原定两项camera-M/sonar-S并行正式实验；这里“两轮”指两项run，预算沿用此前200epoch，而非改成2epoch。

沿用固定2472train/894val、batch8/seed0、无增广、keep_ratio fixed640、原优化器与200epoch LR配方、每项61800更新，epoch200 actual raw主结果/EMA另列、每10epoch验证保存；test仍不使用。两项从同一已核验COCO起点fresh train；相机10epoch pilot保留为独立诊断，不将其权重当成新的COCO起点。

本次只改变运行状态和输出目录；旧停止run及pilot完全保留，不移动或覆盖。新目录为各baseline下after_pilot/train及独立train.log，用户服务名加after-pilot。同源码/初始化/数据hash不变时沿用此前已完成的真实GPU预检证明，原status文件原样复制至新attempt的preflight，另记来源路径/hash，不能称新执行了一次预检。

判定：启动前两个服务均inactive、显存可用、预检证明与当前数据/初始化/实现/源码hash匹配；启动后两个新run均实际产出有限loss/梯度的optimizer iteration日志，并行显存可承载。只返回PID不算成功。

停止条件沿用原方案：OOM/非有限loss/数据或权重检查错误则保留失败停止该run，不自动改batch/几何/成员，不干预无关进程。原两停止run不重启，短跑不重启；只启动两个新attempt，不创建自动化任务。
