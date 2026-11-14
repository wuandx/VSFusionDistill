# 两项200epoch baseline完成后的结果检查

2026-11-14。用户要求“看看结果”。两项after_pilot run状态completed；主口径固定epoch200 actual raw，不按val择优换epoch或EMA。

目的：汇总同固定val894的总体、逐类、逐录音、逐场景结果及训练过程；同epoch200 raw补train2472自评以辨别拟合/跨录音落差。camera与sonar的输入和GT语义不同，分表解读，不把两模态AP差直接解释为方法增益或可蒸馏空间。

对照：复用保存的epoch200 raw val预测；沿各run自身10–200的监测序列看趋势。相机10轮pilot是独立run，只能另列参考，不能把pilot和完整run拼成一条曲线。每项train自评保持原d0/score.01/NMS.65/maxDets100，核对导出权重身份、父checkpoint与数据hash。

输出：train/val pooled、逐类/逐录音/逐场景COCOeval，8场景无val者N/A；每模态每val录音首/中/末固定3样本图，loss/val趋势和完整表。必要时用固定score≥.25的候选IoU/分类统计作诊断，单独标明，不代替AP。不读test，不调阈值/数据/标签，不启动训练。

判定：训练是否正常完成、权重与指标可复核；特定场景的train高/val低支持该run跨录音/条件落差；train也低时保留拟合/标注及可见性问题的可能。不得仅由AP50/AP75差唯一归因。异常或hash/类别/坐标不符则保留失败并停止新评价。
