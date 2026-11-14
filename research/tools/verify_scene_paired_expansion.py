"""Independent checks of identities, exports, explicit decisions, roles and links."""
from expand_scene_stratified_pairs import *
from urllib.parse import urlparse,unquote
from html.parser import HTMLParser

def main():
    items=read(DEST/'manifest.json');old=read(BASE/'manifest.json');rs=read(DEST/'recordings.json')
    original={x['sample']:x for x in old};now={x['sample']:x for x in items}
    proposals=read(DEST/'proposals.json');decisions=read(DEST/'decisions.json');pr=read(DEST/'protocol.json')
    assert len(items)==len(now)==4061 and len(original)==3716
    assert len(proposals)==len(decisions)==640
    new={x['sample'] for x in items}-set(original)
    assert new=={k for k,v in decisions.items() if v['decision']=='accepted'} and len(new)==345
    assert sum(v['decision']=='unresolved' for v in decisions.values())==295
    for p,h in pr['input_sha256'].items():assert sha(p)==h,p
    for name,x in original.items():
        y=now[name]
        for k in ('role','group_id','scene_id','camera_boxes_xyxy','sonar_bbox_xyxy','camera_image_sha256','sonar_image_sha256','camera_original_label_sha256','review'):
            assert x[k]==y[k],(name,k)
        assert y['previous_membership']==x['membership'] and y['membership']=='selected'
        for k in ('camera_image','sonar_image','camera_original_label'):
            assert (BASE/x[k]).resolve()==(DEST/y[k]).resolve()
    role_by_rec={r['recording']:r['role'] for r in read(BASE/'recordings.json')}
    legacy=read(DATA/'uxo-full/split_manifest.json')['recordings'];groups=defaultdict(set)
    for r in rs:
        assert r['role']==role_by_rec[r['recording']] and legacy[r['recording']]['split']!='test'
        groups[r['group_id']].add(r['role'])
        assert r['selected']==sum(x['recording']==r['recording'] for x in items) and r['reserve']==0
        md={int(m['FrameIndex']):m for m in csv.DictReader((Path(r['source_root'])/'aris_frame_meta.csv').open(encoding='utf-8-sig'))}
        vals=[float(md[x['aris_frame']]['SonarPan']) for x in items if x['recording']==r['recording']]
        assert vals==r['selected_pan_values']
    assert len(groups)==30 and all(len(v)==1 for v in groups.values())
    for x in proposals:
        assert sha(DEST/x['sheet'])==x['sheet_sha256']
        d=decisions[x['sample']];assert d['sheet_sha256']==x['sheet_sha256'] and d['author']=='assistant'
        for p,h in [('camera_source','camera_sha256'),('camera_label_source','camera_label_sha256'),('sonar_source','sonar_sha256')]:
            assert sha(x[p])==x[h]
        before=[o for o in old if o['recording']==x['recording']]
        assert min(abs(int(o['sample'].rsplit('_',1)[1])-x['frame']) for o in before)>=2
        assert min(abs(o['sd_index']-x['sd_index']) for o in before)>=2
        if d['decision']=='accepted':
            assert now[x['sample']]['sonar_bbox_xyxy']==d['bbox_xyxy']==x['proposal_xyxy']
            assert np.array_equal(np.array(Image.open(DEST/now[x['sample']]['sonar_image'])),raw_array(x['sonar_source']))
    hashes={m:defaultdict(set) for m in ('camera','sonar')};decoded=0
    for x in items:
        assert x['role']==role_by_rec[x['recording']] and x['membership']=='selected' and not x['training_ready']
        lab=read(DEST/x['camera_original_label']);assert sha(DEST/x['camera_original_label'])==x['camera_original_label_sha256']
        assert lab['class']==x['category'] and [[lab[k] for k in ('x_min','y_min','x_max','y_max')]]==x['camera_boxes_xyxy']
        for mod in ('camera','sonar'):
            p=DEST/x[mod+'_image'];hsh=sha(p);assert hsh==x[mod+'_image_sha256'];hashes[mod][hsh].add(x['role'])
            im=Image.open(p);im.load();decoded+=1;w,h=im.size
            assert (w,h)==((640,360) if mod=='camera' else tuple(x['sonar_size_wh']))
            if mod=='sonar':assert im.mode=='L' and w==128
            for b in x['camera_boxes_xyxy'] if mod=='camera' else [x['sonar_bbox_xyxy']]:
                assert 0<=b[0]<b[2]<=w and 0<=b[1]<b[3]<=h
    assert all(len(v)==1 for mod in hashes.values() for v in mod.values())
    summary=read(DEST/'summary.json')
    for role in ('train','val','test'):
        xs={x['sample']:x for x in items if x['role']==role}
        assert (DEST/f'{role}-selected.txt').read_text(encoding='utf-8').splitlines()==list(xs)
        s=summary[role];assert len(xs)==s['selected']==s['previous_selected']+s['admitted_previous_reserve']+s['new_pairs']
        for c in CLASSES:assert s['per_class_pairs'][c]==sum(x['category']==c for x in xs.values())
        for mod in ('camera','sonar'):
            coco=read(DEST/mod/f'coco_{role}.json');assert len(coco['images'])==len(coco['annotations'])==len(xs)
            ims={i['id']:i for i in coco['images']};assert len(ims)==len(xs)
            assert {i['sample'] for i in ims.values()}==set(xs)
            for a in coco['annotations']:
                i=ims[a['image_id']];x=xs[i['sample']];b=x['camera_boxes_xyxy'][0] if mod=='camera' else x['sonar_bbox_xyxy']
                assert i['file_name']==x[mod+'_image'] and i['recording']==x['recording']
                assert a['bbox']==[b[0],b[1],b[2]-b[0],b[3]-b[1]] and a['category_id']==list(CLASSES).index(x['category'])+1
                assert a['area']==(b[2]-b[0])*(b[3]-b[1])
    cov=read(DEST/'scene-coverage.json')
    assert sum(bool(c['complete']) for c in cov)==5 and sum(not c['complete'] for c in cov)==3
    for c in cov:
        for role in ('train','val','test'):
            assert c['role_pairs'][role]==sum(x['role']==role and x['scene_id']==c['scene_id'] for x in items)
    class Links(HTMLParser):
        def __init__(self):super().__init__();self.paths=[]
        def handle_starttag(self,tag,attrs):
            for k,v in attrs:
                if k in ('src','href') and v:self.paths.append(v)
    checked=0;pages=list((DEST/'recordings').glob('*.html'))+[DEST/'index.html']
    for page in pages:
        parser=Links();parser.feed(page.read_text(encoding='utf-8'))
        for url in parser.paths:
            u=urlparse(url);assert not u.scheme,url
            target=(page.parent/unquote(u.path)).resolve()
            if target==DEST/'verification.json':continue
            assert target.is_file(),target;checked+=1
    previews=list((DEST/'previews').glob('*.jpg'));assert len(previews)==36
    for p in previews:Image.open(p).load()
    for p,h in pr['input_sha256'].items():assert sha(p)==h,p
    result=dict(passed=True,total_pairs=len(items),previous_identities_boxes_hashes_roles_and_reviews_preserved=3716,
        previous_reserve_admitted=398,new_proposals_reviewed=640,new_accepted=345,new_unresolved_excluded=295,
        new_source_pairs_hashed_including_unresolved=640,all_export_images_hashed_and_decoded=decoded,
        raw_sonar_pixel_equality_checked=345,all_camera_boxes_equal_original_json=True,all_six_coco_files_and_lists_verified=True,
        source_groups=30,recording_and_group_roles_unchanged_and_disjoint=True,cross_role_duplicate_image_hashes=0,
        scene_coverage_complete=5,scene_coverage_incomplete=3,metadata_pan_recomputed_for_all_members=True,
        static_pages_checked=len(pages),static_links_checked=checked,previews_decoded=len(previews),browser_rendering_verified=False,
        original_test_content_opened=False,training=False,model_inference=False,user_or_expert_approval=False,
        input_hashes_unchanged=True)
    save(DEST/'verification.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
