# camera_recording_baseline

2026-11-13。用户要求开始camera-only teacher baseline，按[预登记](../../experiment/archive/camera-recording-baseline-plan.md)执行。训练状态以[status.json](train/status.json)及[日志（本地产物说明）](../../ARTIFACTS.md#artifact-23682527417f)为准，不能将启动记作完成。

- 数据：[train/val准入核验](../../DataSet/camera_recording_baseline/verification.json)，1800/600张；无test内容读取、无备用。使用原640×360 SD框，不乘3、不clip；当前交付标签，非专家GT声明保持。
- 模型：原研究只读的t_camera_s_yoloxs，camera YOLOX-S；workflow本地适配数据加载，不加载声呐图像。类别内部顺序bomb/grenade/mortar，按名称转换，与交付YOLO顺序不同已显式登记；COCO类别1/2/3。
- 起点：官方COCO缓存hash4592a793b95f18f62fd73fbb6cfe61dd445f71a8e072366e114e7134d4492760，仅backbone/neck；head随机。预检逐张量匹配通过，无旧UXO权重。
- 配方：200epoch、batch8、seed0、45000iter，FP32；SGD与历史scheduler/EMA，详见[resolved_config.py](train/resolved_config.py)。无图像增广，实际camera输入8×3×384×640，padding114。
- [预检结果](preflight/status.json)：真实batch前后向、相机梯度、声呐无梯度、CUDA推理通过；[六图几何抽查（本地产物说明）](../../ARTIFACTS.md#artifact-018858fc0f5e)已实际查看，2400张全部解码/哈希/坐标检查通过。
- 训练完成后脚本自动加载epoch200的raw state_dict，在val保存pooled、逐类、逐录音COCO AP/AR和预测，EMA不混报。不是best-val。test不评价。
- 运行环境：WSL Ubuntu22.04，RTX5060Ti16GB、torch2.7.1+cu128/mmcv2.1.0/mmdet3.3.0/mmengine0.10.7。复用既有GPU环境，原项目与包未修改；版本与依赖保存在train/。NMS沿用已有CPU fallback，GPU训练正常。
- 源码：[数据准备](../../tools/prepare_camera_baseline.py)、[数据适配与评测](../../tools/camera_baseline_runtime.py)、[训练入口](../../tools/run_camera_recording_baseline.py)、[启动脚本](../../tools/launch_camera_baseline.sh)。不重复启动已有run，不在失败后自动改配方。

注意：首次通过内联WSL后台命令尝试启动未产生进程/日志，改用保存的shell启动器成功；没有由此改变训练配置。尚无模型结果，历史开发使用与split来源组限制继续有效。
