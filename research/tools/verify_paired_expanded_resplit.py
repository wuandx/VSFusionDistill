"""Independently check every exported pair, label round-trip and split identity."""
from prepare_paired_resplit_additions import *
from collections import defaultdict,Counter
D=ROOT/'DataSet/paired_expanded_resplit_candidate'

def main():
    rows=read(D/'manifest.json');old={x['sample']:x for x in read(BASE/'manifest.json')};assert len(rows)==4836
    byid={x['sample']:x for x in rows};assert len(byid)==len(rows)
    roles={r:set((D/f'{r}.txt').read_text().splitlines()) for r in ('train','val','test')}
    assert set.union(*roles.values())==set(byid)
    assert sum(map(len,roles.values()))==len(rows)
    recroles=defaultdict(set);grouproles=defaultdict(set);hashroles={m:defaultdict(set) for m in ('camera','sonar')}
    for i,x in enumerate(rows):
        recroles[x['recording']].add(x['role']);grouproles[x['group_id']].add(x['role']);assert x['sample'] in roles[x['role']]
        for mod in ('camera','sonar'):
            p=(D/x[mod+'_image']).resolve();assert p.is_relative_to(D.resolve())
            assert sha(p)==x[mod+'_image_sha256'];assert sha(p)==sha(x[mod+'_source_this_version']) if not (mod=='sonar' and x['dataset_origin']!='accepted_4081') else True
            im=Image.open(p);im.load();wh=(640,360) if mod=='camera' else tuple(x['sonar_size_wh']);assert im.size==wh
            boxes=x['camera_boxes_xyxy'] if mod=='camera' else [x['sonar_bbox_xyxy']]
            lines=(D/mod/'labels_yolo'/f'{x["sample"]}.txt').read_text().splitlines();assert len(lines)==len(boxes)
            for line,b in zip(lines,boxes):
                v=line.split();assert int(v[0])==['100lbs_aircraft_bomb','mortar_shell','incindiary_grenade'].index(x['category']);cx,cy,bw,bh=map(float,v[1:]);back=np.array([(cx-bw/2)*wh[0],(cy-bh/2)*wh[1],(cx+bw/2)*wh[0],(cy+bh/2)*wh[1]]);assert np.max(np.abs(back-b))<1e-6
            hashroles[mod][sha(p)].add(x['role'])
        assert sha(D/x['camera_original_label'])==x['camera_original_label_sha256']==sha(x['camera_label_source_this_version'])
        if x['sample'] in old:
            o=old[x['sample']]
            for k in ('recording','category','camera_boxes_xyxy','sonar_bbox_xyxy','sonar_size_wh','camera_image_sha256','sonar_image_sha256','camera_original_label_sha256'):assert x[k]==o[k],(x['sample'],k)
        else:
            assert x['review']['decision']=='accepted' and sha(x['review']['sheet'])==x['review']['sheet_sha256']
            assert np.array_equal(raw_array(x['sonar_source_this_version']),np.array(Image.open(D/x['sonar_image'])))
        if i%1000==0:print('verified',i,flush=True)
    assert all(len(v)==1 for v in recroles.values()) and all(len(v)==1 for v in grouproles.values())
    assert all(len(v)==1 for m in hashroles.values() for v in m.values())
    for role,ids in roles.items():
        for mod in ('camera','sonar'):
            c=read(D/mod/f'coco_{role}.json');images={im['id']:im for im in c['images']};assert len(images)==len(ids) and {im['sample'] for im in images.values()}==ids
            assert [v['name'] for v in c['categories']]==['100lbs_aircraft_bomb','mortar_shell','incindiary_grenade']
            assert len({a['id'] for a in c['annotations']})==len(c['annotations'])
            counts=Counter()
            for a in c['annotations']:
                im=images[a['image_id']];x=byid[im['sample']];assert im['file_name']==x[mod+'_image'];b=a['bbox'];expected=x['camera_boxes_xyxy'] if mod=='camera' else [x['sonar_bbox_xyxy']]
                assert [b[0],b[1],b[0]+b[2],b[1]+b[3]] in expected;assert a['area']==b[2]*b[3] and a['iscrowd']==0;assert a['category_id']==['100lbs_aircraft_bomb','mortar_shell','incindiary_grenade'].index(x['category'])+1;counts[im['id']]+=1
            assert all(counts[i]==1 for i in images)
    p=read(D/'protocol.json');assert all(sha(k)==v for k,v in p['input_sha256'].items())
    report=dict(passed=True,pairs=len(rows),old_pairs_preserved=len(old),new_pairs=len(rows)-len(old),recordings=len(recroles),source_groups=len(grouproles),all_exported_files_decoded_and_hashed=True,all_coco_and_yolo_round_trips=True,all_new_raw_png_pixels_identical=True,review_sheet_hashes_unchanged=True,source_group_disjoint=True,cross_role_image_hash_duplicates=0,manifest_sha256=sha(D/'manifest.json'),protocol_sha256=sha(D/'protocol.json'))
    save(D/'independent-verification.json',report);print(report,flush=True)
if __name__=='__main__':main()
