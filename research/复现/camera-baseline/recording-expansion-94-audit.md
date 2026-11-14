# 94条录音扩充审核与时间映射更正

2026-11-14。任务是在固定当前val/test的前提下，检查更多独立录音用于camera-only训练的可能性；尚未启动新增训练。

## 存量与可扩充范围

原始inventory共94条，其中当前三类72条、test_cylinder另22条。三类中10条原研究test保持关闭；其余62条中51条有相机素材，11条无匹配相机片段。当前已使用37条（train21、val9、test7）；余下14条有相机素材，其中10条有原标签、4条需标注。14条与当前heldout未发现直接共用gopro_file/gantry_file，但纳入前仍须核对完整source group。详细计数与路径见`DataSet/recording_expansion_94_audit/inventory.json`及`summary.json`。

因此21条训练录音最多有增加至35条的候选空间，并非94条都可直接用于三类有监督训练。camera-only素材审核不应仅因声呐配对或投影未解决而排除；通过camera审核也不等于获得有效跨模态配对。

## 更正：首次预览漏用了已有时间修复

用户指出图框偏移曾通过时间对齐解决。核对`tools/rebuild_camera_temporal_all.py`及现有产物后确认：首次新增录音预览直接缩放原生FHD JPG并叠加SD标签，漏用了已有的SD/FHD时间映射。因此撤回所有仅依据该批预览作出的时间偏移或录音不可用判断。首次预览保留作错误对照，不作为新标签审核依据。

修正工具`tools/correct_recording_expansion94_previews.py`复用`DataSet/camera_temporal_all/manifest-resolved.json`的reference_sd，以及174711、162055已有SD pilot；不平移、不缩放重写原标签。120个有标签抽样中映射118个，2个缺失SD显式保留；4条无标签录音的48个预览不作框对齐判断。具体映射、源hash及撤回声明见`corrected_sd_review/manifest.json`、`summary.json`和上级`correction.json`。

实际重新查看了110229、110411、120912各12帧修正概览，框随目标对齐，支持遗漏时间映射是先前预览偏移的原因；不能据此升级为全录音标注认证。其他录音仍需以修正后的SD逐项审核。173615抽样存在坐标数值超出640×360的独立检查项，尚未自动裁框或据此排除整条录音。

修正浏览页：`DataSet/recording_expansion_94_audit/corrected_sd_review/index.html`。现有4081对数据、训练输入和已报告模型结果均未因本次预览更正发生变动。

下一步统一使用已修复时间映射构建camera-only扩充候选，完成标签与source group核验，再在固定train/val协议下分别验证新增录音和增广；不使用test挑方案。
