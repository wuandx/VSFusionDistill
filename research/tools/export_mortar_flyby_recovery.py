"""Export one recovered source while preserving all 4061 old identities and roles."""
import recover_mortar_flyby as audit
from expand_paired_recording_pool import *
from build_scene_stratified_split import attributes
from export_scene_paired_expansion import CSS,svg
import shutil

BASE=ROOT/'DataSet/scene_stratified_paired_expansion'
DEST=ROOT/'DataSet/scene_stratified_mortar_recovered_candidate'
ROLES=('train','val','test')

def main():
    assert not (DEST/'manifest.json').exists(),'Preserve named candidate'
    DEST.mkdir(exist_ok=True)
    old=read(BASE/'manifest.json');rs=read(BASE/'recordings.json');pairing=read(audit.DEST/'pairing-review.json')
    assert pairing[0]['pairing_status']=='published_mapping_no_obvious_conflict_in_checked_timeline'
    fixed=read(audit.DEST/'inputs-sha256.json')
    for p in [BASE/'recordings.json',BASE/'protocol.json',audit.DEST/'pairing-review.json',audit.DEST/'sources.json',audit.DEST/'source-recordings.json',
              audit.DEST/audit.RECS[0]/'proposals.json',audit.DEST/audit.RECS[0]/'decisions.json',audit.DEST/audit.RECS[0]/'review-events.jsonl']:
        fixed[str(p)]=sha(p)
    for p,h in fixed.items():assert sha(p)==h,p
    items=[]
    for x in old:
        y=dict(x)
        for k in ('camera_image','sonar_image','camera_original_label'):y[k]='../scene_stratified_paired_expansion/'+x[k]
        if 'sheet' in y:y['sheet']='../scene_stratified_paired_expansion/'+x['sheet']
        y['prior_expansion_origin']=x['expansion_origin'];y['recovery_origin']='previous_4061'
        items.append(y)
    rec=audit.RECS[0];proposals=read(audit.DEST/rec/'proposals.json');ds=read(audit.DEST/rec/'decisions.json')
    for x in proposals:
        d=ds[x['sample']]
        if d['decision']!='accepted':continue
        for src,hfield in [('camera_source','camera_sha256'),('sonar_source','sonar_sha256'),('camera_label_source','camera_label_sha256')]:assert sha(x[src])==x[hfield]
        assert sha(audit.DEST/x['sheet'])==x['sheet_sha256']
        cp=DEST/'camera/images'/(x['sample']+'.jpg');lp=DEST/'camera/original_labels'/(x['sample']+'.json');sp=DEST/'sonar/images'/(x['sample']+'.png')
        for p in (cp,lp,sp):p.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(x['camera_source'],cp);shutil.copyfile(x['camera_label_source'],lp);Image.fromarray(audit.raw_array(x['sonar_source'])).save(sp)
        y=dict(x);y.update(role='val',group_id=rec,scene_id='mortar_shell|standard|flyby',membership='selected',
            camera_image=cp.relative_to(DEST).as_posix(),camera_original_label=lp.relative_to(DEST).as_posix(),sonar_image=sp.relative_to(DEST).as_posix(),
            camera_image_sha256=sha(cp),camera_original_label_sha256=sha(lp),sonar_image_sha256=sha(sp),sonar_size_wh=list(Image.open(sp).size),
            sonar_bbox_xyxy=d['bbox_xyxy'],review=d,expansion_origin='new_mortar_flyby_recovery',recovery_origin='new_105856',
            pairing_review=pairing[0],training_ready=False,precision_sync_certified=False,expert_verified=False,user_accepted=False)
        y['sheet']='../mortar_flyby_recovery/'+x['sheet'].replace('\\','/');items.append(y)
    items.sort(key=lambda x:x['sample']);assert len(items)==4081 and len({x['sample'] for x in items})==4081
    inventory=next(r for r in read(OUT/'inventory.json') if r['recording']==rec)
    r=dict(inventory);r.update(role='val',group_id=rec,scene_id='mortar_shell|standard|flyby',reserve=0,selected=20,new_recovery_pairs=20,
        status='assistant_reviewed_recovery_pending_user_review',reason='20 of 60 visual-anchor proposals accepted; no precise sync certification',previous_selected=0,previous_reserve=0)
    rs.append(r)
    for r in rs:
        xs=[x for x in items if x['recording']==r['recording']];r['selected']=len(xs);r['new_recovery_pairs']=sum(x['recovery_origin']=='new_105856' for x in xs)
        mp=Path(r['source_root'])/'aris_frame_meta.csv';fixed[str(mp)]=sha(mp)
        md={int(m['FrameIndex']):m for m in csv.DictReader(mp.open(encoding='utf-8-sig'))};frames=[md[x['aris_frame']] for x in xs]
        r['selected_pan_values']=[float(m['SonarPan']) for m in frames];r['selected_pan_range']=[min(r['selected_pan_values']),max(r['selected_pan_values'])]
        r['selected_frame_range']=[min(x['aris_frame'] for x in xs),max(x['aris_frame'] for x in xs)]
        r['settings']={k:sorted({m[k] for m in frames}) for k in ['ReceiverGain','SamplesPerBeam','SamplePeriod','FrequencyHiLow','Enable150V']}
        r['transmit']='Min' if 'min transmit' in r['notes'].lower() else 'Max' if 'max transmit' in r['notes'].lower() else 'unknown'
    for r in rs:
        tr=[t for t in rs if t['role']=='train' and t['scene_id']==r['scene_id']]
        vals=np.array([v for t in tr for v in t['selected_pan_values']]);a=np.array(r['selected_pan_values'])
        r['same_scene_training_recordings']=[t['recording'] for t in tr]
        r['same_scene_pan_support_percent']=100*float((np.abs((a[:,None]-vals[None,:]+180)%360-180)<=5).any(axis=1).mean())
        r['scene_train_missing_attribute_values']=[list(v) for v in sorted(attributes([r])-attributes(tr))]
        r['same_scene_exact_primary_in_train']=any(t['primary_condition']==r['primary_condition'] for t in tr)
    coverage=read(BASE/'scene-coverage.json')
    for c in coverage:
        rr=[r for r in rs if r['scene_id']==c['scene_id']];c['recordings']=len(rr);c['source_groups']=len({r['group_id'] for r in rr})
        c['members']={role:[r['recording'] for r in rr if r['role']==role] for role in ROLES}
        c['role_recordings']={role:len(c['members'][role]) for role in ROLES};c['role_groups']={role:len({r['group_id'] for r in rr if r['role']==role}) for role in ROLES}
        c['role_pairs']={role:sum(x['role']==role and x['scene_id']==c['scene_id'] for x in items) for role in ROLES}
        c['complete']=all(c['members'][role] for role in ROLES);c['status']='all_three_roles_covered' if c['complete'] else 'insufficient_accepted_source_groups'
        c['additional_accepted_groups_needed']=max(0,3-c['source_groups'])
        c['pending_sources']=[x for x in c['pending_sources'] if x['recording']!=rec]
    summary={role:dict(recordings=sum(r['role']==role for r in rs),source_groups=len({r['group_id'] for r in rs if r['role']==role}),
        selected=sum(x['role']==role for x in items),new_recovery_pairs=sum(x['role']==role and x['recovery_origin']=='new_105856' for x in items),
        per_class_pairs={c:sum(x['role']==role and x['category']==c for x in items) for c in CLASSES}) for role in ROLES}
    for role in ROLES:
        xs=[x for x in items if x['role']==role];(DEST/f'{role}-selected.txt').write_text('\n'.join(x['sample'] for x in xs)+'\n',encoding='utf-8')
        for mod in ('camera','sonar'):
            (DEST/mod).mkdir(exist_ok=True);images=[];anns=[]
            for i,x in enumerate(xs,1):
                w,h=(640,360) if mod=='camera' else x['sonar_size_wh'];images.append(dict(id=i,file_name=x[mod+'_image'],width=w,height=h,sample=x['sample'],recording=x['recording'],scene=x['scene_id']))
                for b in x['camera_boxes_xyxy'] if mod=='camera' else [x['sonar_bbox_xyxy']]:anns.append(dict(id=len(anns)+1,image_id=i,category_id=list(CLASSES).index(x['category'])+1,bbox=[b[0],b[1],b[2]-b[0],b[3]-b[1]],area=(b[2]-b[0])*(b[3]-b[1]),iscrowd=0))
            save(DEST/mod/f'coco_{role}.json',dict(images=images,annotations=anns,categories=[dict(id=i+1,name=c) for i,c in enumerate(CLASSES)]))
    save(DEST/'manifest.json',items);save(DEST/'recordings.json',rs);save(DEST/'summary.json',summary);csvout(DEST/'recordings.csv',rs);save(DEST/'scene-coverage.json',coverage)
    save(DEST/'protocol.json',dict(name='scene_stratified_mortar_recovered_candidate',status='candidate_pending_user_review',input_sha256=fixed,
         prior_pairs_preserved=4061,new_recordings=[rec],new_pairs=20,original_roles_changed=False,new_recording_role='val',
         assignment_rule='Only one recovered new source => val; prior110049 remains train; test gap remains',
         source_groups=read(BASE/'protocol.json')['source_groups'],training_ready=False,training=False,model_inference=False,original_test_opened=False,
         untouched_final_test=False,precision_sync_certified=False,expert_verified=False,user_accepted=False))
    render(items,rs,summary,coverage)
    for p,h in fixed.items():assert sha(p)==h,p
    print(json.dumps(summary,ensure_ascii=False,indent=2))

