# camera-only YOLOX-M教师：5090部署与启动证据

用户授权部署到192.168.10.100的WSL wzl目录。按[部署计划](../../experiment/archive/weak-coverage-camera-m-5090-deployment-plan.md)，已于2026-11-14部署并真实训练；本报告仅记录启动，不代表完成或新AP。

## 实际位置与运行

- 主机：192.168.10.100，Windows Administrator SSH 22，再进入Ubuntu-22.04 root。Windows ssh config的git/2222是另一个服务，未修改配置或密钥。
- 根目录：`/root/wzl/weak_coverage_camera_m_teacher`；独立source快照、DataSet、assets与runs，旧远端目录保持。
- 正式日志：`/root/wzl/weak_coverage_camera_m_teacher/runs/weak_coverage_camera_m_teacher/train.log`。
- 模型/状态：上述runs目录的`train/`与`train/status.json`；预检在`preflight/`，启动状态在`remote-launch-status.json`。
- Python：`/root/pby/code/VSFusionDistill/.venv-gpu/bin/python`；GPU实际为RTX5090D v2、24455MiB。
- Windows一次性任务`WeakCoverageCameraMTeacher`（Administrator/S4U），前台托管WSL训练，24h上限、RestartCount=0、无周期触发。断开并重新建立SSH后多次观察进度继续，非依赖本地终端。

## 冻结与核验

只传相机4138train/573val，共4711张；数据/框/角色/来源组/初始化/实现保持。COCO-M fresh backbone/neck、随机三类head，seed0/batch8/200epoch/103600更新、FP32/无增广、原优化器及schedule。固定epoch200 actual raw为主结果，每10epoch仅val监测，EMA另存；不以best替换。

包211896320字节，SHA256 `88fb2462ef1cebc29c2f869659327635f3b3801aa41e2b39bded8d032fa6bc2d`；远端9525文件逐hash通过。全部4711图像解码、框/COCO/身份、组互斥在远端runner复核。GPU batch8和末batch2前后向、推理、逆几何及live raw/EMA保存身份均通过。预检loss92.7346、末batch2loss92.7403，几何最大误差0，梯度有限。这些是预检值，不是训练成绩。

源、实现、数据、冻结和COCO初始化hash与本地一致；远端预检与正式训练六组hash相同。跨主机绝对路径改变，故配置hash本身不要求跨主机相等；独立比较归一化路径后的模型、优化器、schedule、数据加载、hooks等15字段均相同。[启动核验](../../DataSet/weak_coverage_camera_m_5090_deployment/startup-verification.json)。Torch2.7.1+cu128、torchvision0.22.1+cu128、MMCV2.1.0、MMEngine0.10.7、MMDet3.3.0、NumPy1.26.4、pycocotools2.0.11、Pillow12.3.0版本相同；GPU/存储不同仍可能产生浮点差异。

## 进度、预计用时与本地处置

18:09:53的远端真实日志为epoch2的200/518，loss5.8408且有限，约0.196秒/步、框架剩余ETA5:37:26。结合val和保存开销，启动阶段估计总约6小时，预计11月14日23:50至11月15日00:30完成；后续以实际日志为准。此前未经实测的3–5小时估计偏乐观，现以本次测量更正。训练显存nvidia-smi约9.0GB。

远端从COCO重新开始，不是接续本地epoch。确认远端epoch1迭代440、各项核验及SSH独立性后，18:09:31停止本地`weak-coverage-camera-m-teacher.service`，确认为inactive/dead、MainPID0。最后本地epoch7的340/518；没有到首个epoch10保存点，未生成完整epoch checkpoint。原日志、预检、配置和状态历史保留，[迁移记录](../../runs/weak_coverage_camera_m_teacher/migration-to5090.json)保存停止前状态与进度。两次运行日志不可拼接，本地状态标记stopped_deployed_to5090。

## 失败留痕与边界

首次nohup/setsid后台启动随SSH会话退出，未生成预检或正式训练目录/优化迭代；保留空service.log与launcher.pid，改用上述一次性任务后才完成实际启动。远端WSL systemd bus不可用，未重启WSL或改动全局系统设置。核验脚本曾因Config自动导入路径、pip freeze的MMCV直接wheel表示失败，修正为无自定义导入的配置读取及installed metadata版本比较后通过；未改变正式训练代码/数据/配方。

本次未上传test/sonar图像，未启动声呐/KD或test推理。开发重划分与旧val/test使用历史、393助手相机标注、来源数及场景缺留出的限制保持；启动证据不证明泛化改善。

证据入口：[部署包与远端快照](../../DataSet/weak_coverage_camera_m_5090_deployment/README.md)。连接/状态工具：tools/remote_weak_teacher.py、status_weak_teacher_5090.sh、status_weak_teacher_5090_task.ps1。不要重复执行打包/部署/注册/launch，以免触发明确的防覆盖拒绝。
