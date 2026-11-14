"""Check the actual scene allocation, unchanged samples and rendered review links."""
from expand_paired_recording_pool import *
from html.parser import HTMLParser
from urllib.parse import urlparse,unquote
P=ROOT/'DataSet/scene_stratified_recording_candidate'
S=ROOT/'DataSet/expanded_paired_coverage_candidate'
def main():
    a=read(P/'manifest.json');previous={x['sample']:x for x in read(S/'manifest.json')};rr=read(P/'recordings.json');coverage=read(P/'scene-coverage.json');protocol=read(P/'protocol.json')
    assert len(a)==3716==len({x['sample'] for x in a}) and set(previous)=={x['sample'] for x in a}
    assert sum(x['membership']=='selected' for x in a)==3318
    assert sum(x['membership']=='reserve' for x in a)==398
    for p,h in protocol['input_sha256'].items():assert sha(p)==h,p
    byrec={r['recording']:r for r in rr};grouproles=defaultdict(set);recroles=defaultdict(set);hashroles={mod:defaultdict(set) for mod in ('camera','sonar')};decoded=0
    for x in a:
        old=previous[x['sample']];r=byrec[x['recording']]
        for k in ('membership','camera_boxes_xyxy','sonar_bbox_xyxy','camera_image_sha256','sonar_image_sha256','camera_original_label_sha256','group_id','training_ready'):assert x[k]==old[k],(x['sample'],k)
        assert x['role']==r['role'];assert x['scene_id']=='|'.join(r[k] for k in ('category','placement','trajectory'))
        grouproles[x['group_id']].add(x['role']);recroles[x['recording']].add(x['role'])
        for mod in ('camera','sonar'):
            p=(P/x[mod+'_image']).resolve();assert sha(p)==x[mod+'_image_sha256']
            img=Image.open(p);img.load();decoded+=1
            w,h=img.size;assert (w,h)==((640,360) if mod=='camera' else tuple(x['sonar_size_wh']))
            hashroles[mod][sha(p)].add(x['role'])
            for b in x['camera_boxes_xyxy'] if mod=='camera' else [x['sonar_bbox_xyxy']]:assert 0<=b[0]<b[2]<=w and 0<=b[1]<b[3]<=h
        assert sha(P/x['camera_original_label'])==x['camera_original_label_sha256']
    assert all(len(v)==1 for v in grouproles.values()) and all(len(v)==1 for v in recroles.values())
    assert all(len(v)==1 for d in hashroles.values() for v in d.values())
    for c in coverage:
        rows=[r for r in rr if r['scene_id']==c['scene_id']];groups={r['group_id'] for r in rows}
        assert c['source_groups']==len(groups)
        for role in ('train','val','test'):
            subset=[r for r in rows if r['role']==role]
            assert c['members'][role]==[r['recording'] for r in subset]
            assert c['role_pairs'][role]==sum(r['selected'] for r in subset)
        if len(groups)>=3:assert all(c['members'][role] for role in ('train','val','test')) and c['complete']
        else:assert not c['complete'] and c['additional_accepted_groups_needed']==3-len(groups)
    assert len(coverage)==8 and sum(c['complete'] for c in coverage)==5
    coco_files=0
    for role in ('train','val','test'):
        for membership in ('selected','reserve'):
            names={x['sample'] for x in a if x['role']==role and x['membership']==membership}
            assert set((P/f'{role}-{membership}.txt').read_text(encoding='utf-8').splitlines())==names
        sel={x['sample']:x for x in a if x['role']==role and x['membership']=='selected'}
        for mod in ('camera','sonar'):
            c=read(P/mod/f'coco_{role}.json');imgs={i['id']:i for i in c['images']};assert {i['sample'] for i in imgs.values()}==set(sel)
            assert len(c['annotations'])==len(sel)
            for ann in c['annotations']:
                im=imgs[ann['image_id']];x=sel[im['sample']];assert im['file_name']==x[mod+'_image'];assert (P/im['file_name']).exists()
                b=x['camera_boxes_xyxy'][0] if mod=='camera' else x['sonar_bbox_xyxy'];assert ann['bbox']==[b[0],b[1],b[2]-b[0],b[3]-b[1]]
                assert ann['category_id']==list(CLASSES).index(x['category'])+1
            coco_files+=1
    class Links(HTMLParser):
        def __init__(self):super().__init__();self.paths=[]
        def handle_starttag(self,tag,attrs):
            for k,v in attrs:
                if k in ('src','href') and v:self.paths.append(v)
    l=Links();l.feed((P/'index.html').read_text(encoding='utf-8'));links=0
    for url in l.paths:
        u=urlparse(url)
        if u.scheme=='file':p=Path(unquote(u.path).lstrip('/'))
        elif not u.scheme:p=P/unquote(u.path)
        else:continue
        if p.name=='verification.json':continue
        assert p.exists(),p;links+=1
    previews=list((P/'previews').glob('*.jpg'));assert len(previews)==36
    for p in previews:Image.open(p).load()
    legacy=read(DATA/'uxo-full/split_manifest.json')['recordings']
    assert all(legacy[r['recording']]['split']!='test' for r in rr)
    save(P/'verification.json',dict(passed=True,unique_identities=3716,selected=3318,reserve=398,recordings=36,source_groups=len(grouproles),
      total_scenes=8,scenes_in_all_three_roles=5,incomplete_scenes=3,all_scenes_with_at_least_three_groups_covered_in_all_roles=True,
      recording_and_source_group_disjoint=True,cross_role_duplicate_image_hashes=0,all_3716_image_hashes_boxes_and_membership_preserved=True,
      exported_images_hashed_and_decoded=decoded,all_six_coco_files_verified=coco_files==6,all_manifest_and_list_members_equal=True,
      input_and_previous_candidate_hashes_unchanged=True,preview_images_decoded=len(previews),static_html_links_verified=links,
      browser_rendering_verified=False,newly_accepted_annotations=0,training=False,model_inference=False,original_test_content_opened=False))
    save(P/'artifact-sha256.json',{str(p.relative_to(P)):sha(p) for p in P.rglob('*') if p.is_file() and p.name!='artifact-sha256.json'})
    print(json.dumps(read(P/'verification.json'),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
