# 3D模型注册与标定一致性核查

2026-11-11；审计名 `sonar_model_registration_consistency`。按 research-workflow 保存来源、数值控制和未解决项。继承[预登记](../../experiment/archive/sonar-model-registration-plan.md)，不覆盖[上轮审计](sonar-projection-chain-audit.md)。

## 结论与更正

**此前4°的标定不一致已解释并数值复现；公开OBJ的完整mesh→target注册仍未解决，不能宣称已经可以批量生成CMHD式GT。**

1. 官方notebook保存于2024-07-23；2024-07-26官方提交把相机安装轴的约−4°俯仰改为0°。用历史标定复算同一控制帧，最大矩阵元素误差为6.24×10⁻⁷。此前“原因未知”由本报告更正为“标定版本与notebook保存输出不同”；原报告保留。
2. 此变化只涉及相机安装链。两版sonar静态链和target位姿相同，不能以修复该相机差异为由旋转声呐位姿或模型。
3. 官方历史README提供三类目标的名义尺寸，但没有公开每个OBJ到target的完整尺度、旋转和平移。名义长度可以提出尺度候选，无法唯一确定注册。
4. 数据集作者明确说camera–sonar外参来自外部测量、精度有限。数值链自洽不等于逐录音物理投影准确。

## 证据层级与来源

本轮新增依据为**官方仓库历史、官方发布资产、作者公开回复与原始数据复算**，不是CMHD论文新增披露。CMHD方法说明仍采用此前核对的JATS XML；本轮没有获得CMHD的注册文件或标注生成源码。

