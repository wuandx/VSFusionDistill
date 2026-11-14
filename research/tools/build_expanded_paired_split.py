"""Build an inactive, traceable paired expansion and condition-aware split for review."""
from expand_paired_recording_pool import *
import itertools
import shutil
from datetime import datetime, timezone

DEST=ROOT/'DataSet/expanded_paired_coverage_candidate'
OLD=ROOT/'DataSet/paired_assistant_truncated_review/export'
ROLES=('train','val','test')
REPEAT_GROUPS=[['2023-09-20_174200','2023-09-20_174439'],['2023-09-20_180506','2023-09-20_180722'],
 ['2023-09-21_103728','2023-09-21_103927'],['2023-09-21_121124','2023-09-21_121327'],
 ['2023-09-21_123841','2023-09-21_124039'],['2023-09-21_122608','2023-09-21_122855']]
MORTAR_ACCEPT=[72,75,76,77,78,80,81,85,86,93,94,95,96,97,98,99]
def key(s):return hashlib.sha256(('42|'+s).encode()).hexdigest()
def broad(r):return '|'.join(str(r[k]) for k in ('category','placement','trajectory','roll'))
def circular(a,b):return abs((a-b+180)%360-180)
def main():
    assert not (DEST/'manifest.json').exists(),'Preserve completed candidate'
    DEST.mkdir(exist_ok=True);(DEST/'previews').mkdir(exist_ok=True)
    fixed_paths=[OUT/'inventory.json',OUT/'assistant-review-decisions.json',OLD/'manifest.json',
      ROOT/'DataSet/paired_recording_split/manifest.json',ROOT/'DataSet/paired_recording_condition_coverage_candidate/protocol.json',
      DATA/'uxo-full/split_manifest.json',DATA/'data_processed/matches.csv',ROOT/'experiment/archive/expanded-paired-recordings-plan.md']
    fixed={str(p):sha(p) for p in fixed_paths}
    legacy=read(DATA/'uxo-full/split_manifest.json')['recordings']
    decisions=read(OUT/'assistant-review-decisions.json');pool=read(OUT/'inventory.json')
    inventory={r['recording']:r for r in pool}
    oldroles={r['recording']:r['role'] for r in csv.DictReader((ROOT/'DataSet/paired_recording_split/recordings.csv').open(encoding='utf-8-sig'))}
    matches={Path(r['aris_file']).name:r for r in csv.DictReader((DATA/'data_processed/matches.csv').open(encoding='utf-8-sig'))}
    items=[];events=[];stamp=datetime.now(timezone.utc).isoformat()
    for x in read(OLD/'manifest.json'):
        x=dict(x);x['membership']='selected' if x['selected_for_100_per_recording'] else 'reserve'
        x['input_camera']=str(OLD/x['camera_image']);x['input_sonar']=str(OLD/x['sonar_image'])
        x['input_label']=str(OLD/x['camera_original_label']);x['input_sonar_format']='existing_png'
        x['old_role']=oldroles[x['recording']];x['new_assistant_acceptance']=False;items.append(x)
    for rec,d in decisions['decisions'].items():
        specpath=OUT/'full-review'/rec/'spec.json';spec=read(specpath);fixed[str(specpath)]=sha(specpath)
        for sh in spec['sheets']:assert sha(OUT/sh['path'])==sh['sha256']
        for x in spec['items']:
            accepted=x['ordinal'] in d['accepted'];sheet=spec['sheets'][x['ordinal']//20]
            ev=dict(sample=x['sample'],recording=rec,decision='accepted' if accepted else 'unresolved',
              author='assistant',reviewed_at=stamp,reason=d['reason'],sheet=str(OUT/sheet['path']),sheet_sha256=sheet['sha256'],
              bbox_xyxy=x['proposal_xyxy'] if accepted else None,spec_sha256=sha(specpath),camera_box_reviewed=True,
              precision_sync_certified=False,expert_verified=False,user_accepted=False)
            events.append(ev)
            if not accepted:continue
            items.append(dict(x,input_camera=str(OUT/x['camera_image']),input_sonar=x['sonar_source'],input_label=x['original_label'],
              input_sonar_format='raw_pgm',camera_image_sha256=x['camera_sha256'],camera_original_label_sha256=x['original_label_sha256'],
              sonar_bbox_xyxy=x['proposal_xyxy'],sonar_size_wh=[x['sonar_shape'][1],x['sonar_shape'][0]],
              membership='selected',review=ev,new_assistant_acceptance=True,old_role='not_in_old_30',
              pairing={'status':'not_independently_checked','eligible_for_review':True},training_ready=False))
    # Recover only the explicitly re-viewed subset; preserve every historical unresolved decision.
    mortar=ROOT/'DataSet/paired_assistant_mortar_late_review/2023-09-21_110049'
    for start in (72,84,96):
        jp=mortar/f'page-{start:04d}.json';page=read(jp);sheet=mortar/f'page-{start:04d}.jpg';fixed[str(jp)]=sha(jp)
        assert sha(sheet)==page['sheet_sha256']
        for x in page['items']:
            accepted=x['review_ordinal'] in MORTAR_ACCEPT
            ev=dict(sample=x['sample'],recording=x['recording'],decision='accepted' if accepted else 'unresolved',author='assistant',
              reviewed_at=stamp,reason='Re-viewed both views under allowed recognizable truncation policy; accept clear visible echo only. Prior unresolved decision retained.',
              sheet=str(sheet),sheet_sha256=sha(sheet),bbox_xyxy=x['proposed_box'] if accepted else None,
              camera_box_reviewed=True,precision_sync_certified=False,expert_verified=False,user_accepted=False)
            events.append(ev)
            if not accepted:continue
            items.append(dict(x,input_camera=str(ROOT/'DataSet/camera_temporal_all'/x['reference_sd']),input_sonar=x['source'],
              input_label=str(ROOT/'DataSet/camera_temporal_all'/x['label_copy']),input_sonar_format='raw_pgm',
              camera_image_sha256=x['camera_sha256'],camera_original_label_sha256=x['camera_label_sha256'],
              sonar_bbox_xyxy=x['proposed_box'],membership='selected',review=ev,new_assistant_acceptance=True,
              old_role='not_in_old_30',training_ready=False))
    assert len(items)==3716 and sum(x['membership']=='selected' for x in items)==3318
    assert len({x['sample'] for x in items})==len(items)
    byrec=defaultdict(list)
    for x in items:byrec[x['recording']].append(x)
    recordings=[]
    for rec,xs in sorted(byrec.items()):
        r=dict(inventory[rec]);assert legacy[rec]['split']!='test'
        r['old_role']=oldroles.get(rec,'not_in_old_30');r['group_id']=next((min(g) for g in REPEAT_GROUPS if rec in g),rec)
        r['selected']=sum(x['membership']=='selected' for x in xs);r['reserve']=len(xs)-r['selected']
        r['broad_condition']=broad(r);r['precise_condition']=r['category']+'|'+r['primary_condition']
        meta_path=Path(r['source_root'])/'aris_frame_meta.csv';fixed[str(meta_path)]=sha(meta_path)
        md={int(m['FrameIndex']):m for m in csv.DictReader(meta_path.open(encoding='utf-8-sig'))}
        selected=[x for x in xs if x['membership']=='selected']
        frames=[md[int(x['sample'].rsplit('_',1)[1])] for x in selected]
        r['selected_pan_values']=[float(m['SonarPan']) for m in frames]
        r['selected_pan_range']=[min(r['selected_pan_values']),max(r['selected_pan_values'])]
        r['selected_frame_range']=[min(int(m['FrameIndex']) for m in frames),max(int(m['FrameIndex']) for m in frames)]
        r['settings']={k:sorted({m[k] for m in frames}) for k in ['ReceiverGain','SamplesPerBeam','SamplePeriod','FrequencyHiLow','Enable150V']}
        r['transmit']='Min' if 'min transmit' in r['notes'].lower() else 'Max' if 'max transmit' in r['notes'].lower() else 'unknown'
        r['gantry_file']=matches[rec]['gantry_file'];r['gopro_file']=matches[rec]['gopro_file']
        recordings.append(r)
    search=[];assignment={}
    for cat in CLASSES:
        rs=[r for r in recordings if r['category']==cat];groups=sorted({r['group_id'] for r in rs})
        rows={g:[r for r in rs if r['group_id']==g] for g in groups};allb={r['broad_condition'] for r in rs}
        def fields(rr):return {(k,str(r[k])) for r in rr for k in ('placement','trajectory','z','tilt','roll','pan','transmit') if r[k]!='unknown'} | {(k,str(v)) for r in rr for k,vs in r['settings'].items() for v in vs}
        def standard_nominal(rr):return {(r['trajectory'],k,r[k]) for r in rr if r['placement']=='standard' for k in ('z','tilt') if r[k]!='unknown'}
        support={}
        for r in rs:
            for t in rs:
                if r['broad_condition']!=t['broad_condition']:continue
                delta=np.abs((np.array(r['selected_pan_values'])[:,None]-np.array(t['selected_pan_values'])[None,:]+180)%360-180)
                support[r['recording'],t['recording']]=(delta<=5).any(axis=1)
        def pan_support(r,tr):
            masks=[support[r['recording'],t['recording']] for t in tr if t['broad_condition']==r['broad_condition']]
            return float(np.logical_or.reduce(masks).mean())
        best=None;feasible=0
        for mask in range(1,2**len(groups)-1):
            tg={g for j,g in enumerate(groups) if mask>>j&1};tr=[r for g in tg for r in rows[g]]
            if {r['broad_condition'] for r in tr}!=allb:continue
            if standard_nominal(rs)-standard_nominal(tr):continue
            rest=[g for g in groups if g not in tg]
            if len(rest)<2:continue
            hold=[r for g in rest for r in rows[g]]
            if any(pan_support(r,tr)<.95-1e-9 for r in hold):continue
            if cat=='100lbs_aircraft_bomb' and not any(r['placement']=='floor' and r['trajectory']=='ellipse' for r in hold):continue
            partition=None
            for vmask in range(1,2**len(rest)-1):
                vg={g for j,g in enumerate(rest) if vmask>>j&1};vr=[r for g in vg for r in rows[g]];te=[r for g in rest if g not in vg for r in rows[g]]
                feasible+=1;n=len(rs)
                ratio_error=sum((len(rr)-frac*n)**2 for rr,frac in zip((tr,vr,te),(.6,.2,.2)))
                ps=(round(ratio_error,8),key('|'.join(sorted(tg))+'|'+ '|'.join(sorted(vg))))
                if partition is None or ps<partition[0]:partition=(ps,vr,te)
            if partition is None:continue
            precise={r['precise_condition'] for r in tr};hold=partition[1]+partition[2];trainfields=fields(tr)
            missing=sum(r['precise_condition'] not in precise for r in hold)
            marginal=sum(len(fields([r])-trainfields) for r in hold)
            pan=sum(1-pan_support(r,tr) for r in hold)
            score=(missing,marginal,partition[0][0],round(pan,8),partition[0][1])
            if best is None or score<best[0]:best=(score,tr,partition[1],partition[2])
        assert best,cat
        for role,rr in zip(ROLES,best[1:]):
            for r in rr:assignment[r['recording']]=role
        search.append(dict(category=cat,feasible=feasible,score=list(best[0]),roles={role:[r['recording'] for r in rr] for role,rr in zip(ROLES,best[1:])}))
    for r in recordings:r['role']=assignment[r['recording']]
    coverage=[]
    for b in sorted({r['broad_condition'] for r in recordings}):
        rr=[r for r in recordings if r['broad_condition']==b]
        coverage.append(dict(condition=b,groups=len({r['group_id'] for r in rr}),**{role:[r['recording'] for r in rr if r['role']==role] for role in ROLES}))
    for r in recordings:
        tr=[t for t in recordings if t['role']=='train' and t['broad_condition']==r['broad_condition']]
        r['same_broad_training_recordings']=[t['recording'] for t in tr]
        r['exact_condition_in_train']=any(t['precise_condition']==r['precise_condition'] for t in tr)
        r['nominal_differences']={k:dict(heldout=r[k],training_values=sorted({t[k] for t in tr})) for k in ('z','tilt','pan') if r[k] not in {t[k] for t in tr}}
        vals=[v for t in tr for v in t['selected_pan_values']]
        r['pan_support_percent']=100*sum(any(circular(v,t)<=5 for t in vals) for v in r['selected_pan_values'])/r['selected']
        r['electronic_values_absent_from_same_broad_train']={k:sorted(set(vs)-{v for t in tr for v in t['settings'][k]}) for k,vs in r['settings'].items() if set(vs)-{v for t in tr for v in t['settings'][k]}}
    save(DEST/'review-events.json',dict(timestamp=stamp,events=events,expert_verified=False,user_accepted=False))
    # Export image/label copies without changing original labels or activating a training run.
    for mod in ('camera','sonar'):
        for sub in ('images','labels_yolo'): (DEST/mod/sub).mkdir(parents=True,exist_ok=True)
    (DEST/'camera/original_labels').mkdir(exist_ok=True)
    for x in items:
        rec=x['recording'];x['role']=assignment[rec];x['group_id']=next(r['group_id'] for r in recordings if r['recording']==rec)
        cam=Path(x.pop('input_camera'));son=Path(x.pop('input_sonar'));lab=Path(x.pop('input_label'))
        assert sha(cam)==x['camera_image_sha256'] and sha(lab)==x['camera_original_label_sha256']
        raw_hash=x.get('sonar_sha256') or x.get('source_sha256') or x.get('review',{}).get('source_sha256')
        if x['input_sonar_format']=='existing_png':assert sha(son)==x['sonar_image_sha256']
        else:assert sha(son)==raw_hash
        x['camera_image']='camera/images/'+x['sample']+'.jpg';x['sonar_image']='sonar/images/'+x['sample']+'.png';x['camera_original_label']='camera/original_labels/'+x['sample']+'.json'
        shutil.copyfile(cam,DEST/x['camera_image']);shutil.copyfile(lab,DEST/x['camera_original_label'])
        a=Image.open(son);a.load();assert a.mode=='L';assert a.width==128
        if x['input_sonar_format']=='existing_png':shutil.copyfile(son,DEST/x['sonar_image'])
        else:a.save(DEST/x['sonar_image'])
        x['sonar_image_sha256']=sha(DEST/x['sonar_image']);x['sonar_size_wh']=list(a.size)
        x['camera_source']=str(cam);x['sonar_source']=str(son);x['camera_label_source']=str(lab)
        x['training_ready']=False;x['expert_verified']=False;x['precision_sync_certified']=False
        category=list(CLASSES).index(x['category'])
        for mod,wh,boxes in [('camera',(640,360),x['camera_boxes_xyxy']),('sonar',a.size,[x['sonar_bbox_xyxy']])]:
            lines=[]
            for b in boxes:
                assert 0<=b[0]<b[2]<=wh[0] and 0<=b[1]<b[3]<=wh[1],(x['sample'],b,wh)
                lines.append(f'{category} {(b[0]+b[2])/2/wh[0]:.10f} {(b[1]+b[3])/2/wh[1]:.10f} {(b[2]-b[0])/wh[0]:.10f} {(b[3]-b[1])/wh[1]:.10f}')
            (DEST/mod/'labels_yolo'/(x['sample']+'.txt')).write_text('\n'.join(lines)+'\n')
    for role in ROLES:
        for membership in ('selected','reserve'):
            ss=[x for x in items if x['role']==role and x['membership']==membership]
            (DEST/f'{role}-{membership}.txt').write_text('\n'.join(x['sample'] for x in ss)+'\n')
        for mod in ('camera','sonar'):
            imgs=[];anns=[]
            for i,x in enumerate([x for x in items if x['role']==role and x['membership']=='selected'],1):
                w,h=(640,360) if mod=='camera' else x['sonar_size_wh'];imgs.append(dict(id=i,file_name=x[mod+'_image'],width=w,height=h,recording=x['recording'],sample=x['sample']))
                boxes=x['camera_boxes_xyxy'] if mod=='camera' else [x['sonar_bbox_xyxy']]
                for b in boxes:anns.append(dict(id=len(anns)+1,image_id=i,category_id=list(CLASSES).index(x['category'])+1,bbox=[b[0],b[1],b[2]-b[0],b[3]-b[1]],area=(b[2]-b[0])*(b[3]-b[1]),iscrowd=0))
            save(DEST/mod/f'coco_{role}.json',dict(images=imgs,annotations=anns,categories=[dict(id=i+1,name=c) for i,c in enumerate(CLASSES)]))
    for g in {r['group_id'] for r in recordings}:assert len({r['role'] for r in recordings if r['group_id']==g})==1
    for mod in ('camera','sonar'):
        hashes=defaultdict(set)
        for x in items:hashes[x[mod+'_image_sha256']].add(x['role'])
        assert all(len(v)==1 for v in hashes.values()),'Cross-role duplicate image content'
    assert fixed=={p:sha(p) for p in fixed}
    summary={role:dict(recordings=sum(r['role']==role for r in recordings),selected=sum(x['role']==role and x['membership']=='selected' for x in items),reserve=sum(x['role']==role and x['membership']=='reserve' for x in items),per_class={c:sum(r['category']==c and r['role']==role for r in recordings) for c in CLASSES}) for role in ROLES}
    save(DEST/'manifest.json',items);save(DEST/'recordings.json',recordings);csvout(DEST/'recordings.csv',recordings);save(DEST/'coverage.json',coverage)
    save(DEST/'protocol.json',dict(name='expanded_paired_coverage_split',status='candidate_pending_user_review',seed=42,input_sha256=fixed,groups=REPEAT_GROUPS,algorithm='Hard broad-condition train coverage; standard-placement trajectory z/tilt marginal train coverage; holdout pan support >=95% within circular5deg from same-broad train; floor ellipse in train and at least one holdout. Lexicographic held-out exact-condition gaps, marginal-field/setting gaps, per-class squared 60/20/20 count error, unsupported pan fraction, seeded hash tie break.',search=search,model_metrics_used=False,untouched_final_test=False,training_started=False,original_test_opened=False,old_split_changed=False))
    save(DEST/'verification.json',dict(passed=True,summary=summary,recordings=len(recordings),selected=3318,reserve=398,new_recordings=6,new_assistant_accepted_pairs=318,original_3398_identities_preserved=True,recording_and_group_disjoint=True,cross_role_duplicate_hashes=0,all_inputs_hash_unchanged=True,all_images_decoded=True,all_boxes_in_bounds=True,broad_conditions=len(coverage),all_broad_conditions_in_train=all(c['train'] for c in coverage),user_accepted_new_pairs=0,expert_verified_new_pairs=0))
    render(recordings,items,summary,coverage)
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)

