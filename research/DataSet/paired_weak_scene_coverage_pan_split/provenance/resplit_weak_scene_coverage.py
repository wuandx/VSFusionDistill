"""Enumerate conservative group allocations for observed-condition train coverage."""
from expand_paired_recording_pool import *
import itertools
import copy
import shutil

BASE=ROOT/'DataSet/paired_four_recording_expanded'
DEST=ROOT/'DataSet/paired_weak_scene_coverage_pan_split'
ROLES=('train','val','test')
FOCUS=['2023-09-21_'+s for s in ('101416','105856','121539','123841','124039','125048','104749','155609')]
JOINT=('z','tilt','roll')


def joint(r):return tuple(str(r[k]) for k in JOINT)
def tie(x):return hashlib.sha256(('42|'+json.dumps(x,sort_keys=True)).encode()).hexdigest()
def attrs(rr):
    return {('transmit',r['transmit']) for r in rr}|{(k,v) for r in rr for k,vs in r['settings'].items() for v in vs}


def assign(rs,pans):
    scenes=defaultdict(list)
    for r in rs:scenes[r['scene_id']].append(r)
    search=[];train=set();scene_rest={}
    for sid,rr in sorted(scenes.items()):
        groups=sorted({r['group_id'] for r in rr});allj={joint(r) for r in rr}
        focus={r['group_id'] for r in rr if r['recording'] in FOCUS}
        feasible=[];minimum_cover=len(groups)
        for n in range(1,len(groups)+1):
            for gtuple in itertools.combinations(groups,n):
                gs=set(gtuple);tr=[r for r in rr if r['group_id'] in gs]
                if {joint(r) for r in tr}!=allj:continue
                minimum_cover=min(minimum_cover,n)
                if focus<=gs:feasible.append((gs,tr))
        assert feasible
        maxhold=max(len(groups)-len(gs) for gs,tr in feasible)
        minhold=min(2,maxhold)
        candidates=[]
        for gs,tr in feasible:
            if len(groups)-len(gs)<minhold:continue
            missing=attrs(rr)-attrs(tr)
            supports=[]
            for held in rr:
                if held['group_id'] in gs:continue
                values=np.array(pans[held['recording']])
                tv=np.array([v for t in tr if joint(t)==joint(held) for v in pans[t['recording']]])
                delta=np.abs((values[:,None]-tv[None,:]+180)%360-180)
                supports.append(float((delta<=5).any(axis=1).mean()))
            pan_shortfall=sum(max(0,.95-v) for v in supports)
            score=(sum(v<.95-1e-12 for v in supports),round(pan_shortfall,10),len(missing),round((len(gs)-.6*len(groups))**2,8),
                   round((sum(r['selected'] for r in tr)-.6*sum(r['selected'] for r in rr))**2,8),
                   sum((r['group_id'] in gs)!=(r['role']=='train') for r in rr),tie(sorted(gs)))
            candidates.append((score,gs,tr))
        score,gs,tr=min(candidates,key=lambda z:z[0]);train|=gs
        rest=sorted(set(groups)-gs);scene_rest[sid]=rest
        search.append(dict(scene=sid,groups=len(groups),joint_conditions=len(allj),
            minimum_train_groups_for_all_joint_conditions=minimum_cover,
            maximum_holdout_groups_with_all_joint_conditions=len(groups)-minimum_cover,
            focus_train_groups=sorted(focus),selected_train_groups=sorted(gs),remaining_groups=rest,
            feasible_train_subsets=len(feasible),score=score,
            train_missing_electronic_marginal_values=sorted([list(x) for x in attrs(rr)-attrs(tr)])))
    remaining=sorted({r['group_id'] for r in rs}-train)
    fixedval={g for rest in scene_rest.values() if len(rest)==1 for g in rest}
    variable=[g for g in remaining if g not in fixedval];best=None;feasible_count=0
    for labels in itertools.product(('val','test'),repeat=len(variable)):
        roles={g:'train' for g in train};roles.update({g:'val' for g in fixedval});roles.update(zip(variable,labels))
        if any(len(rest)>=2 and {roles[g] for g in rest}!={'val','test'} for rest in scene_rest.values()):continue
        if any(not all(any(r['category']==cat and roles[r['group_id']]==role for r in rs) for role in ('val','test')) for cat in CLASSES):continue
        counts={role:sum(r['selected'] for r in rs if roles[r['group_id']]==role) for role in ROLES}
        total=counts['val']+counts['test']
        class_imbalance=sum((sum(r['selected'] for r in rs if r['category']==c and roles[r['group_id']]=='val')-sum(r['selected'] for r in rs if r['category']==c and roles[r['group_id']]=='test'))**2 for c in CLASSES)
        score=((counts['val']-counts['test'])**2,class_imbalance,
            sum(roles[r['group_id']]!=r['role'] for r in rs),tie(roles))
        feasible_count+=1
        if best is None or score<best[0]:best=(score,roles,counts)
    assert best
    return best[1],search,dict(feasible_holdout_assignments=feasible_count,score=best[0],pair_counts=best[2])


