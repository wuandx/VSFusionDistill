# camera_train_self_evaluation

2026-11-13。用户要求独立排查训练集表现和实现。对象为已完成camera YOLOX-S 640×384 epoch200 actual raw。只增加train1800自评，使用与既有val600完全同权重、预处理、score .01/NMS .65/max100与COCO指标；sampler关闭shuffle，仅model.eval/no_grad，不更新参数。对照为该权重既有val结果，test不读。

判定：报告train/val pooled、逐类、逐录音AP/AR及固定score .25/IoU .5错误分组，不把训练集成绩当泛化性能。若训练也大规模错类，继续核对真实加载框/类别与原JSON、权重、模式/配置；若训练几乎全对而val错类，支持跨录音性能落差，不单独认定具体原因或绝对排除实现问题。将先前检索的train近邻真正预测加入并排页，避免把“训练图外观”当“训练图预测正确”。必要时挑少量具体身份请用户确认物体/标注语义；不要求用户审全量。

保留原指标和配置，只新增train_actual_raw_epoch200结果及诊断报告。框/类/身份不一致或非有限预测停止，失败保留，不改label/split/训练/阈值。此次不进行新训练或参数搜索。
