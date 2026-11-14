"""Export reviewed paired additions, group split, standalone images and audit trail."""
from prepare_paired_resplit_additions import *
from expand_paired_recording_pool import defaultdict, Counter, csvout, html, DATA, CLASSES
from build_expanded_paired_split import REPEAT_GROUPS
import itertools
import shutil

DEST=ROOT/'DataSet/paired_expanded_resplit_candidate'
ARC=ROOT/'DataSet/paired_new_recording_arc_review/revision-2'
ROLES=('train','val','test')

def attrs(rr):
    return {(k,str(r[k])) for r in rr for k in ('z','tilt','roll','transmit') if r[k]!='unknown'} | {(k,str(v)) for r in rr for k,vs in r['settings'].items() for v in vs}
def error(ns):
    return round(sum((n-f*sum(ns))**2 for n,f in zip(ns,(.6,.2,.2))),8)
def tie(x):
    import hashlib
    return hashlib.sha256(('42|'+str(x)).encode()).hexdigest()

def main():
    assert not DEST.exists(),'Preserve named outputs'
    DEST.mkdir()
    fixed_paths=[BASE/'manifest.json',BASE/'recordings.json',OUT/'proposals.json',OUT/'assistant-decisions.json',ARC/'proposals.json',ARC/'assistant-decisions.json',ROOT/'experiment/archive/paired-expanded-resplit-plan.md',DATA/'uxo-full/split_manifest.json']
    fixed={str(p):sha(p) for p in fixed_paths}
    old=read(BASE/'manifest.json');rs=read(BASE/'recordings.json');meta={r['recording']:r for r in rs}
    inventory={r['recording']:r for r in read(ROOT/'DataSet/expanded_paired_recordings/inventory.json')}
    legacy=read(DATA/'uxo-full/split_manifest.json')['recordings']
    temporal={r['sample']:r for r in read(ROOT/'DataSet/camera_temporal_all/manifest-resolved.json')['items']}
    items=[];events=[]
    for x in old:
        x=dict(x);x['role_before_resplit']=x['role'];x['dataset_origin']='accepted_4081'
        x['_cam']=str((BASE/x['camera_image']).resolve());x['_son']=str((BASE/x['sonar_image']).resolve());x['_lab']=str((BASE/x['camera_original_label']).resolve());x['_raw']=False
        items.append(x)
    decisions=read(OUT/'assistant-decisions.json')['decisions']
    for r in read(OUT/'proposals.json'):
        d=decisions[r['recording']]
        if r['ordinal'] not in d['accepted']:continue
        sheet=OUT/r['sheet'];assert sheet.is_file()
        t=temporal.get(r['sample']);lab=ROOT/'DataSet/camera_temporal_all'/t['label_copy'] if t else Path(meta[r['recording']]['source_root'])/'labels'/f'{r["frame"]:04d}.json'
        ev=dict(sample=r['sample'],recording=r['recording'],decision='accepted',author='assistant',reason=d['reason'],sheet=str(sheet),sheet_sha256=sha(sheet),proposal=r,expert_verified=False,precision_sync_certified=False)
        events.append(ev)
        items.append(dict(sample=r['sample'],recording=r['recording'],category=r['category'],aris_frame=r['frame'],camera_boxes_xyxy=[r['camera_box']],sonar_bbox_xyxy=r['proposal_xyxy'],sonar_size_wh=r['sonar_size_wh'],sd_index=r['sd_index'],dataset_origin='new_near_anchor_reviewed',role_before_resplit='not_selected',group_id=r['group_id'],scene_id=r['scene_id'],_cam=r['camera_source'],_son=r['sonar_source'],_lab=str(lab),_raw=True,camera_image_sha256=r['camera_sha256'],sonar_raw_sha256=r['sonar_sha256'],camera_original_label_sha256=sha(lab),review=ev))
    ad=read(ARC/'assistant-decisions.json')
    for name,h in ad['sheets'].items():assert sha(ARC/name)==h
    for r in read(ARC/'proposals.json'):
        if r['ordinal'] not in ad['accepted']:continue
        rec=r['recording']
        if rec not in meta:
            m=dict(inventory[rec]);m.update(group_id=next((min(g) for g in REPEAT_GROUPS if rec in g),rec),scene_id=r['scene_id'],transmit='Max',settings={})
            rs.append(m);meta[rec]=m
        sheet=ARC.parent/r['sheet'];ev=dict(sample=r['sample'],recording=rec,decision='accepted',author='assistant',reason=ad['reason'],sheet=str(sheet),sheet_sha256=sha(sheet),proposal=r,expert_verified=False,precision_sync_certified=False)
        events.append(ev)
        items.append(dict(sample=r['sample'],recording=rec,category=r['category'],aris_frame=r['frame'],camera_boxes_xyxy=r['camera_boxes_xyxy'],sonar_bbox_xyxy=r['proposal_xyxy'],sonar_size_wh=r['sonar_size_wh'],sd_index=r['sd_index'],dataset_origin='new_recording_direct_arc_review',role_before_resplit='new_recording',group_id=meta[rec]['group_id'],scene_id=r['scene_id'],_cam=r['camera_source'],_son=r['sonar_source'],_lab=r['camera_label_source'],_raw=True,camera_image_sha256=r['camera_sha256'],sonar_raw_sha256=r['sonar_sha256'],camera_original_label_sha256=r['camera_label_sha256'],review=ev,pairing_status='published_mapping_with_assistant_dual_view_check_not_precision_sync'))
    assert len(old)==4081 and len(events)==755 and len(items)==4836
    assert len({x['sample'] for x in items})==len(items)
    byrec=defaultdict(list)
    for x in items:byrec[x['recording']].append(x)
    # Metadata and grouping are frozen before any model evaluation on this split.
    for r in rs:
        rec=r['recording'];assert legacy[rec]['split']!='test'
        r['role_before_resplit']=r.get('role','new_recording');r['selected']=len(byrec[rec]);r['reserve']=0
        r['added_pairs_this_version']=sum(x['dataset_origin']!='accepted_4081' for x in byrec[rec])
        md={int(m['FrameIndex']):m for m in csv.DictReader((Path(r['source_root'])/'aris_frame_meta.csv').open(encoding='utf-8-sig'))}
        frames=[md[int(x.get('aris_frame',x['sample'].rsplit('_',1)[1]))] for x in byrec[rec]]
        r['selected_pan_values']=[float(m['SonarPan']) for m in frames]
        r['settings']={k:sorted({m[k] for m in frames}) for k in ('ReceiverGain','SamplesPerBeam','SamplePeriod','FrequencyHiLow','Enable150V')}
    scenes=defaultdict(list)
    for r in rs:scenes[r['scene_id']].append(r)
    assignments={};search=[]
    for sid,rr in sorted(scenes.items()):
        groups=sorted({r['group_id'] for r in rr});best=None;feasible=0
        for labels in itertools.product(range(3),repeat=len(groups)):
            present=set(labels)
            if len(groups)>=3 and present!={0,1,2}:continue
            if len(groups)==2 and present!={0,1}:continue
            if len(groups)==1 and labels!=(0,):continue
            roles={r['recording']:ROLES[labels[groups.index(r['group_id'])]] for r in rr}
            counts=[sum(v==role for v in roles.values()) for role in ROLES]
            tr=[r for r in rr if roles[r['recording']]=='train']
            missing=len(attrs(rr)-attrs(tr));precise=len({r['primary_condition'] for r in rr}-{r['primary_condition'] for r in tr})
            pairs=[sum(r['selected'] for r in rr if roles[r['recording']]==role) for role in ROLES]
            # Whole-group 60/20/20 scene allocation first; metadata diversity next.
            score=(error(counts),missing,precise,error(pairs),tie(sorted(roles.items())))
            feasible+=1
            if best is None or score<best[0]:best=(score,roles)
        assert best
        assignments.update(best[1]);search.append(dict(scene=sid,groups=groups,feasible_assignments=feasible,score=best[0],roles=best[1]))
    for r in rs:
        r['role']=assignments[r['recording']]
        tr=[t for t in scenes[r['scene_id']] if assignments[t['recording']]=='train']
        r['same_scene_training_recordings']=[t['recording'] for t in tr]
        r['scene_train_missing_attribute_values']=[list(v) for v in sorted(attrs([r])-attrs(tr))]
        r['same_scene_exact_primary_in_train']=any(t['primary_condition']==r['primary_condition'] for t in tr)
        # Remove inherited coverage diagnostics computed for an obsolete split.
        for k in ('same_scene_pan_support_percent','selected_pan_range','selected_frame_range','previous_candidate_role'):r.pop(k,None)
    for mod in ('camera','sonar'):
        (DEST/mod/'images').mkdir(parents=True);(DEST/mod/'labels_yolo').mkdir()
    (DEST/'camera/original_labels').mkdir()
    for idx,x in enumerate(items):
        cam=Path(x.pop('_cam'));son=Path(x.pop('_son'));lab=Path(x.pop('_lab'));raw=x.pop('_raw')
        assert sha(cam)==x['camera_image_sha256'] and sha(lab)==x['camera_original_label_sha256']
        assert sha(son)==x['sonar_raw_sha256' if raw else 'sonar_image_sha256']
        label=read(lab);cb=[label[k] for k in ('x_min','y_min','x_max','y_max')]
        assert x['camera_boxes_xyxy']==[cb] and label['class']==x['category']
        x['camera_source_this_version']=str(cam);x['sonar_source_this_version']=str(son);x['camera_label_source_this_version']=str(lab)
        x['camera_image']='camera/images/'+x['sample']+'.jpg';x['sonar_image']='sonar/images/'+x['sample']+'.png';x['camera_original_label']='camera/original_labels/'+x['sample']+'.json'
        shutil.copyfile(cam,DEST/x['camera_image']);shutil.copyfile(lab,DEST/x['camera_original_label'])
        arr=raw_array(son) if raw else np.array(Image.open(son));assert arr.dtype==np.uint8 and arr.ndim==2
        if raw:Image.fromarray(arr).save(DEST/x['sonar_image'])
        else:shutil.copyfile(son,DEST/x['sonar_image'])
        assert np.array_equal(np.array(Image.open(DEST/x['sonar_image'])),arr)
        x['sonar_image_sha256']=sha(DEST/x['sonar_image']);x['role']=assignments[x['recording']];x['membership']='selected';x['training_ready']=True;x['expert_verified']=False;x['precision_sync_certified']=False
        im=Image.open(DEST/x['camera_image']);im.load();assert im.size==(640,360);assert list(arr.shape[::-1])==x['sonar_size_wh']
        for mod,wh,boxes in [('camera',(640,360),x['camera_boxes_xyxy']),('sonar',x['sonar_size_wh'],[x['sonar_bbox_xyxy']])]:
            lines=[]
            for b in boxes:
                assert 0<=b[0]<b[2]<=wh[0] and 0<=b[1]<b[3]<=wh[1],(x['sample'],b,wh)
                vals=[(b[0]+b[2])/2/wh[0],(b[1]+b[3])/2/wh[1],(b[2]-b[0])/wh[0],(b[3]-b[1])/wh[1]]
                lines.append(str(list(CLASSES).index(x['category']))+' '+' '.join(f'{v:.12f}' for v in vals))
            (DEST/mod/'labels_yolo'/(x['sample']+'.txt')).write_text('\n'.join(lines)+'\n')
        if idx%1000==0:print('export',idx,flush=True)
    for role in ROLES:
        xx=[x for x in items if x['role']==role];(DEST/f'{role}.txt').write_text('\n'.join(x['sample'] for x in xx)+'\n')
        for mod in ('camera','sonar'):
            imgs=[];anns=[]
            for i,x in enumerate(xx,1):
                w,h=(640,360) if mod=='camera' else x['sonar_size_wh'];imgs.append(dict(id=i,file_name=x[mod+'_image'],width=w,height=h,sample=x['sample'],recording=x['recording'],scene=x['scene_id']))
                for b in x['camera_boxes_xyxy'] if mod=='camera' else [x['sonar_bbox_xyxy']]:anns.append(dict(id=len(anns)+1,image_id=i,category_id=list(CLASSES).index(x['category'])+1,bbox=[b[0],b[1],b[2]-b[0],b[3]-b[1]],area=(b[2]-b[0])*(b[3]-b[1]),iscrowd=0))
            save(DEST/mod/f'coco_{role}.json',dict(images=imgs,annotations=anns,categories=[dict(id=i+1,name=c) for i,c in enumerate(CLASSES)]))
    for g in {r['group_id'] for r in rs}:assert len({r['role'] for r in rs if r['group_id']==g})==1
    for mod in ('camera','sonar'):
        hashes=defaultdict(set)
        for x in items:hashes[x[mod+'_image_sha256']].add(x['role'])
        assert all(len(v)==1 for v in hashes.values()),'Cross-role duplicate image'
    assert all(sha(p)==h for p,h in fixed.items())
    summary={role:dict(recordings=sum(r['role']==role for r in rs),groups=len({r['group_id'] for r in rs if r['role']==role}),pairs=sum(x['role']==role for x in items),per_class_pairs={c:sum(x['role']==role and x['category']==c for x in items) for c in CLASSES}) for role in ROLES}
    coverage=[dict(scene=sid,members={role:[r['recording'] for r in rr if r['role']==role] for role in ROLES},pairs={role:sum(r['selected'] for r in rr if r['role']==role) for role in ROLES}) for sid,rr in sorted(scenes.items())]
    save(DEST/'manifest.json',items);save(DEST/'recordings.json',rs);csvout(DEST/'recordings.csv',rs);save(DEST/'summary.json',summary);save(DEST/'scene-coverage.json',coverage);save(DEST/'review-events.json',events)
    save(DEST/'protocol.json',dict(name='paired_expanded_resplit_4836',status='exported_reviewed_development_split',user_authorized_expansion_and_resplit=True,seed=42,classes=list(CLASSES),source_groups=REPEAT_GROUPS,algorithm='All 8 scenes in train; >=3 source groups: all three roles required; 2 groups: train/val; 1 group: train only. Per scene lexicographic whole-recording 60/20/20 count error, missing train metadata values, missing joint primary conditions, pair count error, seeded hash tie. No model metric used.',search=search,input_sha256=fixed,old_715_test_evaluated=True,untouched_final_test=False,original_research_test_opened=False,training_started=False,coco_file_name_root='dataset root; not modality subdirectory',source_images_self_contained=True,precision_sync_certified=False,expert_verified=False))
    save(DEST/'verification.json',dict(passed=True,pairs=len(items),recordings=len(rs),groups=len({r['group_id'] for r in rs}),new_pairs=755,new_recordings=1,old_4081_identities_images_and_boxes_preserved=True,all_images_decoded=True,all_boxes_in_bounds=True,original_camera_json_boxes_unchanged=True,raw_to_png_pixel_exact=True,source_groups_disjoint=True,cross_role_duplicate_hashes=0,inputs_unchanged=True,summary=summary))
    render(items,rs,summary,coverage)
    print(summary,flush=True)

