# 新版baseline独立train/val执行副本

固定来源：`../scene_stratified_mortar_recovered_candidate/`。本副本包含2472train/894val，相机和声呐各3366张，共6732张；不包含test图像或test逐帧COCO。原划分和候选不变。

- 类别：COCO 1=bomb、2=mortar、3=grenade；模型内部0/1/2。
- camera：原SD 640×360像素与原camera框。
- sonar：原raw PNG像素与已接受可见回波框。
- 所有图像路径相对此目录；`SceneSingleModalDataset`在加载时解析，不写死机器绝对数据路径。`source_image`仅来源留痕，不作为加载路径。
- `verification.json`记录复制时的全量解码、图像hash、边界与组隔离；`independent-verification.json`为另一次6741文件hash及源输入hash核对。
- `files-sha256.json`覆盖6732图像、8份COCO/适配数据清单及trainval成员表。
- `trainval-members.json`保存sample、recording、group、scene及role。

新版入口：`../../tools/run_scene_baseline.py`；旧prepare/run_camera_recording/run_workstation入口仍用于历史实验，不能用于此包。

输入管线固定keep_ratio、右/底pad114至640×640，图框逆变换由预检确认。尺寸—类别关联仍存在；此副本不作去混杂或新标注。200epoch正式训练尚未启动。
