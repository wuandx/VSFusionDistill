# 5090 camera YOLOX-M部署

已部署并启动，尚未完成训练。远端根`/root/wzl/weak_coverage_camera_m_teacher`。

- [完整部署报告](../../复现/camera-baseline/weak-coverage-camera-m-5090-deployment.md)
- [包核验](verification.json)、[逐文件hash（本地产物说明）](../../ARTIFACTS.md#artifact-3ed5ac9ba84a)
- [独立启动核验](startup-verification.json)、[任务快照（本地产物说明）](../../ARTIFACTS.md#artifact-b14b9548765a)
- [本地停止后远端继续训练快照（本地产物说明）](../../ARTIFACTS.md#artifact-fb245a689071)
- [本地停止记录](../../runs/weak_coverage_camera_m_teacher/migration-to5090.json)

4711相机图，仅4138train/573val；不含sonar/test图。tar包与旧启动快照保留，不重跑覆盖。18:09远端epoch2/200步，约0.196秒/步，预计总约6h；后续进度读远端日志。
