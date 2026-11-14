# 上次弱场景的训练覆盖与5229对重划分

2026-11-14。用户允许重新划分，以覆盖上次模型能力弱的场景。结论：**可将上次已知薄弱条件放入训练，现有27种scene×z×tilt×roll联合条件均可覆盖；不能据此声称模型能力提高或所有场景都有独立评价。** 本轮仅5229对角色变化，无新训练、推理、标注或AP。原5229版、4836版和4081版保留。

## 对上次弱项的逐项回答

下表旧分数是固定epoch200 actual raw的历史读数，val与test分别标注，均不是新划分模型成绩。

|上次弱项|历史证据|新train实际覆盖|仍有边界|
|---|---|---|---|
|mortar flyby 105856|旧val camera47.15%、sonar0.59%|105856的20对进入train，z250/tilt−60/roll0、Max/5dB及原来横向截断相机呈现可以被拟合|110049的38对Min/15dB改为val；train仍只有20对/1组该场景，未覆盖Min15设置，原弱录音不再是留出|
|grenade左右121539|旧test camera66.85%、sonar73.04%|121539的102对进入train，z750/tilt−22/roll90组合不再缺失|该精确组合仅1组，无法同时作独立同条件评价；新增124241/124440不是这个组合|
|grenade flyby 125048|旧val camera68.85%、sonar51.84%|125048的100对−90加入train，同时124735的59对−60/Min15训练；train共159对/2组|124915的108对−60/Max0作val，−90仍无独立同条件留出；该场景无test|
|grenade左右123841/124039|旧val sonar45.66%/40.68%，主要定位问题|两条同组共212对Max0进入train；新124241/124440共193对roll90也保留train|123500的175对Min15作val；可以看到训练样式，不能证明边界误差唯一来自数据覆盖|
|mortar左右101416|旧val sonar9.36%|120对z750/−22/roll0在当前5229已是train，本次继续保留|该联合组合仍单组；100927/101131历史配对疑点未解除，没有借重分自动放行|
|mortar左右104749|旧test sonar35.89%|118对在当前5229已是train，继续保留，另103728/103927同联合条件加入train扩大实际pan范围|105230 val同联合条件pan支持92.42%，仍有范围差异|
|floor bomb ellipse 155609|旧test sonar48.70%、camera81.11%|155609的57对以及160146的69对均进入train，加160551的155对，共281对/3组|三组分别对应三个z/tilt联合条件，全覆盖后该scene无独立val/test|

旧结果依据：[最终val报告](scene-expanded-baselines-final-results.md)、[旧715 test报告](scene-baselines-test715-results.md)，当前角色与框依据5229原manifest与逐录音metadata。旧test已经用于开发目标定义，必须披露，不能因重划分重新称为盲测。将困难录音移进训练后，训练覆盖可以增加，但原困难录音的未见泛化问题无法再用其本身验证。

## 新划分

|集合|对数|录音|保守来源组|bomb / mortar / grenade对数|
|---|---:|---:|---:|---|
|train|4138|33|27|1844 / 1247 / 1047|
|val|573|5|5|120 / 170 / 283|
|test|518|4|3|30 / 146 / 342|
|合计|5229|42|35|1994 / 1563 / 1672|

22条录音相对上一5229版改变角色，全部35个原保守组定义不变且不可拆（这里不新增物理独立性主张）。具体角色以[42录音表](../../DataSet/paired_weak_scene_coverage_pan_split/recordings.csv)和[变更表](../../DataSet/paired_weak_scene_coverage_pan_split/role-changes.csv)为准；两侧共用身份，使用各自模态框。

val：175506(120), 105230(132), 110049(38), 123500(175), 124915(108)；test：101622(146), 121124(164), 121327(178), 174711(30)。test只有3个保守来源组，每类1组，bomb仅30对；样本数不能代替独立来源数，不适合用少量总体AP宣称广泛泛化。由于覆盖优先，比例约79.1/11.0/9.9而非强行6:2:2。

## 覆盖到什么程度

