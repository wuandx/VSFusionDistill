"""Export explicitly reviewed additions in unchanged recording/scene roles."""
from expand_scene_stratified_pairs import *
import shutil

ROLES=('train','val','test')

def export():
    assert not (DEST/'manifest.json').exists(), 'Preserve named export'
    old=read(BASE/'manifest.json');rs=read(BASE/'recordings.json')
    proposals=read(DEST/'proposals.json');decisions=read(DEST/'decisions.json')
    assert len(proposals)==len(decisions)==640
    assert {x['sample'] for x in proposals}==set(decisions)
    fixed=read(DEST/'inputs-sha256.json')
    for p in ('proposals.json','decisions.json','review-events.jsonl'):
        fixed[str(DEST/p)]=sha(DEST/p)
    for p,h in fixed.items():assert sha(p)==h,p
    items=[]
    for x in old:
        y=dict(x);y['previous_membership']=y['membership'];y['membership']='selected'
        y['aris_frame']=int(x['sample'].rsplit('_',1)[1])
        y['expansion_origin']='previous_selected' if x['membership']=='selected' else 'previous_reserve'
        y['previous_selected_for_100_per_recording']=y.pop('selected_for_100_per_recording',None)
        y['previous_preview']=str((BASE/x['preview']).relative_to(ROOT))
        y.pop('preview',None);items.append(y)
    for x in proposals:
        d=decisions[x['sample']]
        if d['decision']!='accepted':continue
        assert d['bbox_xyxy']==x['proposal_xyxy']
        for field,hfield in [('camera_source','camera_sha256'),('camera_label_source','camera_label_sha256'),('sonar_source','sonar_sha256')]:
            assert sha(x[field])==x[hfield]
        assert sha(DEST/d['sheet'])==d['sheet_sha256']
        cp=DEST/'camera/images'/(x['sample']+'.jpg');sp=DEST/'sonar/images'/(x['sample']+'.png')
        lp=DEST/'camera/original_labels'/(x['sample']+'.json')
        for p in (cp,sp,lp):p.parent.mkdir(exist_ok=True,parents=True)
        shutil.copyfile(x['camera_source'],cp);shutil.copyfile(x['camera_label_source'],lp)
        Image.fromarray(raw_array(x['sonar_source'])).save(sp)
        y=dict(x);y.pop('decision');y.pop('proposal_xyxy')
        y.update(aris_frame=x['frame'],membership='selected',previous_membership=None,expansion_origin='new_explicit_review',
                 camera_image=cp.relative_to(DEST).as_posix(),sonar_image=sp.relative_to(DEST).as_posix(),
                 camera_original_label=lp.relative_to(DEST).as_posix(),camera_image_sha256=sha(cp),sonar_image_sha256=sha(sp),
                 camera_original_label_sha256=sha(lp),sonar_bbox_xyxy=d['bbox_xyxy'],review=d,training_ready=False,
                 new_assistant_acceptance=True,user_accepted=False)
        items.append(y)
    items.sort(key=lambda x:x['sample']);assert len({x['sample'] for x in items})==len(items)
    for r in rs:
        xs=[x for x in items if x['recording']==r['recording']]
        r['previous_selected']=r['selected'];r['previous_reserve']=r['reserve']
        r['selected']=len(xs);r['reserve']=0;r['new_pairs']=sum(x['expansion_origin']=='new_explicit_review' for x in xs)
        r['reviewed_new_proposals']=sum(x['recording']==r['recording'] for x in proposals)
        r['unresolved_new_proposals']=r['reviewed_new_proposals']-r['new_pairs']
        mp=Path(r['source_root'])/'aris_frame_meta.csv';fixed[str(mp)]=sha(mp)
        md={int(m['FrameIndex']):m for m in csv.DictReader(mp.open(encoding='utf-8-sig'))}
        frames=[md[x['aris_frame']] for x in xs]
        r['selected_pan_values']=[float(m['SonarPan']) for m in frames]
        r['selected_pan_range']=[min(r['selected_pan_values']),max(r['selected_pan_values'])]
        r['selected_frame_range']=[min(x['aris_frame'] for x in xs),max(x['aris_frame'] for x in xs)]
        r['settings']={k:sorted({m[k] for m in frames}) for k in ['ReceiverGain','SamplesPerBeam','SamplePeriod','FrequencyHiLow','Enable150V']}
    from build_scene_stratified_split import attributes
    for r in rs:
        tr=[t for t in rs if t['role']=='train' and t['scene_id']==r['scene_id']]
        vals=np.array([v for t in tr for v in t['selected_pan_values']]);a=np.array(r['selected_pan_values'])
        r['same_scene_pan_support_percent']=100*float((np.abs((a[:,None]-vals[None,:]+180)%360-180)<=5).any(axis=1).mean())
        r['scene_train_missing_attribute_values']=[list(v) for v in sorted(attributes([r])-attributes(tr))]
    coverage=read(BASE/'scene-coverage.json')
    for c in coverage:
        c['role_pairs']={role:sum(x['scene_id']==c['scene_id'] and x['role']==role for x in items) for role in ROLES}
    summary={role:dict(recordings=sum(r['role']==role for r in rs),source_groups=len({r['group_id'] for r in rs if r['role']==role}),
          selected=sum(x['role']==role for x in items),previous_selected=sum(x['role']==role and x['expansion_origin']=='previous_selected' for x in items),
          admitted_previous_reserve=sum(x['role']==role and x['expansion_origin']=='previous_reserve' for x in items),
          new_pairs=sum(x['role']==role and x['expansion_origin']=='new_explicit_review' for x in items),
          per_class_pairs={c:sum(x['role']==role and x['category']==c for x in items) for c in CLASSES}) for role in ROLES}
    for role in ROLES:
        xs=[x for x in items if x['role']==role]
        (DEST/f'{role}-selected.txt').write_text('\n'.join(x['sample'] for x in xs)+'\n',encoding='utf-8')
        for mod in ('camera','sonar'):
            (DEST/mod).mkdir(exist_ok=True);images=[];anns=[]
            for i,x in enumerate(xs,1):
                w,h=(640,360) if mod=='camera' else x['sonar_size_wh']
                images.append(dict(id=i,file_name=x[mod+'_image'],width=w,height=h,sample=x['sample'],recording=x['recording'],scene=x['scene_id']))
                for b in x['camera_boxes_xyxy'] if mod=='camera' else [x['sonar_bbox_xyxy']]:
                    anns.append(dict(id=len(anns)+1,image_id=i,category_id=list(CLASSES).index(x['category'])+1,bbox=[b[0],b[1],b[2]-b[0],b[3]-b[1]],area=(b[2]-b[0])*(b[3]-b[1]),iscrowd=0))
            save(DEST/mod/f'coco_{role}.json',dict(images=images,annotations=anns,categories=[dict(id=i+1,name=c) for i,c in enumerate(CLASSES)]))
    save(DEST/'manifest.json',items);save(DEST/'recordings.json',rs);csvout(DEST/'recordings.csv',rs)
    save(DEST/'summary.json',summary);save(DEST/'scene-coverage.json',coverage)
    save(DEST/'protocol.json',dict(name='scene_stratified_paired_expansion',status='candidate_pending_user_review',
        inherited_recording_roles=str(BASE/'protocol.json'),recording_roles_changed=False,source_groups=read(BASE/'protocol.json')['source_groups'],
        total_pairs=len(items),old_selected=3318,old_reserve_admitted=398,new_reviewed=len(proposals),new_accepted=len(items)-len(old),
        new_unresolved=len(proposals)-(len(items)-len(old)),per_recording_cap=None,total_pair_cap=None,
        sampling='time-stratified first review batch, at most 20 proposals per recording; not an inclusion cap',
        new_frame_min_distance_from_prior_accepted_aris_and_sd_indices=2,
        camera='original SD 640x360 image/JSON box',sonar='raw uint8, no flip or review gain in exported image; visible target echo',
        inherited_acceptances_reaudited_visually=False,new_review_author='assistant',user_accepted=False,expert_verified=False,
        precision_sync_certified=False,training_ready=False,training=False,model_inference=False,original_test_opened=False,untouched_final_test=False,
        review_revision_history='Prior snapshot overwrite corrected by append-only events; three prior corrections reconstructed with unknown original timestamps.',input_sha256=fixed))
    render(items,rs,summary,coverage)
    for p,h in fixed.items():assert sha(p)==h,p
    print(json.dumps(summary,ensure_ascii=False,indent=2))

