# camera_temporal_pilot：执行前登记

用户授权：try it and verification。范围固定为101622、103140两条已允许开发录音的gallery native全部样本；paired身份从现有gallery交叉引用，不重划split。预期768+714=1482个原生样本，含268个paired身份。原研究与源文件只读，test关闭，不训练。

唯一变更：在独立副本中将camera图像取帧改成SD参考时刻对应的FHD帧。类别与原始标签字节保留；FHD框为原生SD坐标乘3，与已有gallery数值一致。候选副本不直接作为训练准入通过的数据。

新证据：完整源的两份 *_frames.csv 含精确aris_onset时间，不再沿用前轮外推。遵循公开公式 int((FrameTime−onsetTime)/1e6*fps)+gopro_offset 计算SD帧号；保存全部实际解码PTS，以最近时间FHD帧作为候选，限制半帧容差。整数偏移只做独立一致性检查，禁止用bbox或模型分数拟合对应。

核验：流帧数/单调PTS；原JPG与预测旧FHD帧低分辨率去均值MSE；SD参考与候选FHD同法比较；标签SHA与旧gallery一致，原始输入前后SHA不变；输出数量与每条样本状态闭合。依据前轮27个JPG查询MSE约0.71–1.18，预先把原JPG匹配MSE>4标为lineage_pending；候选SD/FHD MSE>9标为content_pending，不作为坏GT判定。每条仍保留读数和样本，阈值只做保守筛查，不等于唯一帧对应或框质量验收。

范围缺失、时间残差超半帧、lineage/content异常均保留状态，不自动外推、补帧或按检测结果选择。对于无FHD覆盖不临时混入SD/UHD。先完成两条录音与独立内容/输出核验，不自动扩展其余38条。首中尾、用户三个问题帧及不确定样本生成并排图并目视核查；异常如实报告，不承诺全量修复。

停止条件：源身份不符、需进入test、标签对应冲突或解码计数错误。异常日志保留，未完成副本不得作为训练输入。
