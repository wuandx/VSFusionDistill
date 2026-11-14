# 声呐目标检测 · UXO 教师图像基线复现

本工作区组织并审计 `D:\agent_workspace\水下\声呐目标检测` 中的既有研究。当前目标是验证纯光学（camera-only）教师基线，弄清它与 CMOLD 论文教师及早期实现的差异，再决定后续复现与蒸馏实验。

**核心主张：先固定数据、标注、划分和测评协议，再比较模型。论文未说明的内容只能标为未知或我方选择，不能写成论文事实。**

目标：形成可审计的教师图像基线复现；会议、期刊和截止日期尚未指定。

## 每次进入先读

1. 本文件。
2. [handoff.md](handoff.md)。
3. 涉及实验时读 [experiment/results.md](experiment/results.md) 与 [experiment/evaluation.md](experiment/evaluation.md)。
4. 原项目的入口为 `D:\agent_workspace\水下\声呐目标检测\README.md`；代码在 `code/VSFusionDistill/`。

## 目录职责

| 路径 | 职责 |
|---|---|
| `paper/` | 论文正文；当前中英双语数据集小节共用 `paper/dataset.md`，不放审核日志 |
| `related_work/` | 文献及 LaTeX 源码，保留来源与获取记录 |
| `复现/` | 基线审计与复现报告 |
| `brainstorm.md` | 按时间倒序记录问题、假设与证据状态 |
| `experiment/results.md` | 新实验登记；不覆盖历史读数 |
| `experiment/evaluation.md` | 冻结的测评协议与不可比边界 |
| `experiment/archive/` | 历史计划、失败控制和旧协议；保留证据，避免顶层堆文件 |
| `DataSet/`、`dataset.md` | 数据副本或数据说明、来源、划分和标注血缘 |
| `handoff.md` | 可接续的进度与下一步 |

## 硬规矩

1. 使用项目已有术语：CMOLD、CMHD、UXO、YOLOX、camera-only teacher、recording-level split、val、val_id、blob、projected、AP50、mAP@[.5:.95]。不要创造新的术语替代它们。
2. **原研究目录默认只读。** 不修改代码、配置、文档、数据、结果或 Git 状态，不删除或归档旧工作。工作流报告写在本目录。
3. **区分事实层级：**论文原文 / 原始产物复算 / 仓库历史记录 / 推断。不能用后续 AI 报告替代论文或原始产物。
4. CMOLD 未公开测试集构成不等于采用帧级随机划分。任何这类表述都是错误升级。只有 LaTeX 原文明确支持时才能写“帧级”。
5. `blob` 与 `all`、`val` 与 `val_id`、逐录音均值与 pooled COCOeval、单种子与多种子，必须分别标注；不可拼接为一次实验的读数。
6. 不把 `val_id` 称为“文献式考场”或“论文协议”：它仅是同录音留出诊断，不能解决论文未披露的划分。
7. 测试集只能在协议冻结后使用。当前审计不读取、不评价原项目标记为 `test` 的样本，不据其调参。
8. 论文关键事实优先查 `related_work/**/source/*.tex`。若只能获取 XML、HTML 或 PDF，明确记录，不能把其他格式冒充 LaTeX 源码。
9. 变更实验前先写目的、唯一改动、对照、判定标准与停止条件。每个实验有名字，失败也保留。本次先审计，不启动训练。
10. 结论按证据强度表达；不强行将绝对差距归因给单一因素。发现前报告的错误时，在新报告记录更正，不静默重写历史。
