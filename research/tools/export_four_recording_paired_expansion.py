"""Export explicit assistant-reviewed additions while preserving all previous roles."""
from register_four_recording_final_decisions import *
import shutil
import copy

BASE=ROOT/'DataSet/paired_expanded_resplit_candidate'
DEST=ROOT/'DataSet/paired_four_recording_expanded'
ROLES=('train','val','test')


def coco(rows, mod):
    images, annotations = [], []
    for i,x in enumerate(rows,1):
        w,h=(640,360) if mod=='camera' else x['sonar_size_wh']
        images.append(dict(id=i,file_name=x[mod+'_image'],width=w,height=h,
                           sample=x['sample'],recording=x['recording'],scene=x['scene_id']))
        for b in x['camera_boxes_xyxy'] if mod=='camera' else [x['sonar_bbox_xyxy']]:
            annotations.append(dict(id=len(annotations)+1,image_id=i,
                category_id=list(CLASSES).index(x['category'])+1,
                bbox=[b[0],b[1],b[2]-b[0],b[3]-b[1]],area=(b[2]-b[0])*(b[3]-b[1]),iscrowd=0))
    return dict(images=images,annotations=annotations,
                categories=[dict(id=i+1,name=c) for i,c in enumerate(CLASSES)])


def main():
    assert not DEST.exists(),'Preserve named completed or failed outputs'
    decisions={x['sample']:x for x in read(D/'review-decisions-final.json')}
    candidates=read(D/'proposals-v3.json'); old=read(BASE/'manifest.json')
    assert len(old)==4836 and sum(x['decision']=='accepted' for x in decisions.values())==393
    assert not {x['recording'] for x in old}&set(RECS)
    legacy=read(DATA/'uxo-full/split_manifest.json')['recordings']
    assert all(legacy[r]['split']!='test' for r in RECS)
    original_inputs=read(D/'inputs-sha256.json')
    for path,h in original_inputs.items():
        check=D/'plan-before-export-amendment.md' if path.endswith('four-recording-paired-annotation-plan.md') else Path(path)
        assert sha(check)==h,(path,'source changed')
    fixed={str(p):sha(p) for p in [BASE/'manifest.json',BASE/'recordings.json',BASE/'summary.json',
        BASE/'protocol.json',D/'proposals-v3.json',D/'review-decisions-final.json',
        D/'review-summary-final.json',ROOT/'experiment/archive/four-recording-paired-annotation-plan.md',
        DATA/'data_processed/matches.csv',DATA/'uxo-full/split_manifest.json']}
    DEST.mkdir()
    for mod in ('camera','sonar'):
        (DEST/mod/'images').mkdir(parents=True)
        (DEST/mod/'labels_yolo').mkdir()
    (DEST/'camera/original_labels').mkdir()
    (DEST/'camera/assistant_labels').mkdir()
    # The previous 4836 rows are kept exactly, including boxes, hashes and roles.
    for i,x in enumerate(old):
        for field in ('camera_image','sonar_image','camera_original_label'):
            shutil.copyfile(BASE/x[field],DEST/x[field])
        for mod in ('camera','sonar'):
            rel=Path(mod)/'labels_yolo'/(x['sample']+'.txt')
            shutil.copyfile(BASE/rel,DEST/rel)
        if i%1500==0:print('copied old',i,flush=True)
    (DEST/'review').mkdir()
    for s in read(D/'corrected_v3/sheet-sha256.json'):
        shutil.copyfile(D/s['path'],DEST/'review'/Path(s['path']).name)
    for name in ('review-decisions-final.json','review-summary-final.json','explicit-corrections-final.json',
                 'review-events-final.json','registration-correction.json'):
        shutil.copyfile(D/name,DEST/'review'/name)
    added=[];unresolved=[]
    for r in candidates:
        ev=decisions[r['sample']];accepted=ev['decision']=='accepted'
        assert sha(r['camera_source'])==r['camera_sha256'] and sha(r['sonar_source'])==r['sonar_sha256']
        x=copy.deepcopy(r);x['review']=ev;x['decision']=ev['decision']
        prefix='' if accepted else 'unresolved/'
        x['camera_image']=prefix+'camera/images/'+r['sample']+'.jpg'
        x['sonar_image']=prefix+'sonar/images/'+r['sample']+'.png'
        for field in ('camera_image','sonar_image'):(DEST/x[field]).parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(r['camera_source'],DEST/x['camera_image'])
        a=raw_array(r['sonar_source']);Image.fromarray(a).save(DEST/x['sonar_image'])
        x.update(camera_image_sha256=sha(DEST/x['camera_image']),sonar_image_sha256=sha(DEST/x['sonar_image']),
                 sonar_raw_sha256=r['sonar_sha256'],aris_frame=r['frame'],
                 camera_annotation_origin='assistant_new_visible_target_annotation',
                 sonar_annotation_origin='assistant_new_visible_echo_annotation',
                 dataset_origin='four_new_recordings_assistant_review',
                 review_sheet='review/'+Path(r['sheet']).name,
                 role='train' if accepted else 'unresolved',membership='selected' if accepted else 'excluded',
                 training_ready=accepted,
                 pairing_status='published_mapping_with_assistant_dual_view_check_not_precision_sync')
        if not accepted:
            unresolved.append(x);continue
        x['camera_annotation']='camera/assistant_labels/'+r['sample']+'.json'
        annotation=dict(sample=x['sample'],recording=x['recording'],class_name=x['category'],
            boxes_xyxy=x['camera_boxes_xyxy'],annotation_origin=x['camera_annotation_origin'],
            author='assistant',expert_verified=False,source_image_sha256=x['camera_image_sha256'])
        save(DEST/x['camera_annotation'],annotation)
        x['camera_annotation_sha256']=sha(DEST/x['camera_annotation'])
        for mod,wh,boxes in [('camera',(640,360),x['camera_boxes_xyxy']),('sonar',x['sonar_size_wh'],[x['sonar_bbox_xyxy']])]:
            lines=[]
            for b in boxes:
                assert 0<=b[0]<b[2]<=wh[0] and 0<=b[1]<b[3]<=wh[1]
                vals=[(b[0]+b[2])/2/wh[0],(b[1]+b[3])/2/wh[1],(b[2]-b[0])/wh[0],(b[3]-b[1])/wh[1]]
                lines.append(str(list(CLASSES).index(x['category']))+' '+' '.join(f'{v:.12f}' for v in vals))
            (DEST/mod/'labels_yolo'/(x['sample']+'.txt')).write_text('\n'.join(lines)+'\n')
        added.append(x)
    assert len(added)==393 and len(unresolved)==7
    items=old+added;rs=read(BASE/'recordings.json')
    inv={r['recording']:r for r in read(ROOT/'DataSet/all94_recording_coverage_audit/inventory-reviewed.json')}
    matches={Path(r['aris_file']).name:r for r in csv.DictReader((DATA/'data_processed/matches.csv').open(encoding='utf-8-sig'))}
    for rec in RECS:
        r=copy.deepcopy(inv[rec]);xx=[x for x in added if x['recording']==rec]
        root=NATIVE/r['category_dir']/rec;meta=root/'aris_frame_meta.csv';fixed[str(meta)]=sha(meta)
        md={int(m['FrameIndex']):m for m in csv.DictReader(meta.open(encoding='utf-8-sig'))}
        frames=[md[x['aris_frame']] for x in xx]
        r.update(role='train',group_id=xx[0]['group_id'],selected=len(xx),reserve=0,
            unresolved=100-len(xx),source_root=str(root),primary_condition=condition(r),
            transmit='Min' if 'min transmit' in r['notes'].lower() else 'Max',
            settings={k:sorted({m[k] for m in frames}) for k in ('ReceiverGain','SamplesPerBeam','SamplePeriod','FrequencyHiLow','Enable150V')},
            gantry_file=matches[rec]['gantry_file'],gopro_file=matches[rec]['gopro_file'],
            grouping_basis=('Conservative same-posture consecutive acquisitions 124241/124440 kept together; no exact repeat asserted.'
                if rec.endswith(('124241','124440')) else 'Distinct recording; no explicit repeat in source notes; conservative group is not proof of physical independence.'),
            annotation_origin='assistant_new_visible_target_and_echo_annotation')
        rs.append(r)
    summary={role:dict(pairs=sum(x['role']==role for x in items),recordings=sum(r['role']==role for r in rs),
        groups=len({r['group_id'] for r in rs if r['role']==role}),
        per_class_pairs={c:sum(x['role']==role and x['category']==c for x in items) for c in CLASSES}) for role in ROLES}
    assert [summary[r]['pairs'] for r in ROLES]==[3433,961,835]
    for role in ROLES:
        xx=[x for x in items if x['role']==role]
        if role=='train':(DEST/f'{role}.txt').write_text('\n'.join(x['sample'] for x in xx)+'\n')
        else:shutil.copyfile(BASE/f'{role}.txt',DEST/f'{role}.txt')
        for mod in ('camera','sonar'):
            if role=='train':save(DEST/mod/f'coco_{role}.json',coco(xx,mod))
            else:shutil.copyfile(BASE/mod/f'coco_{role}.json',DEST/mod/f'coco_{role}.json')
    (DEST/'added_train.txt').write_text('\n'.join(x['sample'] for x in added)+'\n')
    for mod in ('camera','sonar'):save(DEST/mod/'coco_added_train.json',coco(added,mod))
    save(DEST/'manifest.json',items);save(DEST/'added-manifest.json',added)
    save(DEST/'unresolved/manifest.json',unresolved);save(DEST/'recordings.json',rs)
    csvout(DEST/'recordings.csv',rs);save(DEST/'summary.json',summary)
    coverage=[dict(scene=sid,pairs={role:sum(x['scene_id']==sid and x['role']==role for x in items) for role in ROLES},
                   recordings={role:[r['recording'] for r in rs if r['scene_id']==sid and r['role']==role] for role in ROLES})
              for sid in sorted({x['scene_id'] for x in items})]
    save(DEST/'scene-coverage.json',coverage)
    save(DEST/'protocol.json',dict(name='paired_four_recording_expanded_5229',
        status='exported_assistant_reviewed_train_expansion',base_dataset=str(BASE),base_pairs=4836,
        new_pairs=393,new_recordings=4,new_conservative_groups=3,
        assignment='All four new recordings train; previous 4836 roles/boxes/images/rows unchanged; val/test indices and COCO copied byte-for-byte. No metric used for assignment.',
        group_pair=['2023-09-21_124241','2023-09-21_124440'],
        classes=list(CLASSES),coco_file_name_root='dataset root',source_images_self_contained=True,
        original_input_sha256=original_inputs,input_sha256=fixed,
        original_plan_snapshot=str(D/'plan-before-export-amendment.md'),
        annotation_policy='visible camera target / visible sonar echo; identifiable truncation allowed; no negative labels from unresolved',
        old_test_evaluation_and_development_history_preserved=True,untouched_final_test=False,
        original_research_test_opened=False,existing_test_copy_and_integrity_check_only=True,
        training_started=False,model_inference=False,expert_verified=False,precision_sync_certified=False))
    assert all(sha(p)==h for p,h in fixed.items())
    render(added,unresolved,summary)
    print(summary,flush=True)


