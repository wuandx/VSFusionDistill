"""Publish saved diagnostics and written visual reviews; never changes projections."""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import html
import json
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'DataSet/sonar_fixed_mesh'
SIGN = ROOT / 'DataSet/sonar_fixed_mesh_beam_sign'


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def save(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fmt(values, n=2):
    return '空' if values is None else ' / '.join(f'{v:.{n}f}' for v in values)


def counts(items):
    c = Counter(x['status'] for x in items)
    return {k: c[k] for k in ('aligned', 'partial', 'misaligned', 'uncertain')}


datasets = []
for p in (BASE, SIGN):
    result = read(p / 'results.json')
    qa = read(p / 'qa-after-projection.json')
    independent = read(p / 'independent-visual-qa.json')
    verification = read(p / 'independent-verification.json')
    assert verification['passed']
    ids = [x['sample'] for x in result['outputs']]
    assert len(ids) == len(set(ids)) == 18
    assert set(ids) == {x['sample'] for x in qa['items']} == {x['sample'] for x in independent['items']}
    assert sha(p / 'fixed-mesh-transforms.json') == result['fixed_transform_sha256']
    datasets.append(dict(path=p, result=result, rows=result['outputs'], qa={x['sample']: x for x in qa['items']},
                         independent={x['sample']: x for x in independent['items']},
                         counts=counts(qa['items']), independent_counts=counts(independent['items'])))

assert (BASE / 'fixed-mesh-transforms.json').read_bytes() == (SIGN / 'fixed-mesh-transforms.json').read_bytes()
models = read(BASE / 'fixed-mesh-transforms.json')['models']
records = list(dict.fromkeys(x['recording'] for x in datasets[0]['rows']))
summary = {
    'run': 'sonar_fixed_mesh_review_complete',
    'status': 'diagnostic projections and visual QA completed; no class approved for training GT',
    'unique_identities': 18, 'recordings': 6, 'models': 3, 'projection_versions': 2,
    'fixed_transform_sha256': sha(BASE / 'fixed-mesh-transforms.json'),
    'mesh_transform_revisions': 0, 'per_frame_model_adjustments': 0, 'echo_fits': 0,
    'approved_training_boxes': 0, 'expert_human_review_performed': False,
    'assistant_visual_review_performed': True, 'test_images_read': 0, 'training_runs': 0,
    'versions': [],
    'limitations': [
        'Assistant visual QA, not expert manual ground truth; no independent annotated IoU or AP.',
        'Both versions use the same already-seen development identities; this is not a blind holdout experiment.',
        'Beam ordering is documented; the optical interpretation of the sonar axes still needs a physical control.',
        'PCA origin/orientation, target placement across recordings, vertical FOV and acoustic boundary are unverified.',
        'The fan display has its own pixel geometry and is not the official polar2 raster.'
    ]
}
for d in datasets:
    disagreements = [dict(sample=s, root=q['status'], independent=d['independent'][s]['status'])
                     for s, q in d['qa'].items() if q['status'] != d['independent'][s]['status']]
    summary['versions'].append(dict(run=d['result']['run'], main_qa_counts=d['counts'],
                                    independent_qa_counts=d['independent_counts'], disagreements=disagreements))
    with (d['path'] / 'candidate-boxes.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['sample','recording','model','historical_role','main_qa','independent_qa',
                         'raw_width','raw_height','x_min','y_min','x_max','y_max','range_min_m','range_max_m',
                         'beam_az_min_deg','beam_az_max_deg','elev_min_deg','elev_max_deg',
                         'sample_fraction_visible_7deg','sample_fraction_visible_7_5deg','approved_for_training_gt'])
        for r in d['rows']:
            writer.writerow([r['sample'],r['recording'],r['model'],r['historical_role'],d['qa'][r['sample']]['status'],
                d['independent'][r['sample']]['status'],r['raw_shape_hw'][1],r['raw_shape_hw'][0],
                *(r['visible_raw_bbox_padded_clipped_xyxy'] or ['', '', '', '']),*r['mesh_range_m'],*r['mesh_azimuth_deg'],
                *r['mesh_elevation_deg'],r['fraction_visible_assumed_7deg'],r['fraction_visible_assumed_7_5deg'],False])
