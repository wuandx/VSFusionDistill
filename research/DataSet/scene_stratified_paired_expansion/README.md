# 场景分层配对扩充候选

[分场景浏览及全部配对（本地产物说明）](../../ARTIFACTS.md#artifact-dcdb7635c6e3)。4061对=3318原选入+398原备用+345新增助手接受；640新提案全部双端实际审阅，295待修不入清单。

|集合|录音|来源组|配对数|新增|
|---|---:|---:|---:|---:|
|train|21|17|2472|201|
|val|8|6|874|72|
|test|7|7|715|72|

每条录音100帧、总共3000对均非上限；本轮20项只是首批审阅批量。保持scene_stratified_recording_candidate录音/来源组角色。旧3716全部纳入selected，previous_membership记录原选入/备用；历史100帧字段改名previous_selected_for_100_per_recording。

camera/sonar/coco_train.json、coco_val.json、coco_test.json共6份；file_name均以本候选根目录解析，旧3716图像与原相机JSON引用旧候选，新增345图像在本目录。原SD框不改；声呐raw无翻转、无审阅增益。

5场景有三集合独立录音；普通炸弹flyby、迫击炮flyby、地面炸弹flyby各仅一接受来源组，缺口不因增帧消失。当前仅候选、未冻结训练；用户/专家验收与精密同步未认证。test来自允许开发来源，有审阅历史；原研究test内容仍关闭。若采用需冻结成员并从固定COCO重新训练。

本批早期decide覆写了快照；review-events.jsonl记录启用日志时的hash，并如实重建105230、121124、121327三次收回记录（原时间未知），之后显式审核追加事件。提案页包含未接受框，只有decisions中的accepted进入manifest。
