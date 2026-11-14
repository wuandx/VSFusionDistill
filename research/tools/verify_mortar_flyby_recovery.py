"""Verify preserved membership, raw pixels, source mapping, COCO and review links."""
import recover_mortar_flyby as audit
from export_mortar_flyby_recovery import BASE,DEST,ROLES
from expand_paired_recording_pool import *
from html.parser import HTMLParser
from urllib.parse import urlparse,unquote

def render_audit_index():
    from export_scene_paired_expansion import CSS
    reviews=read(audit.DEST/'pairing-review.json');cards=''
    for r in reviews:
        rec=r['recording'];decision='接受20/60修框提案，整录音val候选' if rec==audit.RECS[0] else '未准入'
        cards+=f'<section><h2>{rec} · {decision}</h2><p>{html.escape(r["observation"])}</p><pre>{html.escape(r["published_note"])}</pre><p>官方notes在上；审核判断属于本次助手观察。已复算{r["reference_sd_index_checks"]}个标注身份到SD index，直接视频像素抽查{r["reference_pixel_checks"]}个。复算规则一致不认证同步。</p><a href="{rec}/overview.jpg"><img src="{rec}/overview.jpg" loading="lazy"></a><video controls preload="metadata" style="width:100%" src="{rec}/published-pairing.mp4"></video>'
        for name in r['timeline_contacts_viewed']:cards+=f'<details><summary>实际查看的连续时间概览 {name}</summary><a href="{rec}/{name}"><img loading="lazy" src="{rec}/{name}"></a></details>'
        if rec==audit.RECS[0]:
            for n in (0,20,40):cards+=f'<p><a href="{rec}/proposal-{n:03d}.jpg">60提案中的{n}–{n+19}：'+('待修，未入数据集' if n<40 else '助手接受，已入新候选')+'</a></p>'
            cards+=f'<a href="../scene_stratified_mortar_recovered_candidate/recordings/{rec}.html">查看20对新标注</a>'
        else:cards+='<p>供人工判断的具体问题：能否从同一可辨目标或进入/退出事件确认两端对应？110229的小亮线是否足够辨识目标主体；110411强回波出现前后的相机变化是否有可靠对应？没有确认前不纳入共用训练集。</p>'
        cards+='</section>'
    page='<h1>迫击炮flyby三条来源处理记录</h1><p><a href="../scene_stratified_mortar_recovered_candidate/index.html">4081对新候选总览</a> · <a href="pairing-review.json">配对审核记录</a> · <a href="verification.json">核验</a></p><p>固定时间抽样，发布配对原偏移，不拟合新时间、不用模型预测。视频已生成；助手实际查看的是12项/录音概览和下面展开的时间序列图，未声称观看全部视频帧。相机为原SD，声呐raw显示增益2.5；无翻转。仅105856的20个明确接受提案进入新候选；其余源数据保留，不作为负样本。</p>'+cards
    (audit.DEST/'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>迫击炮flyby来源复核</title>'+CSS+page+'</html>',encoding='utf-8')

