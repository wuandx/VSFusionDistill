# workstation_sonar_s / workstation_camera_s_fixed640

2026-11-13，用户授权在192.168.10.100 AMHS工作站运行两项，数据传/root/wzl/dataset。只使用冻结1800train/600val，test与备用不上传。原图/标注不变，数据hash/成员清单及包hash留档。

1. sonar_s：建立sonar-only YOLOX-S、无蒸馏基线，监督当前可见回波框（非旧blob/projected）。raw PNG转三通道BGR，不翻转/不增益，keep_ratio到640×640并右/底pad114到固定640×640，框按实际fx/fy缩放并按原尺寸反算。COCO S backbone/neck起点、随机三类head；无camera输入。后续蒸馏学生应沿用本输入及起点。
2. camera_s_fixed640：对照本地camera S，唯一预定管线变化为把右/底padding从32倍数改固定640×640；原SD像素、框、缩放保持，scale_factor仍1，不拉伸。另有工作站硬件/环境差异须记录，非逐位严格单变量重放。

两项200epoch/batch8/seed0/45000iter、FP32，SGD lr.00125/momentum.9/decay.0005/nesterov/clip35，历史warmup5/cosine185/constant15、EMA.0001，无图像增广/退化，epoch200 raw权重，最终val pooled/逐类/逐录音mAP/AP50/AP75/AR1/10/100，score.01/NMS.65/max100。若原EMA checkpoint含交换需核对raw实际来源，不凭名称。

使用本地只读代码快照部署/root/wzl/workflow_baselines/source，避免远端旧repo差异；不覆盖/root/wzl/VSFusionDistill或旧结果。用户授权本次工作站训练更新历史只审计限制。远端复用既有GPU环境，先检查版本、CUDA、COCO权重hash、全量train/val图像/框/角色一致，再真实batch前后向、推理、padding/scale逆变换；失败保留停止，不自动降batch或换数据。资源允许则并行，不抢占或终止其他进程。
