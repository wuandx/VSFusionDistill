"""Attach visual review evidence and concise delivery report without reassigning samples."""
from expand_paired_recording_pool import *
P=ROOT/'DataSet/expanded_paired_coverage_candidate'
def main():
    rs=read(P/'recordings.json');ev=read(P/'review-events.json')['events'];pool=read(OUT/'inventory.json')
    style='<style>body{font:16px/1.7 Microsoft YaHei,sans-serif;max-width:1400px;margin:25px auto;padding:12px}img{max-width:100%}article{padding:15px;border:1px solid #ccd;margin:20px 0}pre{white-space:pre-wrap}</style>'
    for rec in sorted({e['recording'] for e in ev}):
        ee=[e for e in ev if e['recording']==rec];accepted=[e['sample'] for e in ee if e['decision']=='accepted'];sheets=sorted({e['sheet'] for e in ee})
        body=f'<h1>{rec} 双端审阅记录</h1><p>本轮实际查看{len(ee)}项；助手接受{len(accepted)}项。用户尚未验收，非专家GT。图上框是当时的提案，只有下列接受身份的框进入扩充候选；其他框没有被接受。</p><p>接受身份：{", ".join(x.rsplit("_",1)[1] for x in accepted)}</p><p>{html.escape(ee[0]["reason"])}</p>'
        body+=''.join(f'<article><h3>{Path(sh).name}</h3><a href="{Path(sh).as_uri()}"><img loading="lazy" src="{Path(sh).as_uri()}"></a></article>' for sh in sheets)
        dest=OUT/'review-pages';dest.mkdir(exist_ok=True);(dest/(rec+'.html')).write_text('<!doctype html><meta charset="utf-8">'+style+body,encoding='utf-8')
    p=P/'index.html';text=p.read_text(encoding='utf-8')
    for rec in {e['recording'] for e in ev}:
        spec=(OUT/'full-review'/rec/'spec.json').as_uri()
        old=(ROOT/'DataSet/paired_assistant_mortar_late_review'/rec/'page-0072.jpg').as_uri()
        text=text.replace(spec,(OUT/'review-pages'/(rec+'.html')).as_uri()).replace(old,(OUT/'review-pages'/(rec+'.html')).as_uri())
    intro='<p style="background:#e6f3ee;padding:14px">推荐候选采用覆盖优先：所有留出录音的记录pan在同宽条件train内有≥95%落在±5°对应值内；比例优先草案另存但不推荐。155609地面val的z=1250而train为1000，属于跨高度评价；124735的ReceiverGain=15和Enable150V=0在同宽条件train未覆盖。记录pan不等于物理姿态。</p><p><a href="'+(OUT/'index.html').as_uri()+'">47条来源审计与未决项</a> · <a href="independent-verification.json">独立交付核验</a></p>'
    text=text.replace('<h2>宽条件覆盖</h2>',intro+'<h2>宽条件覆盖</h2>')
    p.write_text(text,encoding='utf-8')
    pending={r['recording']:r for r in pool if r['recording'] not in {x['recording'] for x in rs}}
    additions=[r for r in rs if r['old_role']=='not_in_old_30']
    lines=['# 扩充相机—声呐共用录音与覆盖优先划分','', '2026-11-13。状态：供用户审阅的候选，未激活、未启动训练。','',
      '## 更正范围与原因','',
      '原30条是此前为了组织每类10条、每条100对的局部基线样本形成的选择，不是原数据仅有30条，也不是可用共用录音的上限。先限制30条再均衡条件，遗漏了可补充条件的来源。前报告“当前30条中唯一floor”仅限该子集；源数据另有155609、160146、161916、162055地面录音。','',
      '用户明确优先相机与声呐共用录音，便于后续蒸馏。本轮检查原40开发来源与7条额外非原test来源，共47条；不以模型成绩选取，不读取原研究test的图像、视频、逐帧标注或预测。新增7条旧excluded仅因投影残差被挡住；该几何排除不等同可见回波标注不可用。','',
      '## 实际扩充','', '|新增录音|类别/场景|本轮接受对|候选角色|','|---|---|---:|---|']
    for r in additions:lines.append(f'|{r["recording"]}|{CLASSES[r["category"]]} / {r["placement"]} / {r["trajectory"]}|{r["selected"]}|{r["role"]}|')
    lines+=['', '新增7来源的700项提案已全部实际查看，接受5录音302对；174711和162055的200项现有提案全部未通过，主要框混入支架/横向地面回波，目标可辨，仍可修框，不把整条录音判定永久不可用。110049重新查看72–99共28项，按允许可辨截断政策接受16项。合计新增6录音318对。其他3条旧mortar仅抽页重看，未声称本轮全部复审或恢复。','',
      '旧3398对（3000选入/398备用）的身份、图像、原相机框、声呐框和选入标志全部保留。新318对全选入；故共3716助手接受对，其中3318选入、398备用。新增并非每条100，不凑满配额。全部新增用户验收0、专家确认0、精密同步认证0；training_ready=false。published matches支持来源配对，不认证精密时序。','',
      '## 推荐划分','', '|集合|录音/来源组|选入对|备用|炸弹/迫击炮/燃烧弹选入对|','|---|---|---:|---:|---|']
    for role in ('train','val','test'):
        rr=[r for r in rs if r['role']==role];lines.append(f'|{role}|{len(rr)} / {len({r["group_id"] for r in rr})}|{sum(r["selected"] for r in rr)}|{sum(r["reserve"] for r in rr)}|'+ ' / '.join(str(sum(r['selected'] for r in rr if r['category']==c)) for c in CLASSES)+'|')
    lines+=['', '比例服从实际覆盖：先以类别×摆放×运动×roll定义宽条件，所有宽条件在train；标准摆放按运动分组的z/tilt边际值在train覆盖；留出记录pan有≥95%能在同宽条件train找到圆周±5°对应值。满足这些后减少精确条件和设置缺口，再接近6:2:2，seed42 hash破同分。没有AP、预测或现模型表现参与分配。','',
      'repeat及原ARIS拆段保守同组：174200/174439、180506/180722、103728/103927、121124/121327、123841/124039、122608/122855。共36录音30来源组；不声称不同录音必是不同实物或完全独立采集批次。','',
      '- val：104749、105230、124735、155609。','- test：175506、101622、123841、124039；后两条同来源组，燃烧弹test只有一个来源组。','- 地面ellipse：160146、160551进train；155609进val。其z1250在train仅有z1000，因此只能称跨高度地面录音评价，不能称严格同条件。地面flyby161916仅train，没有独立同宽条件留出。','- 124735的名义条件在train124915出现，但ReceiverGain15、Enable150V0在同宽条件train未覆盖，是额外设置差异。','- 推荐候选8条holdout的pan支持95%–100%，只是所选帧的记录值覆盖，不等于3D姿态或相机物理视角覆盖。','- val中炸弹、燃烧弹各仅42对，来自可辨窗口；录音与样本数不均衡，后续必须同时报告pooled与逐录音结果，不能据其推断全轨迹或无目标误报率。','',
      '比例优先草案expanded_paired_split_candidate为22/7/7，保留但不推荐：地面holdout的pan支持仅43.4%/57.1%，部分条件缺相同roll下的高度/倾角。按计划追加覆盖约束后另建expanded_paired_coverage_candidate，未静默覆盖历史。','',
      '## 其余11录音未准入','',
      '5条历史配对不足173329、100927、101131、120653、120912不恢复；173615原相机框全部越界，尚未修正；旧105856、110229、110411的边界/可辨性疑问仍未解决；174711、162055现声呐提案需修框。未决不当负样本，未因扩量自动放行。','',
      '## 核验与产物','',
      '独立核验通过：3716身份唯一，旧3398框/图像/选入标志不变，7432导出图像hash和解码，700新增提案的源图/标签hash（含未决），原输入库存/metadata/clip/旧split hash均不变；原SD标签逐项等于导出框，YOLO坐标往返<1e-6像素，六份COCO类别/框/成员核对通过。录音与来源组互斥、跨角色图像内容hash无重复，36预览解码与静态链接核验通过。实际查看新增6录音导出首中末预览，不将预览替代逐帧审阅。浏览器渲染未验证。','',
      '- [推荐浏览页](../../DataSet/expanded_paired_coverage_candidate/index.html)','- [逐录音表](../../DataSet/expanded_paired_coverage_candidate/recordings.csv)','- [逐对manifest](../../DataSet/expanded_paired_coverage_candidate/manifest.json)','- [审阅事件](../../DataSet/expanded_paired_coverage_candidate/review-events.json)','- [核验](../../DataSet/expanded_paired_coverage_candidate/independent-verification.json)','- [47来源库存](../../DataSet/expanded_paired_recordings/index.html)','',
      '旧训练和模型不改。新test有开发审阅与历史使用，不能称全研究untouched；若确认此候选再冻结新版本，从COCO重新训练后比较，旧模型不用于宣称新版未见录音效果。']
    (ROOT/'复现/camera-baseline/expanded-paired-recordings.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    snapshot=P/'build-script.py';shutil_module=__import__('shutil');shutil_module.copyfile(ROOT/'tools/build_expanded_paired_split.py',snapshot)
    save(P/'artifact-sha256.json',{str(f.relative_to(P)):sha(f) for f in P.rglob('*') if f.is_file() and f.name!='artifact-sha256.json'})
    print('review pages, report and artifact hashes saved')
if __name__=='__main__':main()
