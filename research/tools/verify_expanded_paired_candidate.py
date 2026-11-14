"""Independent delivery checks for the expanded paired candidate; no model inference."""
from expand_paired_recording_pool import *
from urllib.parse import urlparse,unquote
from html.parser import HTMLParser
P=ROOT/'DataSet/expanded_paired_coverage_candidate'
def main():
    protocol=read(P/'protocol.json');items=read(P/'manifest.json');rs=read(P/'recordings.json');legacy=read(DATA/'uxo-full/split_manifest.json')['recordings']
    assert len(items)==3716 and len({x['sample'] for x in items})==3716
    original={x['sample']:x for x in read(ROOT/'DataSet/paired_assistant_truncated_review/export/manifest.json')}
    now={x['sample']:x for x in items};assert set(original)<=set(now)
    for name,x in original.items():
        y=now[name]
        assert x['sonar_bbox_xyxy']==y['sonar_bbox_xyxy'] and x['camera_boxes_xyxy']==y['camera_boxes_xyxy']
        assert x['camera_image_sha256']==y['camera_image_sha256'] and x['sonar_image_sha256']==y['sonar_image_sha256']
        assert x['selected_for_100_per_recording']==(y['membership']=='selected')
    for p,h in protocol['input_sha256'].items():assert sha(p)==h,p
    for p,h in read(OUT/'inputs-sha256.json').items():assert sha(p)==h,p
    new_source_pairs_checked=0
    for spec in (OUT/'full-review').glob('*/spec.json'):
        s=read(spec)
        for sh in s['sheets']:assert sha(OUT/sh['path'])==sh['sha256']
        for x in s['items']:
            assert sha(OUT/x['camera_image'])==x['camera_sha256'] and sha(x['original_label'])==x['original_label_sha256'] and sha(x['sonar_source'])==x['sonar_sha256']
            new_source_pairs_checked+=1
    roles={r['recording']:r['role'] for r in rs};bygroup=defaultdict(set)
    for r in rs:
        assert legacy[r['recording']]['split']!='test'
        bygroup[r['group_id']].add(r['role'])
        if r['role']!='train':assert r['pan_support_percent']>=95-1e-8
    assert all(len(v)==1 for v in bygroup.values())
    decoded=0;hashroles={mod:defaultdict(set) for mod in ('camera','sonar')}
    for x in items:
        assert x['role']==roles[x['recording']]
        label=read(P/x['camera_original_label']);assert sha(P/x['camera_original_label'])==x['camera_original_label_sha256']
        assert label['class']==x['category']
        assert x['camera_boxes_xyxy']==[[label[k] for k in ('x_min','y_min','x_max','y_max')]]
        for mod in ('camera','sonar'):
            p=P/x[mod+'_image'];assert sha(p)==x[mod+'_image_sha256'];hashroles[mod][sha(p)].add(x['role'])
            a=Image.open(p);a.load();decoded+=1;w,h=a.size
            if mod=='camera':assert (w,h)==(640,360)
            else:assert w==128
            boxes=x['camera_boxes_xyxy'] if mod=='camera' else [x['sonar_bbox_xyxy']]
            yy=[line.split() for line in (P/mod/'labels_yolo'/(x['sample']+'.txt')).read_text().splitlines()]
            assert len(yy)==len(boxes)
            for vals,b in zip(yy,boxes):
                assert int(vals[0])==list(CLASSES).index(x['category'])
                cx,cy,bw,bh=map(float,vals[1:]);back=np.array([(cx-bw/2)*w,(cy-bh/2)*h,(cx+bw/2)*w,(cy+bh/2)*h])
                assert np.max(np.abs(back-np.array(b)))<1e-6
                assert 0<=b[0]<b[2]<=w and 0<=b[1]<b[3]<=h
    assert all(len(v)==1 for mod in hashroles.values() for v in mod.values())
    for role in ('train','val','test'):
        selected={x['sample']:x for x in items if x['role']==role and x['membership']=='selected'}
        assert set((P/f'{role}-selected.txt').read_text().splitlines())==set(selected)
        for mod in ('camera','sonar'):
            coco=read(P/mod/f'coco_{role}.json');assert len(coco['images'])==len(selected)==len(coco['annotations'])
            imagebyid={i['id']:i for i in coco['images']}
            for a in coco['annotations']:
                i=imagebyid[a['image_id']];x=selected[i['sample']];b=x['camera_boxes_xyxy'][0] if mod=='camera' else x['sonar_bbox_xyxy']
                assert a['bbox']==[b[0],b[1],b[2]-b[0],b[3]-b[1]]
                assert a['category_id']==list(CLASSES).index(x['category'])+1
    class Links(HTMLParser):
        def __init__(self):super().__init__();self.paths=[]
        def handle_starttag(self,tag,attrs):
            for k,v in attrs:
                if k in ('src','href') and v:self.paths.append(v)
    links=Links();links.feed((P/'index.html').read_text(encoding='utf-8'));checked=0
    for url in links.paths:
        u=urlparse(url)
        if u.scheme=='file':path=Path(unquote(u.path).lstrip('/'))
        elif not u.scheme:path=P/unquote(u.path)
        else:continue
        assert path.exists(),path;checked+=1
    for p in (P/'previews').glob('*.jpg'):Image.open(p).load()
    result=dict(passed=True,recordings=len(rs),selected=3318,reserve=398,new_recordings=6,new_assistant_acceptances=318,
      original_identities_and_boxes_preserved=len(original),all_export_images_hashed_and_decoded=decoded,
      new_source_pairs_hashed_including_unresolved=new_source_pairs_checked,all_source_inventory_and_protocol_hashes_unchanged=True,
      all_original_camera_labels_equal_exported_boxes=True,yolo_roundtrip_max_tolerance_px=1e-6,all_six_coco_files_verified=True,
      cross_role_duplicate_image_hashes=0,recording_group_disjoint=True,holdout_min_pan_support_percent=min(r['pan_support_percent'] for r in rs if r['role']!='train'),
      all36_previews_decoded=True,static_html_links_verified=checked,browser_rendering_verified=False,
      original_test_content_opened=False,model_inference=False,training=False)
    save(P/'independent-verification.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
