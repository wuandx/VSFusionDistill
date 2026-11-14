# 已有 camera GT 全量可视化导出

2026-11-10，按用户“把camera侧数据画框展示、逐张检查”的要求执行。此项不是训练实验，也未使用模型重新标注。原研究、原始图片和标签未修改。

浏览入口：[逐帧浏览页（本地产物说明）](../../ARTIFACTS.md#artifact-c8be9f3fdccf)。使用本机浏览器打开，可按类别、recording、数据版本、split、帧号筛选，原图/带框图并排，左右键翻帧，标记问题并下载检查CSV。

| 导出版本 | aircraft bomb | incendiary grenade（沿用源名称incindiary_grenade） | mortar shell | 合计 |
|---|---:|---:|---:|---:|
| 当前paired实际GT | 1,294 | 1,524 | 1,928 | 4,746 |
| native完整序列、原始标注×3 | 8,997 | 7,932 | 9,832 | 26,761 |

共31,507张全分辨率带框图及同数量缩略图；两套有重复帧，不是31,507个独立采样。paired覆盖train 2,652 / val 1,500 / val_id 594，无抽样。native覆盖当前37条录音及未完成train/val副本的额外3条录音，共40条；只导出同时有标签与JPG的帧。不声称已覆盖本机缺失的旧remote dense等所有历史平台。

绿色框来自当前paired/camera.json；蓝色框来自原始SD标签×3，不clip或修正。导出图在未缩放图像上绘框，额外增加48px标题条。画布之外的线段不可见不表示标签被裁剪；manifest保留原数值。未完成副本仍HOLD，未续跑它的数据生成脚本；其额外录音只展示native标签，不能冒充其尚未写出的最终camera.json。

源文件和每张图的来源、框坐标、原始label hash及生成规则见输出manifest.json和image-index.csv。导出脚本为 [export_camera_annotation_gallery.py](../../tools/export_camera_annotation_gallery.py)。verification.json记录完整性：缺失0、失败0；progress.json最终status=complete。浏览器实际渲染检查通过：网格48张、类别筛选、并排视图的原图和带框图宽均为1920；工具没有修改GT。

访问例外：头部检查时误把单行camera.json当多行，Get-Content -TotalCount 30读取了完整混合标注。因此本轮不能声称从未读取test标注，已记录在输出README与provenance。后续按非test ID筛选解码，未打开或导出test图像、未运行test评价、未据其选择模型或改标签。test封存图像仍不进入浏览页。

目前不自动判定哪一类标注错误；等待用户按sample_id/recording和问题类型记录，再回到原图、转换、训练输入三层定位原因。