save(BASE / 'run-summary.json', summary)
save(BASE / 'revision-log.json', {
    'revisions': [
        {'name':'sonar_fixed_mesh','action':'Created one frozen s/R/t per model and 18 initial projections; kept all failures.'},
        {'name':'initial_visual_review_correction','action':'0456 bomb and 0909 mortar downgraded to uncertain; initial notes preserved.',
         'details':'qa-after-projection.json: corrections_to_initial_review'},
        {'name':'sonar_fixed_mesh_beam_sign','action':'Changed only 3D azimuth to beam angle sign; frozen mesh bytes and poses retained.',
         'plan':'../../experiment/sonar-fixed-mesh-beam-sign-plan.md','result':'../sonar_fixed_mesh_beam_sign/results.json',
         'basis':'Official raw beam ordering and matching camera/sonar rotation; physical axis control still missing.'},
        {'name':'review_complete','action':'All 18 identities reviewed for both versions by two assistants; disagreements retained, zero GT approvals.'}
    ], 'immutable_generation_state': 'results.json retains its original awaiting-QA wording; run-summary.json records completed QA.'
})

esc = html.escape
parts = ['''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>固定 mesh 声呐投影 · 18 帧复核</title><style>
body{font-family:system-ui,"Microsoft YaHei",sans-serif;margin:0;background:#f0f3f7;color:#1b2737;line-height:1.6}
header,main{max-width:1350px;margin:auto;padding:22px}header{background:#fff;border-bottom:3px solid #24446c}
h1{font-size:26px;margin:0 0 10px}h2{font-size:20px}p{margin:9px 0}a{color:#1554a5}code,pre{font-size:12px;overflow:auto}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #cbd3dd;padding:7px;text-align:left}
.controls{position:sticky;top:0;background:#fff;padding:12px;z-index:2;border:1px solid #ccd5df;display:flex;gap:14px;flex-wrap:wrap}
select{font-size:15px;padding:5px}.card{background:#fff;border:1px solid #ccd5df;border-radius:8px;margin:18px 0;padding:18px}
.panels{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.panels figure{margin:0}.panels img{width:100%;height:500px;object-fit:fill;background:#000}
figcaption{font-size:13px;font-weight:600}.fan{display:flex;gap:14px;justify-content:center}.fan img{height:440px;max-width:48%;object-fit:contain;background:#000}
.badge{font-weight:650;padding:2px 7px;border-radius:4px;background:#eee}.misaligned{background:#ffe1db}.partial{background:#fff0c4}.uncertain{background:#e6e9ef}.aligned{background:#ccebd9}
.notice{background:#fff3d5;border-left:4px solid #b87710;padding:12px}.muted{color:#576578;font-size:13px}.metrics{display:grid;grid-template-columns:1fr 1fr;gap:12px}
details{margin:10px 0}summary{cursor:pointer;font-weight:600}[hidden]{display:none!important}
@media(max-width:760px){.panels{grid-template-columns:1fr}.panels img{height:560px}.metrics{grid-template-columns:1fr}.fan img{height:300px}}
</style></head><body><header><h1>固定 mesh → target · 声呐投影与逐图 QA</h1>
<p>3 类模型 × 每类 2 条录音 × 首 / 中 / 末，共 <b>18 个固定身份</b>。每类只用一套 s/R/t；两版均无逐帧移动模型。</p>
<p class="notice">已完成几何重放和两轮 assistant 目视复核；<b>目前 0 个正式训练框准入</b>。方位反号候选改善了多帧方向，仍有位置、边界和可见性疑点。这里不是专家人工真值。</p>
<p>初版 beam = atan2(x,z)；修订候选 beam = −atan2(x,z)。修订依据为官方 beam 从右向左编号及相机/声呐轴关系，模型变换字节不变。两版原图完全相同，失败全部保留。</p>
<p>绿色：距离、beam 和假设 ±7° 垂直视场内的网格采样及框。橙色：未加垂直门限的几何。框不包含声学散射/遮挡/阴影模型。比例是采样点占比，不是表面积占比。</p>
''']
parts.append('<p>' + ' · '.join(f'<a href="{href}">{label}</a>' for href,label in [
    ('fixed-mesh-transforms.json','固定变换与依据'),('run-summary.json','汇总和分歧'),('revision-log.json','修订记录'),
    ('results.json','初版数值'),('../sonar_fixed_mesh_beam_sign/results.json','反号候选数值'),
    ('independent-verification.json','初版独立复算'),('../sonar_fixed_mesh_beam_sign/independent-verification.json','候选独立复算'),
    ('qa-before-projection.json','最初无框观察'),('qa-after-projection.json','初版主QA'),('independent-visual-qa.json','初版独立QA'),
    ('../sonar_fixed_mesh_beam_sign/qa-after-projection.json','候选主QA'),('../sonar_fixed_mesh_beam_sign/independent-visual-qa.json','候选独立QA'),
    ('candidate-boxes.csv','初版候选框CSV'),('../sonar_fixed_mesh_beam_sign/candidate-boxes.csv','候选框CSV'),
    ('../../'+quote('复现/camera-baseline/sonar-fixed-mesh.md'),'完整报告')]) + '</p>')
