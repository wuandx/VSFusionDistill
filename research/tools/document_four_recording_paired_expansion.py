"""Publish verified dataset delivery and explicit correction without erasing history."""
from expand_paired_recording_pool import *
import shutil

D=ROOT/'DataSet/paired_four_recording_expanded'
R=ROOT/'DataSet/four_recording_paired_annotation'


def prepend(path,marker,text):
    previous=path.read_text(encoding='utf-8')
    if marker not in previous:path.write_text(text+'\n\n'+previous,encoding='utf-8')


def main():
    v=read(D/'independent-verification.json');assert v['passed']
    # Preserve the mistaken payloads, then make the ordinary entry paths authoritative.
    for name,final in [('review-decisions.json','review-decisions-final.json'),('review-summary.json','review-summary-final.json')]:
        assert (R/(Path(name).stem+'-premature-geometric-registration.json')).is_file()
        shutil.copyfile(R/final,R/name)
    correction=read(R/'registration-correction.json')
    correction.update(ordinary_entry_paths_now_copy_final_decisions=True,
                      premature_payloads_retained_in_suffixed_files=True,
                      intermediate_correction_log_missed_four_in_place_sonar_edits=True,
                      authoritative_corrections='explicit-corrections-final.json',corrected_samples=24)
    save(R/'registration-correction.json',correction)
    shutil.copyfile(R/'registration-correction.json',D/'review/registration-correction.json')
    report='''# 四条新增录音配对扩充：393对已导出，合计5229对

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

先查看每条12个全程概览，再查看覆盖400身份的20张双端页（相机全图/框局部、声呐全图/框局部），算法仅提框。第二版修正125924颜色阈值后重看全部100项。之后显式修正24项边界：124241序号58–66与124440序号54–59、95–99共20个相机框，125924序号4–7共4个声呐上边界；修后相应5页实际复看。最终边界以[proposals-v3](../../DataSet/four_recording_paired_annotation/proposals-v3.json)与[24项修正](../../DataSet/four_recording_paired_annotation/explicit-corrections-final.json)为准。允许可辨认截断，声呐框包可见目标回波，尽量排除明显支架/地面散射；可见性审核不认证精密同步。

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

- [合并数据浏览](../../DataSet/paired_four_recording_expanded/index.html)
- [新增393清单](../../DataSet/paired_four_recording_expanded/added-manifest.json) / [逐录音表](../../DataSet/paired_four_recording_expanded/recordings.csv)
- [完整manifest](../../DataSet/paired_four_recording_expanded/manifest.json) / [协议](../../DataSet/paired_four_recording_expanded/protocol.json)
- [7未决](../../DataSet/paired_four_recording_expanded/unresolved/manifest.json) / [最终逐项审核](../../DataSet/four_recording_paired_annotation/review-decisions-final.json)

下一步数据工作仍是162055共同可见窗口，以及11段未登记相机视频的具体ARIS对应恢复；这些尚未作为新增配对或独立来源计入。本次不把四条普通左右运动扩充说成所有弱场景覆盖完成。
'''
    (ROOT/'复现/camera-baseline/four-recording-paired-expansion-5229.md').write_text(report,encoding='utf-8')
    oldreport=ROOT/'复现/camera-baseline/four-recording-paired-annotation-review.md'
    prepend(oldreport,'## 更正：本初稿已作废','''## 更正：本初稿已作废

下文“400/400通过”及待用户split批准的结论均已撤回。最终为393接受+7未决，已经导出为5229版；不是400接受。几何检查被过早登记为目视准入的错误、完整24项修框与历史保留见[更正及交付报告](four-recording-paired-expansion-5229.md)。以下保留原初稿作为错误历史，不作当前准入依据。''')
    dataset_note='''## 2026-11-14 四条新增录音双端扩充完成：5229对

[浏览](DataSet/paired_four_recording_expanded/index.html) / [报告及更正](复现/camera-baseline/four-recording-paired-expansion-5229.md) / [独立核验](DataSet/paired_four_recording_expanded/independent-verification.json)。新增393对：180126/124241/124440/125924=100/100/93/100，全部train；124440另7项声呐弱回波未决，不当负样本。新增4录音、3保守组（124241/124440同组），合计42录音35组，train3433/val961/test835。旧4836身份/图/框/角色保持，val/test索引与COCO字节不变；独立两端副本可复制。新增相机JSON明确助手标注，非原标签/专家GT；未认证精密同步。

实际400项双端逐对审阅，24项显式修框后复看。此前“400个全部接受”是过早几何登记，已撤回，历史保留；最终393+7，以final记录为准。全图像/hash/坐标往返、raw像素、独立12帧提取和400时间映射复核通过，跨角色编码/像素hash重复0。新四条仅补左右运动联合条件及采集来源，未补flyby缺口。无训练或模型推理；既有test仅副本完整性检查，原研究10条test关闭，旧开发/评价史保持。'''
    prepend(ROOT/'dataset.md','## 2026-11-14 四条新增录音双端扩充完成：5229对',dataset_note)
    results_note='''## 2026-11-14 paired_four_recording_expanded_5229：新增393配对，无新AP

[交付](../DataSet/paired_four_recording_expanded/index.html)、[报告与过早登记更正](../复现/camera-baseline/four-recording-paired-expansion-5229.md)。按[计划及导出前补充](archive/four-recording-paired-annotation-plan.md)，400候选实际双端审阅，393接受+7未决，24项修框后复看。新增4录音/3保守组，全进train；train3433/val961/test835，总5229对/42录音35组。旧4836行/图/框/角色与val/test文件字节保持，独立解码/hash/标注往返/raw像素/时间身份及12帧重提取通过。早期400/400接受说法撤回，不把几何有效当目视准入；最终事件与历史错误均保留。新增助手标注非专家GT/精密同步，无训练、模型推理或新AP；旧test和开发史继续披露，原研究10条test关闭。'''
    prepend(ROOT/'experiment/results.md','## 2026-11-14 paired_four_recording_expanded_5229',results_note)
    evaluation_note='''## 2026-11-14 新增393配对后的固定评价成员

当前数据版本[paired_four_recording_expanded](../DataSet/paired_four_recording_expanded/index.html)：5229对，train3433/val961/test835，42录音35保守组。新增393来自4录音/3组，全train；原4836角色/图/框保持，val/test索引和两端COCO与4836版字节相同。[协议](../DataSet/paired_four_recording_expanded/protocol.json)、[核验](../DataSet/paired_four_recording_expanded/independent-verification.json)、[报告](../复现/camera-baseline/four-recording-paired-expansion-5229.md)。COCO根与类别语义不变；新增相机框是助手新标注，声呐是助手可见回波框，非官方相机原标签/专家GT或精密同步认证。7未决无负样本标签且不在任何训练或COCO中。

保持4836版留出便于后续比较训练来源扩充；若研究覆盖效应，固定模型/初始化/训练预算/增广与评价成员，并同时报告样本数和来源数变化，不能把联合扩样差异说成单因素因果。旧4081/4836及旧模型结果保留，旧权重与当前留出的历史暴露边界不变，后续需fresh COCO。旧test评价及开发使用史保持，新test不称未触碰盲测；未授权新训练/模型test评价，原研究10test关闭。'''
    prepend(ROOT/'experiment/evaluation.md','## 2026-11-14 新增393配对后的固定评价成员',evaluation_note)
    handoff='''## 2026-11-14 四条新增录音双端扩充已交付：5229对/42录音

用户在全94审计后要求“继续”。本轮完成180126/124241/124440/125924各100个跨全程公开映射SD/raw候选的实际双端审阅，24项修框后相应页复看。最终100/100/93/100=393接受，124440序号17–23共7项声呐弱/破碎/空提案未决，不作负样本。新4录音/3保守组全train（124241/124440同组），DataSet/paired_four_recording_expanded/完整两端副本5229对，train3433/26录音22组、val961/9录音6组、test835/7录音7组；旧4836行manifest/图/框/角色全保留，val/test索引+COCO字节相同。新增相机assistant_labels是新助手标注，不误称original_labels或专家GT；精密同步未认证。报告复现/camera-baseline/four-recording-paired-expansion-5229.md，index.html有400身份逐对带框浏览和7未决。

重要错误留痕：早期finalizer把几何有效当目视接受，实际399+1但初稿称400/400且打印NameError；已撤回并保留premature-geometric-registration文件，旧脚本main现在阻止执行。review-decisions-final.json、review-summary-final.json权威393+7，普通入口已复制最终记录；旧报告及dataset/results末尾初稿标明作废。中间explicit-corrections因list别名漏4声呐修改，独立v2/v3差分重建explicit-corrections-final.json共24。勿再跑旧finalizer或把400当已接受。

独立核验：全部10458准入图像解码/hash、旧4836保持、393raw用PIL独立像素解码、COCO/YOLO全往返、组互斥、跨角色编码及像素hash重复0；400映射Decimal时间/精确fps复算、12固定首中末源SD独立重提取JPEG hash完全一致、源/旧输入不变。计划因导出补充有显式版本变更，旧hash由plan-before-export-amendment.md复核。HTML静态链接通过，真实浏览器未验证。tools/register_four_recording_final_decisions.py、export_four_recording_paired_expansion.py、verify_four_recording_paired_expansion.py、document_four_recording_paired_expansion.py可追踪全过程；完成产物不可直接重跑覆盖。

四条均L_to_R，只补bomb500/−34/roll90、grenade250/−42/roll90联合条件和grenade750/−22/roll0 Min15来源，未补mortar flyby/grenade−90 flyby。2897候选容量仅400实际审，其他未审。没有训练/模型推理/新AP；既有835test只副本及完整性访问，原研究10test关闭，旧评价/开发史不消除。后续若训练仍需授权和fresh COCO、固定本版train/val；下一步数据恢复162055有效共同窗口及11未登记视频具体ARIS对应，未计入本版。
'''
    prepend(ROOT/'handoff.md','## 2026-11-14 四条新增录音双端扩充已交付：5229对/42录音',handoff)
    # Mark the erroneous older entries in place, retaining their wording verbatim.
    for path,title in [(ROOT/'dataset.md','# 2026-11-14 四条录音双端候选：400个待准入样本'),
                       (ROOT/'experiment/results.md','# 2026-11-14 四条优先录音双端候选复核：400个待准入样本')]:
        text=path.read_text(encoding='utf-8');needle=title+'\n\n'
        if needle in text:text=text.replace(needle,title+'\n\n> 本条初稿已作废：400全部接受的说法错误，最终393接受、7未决；见本文顶部5229版更正。下文原样保留历史。\n\n',1)
        path.write_text(text,encoding='utf-8')
    # Freeze relevant scripts beside delivery, and a full local artifact hash index.
    (D/'provenance').mkdir(exist_ok=True)
    for name in ('prepare_four_recording_annotations.py','propose_four_recording_boxes.py',
                 'correct_four_recording_annotation_review.py','register_four_recording_final_decisions.py',
                 'export_four_recording_paired_expansion.py','verify_four_recording_paired_expansion.py',
                 'document_four_recording_paired_expansion.py'):
        shutil.copyfile(ROOT/'tools'/name,D/'provenance'/name)
    save(D/'artifact-sha256.json',{str(f.relative_to(D)).replace('\\','/'):sha(f)
        for f in D.rglob('*') if f.is_file() and f.name!='artifact-sha256.json'})
    print('Verified report, corrections, dataset, protocol and handoff published.',flush=True)


if __name__=='__main__':main()
