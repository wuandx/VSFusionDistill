# 四条新增录音配对扩充：393对已导出，合计5229对

2026-11-14。用户在全94录音审计后要求“继续”。本轮完成180126、124241、124440、125924的双端取样、候选框、实际逐对审阅、修框、明确准入、独立导出与核验。没有训练、模型推理或新模型AP。事前目的、改动、对照、判定与停止条件及导出前角色补充见[计划](../../experiment/archive/four-recording-paired-annotation-plan.md)。

## 实际增加与覆盖

|新增录音|接受配对|未决|原notes名义条件|对原4836 train的补充|
|---|---:|---:|---|---|
|2023-09-20_180126|100|0|bomb，z500 / tilt−34 / roll90，Min / 10dB|此前train无这一联合条件|
|2023-09-21_124241|100|0|grenade，z250 / tilt−42 / roll90，Max / 0dB|此前train无这一联合条件|
|2023-09-21_124440|93|7|grenade，z250 / tilt−42 / roll90，Min / 15dB|同姿态的另一采集设置，与124241保守同组|
|2023-09-21_125924|100|0|grenade，z750 / tilt−22 / roll0，Min / 15dB|相同名义姿态原train已有121124/121327，新增Min / 15dB来源|
|合计|393|7||新增4录音、3保守来源组|

以上条件来自官方matches/notes与本地逐帧metadata复算，不是物理姿态认证。逐条对比的是同类、同摆放和运动场景内的z/tilt/roll联合值。四条都是L_to_R，并没有增加新的宽场景；mortar flyby、grenade tilt−90 flyby等缺口仍在。录音不同及保守分组都不能证明换了实物或完全独立采集环境。

## 取样、标注与审阅

四条原始相机标签均缺失；这次相机框与声呐框是助手新增标注，不能称官方原始GT或专家GT。公开matches与ARIS FrameTime、onset、视频fps、gopro_offset给出SD身份。原映射有效池分别为740/754/695/708，总2897；每条跨完整有效池均匀取100个不同SD身份，共400个。未选的2497项仍未经本轮逐对审阅。

先查看每条12个全程概览，再查看覆盖400身份的20张双端页（相机全图/框局部、声呐全图/框局部），算法仅提框。第二版修正125924颜色阈值后重看全部100项。之后显式修正24项边界：124241序号58–66与124440序号54–59、95–99共20个相机框，125924序号4–7共4个声呐上边界；修后相应5页实际复看。最终边界以[proposals-v3（本地产物说明）](../../ARTIFACTS.md#artifact-3eb1f4d96c84)与[24项修正（本地产物说明）](../../ARTIFACTS.md#artifact-a08ee6824192)为准。允许可辨认截断，声呐框包可见目标回波，尽量排除明显支架/地面散射；可见性审核不认证精密同步。

124440序号17–23（ARIS 186、193、200、207、214、221、228）回波过弱、破碎或空提案，全部保留未决；393=100+100+93+100。未决7项有双端副本和身份记录，但不在任何训练索引、COCO或YOLO中，也不是无目标负样本。这个可辨性筛选具有选择偏向，不能把接受率当全轨迹标注准确率。

## 合并与角色

|版本/集合|配对数|录音数|保守组数|
|---|---:|---:|---:|
|train|3433|26|22|
|val|961|9|6|
|test|835|7|7|
|合计|5229|42|35|

新393项全部进train，目的为补训练来源及联合条件，保持评价成员便于后续控制比较；124241/124440同组。原4836行manifest、身份、两端图像、原相机JSON、框和角色完全保留；val/test索引与两端COCO逐字节相同。本目录是独立图像/标注副本，不是对旧目录的替换。仍保持8种宽场景train覆盖、5种场景三集合覆盖，未因新增普通左右运动而填补flyby留出缺口。

两侧共用身份，各自使用各模态框。类别沿用100lbs_aircraft_bomb / mortar_shell / incindiary_grenade，对应COCO 1/2/3、YOLO 0/1/2。COCO file_name相对数据集根。新增camera/assistant_labels明确标助手新建；旧camera/original_labels保持。声呐训练PNG与原raw像素完全相同，网页仅显示时提亮2.5倍，不改训练输入。

## 对此前过早登记的更正

初稿“400/400通过”撤回：当时的程序主要检查框几何，不能据此登记全部目视接受；程序实际写出的是399候选、1未决，并在末尾打印时NameError退出。之后实际全400项查看与修框得出393接受、7未决。早期脚本和JSON已保留为premature-geometric-registration历史副本；旧普通入口review-decisions.json/review-summary.json现复制最终记录，权威版本为review-decisions-final.json/review-summary-final.json，不能使用早期399或文字400作为准入数。旧finalizer已阻止再次运行。

另更正中间修框日志：共享list引用漏记了4个声呐in-place改动；通过独立比较v2/v3重建完整24项事件。原中间20项日志保留，新explicit-corrections-final.json为完整记录。此前pending_user_split_review是流程额外引入的状态，用户已有扩充授权，本轮在明确成员/角色并完成核验后直接交付；没有新增批准门槛。

## 独立核验与访问边界

[independent-verification.json](../../DataSet/paired_four_recording_expanded/independent-verification.json)通过：

- 全5229身份唯一，10458张准入图像全部解码/hash、标签边界与类别、COCO/YOLO坐标往返通过；新增393 raw→PNG由PIL独立于导出OpenCV路径复核像素全等。
- 原4836 manifest行完全相同，旧图/框/标签/角色保持，val/test身份及COCO字节一致；录音与保守组角色互斥，跨角色编码文件和解码像素hash重复均为0。
- 400个ARIS→SD身份用Decimal时间及精确fps独立复算，12个固定首中末SD帧从源视频独立提取，JPEG hash与原提取完全一致。源视频、metadata、公开matches和旧manifest等hash未变；原计划hash由修改前副本核验，补充计划另存当前hash。
- 7未决已验证不在训练/COCO/YOLO。全部HTML静态本地链接存在；本轮未用真实浏览器验证渲染。

本轮复制/解码既有835 test身份仅用于打包和完整性检查，未作新模型test评价或用其内容挑新来源；原研究10条test图像/视频/标签保持关闭。旧715test已评价和新划分的开发使用史继续披露，新test不称未触碰外部盲测。现有旧模型接触过部分新留出录音，后续必须fresh COCO重新训练，不能将旧指标直接套在5229版或声称这393对已提高泛化。训练仍需另行任务授权。

## 入口与后续

- [合并数据浏览（本地产物说明）](../../ARTIFACTS.md#artifact-9940a746ec7f)
- [新增393清单（本地产物说明）](../../ARTIFACTS.md#artifact-c0939f7eefac) / [逐录音表](../../DataSet/paired_four_recording_expanded/recordings.csv)
- [完整manifest（本地产物说明）](../../ARTIFACTS.md#artifact-0aea4b2cee24) / [协议](../../DataSet/paired_four_recording_expanded/protocol.json)
- [7未决（本地产物说明）](../../ARTIFACTS.md#artifact-3545251dfa04) / [最终逐项审核](../../DataSet/four_recording_paired_annotation/review-decisions-final.json)

下一步数据工作仍是162055共同可见窗口，以及11段未登记相机视频的具体ARIS对应恢复；这些尚未作为新增配对或独立来源计入。本次不把四条普通左右运动扩充说成所有弱场景覆盖完成。
