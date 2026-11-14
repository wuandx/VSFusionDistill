# AMHS工作站两项baseline部署

2026-11-13。用户明确授权在192.168.10.100运行sonar-only YOLOX-S与固定640×640 camera YOLOX-S。[事前规则](../../experiment/archive/workstation-baselines-plan.md)。

## 位置与连接

SSH经本地WSL：`ssh -p 22 -i /home/ty/.ssh/id_5090 -o IdentitiesOnly=yes Administrator@192.168.10.100`，然后使用工作站`wsl -d Ubuntu-22.04 -u root -e bash`。Windows原ssh config的git/2222是Git服务，不是工作站shell；root直连22未通过，不修改用户ssh配置。

数据实际位于`/root/wzl/dataset/paired_recording_trainval`；独立代码快照、脚本、结果位于`/root/wzl/workflow_baselines`。未覆盖`/root/wzl/VSFusionDistill`及既有结果。

| 实验 | 远端训练日志 | 远端输出 |
|---|---|---|
| camera_s_fixed640 | `/root/wzl/workflow_baselines/runs/camera-train.log` | `/root/wzl/workflow_baselines/runs/camera_s_fixed640/train` |
| sonar_s，无蒸馏 | `/root/wzl/workflow_baselines/runs/sonar-train.log` | `/root/wzl/workflow_baselines/runs/sonar_s/train` |

启动PID为camera952/sonar953，后续应结合命令行与日志确认，不能仅凭PID判断。状态在各输出的status.json，完成后自动只评val并保存预测、pooled/逐类/逐录音完整COCO AP/AR。当前启动不是完成。

## 数据和配方

冻结split的1800train/600val，每类600/200，test与备用均未上传。4800张双端图像及原相机JSON/声呐YOLO标签、分模态COCO与加载清单保留；原类名按名称转换为模型bomb/grenade/mortar。声呐COCO从交付YOLO重建到原像素，精度1e-6，不用旧blob/projected；图片不翻转、不改增益。

两项200epoch、batch8、seed0、45000iter、FP32，与本地S相同COCO S backbone/neck起点（hash4592a793…）、随机head、SGD/scheduler/EMA/无增广。camera保持640×360，右底补114到640×640；sonar原raw三通道，等比例缩放到640范围后右底补114。补边在打包后实施，保留未补边img_shape及真实scale_factor，camera scale仍1。远端CUDA环境版本与本地一致，GPU为RTX5090D v2；硬件差异与浮点非确定性仍需披露。

[本地全量核验与包hash](verification.json)、[远端核验（本地产物说明）](../../ARTIFACTS.md#artifact-94974c270e36)、[源代码逐文件hash（本地产物说明）](../../ARTIFACTS.md#artifact-de2166c6e43d)、[camera预检（本地产物说明）](../../ARTIFACTS.md#artifact-3926a5cc9e33)、[sonar预检（本地产物说明）](../../ARTIFACTS.md#artifact-9757dc784711)。远端9609文件hash、4800图解码、角色/来源组互斥、原框范围、源快照hash均通过；真实batch8 CUDA前后向、逐张量COCO加载、推理、640画布及camera scale1通过。

14:20日志两项均到epoch1第100/225步，有限loss，预计约3h；总显存约12GB。后续以最新日志为准。

## EMA口径更正

本轮直接核对mmengine0.10.7 EMAHook.before_save_checkpoint/_swap_ema_state_dict：启用该hook时，checkpoint.state_dict实际保存EMA，原始参数在ema_state_dict的module.*。先前本地S/M文档及脚本把state_dict称raw有误，此处公开更正，不静默覆盖历史。训练本身不受影响；远端脚本已从实际raw字段提取raw_epoch_200.pth并评价。**本地S/M当前运行脚本结束后自动产生的val_raw_epoch200名称不证明raw，其加载的是EMA，必须标作EMA并另行以真正raw评价后再和这两项比较。**该本地补评尚未执行，不冒称已修复。

## 保留的准备失败

最初root直连SSH未通过，按既有远端脚本找到Administrator→WSL路径；探针一度受CRLF影响，写LF后通过。数据打包期间脚本生成遇GBK读取失败，改显式UTF8后生成，最终包及远端代码均通过hash/语法/真实预检。上述失败均未发起错误配置训练。

源码：[打包](../../tools/package_workstation_baselines.py)、[训练](../../tools/run_workstation_baseline.py)、[固定画布](../../tools/workstation_baseline_runtime.py)、[远端核验](../../tools/verify_workstation_package.py)、[启动](../../tools/launch_workstation_baselines.sh)、[状态探针](../../tools/status_workstation_baselines.sh)。不重复运行bootstrap或launch以免覆盖当前run；不自动变更batch/seed/输入或重洗split。
