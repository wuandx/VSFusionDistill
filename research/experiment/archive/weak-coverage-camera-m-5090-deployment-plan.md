# weak_coverage_camera_m_teacher：5090部署

用户授权部署到192.168.10.100的WSL wzl目录。目的为缩短已冻结camera-only YOLOX-M训练时间。

保持4138 train/573 val、4711相机图、seed0/batch8/200epoch/103600更新、无增广、COCO-M初始化、固定epoch200实际raw与val协议。唯一计划变动为执行主机和存储路径；记录实际GPU、依赖与源代码hash，浮点与硬件差异需披露。不上传test或sonar，不运行KD。

在/root/wzl/weak_coverage_camera_m_teacher中使用独立源快照和数据包；保留旧远端工作。远端从fresh COCO开始，本地已运行早期epoch保留为停止的尝试，不能混合两次日志或声称跨主机精确续训。远端真实预检及优化迭代健康后停止本任务的本地服务。

对照为本地同名冻结实验。准入标准：传输包/hash匹配，全部图像及框/组互斥核验，源与初始化hash相同，实际batch8和末batch2 GPU前后向、推理、几何及raw/EMA身份通过；正式训练输入/实现/源/配置语义与远端预检一致，真实迭代loss有限。

停止条件：hash/数据/依赖/预检失败或非有限loss即停止，保留失败目录；不自动调整batch/学习率/数据。训练仅val每10epoch，固定200epoch raw主结果，EMA单列，不访问test。启动后测量实际速度更新ETA。远端进程持久运行且不自动重启失败任务。
