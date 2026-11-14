# condition_aware_recording_split：条件覆盖审计与新划分候选

用户授权检查全部30录音条件、生成新划分并展示，比例服从实际覆盖。本轮不重训、不评价候选AP，不替换旧split、数据或旧结果。

依据当前3000选入清单、原matches/notes及30条原始录音级/选入帧ARIS metadata。主条件按类别内【目标摆放、运动类型、notes名义z、tilt、roll、pan】精确组合，不为了比例合并725/750、不同旋转或flyby角。每个主条件至少一整个来源组进train；单组条件train-only并单列不能评价的边界。原122608/122855保守同组。电子采集设置、选入帧实际角范围、源帧跨度与相机触边只作为次级覆盖审计，不把notes名义姿态当每帧RGB姿态；缺字段记未知。

在各主条件中按SHA256(seed=42|condition|group)排序保留至少一train组，其余可留出；在满足主条件的方案中尽量增加留出、兼顾每类val/test均有独立组及数量近似、次级设置覆盖。优先级不使用旧val/test成绩，不把困难录音移除数据包。若无法覆盖所有条件且每类有留出，则明确限制，不拆相邻帧。所有3000选入和398备用留存，备用继承来源角色且不计主实验。

输出独立DataSet/paired_recording_condition_candidate：逐录音条件/来源/旧新角色、每类主条件覆盖表、train/val/test成员及全量角色索引、输入/输出hash、规则与校验、含每录音首中末原图预览的浏览页。本轮标candidate_pending_user_review，不自动激活或发训练。新版本制定已受旧test分析启发，必须记录历史，不追认全研究untouched test；未来重新COCO初始化训练。

## 主条件审计后、输出最终候选前的补充约束

首版metadata-only草案保留于paired_recording_condition_candidate，未激活；其同名义条件mortar105017/105230实际pan范围差异大，故只覆盖名义条件不足。最终候选单独输出paired_recording_condition_coverage_candidate。增加：所有类别内已出现的次级边际电子设置值及Min/Max Transmit至少在train出现；每条holdout至少95/100个选入帧，其记录SonarPan在同主条件train的选入帧中能找到±5°（圆周距离）内样本。5°和95%为本次候选的我方覆盖规则，不是论文标准或实际3D/RGB姿态认证，不据模型AP选择。枚举全部满足条件的train来源组子集，最少train录音→最小剩余pan不支持总数→seed42 hash；剩余独立组按类平分val/test。若无解则报告而不放宽阈值。此过程不评价任何新模型。
