# beam 符号与固定 mesh 投影的独立源码复核

2026-11-11。本轮只读官方代码/公开历史记录及已有固定 mesh 产物；没有生成投影、拟合参数、读取新录音或 test，也没有训练。本文是新增更正记录，旧报告和两版产物不改。

## 结论

反号可以是坐标约定的必要转换，但不能作为使整条物理投影成立的修复结论。当前最明确的失败边界是：我们冻结的 `mesh→target` 使用了人为注册假设，并未验证为官方注册；数值重放一致只能证明这些假设被一致执行。不能据本次失败推断 UXO 的公开位姿和模型不可使用。

## 比既有报告更直接的坐标依据

- 官方仓库历史 `README.md`（commit `d713bed7eb5253d5462218138c009bc004bebf47`）明确写：`All offsets in ARIS acoustic frame (analog conventional optical frame of cameras)`，并列 `x = right`、`y = down`、`z = forward (optical axis)`。本地原文：[historical-README.md](../model-registration-sources/historical-README.md)，125–129 行；来源登记：[history-provenance.json](../model-registration-sources/history-provenance.json)。这是仓库历史证据，不能标成论文原文。
- 当前 `transforms.yaml` 的 `setup/sonar` 和 `setup/camera` 均使用 quaternion `(x,y,z,w)=(0.5,0.5,0.5,0.5)`，当前安装中间旋转为单位阵；见 [transforms.yaml（本地产物说明）](../../ARTIFACTS.md#artifact-64be26eceb2d) 24–34、46–71 行。此版本的两个局部轴方向相同。
- 官方 [aris_definitions.py（本地产物说明）](../../ARTIFACTS.md#artifact-b6bbc201b4c6) 250–315、318–320 行：beam 表按列由负角到正角排列，第 0 列为负角。官方 [view_recording.py（本地产物说明）](../../ARTIFACTS.md#artifact-f518715eec11) 178–180 行注释说明 raw beams 从右到左编号。
- 因而采用上述 `sonar x` 向右、`z` 向前的约定时，右侧点的 `atan2(x,z)>0`，却应该落到负表角/较小 raw 列；这对应 `beam_angle=-atan2(x,z)`。这是坐标约定推导，不能由“看起来更好”证明。
- 后续交叉复核补充：同一历史 README 第 138 行把 right “ear”括注为 `-x`，与第 125–129 行 `x=right` 存在字面不一致；可能涉及观察方向或不同 frame，尚未核实。因此上述推导以采用第 125–129 行约定为条件，不能称历史文档无歧义认证了物理 beam 符号。
- 官方 [prep_2_aris_to_polar.py（本地产物说明）](../../ARTIFACTS.md#artifact-78fba5f843d4) 174–188、207 行先取表角负号、使用 `cos(angle+90)`，最后水平翻转，最终正表角落在 fan 显示左侧。显示变换与上述 raw 列定义相容。

更正旧报告的两处措辞：

1. 旧报告把 `sonar +x 向右` 只写成“若与 camera optical 同轴”，漏掉了已保存历史 README 的明确轴说明。应改为有官方历史约定支持，但逐录音实际安装/标定有效性仍未由本次试点独立验证。
2. `view_recording.py:180` 实际为 `cv2.flip(aris_frame, -1)`，会同时水平、垂直翻转，不能简称该调用“仅水平翻转”。其中水平分量支持左右显示；垂直分量使距离由向下增加变成向上增加。

## 本次模型输入的未验证部分

[project_fixed_mesh_to_sonar.py](../../tools/project_fixed_mesh_to_sonar.py) 50–62 行实际执行：PCA 轴对齐、对角分量定符号、名义全长定尺度、PCA 极值中点归零。它没有从官方记录读取完整的 OBJ→target 注册矩阵。

1. 名义全长对应扫描模型全长（尤其腐蚀/变形目标）；
2. mesh 长轴为 target +x，头尾由 PCA 数值符号决定；
3. 第二 PCA 轴定义 roll；
4. target 原点为 PCA 包围盒极值中点；
5. 同一公开 target 位姿适用于所取两条录音。

这些假设都明确写在 [fixed-mesh-transforms.json（本地产物说明）](../../ARTIFACTS.md#artifact-fbc529ae2c21)。冻结它们可以保证不逐帧调参，不能保证它们是真实注册。

官方历史 README 101–104、150–165 行描述用 gantry/ARIS 目视对齐估计目标位置；没有定义该位置与公开 OBJ 的 PCA 极值中点相等。官方 [snippet_for_pose_gt.ipynb（本地产物说明）](../../ARTIFACTS.md#artifact-3c9d6d4f9ee3) 281 行使用 `100lbs_aircraft_bomb/100lbs_aircraft_bomb.stl`、`s=np.ones(3)` 加 target→world；所下载模型包的[成员清单](../sonar-projection-audit-assets/data_export_3dmodels.7z.members.json)只有 OBJ/MTL/JPG，没有该 STL。这证明当前所用 OBJ 与示例输入存在未解决的衔接，不证明其他地方不可能有注册，也不证明数据不能利用。

投影器另外使用假设 `|elevation|≤7°`、离散表面点加 1 bin/beam padding，且不预测散射、遮挡、声影（代码 59、77–90 行）。这些是我方实现选择，不能冒充 CMHD 的精确实现。它们应被验证，但本轮未找到足以把所有错位唯一归因于其中某一项的新证据。

## 结论用语建议

可以说：“UXO 提供了可用的位姿、模型和导出依据；我们尚未把公开 OBJ、target 原点/朝向及声呐图像坐标连成经过验证的标注实现。反号是坐标检查的一项，不能解决注册和框定义问题。”

不应说：“UXO 的变换不准确，所以做不了”；也不应说：“反号后多数 partial，所以符号和物理框已经正确”。
