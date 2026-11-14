"""Document user-authorized partial camera targets without rewriting earlier exports."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'DataSet/paired_assistant_truncated_review/export'


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def prepend(path, heading, body):
    old = path.read_text(encoding='utf-8-sig')
    if heading not in old:
        path.write_text(heading + '\n\n' + body.strip() + '\n\n' + old, encoding='utf-8')


def main():
    audit = json.loads((OUT / 'provenance-audit.json').read_text('utf-8'))
    verify = json.loads((OUT / 'verification.json').read_text('utf-8'))
    summary = json.loads((OUT / 'summary.json').read_text('utf-8'))
    visibility = json.loads((OUT / 'camera-visibility.json').read_text('utf-8'))
    assert audit['status'] == verify['status'] == 'passed'
    qa = OUT.parent / 'preview-qa'
    save(qa / 'review-result.json', dict(status='completed', actually_viewed=True,
        sheet='new-truncated-previews.jpg', samples=[r['sample'] for r in json.loads((qa/'items.json').read_text('utf-8'))],
        observation='Four actual exported paired previews inspected: boundary transition, early/middle/late truncation. No obvious export coordinate/direction error.',
        limits='Export QA only; not independent expert accuracy or synchronization certification.'))
    page_path = OUT / 'index.html'
    page = page_path.read_text('utf-8')
    for sample, info in visibility.items():
        status = '相机底部截断' if info['truncated'] is True else '相机触底过渡'
        for role in ('选入', '备用'):
            before = f'<summary>{sample} — {role}</summary>'
            page = page.replace(before, f'<summary>{sample} — {role} · {status}</summary>')
    page_path.write_text(page, encoding='utf-8')

    readme = '''# 相机—声呐双端标注：允许可辨认的截断目标

2026-11-13。按用户要求重新审核182317，允许目标部分出画。**本版累计3398对助手接受：3000对选入，398对备用；30条录音各100，三类各1000。** 182317由31增至146，选100、备用46。旧3283对包原样保留。

| 类别 | 接受 | 选入 | 备用 |
|---|---:|---:|---:|
| 100lbs_aircraft_bomb | 1109 | 1000 | 109 |
| mortar_shell | 1204 | 1000 | 204 |
| incindiary_grenade | 1085 | 1000 | 85 |
| 合计 | 3398 | 3000 | 398 |

## 读取

- [带框配对浏览页](index.html)、[全部manifest](manifest.json)、[选入成员](selected-samples.txt)、[备用成员](reserve-samples.txt)。图像目录保存全部3398对，通过成员清单区分用途。
- 相机图`camera/images/{sample}.jpg`，声呐图`sonar/images/{sample}.png`，同名sample成对。
- 原相机JSON在`camera/original_labels/{sample}.json`；两侧分别有`labels_yolo/{sample}.txt`、`coco_all_reviewed.json`、`coco_selected.json`。
- COCO的file_name从本export目录解析；两侧共享image_id/sample。相机640×360，声呐原raw为128×441/603/780，不翻转。YOLO按各自图像宽高归一化。
- 类别沿用来源拼写：YOLO 0/1/2与COCO 1/2/3依次为100lbs_aircraft_bomb、mortar_shell、incindiary_grenade。

## 截断标记和框含义

新增115对全部实际查看两侧审核图；110明确相机底部截断，另5为触底过渡。相机剩余部分仍可辨、原框包围画面内可见部分，不推测画面外的完整物体。原相机JSON与框不修改。

[camera-visibility.json](camera-visibility.json)、manifest的camera_visibility及camera COCO annotation的attributes保存状态。`truncated_bottom/truncated=true`表示明确截断，`bottom_edge_transition/truncated=null`表示边界过渡。YOLO格式不承载截断字段，读取时通过sample关联sidecar。旧3283对缺少本次visibility字段表示“本次未重新分配截断状态”，不能当成全部未截断。

## 范围与限制

本轮审核182317全部146个已有原相机标签身份（ARIS140–285），对应相机播放器进度约0–9.94秒。用户指出的14秒画面可能也适合检测；那部分缺少原相机框，不在本次原标签复核成果中，不能冒称已标注。此范围已足够该录音选100，无需扩到14秒凑数。

时间对应未变；官方matches的incorrect gopro offset疑点仍保留。116对沿用既有窗口支持，3282对未独立核验精密同步。数量达到3000不代表CMHD几何标注方法复现或专家GT；本版直接审阅可见回波，并在已接受帧中均匀选最多100。未建立正式recording-level split、未训练或访问原test。

[完整性核验](verification.json)及[旧3283对保留审计](provenance-audit.json)通过：6796个模态框COCO/YOLO往返、3398个不同SD帧、两侧无完全重复像素。旧图/框/来源/审核全部保留；182317重新均匀选样使其旧31对中的10个从选入转备用，旧导出未改。新增导出预览已实际查看。

[复核报告](../../../复现/camera-baseline/paired-bomb-truncated-results.md) · [审核记录](../../paired_assistant_bomb_truncated/visual-review.json)。
'''
    (OUT / 'README.md').write_text(readme, encoding='utf-8')
    report = f'''# paired_bomb_truncated：纠正完整相机门槛，182317保留146对

2026-11-13。用户指出“目标检测也不一定需要完整图片”，并授权复核。按[事前计划](../../experiment/paired-bomb-truncated-plan.md)实际查看182317全部13页双端审核图、146个身份。**新增115接受；原31不动；合计146，选入100、备用46。新累计包3398接受、3000选入、398备用，30条各100，三类各1000。**

[新浏览页](../../DataSet/paired_assistant_truncated_review/export/index.html) · [使用说明](../../DataSet/paired_assistant_truncated_review/export/README.md) · [清单](../../DataSet/paired_assistant_truncated_review/export/manifest.json) · [完整性验证](../../DataSet/paired_assistant_truncated_review/export/verification.json) · [保留审计](../../DataSet/paired_assistant_truncated_review/export/provenance-audit.json)。旧[3283包](../../DataSet/paired_assistant_full_review/export/index.html)完整保留，历史结论未静默改写。

## 更正之前的说法

此前31及36上界都以“相机物体完整”为附加条件。用户目标是检测可见目标，这个条件过严：不能因为部分出画就排除。原库存数量和“完整相机帧上界36”的统计仍限于旧条件，不能当作可用检测样本上界。本轮只改变截断准入，不改时间/gantry/注册，也不把新结果归因给模型升级。

新增115为ARIS171–285，原camera框均到y=360；不是仅凭触边数值接受，而是逐图确认剩余的上部主体/头端可辨、原框包围画面内可见部分，并检查声呐主回波框。171–175为5个触底过渡，不武断记明确截断；176–285为110个明确底部截断。声呐沿用B候选边界，实际审核后接受，未按算法置信度自动放行。原31的修订边界不覆盖。

相机框定义为画面内可见部分，画面外范围不估计。原相机JSON与坐标均逐字节保留。新增manifest/review保存camera_visibility，camera COCO增加attributes，YOLO标签依旧通过sample关联[camera-visibility.json](../../DataSet/paired_assistant_truncated_review/export/camera-visibility.json)取截断状态。旧样本未重新赋状态，不允许将缺字段解读成未截断。

## 14秒与本次实际覆盖

全部原标签身份覆盖SD index0–298，即播放器约0–9.943秒；SD流PTS起点约7.378秒，末帧PTS17.321267秒。**流PTS不是播放器从0开始的进度**，不要混用。本次新增已覆盖到原标签末尾，足以选100对；播放器14秒附近仍可能是可用截断检测图，但没有原camera框，本次未新增该处相机标签，不能算入交付。

## 数量

| 类别 | 助手接受 | 选入 | 备用 | 满100录音 |
|---|---:|---:|---:|---:|
| bomb | 1109 | 1000 | 109 | 10 |
| mortar | 1204 | 1000 | 204 | 10 |
| grenade | 1085 | 1000 | 85 | 10 |
| 总计 | 3398 | 3000 | 398 | 30 |

本轮是在既有146身份上重审，不新增“已查看唯一身份”分母：累计仍为6273唯一身份，替代审核决定另存。相比旧包的接受增加115。与旧825待双端候选的唯一并集3827中仅3398为双端已接受，429仍待双端，不混算。

## 验证及限制

全3398对原图/hash/原相机JSON字节、声呐raw像素、6796个框COCO/YOLO往返通过；3398个不同SD帧，两侧没有完全重复像素。独立保留审计逐项比较旧3283对图像、框、时间/索引、来源和review，全部相同。新均匀选100让182317的旧31中10个转为备用，其他录音成员不变。camera COCO与sidecar的115个visibility一致。4个实际新增导出预览（175/205/240/285）已看，未见明显坐标/方向问题；这是导出QA，不是专家准确率估计。HTML仅做静态链接核验，未声称浏览器渲染通过。

manifest SHA256：`{verify['manifest_sha256']}`。复核脚本`tools/review_bomb_truncated.py`，累计导出`tools/export_paired_assistant_truncated.py`，保留审计`tools/audit_paired_assistant_truncated.py`；均保留旧版本。

本轮没有解决官方incorrect gopro offset疑点；116对保留既有checked_window支持、3282仍not_independently_checked，所有precision_sync_certified/expert_verified/training_ready保持false。可见目标一致不能证明精密同步。CMHD的3000数量达到，但本版直接回波标注和质量筛选后取样不同于论文几何投影及完整轨迹采样。无DS、原test读取、训练、新正式split、原研究目录/相机框/时间/注册变更。
'''
    (ROOT / '复现/camera-baseline/paired-bomb-truncated-results.md').write_text(report, encoding='utf-8')
    common = '''
用户明确允许可辨认的截断目标，纠正旧完整相机门槛。[新浏览页](DataSet/paired_assistant_truncated_review/export/index.html)、[结果](复现/camera-baseline/paired-bomb-truncated-results.md)。182317全146身份/13页本轮实际重看，新增115接受（110明确底部截断、5触底过渡），原31图/框/来源不变；该条146=100选入+46备用。累计3398=3000选入+398备用，30条各100、三类各1000；旧3283包保留，旧69缺额是旧准入历史，不再是当前数量。

新增camera_visibility与COCO attributes、YOLO关联sidecar；原相机JSON/框不动，旧样本缺新状态不表示全部未截断。全量3398原像素/字节/hash、6796框往返与去重通过；旧3283图/框/review/时间/来源全保留，仅182317旧10个选入标志转备用。4导出预览实际查看，HTML静态链接核验，未认证真实浏览器渲染。全部原标签只覆盖播放器0–9.94秒；14秒处无原camera框，本轮未新造框。精密同步疑点未解决（116窗口支持/3282未独立精密同步），非专家GT/CMHD标注方法复现/正式训练版本；无DS/test/训练/split/时间注册/原研究变更。
'''
    prepend(ROOT / 'handoff.md', '## 2026-11-13 当前交付更新：允许截断，3000选入＋398备用', common)
    prepend(ROOT / 'dataset.md', '## 2026-11-13 截断目标复核后累计3398对，选入3000对', common)
    for filename, heading in [('results.md', '## 2026-11-13 paired_bomb_truncated：新增115，数量达到3000选入'),
                               ('evaluation.md', '## 2026-11-13 截断准入更正及数量边界')]:
        prepend(ROOT / 'experiment' / filename, heading,
                common.replace('](DataSet/', '](../DataSet/').replace('](复现/', '](../复现/'))
    print(json.dumps(dict(status='documented', selected=3000, reserve=398)))


if __name__ == '__main__':
    main()
