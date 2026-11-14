# UXO 可用性、CMHD 标注流程与 beam 符号复核

2026-11-11。回应用户对反号候选及“论文能做、当前复现为何未做成”的质疑。本轮是文献与源码审计，没有生成新投影或标签、拟合参数、访问 test 或训练。旧版投影、QA 和报告保留。

## 结论及前述表述更正

**UXO 的公开位姿、目标尺寸、3D 模型及导出脚本可以用于这条几何标注路线。当前失败的是我方尚未验证完整的实现，不能把它升级为 UXO 数据不可用或 CMHD 路线不可实现。**

“固定变换”只表示没有逐帧调整，不表示变换已正确注册。我方实际使用 PCA、名义长度和极值中点定义 OBJ→target，尚未恢复官方示例所用 STL 与 target 坐标的对应。13 帧 partial 等计数为助手主观检查，既不是标注精度测量，也不能证明反号解决了问题。

用户不赞成把反号作为继续推进的主要方向，这一点合理。另一方面，新复核发现官方历史文档明确给出 acoustic frame 的轴；因此也不应为了撤回“反号修好”的印象，反过来说反号完全没有依据。应将它作为需要统一的坐标换算问题，并把模型注册与标注规则单独解决。

## UXO 七项信息：能用，但不能跳过网格坐标的衔接

