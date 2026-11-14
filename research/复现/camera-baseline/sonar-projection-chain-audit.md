# CMHD式声呐标注：本地投影链审计结果

2026-11-11。按用户“do it”执行前一轮约定的投影链核查与固定小样本复算。结果：**现有blob/projected不能当成CMHD的3D模型投影标注；本轮未产出通过准入的新训练GT。** 相机教师与共同配对集冻结仍需先解决物理投影坐标依据与标签QA。

预登记：[sonar_projection_chain_audit](../../experiment/archive/sonar-projection-chain-audit-plan.md)。[9帧并排浏览（本地产物说明）](../../ARTIFACTS.md#artifact-3db267dd4f52)、[数值结果（本地产物说明）](../../ARTIFACTS.md#artifact-a0fc851e3a35)、[验证记录](../../DataSet/sonar_projection_chain_audit/verification.json)、[40条输入清点（本地产物说明）](../../ARTIFACTS.md#artifact-cbfcb216c7d7)。没有模型训练/推理、没有新split、没有打开test样本/逐帧标注/预测，原研究只读。

## 1. 论文事实与本地实现的差异

论文证据是CMHD §3.1原始JATS XML（非LaTeX）。论文描述用目标初始位姿、gantry轨迹、sonar外参和ARIS极坐标几何，将3D UXO模型逐帧投影为轴对齐框，再做人工QA。未公开全部生成代码/投影可见性规则或具体样本清单。

| 项目 | 本地源代码/原始产物证据 | 与CMHD关系 |
|---|---|---|
| 目标位置 | uxo_projection.py:265载入camera GT框中心视线与sonar blob；:581等拟合目标点P、相机/声呐旋转及range bias | 是观测拟合，不是读取并投影3D网格 |
| 框边界 | :749 sonar_bbox使用类别名义长度、拟合中心和范围；:121及:770–773将projected上限设为40×60像素 | 无证据是论文规则；不能称物理完整目标边界 |
| blob覆盖 | 满足列/距离gate时用检测到的bright blob框加1像素padding替换projected | 形成blob/projected混合标注；CMHD没有披露这套替换规则 |
| 逐帧姿态 | 原始ARIS metadata有SonarPan/Tilt/Roll；uxo_to_paired.py:114的字段清单未携带它们，旧链改为拟合朝向 | “gantry.csv无姿态”不等于“原始数据无姿态”。此前不能用旧paired字段缺失认定官方没有该输入 |
| 图像边界 | :785写死x≤128、y≤441 | 40条原始metadata对应28条441行、11条780行、1条603行；应按实际图像边界审查。本轮9帧的纯projected框没有因441裁剪产生数值变化，不能把样例问题全部归因于这处硬编码 |
| 输出副作用 | project_uxo_sonar.py即使无--write也写report/cache | 本轮未运行该入口；只加载纯计算模块，禁止pyc写回原仓 |

源目录：`D:/agent_workspace/水下/声呐目标检测/code/VSFusionDistill/`。代码注释中的旧test结果只作为历史来源被读到，不访问其样本或复算其分数，也不据此选择新方案。

## 2. 固定9帧复算与目视

按预登记，每类从允许manifest按录音名字典序取第一条，然后取该录音既有paired身份的首/中/尾，共9帧。录音分别171105、120653、100927；当前允许manifest中paired_role为val/train/train，100927虽在早期小sample默认test注释出现，但不是当前配对角色中的test。全量允许范围和具体角色先核实后才读取。

- 9/9原始sonar PGM与对应paired副本SHA256相等；9/9原始FrameTime与允许manifest相等。
- 同一缓存参数下重算得到3个blob、6个projected；独立复算距离→行公式和几何边界/上限与纯projected计算全部通过。
- **这不是重跑标定，也不是证明当前sonar.json逐框一致。** 仅从缓存文本定位并解析这3条calib对象；未解析其他录音calib条目，但为追踪身份读取/计算了整个cache文件hash。缓存未重算fingerprint或认证其适合修复后的camera版本，不作为新GT依据。
- 120653_0933缺实际SD参考，保留固定身份并显示空白，记deferred；没有换更好看的帧或偷用旧FHD作SD。其sonar公式仍可诊断，不能作为已合格SD配对样本。
- 已目视3张首中尾整录音sheet及其9行：171105_0981的40×60框只覆盖横向回波局部，171105_1336的blob为9×13像素局部；120653部分投影框偏离主要回波，100927末帧blob与纯projected中心亦不一致。这些是样例层面的标签疑点，不是全量错误率，也没有把回波外形直接裁成新GT。
- 绿色无上限框只是“同一名义长度公式去掉40×60限制”的诊断，通常过大且仍受拟合中心影响，**不是3D网格投影，也不是修复方案**。不能简单去上限就宣称标签修好了。

## 3. 物理输入已补齐哪些，仍缺哪些

已从官方Zenodo记录13778485下载并校验：

| 资产 | 大小 | 官方MD5核验 |
|---|---:|---|
| data_export_calibration.7z | 1020 B | bb7641890899bf424e3eeb242509f261，通过 |
| data_export_3dmodels.7z | 26442213 B | 4ed8820771bbb39819eacf66b50ff509，通过 |

解压到工作流独立资产目录，包含三类相关OBJ/材质/纹理与setup/target transforms；另取官方pose演示notebook。来源、字节数、hash和归档成员在[资产日志](../../related_work/sonar-projection-audit-assets/acquisition-log.json)。标定归档与当前GitHub transforms内容语义相等。

允许40条录音全部有gantry与ARIS逐帧Pan/Tilt/Roll，索引集合一致；这些字段可恢复官方定义的AR3逐帧位姿。当前本地40条都没有ar3.csv，不能因此宣称位姿信息丢失。notes与姿态范围已保留，未用“没有moving字样”推断静止。

**仍不能直接开始批量网格投影：**

1. 官方notebook引用`100lbs_aircraft_bomb/100lbs_aircraft_bomb.stl`，本次官方3D包只有`100lbs.obj`等。OBJ到target frame的单位、尺度、旋转和原点对应尚未找到。三类OBJ轴向最大extent分别约4.808、5.365、9.314（原OBJ单位），不能擅自当米或猜一个统一缩放。重新居中/按长度缩放都是需要依据的变换，不可默认为论文做法。
2. 使用官方导出公式，从171105第1211帧独立重建的AR3位置/四元数与官方notebook保存值逐位相同；但当前公开标定算出的target→camera变换与notebook保存输出差约4°、平移范数0.07283 m。手工矩阵链与独立pytransform3d库相符，差异不来自两种复算之间；差异原因仍未知，可能涉及示例保存时使用的标定版本等，但未证实，未拟合补偿。见[官方位姿控制（本地产物说明）](../../ARTIFACTS.md#artifact-6228715fe4f4)。
3. target的静态位姿是否适用于每条录音（含变更目标位置、floor等）仍需录音级核查；声呐显示方向、beam/elevation可见范围和最终polar图框转换也未形成验收链。当前PGM为range×beam矩形阵列，不能把它的框直接叠到扇形显示上。

因此目前只可称“官方输入部分可追溯，3D模型注册与坐标链未验收”，不能称CMHD标注复现成功。

## 4. 验证、失败与保留边界

9帧审计52个输入文件hash前后相同；40条物理输入清点的160个metadata/gantry/yaml/notes文件hash检查相同。原仓HEAD仍4fadd06829c6c738977639a55b6e44ad0e35ac44，status clean。依赖仅装入工作流`tools/_sonar_audit_deps`。未对整个数据盘做全文件hash。

第一次固定样本准备因reference_sd缺失KeyError失败，日志保留于[attempt-1-failure.json（本地产物说明）](../../ARTIFACTS.md#artifact-b87a4cbb0574)，随后保持选样不变并显式处理缺SD。官方pose控制最初期待复现保存矩阵但断言失败，随后保留差异并用独立库验证；最终JSON的passed=false，未伪装成通过。

## 下一步

先追查公开OBJ对应的metric mesh/target注册与标定版本，或利用可靠的目标尺寸/标记建立并独立验证该变换；不能据这9帧目视去调参数后宣称同协议。坐标链通过后，先在同样三条录音上导出新物理候选框并检查，再扩展允许开发范围、处理173615/175000的camera框准入，最后冻结CMHD式共同配对抽样/划分。

本轮到达预登记停止条件：物理网格坐标依据不足，不批量写训练GT。无需用户重复授权已允许的只读追查；若后续需改变标注定义、以人工注册替代缺失官方变换或访问原test，则需另行明确方案与边界。
