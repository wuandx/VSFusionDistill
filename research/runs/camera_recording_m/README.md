# camera_recording_m：YOLOX-M camera-only teacher

2026-11-13。按用户要求与S并行训练；[预登记](../../experiment/archive/camera-recording-m-plan.md)。运行状态见[status](train/status.json)和[日志（本地产物说明）](../../ARTIFACTS.md#artifact-b08307b8496c)。

保持S的数据/配方/预算：1800train、600val、原SD640×360→pad640×384，200epoch、batch8、seed0、FP32、SGD和原scheduler/EMA、无增广，最终epoch200 raw权重仅val评价，完整pooled/逐类/逐录音COCO AP与AR。不加载sonar图、不读test、备用不使用。M为depth.67/width.75、neck192与CSP2；原S进程/脚本未改。

M使用[作者官方COCO权重](https://github.com/Megvii-BaseDetection/YOLOX#benchmark)转换backbone/neck，head随机；S使用MMDetection COCO S，**预训练来源不同，不能把差值完全归因于容量**。mmdet3.3.0本地模型索引未列M权重，故未用随机初始化替代COCO。neck out_convs对应原作者head.stems；已按此映射。

[转换脚本](../../tools/convert_author_yolox_m.py)、[完整映射和hash/数值核验](../../assets/checkpoints/yolox_m_conversion.json)。516个张量全覆盖，最大输出绝对差9.03e-6；[GPU预检](preflight/status.json)加载逐张量相等、batch8前后向/推理通过。只改变模型规模及匹配COCO来源，不改数据角色或训练超参。两任务共享GPU，时间不用于独立吞吐比较。

首次数值控制失败是参考模块默认BN eps1e-5未应用作者Exp的eps.001/momentum.03；修正参考构建条件后通过，未改变目标模型或预训练张量。此失败在训练前发生，没有运行失败权重的训练。原始M包203MB及转换产物保留。参考代码仅下载作者network_blocks/darknet/yolo_pafpn三文件，hash已记录，未安装或修改环境包。

[训练入口](../../tools/run_camera_recording_m.py)、[启动器](../../tools/launch_camera_m.sh)。预训练来源、权重hash、数据hash、源码commit及环境保存在train/；失败停止留档，不自动降batch或改配方。尚无指标时不能称训练完成。