官方 [README（本地产物说明）](../../ARTIFACTS.md#artifact-4056e8820906) 第 12–19 行直接支持用户引用的性质，包括：

> Known and accurate transforms between sonar and targets.
> Known details of UXO targets including munition types, dimensions, and 3D models.

这些是官方说明的直接证据。当前 README 指向 Zenodo v1.1 记录 13778485，用户引用的是早期记录 11068046。

列向量约定下，具体衔接是：

`p_sonar = T_sonar_from_target · (s R p_OBJ + t)`

官方提供的传感器/target 位姿支持左侧的刚体链；当前投影还要求右侧所用 OBJ 的单位、原点、头尾和 roll 对上该 target 坐标。一个刚体矩阵准确，并不能自动使任意坐标系中的 OBJ 顶点成为这个坐标系的点。

实际证据：官方 [transforms_nb.ipynb（本地产物说明）](../../ARTIFACTS.md#artifact-f90e3377e9f1) 第 753 行直接以 `s=np.ones(3)` 将 `100lbs_aircraft_bomb/100lbs_aircraft_bomb.stl` 放入 `target/100lbs→world`；我们下载的模型包[成员清单](../../related_work/sonar-projection-audit-assets/data_export_3dmodels.7z.members.json)包含 OBJ/MTL/JPG，没有这个 STL。这不证明作者没有注册，也不证明全网没有其他文件；它说明不能把我方针对 OBJ 的 PCA 操作当成已经恢复了该示例的坐标。

[本地生成器](../../tools/project_fixed_mesh_to_sonar.py)第 50–62 行的未验证选择包括：长轴对应 target +x、数值轴符号决定头尾、第二主轴定义 roll、名义全长定义尺度、PCA 极值中点定义原点。官方[历史 README](../../related_work/model-registration-sources/historical-README.md)第 101–104、150–165 行描述以 gantry/ARIS 目视对齐估计目标位置，没有说该点等于 PCA 极值中点。**这是目前可以具体指出的实现缺口；尚不能断言它解释全部错位。**

## CMHD 原文：几何投影、人工 QA、残余误差

本轮直接解析 [CMHD 原始 JATS XML（本地产物说明）](../../ARTIFACTS.md#artifact-f5ac120ef892)，不是 LaTeX。论文 [DOI](https://doi.org/10.3390/s26144340)，[§3.1 在线入口](https://pmc.ncbi.nlm.nih.gov/articles/PMC13417324/#sec3dot1-sensors-26-04340)。

§3.1 明确写：

> Using the target’s initial pose, gantry motion trajectories, sonar extrinsics, and ARIS polar imaging geometry from system calibration, we projected the 3D UXO model onto sonar images frame by frame and generated physically grounded axis-aligned bounding boxes.

其后明确说明自动投影、`manual visual inspection`、处理明显错位或异常样本，并承认 `slight residual calibration or motion errors`，不等同于穷尽逐帧人工标注。不能将作者流程改写成要求所有框和回波轮廓零误差重合，也不能推断其逐帧移动模型、删了哪些样本或如何修框。

Data Availability Statement 进一步区分了原始 UXO 和新生成标签：

> The geometrically projected sonar annotations generated in this study are available from the corresponding author upon reasonable request.

UXO 作者也在 [issue #2 的回复](https://github.com/dfki-ric/uxo-dataset2024/issues/2#issuecomment-2929346833)明确说原数据没有 sonar labels；本轮重新请求 GitHub API，仍有该原文。因此 CMHD 做了额外的数据构建，不能认为 Zenodo 原包已包含它的声呐框。

正文没有给出可直接重放的各模型注册矩阵、beam 符号公式、完整像素实现及异常处理清单。本文 9 个编号公式涉及网络/蒸馏，而非 ARIS 投影。§4.4 的 100 张困难图像人工标注子集也不能追认为全部 3000 张都由专家逐帧重标。论文支持路线可行，但不足以直接复制其全部标注。

## beam 反号：新增依据与限制

官方历史 README（commit `d713bed7eb5253d5462218138c009bc004bebf47`）第 125–129 行明确：

> All offsets in ARIS acoustic frame (analog conventional optical frame of cameras)
> x = right; y = down; z = forward (optical axis)

这是仓库历史证据，不是论文原文。配合官方 raw beam 从右到左编号、[beam 表（本地产物说明）](../../ARTIFACTS.md#artifact-b6bbc201b4c6)第 0 列对应负表角，采用上述坐标约定时，右侧点 `atan2(x,z)>0` 应对应负表角，因此 `beam_angle=-atan2(x,z)` 有条件性的坐标依据。旧报告仅写“若与相机 optical 同轴”，漏掉了该明确历史说明。

但同一历史 README 第 138 行把安装孔所在的 ARIS right “ear”括注为 `-x`，与前述 `x=right` 存在字面不一致，可能涉及观察方向或不同 frame，尚未核实。不能把这份历史文档说成无歧义的物理符号认证。该冲突不支持直接选回正号；需要把实际 frame 和图像方向对应起来。

同时更正旧报告对 viewer 的简称：[view_recording.py（本地产物说明）](../../ARTIFACTS.md#artifact-f518715eec11)第 180 行为 `cv2.flip(aris_frame,-1)`，同时水平、垂直翻转，不是只有水平翻转。raw、viewer 与 polar 图必须分别定义坐标。

以上没有认证逐录音安装、注册及框边界。保留两版作为诊断记录，不因符号有依据就把 13 帧 partial 升格为合格标签。CMHD 正文未提供反号修正的直接论据。

## 为什么目前未达到论文的结果

当前实现已能数值重放，但完整模型注册、声呐像素映射的物理对齐和标注有效性尚未验证，这是应承担的复现工作。先前把 GoPro 完整标定变成声呐链硬前置已经更正；此次又不能用“冻结了假设”替代“验证了注册”，或者把软件数值重放当成物理对齐通过。

可继续推进的技术重点是：以官方 target 定义和目标几何对应建立可解释的 OBJ→target 注册；统一 raw 与官方 polar 导出坐标；明确几何投影框的目标范围、可见性、截断和异常处理规则，再跨开发轨迹核验。若用开发观测确定参数，应记录为我方注册，并用未参与拟合的开发轨迹检查。无需把等待作者或完整相机重新标定作为唯一入口，也不应继续靠正负号或逐帧平移追求视觉贴合。

## 阅读范围与产物

UXO 正式论文全文本轮仍未取得：DFKI PDF、ResearchGate 返回 403，替代路径 404；OpenAlex 返回元数据/摘要。原研究文献目录未找到对应命名的正式 PDF。因此不能断言 UXO 全文没有更多解释，也不能把官方 README 冒充论文全文。完整获取边界见下列 UXO 证据记录。

- [CMHD 原文引文及数据可用性声明](../../related_work/sonar-literature-recheck/CMHD-evidence.md)
- [beam、模型注册与显示方向源码复核](../../related_work/sonar-literature-recheck/beam-evidence.md)
- [UXO 官方信息及正式全文获取记录](../../related_work/sonar-literature-recheck/uxo/evidence.md)

本轮没有改变旧候选的训练准入状态，没有覆盖历史失败、原 GT 或冻结变换；仅追加证据和更正。
