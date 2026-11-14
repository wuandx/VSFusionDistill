# sonar_projection_chain_audit：预登记

2026-11-11。用户授权核查CMHD式声呐标注准备；本轮只做数据/代码审计与固定小样本复算，不训练，不修改原研究，不重划split，不读原test样本/逐帧标注/预测。

- 目的：判断现有projected链是否实现CMHD描述的3D模型投影，定位其坐标、框尺寸与输入缺口。
- 唯一操作：对固定允许开发录音，用现有公式和缓存标定参数重算候选框，并与原始声呐和时间对应SD camera并排展示。不是训练消融。
- 样本：每类按recording字典序第一条允许录音（171105、120653、100927）；从其既有paired身份按序首/中/尾取3帧，共9帧，不按画面或模型表现选。若参考SD缺失记录失败，不换帧。100927为当前全量允许开发manifest中录音，按当前角色而非旧小sample脚本默认角色判定；开始前核对paired_role仅train/val/val_id。
- 对照：现有sonar_bbox返回的blob/projected框、同公式禁用blob的projected框、独立复算未施加40×60上限的几何边界。最后一项仅诊断，非3D模型投影或新训练GT。
- 验收：原输入hash前后相同；选样/源路径受允许manifest约束；数值公式能独立复算；图像与框坐标一致；查明3D模型、目标位姿、外参、ARIS行列几何的来源/可用性。目视只说明这些9帧，不推广成全量标签验收。
- 停止条件：路径不属于允许录音、paired_role出现test、源图/标签/索引不一致或变更即停止；3D位姿/模型链不足时不批量制作所谓CMHD GT；候选为空保留原因，不补造目标框或当成确认负样本。
- 输出：DataSet/sonar_projection_chain_audit/固定样本、诊断图、JSON/CSV、独立检查；复现/camera-baseline/sonar-projection-chain-audit.md与handoff。

初步静态发现：本地uxo_projection.py由camera框中心和sonar blob反求目标点/旋转，非3D网格投影；存在projected框上限40×60与y=441硬编码；工具默认dry-run仍写cache/report，不直接运行该入口。后续复算仅载入纯计算模块并写独立目录。
