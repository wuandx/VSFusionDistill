# 当前715对test：冻结模型后的授权评价

2026-11-14。用户明确要求“看看测试集”，授权当前已接受4081对划分中的715对test评价，覆盖此前该候选test保持关闭的执行状态；不扩大到原研究另外标记test的来源，不新增训练。

在读取预测结果前固定：camera-M与sonar-S均使用after_pilot完成run的epoch200 actual raw导出权重，核验导出身份、父checkpoint hash、原resolved config和类别映射。不得按test在raw/EMA、epoch或模型配方间择优。

数据：scene_stratified_mortar_recovered_candidate中现有test-selected.txt及camera/sonar coco_test.json，715对、7录音/7来源组，bomb308/mortar246/grenade161。不重分、不改框、不剔除难例；按候选根解析源图引用，另做独立test执行副本。准备前记录原test COCO/成员表/录音表和两个模型权重/配置hash，核对与train/val来源组互斥、样本身份与跨角色图像hash，不读取其他原test来源。

测量：各模态各自原图与GT，keep_ratio+右底114固定640、BGR0–255、d0、无增广、score.01/NMS.65/maxDets100，原训练配置几何和逆变换不变。pooled COCOeval mAP@[.5:.95]/AP50/AP75/AR@1/10/100，附逐类/录音/场景及样本/来源组数。无test的场景N/A；不将逐录音均值代替pooled，不直接将两模态AP差当方法增益。

判定：完成完整715身份推理、权重和坐标/类别可复核，成功或失败均登记；原test有数据建设/开发审阅历史，本次不称全研究untouched external test。此后test已有模型评价使用记录，不能据其调参再继续称独立盲验。

停止：成员、来源、权重hash、标签坐标/类别异常或非有限预测则保留失败停止，不换epoch/阈值/GT重试以求高分。输出独立预测、metrics、权重/输入身份、逐场景结果与报告；不训练、不评价EMA、不自动触发后续实验。
