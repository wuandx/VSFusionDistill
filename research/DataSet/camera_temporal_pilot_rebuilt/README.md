# Camera 时间对应试点副本

状态：完成导出及自动核验，待逐框人工验收。只含101622与103140两条开发录音，未触及test、未训练。

1482个原生样本全部有记录；1449张候选FHD，33个因FHD起点较晚而缺覆盖，保留原样本身份与状态。

- `index.html`：全部样本并排浏览；左旧图/原框，中时间对应FHD/原框，右参考SD/原框。
- `images/`：无绘制框的候选FHD副本。
- `labels_sd_original/`：原始SD坐标JSON字节副本；不能直接当FHD框使用。
- `manifest.json`：逐样本来源、时间、hash、状态和 `boxes_fhd_xywh`，后者与旧gallery相同，原生坐标乘3一次。
- `correspondence.csv`：逐样本帧序号、PTS及内容检查。
- `verification.json`：独立自动核验记录；独立单帧解码检查为9张抽样。
- `comparisons/` 与 `verification-overview.jpg`：对照图及首中尾总览。
- `reference_sd/`、`decoded_fhd/`：诊断参考与导出中间件，均非新split。

原图、标签、视频均保持不变。candidate仅表示时间/内容筛查通过，框质量仍需人工QA；不存在本次模型AP结果。详见[结果报告](../../复现/camera-baseline/annotation-issues/camera-temporal-pilot-results.md)。