| 来源 | 能支持什么 | 不能支持什么 |
|---|---|---|
| [官方7月23日notebook提交](https://github.com/dfki-ric/uxo-dataset2024/commit/ffd60f8271038e3dc9f12e3dd218e3a1c9e9a4a9) | 保存的AR3及target→camera控制值、历史标定版本 | 每录音精确标定、公开OBJ已注册 |
| [官方7月26日提交](https://github.com/dfki-ric/uxo-dataset2024/commit/3aa12eca086e03469edd901f7cd766bd7bb8ff1c) | `changed camera pitch to 0`，有效四元数改变 | 0°比−4°更接近所有实测录音 |
| [官方历史README](https://github.com/dfki-ric/uxo-dataset2024/blob/d713bed7eb5253d5462218138c009bc004bebf47/README.md) | 名义尺寸、摄影测量来源、用吊架估计物体位置的步骤 | 精确scan尺度、目标坐标原点在mesh上的对应点 |
| [作者2025年回复](https://github.com/dfki-ric/uxo-dataset2024/issues/3#issuecomment-3219604993) | camera–sonar外部测量外参精度有限，目标位姿是估计值 | 外参已达到像素级GT精度 |
| [第三方PR6](https://github.com/dfki-ric/uxo-dataset2024/pull/6) | 提供可供检查的可视化思路 | 不是已合并官方方案，不能认证注册 |
| [第三方issue5](https://github.com/dfki-ric/uxo-dataset2024/issues/5) | 同类问题公开存在且抓取时未获回复 | 问题正文中的论文转述和数值不是作者确认事实 |

作者原话："we don't have highly precise transforms between camera and sonar"；"from external measurements"。回复者`ndahn`在GitHub标记为COLLABORATOR。

来源已保存于[来源目录](../../related_work/model-registration-sources/README.md)：网络获取日志保留URL/时间/hash；历史文件保留精确commit/path/hash。克隆范围为官方公开仓库当前可见历史，HEAD `323ac6cf45bb6129806c8e3ed8ec31e22e1a392d`；不是私有仓库、所有潜在附件或作者内部文件的穷尽检索。

## 1. 4°差异：版本控制已通过

固定控制：允许开发录音`2023-09-20_171105`，ARIS frame1211。使用原始gantry和Pan/Tilt/Roll，AR3输出按官方示例保留6位小数，不拟合任何参数。

| 标定 | 相对notebook的最大元素误差 | 旋转差 | 平移差范数 |
|---|---:|---:|---:|
| 2024-07-23历史版 | 6.2358274×10⁻⁷ | 0.00005105° | 0.0000006015 m |
| 当前发布版 | 0.07279660 | 3.99994991° | 0.07282592 m |

两版均由NumPy/SciPy矩阵链与独立pytransform3d变换图复核，最大差小于10⁻¹⁰。历史控制容差为2×10⁻⁶，考虑保存的AR3位姿及矩阵数字舍入；**该容差只验软件数值复现，不是实测标定精度指标。**

唯一有效变更为`setup/gopro_mounting_axis`的四元数xyzw：

- 历史：`[0, -0.034899, 0, 0.999391]`。
- 当前：`[0, 0, 0, 1]`。

数据发布包与当前仓库YAML语义一致。Zenodo v1与本地已校验版本的calibration/3dmodels包MD5也相同；没有发现一个可通过换版本自动补上注册的资产包。

已产出[calibration-versions.json（本地产物说明）](../../ARTIFACTS.md#artifact-60a2cae3f48e)，分别保存两版矩阵及hash。复现历史notebook显式选历史版；发布数据诊断以当前版为基线。这是我方版本管理规则，尚未批准任一版本为所有录音的精确GT。

## 2. 坐标链：明确哪些变换已知

统一列向量，`A_from_B`表示B坐标点变为A坐标点，已知刚体平移单位为米。

```text
mesh --(未知的尺度/旋转/平移)--> target --(官方估计位姿)--> world
world --(gantry + AR3姿态的逆)--> ar3 --(固定安装变换的逆)--> sonar
                                                     └--> camera
```

设mesh顶点为v，缺失注册为`s R v + t`，则：

```text
p_sonar = inv(world_from_sonar) @ world_from_target @ [s R v + t; 1]
world_from_sonar = world_from_ar3 @ ar3_from_aris @ aris_from_sonar
world_from_camera = world_from_ar3 @ ar3_from_mount_hole
                    @ mount_hole_from_mount_axis @ mount_axis_from_camera
```

AR3朝向复用官方`R_static @ R_xyz(roll,tilt,pan)`，位置是gantry xyz加静态AR3平移。不能把AR3姿态简单替换成固定yaw或沿用camera框中心拟合来声称物理mesh投影。

**生成sonar几何框本身不要求先解决相机内参和相机安装角**；它要求可靠的mesh→target、target→world、world→sonar和声呐成像约定。相机投影可作为额外验证，但不能把不确定的相机误差吸收到mesh注册后再称声呐GT正确。

## 3. OBJ注册：尺度候选已计算，完整注册尚缺

官方notebook加载的是`100lbs_aircraft_bomb/100lbs_aircraft_bomb.stl`，并用`scale=1`叠加target位姿；当前公开模型包提供的是不同路径的OBJ。所查公开git历史没有跟踪OBJ/STL/PLY/Metashape工程资产，未找到这份STL或生成它的注册变换。因此不能把notebook里`scale=1`套到OBJ。

从历史官方README恢复的名义尺寸与OBJ诊断如下。候选计算采用顶点PCA第一主轴极值跨度，`s=名义长度/跨度`，**仅用于几何诊断**。

| 模型文件 | 名义长度/直径(m) | PCA纵向跨度(OBJ单位) | 长度约束候选s(m/单位) | 缩放后的两横向跨度(m) |
|---|---|---:|---:|---|
| `100lbs.obj` | 0.737 / 0.208 | 4.810422 | 0.153209 | 0.209646 / 0.230058 |
| `incindiary.obj` | 0.442 / 0.127 | 5.347621 | 0.082654 | 0.153636 / 0.122544 |
| `mortar_shell.obj` | 0.580 / 0.120 | 9.393465 | 0.061745 | 0.129746 / 0.122015 |

名义尺寸描述的是弹药类型，不保证等于损坏/锈蚀扫描物的精确极值；尾翼也不必等于弹体直径。PCA轴符号任意，横向方向受几何对称性影响，顶点分布不保证均匀。因此不能把PCA原点/轴自动当成target原点/轴，也不能根据横向差异随意做非均匀拉伸。

已目视检查[三模型几何图（本地产物说明）](../../ARTIFACTS.md#artifact-26cece11be2a)，可辨识外形、弹头和尾部；这不是坐标注册证据。历史`object_notes.md`混合了吊架测点、尖端/上方描述和“TF未更新”注记，与后续README/标定也不完全一致，不能据此唯一指定mesh原点。

[mesh-registration.json（本地产物说明）](../../ARTIFACTS.md#artifact-16dd20e0025e)保留三个模型的hash、原始/PCA尺度与候选值，`mesh_to_target=null`、`approved_for_gt=false`，避免后续脚本把候选误当冻结GT变换。

第三方PR6的不可变commit `8810df836c8391dd5cea9c6824093e988c46c8dd`中，模型只显示在独立视图；源码明确写：`Photogrammetry scan in its own (unregistered) frame and scale`。本轮只读此代码，未运行其样本、未据其视觉结果认定标定准确。

## 4. 后续如何完成注册验收

当前可直接使用的成果是版本明确、可复算的标定链；缺失的是每类模型的完整注册及实测控制。完成路径如下，不能跳过中间验收直接量产框：

1. 优先获取与公开OBJ对应的metric注册矩阵，或官方示例所用的已注册STL及其定义；每类需明确单位、target原点、轴向、适用目标放置条件。当前公开来源未提供这些内容。
2. 如果原始注册无法取得，采用**我方重新注册**：用可识别的几何端点/轴线/实际尺度建立mesh约束；把名义长度作为有误差的先验，区分`s,R,t`、每录音目标位姿误差和相机安装误差。camera框中心与sonar最亮blob都不能充当精确3D对应点。
3. 先用固定开发控制帧做拟合与验证分离，固定声呐beam方向、range-bin映射、垂直视场、真实每帧高度和截断规则。原九帧保留，不按对齐好坏替换；缺SD帧保留deferred。若增用其他开发录音，先写入明确白名单，避免读取test或用旧GT自证。
4. 需要人工核对独立的声呐目标范围/特征对应，并预登记接受误差后，才可批准注册与导出sonar候选框；记录残差和失败录音。通过相机框内点检查或单帧视觉重合不足以验收。公开资料没有给出可直接继承的像素阈值，本轮未编造阈值或标注真值。

若无法取得官方注册，也无法建立独立实测对应，则CMHD式物理GT仍有缺项；可另行构建人工审核sonar标注，但必须标为我方数据方法，不能称恢复了论文UXO†。

## 执行与核验

- 工具：[audit_model_registration_consistency.py](../../tools/audit_model_registration_consistency.py)。运行：`python tools/audit_model_registration_consistency.py`；依赖与上轮一致，只写工作流副本。
- 首次执行历史notebook路径误用当前`demo/`，中断于来源快照阶段；改为历史`scripts/`后成功。对象notes删除提交的预期缺文件查询已改为先检查tree；未产生训练GT或改源文件。
- [verification.json](../../DataSet/sonar_model_registration_consistency/verification.json)：160个原始录音物理metadata文件hash与上轮及执行前后一致；原代码仓HEAD仍`4fadd06829c6c738977639a55b6e44ad0e35ac44`，status clean。不是全源目录逐文件认证。
- 0次训练、0次模型推理、0次test样本访问、新split和训练GT均为0。本轮只读取固定开发录音元数据，未增加图像样本访问；几何图仅来自公开OBJ。

本轮状态：**标定版本差异已解决；完整3D注册未通过；正式声呐GT继续HOLD。**
