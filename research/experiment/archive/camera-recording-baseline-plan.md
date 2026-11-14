# camera_recording_baseline：首轮训练预登记

2026-11-13，用户要求进入camera baseline。目的：在冻结recording-level split上建立camera-only teacher。采用现有t_camera_s_yoloxs模型及配方，新数据平台为已结项SD选入子集；与历史模型仅并列，不归因为单变量提升。

train=1800、val=600，备用不使用；不读取test图像/标注。仅相机原SD框，640×360 BGR 0–255，不乘3、不clip；keep_ratio至640×640限制，实际resize仍640×360，右/底pad114至640×384。无Mosaic/MixUp/flip/HSV/多尺度/退化。所有原框须有限、正面积且位于图内，否则停止。

YOLOX-S现有camera分支，保留未前向未监督的sonar backbone/neck；数据适配器不加载sonar图。三类顺序明确冻结为当前交付0 bomb/1 grenade/2 mortar的模型内部映射（对应类别名，不沿用交付YOLO顺序）；COCO category_id依次1/2/3。初始化仅camera backbone/neck加载缓存的官方COCO YOLOX-S，head随机；旧UXO权重禁止。训练seed0，200epoch，batch8，225 iter/epoch，共45000 iter、360000样本曝光。FP32、SGD lr0.00125/momentum0.9/nesterov/decay0.0005，norm/bias不decay，clip35；warmup5、cosine到185、constant尾15，保留历史T_max185实际配方不宣称末LR精确等于eta_min；EMA momentum0.0001。

主权重为epoch200原始模型参数（checkpoint的state_dict），EMA另保存不混写；不以best-val挑权重。训练期间不做AP选择，最终仅val评价，score0.01/NMS0.65/max100。主pooled COCO mAP@[.5:.95]，同报AP50/AP75/AR1/10/100及逐类/逐录音、图像/GT/预测数量。保存预测、配置、版本、初始化hash、checkpoint hash。

先执行数据hash/解码/坐标检查、真实batch GPU前后向、初始化加载核对。非有限loss、坐标/映射异常、训练进程失败即停止且保留产物，不自动调参。训练脚本/配置/结果都写工作流目录，原研究目录只读（PYTHONDONTWRITEBYTECODE=1）。WSL现有GPU环境复用；不改它的包。此次不做容量/增广/学习曲线多臂搜索或test评价。单seed仅运行基线，不作稳定性结论。