def make_coco(xx,mod):
    images=[];anns=[]
    for i,x in enumerate(xx,1):
        w,h=(640,360) if mod=='camera' else x['sonar_size_wh']
        images.append(dict(id=i,file_name=x[mod+'_image'],width=w,height=h,sample=x['sample'],recording=x['recording'],scene=x['scene_id']))
        for b in x['camera_boxes_xyxy'] if mod=='camera' else [x['sonar_bbox_xyxy']]:
            anns.append(dict(id=len(anns)+1,image_id=i,category_id=list(CLASSES).index(x['category'])+1,bbox=[b[0],b[1],b[2]-b[0],b[3]-b[1]],area=(b[2]-b[0])*(b[3]-b[1]),iscrowd=0))
    return dict(images=images,annotations=anns,categories=[dict(id=i+1,name=c) for i,c in enumerate(CLASSES)])


def main():
    assert not DEST.exists(),'Keep named previous or failed outputs intact'
    rs=read(BASE/'recordings.json');source=read(BASE/'manifest.json');assert len(rs)==42 and len(source)==5229
    assert {r['group_id'] for r in rs}=={x['group_id'] for x in source}
    pans={};metadata_hashes={}
    for r in rs:
        path=Path(r['source_root'])/'aris_frame_meta.csv';metadata_hashes[str(path)]=sha(path)
        md={int(m['FrameIndex']):float(m['SonarPan']) for m in csv.DictReader(path.open(encoding='utf-8-sig'))}
        pans[r['recording']]=[md[int(x.get('aris_frame',x['sample'].rsplit('_',1)[1]))] for x in source if x['recording']==r['recording']]
    roles,search,allocation=assign(rs,pans)
    assert len(roles)==35
    # Confirm role assignment and complete observed-condition coverage before writing any copy.
    for r in rs:
        if r['recording'] in FOCUS:assert roles[r['group_id']]=='train'
    assert all({joint(r) for r in rs if r['scene_id']==sid}=={joint(r) for r in rs if r['scene_id']==sid and roles[r['group_id']]=='train'} for sid in {r['scene_id'] for r in rs})
    legacy=read(DATA/'uxo-full/split_manifest.json')['recordings']
    assert all(legacy[r['recording']]['split']!='test' for r in rs)
    fixed={str(p):sha(p) for p in [BASE/'manifest.json',BASE/'recordings.json',BASE/'protocol.json',BASE/'artifact-sha256.json',
        ROOT/'experiment/archive/weak-scene-coverage-resplit-plan.md',ROOT/'runs/scene_baselines_after_pilot_review/per-recording.csv',
        ROOT/'runs/scene_baselines_test715_review/results.json',DATA/'uxo-full/split_manifest.json']}
    DEST.mkdir();save(DEST/'search.json',search);save(DEST/'allocation.json',allocation)
    print('computed',allocation,flush=True)
    # Copy all image/label roots once; no native/test source content is opened.
    for mod in ('camera','sonar'):shutil.copytree(BASE/mod,DEST/mod)
    shutil.copytree(BASE/'review',DEST/'review')
    rows=[];changes=[]
    for old in source:
        x=copy.deepcopy(old);x['role_before_weak_coverage_resplit']=old['role'];x['role']=roles[x['group_id']];rows.append(x)
    for r in rs:
        oldrole=r['role'];r['role_before_weak_coverage_resplit']=oldrole;r['role']=roles[r['group_id']]
        r['same_scene_training_recordings']=[t['recording'] for t in rs if t['scene_id']==r['scene_id'] and roles[t['group_id']]=='train']
        r['same_scene_exact_joint_in_train']=any(joint(t)==joint(r) and t['scene_id']==r['scene_id'] and roles[t['group_id']]=='train' for t in rs)
        r['scene_train_missing_electronic_marginal_values']=sorted([list(z) for z in attrs([r])-attrs([t for t in rs if t['scene_id']==r['scene_id'] and roles[t['group_id']]=='train'])])
        for k in ('same_scene_exact_primary_in_train','scene_train_missing_attribute_values','current_role','in_current'):
            r.pop(k,None)
        changes.append(dict(recording=r['recording'],group_id=r['group_id'],scene=r['scene_id'],pairs=r['selected'],
            old_role=oldrole,new_role=r['role'],changed=oldrole!=r['role'],focus=r['recording'] in FOCUS,
            nominal_joint=list(joint(r)),transmit=r['transmit'],gain=r['settings']['ReceiverGain']))
    summary={role:dict(pairs=sum(x['role']==role for x in rows),recordings=sum(r['role']==role for r in rs),
        groups=len({r['group_id'] for r in rs if r['role']==role}),
        per_class_pairs={c:sum(x['role']==role and x['category']==c for x in rows) for c in CLASSES}) for role in ROLES}
    for role in ROLES:
        xx=[x for x in rows if x['role']==role]
        (DEST/f'{role}.txt').write_text('\n'.join(x['sample'] for x in xx)+'\n')
        for mod in ('camera','sonar'):save(DEST/mod/f'coco_{role}.json',make_coco(xx,mod))
    # The old "added_train" index is deliberately not inherited: some new sources can now be held out.
    for mod in ('camera','sonar'):
        path=DEST/mod/'coco_added_train.json'
        if path.exists():path.rename(DEST/mod/'coco_previous_added393_historical.json')
    coverage=[dict(scene=sid,nominal_joint_conditions=len({joint(r) for r in rs if r['scene_id']==sid}),
        train_joint_conditions=len({joint(r) for r in rs if r['scene_id']==sid and r['role']=='train'}),
        **{role:dict(pairs=sum(x['scene_id']==sid and x['role']==role for x in rows),
             recordings=[r['recording'] for r in rs if r['scene_id']==sid and r['role']==role],
             groups=len({r['group_id'] for r in rs if r['scene_id']==sid and r['role']==role})) for role in ROLES})
        for sid in sorted({r['scene_id'] for r in rs})]
    save(DEST/'manifest.json',rows);save(DEST/'recordings.json',rs);csvout(DEST/'recordings.csv',rs)
    save(DEST/'role-changes.json',changes);csvout(DEST/'role-changes.csv',changes)
    save(DEST/'summary.json',summary);save(DEST/'scene-coverage.json',coverage)
    # Audit actual selected pan values, using the source metadata, without interpreting them as pose GT.
    inputs=dict(fixed);inputs.update(metadata_hashes)
    for r in rs:
        metadata=Path(r['source_root'])/'aris_frame_meta.csv';inputs[str(metadata)]=sha(metadata)
        md={int(m['FrameIndex']):float(m['SonarPan']) for m in csv.DictReader(metadata.open(encoding='utf-8-sig'))}
        pans[r['recording']]=[md[int(x.get('aris_frame',x['sample'].rsplit('_',1)[1]))] for x in rows if x['recording']==r['recording']]
    pan_report=[]
    for r in rs:
        tr=[t for t in rs if t['role']=='train' and t['scene_id']==r['scene_id'] and joint(t)==joint(r)]
        vv=np.array([v for t in tr for v in pans[t['recording']]])
        values=np.array(pans[r['recording']]);delta=np.abs((values[:,None]-vv[None,:]+180)%360-180)
        pan_report.append(dict(recording=r['recording'],role=r['role'],same_joint_train_recordings=[t['recording'] for t in tr],
            selected_frames=len(values),pan_min=float(values.min()),pan_max=float(values.max()),
            same_joint_train_pan_within_5_degree_percent=100*float((delta<=5).any(axis=1).mean())))
    save(DEST/'pan-support.json',pan_report)
    protocol=dict(name='weak_scene_coverage_recording_split_5229',status='exported_development_split',seed=42,
        base_dataset=str(BASE),input_sha256=inputs,roles=list(ROLES),classes=list(CLASSES),
        purpose='Full observed scene×z×tilt×roll train coverage and explicitly identified old weak recording conditions.',
        focus_recordings=FOCUS,old_val_and_test_diagnostics_used_to_define_development_targets=True,
        untouched_final_test=False,all_5229_accepted_pairs_preserved=True,
        algorithm='Enumerate train source-group subsets per scene; full observed z/tilt/roll coverage and specified focus groups; preserve at least two holdout groups if possible (otherwise one/zero); minimize held recordings below95% same-joint pan within5deg, their shortfall, absent electronic marginal values, 60% train group error, train pair error, changes, seed42 hash. Then per-class val/test and two-role scenes required, single holdout scene to val; balance val/test pairs, class counts, changes, seed42 hash.',
        no_new_model_metric_used_for_search=True,coco_file_name_root='dataset root',
        original_research_test_opened=False,existing_dataset_test_content_copied_for_export_only=True,
        training_started=False,model_inference=False,expert_verified=False,precision_sync_certified=False,
        all_observed_joint_conditions_in_train=True,all_electronic_joint_or_pan_coverage_certified=False,
        isolated_sources_cannot_supply_independent_same_condition_evaluation=True,
        source_images_self_contained=True,unresolved_samples_admitted=0)
    save(DEST/'protocol.json',protocol)
    assert all(sha(k)==v for k,v in inputs.items())
    render(rs,rows,summary,coverage,changes)
    print(summary,flush=True)