8种scene均进入train；27种现有scene内z/tilt/roll联合条件全部覆盖。它们是元数据名义条件，不是所有相机视图/实物姿态，更不是所有设置联合组合。保留两类左右运动等可评价来源后，电子边际仍缺grenade左右gain5（121124留test）和mortar flyby Min/15dB/Enable150V0（110049留val）。未知高度unknown按未知登记，不认证覆盖了具体高度。

为避免名义条件相同而实际轨迹差异很大，使用实际选入帧SonarPan的圆周±5°支持诊断，只在同scene、同z/tilt/roll训练录音中查找。9条留出录音中7条100%，175506为95%，105230为92.42%；不足95%未隐藏。此指标不是精密物理姿态对应，也未按模型预测优化。

最初仅名义联合覆盖草稿在两条mortar留出上的pan支持仅28.4%/30.1%，已标superseded并保留。推荐目录另加pan范围优先，再按电子边际、训练比例和样本量选取；没有新增模型成绩参与。规则及补充见[事前计划](../../experiment/archive/weak-scene-coverage-resplit-plan.md)、[搜索](../../DataSet/paired_weak_scene_coverage_pan_split/search.json)、[pan逐录音诊断](../../DataSet/paired_weak_scene_coverage_pan_split/pan-support.json)。

## 不能同时保有的评价范围

|场景|现有组数|覆盖所有名义联合条件至少需train组|本方案val/test|
|---|---:|---:|---|
|floor bomb ellipse|3|3|无/无|
|floor bomb flyby|1|1|无/无|
|standard bomb flyby|1|1|无/无|
|mortar flyby|2|1|1组/无|
|grenade flyby|3|2|1组/无|

后两场景的val与train采集条件仍不完全相同。train8场景、val5场景、test3场景，不能将test518称八场景全覆盖。全训练覆盖与全场景独立评价无法单靠重新分配这些来源同时实现；需要额外独立录音。若保留原弱录音评价不动，则相应精确条件无法凭同一来源补train，两种目标需要分别报告。

因此本版适合作为“尽量让模型学到现有薄弱条件”的开发训练方案；若要证明这些弱场景已泛化，应继续恢复110411/110229、100927/101131、162055有效配对，以及11段未登记相机视频的具体录音对应，不能把这些未决来源直接计入。本轮新增接受配对为0，只重分5229。

## 导出和独立核验

[独立核验](../../DataSet/paired_weak_scene_coverage_pan_split/independent-verification.json)对5229身份、10458图像解码/hash、所有框和标签血缘、YOLO/COCO往返、角色/录音/组互斥、跨角色编码与解码像素hash重复0均通过。manifest只增加previous_role并变更role，其余字段与旧5229逐项一致；新增标注仍是助手标注，未提升专家GT/精密同步认证。7未决不入清单、不作负样本。原输入hash不变，27联合覆盖和每场景最少训练组数由另一工具独立枚举，pan由独立逐帧算法重算。

独立图像/标签副本与各角色COCO、train/val/test索引已导出，COCO file_name仍相对数据根。原review记录保留的是当时审核与角色，现角色以顶层manifest和索引为准。camera/assistant_labels与camera/original_labels来源区分保持。42条首中末预览共126双端身份已生成并解码，本次实际查看105856/121539/125048的9个双端视图；不把生成预览说成重新全量目视标注验收。静态HTML链接通过，真实浏览器渲染未验证。

本轮未开启原研究10条test，仅对既有5229副本作重分、复制及完整性检查。旧val/test开发与模型评价历史保留。本版必须fresh COCO重新训练才有对应成绩，不直接评价旧UXO权重并宣称未见泛化；与旧AP比较会同时受训练和评价成员变化影响，不能归因为重分收益。

入口：[新划分双端浏览（本地产物说明）](../../ARTIFACTS.md#artifact-7b6b78ded1da)、[协议](../../DataSet/paired_weak_scene_coverage_pan_split/protocol.json)、[角色变化](../../DataSet/paired_weak_scene_coverage_pan_split/role-changes.csv)。