CSS='<style>body{font:16px/1.7 "Microsoft YaHei",sans-serif;max-width:1500px;margin:auto;padding:24px;color:#243547;background:#f4f6f9}table{border-collapse:collapse;width:100%;background:white}td,th{border:1px solid #c7d0dc;padding:8px;vertical-align:top}section,article{background:white;padding:16px;margin:18px 0;border-radius:9px;border:1px solid #ccd}img{max-width:100%}.roles{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.pair{display:grid;grid-template-columns:2fr 1fr;gap:12px}svg{width:100%;max-height:440px;background:#111}.note{background:#fff1d4;padding:12px}pre{white-space:pre-wrap}@media(max-width:900px){.roles{grid-template-columns:1fr}}</style>'

def svg(x,mod):
    w,h=(640,360) if mod=='camera' else x['sonar_size_wh'];boxes=x['camera_boxes_xyxy'] if mod=='camera' else [x['sonar_bbox_xyxy']]
    lo,hi=(0,h) if mod=='camera' else (max(0,boxes[0][1]-30),min(h,boxes[0][3]+30))
    src='../'+x[mod+'_image'].replace('\\','/')
    rects=''.join(f'<rect x="{b[0]}" y="{b[1]}" width="{b[2]-b[0]}" height="{b[3]-b[1]}" fill="none" stroke="#00ff60" stroke-width="{2 if mod=="camera" else 1}"/>' for b in boxes)
    return f'<svg viewBox="0 {lo} {w} {hi-lo}" xmlns="http://www.w3.org/2000/svg"><image href="{src}" width="{w}" height="{h}"/>{rects}</svg>'

