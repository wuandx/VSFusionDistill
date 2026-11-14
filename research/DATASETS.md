# 历史baseline对应的数据集与划分

本页把每组模型成绩对应到当时使用的数据版本。仓库发布成员身份、标签/框元数据、划分协议、文件hash及部分配置；全量图像、视频和模型权重仍保存在本地。本次没有建立这些大文件的下载地址，不能把本仓库称为开箱即用的完整数据集。

| 版本 | baseline模型 | train / val / test | 划分性质与入口 |
|---|---|---|---|
| 原代码4152帧train+val池 | t_camera_s、t_camera_s_stretch | 3322 / 830 / 本表不迁入原test | train/val共享37录音；[原frame_split](legacy_code_data/frame_split.json)、[原始审计](复现/camera-baseline/results-and-failure-evidence.md) |
| 3000对 | camera YOLOX-S/M 640×384；workstation S两模态 | 1800 / 600 / 600 | 每类6/2/2录音，122608/122855保守同组；[协议](DataSet/paired_recording_split/protocol.json)、[录音表](DataSet/paired_recording_split/recordings.csv)、[完整manifest](DataSet/paired_recording_split/manifest.json.gz) |
| 4081对 | scene camera-M / sonar-S after_pilot | 2472 / 894 / 715 | 37录音、31保守来源组；[协议](DataSet/scene_stratified_mortar_recovered_candidate/protocol.json)、[录音表](DataSet/scene_stratified_mortar_recovered_candidate/recordings.csv)、[完整manifest](DataSet/scene_stratified_mortar_recovered_candidate/manifest.json.gz) |
| 5229对当前版 | 最新weak_coverage_camera_m_teacher，尚无本次确认的最终结果 | 4138 / 573 / 518 | 42录音、35保守来源组；[协议](DataSet/paired_weak_scene_coverage_pan_split/protocol.json)、[录音表](DataSet/paired_weak_scene_coverage_pan_split/recordings.csv)、[完整manifest](DataSet/paired_weak_scene_coverage_pan_split/manifest.json.gz) |

## 训练与评测使用的标签元数据

- 3000对本地camera S/M：[train COCO压缩副本](DataSet/camera_recording_baseline/train-coco.json.gz)、[val COCO](DataSet/camera_recording_baseline/val-coco.json)、[历史test COCO](DataSet/camera_recording_baseline/test-coco.json)、[准备与身份核验](DataSet/camera_recording_baseline/verification.json)。相机输入640×384，与fixed640工作站分开。
- 3000对工作站相机/声呐：对应[数据目录](DataSet/workstation_baselines/)包含两模态train/val COCO与dataset压缩副本、成员表和文件hash；不含图像。其最终模型结果在本次依据的记录中仍缺失。
- 4081对正式baseline：对应[执行数据目录](DataSet/scene_expanded_baseline_trainval/)包含两模态train/val COCO、dataset、成员表和hash；[train camera COCO](DataSet/scene_expanded_baseline_trainval/camera-train-coco.json.gz)、[val camera COCO](DataSet/scene_expanded_baseline_trainval/camera-val-coco.json)、[val sonar COCO](DataSet/scene_expanded_baseline_trainval/sonar-val-coco.json)。[历史715 test元数据](DataSet/scene_baseline_test715/)另列。
- 最新5229对教师：[相机train/val执行副本元数据](DataSet/camera_weak_coverage_trainval/)、[run冻结](runs/weak_coverage_camera_m_teacher/dataset-freeze.json)。当前角色变更不适用于旧模型的结果表。

3000和4081对版本各自保留train/val/test身份列表。`.json.gz`解压后与发布清单中的源SHA256一致；原始JSON内的本机路径保留用于血缘追溯，换机器时需要准备图像并调整路径。标签由各自数据准备脚本生成，类别编号/名称和几何以相应COCO、dataset与配置为准，不跨版本直接替换。

## 图像、标注来源与历史边界

原始UXO来源：[官方仓库](https://github.com/dfki-ric/uxo-dataset2024) / [Zenodo v1.1](https://zenodo.org/records/13778485)。我方存在时间对应恢复、筛选、声呐可见回波框和助手补标，仅下载原数据不等于得到相同训练集。完整本地位置保存在各版本manifest、准备脚本与[数据演进记录](dataset.md)。

最新新增393对含助手相机标注，不能统称官方原标签或专家GT。原研究的历史声呐blob/projected标签与workflow的可见回波标签要分别标注。旧val/test已用于评价或开发诊断，重划分不能恢复盲测资格；[历史模型结果](BASELINES.md)按原版本列出，禁止用当前划分解释旧分数。

原研究保留test的图像与混合标注没有在此次发布整理中读取或上传。这里的历史600/715 test元数据来自workflow里此前已授权生成的独立产物，没有新推理或评价。
