"""Document the existing verified package and the user's accepted shortfall."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'DataSet/paired_assistant_full_review/export'
REPORT = ROOT / '复现/camera-baseline/paired-assistant-full-review-results.md'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(value, encoding='utf-8')


def save(path, value):
    write(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def prepend(path, heading, content):
    previous = path.read_text(encoding='utf-8-sig')
    if heading not in previous:
        write(path, heading + '\n\n' + content.strip() + '\n\n' + previous)


def main():
    rows = read(OUT / 'manifest.json')
    summary = read(OUT / 'summary.json')
    verification = read(OUT / 'verification.json')
    audit = read(OUT / 'provenance-audit.json')
    manifest_hash = sha(OUT / 'manifest.json')
    assert verification['status'] == audit['status'] == 'passed'
    assert manifest_hash == verification['manifest_sha256']
    assert len(rows) == summary['accepted_pairs'] == 3283
    selected = [r for r in rows if r['selected_for_100_per_recording']]
    reserve = [r for r in rows if not r['selected_for_100_per_recording']]
    assert len(selected) == 2931 and len(reserve) == 352
    assert audit['prior_885_retained_exact'] == 885
    assert summary['recordings_with_100'] == 29

    write(OUT / 'selected-samples.txt', ''.join(r['sample'] + '\n' for r in selected))
    write(OUT / 'reserve-samples.txt', ''.join(r['sample'] + '\n' for r in reserve))
    decision = {
        'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
        'user_decision': '保留现有数量，明确报告缺额（推荐）',
        'scope': 'Retain the existing package and report the shortfall; no quota-driven expansion.',
        'assistant_reviewed_accepted_pairs': 3283,
        'selected_pairs': 2931,
        'reserve_pairs': 352,
        'recordings_with_100': 29,
        'short_recording': '2023-09-20_182317',
        'short_recording_selected': 31,
        'shortfall_to_cmhd_3000': 69,
        'cmhd_exact_count_met': False,
        'user_expert_approval_of_all_annotations': False,
        'precision_sync_certified': False,
        'formal_split_created': False,
        'manifest_sha256': manifest_hash,
    }
    save(OUT / 'delivery-decision.json', decision)

    qa_root = OUT.parent / 'preview-qa'
    items = read(qa_root / 'items.json')
    sheets = sorted(qa_root.glob('new-recordings-*.jpg'))
    assert len(items) == 20 and len(sheets) == 5
    assert len({x['recording'] for x in items}) == 20
    for item in items:
        assert sha(OUT / item['preview']) == item['preview_sha256']
    save(qa_root / 'review-result.json', {
        'status': 'completed',
        'reviewer': 'assistant',
        'actual_viewing': 'All five sheets were visually inspected in the preceding continuation of this task.',
        'preview_count': 20,
        'new_recording_count': 20,
        'sheets': [{'path': p.name, 'sha256': sha(p), 'viewed': True} for p in sheets],
        'items_sha256': sha(qa_root / 'items.json'),
        'observation': 'No obvious export rendering or coordinate error in the inspected paired previews.',
        'limits': 'Export QA only; not an independent annotation accuracy estimate or synchronization certification.',
    })

    class_rows = []
    for category in ('100lbs_aircraft_bomb', 'mortar_shell', 'incindiary_grenade'):
        accepted = summary['by_category'][category]
        n = audit['selected_by_category'][category]
        full = audit['recordings_with_100_by_category'][category]
        class_rows.append(f'| {category} | {accepted} | {n} | {accepted-n} | {full} | {1000-n} |')
    class_table = ('| 类别 | 助手接受 | 选入 | 备用 | 满100条数 | 距每类1000缺额 |\n'
                   '|---|---:|---:|---:|---:|---:|\n' + '\n'.join(class_rows) +
                   '\n| 合计 | 3283 | 2931 | 352 | 29 | 69 |')
    recording_table = ('| recording | 类别 | 助手接受 | 选入 | 备用 | 缺额 |\n'
                       '|---|---|---:|---:|---:|---:|\n' + '\n'.join(
                           f"| {r['recording']} | {r['category']} | {r['accepted']} | {r['selected']} | {r['reserve']} | {r['shortfall']} |"
                           for r in summary['recordings']))

    write(OUT / 'README.md', f'''# 相机—声呐双端助手审核包

2026-11-13。已导出 **3283对**，每对包括相机图、声呐图及两侧框；按每录音最多100对选入 **2931对**，另有 **352对备用**。29条各100，2023-09-20_182317为31，距CMHD的30条×100缺69。用户已选择“保留现有数量，明确报告缺额”，本版据此收口。

{class_table}

## 打开与读取

- [配对带框浏览页](index.html)：按录音展开查看两侧带框预览。
- [manifest.json](manifest.json)：3283对的sample、录音、ARIS/SD索引、两侧框、源路径、哈希和审核决定。
- [selected-samples.txt](selected-samples.txt)：2931个选入sample，一行一个；[reserve-samples.txt](reserve-samples.txt)为352个备用sample。这是取样成员清单，尚非train/val/test划分。
- 相机：`camera/images/{{sample}}.jpg`；原JSON：`camera/original_labels/{{sample}}.json`；YOLO：`camera/labels_yolo/{{sample}}.txt`。
- 声呐：`sonar/images/{{sample}}.png`；YOLO：`sonar/labels_yolo/{{sample}}.txt`。
- 两侧分别有`coco_all_reviewed.json`和`coco_selected.json`。COCO的`file_name`从本export目录解析，两侧共享image_id和sample。

图像目录包含全部3283对，选入与备用通过清单区分。同一sample的两侧图像和标签相互对应。相机保留原SD 640×360像素与原框；声呐宽128、高441/603/780，使用各自原始raw坐标，未翻转、未缩放标签。预览增益仅用于显示。两传感器左右看似相反不作为翻转原图的依据。

| 类别名称（沿用来源拼写） | YOLO class | COCO category_id |
|---|---:|---:|
| 100lbs_aircraft_bomb | 0 | 1 |
| mortar_shell | 1 | 2 |
| incindiary_grenade | 2 | 3 |

manifest的xyxy为像素边缘坐标；COCO为像素xywh；YOLO为按各模态自身宽高归一化的中心xywh。声呐框表示助手审阅的可见目标回波范围，可能包含轴对齐矩形内部无法排除的支架交叠；不等同于3D完整物体投影。

## 配对与使用边界

配对沿用已有ARIS—SD关联，并实际审阅两侧可见目标。116对保留既有`supported_in_checked_window`记录，3167对仍为`not_independently_checked`；视觉一致不认证精密时间同步或gantry。182317的原matches还记有`incorrect gopro offset`疑点，本版保留此限制，未改对应。助手接受不等于专家GT或用户逐框验收；尚未冻结正式训练版本或recording-level split。

CMHD为几何投影加人工异常检查，3000对来自3类各10条完整轨迹×100；本版为可辨帧直接审阅、在接受序列上均匀取最多100，方法和采样偏向均有差异。CMOLD约4700对是训练与验证合计。论文原文、方法边界及逐录音数量见[累计报告](../../../复现/camera-baseline/paired-assistant-full-review-results.md)。

## 可复核证据

[全量文件核验](verification.json)、[血缘与旧885对保留核验](provenance-audit.json)、[34条审核覆盖](all-recording-coverage.json)、[用户数量决定](delivery-decision.json)、[导出预览QA](../preview-qa/review-result.json)。6566个框的COCO/YOLO往返通过；两侧无完全重复像素；原相机图/JSON字节与声呐raw像素保持一致。旧885对的框和来源保留；加入新接受帧重新均匀选样后，其中10个身份的选入/备用标志改变，旧导出未修改。

manifest SHA256：`{manifest_hash}`。
''')

    page_path = OUT / 'index.html'
    page = page_path.read_text(encoding='utf-8')
    marker = '<!-- delivery-decision-note -->'
    if marker not in page:
        note = (marker + '<section style="background:#fff4d8;padding:16px;border:1px solid #c78d24">'
                '<strong>本版数量已按用户决定保留：2931对选入，352对备用。</strong>'
                '<p>29条录音各100对；2023-09-20_182317为31对，缺69对。用户选择“保留现有数量，明确报告缺额”。'
                '未达到CMHD严格的30条×100，未认证精密同步或专家GT。</p>'
                '<p><a href="README.md">使用说明与类别映射</a> · '
                '<a href="selected-samples.txt">2931对成员</a> · '
                '<a href="reserve-samples.txt">352对备用</a> · '
                '<a href="provenance-audit.json">血缘审计</a> · '
                '<a href="../../../复现/camera-baseline/paired-assistant-full-review-results.md">累计报告</a></p></section>')
        page = page.replace('</h1>', '</h1>' + note, 1)
        write(page_path, page)

    write(REPORT, f'''# paired_assistant_full_review：2931对选入、352对备用，按用户决定保留缺额

2026-11-13。按[事前计划](../../experiment/paired-assistant-mortar-plan.md)完成持续双端审核、并行补充、独立库存核查和累计导出。**本版3283对助手接受：2931对选入，352对备用；29条各100，最后一条bomb为31，缺69。** 用户已明确选择“保留现有数量，明确报告缺额（推荐）”，不再以3000配额推动扩库、改时间或降低边界要求。这一决定仅接受数量缺额，不代表用户已逐框验收全部标注。

[浏览入口](../../DataSet/paired_assistant_full_review/export/index.html) · [使用说明](../../DataSet/paired_assistant_full_review/export/README.md) · [manifest](../../DataSet/paired_assistant_full_review/export/manifest.json) · [数量](../../DataSet/paired_assistant_full_review/export/summary.json) · [完整性核验](../../DataSet/paired_assistant_full_review/export/verification.json) · [血缘核验](../../DataSet/paired_assistant_full_review/export/provenance-audit.json)。

## 实际数量

{class_table}

接受总数超过3000，仍不能用其他录音的备用替代182317的69个缺额。选入成员是在每条已接受序列上均匀取最多100，不是新增正式split。两侧同名图像、原相机JSON、两侧YOLO与COCO均已导出；没有只交声呐单边。

39个命名审核根中累计有8260条当前候选决定，去重后实际查看6273个sample身份；不同提案的重复审核不计新增样本。3283个接受身份全部有对应实际审核图及决定。相比旧885包，新增2398个接受身份。审核覆盖34条录音，接受分布在30条；另外4条mortar的全部允许来源候选已看但当前0接受，保留未决，不作为负样本或声称在所有新标注方法下都不可能可用。

{recording_table}

## 182317为什么只有31

[独立库存报告](bomb182317-camera-coverage-audit.md)复核本地与已保存官方归档catalog：gopro与ARIS各501张（140–640），原camera JSON仅146个（140–285），恰好覆盖现有temporal/source-inventory全部身份；292个原图和JSON的大小/CRC与归档目录一致，SHA与temporal输入记录一致。未重新下载整个归档。

现行时间关联下0–139映射为负SD索引，原归档也没有这些原camera导出与标签；286–640虽有图但缺原camera框，不能记作已标注库存遗漏。已有146张SD图全部实际看过，176以后明显截断且未重新完整进入画面；即使宽松纳入140–175，完整相机候选上界仍只有36。36是上界，实际双端接受31。原matches注明`incorrect gopro offset`，本轮未据数量擅改时间，也没有用注册补偿。结论只适用于现行对应、原标签和完整相机条件。

## 标注方法、方向和配对边界

保留原SD相机图与原框，声呐直接在raw坐标审阅可见目标回波框。B/E/G/K等算法与手工边界只是候选，必须实际查看两侧审核图后才接受；失败候选、撤销事件和替代提案均保存。K用于避免中央支架的外部延伸主导端点；grenade完整环P修订先前裁掉下环的候选，保留旧失败。轴对齐框内部支架交叠不能自动等同于框向外多扩，仍按可见边界逐帧判断。

声呐raw不翻转；相机640×360，声呐128×441/603/780；导出坐标按各模态自身尺寸归一化。用户提出的左右看似相反已作为显示方向说明保留，不靠翻图改标签或伪造几何一致。

沿现有ARIS—SD配对关联图像并做可见目标一致性审阅，不等于独立时间认证。116对保留既有checked window支持；3167对仍为`not_independently_checked`。所有样本`precision_sync_certified=false`、`expert_verified=false`、`training_ready=false`。原时间、gantry、3D注册、相机框、原研究目录和原test均未修改或用于新测评。

## 论文规模对照

| 论文/来源 | 数量事实 | 证据与限制 |
|---|---|---|
| CMHD §3.1 | 3000对；3类各10轨迹×100；按轨迹6:2:2为1800/600/600 | [原JATS XML](../../related_work/recording-split-review-20261111/cmhd-fulltext.xml)，不是LaTeX；具体录音/帧号/seed未公开 |
| CMOLD §IV-A | 约4700对训练和验证合计 | [保存的PDF正文抽取](../../related_work/cmold/evidence-existing/cmold_numbered.txt)第575行；不是4700训练对，不能套用CMHD划分 |
| 原UXO，CMHD §3.1转述 | 95轨迹、74437声呐帧、48462配相机、37278相机帧有框 | 全集口径，不是本版允许开发录音或已接受数量 |

CMHD声呐框来自3D投影与人工异常检查；本版为可见回波直接审阅，且在质量筛选后的接受序列取样。两者标注方法、可见性偏向与录音选择不相同。论文允许残余误差不能为系统性错位开脱，本版没有以该描述追认时间或几何链。相关原文与先前数量审计见[paired-paper-scale.md](paired-paper-scale.md)。

## 验证结果及失败留痕

- 全3283对源/输出/审核图hash通过，声呐原像素精确，相机与原JSON字节精确；3283个不同SD帧，两模态均无完全重复像素。
- 6566个模态框的COCO/YOLO往返通过，两侧COCO身份一致。
- 旧885对的图像、框和源字段全部保留。添加新接受帧后重新均匀取样，使其中10个sample的选入/备用标志变化；这不改变旧框，旧导出原样保留。
- 对全部决定（含未决）核对审核图及原图/相机标签hash。260条旧审核项未在spec内保存相机label hash，改对权威temporal原标签hash核验，通过；不是补造旧hash字段。
- 第一次追加审计因假定旧spec都有`camera_label_sha256`而抛KeyError，修正审计读取后通过。失败记在[provenance-audit-attempts.jsonl](../../DataSet/paired_assistant_full_review/export/provenance-audit-attempts.jsonl)，未改图、框或决定。
- 20条新增录音各一个实际导出预览，组成5页，全部实际查看，未见明显导出方向/坐标问题；[QA记录](../../DataSet/paired_assistant_full_review/preview-qa/review-result.json)。这是导出QA，不是独立准确率估计。HTML静态链接另核对，实际浏览器渲染未作为通过证据。

manifest SHA256：`{manifest_hash}`。

与旧825待双端候选重叠334，唯一并集3774=3283双端已审+491仅旧声呐待双端；不能合并为3774已接受。所有助手接受仍非专家真值。冻结的是本次交付清单和来源，不是正式训练/测评准入。

## 模型复核与交接

用户换用6.1-sol后，同12对旧G提案的当前判断与旧决定12/12一致；这是非盲局部复核，没有独立专家真值，不能断言视觉整体变好。更多接受量来自继续查看及候选边界修订，不能归因于模型升级。[同提案记录](../../DataSet/paired_assistant_mortar/model-recheck/same-proposal-review.json)。

细分报告：[root mortar](paired-assistant-mortar-results.md)、[bomb](paired-bomb-remaining-review.md)、[grenade](paired-grenade-remaining-review.md)、[grenade完整环](paired-grenade-complete-ring.md)、[后段mortar](paired-mortar-late-review.md)、[mortar独立QA](paired-mortar-independent-qa.md)。所有并行审核已结束，本轮未调用DS。导出脚本`tools/export_paired_assistant_full_review.py --verify-only`可重验；血缘脚本`tools/audit_paired_assistant_full_review.py`；说明脚本`tools/document_paired_assistant_full_review.py`只补交付文档及成员清单。

本次数据交付按用户数量决定收口。后续若开展训练，应单独冻结标签语义、配对准入、recording-level split与历史开发使用边界；当前未启动训练、未新划分、未读原test，不自动分出600对称未触碰test。
''')

    prepend(ROOT / 'handoff.md', '## 2026-11-13 最新累计配对交付：2931选入＋352备用，用户接受69缺额', '''
按research-workflow收口本次双端标注交付。[浏览页](DataSet/paired_assistant_full_review/export/index.html)、[使用说明](DataSet/paired_assistant_full_review/export/README.md)、[累计报告](复现/camera-baseline/paired-assistant-full-review-results.md)。累计6273唯一身份实际看过、3283接受（bomb994/mortar1204/grenade1085），每录音最多100选2931、备用352。29条各100；182317为31，缺69，用户明确选择“保留现有数量，明确报告缺额”。不再默认追3000；接受该缺额不等于逐框专家验收。

新2398接受，旧885图像/框/来源全保留；重新均匀选样令旧10个身份选入/备用标志变化，旧包未改。3283对全量像素/字节/hash、6566框往返、无完全重复像素与血缘核验通过；20新增录音实际导出预览全看。追加审计先遇旧spec缺label hash的KeyError，改读权威temporal hash后通过，失败保留。manifest hash与核验在新包，源决定已冻结。39审核根、8260候选决定；四条0接受mortar的允许池全看，未决不作负样本。

182317全部146原标注身份与官方归档catalog一致，完整相机宽松上界36、实际双端31；matches已有incorrect gopro offset疑点，未据配额改时间。116对沿用checked_window支持、3167未独立精密同步核对；全包非专家GT/正式训练版本。与旧825并集3774只3283双端已审，491待双端。没有DS/时间注册/原框/正式split/test/训练变更；实际浏览器渲染未验。三并行任务和本次导出审计均结束，无待跑批次。6.1-sol同12旧G提案12/12同判，非盲不能证明整体更优。下列其他注册/RGB任务历史继续保留，未被本次直接标注交付解决。
''')
    prepend(ROOT / 'experiment/results.md', '## 2026-11-13 paired_assistant_full_review：3283接受，2931选入，缺69按用户决定保留', '''
按[事前计划](paired-assistant-mortar-plan.md)持续双端审核与并行补充，累计6273唯一身份实际查看、8260候选决定、3283接受；新增2398，bomb994/mortar1204/grenade1085。29条各100另182317为31，选2931/备用352；用户选择保留现有数量并报告69缺额。全3283对完整性、6566框往返、两侧无重复像素和旧885图/框/来源保留通过；10个旧身份重采样改变选入标志，旧包未改。20新增录音导出预览全看。追加审计旧spec缺hash的KeyError已修正读取并留失败记录。无DS/时间注册/正式split/test/训练；配对精密同步与专家GT未认证。[完整结果](../复现/camera-baseline/paired-assistant-full-review-results.md)。
''')
    prepend(ROOT / 'experiment/evaluation.md', '## 2026-11-13 paired_assistant_full_review 交付边界', '''
本次固定交付3283对助手双端接受、2931选入/352备用：29条各100，182317为31，用户明确接受数量缺额69。不是CMHD严格3000/完整轨迹抽样或几何标注复现；保留缺额不等于专家GT或正式训练准入。116对沿用checked_window支持、3167未独立精密同步认证，所有precision_sync_certified/expert_verified/training_ready均false。未决不作负样本；相机原SD框与声呐raw方向保留，边界语义为可见回波。旧885接受/框/来源保留，但重新均匀取样改变10个旧身份选入/备用标志，必须使用本版成员清单。未建正式recording-level split、未训练/读原test/改时间gantry注册。数量收口不解决其他物理注册疑点。[报告](../复现/camera-baseline/paired-assistant-full-review-results.md)。
''')
    prepend(ROOT / 'dataset.md', '## 2026-11-13 最新双模态标注交付：2931选入，352备用', '''
[paired_assistant_full_review](DataSet/paired_assistant_full_review/export/index.html)含3283对同名相机/声呐图、原相机JSON、两侧COCO/YOLO、逐帧血缘和全量验证。[使用说明](DataSet/paired_assistant_full_review/export/README.md)及selected/reserve成员清单均已提供。bomb994/mortar1204/grenade1085接受；选931/1000/1000，共2931，另352备用。29条足100，182317仅31，用户已选择保留69缺额。旧885图/框/来源保留，旧包未动；重选样令10个旧身份成员标志变化。

6273唯一身份实际看过；3283不同SD帧、6566框往返、原像素/原相机图JSON字节及血缘核验通过，两侧无完全重复像素。20条新增录音实际预览全看。相机640×360，声呐128×441/603/780不翻转；116沿用窗口支持、3167未独立精密同步认证，全包非专家GT/正式训练版本。与旧825并集3774中491仍待双端复核。原时间/gantry/注册/相机标签/正式split/test/训练未变。[累计报告](复现/camera-baseline/paired-assistant-full-review-results.md)含官方库存核查、论文数量原文和全部30条统计。
''')
    assert sha(OUT / 'manifest.json') == manifest_hash
    print(json.dumps({'status': 'documented', 'selected': len(selected),
                      'reserve': len(reserve), 'manifest_unchanged': True}))


if __name__ == '__main__':
    main()
