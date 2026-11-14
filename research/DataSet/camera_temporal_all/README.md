# Camera 全量时间对应重建

2026-11-11：40条允许开发录音全部完成；26761原生样本全部保留，26139候选FHD，622未恢复。现有4746个非test paired身份对应4566候选、180未恢复。原图、GT、视频和原研究均不变，没有训练或新split。

**打开 [index.html（本地产物说明）](../../ARTIFACTS.md#artifact-509c66e4b095) 查看。** 左旧图、中重建FHD、右SD参考，三列使用同一原框。可筛类别/录音/处理状态/native或paired/框范围，点击后左右翻图，G正常、B待复核；检查标记本机保存，请导出CSV留档。

当前清单与证据：

- `manifest-resolved.json` / `correspondence-resolved.csv`：包含7个有独立缓存血缘证据的补充恢复，保留initial_status；当前权威清单。
- `verification.json` + `verification-resolved.json`：初始全量核验与补充核验；全部候选实际JPEG内容检查、130张独立全分辨率单帧解码抽查。
- `manifest.json` / `index-initial.html`：初始保守结果，保留不改。
- `unresolved.csv`：622未恢复样本，609缺FHD时间覆盖、5时间戳待核、8缺SD参考；不伪造对应图。
- `annotation-geometry-flags.csv/json`：1117个原框越界提示，不等于判定错标；173615框包含大量支架/背景，优先复核。时间候选不等于框QA通过。
- `recordings/<rec>/...`：每录音副本、中间件、原标签字节副本、probe及检查点。
- `cache_resolution/`：7个补充恢复及逐例证据。
- `verification/<rec>-overview.jpg`：每录音固定首中尾对照。
- `source-archive-verification.json`、`annotation-archive-verification.json`：121个processed源文件、53522个允许原图/标签文件均与官方归档size/CRC匹配。

使用manifest中的 `image` 路径和 **`boxes_fhd_xywh`**；`labels_sd_original`仍是SD原坐标JSON，不能直接用于FHD图。候选数据尚待原框QA和协议冻结，未提供新的训练split。

完整说明见[全量结果报告](../../复现/camera-baseline/annotation-issues/camera-temporal-all-results.md)。