def render(recordings,items,summary,coverage):
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',19)
    cards=[]
    for r in recordings:
        xs=sorted([x for x in items if x['recording']==r['recording'] and x['membership']=='selected'],key=lambda x:x['sample'])
        take=[xs[0],xs[len(xs)//2],xs[-1]];canvas=Image.new('RGB',(1920,700),'#f0f3f5');d=ImageDraw.Draw(canvas)
        for j,x in enumerate(take):
            ox=j*640;d.text((ox+4,4),x['sample']+' '+r['role'],font=font,fill='black')
            cam=Image.open(DEST/x['camera_image']).convert('RGB');dr=ImageDraw.Draw(cam)
            for b in x['camera_boxes_xyxy']:dr.rectangle(b,outline='#00ff60',width=2)
            canvas.paste(cam,(ox,30))
            son=Image.open(DEST/x['sonar_image']);b=x['sonar_bbox_xyxy'];s=Image.fromarray(np.clip(np.array(son).astype(float)*2.5,0,255).astype(np.uint8)).convert('RGB')
            ImageDraw.Draw(s).rectangle(b,outline='#00ff60',width=1);canvas.paste(s.resize((128,280)),(ox,405))
            lo=max(0,int(b[1])-20);hi=min(s.height,int(b[3])+20);canvas.paste(s.crop((0,lo,128,hi)).resize((500,280)),(ox+134,405))
        preview=DEST/'previews'/(r['recording']+'.jpg');canvas.save(preview,quality=92)
        diff=json.dumps(r['nominal_differences'],ensure_ascii=False)
        reviewlink=(OUT/'full-review'/r['recording']/'spec.json').as_uri() if r['old_role']=='not_in_old_30' and r['recording'].endswith('110049')==False else (ROOT/'DataSet/paired_assistant_mortar_late_review'/r['recording']/'page-0072.jpg').as_uri() if r['recording'].endswith('110049') else (ROOT/'DataSet/paired_recording_condition_coverage_candidate/index.html').as_uri()
        cards.append(f'<article data-role="{r["role"]}" data-class="{r["category"]}" id="{r["recording"]}"><h3>{r["recording"]} · {CLASSES[r["category"]]} · <b>{r["role"]}</b> · {r["selected"]}对 / 备用{r["reserve"]}</h3><p>旧角色：{r["old_role"]}；来源组：{r["group_id"]}；{r["placement"]} / {r["trajectory"]} / z={r["z"]} / tilt={r["tilt"]} / roll={r["roll"]}</p><p>同宽条件train：{"、".join(t[-6:] for t in r["same_broad_training_recordings"])}；精确名义条件train覆盖：{r["exact_condition_in_train"]}；记录pan在同宽条件train ±5°支持：{r["pan_support_percent"]:.1f}%</p><p>名义差异：{html.escape(diff)}；电子设置缺口：{html.escape(json.dumps(r["electronic_values_absent_from_same_broad_train"]))}</p><a href="previews/{preview.name}"><img loading="lazy" src="previews/{preview.name}"></a><details><summary>原始notes与审阅来源</summary><pre>{html.escape(r["notes"])}</pre><a href="{reviewlink}">审阅来源</a></details></article>')
    counts=''.join(f'<tr><td>{role}</td><td>{s["recordings"]}</td><td>{s["selected"]}</td><td>{s["reserve"]}</td><td>{" / ".join(str(s["per_class"][c]) for c in CLASSES)}</td></tr>' for role,s in summary.items())
    cov=''.join('<tr><td>'+html.escape(c['condition'])+'</td>'+''.join('<td>'+', '.join(x[-6:] for x in c[role])+'</td>' for role in ROLES)+'</tr>' for c in coverage)
    remaining=[r for r in read(OUT/'inventory.json') if r['recording'] not in {x['recording'] for x in recordings}]
    pending=''.join(f'<li>{r["recording"]}：{html.escape(r["reason"])}'+('；本轮100提案已看，需修声呐框。' if r['recording'].endswith(('174711','162055')) else '')+'</li>' for r in remaining)
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>扩充共用录音与新划分候选</title><style>body{font:16px/1.6 "Microsoft YaHei",sans-serif;max-width:1450px;margin:25px auto;padding:15px;color:#203047;background:#f5f7fa}article{background:white;border:1px solid #ccd4df;border-radius:8px;padding:16px;margin:18px 0}img{width:100%;height:auto}table{border-collapse:collapse;width:100%;background:white}td,th{border:1px solid #cbd5e1;padding:8px}pre{white-space:pre-wrap}button{padding:8px 20px;margin:5px}.note{background:#fff1d6;padding:14px}</style><h1>36条相机—声呐共用录音 · 新划分候选</h1><p>此前30条是为了对齐CMHD每类10条的局部基线选择，并非原数据只有30条。本轮以条件覆盖重新扩选：47条非原test来源审计，36条有接受样本；共3318选入对+398备用。新增6录音318对为助手双端视觉接受，等待用户审阅，非专家GT。</p><p class="note">候选尚未激活、未重训。旧test已用于开发，新test不称全研究untouched。相邻帧/来源组不跨集合；published matches未升级为精密同步认证。绿框为原相机框/助手接受的声呐可见回波框，声呐显示增亮2.5倍。首中末只是浏览预览，新增接受项的逐帧审阅另有记录。</p><p><a href="recordings.csv">逐录音表</a> · <a href="manifest.json">逐对身份与框</a> · <a href="coverage.json">条件覆盖</a> · <a href="protocol.json">划分规则</a> · <a href="verification.json">核验</a></p><table><tr><th>集合</th><th>录音</th><th>选入对</th><th>备用</th><th>炸弹/迫击炮/燃烧弹录音数</th></tr>'''+counts+'</table><h2>宽条件覆盖</h2><p>宽条件=类别×摆放×运动×roll。高度/倾角/pan及电子设置差异逐条列出；宽条件有对应不等于完全同分布，也不代表同一件实物或物理姿态认证。唯一宽条件只能训练，不能获得独立同条件评价。</p><table><tr><th>条件</th><th>train</th><th>val</th><th>test</th></tr>'+cov+'</table><h2>录音与双端预览</h2><div><button onclick="filterRole(\'all\')">全部</button>'+''.join(f'<button onclick="filterRole(\'{r}\')">{r}</button>' for r in ROLES)+'</div>'+''.join(cards)+'<h2>其余11条未准入</h2><ul>'+pending+'</ul><p>110049仅复看72–99共28项，接受16项；其余3条迫击炮只抽页复核，未声称本轮全序列重审。原未决与失败完整保留。</p><script>function filterRole(r){document.querySelectorAll("article").forEach(x=>x.hidden=r!=="all"&&x.dataset.role!==r)}</script></html>'
    (DEST/'index.html').write_text(page,encoding='utf-8')
    lines=['# 扩充共用录音与新划分候选','','36条、3318选入对、398备用；新增6录音318对助手接受，用户尚未验收。旧数据/划分不变，未启动训练。','', '|集合|录音|选入对|备用|','|---|---:|---:|---:|']
    lines += [f'|{role}|{s["recordings"]}|{s["selected"]}|{s["reserve"]}|' for role,s in summary.items()]
    for role in ROLES:lines+=['',f'## {role}','',', '.join(r['recording'] for r in recordings if r['role']==role)]
    lines+=['','[带图浏览](index.html)。宽条件覆盖不等于精确名义条件覆盖；逐条差异与pan支持见recordings.csv。新test为开发协议下留出，不声称全研究未触碰。新训练需要冻结后从COCO重新初始化。','', '原30条/3000对不是源数据上限，扩充范围不再受论文每类10条限制。47审计来源非47准入；未决不作负样本。']
    (DEST/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

if __name__=='__main__':main()
