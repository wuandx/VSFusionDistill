"""Document actual coverage gains and the evaluation sacrificed by reallocation."""
from expand_paired_recording_pool import *
import shutil

D=ROOT/'DataSet/paired_weak_scene_coverage_pan_split'
OLD=ROOT/'DataSet/paired_weak_scene_coverage_split'


def prepend(p,marker,text):
    s=p.read_text(encoding='utf-8')
    if marker not in s:p.write_text(text+'\n\n'+s,encoding='utf-8')


def main():
    assert read(D/'independent-verification.json')['passed']
    summary=read(D/'summary.json');coverage=read(D/'scene-coverage.json');changes=read(D/'role-changes.json')
    report='''# 上次弱场景的训练覆盖与5229对重划分

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

22条录音相对上一5229版改变角色，20组规则保持不可拆，全部35个原保守组定义不变（这里不新增物理独立性主张）。具体角色以[42录音表](../../DataSet/paired_weak_scene_coverage_pan_split/recordings.csv)和[变更表](../../DataSet/paired_weak_scene_coverage_pan_split/role-changes.csv)为准；两侧共用身份，使用各自模态框。

val为175506(120)、101?不使用猜测清单，以后附精确名单为准。test只有3个保守来源组，每类1组，bomb仅30对；样本数不能代替独立来源数，不适合用少量总体AP宣称广泛泛化。由于覆盖优先，比例约79.1/11.0/9.9而非强行6:2:2。

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

入口：[新划分双端浏览](../../DataSet/paired_weak_scene_coverage_pan_split/index.html)、[协议](../../DataSet/paired_weak_scene_coverage_pan_split/protocol.json)、[角色变化](../../DataSet/paired_weak_scene_coverage_pan_split/role-changes.csv)。
'''
    # Replace the temporary placeholder with exact computed role membership.
    rs=read(D/'recordings.json')
    role_text='；'.join(role+'：'+', '.join(r['recording'][-6:]+'('+str(r['selected'])+')' for r in rs if r['role']==role) for role in ('val','test'))+'。'
    report=report.replace('val为175506(120)、101?不使用猜测清单，以后附精确名单为准。',role_text)
    # Count total classes from exported rows rather than prose arithmetic.
    rows=read(D/'manifest.json');total={c:sum(x['category']==c for x in rows) for c in CLASSES}
    report=report.replace('1994 / 1563 / 1672',' / '.join(str(total[c]) for c in CLASSES))
    report=report.replace('22条录音相对上一5229版改变角色，20组规则保持不可拆，全部35个原保守组定义不变',
        str(sum(x['changed'] for x in changes))+'条录音相对上一5229版改变角色，全部35个原保守组定义不变且不可拆')
    (ROOT/'复现/camera-baseline/weak-scene-coverage-resplit-5229.md').write_text(report,encoding='utf-8')
    notice='''# 已被pan覆盖方案替代的名义联合覆盖草稿

本目录保留首版探索证据：仅z/tilt/roll覆盖后，两条mortar留出pan支持低至28.4%/30.1%，不作为推荐方案。推荐版本为../paired_weak_scene_coverage_pan_split/。原protocol hash中的计划后续有显式补充，因此不要把当前计划hash变化当源图/标签变化。本草稿没有训练或模型结果。
'''
    (OLD/'SUPERSEDED.md').write_text(notice,encoding='utf-8')
    oldpage=OLD/'index.html';s=oldpage.read_text(encoding='utf-8')
    s=s.replace('<h1>','<p style="color:#a00">本草稿已被加入pan诊断的方案替代；<a href="../paired_weak_scene_coverage_pan_split/index.html">查看推荐版</a></p><h1>',1)
    oldpage.write_text(s,encoding='utf-8')
    p=D/'index.html';s=p.read_text(encoding='utf-8')
    s=s.replace('<h1>','<p><a href="../../复现/camera-baseline/weak-scene-coverage-resplit-5229.md">弱项逐条覆盖与边界报告</a></p><h1>',1)
    s=s.replace('电子组合、相机视图和pan不保证全覆盖。','电子组合、相机视图和pan不保证全覆盖：留出pan支持7条100%、1条95%、1条92.42%；test仅3个保守组、bomb30对。')
    p.write_text(s,encoding='utf-8')
    link='DataSet/paired_weak_scene_coverage_pan_split/index.html';rep='复现/camera-baseline/weak-scene-coverage-resplit-5229.md'
    note='''## 2026-11-14 用户允许弱场景优先重分：train4138/val573/test518

[新划分浏览]({link})、[弱项对应与限制]({rep})、[独立核验](DataSet/paired_weak_scene_coverage_pan_split/independent-verification.json)。既有5229对/42录音/35组只变角色，train4138/33录音27组、val573/5录音5组、test518/4录音3组；全部27种已登记scene×z×tilt×roll联合条件进train。上次弱项10585620、121539102、125048100、123841/124039212、15560957进入train，101416/104749原已train继续；新增四录音393仍全train。

用户本轮明确允许重新划分，覆盖优先替代此前固定5229版val/test约束；旧版保持。全组不可拆，原图/框/血缘不变，7未决不放行，无新训练/推理/AP。新方案受旧val/test诊断启发，属于开发协议，不能称未触碰盲测。floor ellipse与两种bomb flyby无留出，两类其余flyby只有val；test只3场景/3组、bomb仅30对。mortar flyby train只有10585620对，不含Min15；grenade左右gain5仍缺。实际留出pan支持7条100%、1条95%、105230为92.42%。名义联合覆盖不等于全部视图/设置或能力改善。

独立10458图像hash/解码、全COCO/YOLO、身份/录音/组、27联合与最少组独立枚举、pan复算、旧输入保持通过，跨角色编码/像素hash重复0。首版joint_only草稿paired_weak_scene_coverage_split因mortar pan28.4/30.1不推荐，标superseded保留；推荐paired_weak_scene_coverage_pan_split。原研究10条test关闭，旧评价史保持，后续需fresh COCO；优先恢复110411/110229、100927/101131、162055与11未登记相机对应，以补独立来源。
'''.format(link=link,rep=rep)
    prepend(ROOT/'dataset.md','## 2026-11-14 用户允许弱场景优先重分：train4138/val573/test518',note)
    prepend(ROOT/'handoff.md','## 2026-11-14 用户允许弱场景优先重分：train4138/val573/test518',note+'\n\n工具resplit_weak_scene_coverage.py枚举分配与导出，verify_weak_scene_coverage_split.py独立校验，document_weak_scene_coverage_split.py登记。完成目录不可重跑覆盖；无训练服务启动。')
    exp_note=note.replace(']('+link,'](../'+link).replace(']('+rep,'](../'+rep).replace('](DataSet/','](../DataSet/')
    prepend(ROOT/'experiment/results.md','## 2026-11-14 用户允许弱场景优先重分：train4138/val573/test518',exp_note)
    ev='''## 2026-11-14 弱场景覆盖优先的开发重划分

用户明确允许重分后，采用[新开发方案](../DataSet/paired_weak_scene_coverage_pan_split/index.html)：5229对保持，train4138/val573/test518，33/5/4录音、27/5/3保守组。全部27现有scene内z/tilt/roll联合条件进train，旧弱val/test录音可进入训练；因此本版受已使用val/test启发，不可称新未接触盲测，旧分数不套用。[报告](../复现/camera-baseline/weak-scene-coverage-resplit-5229.md)、[协议](../DataSet/paired_weak_scene_coverage_pan_split/protocol.json)、[核验](../DataSet/paired_weak_scene_coverage_pan_split/independent-verification.json)。旧版和数据保持；用户本次授权更新此前固定val/test成员约束。

组整体、模态身份共同、各模态原框、类ID与COCO根保持。train8scene、val5scene、test3scene；floor ellipse和两种bomb flyby无独立留出，mortar/grenade flyby仅val，test仅每类1保守组（bomb30对），N/A必须明确，不拼接旧场景结果。pan仅metadata诊断，10523092.42%仍有差异，电子边际/相机视图非全覆盖。原研究10test关闭，7未决不准入。后续fresh COCO训练并冻结模型/评价后才有本版成绩；不能将困难样本移出留出造成的AP变化当模型能力增益，若要验证这些弱项的泛化，需额外独立来源或独立分组对照。
'''
    prepend(ROOT/'experiment/evaluation.md','## 2026-11-14 弱场景覆盖优先的开发重划分',ev)
    (D/'provenance').mkdir()
    for name in ('resplit_weak_scene_coverage.py','verify_weak_scene_coverage_split.py','document_weak_scene_coverage_split.py'):
        shutil.copyfile(ROOT/'tools'/name,D/'provenance'/name)
    shutil.copyfile(ROOT/'experiment/archive/weak-scene-coverage-resplit-plan.md',D/'provenance/plan.md')
    save(D/'artifact-sha256.json',{str(f.relative_to(D)).replace('\\','/'):sha(f) for f in D.rglob('*') if f.is_file() and f.name!='artifact-sha256.json'})
    print('coverage report, superseded draft, current dataset/evaluation/results/handoff written',flush=True)


if __name__=='__main__':main()