parts.append('<table><tr><th>版本 / 复核者</th><th>aligned</th><th>partial</th><th>misaligned</th><th>uncertain</th></tr>')
for d in datasets:
    for label,key in [('主复核','counts'),('独立复核','independent_counts')]:
        parts.append(f'<tr><td>{d["result"]["run"]} / {label}</td>'+''.join(f'<td>{n}</td>' for n in d[key].values())+'</tr>')
parts.append('</table><p class="muted">复核分歧未强行合并。partial 也未通过训练准入；这不是客观标注精度或 AP。两版使用已观察的开发帧，不是盲验。</p>')
parts.append('<details><summary>三类模型的固定尺度、旋转、平移与假设</summary>')
for name,m in models.items():
    parts.append(f'<h3>{name}</h3><p>s = {m["scale_m_per_obj_unit"]:.14g} m / OBJ unit；t = [{fmt(m["translation_target_from_mesh_m"],9)}] m；尺寸 = [{fmt(m["target_mesh_extent_m"],6)}] m。</p><pre>R = {esc(json.dumps(m["rotation_target_from_mesh"],indent=2))}</pre>')
parts.append('<p>名义全长来自历史 README；PCA 长轴→target +x、第二轴定 roll、极值中点→原点以及同类两录音共用静态 target 位姿，均为我方假设。完整来源及 hash 见固定变换 JSON。</p></details></header><main>')
parts.append('<div class="controls"><label>录音 <select id="recording"><option value="all">全部 6 条</option>'+''.join(f'<option>{r}</option>' for r in records)+'</select></label><label>候选主QA <select id="status"><option value="all">全部状态</option><option>misaligned</option><option>partial</option><option>uncertain</option><option>aligned</option></select></label><span id="count">显示 18 / 18 帧</span></div>')
for old,new in zip(datasets[0]['rows'],datasets[1]['rows']):
    sid = old['sample']; assert sid==new['sample']
    oq,nq=datasets[0]['qa'][sid],datasets[1]['qa'][sid]
    oi,ni=datasets[0]['independent'][sid],datasets[1]['independent'][sid]
    parts.append(f'<article class="card" data-recording="{old["recording"]}" data-status="{nq["status"]}" id="{sid}"><h2>{sid} · {old["model"]}</h2>')
    parts.append(f'<p>主QA：初版 <span class="badge {oq["status"]}">{oq["status"]}</span> → 候选 <span class="badge {nq["status"]}">{nq["status"]}</span>；独立QA：{oi["status"]} → {ni["status"]}。历史角色 {old["historical_role"]}。</p>')
    parts.append('<div class="panels">')
    for href,label in [(f'frames/{sid}-raw.png','原图'),(f'frames/{sid}-raw-overlay.png','初版 +atan2'),(f'../sonar_fixed_mesh_beam_sign/frames/{sid}-raw-overlay.png','反号候选 −atan2')]:
        parts.append(f'<figure><figcaption>{label}</figcaption><a href="{href}"><img src="{href}" loading="lazy" alt="{sid} {label}"></a></figure>')
    parts.append(f'</div><p class="muted">三列均显示完整原图（{old["raw_shape_hw"][1]}×{old["raw_shape_hw"][0]}），横纵显示比例调整以便比较；不是裁剪。点图可看原像素。原始图向下距离增大，向右 beam 编号增大。</p>')
    parts.append('<div class="metrics">')
    for label,r,q in [('初版',old,oq),('候选',new,nq)]:
        parts.append(f'<section><b>{label}</b><p>模型距离 {fmt(r["mesh_range_m"],3)} m；beam 方位 {fmt(r["mesh_azimuth_deg"],2)}°；俯仰 {fmt(r["mesh_elevation_deg"],2)}°。</p><p>采样点可见比例 ±7° / ±7.5°：{r["fraction_visible_assumed_7deg"]:.2%} / {r["fraction_visible_assumed_7_5deg"]:.2%}。原图候选框 xyxy：{fmt(r["visible_raw_bbox_padded_clipped_xyxy"],2)}。</p><p>{esc(q["reason"])}</p><p class="muted">距离：{esc(q["range"])}；方位：{esc(q["azimuth"])}；框：{esc(q["box"])}。</p></section>')
    parts.append('</div>')
    parts.append(f'<details><summary>完整扇形图与复核分歧</summary><p>扇形是本地显示重采样，距原点越远越向上；不能把这里的框直接用于官方 polar2 图。</p><div class="fan"><img src="../sonar_fixed_mesh_beam_sign/frames/{sid}-fan.png" loading="lazy" alt="unboxed fan"><img src="../sonar_fixed_mesh_beam_sign/frames/{sid}-fan-overlay.png" loading="lazy" alt="candidate fan"></div><p>初版独立复核：{esc(oi.get("bbox_assessment",""))}</p><p>候选独立复核：{esc(ni.get("bbox_assessment",""))}</p></details></article>')
