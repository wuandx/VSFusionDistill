# camera-only YOLOX-M 10轮短跑检查

2026-11-13。用户要求先停止此前两项并行长跑，按此前经验先单独跑少轮camera-only YOLOX-M看问题。两项systemd服务已停止，日志保留；停止时均在epoch2且未到首次epoch10 checkpoint，没有可用正式checkpoint，不能声称完整resume。

本次默认10epoch、3090更新，仅camera-M，重新从同一COCO backbone/neck起点开始，随机3类head、2472train/894val、batch8/seed0、keep_ratio fixed640、无增广不变。保留原200epoch配方的LR scheduler常量和时间边界，执行其前10epoch；不将cosine压缩成10epoch，不把这次短跑当200epoch收敛结论。

对照：同新版已通过实际预检的camera-M配置；唯一预算变化为截止10epoch，并在5/10epoch验证和保存checkpoint，便于先排查。原长跑不续跑，sonar保持停止。

判定：有限loss/梯度、正常完成3090更新；第5/10轮的raw val pooled/逐类/逐录音指标、三类及9录音固定预测图和loss/LR曲线，用于检查分类、定位、拟合趋势及明显整录音失败，不设AP硬门槛。主读数epoch10真实raw，EMA分开导出，不按val挑权重。val为开发集，test不读。

停止条件：数据/源码/初始化预检hash不符、OOM、非有限loss或运行错误立即保留失败停止，不改batch/几何/数据自动重试。10epoch结束自动退出，不恢复两项200epoch。短跑结束保存可检查产物；继续训练或改变配方由后续用户指令决定。