STYLE='<style>body{font:16px/1.7 Microsoft YaHei,sans-serif;max-width:1380px;margin:auto;padding:24px;background:#f4f6fa}article{background:white;padding:18px;margin:18px 0;border:1px solid #ccd}table{border-collapse:collapse;width:100%}td,th{border:1px solid #bbc;padding:8px}.pair{display:grid;grid-template-columns:2fr 1fr 1fr;gap:12px}.pair svg{width:100%;max-height:480px;background:#222}p{overflow-wrap:anywhere}a{color:#1658a0}pre{white-space:pre-wrap}</style>'


def svg(x,mod,crop=False):
    w,h=(640,360) if mod=='camera' else x['sonar_size_wh']
    b=x['camera_boxes_xyxy'][0] if mod=='camera' else x['sonar_bbox_xyxy']
    view=f'0 0 {w} {h}'
    if crop and b:
        lo=max(0,b[1]-20);hi=min(h,b[3]+20);view=f'0 {lo} {w} {hi-lo}'
    rect='' if b is None else f'<rect x="{b[0]}" y="{b[1]}" width="{b[2]-b[0]}" height="{b[3]-b[1]}" fill="none" stroke="#00ff40" stroke-width="1.5"/>'
    gain=' style="filter:brightness(2.5)"' if mod=='sonar' else ''
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}"><image href="{x[mod+"_image"]}" width="{w}" height="{h}"{gain}/>{rect}</svg>'


