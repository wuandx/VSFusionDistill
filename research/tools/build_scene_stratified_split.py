"""Stratify whole recording groups by scene and expose unavoidable scene gaps."""
from expand_paired_recording_pool import *
import itertools
from datetime import datetime,timezone

SRC=ROOT/'DataSet/expanded_paired_coverage_candidate'
DEST=ROOT/'DataSet/scene_stratified_recording_candidate'
ROLES=('train','val','test')
SCENE_NAMES={('standard','L_to_R'):'非地面／支架 · 左右运动',('standard','flyby'):'非地面／支架 · flyby',('floor','ellipse'):'地面 · 椭圆轨迹',('floor','flyby'):'地面 · flyby'}
def scene(r):return '|'.join(r[k] for k in ('category','placement','trajectory'))
def key(s):return hashlib.sha256(('42|'+s).encode()).hexdigest()
def count_error(n):
    total=sum(n);return sum((v-f*total)**2 for v,f in zip(n,(.6,.2,.2)))
def attributes(rows):
    return {(k,r[k]) for r in rows for k in ('z','tilt','roll','transmit') if r[k]!='unknown'} | {(k,v) for r in rows for k,vs in r['settings'].items() for v in vs}
def main():
    assert not (DEST/'manifest.json').exists(),'Do not overwrite a named candidate'
    DEST.mkdir(exist_ok=True);(DEST/'previews').mkdir(exist_ok=True)
    paths=[SRC/'manifest.json',SRC/'recordings.json',SRC/'protocol.json',SRC/'independent-verification.json',
      OUT/'inventory.json',ROOT/'experiment/archive/scene-stratified-recording-split-plan.md',
      DATA/'uxo-full/inventory.json',DATA/'uxo-full/split_manifest.json',DATA/'data_processed/matches.csv']
    hashes={str(p):sha(p) for p in paths};items=read(paths[0]);rs=read(paths[1]);inventory=read(paths[4]);scenes=defaultdict(list)
    for r in rs:scenes[scene(r)].append(r)
    # Pairwise pan masks are a secondary diagnostic; no pan cutoff can defeat scene coverage.
    support={}
    for rr in scenes.values():
        for r in rr:
            for t in rr:
                dd=np.abs((np.array(r['selected_pan_values'])[:,None]-np.array(t['selected_pan_values'])[None,:]+180)%360-180)
                support[r['recording'],t['recording']]=(dd<=5).any(axis=1)
    candidates={};search=[]
    for sid,rr in sorted(scenes.items()):
        groups=sorted({r['group_id'] for r in rr});rows={g:[r for r in rr if r['group_id']==g] for g in groups};options=[];best_error=None;feasible=0
        for labels in itertools.product(range(3),repeat=len(groups)):
            present=set(labels)
            if len(groups)>=3 and present!={0,1,2}:continue
            if len(groups)==2 and not (0 in present and len(present)==2):continue
            if len(groups)==1 and labels!=(0,):continue
            feasible+=1;roles={r['recording']:ROLES[label] for g,label in zip(groups,labels) for r in rows[g]}
            counts=[sum(v==role for v in roles.values()) for role in ROLES];err=round(count_error(counts),8)
            if best_error is not None and err>best_error:continue
            if best_error is None or err<best_error:options=[];best_error=err
            tr=[r for r in rr if roles[r['recording']]=='train'];hold=[r for r in rr if roles[r['recording']]!='train']
            attr_missing=len(attributes(rr)-attributes(tr));samples=[sum(r['selected'] for r in rr if roles[r['recording']]==role) for role in ROLES]
            pan=sum(1-float(np.logical_or.reduce([support[r['recording'],t['recording']] for t in tr]).mean()) for r in hold)
            options.append(dict(roles=roles,recording_counts=counts,pair_counts=samples,attr_missing=attr_missing,
              sample_error=count_error(samples),unsupported_pan=pan,tie=key(json.dumps(roles,sort_keys=True))))
        assert options,sid
        # Prefer in-scene train metadata diversity only among the optimal scene count allocations.
        min_missing=min(o['attr_missing'] for o in options);options=[o for o in options if o['attr_missing']==min_missing]
        candidates[sid]=options
        search.append(dict(scene=sid,recordings=len(rr),groups=len(groups),feasible_assignments=feasible,
          minimum_scene_count_error=best_error,minimum_missing_train_attribute_values=min_missing,remaining_options=len(options)))
    assignments={};class_search=[]
    for cat in CLASSES:
        ss=sorted(sid for sid in candidates if sid.startswith(cat+'|'));best=None
        for combo in itertools.product(*(candidates[sid] for sid in ss)):
            roles={rec:role for o in combo for rec,role in o['roles'].items()};counts=[sum(v==role for v in roles.values()) for role in ROLES]
            score=(round(count_error(counts),8),round(sum(o['sample_error'] for o in combo),8),round(sum(o['unsupported_pan'] for o in combo),8),key('|'.join(o['tie'] for o in combo)))
            if best is None or score<best[0]:best=(score,roles)
        assignments.update(best[1]);class_search.append(dict(category=cat,score=list(best[0]),roles=best[1]))
    for r in rs:
        r['previous_candidate_role']=r['role'];r['role']=assignments[r['recording']];r['scene_id']=scene(r)
        tr=[t for t in rs if assignments[t['recording']]=='train' and scene(t)==scene(r)]
        r['same_scene_training_recordings']=[t['recording'] for t in tr]
        vals=np.array([v for t in tr for v in t['selected_pan_values']]);a=np.array(r['selected_pan_values'])
        r['same_scene_pan_support_percent']=100*float((np.abs((a[:,None]-vals[None,:]+180)%360-180)<=5).any(axis=1).mean())
        r['scene_train_missing_attribute_values']=[list(v) for v in sorted(attributes([r])-attributes(tr))]
        r['same_scene_exact_primary_in_train']=any(t['primary_condition']==r['primary_condition'] for t in tr)
        for k in ['same_broad_training_recordings','exact_condition_in_train','nominal_differences','pan_support_percent','electronic_values_absent_from_same_broad_train']:
            r.pop(k,None)
    inventory_by_scene=defaultdict(list)
    for r in inventory:inventory_by_scene[scene(r)].append(r)
    coverage=[]
    for sid,rr in sorted(scenes.items()):
        ng=len({r['group_id'] for r in rr});role_rows={role:[r for r in rr if assignments[r['recording']]==role] for role in ROLES}
        row=dict(scene_id=sid,category=rr[0]['category'],placement=rr[0]['placement'],trajectory=rr[0]['trajectory'],name=CLASSES[rr[0]['category']]+' · '+SCENE_NAMES[rr[0]['placement'],rr[0]['trajectory']],
          recordings=len(rr),source_groups=ng,complete=all(role_rows[role] for role in ROLES),
          status='all_three_roles_covered' if ng>=3 else 'insufficient_accepted_source_groups',
          additional_accepted_groups_needed=max(0,3-ng),members={role:[r['recording'] for r in role_rows[role]] for role in ROLES},
          role_recordings={role:len(role_rows[role]) for role in ROLES},role_groups={role:len({r['group_id'] for r in role_rows[role]}) for role in ROLES},
          role_pairs={role:sum(r['selected'] for r in role_rows[role]) for role in ROLES},
          pending_sources=[dict(recording=r['recording'],status=r['status'],reason=r['reason']) for r in inventory_by_scene[sid] if r['recording'] not in assignments])
        assert ng<3 or row['complete'];coverage.append(row)
    # Metadata-only investigation outside the prior 47. No frames/labels from original test are read.
    legacy=read(DATA/'uxo-full/split_manifest.json')['recordings'];allinv=read(DATA/'uxo-full/inventory.json')['recordings']
    matches={Path(r['aris_file']).name:r for r in csv.DictReader((DATA/'data_processed/matches.csv').open(encoding='utf-8-sig'))}
    category_dirs={'100lbs_bomb':'100lbs_aircraft_bomb','15cm_mortar':'mortar_shell','20lbs_incendiary':'incindiary_grenade','100lbs_bomb_(floor)':'100lbs_aircraft_bomb'}
    known={r['recording'] for r in inventory};additional=[]
    for rec,l in legacy.items():
        inv=allinv.get(rec,{})
        if rec in known or l['split']=='test' or inv.get('category_dir') not in category_dirs:continue
        m=matches.get(rec,{});clip=DATA/'data_processed/gopro/clips_sd'/Path(m.get('gopro_file') or '__missing').name
        n=nominal(m.get('notes',''));additional.append(dict(recording=rec,category=category_dirs[inv['category_dir']],**n,
          original_camera_annotations=inv['n_annotated'],matched_sd_clip_exists=clip.is_file(),extracted_camera=inv['n_gopro'],
          notes=m.get('notes',''),status='needs_new_annotations' if clip.is_file() else 'no_matched_camera_clip',legacy_role=l['split']))
    save(DEST/'source-shortfalls.json',dict(accepted_scope_recordings=36,annotated_audit_sources=47,additional_metadata_only_sources=additional,
      note='No matched clip in current published matches/local SD directory is not proof no external recovery is possible. Unreviewed or missing annotations are not accepted pairs.'))
    for x in items:
        x['previous_candidate_role']=x['role'];x['role']=assignments[x['recording']];x['scene_id']=scene(next(r for r in rs if r['recording']==x['recording']))
        for k in ('camera_image','sonar_image','camera_original_label'):x[k]='../expanded_paired_coverage_candidate/'+x[k]
        x['preview']='previews/'+x['recording']+'.jpg';x['training_ready']=False
    summary={role:dict(recordings=sum(r['role']==role for r in rs),source_groups=len({r['group_id'] for r in rs if r['role']==role}),
      selected=sum(x['role']==role and x['membership']=='selected' for x in items),reserve=sum(x['role']==role and x['membership']=='reserve' for x in items),
      per_class_recordings={c:sum(r['role']==role and r['category']==c for r in rs) for c in CLASSES},
      per_class_pairs={c:sum(x['role']==role and x['category']==c and x['membership']=='selected' for x in items) for c in CLASSES}) for role in ROLES}
    for role in ROLES:
        for membership in ('selected','reserve'):(DEST/f'{role}-{membership}.txt').write_text('\n'.join(x['sample'] for x in items if x['role']==role and x['membership']==membership)+'\n',encoding='utf-8')
        for mod in ('camera','sonar'):
            (DEST/mod).mkdir(exist_ok=True);imgs=[];anns=[]
            for i,x in enumerate([x for x in items if x['role']==role and x['membership']=='selected'],1):
                w,h=(640,360) if mod=='camera' else x['sonar_size_wh'];imgs.append(dict(id=i,file_name=x[mod+'_image'],width=w,height=h,sample=x['sample'],recording=x['recording'],scene=x['scene_id']))
                for b in x['camera_boxes_xyxy'] if mod=='camera' else [x['sonar_bbox_xyxy']]:anns.append(dict(id=len(anns)+1,image_id=i,category_id=list(CLASSES).index(x['category'])+1,bbox=[b[0],b[1],b[2]-b[0],b[3]-b[1]],area=(b[2]-b[0])*(b[3]-b[1]),iscrowd=0))
            save(DEST/mod/f'coco_{role}.json',dict(images=imgs,annotations=anns,categories=[dict(id=i+1,name=c) for i,c in enumerate(CLASSES)]))
    save(DEST/'manifest.json',items);save(DEST/'recordings.json',rs);csvout(DEST/'recordings.csv',rs);save(DEST/'scene-coverage.json',coverage)
    save(DEST/'summary.json',summary)
    save(DEST/'protocol.json',dict(name='scene_stratified_recording_split',status='candidate_incomplete_scene_coverage_pending_user_review',user_intent='each scene represented separately in train/val/test',
      scene_fields=['category','placement','trajectory'],within_scene_fields=['z','tilt','roll','pan','transmit','settings'],seed=42,
      objective='Hard all-three scene coverage when >=3 accepted source groups; then per-scene 60/20/20 recording count error, train metadata diversity, per-class count error, scene sample-count error, recorded pan support, seeded hash.',
      no_hard_pan_threshold=True,source_groups=read(SRC/'protocol.json')['groups'],scene_search=search,class_search=class_search,input_sha256=hashes,
      images_and_annotations_reused_from=str(SRC),old_splits_changed=False,new_labels_accepted=0,training=False,model_inference=False,original_test_opened=False,untouched_final_test=False))
    assert all(sha(p)==h for p,h in hashes.items())
    render(rs,items,summary,coverage,additional)
    print(json.dumps(dict(summary=summary,complete_scenes=sum(bool(c['complete']) for c in coverage),incomplete_scenes=[c['name'] for c in coverage if not c['complete']]),ensure_ascii=False,indent=2))