def render(items,rs,summary,coverage):
    rec=audit.RECS[0];xs=[x for x in items if x['recovery_origin']=='new_105856'];(DEST/'recordings').mkdir(exist_ok=True)
    cards=''.join(f'<article><b>{x["sample"]}</b> · val<div class="pair">{svg(x,"camera")}{svg(x,"sonar")}</div><a href="../{x["sonar_image"]}">声呐全图</a></article>' for x in xs)
    title=f'<h1>{rec} · val · 新增20对</h1><p><a href="../index.html">返回新场景总览</a>。原相机SD框＋助手修订声呐框，绿色。60提案接受序号40–59；0–39待修未纳入。精密同步和用户/专家验收未认证。</p>'
    title+='<p><a href="../../mortar_flyby_recovery/2023-09-21_105856/published-pairing.mp4">发布配对时间序列</a> · <a href="../../mortar_flyby_recovery/2023-09-21_105856/proposal-000.jpg">未接受0–19</a> · <a href="../../mortar_flyby_recovery/2023-09-21_105856/proposal-020.jpg">未接受20–39</a> · <a href="../../mortar_flyby_recovery/2023-09-21_105856/proposal-040.jpg">接受40–59</a></p>'
    (DEST/'recordings'/(rec+'.html')).write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>105856新增配对</title>'+CSS+title+cards+'</html>',encoding='utf-8')
    heading='<h1>迫击炮flyby补入独立录音：4081对候选</h1><p>原4061对、图像/框和集合角色完整保留；新增105856的20对，整录音加入val。该场景现在train110049共16对、val105856共20对，test仍缺。其余5个完整场景保持。</p><p class="note">110229：所查声呐目标主体不清；110411：配对警告仍未解决，均未加入。只有文件齐全不等于配对合格。助手接受仍待用户/专家审核；精密同步未认证。原研究test未访问；本候选test有开发历史。未训练。</p><p><a href="../mortar_flyby_recovery/index.html">三条来源的实际检查与短片</a> · <a href="recordings.csv">37录音条件与数量</a> · <a href="manifest.json">4081成员</a> · <a href="verification.json">独立核验</a> · <a href="README.md">使用说明</a></p>'
    tally='<table><tr><th>集合</th><th>录音/来源组</th><th>配对数</th><th>本轮增加</th></tr>'+''.join(f'<tr><td>{role}</td><td>{s["recordings"]}/{s["source_groups"]}</td><td>{s["selected"]}</td><td>{s["new_recovery_pairs"]}</td></tr>' for role,s in summary.items())+'</table>'
    sections=''
    for c in coverage:
        sections+=f'<section><h2>{c["name"]}</h2><p>{"三集合均有独立来源" if c["complete"] else "未完成三集合覆盖，还缺"+str(c["additional_accepted_groups_needed"])+"个可用独立来源组"}</p><div class="roles">'
        for role in ROLES:
            sections+=f'<div><h3>{role} · {c["role_pairs"][role]}对</h3>'
            for rec in c['members'][role]:
                r=next(r for r in rs if r['recording']==rec);isnew=rec==audit.RECS[0]
                href=f'recordings/{rec}.html' if isnew else f'../scene_stratified_paired_expansion/recordings/{rec}.html'
                preview=f'../mortar_flyby_recovery/{rec}/proposal-040.jpg' if isnew else f'../scene_stratified_paired_expansion/previews/{rec}.jpg'
                sections+=f'<article><b>{rec} · {r["selected"]}对</b><p>z{r["z"]} / tilt{r["tilt"]} / roll{r["roll"]}<br>记录pan ±5°同场景train支持 {r["same_scene_pan_support_percent"]:.1f}%（仅诊断）</p><a href="{href}"><img src="{preview}" loading="lazy">查看全部配对</a></article>'
            sections+='</div>'
        sections+='</div></section>'
    (DEST/'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>迫击炮flyby恢复候选</title>'+CSS+heading+tally+sections+'</html>',encoding='utf-8')
    (DEST/'README.md').write_text('# 迫击炮flyby恢复后的场景候选\n\n[浏览](index.html)。4081对=原4061+105856新增20。train2472/val894/test715，37录音/31来源组。新录音整条val，旧4061身份/框/角色保持。\n\n迫击炮flyby现在train110049/val105856，test仍缺；110229/110411未通过本次复核。5种场景完整、迫击炮flyby部分覆盖、普通及地面炸弹flyby仍train-only。更多录音不等于不同实物/采集批次。\n\n6份COCO的file_name以本候选根解析；旧图引用scene_stratified_paired_expansion，新增图保存本目录。原SD框/raw像素保留。不修改旧版，不启动训练；待用户审阅、精密同步/专家未认证。若采用需冻结后固定COCO起点重训。候选test有开发史；原研究test关闭。\n',encoding='utf-8')

if __name__=='__main__':main()