def render(added,unresolved,summary):
    cards=[]
    for rec in RECS:
        xx=[x for x in added+unresolved if x['recording']==rec]
        body=f'<h1>{rec}：接受{sum(x["decision"]=="accepted" for x in xx)} / 未决{sum(x["decision"]=="unresolved" for x in xx)}</h1><p><a href="index.html">返回总览</a> · 左：相机全图；中：声呐raw全图；右：声呐局部。声呐仅显示提亮2.5倍，训练PNG像素保持raw。红标题样本为未决，均未进入任何COCO/YOLO或训练索引。</p>'
        for x in sorted(xx,key=lambda x:x['ordinal']):
            color='#a52222' if x['decision']=='unresolved' else '#183b35'
            body+=f'<article id="{x["sample"]}"><h3 style="color:{color}">#{x["ordinal"]} · {x["sample"]} · {x["decision"]}</h3><p>ARIS {x["frame"]} → SD {x["sd_index"]}；相机框{html.escape(str(x["camera_boxes_xyxy"]))}；声呐框{html.escape(str(x["sonar_bbox_xyxy"]))}</p><div class="pair">{svg(x,"camera")}{svg(x,"sonar")}{svg(x,"sonar",True)}</div><a href="{x["review_sheet"]}">对应双端审核页</a></article>'
        (DEST/f'{rec}.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'+STYLE+body+'</html>',encoding='utf-8')
        r=xx[0];n=sum(x['decision']=='accepted' for x in xx)
        cards.append(f'<article><h2><a href="{rec}.html">{rec}：{n}对接受、{100-n}对未决</a></h2><p>{html.escape(r["category"])}；{html.escape(str(r["nominal"]))}；组：{r["group_id"]}</p>{svg(r,"camera")}</article>')
    table='<table><tr><th>集合</th><th>配对数</th><th>录音</th><th>保守来源组</th></tr>'+''.join(f'<tr><td>{k}</td><td>{v["pairs"]}</td><td>{v["recordings"]}</td><td>{v["groups"]}</td></tr>' for k,v in summary.items())+'</table>'
    body='<h1>相机—声呐配对扩充：5229对 / 42录音</h1><p>新增4条录音、3个保守来源组、393对双端助手标注，全部进入train。原4836的身份、图像、框和角色保留；val961/test835不变。124241/124440保守同组，7个声呐疑难样本另存未决。标注不是专家GT，公开映射与双端可辨不等于精密同步认证。</p><p><a href="manifest.json">完整清单</a> · <a href="added-manifest.json">新增393清单</a> · <a href="unresolved/manifest.json">7未决</a> · <a href="recordings.csv">逐录音</a> · <a href="protocol.json">协议</a> · <a href="independent-verification.json">独立核验</a> · <a href="review/review-summary-final.json">最终审核摘要</a> · <a href="../paired_expanded_resplit_candidate/index.html">旧4836与原有录音浏览</a></p><p>早期“400/400通过”是过早登记，已撤回；最终为393接受+7未决，历史文件保留。两端图像/COCO/YOLO自包含，COCO file_name相对本数据根。新增相机标注在camera/assistant_labels，不能当原始官方标签。未训练或模型评价，旧test与开发使用史不因换版清除。四条均为左右运动，未补mortar flyby或grenade −90 flyby缺口。</p>'
    (DEST/'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>5229对配对数据</title>'+STYLE+body+table+''.join(cards)+'</html>',encoding='utf-8')
    (DEST/'README.md').write_text('# 5229对相机—声呐配对数据\n\n[浏览](index.html)；新增393对/4录音/3保守组进入train，train3433、val961、test835。旧4836成员/图像/框/角色保持，val/test COCO和身份文件字节不变；旧版目录保留。\n\n本目录两侧图像、COCO与YOLO自包含；审核历史可指向上游目录。COCO file_name相对本数据根，类别沿用100lbs_aircraft_bomb / mortar_shell / incindiary_grenade，ID分别1/2/3（YOLO为0/1/2）。新增相机JSON是assistant_labels，不是原始标签；旧相机JSON在original_labels。新增7未决仅在unresolved中，不在训练/COCO/YOLO。\n\n助手实际双端目视标注，非专家GT，未认证精密同步。原研究10条test关闭；既有835 test仅复制和完整性核验，无新模型评价。没有训练；后续须单独预登记并从COCO初始化。未解决其他flyby覆盖缺口，不报告AP增益。\n',encoding='utf-8')


if __name__=='__main__':main()