def render(rs,items,summary,coverage,additional):
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',19)
    for r in rs:
        img=Image.open(SRC/'previews'/(r['recording']+'.jpg')).convert('RGB');d=ImageDraw.Draw(img);d.rectangle((0,0,img.width,29),fill='#f0f3f5')
        xs=sorted([x for x in items if x['recording']==r['recording'] and x['membership']=='selected'],key=lambda x:x['sample'])
        for j,x in enumerate([xs[0],xs[len(xs)//2],xs[-1]]):d.text((j*640+4,4),x['sample']+' '+r['role'],font=font,fill='black')
        img.save(DEST/'previews'/(r['recording']+'.jpg'),quality=94)
    css='''<style>body{font:16px/1.7 "Microsoft YaHei",sans-serif;max-width:1500px;padding:20px;margin:auto;background:#f4f6fa;color:#203047}h1{font-size:29px}table{width:100%;border-collapse:collapse;background:white}th,td{border:1px solid #c8d1df;padding:9px;vertical-align:top}article,section{background:white;padding:18px;margin:20px 0;border:1px solid #c8d1df;border-radius:8px}.ok{color:#157347}.gap{color:#a13d00}.note{background:#fff1d6;padding:15px}img{max-width:100%}pre{white-space:pre-wrap}button{padding:8px 18px;margin:4px}.roles{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:15px}@media(max-width:1000px){.roles{grid-template-columns:1fr}}.rec{border:1px solid #ccd;padding:10px;margin-bottom:14px}.rec img{width:100%}.small{font-size:14px}</style>'''
    heading='<h1>按场景分层：每种场景分别安排train、val、test</h1><p>场景＝类别 × 摆放方式 × 运动方式。高度、倾角、roll、增益与pan作为场景内部差异展示。本页替代此前只优先保证train条件/pan覆盖的推荐方向，旧候选保留。</p><p class="note"><b>5种场景已覆盖三个集合；3种场景仍各只有1个已审可用来源组，val/test缺失。</b>这是当前可分部分与真实缺口，不声称已完成全场景均衡。36录音/30来源组、3318选入对+398备用；原图与框沿用，新增标签0。仅候选，未激活或重训；新test已有开发历史。</p><p><a href="recordings.csv">逐录音表</a> · <a href="scene-coverage.json">场景覆盖</a> · <a href="source-shortfalls.json">补录音缺口</a> · <a href="protocol.json">规则</a> · <a href="verification.json">核验</a> · <a href="README.md">清单</a></p>'
    tally='<table><tr><th>集合</th><th>录音/来源组</th><th>选入对</th><th>备用</th><th>炸弹/迫击炮/燃烧弹对数</th></tr>'+''.join(f'<tr><td>{role}</td><td>{s["recordings"]} / {s["source_groups"]}</td><td>{s["selected"]}</td><td>{s["reserve"]}</td><td>{" / ".join(str(s["per_class_pairs"][c]) for c in CLASSES)}</td></tr>' for role,s in summary.items())+'</table>'
    cov='<h2>逐场景覆盖</h2><table><tr><th>场景</th><th>train</th><th>val</th><th>test</th><th>状态</th></tr>'
    for c in coverage:
        cov+='<tr><td>'+c['name']+'</td>'+''.join(f'<td>{c["role_recordings"][role]}录音 / {c["role_groups"][role]}组 / {c["role_pairs"][role]}对<br>'+', '.join(x[-6:] for x in c['members'][role])+'</td>' for role in ROLES)+f'<td class="{"ok" if c["complete"] else "gap"}">'+('三集合均有' if c['complete'] else '缺val/test；还需至少2组')+'</td></tr>'
    cov+='</table><p>录音不足的场景保留为train补充，不把相邻帧拆开伪造三个独立录音。若只比较场景在三集合都有的主结果，应单列上述5种完整场景；3种缺口场景的训练暴露仍须披露。</p>'
    sections=''
    for c in coverage:
        sections+=f'<section><h2>{c["name"]}</h2><div class="roles">'
        for role in ROLES:
            sections+=f'<div><h3>{role} · {c["role_pairs"][role]}对</h3>'
            for rec in c['members'][role]:
                r=next(r for r in rs if r['recording']==rec);diff=json.dumps(r['scene_train_missing_attribute_values'],ensure_ascii=False)
                review=OUT/'review-pages'/(rec+'.html');url=review.as_uri() if review.exists() else (ROOT/'DataSet/paired_recording_condition_coverage_candidate/index.html').as_uri()
                sections+=f'<div class="rec"><b>{rec} · {r["selected"]}对</b><p class="small">来源组 {r["group_id"]}<br>z {r["z"]} / tilt {r["tilt"]} / roll {r["roll"]} / {r["transmit"]}<br>旧候选 {r["previous_candidate_role"]} → {role}</p><a href="previews/{rec}.jpg"><img loading="lazy" src="previews/{rec}.jpg"></a><details><summary>场景内差异与审阅来源</summary><p>同场景train缺少的本录音边际值：{html.escape(diff)}<br>记录pan ±5°支持 {r["same_scene_pan_support_percent"]:.1f}%（仅诊断，不是硬门槛）<br>同精确名义条件在train：{r["same_scene_exact_primary_in_train"]}</p><pre>{html.escape(r["notes"])}</pre><a href="{url}">原审阅记录</a></details></div>'
            if not c['members'][role]:sections+='<p class="gap">无独立可用录音。缺口保留。</p>'
            sections+='</div>'
        sections+='</div></section>'
    gaps='<h2>缺口与来源核查</h2><ul><li>普通炸弹flyby：已审仅182317。另182600、182843在原始notes记载GoPro丢失，当前matches无SD剪辑，暂不能作为共用录音。</li><li>迫击炮flyby：已审仅110049的16对。105856、110229、110411仍有声呐可辨性/边界疑问，需具体修框或复核后才可能补足。</li><li>地面炸弹flyby：已审仅161916。162055目标可辨但现声呐框需修；即使恢复也只有2条。另162251、162428没有匹配GoPro剪辑，需要找回相机或新增独立录音。</li></ul><p>原test内容仍关闭；库存无相机不等于外部不可能找回。未审与未决不算已验收。当前范围外另有4条非test来源具SD剪辑但无原相机标注，属于后续补标候选，见source-shortfalls.json，不能直接计入。</p>'
    (DEST/'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>按场景分层的录音划分</title>'+css+heading+tally+cov+sections+gaps+'</html>',encoding='utf-8')
    lines=['# 按场景分层的录音划分候选','', '用户意图：每种场景分别选录音进入train、val、test。当前5场景三集合覆盖，3场景缺独立来源，未满足全场景覆盖，未激活/未重训。','', '|集合|录音|来源组|选入对|备用|','|---|---:|---:|---:|---:|']
    lines += [f'|{role}|{s["recordings"]}|{s["source_groups"]}|{s["selected"]}|{s["reserve"]}|' for role,s in summary.items()]
    lines+=['','## 场景覆盖','','|场景|train录音|val录音|test录音|','|---|---|---|---|']
    lines += ['|'+c['name']+'|'+'|'.join(', '.join(x[-6:] for x in c['members'][role]) or '缺' for role in ROLES)+'|' for c in coverage]
    lines+=['', '[查看分场景双端预览](index.html)。相机/声呐图像、原相机标签和助手接受的声呐框通过相对路径引用expanded_paired_coverage_candidate，不复制或修改原数据。COCO file_name以本候选根目录为基准解析。','', '5种完整场景：三类非地面L_to_R、燃烧弹flyby、地面炸弹ellipse。缺口：普通炸弹flyby、迫击炮flyby、地面炸弹flyby各缺至少2个已接受独立组。未来若修框或找回来源改变成员，另建候选，保留本版。','', 'roll、z、tilt、Tx与设置仍可能在留出与训练之间不同；见recordings.csv。当前新test有开发审阅历史，不称全研究untouched。新318对尚非用户/专家验收，精密同步未认证。']
    (DEST/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

if __name__=='__main__':main()
