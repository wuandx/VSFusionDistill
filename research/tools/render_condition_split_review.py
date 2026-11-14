from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'DataSet/paired_recording_condition_coverage_candidate'
SOURCE=ROOT/'DataSet/paired_assistant_truncated_review/export'
ZH={'100lbs_aircraft_bomb':'炸弹','mortar_shell':'迫击炮','incindiary_grenade':'燃烧弹'}

def main():
    rows=json.loads((OUT/'condition-audit.json').read_text(encoding='utf-8'))
    coverage=json.loads((OUT/'coverage.json').read_text(encoding='utf-8'))
    manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    verification=json.loads((OUT/'verification.json').read_text(encoding='utf-8'))
    previews=OUT/'previews';previews.mkdir(exist_ok=True)
    refs=[];cards=[]
    for row in rows:
        rec=row['recording']
        images=sorted([x for x in manifest if x['recording']==rec and x['membership']=='selected'],key=lambda x:int(x['sample'].rsplit('_',1)[1]))
        tiles=[]
        for j in [0,49,99]:
            x=images[j];p=SOURCE/x['camera_image']
            assert hashlib.sha256(p.read_bytes()).hexdigest()==x['camera_image_sha256']
            im=cv2.imread(str(p));assert im is not None
            label=json.loads((SOURCE/'camera/original_labels'/f"{x['sample']}.json").read_text())
            cv2.rectangle(im,(label['x_min'],label['y_min']),(label['x_max'],label['y_max']),(0,255,0),2)
            im=cv2.resize(im,(320,180));im=cv2.copyMakeBorder(im,28,0,0,0,cv2.BORDER_CONSTANT,value=(25,25,25))
            cv2.putText(im,x['sample'],(4,19),cv2.FONT_HERSHEY_SIMPLEX,.4,(255,255,255),1)
            tiles.append(im);refs.append(x['sample'])
        cv2.imwrite(str(previews/f'{rec}.jpg'),np.hstack(tiles))
        sensors=', '.join(f'{k}={"/".join(v)}' for k,v in row['sonar_settings'].items())
        oldnew=f'{row["old_role"]} → {row["role"]}'
        key=row['primary_condition'].replace('|',' / ')
        details=f'''<article data-role="{row['role']}" data-cat="{row['category']}" id="{rec}"><h3>{rec} · {ZH[row['category']]} · <span class="{row['role']}">{oldnew}</span></h3><p>{html.escape(key)}；同条件{row['condition_recordings']}录音/{row['condition_groups']}来源组。原因：{row['reason']}</p><p>所选100帧ARIS记录pan：{row['selected_pan_range'][0]:.2f}–{row['selected_pan_range'][1]:.2f}°；tilt：{row['selected_tilt_range'][0]:.2f}–{row['selected_tilt_range'][1]:.2f}°；源帧{row['selected_frame_min']}–{row['selected_frame_max']}，所选时间跨度{row['selected_duration_s']:.2f}s。{'留出pan支持 '+str(row['same_condition_pan_support_count'])+'/100' if row['role']!='train' else 'train（训练帧自支持不算泛化证据）'}</p><p>{html.escape(sensors)}；原相机框触底{row['camera_bottom_touch']}/100（触边不是人工截断认证）。</p><a href="previews/{rec}.jpg"><img loading="lazy" src="previews/{rec}.jpg" alt="首中末三帧"></a><details><summary>原始notes与来源</summary><pre>{html.escape(row['notes'])}</pre><p>{html.escape(row['source_metadata'])}</p></details></article>'''
        cards.append(details)
    table='<table><tr><th>类别</th><th>train</th><th>val</th><th>test</th></tr>'
    for cat in ['100lbs_aircraft_bomb','mortar_shell','incindiary_grenade']:
        table+=f'<tr><td>{ZH[cat]}</td>'+''.join('<td>'+', '.join(f'<a href="#{r["recording"]}">{r["recording"][-6:]}</a>' for r in rows if r['category']==cat and r['role']==role)+'</td>' for role in ['train','val','test'])+'</tr>'
    table+='</table>'
    summary='<table><tr><th>角色</th><th>录音</th><th>选入</th><th>备用（不使用）</th></tr>'+''.join(f'<tr><td>{role}</td><td>{s["recordings"]}</td><td>{s["selected"]}</td><td>{s["reserve"]}</td></tr>' for role,s in verification['summary'].items())+'</table>'
    ct='<table><tr><th>类别</th><th>主条件</th><th>录音/来源组</th><th>train/val/test</th></tr>'+''.join(f'<tr><td>{ZH[c["category"]]}</td><td>{html.escape(c["condition"])}</td><td>{c["total_recordings"]}/{c["source_groups"]}</td><td>{c["train"]}/{c["val"]}/{c["test"]}</td></tr>' for c in coverage)+'</table>'
    controls='''<label>角色 <select id="role" onchange="filter()"><option value="all">全部</option><option>train</option><option>val</option><option>test</option></select></label> <label>类别 <select id="cat" onchange="filter()"><option value="all">全部</option><option value="100lbs_aircraft_bomb">炸弹</option><option value="mortar_shell">迫击炮</option><option value="incindiary_grenade">燃烧弹</option></select></label><script>function filter(){const r=document.getElementById('role').value,c=document.getElementById('cat').value;document.querySelectorAll('article').forEach(e=>e.hidden=(r!=='all'&&e.dataset.role!==r)||(c!=='all'&&e.dataset.cat!==c))}</script>'''
    page='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>30条录音条件覆盖与新划分候选</title><style>body{font:16px/1.6 sans-serif;background:#f6f7f9;color:#152332;margin:24px auto;max-width:1300px;padding:0 18px}h1,h2{line-height:1.3}table{border-collapse:collapse;width:100%;background:white;margin:16px 0}td,th{padding:9px;border:1px solid #ccd3db;text-align:left}article{background:white;border:1px solid #ccd3db;border-radius:8px;padding:16px;margin:18px 0}img{width:100%;max-width:960px}.train{color:#08724a}.val{color:#a15b00}.test{color:#345bc2}.notice{background:#fff0cf;padding:16px;border-radius:8px}pre{white-space:pre-wrap}a{color:#255caa}[hidden]{display:none}</style><h1>30条录音：条件审计与新划分候选</h1><p class="notice"><strong>待用户审阅，未激活、未重训。</strong>旧split和3000+398交付不改。旧test已经评价，本次修订受既有分析启发，不能称全研究未触碰final test；新版本需从COCO起点重训，旧模型不能冒充新划分留出评价。</p><h2>候选规则与数量</h2><p>按类别内“摆放、运动、notes名义z/tilt/roll/pan”精确组合；缺pan保留unknown，不能解释为0。全部21种主条件在train出现；14种仅有一个来源组，只能train-only，不能宣称评价覆盖它们。相同条件的留出帧至少95%有同条件train pan记录值在±5°内；并覆盖类别内电子设置边际值与Min/Max Transmit。这些是我方采集元数据约束，不是真实RGB视角、物体3D姿态或完整场景覆盖认证。</p>'''+summary+'''<p>最终候选8条留出录音的pan支持实为99–100/100。固定来源组不跨角色，398备用继承角色、不参加主实验。枚举满足约束的最少train录音方案，用seed42 hash打破平局；没有读取模型AP来选择。比例服从条件覆盖，约73.3%/13.3%/13.3%。</p><h2>录音分配（短编号可点击）</h2>'''+table+'''<h2>全部主条件覆盖</h2>'''+ct+'''<p>不能同时保证全部条件在三集合齐全：例如floor bomb只有160551，纳入train后没有独立floor测试。声呐窗口范围不是目标距离；pan只是记录角，不认证同步或RGB物体姿态；首中末为所选100帧，不代表完整运动视频。</p><p><a href="recordings.csv">逐录音CSV</a> · <a href="coverage.csv">条件覆盖CSV</a> · <a href="protocol.json">算法与来源hash</a> · <a href="verification.json">核验</a></p><h2>逐录音首/中/末帧与条件</h2>'''+controls+''.join(cards)+'</html>'
    (OUT/'index.html').write_text(page,encoding='utf-8')
    (OUT/'preview-verification.json').write_text(json.dumps(dict(previews=30,source_images=90,source_image_hashes_match=True,all_decoded=True,samples=refs),indent=2)+'\n')
    print('Built 30 previews / 90 source images and review page')

if __name__=='__main__':main()
