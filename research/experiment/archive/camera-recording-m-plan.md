# camera_recording_m：YOLOX-M对照预登记

用户授权与S同时运行。目的为比较同一数据平台上的M与S教师候选。保持1800/600、200epoch、batch8、seed0、45000iter、FP32、输入/增广/SGD/scheduler/EMA及epoch200 raw权重、val COCO口径相同，不读test。

结构采用安装的mmdet3.3.0 yolox_m配置：depth0.67/width0.75，neck输入192/384/768、输出192、CSP2块，head192；未使用的sonar模块同步为M且不前向。S原进程及脚本不改。

初始化来源存在已知差异：mmdet模型索引未列M权重，使用YOLOX作者0.1.1rc0 yolox_m.pth，转换backbone/neck，head重新随机。参考https://github.com/Megvii-BaseDetection/YOLOX 。故不能把结果差完全归因于容量。保存原始/转换hash与映射，必须目标张量全覆盖、形状正确、加载逐项相等，并与作者原始backbone+PAFPN+head.stems数值前向一致后方可训练。转换不取UXO权重。

先做batch8 GPU真实前后向及推理，确认S仍运行且显存足够。OOM/非有限loss/加载或数值控制失败则停止留档，不自动降batch或改配方。训练与结束后的val均写独立runs/camera_recording_m目录。两任务共享GPU，运行速度不作为模型独立性能比较。单seed不作稳定性结论。
