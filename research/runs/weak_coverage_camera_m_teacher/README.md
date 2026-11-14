> 运行位置更正：本地尝试已停止并迁移至5090。此处保留本地记录，最新位置见[部署报告](../../复现/camera-baseline/weak-coverage-camera-m-5090-deployment.md)。本次发布未实时查询远端训练。

# camera-only YOLOX-M教师：weak_coverage_camera_m_teacher

用户已确认并授权使用paired_weak_scene_coverage_pan_split。冻结camera4138 train/573 val，33/5录音27/5保守组；仅camera图像载入。数据副本：DataSet/camera_weak_coverage_trainval/。冻结详情dataset-freeze.json；训练前真实GPU预检和正式迭代证据startup-verification.json。

COCO-M backbone/neck fresh初始化，随机3类head；200epoch、batch8、seed0，无增广，SD640×360 keep_ratio+右底pad114到640。每epoch518更新（末batch2），共103600更新。SGD/LR/epoch schedule沿用前camera-M；与旧2472/894同时改变数据与更新总量，不作单因素收益结论。

主结果epoch200 actual raw，EMA另存。每10epoch raw val监测，最终val包含pooled/逐类/逐录音；未按best或EMA换主权重。test不复制/载入/评价，不启动sonar。旧val/test使用史保持，新val只有5组且3种场景无val，不称外部盲测。

服务weak-coverage-camera-m-teacher.service，WSL user systemd，Restart=no。launch-status.json是队列阶段；train/status.json是模型阶段，train.log与train/下MMEngine日志反映真实进度。状态configured、preflight_passed或training初始化不是完成，查看实际Epoch(train)迭代。失败保留日志且不自动改配方重启；完成后train/raw_epoch_200.pth、ema_epoch_200.pth和val_actual_raw_epoch200/。