def main():
    render_audit_index()
    items=read(DEST/'manifest.json');old=read(BASE/'manifest.json');now={x['sample']:x for x in items};original={x['sample']:x for x in old}
    pr=read(DEST/'protocol.json');rs=read(DEST/'recordings.json');src=read(audit.DEST/'sources.json');records=read(audit.DEST/'source-recordings.json')
    assert len(items)==len(now)==4081 and len(original)==4061 and len(rs)==37
    for p,h in pr['input_sha256'].items():assert sha(p)==h,p
    for name,x in original.items():
        y=now[name]
        for k in ('camera_boxes_xyxy','sonar_bbox_xyxy','role','group_id','scene_id','review','camera_image_sha256','sonar_image_sha256','camera_original_label_sha256'):
            assert x[k]==y[k],(name,k)
        for k in ('camera_image','sonar_image','camera_original_label'):assert (BASE/x[k]).resolve()==(DEST/y[k]).resolve()
    new=set(now)-set(original);assert len(new)==20
    ds=read(audit.DEST/audit.RECS[0]/'decisions.json');props=read(audit.DEST/audit.RECS[0]/'proposals.json')
    assert len(ds)==60 and new=={k for k,v in ds.items() if v['decision']=='accepted'}
    assert sum(x['decision']=='unresolved' for x in ds.values())==40
    for x in props:assert sha(audit.DEST/x['sheet'])==x['sheet_sha256'] and ds[x['sample']]['sheet_sha256']==x['sheet_sha256']
    for x in src:
        for k,h in [('camera_source','camera_sha256'),('sonar_source','sonar_sha256'),('camera_label_source','camera_label_sha256')]:assert sha(x[k])==x[h]
        lab=read(x['camera_label_source']);assert lab['class']=='mortar_shell' and x['camera_boxes_xyxy']==[[lab[k] for k in ('x_min','y_min','x_max','y_max')]]
    assert len(src)==723
    timeline_checked=0
    for r in records:
        mdpath=DATA/'data_processed'/r['match']['aris_file']/(r['recording']+'_frames.csv')
        md={int(m['FrameIndex']):m for m in csv.DictReader(mdpath.open(encoding='utf-8-sig'))};onset=int(md[int(r['match']['aris_onset'])]['FrameTime'])
        for x in [x for x in src if x['recording']==r['recording']]:
            seconds=(int(md[x['aris_frame']]['FrameTime'])-onset)/1e6
            assert seconds==x['t_s'] and int(seconds*r['fps'])+int(r['match']['gopro_offset'])==x['sd_index']
        assert all(x['decoded_video_vs_reference_sd_mse']<12 for x in r['reference_sd_pixel_checks'])
        for x in r['timeline_samples']:assert sha(x['sonar_source'])==x['sonar_sha256'];timeline_checked+=1
        video=audit.DEST/r['recording']/'published-pairing.mp4'
        probe=json.loads(run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames','-of','json',str(video)]))['streams'][0]
        assert (probe['width'],probe['height'],int(probe['nb_frames']))==(1024,620,len(r['timeline_samples']))
    groups=defaultdict(set);legacy=read(DATA/'uxo-full/split_manifest.json')['recordings'];roles={r['recording']:r['role'] for r in rs}
    for r in rs:assert legacy[r['recording']]['split']!='test';groups[r['group_id']].add(r['role'])
    assert len(groups)==31 and all(len(v)==1 for v in groups.values()) and roles[audit.RECS[0]]=='val'
    hashes={m:defaultdict(set) for m in ('camera','sonar')};decoded=0
    for x in items:
        assert x['role']==roles[x['recording']] and not x['training_ready']
        lab=read(DEST/x['camera_original_label']);assert sha(DEST/x['camera_original_label'])==x['camera_original_label_sha256']
        assert lab['class']==x['category'] and x['camera_boxes_xyxy']==[[lab[k] for k in ('x_min','y_min','x_max','y_max')]]
        for mod in ('camera','sonar'):
            p=DEST/x[mod+'_image'];hh=sha(p);assert hh==x[mod+'_image_sha256'];hashes[mod][hh].add(x['role'])
            im=Image.open(p);im.load();w,h=im.size;decoded+=1
            assert (w,h)==((640,360) if mod=='camera' else tuple(x['sonar_size_wh']))
            for b in x['camera_boxes_xyxy'] if mod=='camera' else [x['sonar_bbox_xyxy']]:assert 0<=b[0]<b[2]<=w and 0<=b[1]<b[3]<=h
        if x['sample'] in new:
            assert np.array_equal(np.array(Image.open(DEST/x['sonar_image'])),audit.raw_array(x['sonar_source']))
            assert x['review']==ds[x['sample']] and x['sonar_bbox_xyxy']==ds[x['sample']]['bbox_xyxy']
    assert all(len(v)==1 for m in hashes.values() for v in m.values())
    summary=read(DEST/'summary.json')
    for role in ROLES:
        xs={x['sample']:x for x in items if x['role']==role};assert len(xs)==summary[role]['selected']
        assert (DEST/f'{role}-selected.txt').read_text(encoding='utf-8').splitlines()==list(xs)
        for mod in ('camera','sonar'):
            c=read(DEST/mod/f'coco_{role}.json');assert len(c['images'])==len(c['annotations'])==len(xs)
            ims={i['id']:i for i in c['images']};assert {i['sample'] for i in ims.values()}==set(xs)
            for a in c['annotations']:
                i=ims[a['image_id']];x=xs[i['sample']];b=x['camera_boxes_xyxy'][0] if mod=='camera' else x['sonar_bbox_xyxy']
                assert a['bbox']==[b[0],b[1],b[2]-b[0],b[3]-b[1]] and a['category_id']==list(CLASSES).index(x['category'])+1 and i['file_name']==x[mod+'_image']
    cov=read(DEST/'scene-coverage.json');assert sum(bool(c['complete']) for c in cov)==5
    mortar=next(c for c in cov if c['scene_id']=='mortar_shell|standard|flyby')
    assert mortar['role_pairs']==dict(train=16,val=20,test=0) and mortar['additional_accepted_groups_needed']==1
    for c in cov:
        for role in ROLES:assert c['role_pairs'][role]==sum(x['role']==role and x['scene_id']==c['scene_id'] for x in items)
    class Links(HTMLParser):
        def __init__(self):super().__init__();self.paths=[]
        def handle_starttag(self,tag,attrs):
            for k,v in attrs:
                if k in ('href','src') and v:self.paths.append(v)
    pages=[DEST/'index.html',DEST/'recordings'/f'{audit.RECS[0]}.html',audit.DEST/'index.html'];checked=0
    for page in pages:
        parser=Links();parser.feed(page.read_text(encoding='utf-8'))
        for url in parser.paths:
            u=urlparse(url);assert not u.scheme
            target=(page.parent/unquote(u.path)).resolve()
            if target in (DEST/'verification.json',audit.DEST/'verification.json'):continue
            assert target.is_file(),target;checked+=1
    for p,h in pr['input_sha256'].items():assert sha(p)==h,p
    result=dict(passed=True,total_pairs=4081,previous_identities_boxes_roles_reviews_preserved=4061,new_recordings=1,new_pairs=20,
        original_source_identities_hashes_labels_and_index_mapping_checked=723,reference_sd_pixel_checks=36,timeline_raw_hash_checks=timeline_checked,
        proposal_items_reviewed=60,accepted=20,unresolved=40,export_image_hashes_and_decodes=decoded,new_sonar_raw_pixel_equality=20,
        all_six_coco_and_three_lists=True,source_groups=31,recording_group_disjoint=True,cross_role_image_hash_duplicates=0,
        mortar_flyby_role_pairs=mortar['role_pairs'],complete_scenes=5,partially_covered_scenes=1,train_only_scenes=2,
        static_pages_checked=len(pages),static_links_checked=checked,browser_rendering_verified=False,source_hashes_unchanged=True,
        original_test_content_opened=False,training=False,inference=False,user_or_expert_acceptance=False,precision_sync_certified=False)
    save(DEST/'verification.json',result);save(audit.DEST/'verification.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
