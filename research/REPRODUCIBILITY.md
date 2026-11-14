# 复现输入与运行边界

本次发布是研究记录与脚本快照，不是已经验证的一键训练发行版。模型代码来自原工作区commit `4fadd06829c6c738977639a55b6e44ad0e35ac44`；原目录保持原位。

## 已提供

- `../aodet/`、`../configs/`与原训练/评测代码及其Git历史。
- `tools/`中的workflow处理、训练、评价、核验脚本与相关runtime；脚本原文保留，不在发布过程中执行。
- 当前5229对划分的train/val/test身份列表、录音/保守来源组表、协议、核验与完整manifest压缩副本。
- 当前相机train/val的COCO、dataset与成员/文件hash记录；这些JSON不包含图像文件。
- 已完成开发baseline的结果JSON、逐类/逐录音表、权重身份记录；最新run的冻结、配置与启动证据。

## 仍需准备

原始UXO图像/视频可从[官方来源](https://zenodo.org/records/13778485)取得。我方筛选后的配对图像、助手补标及图像恢复结果仍在本地workflow；仓库没有提供其独立下载地址。仅下载原始UXO不能自动得到我方完整训练输入。

完整manifest位于`DataSet/paired_weak_scene_coverage_pan_split/manifest.json.gz`，解压后SHA256应为`744aff50c0a6d69b4e79003c78262df9c2f1100ee438380cc71f44cc22ba26a5`。相机train/val图像需与`DataSet/camera_weak_coverage_trainval/files-sha256.json`核对。COCO-M初始化权重不随Git发布，身份见冻结与部署记录。

最新部署记录的环境为Python对应远端环境、Torch2.7.1+cu128、torchvision0.22.1+cu128、MMCV2.1.0、MMEngine0.10.7、MMDetection3.3.0、NumPy1.26.4、pycocotools2.0.11、Pillow12.3.0。以[启动核验](DataSet/weak_coverage_camera_m_5090_deployment/startup-verification.json)和[部署报告](复现/camera-baseline/weak-coverage-camera-m-5090-deployment.md)为证据；旧`../env/`属于原代码环境，不能把两者混为同一环境。

## 路径与执行

导入脚本通常以`research/`为ROOT，部分历史脚本含Windows、WSL或远端绝对路径。运行前必须逐项准备数据、核对输入hash并调整部署路径；发布时没有验证跨机器可移植性。部分脚本使用`--repo`、`--checkpoint`等参数，需显式指向对应代码与初始化权重。

有数据导出或服务启动作用的脚本不得仅为阅读仓库而执行；部分产物有防覆盖约束。最新教师任务已有启动记录，发布操作不应重复注册、重启或生成新run。本仓库没有新增训练授权。

actual raw与EMA按实际checkpoint结构区分，不能按目录名推定。旧val/test开发使用史、模态GT区别、数据版本和单seed边界见[测评协议](experiment/evaluation.md)。
