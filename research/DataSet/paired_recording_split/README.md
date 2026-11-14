# 冻结的recording-level split

2026-11-13，用户确认采用6:2:2。来源为已结项paired_assistant_truncated_review/export；本目录仅增加角色索引，不复制或修改图像、标注、原manifest。

| 角色 | 录音 | 选入对数 | 备用对数 |
|---|---:|---:|---:|
| train | 18 | 1800 | 243 |
| val | 6 | 600 | 113 |
| test | 6 | 600 | 42 |

每类分别6/2/2条、600/200/200对。备用不计入训练/测评，继承来源录音角色。

- [录音角色和来源条件](recordings.csv)
- [逐样本角色索引（本地产物说明）](../../ARTIFACTS.md#artifact-734b26cfcd9b)：camera_image/sonar_image相对原export目录解析；membership区分selected与reserve，两侧共享role。
- 主实验清单：[train（本地产物说明）](../../ARTIFACTS.md#artifact-7c0c1080707c)、[val（本地产物说明）](../../ARTIFACTS.md#artifact-ed376ef0b99a)、[test（本地产物说明）](../../ARTIFACTS.md#artifact-956d98a14dec)。不要直接将原包coco_selected.json全量作为训练输入；加载器必须按对应清单过滤图像及关联annotation。
- [冻结算法、seed与输入hash](protocol.json)、[核验](verification.json)、[事前规则](../../experiment/archive/paired-recording-split-plan.md)、[生成脚本](../../tools/freeze_paired_recording_split.py)。脚本拒绝覆盖已有冻结manifest。

seed=42，以类别内SHA256组排序确定首个满足整组6:2:2的组合；未按成绩选择。122608与122855因原始ARIS双轨迹备注保守合组；所查30条完整gopro clip及gantry文件无重复关联。同相机chapter的不同clip未全部合组，本划分不声称session隔离。主要采集条件逐录音披露，没有强行令各稀有条件在三个集合齐全；例如floor bomb仅一条，落在test，故不能用test结果再调整训练配方。grenade test两条录音只有一个保守来源组；不能把它们作为两个独立组估计不确定性。

核验：3000选入和398备用全覆盖、互斥，类别计数正确；整录音/来源组不跨角色；两侧图像hash跨角色重复为0；输入hash不变；独立复核角色/选入清单/hash通过。未解码图像、未读取原项目test内容、未训练或计算模型指标。

历史角色来自原manifest，空值仅表示没有记录到paired角色，不证明未使用。全部来自已有40录音开发检查范围；已有教师曾见原37条录音，新run从固定COCO起点训练，不能沿用旧UXO权重宣称未见。本test是新run的保留角色，不认证全研究未触碰final test，也不认证未见实物、跨日期/session或真实海域泛化。

本次冻结的是成员和角色。配对精密同步、专家复核等原状态不因划分提升；数据结项保持，训练所需加载、指标、初始化及准入按[测评协议](../../experiment/evaluation.md)执行。此次不启动训练或开放test评价。