parts.append('''</main><script>
const rec=document.getElementById('recording'),sta=document.getElementById('status');
function filter(){let n=0;document.querySelectorAll('.card').forEach(el=>{el.hidden=!( (rec.value==='all'||el.dataset.recording===rec.value)&&(sta.value==='all'||el.dataset.status===sta.value));if(!el.hidden)n++;});document.getElementById('count').textContent=`显示 ${n} / 18 帧`;}
rec.addEventListener('change',filter);sta.addEventListener('change',filter);
</script></body></html>''')
(BASE/'index.html').write_text(''.join(parts),encoding='utf-8')
(SIGN/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>固定模型反号候选</title><p><a href="../sonar_fixed_mesh/index.html">打开初版与反号候选的18帧完整对照</a></p>',encoding='utf-8')

# Machine-generated exact numeric appendix, used by the separately authored report.
lines=['# 固定变换与逐帧数值附表','', '本表来自冻结 JSON；数值不经过视觉拟合。p_target = s R p_mesh + t。', '']
for name,m in models.items():
    lines += [f'## {name}', '', f'- s = {m["scale_m_per_obj_unit"]:.14g} m / OBJ unit',
              f'- t = [{fmt(m["translation_target_from_mesh_m"],10)}] m',
              f'- target 空间尺寸 = [{fmt(m["target_mesh_extent_m"],6)}] m',
              '- R（行对应 target x/y/z，列对应 OBJ x/y/z）：', '', '```text']
    lines += ['['+', '.join(f'{v:.10f}' for v in row)+']' for row in m['rotation_target_from_mesh']]
    lines += ['```','',f'OBJ SHA256: `{m["source_sha256"]}`','']
lines += ['## 反号候选：18帧全部保留','',
          '| 身份 | 距离 m | beam 方位 ° | 俯仰 ° | 可见点 ±7° / ±7.5° | 原图框 xyxy | 主 / 独立 QA |',
          '|---|---|---|---|---|---|---|']
for r in datasets[1]['rows']:
    sid=r['sample'];lines.append(f'| {sid} | {fmt(r["mesh_range_m"],3)} | {fmt(r["mesh_azimuth_deg"],2)} | {fmt(r["mesh_elevation_deg"],2)} | {r["fraction_visible_assumed_7deg"]:.2%} / {r["fraction_visible_assumed_7_5deg"]:.2%} | {fmt(r["visible_raw_bbox_padded_clipped_xyxy"],1)} | {datasets[1]["qa"][sid]["status"]} / {datasets[1]["independent"][sid]["status"]} |')
(BASE/'numeric-appendix.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps(summary['versions'],ensure_ascii=True))
