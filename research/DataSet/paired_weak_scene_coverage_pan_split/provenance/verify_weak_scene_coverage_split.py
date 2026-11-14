"""Independent exported-role, label, group, condition and pan verification."""
from expand_paired_recording_pool import *
from itertools import combinations
from html.parser import HTMLParser

D=ROOT/'DataSet/paired_weak_scene_coverage_pan_split'
B=ROOT/'DataSet/paired_four_recording_expanded'
ROLES=('train','val','test')


class Links(HTMLParser):
    def __init__(self):super().__init__();self.paths=[]
    def handle_starttag(self,tag,attrs):
        self.paths.extend(v for k,v in attrs if k in ('href','src') and v and not v.startswith(('#','http','data:')))


def main():
    rows=read(D/'manifest.json');base={x['sample']:x for x in read(B/'manifest.json')}
    rs=read(D/'recordings.json');byrec={r['recording']:r for r in rs};protocol=read(D/'protocol.json')
    assert len(rows)==len(base)==5229 and len(rs)==42 and len({r['group_id'] for r in rs})==35
    byid={x['sample']:x for x in rows};assert len(byid)==5229 and set(byid)==set(base)
    roles={role:set((D/f'{role}.txt').read_text().splitlines()) for role in ROLES}
    assert set.union(*roles.values())==set(base) and sum(map(len,roles.values()))==len(base)
    hashes={mod:defaultdict(set) for mod in ('camera','sonar')};pixels={mod:defaultdict(set) for mod in ('camera','sonar')}
    group_roles=defaultdict(set);rec_roles=defaultdict(set)
    for i,x in enumerate(rows):
        old=base[x['sample']];expected=dict(old,role_before_weak_coverage_resplit=old['role'],role=x['role'])
        assert x==expected
        assert x['sample'] in roles[x['role']] and byrec[x['recording']]['role']==x['role']
        group_roles[x['group_id']].add(x['role']);rec_roles[x['recording']].add(x['role'])
        for mod in ('camera','sonar'):
            path=(D/x[mod+'_image']).resolve();assert path.is_relative_to(D.resolve())
            h=sha(path);assert h==x[mod+'_image_sha256']==sha(B/x[mod+'_image'])
            im=Image.open(path);im.load();wh=(640,360) if mod=='camera' else tuple(x['sonar_size_wh'])
            assert im.size==wh;hashes[mod][h].add(x['role']);pixels[mod][hashlib.sha256(im.tobytes()).hexdigest()].add(x['role'])
            lab=Path(mod)/'labels_yolo'/(x['sample']+'.txt');assert sha(D/lab)==sha(B/lab)
            boxes=x['camera_boxes_xyxy'] if mod=='camera' else [x['sonar_bbox_xyxy']]
            lines=(D/lab).read_text().splitlines();assert len(lines)==len(boxes)
            for line,b in zip(lines,boxes):
                vals=line.split();assert int(vals[0])==list(CLASSES).index(x['category'])
                assert 0<=b[0]<b[2]<=wh[0] and 0<=b[1]<b[3]<=wh[1]
                cx,cy,bw,bh=map(float,vals[1:]);bb=[(cx-bw/2)*wh[0],(cy-bh/2)*wh[1],(cx+bw/2)*wh[0],(cy+bh/2)*wh[1]]
                assert max(abs(a-z) for a,z in zip(bb,b))<1e-6
        field='camera_original_label' if 'camera_original_label' in x else 'camera_annotation'
        assert sha(D/x[field])==sha(B/x[field])
        if i%1500==0:print('verified',i,flush=True)
    assert all(len(v)==1 for v in rec_roles.values()) and all(len(v)==1 for v in group_roles.values())
    for hh in (hashes,pixels):assert all(len(v)==1 for mod in hh.values() for v in mod.values())
    for role in ROLES:
        assert {x['category'] for x in rows if x['role']==role}==set(CLASSES)
        for mod in ('camera','sonar'):
            c=read(D/mod/f'coco_{role}.json');images={im['id']:im for im in c['images']}
            assert len(images)==len(roles[role]) and {im['sample'] for im in images.values()}==roles[role]
            assert c['categories']==[dict(id=i+1,name=cl) for i,cl in enumerate(CLASSES)]
            assert len({a['id'] for a in c['annotations']})==len(c['annotations'])
            count=Counter()
            for a in c['annotations']:
                im=images[a['image_id']];x=byid[im['sample']]
                assert im['file_name']==x[mod+'_image']
                boxes=x['camera_boxes_xyxy'] if mod=='camera' else [x['sonar_bbox_xyxy']]
                b=a['bbox'];assert [b[0],b[1],b[0]+b[2],b[1]+b[3]] in boxes
                assert a['category_id']==list(CLASSES).index(x['category'])+1 and a['area']==b[2]*b[3] and a['iscrowd']==0
                assert (im['width'],im['height'])==((640,360) if mod=='camera' else tuple(x['sonar_size_wh']))
                count[im['id']]+=1
            assert all(count[i]==1 for i in images)
    focus=protocol['focus_recordings'];assert all(byrec[r]['role']=='train' for r in focus)
    joint=lambda r:(r['scene_id'],r['z'],r['tilt'],r['roll'])
    alljoint={joint(r) for r in rs};trainjoint={joint(r) for r in rs if r['role']=='train'}
    assert alljoint==trainjoint and len(alljoint)==27
    # Independent minimum set-cover enumeration verifies the structural holdout limits.
    limits=[]
    for sid in sorted({r['scene_id'] for r in rs}):
        rr=[r for r in rs if r['scene_id']==sid];groups=sorted({r['group_id'] for r in rr});jj={joint(r) for r in rr}
        minimum=None
        for n in range(1,len(groups)+1):
            if any({joint(r) for r in rr if r['group_id'] in gs}==jj for gs in combinations(groups,n)):
                minimum=n;break
        limits.append(dict(scene=sid,minimum_groups_for_full_joint_train=minimum,max_independent_holdout_groups=len(groups)-minimum))
    expected_limits={x['scene']:x['maximum_holdout_groups_with_all_joint_conditions'] for x in read(D/'search.json')}
    assert all(expected_limits[x['scene']]==x['max_independent_holdout_groups'] for x in limits)
    md={}
    for r in rs:
        path=Path(r['source_root'])/'aris_frame_meta.csv'
        md[r['recording']]={int(m['FrameIndex']):float(m['SonarPan']) for m in csv.DictReader(path.open(encoding='utf-8-sig'))}
    recorded={r['recording']:r for r in read(D/'pan-support.json')};held=[]
    for r in rs:
        if r['role']=='train':continue
        trainrecs=[t['recording'] for t in rs if t['role']=='train' and joint(t)==joint(r)]
        tv=[md[x['recording']][int(x.get('aris_frame',x['sample'].rsplit('_',1)[1]))] for x in rows if x['recording'] in trainrecs]
        values=[md[x['recording']][int(x.get('aris_frame',x['sample'].rsplit('_',1)[1]))] for x in rows if x['recording']==r['recording']]
        rate=100*sum(any(abs((v-w+180)%360-180)<=5 for w in tv) for v in values)/len(values)
        assert abs(rate-recorded[r['recording']]['same_joint_train_pan_within_5_degree_percent'])<1e-8
        held.append(dict(recording=r['recording'],role=r['role'],percent=rate))
    unresolved=read(B/'unresolved/manifest.json');assert not {x['sample'] for x in unresolved}&set(byid)
    assert all(sha(k)==v for k,v in protocol['input_sha256'].items())
    links=0
    for f in D.glob('*.html'):
        parser=Links();parser.feed(f.read_text(encoding='utf-8'))
        for path in parser.paths:
            if path=='independent-verification.json':continue
            assert (f.parent/path).is_file(),(f,path)
            links+=1
    for f in (D/'previews').glob('*.jpg'):Image.open(f).load()
    assert len(list((D/'previews').glob('*.jpg')))==42
    report=dict(passed=True,pairs=5229,recordings=42,conservative_groups=35,
        all_base_5229_identities_images_boxes_annotation_origin_preserved=True,
        changed_fields_only_role_and_previous_role=True,decoded_and_hashed_images=10458,
        coco_and_yolo_roundtrip_passed=True,all_three_classes_in_each_role=True,
        source_groups_and_recordings_disjoint=True,cross_role_encoded_and_pixel_hash_duplicates=0,
        all_27_observed_scene_z_tilt_roll_conditions_in_train=True,all_focus_recordings_in_train=True,
        independent_set_cover_limits=limits,independent_pan_recomputed=held,
        below95_pan_support=[x for x in held if x['percent']<95-1e-8],
        unresolved_admitted=0,original_input_hashes_unchanged=True,
        static_links_verified=links,previews_decoded=42,browser_render_verified=False,
        new_model_inference=False,new_training=False,new_model_metrics=False,
        new_split_is_development_protocol_with_old_val_test_use=True,
        original_research_test_opened=False,expert_verified=False,precision_sync_certified=False,
        manifest_sha256=sha(D/'manifest.json'),protocol_sha256=sha(D/'protocol.json'))
    save(D/'independent-verification.json',report)
    print({k:v for k,v in report.items() if k not in ('independent_set_cover_limits','independent_pan_recomputed')},flush=True)


if __name__=='__main__':main()
