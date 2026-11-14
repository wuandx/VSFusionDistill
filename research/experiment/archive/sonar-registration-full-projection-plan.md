# sonar_registration_full_projection：完整几何框与 elevation 裁剪框诊断

2026-11-12，执行前登记。触发证据：扩展评价中部分原图目标可辨，但现有 ±7° elevation 裁剪产生空框或极窄框，具体待核对示例为 grenade `2023-09-21_125048_0275`。±7° 是本地可见性假设；本地已查的 CMHD §3.1 未给出这一具体裁剪规则。不能由该段省略推断论文采用无 elevation 门限。

## 目的与唯一改动

区分两种外包框定义对初始检测候选的影响：

1. 现有新固定模型在前方、实际 range、beam 及 ±7° elevation 条件内的采样表面外包框。
2. 同一固定模型在前方、实际 range 和 beam 条件内的完整采样表面外包框，不施加 elevation 条件。

唯一变化是第二种定义取消 elevation 门限。它表示完整目标几何在二维声呐坐标中的投影范围，**不表示真实声呐垂直 FOV 无限，也不证明全部表面能够形成回波**。声呐 beam 符号、range、beam 边界、像素边缘坐标、padding=0 全部固定。

## 固定输入与对照

沿用 `DataSet/sonar_fixed_registration_refinement/evaluation-selection.json` 的全部 120 身份（40 录音各 3 帧，9 fit、111 development_check），不按框好坏替换身份。三类 `freeze-model.json` 的全部尺度、旋转、平移与 candidate_id 不变，不运行优化器，不改变 floor 相对 target 外推。使用同一密集点集：原始 OBJ 顶点、三角形中心与三条边中点。保留原评价目录与 JSON。

现有 `evaluation-results.json` 的新模型 ±7° 框为对照。新程序在同一批密集坐标上计算两种规则；核对重新计算的 ±7° 框与现有数值的一致性，这是新诊断的对照检查，不重跑既有 expanded-numeric-verification。数值差阈值 1e-8 px，可见点数须完全一致。

## 产物与判定

输出到 `DataSet/sonar_fixed_registration_refinement/full_projection_diagnostic/`，新建不覆盖已有文件。每帧保留两种框、表面点数、可见点数、增加点数、空框变化、面积比、IoU、框边界变化、模型与图像来源。复用各类评价目录的 `*-raw.png` 副本，不新增源图像访问；显示为全范围 raw、gain=1，原图 / ±7° 框 / 无 elevation 门限完整几何框并排。

先记录所用 freeze、selection、评价 JSON、OBJ、beam 表和 raw 副本 hash，完成后逐项复核。目录总览和每录音对照页保留全部 120 身份；输出分类、录音及总体统计。预先关注空框变非空、面积显著增大（比值≥1.5）、边界不变、仍为空的数量；这些是定义变化的数值描述，不是真值 IoU 或通过率。对明显仍不对的示例保留，不通过逐帧选门限修饰结果。

本诊断不按每帧选择门限、不重新拟合、不改默认服务或正式审阅、不生成 GT、不训练、不访问原 test，不把无门限定义写成论文事实。数值变化不能独自证明框质量；目视发现只作助手诊断，用户验收另行记录。

## 停止条件

输入 hash 与冻结来源不一致、身份不在既有 120 清单、raw 副本形状与 metadata 不一致、±7° 对照框差大于 1e-8 px、计数不一致或任何非有限数值时停止并保存失败记录。完成全部固定规则对照后停止，不依据结果继续调角度或扩展其他参数。