def render(items,rs,summary,coverage):
    (DEST/'recordings').mkdir(exist_ok=True);(DEST/'previews').mkdir(exist_ok=True)
    proposals=read(DEST/'proposals.json');decisions=read(DEST/'decisions.json')
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
    for r in rs:
        xs=[x for x in items if x['recording']==r['recording']];canvas=Image.new('RGB',(1920,800),'white');draw=ImageDraw.Draw(canvas)
        for j,x in enumerate([xs[0],xs[len(xs)//2],xs[-1]]):
            cam=Image.open(DEST/x['camera_image']).convert('RGB');ImageDraw.Draw(cam).rectangle(x['camera_boxes_xyxy'][0],outline=GREEN,width=2)
            canvas.paste(cam,(j*640,30));draw.text((j*640+3,3),x['sample']+' '+r['role'],fill='black',font=font)
            a=np.array(Image.open(DEST/x['sonar_image']));im=Image.fromarray(np.clip(a.astype(float)*2.5,0,255).astype(np.uint8)).convert('RGB')
            b=x['sonar_bbox_xyxy'];lo=max(0,b[1]-30);hi=min(im.height,b[3]+30)
            ImageDraw.Draw(im).rectangle(b,outline=GREEN,width=1)
            canvas.paste(im.resize((128,390)),(j*640,400));canvas.paste(im.crop((0,lo,128,hi)).resize((500,390)),(j*640+135,400))
        canvas.save(DEST/'previews'/(r['recording']+'.jpg'),quality=94)
        heading=f'<h1>{r["recording"]} · {r["role"]} · {len(xs)}对</h1><p><a href="../index.html">返回场景总览</a>。绿框为当前候选标注。新增帧排在前面；声呐为raw显示，点击可看全图。助手接受仍待用户审阅。</p>'
        ds=[d for d in decisions.values() if d['recording']==r['recording']]
        review=''
        if ds:
            proposal=next(x for x in proposals if x['recording']==r['recording'])
            ids={k:[x['review_ordinal'] for x in proposals if x['recording']==r['recording'] and decisions[x['sample']]['decision']==k] for k in ('accepted','unresolved')}
            review=f'<p class="note">本批已审20项，接受序号 {ids["accepted"]}；待修序号 {ids["unresolved"]}。<a href="../{proposal["sheet"].replace(chr(92),"/")}">查看本批全部提案页</a>（其中待修框未进入本候选）。</p>'
        cards=''.join(f'<article><b>{x["sample"]}</b> · {x["expansion_origin"]}<div class="pair">{svg(x,"camera")}{svg(x,"sonar")}</div><a href="../{x["sonar_image"].replace(chr(92),"/")}">声呐全图</a></article>' for x in sorted(xs,key=lambda x:(x['expansion_origin']!='new_explicit_review',x['sample'])))
        (DEST/'recordings'/(r['recording']+'.html')).write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>'+r['recording']+'</title>'+CSS+heading+review+cards+'</html>',encoding='utf-8')
    tally='<table><tr><th>集合</th><th>录音/来源组</th><th>原选入</th><th>纳入原备用</th><th>本批新增</th><th>现有配对数</th><th>炸弹/迫击炮/燃烧弹</th></tr>'+''.join(f'<tr><td>{role}</td><td>{s["recordings"]}/{s["source_groups"]}</td><td>{s["previous_selected"]}</td><td>{s["admitted_previous_reserve"]}</td><td>{s["new_pairs"]}</td><td><b>{s["selected"]}</b></td><td>{" / ".join(str(s["per_class_pairs"][c]) for c in CLASSES)}</td></tr>' for role,s in summary.items())+'</table>'
    sections=''
    for c in coverage:
        sections+=f'<section><h2>{c["name"]}</h2><p>{"三个集合都有独立录音来源" if c["complete"] else "缺口：目前仅一个已接受来源组，val/test缺独立录音"}</p><div class="roles">'
        for role in ROLES:
            sections+=f'<div><h3>{role} · {c["role_pairs"][role]}对</h3>'
            for rec in c['members'][role]:
                r=next(r for r in rs if r['recording']==rec)
                sections+=f'<article><b>{rec} · {r["selected"]}对</b><p>原选入{r["previous_selected"]} + 原备用{r["previous_reserve"]} + 新增{r["new_pairs"]}<br>z {r["z"]} / tilt {r["tilt"]} / roll {r["roll"]}<br>同场景train记录pan ±5°支持：{r["same_scene_pan_support_percent"]:.1f}%</p><a href="recordings/{rec}.html"><img loading="lazy" src="previews/{rec}.jpg">查看该录音全部配对</a></article>'
            sections+='</div>'
        sections+='</div></section>'
    heading=f'<h1>场景分层配对数据扩充：{len(items)}对</h1><p>一对＝一张相机图＋一张声呐图。取消总共3000对和每录音100帧上限；36条录音/30来源组的角色保持。原3318选入＋398备用＋本批345新接受＝4061对。</p><p class="note">640项新提案全部实际双端审阅：345接受，295待修。数量由审核决定，4000不是上限。全部为候选，未启动重训；助手接受不代替用户/专家验收，精密同步未认证。原3716身份本次仅复核完整性，未全部重新目视。</p><p>5种场景在train/val/test都有；3种flyby场景仍缺独立录音，增加同录音帧不能补齐该缺口。高度、倾角和设置差异仍存在；pan只作元数据诊断。候选test有开发审阅历史。</p><p><a href="recordings.csv">逐录音数量与条件</a> · <a href="manifest.json">全部成员</a> · <a href="decisions.json">本批审核</a> · <a href="verification.json">核验</a> · <a href="protocol.json">规则</a> · <a href="../scene_stratified_recording_candidate/source-shortfalls.json">缺录音原因</a></p>'
    (DEST/'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>场景分层配对扩充</title>'+CSS+heading+tally+sections+'</html>',encoding='utf-8')
    lines=['# 场景分层配对扩充候选','','[分场景浏览及全部配对](index.html)。4061对=3318原选入+398原备用+345新增助手接受；640新提案全部双端实际审阅，295待修不入清单。','', '|集合|录音|来源组|配对数|新增|','|---|---:|---:|---:|---:|']
    lines += [f'|{role}|{s["recordings"]}|{s["source_groups"]}|{s["selected"]}|{s["new_pairs"]}|' for role,s in summary.items()]
    lines += ['', '每条录音100帧、总共3000对均非上限；本轮20项只是首批审阅批量。保持scene_stratified_recording_candidate录音/来源组角色。旧3716全部纳入selected，previous_membership记录原选入/备用；历史100帧字段改名previous_selected_for_100_per_recording。', '', 'camera/sonar/coco_train.json、coco_val.json、coco_test.json共6份；file_name均以本候选根目录解析，旧3716图像与原相机JSON引用旧候选，新增345图像在本目录。原SD框不改；声呐raw无翻转、无审阅增益。', '', '5场景有三集合独立录音；普通炸弹flyby、迫击炮flyby、地面炸弹flyby各仅一接受来源组，缺口不因增帧消失。当前仅候选、未冻结训练；用户/专家验收与精密同步未认证。test来自允许开发来源，有审阅历史；原研究test内容仍关闭。若采用需冻结成员并从固定COCO重新训练。', '', '本批早期decide覆写了快照；review-events.jsonl记录启用日志时的hash，并如实重建105230、121124、121327三次收回记录（原时间未知），之后显式审核追加事件。提案页包含未接受框，只有decisions中的accepted进入manifest。']
    (DEST/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

if __name__=='__main__':export()
