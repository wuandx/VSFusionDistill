# paired_recording_split：事前规则

目的：落实用户确认的3000对recording-level 6:2:2。唯一改动：增加独立角色清单；原数据、框、时间及成员不变。对照：原selected/reserve清单。判定：每类6/2/2条、600/200/200对，录音/样本/已知来源组跨角色交集为0，备用继承录音，原包hash不变。任何不满足即停止，不改seed重抽。

固定seed=42；以SHA256('42|'+category+'|'+group_id)排序组，枚举该顺序的test两条组合，再枚举剩余val两条组合，取首个整组可行解；余下train。与模型指标无关，不搜索性能。122608与122855因matches备注原始ARIS含两条轨迹保守合组；其余按recording分组。共享gantry或完整gopro片段时也须同组。相同相机文件主干中的不同clip不自动同组，不能据此主张跨采集session隔离。

只读取当前交付manifest/成员清单、允许40条的来源manifest及matches录音级元数据；不解码图像、不评价模型、不读取原test内容。已有历史train/val/val_id与40录音开发检查单列；历史用途不因新角色消失。独立session、未见实物泛化及全研究未触碰final test均不认证。采集条件留表披露，不为稀有单条条件强行实现三集合覆盖。

输出独立DataSet/paired_recording_split：recordings.csv、逐样本角色manifest、selected与reserve分角色清单、输入hash、核验与README；不复制图片、不改源包。此次不启动训练或测试，训练其余准入仍按evaluation.md。