def render(items,rs,summary,coverage):
    (DEST/'previews').mkdir();font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18);cards=[]
    for r in rs:
        xx=sorted([x for x in items if x['recording']==r['recording']],key=lambda x:x['sample']);take=[xx[0],xx[len(xx)//2],xx[-1]];canvas=Image.new('RGB',(1920,700),'#f0f3f5');d=ImageDraw.Draw(canvas)
        for j,x in enumerate(take):
            ox=j*640;d.text((ox+4,4),x['sample']+' '+r['role'],font=font,fill='black');cam=Image.open(DEST/x['camera_image']).convert('RGB')
            for b in x['camera_boxes_xyxy']:ImageDraw.Draw(cam).rectangle(b,outline='#00ff40',width=2)
            canvas.paste(cam,(ox,30));a=np.array(Image.open(DEST/x['sonar_image']));son=Image.fromarray(np.clip(a.astype(float)*2.5,0,255).astype(np.uint8)).convert('RGB');b=x['sonar_bbox_xyxy'];ImageDraw.Draw(son).rectangle(b,outline='#00ff40',width=1);canvas.paste(son.resize((128,280)),(ox,405));canvas.paste(son.crop((0,max(0,b[1]-20),128,min(son.height,b[3]+20))).resize((500,280)),(ox+134,405))
        canvas.save(DEST/'previews'/f'{r["recording"]}.jpg',quality=92)
        cards.append(f'<article><h3>{r["recording"]} · {r["role"]} · {r["selected"]}对（新增{r["added_pairs_this_version"]}）</h3><p>{html.escape(r["scene_id"])}；z {r["z"]} / tilt {r["tilt"]} / roll {r["roll"]}；旧角色 {r["role_before_resplit"]}</p><img loading="lazy" src="previews/{r["recording"]}.jpg"><details><summary>同场景训练条件缺口</summary><pre>{html.escape(str(r["scene_train_missing_attribute_values"]))}</pre></details></article>')
    counts='<table><tr><th>集合</th><th>对数</th><th>录音</th><th>来源组</th></tr>'+''.join(f'<tr><td>{k}</td><td>{v["pairs"]}</td><td>{v["recordings"]}</td><td>{v["groups"]}</td></tr>' for k,v in summary.items())+'</table>'
    cov='<table><tr><th>场景</th><th>train</th><th>val</th><th>test</th></tr>'+''.join('<tr><td>'+c['scene']+'</td>'+''.join('<td>'+str(c['pairs'][role])+'对<br>'+', '.join(x[-6:] for x in c['members'][role])+'</td>' for role in ROLES)+'</tr>' for c in coverage)+'</table>'
    text='''<h1>相机—声呐配对扩充与重新划分 · 4836对 / 38录音</h1><p>原4081对完整保留，新增755对：19条已有录音增加725对、174711新录音接受30对。新增逐对助手双端复核；不是专家GT或精密同步认证。</p><p>本目录已包含两端图像与标签，可独立复制。COCO file_name相对本目录根解析；类别顺序bomb / mortar / grenade。原715 test已评价，新划分仅为有开发历史的留出，不能称未接触外部盲测。未启动新训练；旧模型接触过部分新留出来源，必须从COCO重新训练。</p><p><a href="manifest.json">清单</a> · <a href="recordings.csv">逐录音</a> · <a href="protocol.json">协议</a> · <a href="verification.json">核验</a> · <a href="review-events.json">755对审阅记录</a></p><p>110229/110411与其他历史配对未决录音仍不纳入；174711后10提案未决。总量增加不等于独立来源、弱场景细条件均已解决。仅1来源组场景保留train，val/test缺失为N/A。</p>'''
    (DEST/'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>4836对配对数据</title><style>body{font:16px/1.7 Microsoft YaHei,sans-serif;max-width:1450px;margin:auto;padding:25px;background:#f4f6fa}article{background:white;padding:15px;margin:20px 0}img{width:100%}table{border-collapse:collapse;width:100%;background:white}td,th{border:1px solid #bbc;padding:8px}pre{white-space:pre-wrap}</style>'+text+counts+'<h2>场景覆盖</h2>'+cov+''.join(cards)+'</html>',encoding='utf-8')
    (DEST/'README.md').write_text('# 4836对相机—声呐配对数据\n\n完整两端图像、原相机JSON、YOLO及COCO已独立复制。见[index.html](index.html)。新增755对为助手逐对审阅，非专家GT；精密同步未认证。原4081身份/图/框不变，新录音174711接受30对，另725来自19条已有录音。\n\n'+str(summary)+'\n\n类别ID：YOLO 0/1/2、COCO 1/2/3 = bomb / mortar / grenade（导出类名沿用原项目）。COCO file_name相对数据集根。新split有旧test评价和开发审阅历史，不称未接触盲测；原研究10条test仍关闭。来源组整体分配，未启动训练，须fresh COCO起点。\n',encoding='utf-8')

if __name__=='__main__':main()
