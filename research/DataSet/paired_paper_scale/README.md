# 声呐—相机配对候选，未达3000对验收目标

目标按CMHD：3类×10完整轨迹×100对=3000对。CMOLD另为约4700对训练+验证，口径不可混用。当前是已有1120张声呐标注的配对恢复，非完成版训练集。

- `index.html`：双模态浏览；默认隐藏相机框越界与此前配对检查不足项，勾选后可查看原始问题。
- `manifest.json`：1120对，包含两模态图/框、源身份、哈希、相机帧索引与时间、作者和配对证据状态。
- `camera/images/`、`sonar/images/`：1120对字节副本，均未镜像。相机640×360；声呐为原raw栅格。左右显示方向可能不同，不据此修改原数据。
- `camera/labels_original/`：原SD标注JSON，包括134个越界待核项，未裁切。
- `camera/labels/`、`sonar/labels/`和各自`annotations.coco.json`：986对框格式有效的候选。**含161对既有配对检查不足项，不能直接用于训练**；是否可继续审核以manifest的`eligible_for_pairing_review`为准（825对，仍非质量验收）。COCO id同对共用，YOLO类0/1/2见classes.txt。
- `source-inventory.json`：40允许录音全部26761身份的相机源/标签格式和既有配对状态清点。
- `uniform-review-queue.json`：每录音100个唯一身份，共4000条待审任务；sonar_bbox为空，不是标签。均匀范围为现有允许标注身份，不保证覆盖完整原采集轨迹。
- `recording-coverage.json`、`summary.json`：每录音/类别缺额及层级计数。
- `verification.json`：全量身份、文件、格式验证；不替代视觉质量或同步认证。

类别：bomb822/mortar199/grenade99对已关联；格式有效688/199/99；扣除既有配对疑点后620/155/50对可继续审核。正式训练准入0，split未建立。仅沿用原配对来源，不调整时间和注册。

完整论文证据、限制和后续工作见[报告](../../复现/camera-baseline/paired-paper-scale.md)。不把本副本称为CMHD几何标注复现或专家GT。