def render(rs,rows,summary,coverage,changes):
    (DEST/'previews').mkdir();font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',17);cards=[]
    for r in sorted(rs,key=lambda z:(z['scene_id'],z['recording'])):
        xx=sorted([x for x in rows if x['recording']==r['recording']],key=lambda x:x['sample'])
        take=[xx[0],xx[len(xx)//2],xx[-1]];canvas=Image.new('RGB',(1920,690),'#f4f6fa');draw=ImageDraw.Draw(canvas)
        for j,x in enumerate(take):
            ox=640*j;draw.text((ox+3,3),f'{x["sample"]} {x["role"]}',fill='black',font=font)
            cam=Image.open(DEST/x['camera_image']).convert('RGB')
            for b in x['camera_boxes_xyxy']:ImageDraw.Draw(cam).rectangle(b,outline='#00ff40',width=2)
            canvas.paste(cam,(ox,27));a=np.array(Image.open(DEST/x['sonar_image']));s=Image.fromarray(np.clip(a.astype(float)*2.5,0,255).astype(np.uint8)).convert('RGB');b=x['sonar_bbox_xyxy'];ImageDraw.Draw(s).rectangle(b,outline='#00ff40',width=1)
            canvas.paste(s.resize((128,285)),(ox,397));canvas.paste(s.crop((0,max(0,b[1]-20),128,min(s.height,b[3]+20))).resize((500,285)),(ox+135,397))
        canvas.save(DEST/'previews'/(r['recording']+'.jpg'),quality=93)
        cards.append(f'<article data-role="{r["role"]}"><h3>{r["recording"]} · {r["role_before_weak_coverage_resplit"]} → {r["role"]} · {r["selected"]}对</h3><p>{html.escape(r["scene_id"])}；z/tilt/roll {html.escape(str(joint(r)))}；{r["transmit"]} / gain {r["settings"]["ReceiverGain"]}；group {r["group_id"]}</p><img loading="lazy" src="previews/{r["recording"]}.jpg"></article>')
    table='<table><tr><th>集合</th><th>对数</th><th>录音数</th><th>组数</th></tr>'+''.join(f'<tr><td>{k}</td><td>{v["pairs"]}</td><td>{v["recordings"]}</td><td>{v["groups"]}</td></tr>' for k,v in summary.items())+'</table>'
    cov='<table><tr><th>场景</th><th>train联合条件/现有</th><th>train对</th><th>val对</th><th>test对</th></tr>'+''.join(f'<tr><td>{html.escape(c["scene"])}</td><td>{c["train_joint_conditions"]}/{c["nominal_joint_conditions"]}</td>'+''.join(f'<td>{c[k]["pairs"]}</td>' for k in ROLES)+'</tr>' for c in coverage)+'</table>'
    intro='''<h1>已知弱场景条件覆盖优先 · 5229对重划分</h1><p>仅改变已接受5229对的角色，图像、标签和来源组不变。所有已登记scene内z/tilt/roll联合条件进入train；旧弱项105856、121539、125048、123841/124039等进入训练。用户允许重分，旧版本保留。此为受旧val/test诊断启发的开发方案，不能称新盲测，也不代表模型能力已改善；未训练、未推理。</p><p>完整覆盖的代价：floor bomb ellipse三联合/三组全train；两种bomb flyby各只有一组；这三场景无独立留出。mortar flyby两组最多留一组val，grenade flyby三组覆盖−60/−90后最多一组val，均无test。电子组合、相机视图和pan不保证全覆盖。新增四条录音不等于补齐所有薄弱场景。</p><p><a href="protocol.json">协议</a> · <a href="recordings.csv">42录音表</a> · <a href="role-changes.csv">角色变化</a> · <a href="pan-support.json">pan支持诊断</a> · <a href="independent-verification.json">独立核验</a> · <a href="../paired_four_recording_expanded/index.html">旧5229版</a></p>'''
    style='<style>body{font:16px/1.7 Microsoft YaHei,sans-serif;margin:20px auto;max-width:1450px;padding:20px;background:#f4f6fa}article{background:white;border:1px solid #ccd;margin:18px 0;padding:16px}img{width:100%}table{border-collapse:collapse;width:100%;background:white}td,th{border:1px solid #ccd;padding:8px}button{padding:8px 20px;margin:8px}</style>'
    buttons='<button onclick="f(\'all\')">全部</button>'+''.join(f'<button onclick="f(\'{k}\')">{k}</button>' for k in ROLES)
    (DEST/'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>弱场景条件覆盖重划分</title>'+style+intro+table+'<h2>场景与联合条件覆盖</h2>'+cov+'<h2>42条录音双端首中末</h2>'+buttons+''.join(cards)+'<script>function f(r){document.querySelectorAll("article").forEach(x=>x.hidden=r!=="all"&&x.dataset.role!==r)}</script></html>',encoding='utf-8')
    (DEST/'README.md').write_text('# 已知弱场景条件覆盖优先的5229配对重划分\n\n[浏览](index.html)。只改角色；旧5229两端图像、标签、全部身份保留。所有已登记scene内z/tilt/roll联合条件进入train，unique来源优先训练，因此floor ellipse和两种bomb flyby没有独立留出；两类其余flyby只有val。见protocol.json、scene-coverage.json和role-changes.csv。\n\n新分配使用旧val/test诊断定义开发目标，不称未触碰测试集；无新训练或推理，无AP增益。原研究10条test关闭；7未决没有纳入。类别及COCO file_name根沿用旧5229，新增相机assistant_labels和原标签original_labels的血缘不变。历史393样本COCO以previous_added393_historical命名，仅供血缘，不作当前train索引。须fresh COCO训练后才可评价本版。\n',encoding='utf-8')


if __name__=='__main__':main()
