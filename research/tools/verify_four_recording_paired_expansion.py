"""Independently verify the combined export, timing identities and annotation formats."""
from expand_paired_recording_pool import *
from html.parser import HTMLParser
from decimal import Decimal

D=ROOT/'DataSet/paired_four_recording_expanded'
B=ROOT/'DataSet/paired_expanded_resplit_candidate'
R=ROOT/'DataSet/four_recording_paired_annotation'
ROLES=('train','val','test')
CATEGORIES=['100lbs_aircraft_bomb','mortar_shell','incindiary_grenade']


class Links(HTMLParser):
    def __init__(self):super().__init__();self.paths=[]
    def handle_starttag(self,tag,attrs):
        for k,v in attrs:
            if k in ('href','src') and v and not v.startswith(('#','http','data:')):self.paths.append(v.split('#')[0])


def main():
    rows=read(D/'manifest.json');old=read(B/'manifest.json');added=read(D/'added-manifest.json')
    unresolved=read(D/'unresolved/manifest.json');p=read(D/'protocol.json')
    assert len(rows)==5229 and len(old)==4836 and len(added)==393 and len(unresolved)==7
    assert rows[:4836]==old and rows[4836:]==added
    byid={x['sample']:x for x in rows};assert len(byid)==len(rows)
    assert not set(byid)&{x['sample'] for x in unresolved}
    assert all(x['role']=='train' and x['decision']=='accepted' for x in added)
    roles={role:set((D/f'{role}.txt').read_text().splitlines()) for role in ROLES}
    assert set.union(*roles.values())==set(byid) and sum(map(len,roles.values()))==len(rows)
    recroles=defaultdict(set);grouproles=defaultdict(set)
    encoded={m:defaultdict(set) for m in ('camera','sonar')};pixels={m:defaultdict(set) for m in ('camera','sonar')}
    for idx,x in enumerate(rows):
        assert x['sample'] in roles[x['role']]
        recroles[x['recording']].add(x['role']);grouproles[x['group_id']].add(x['role'])
        for mod in ('camera','sonar'):
            f=(D/x[mod+'_image']).resolve();assert f.is_relative_to(D.resolve())
            digest=sha(f);assert digest==x[mod+'_image_sha256']
            im=Image.open(f);im.load();wh=(640,360) if mod=='camera' else tuple(x['sonar_size_wh'])
            assert im.size==wh
            encoded[mod][digest].add(x['role']);pixels[mod][hashlib.sha256(im.tobytes()).hexdigest()].add(x['role'])
            bb=x['camera_boxes_xyxy'] if mod=='camera' else [x['sonar_bbox_xyxy']]
            labels=(D/mod/'labels_yolo'/(x['sample']+'.txt')).read_text().splitlines();assert len(labels)==len(bb)
            for line,b in zip(labels,bb):
                v=line.split();assert int(v[0])==CATEGORIES.index(x['category'])
                assert 0<=b[0]<b[2]<=wh[0] and 0<=b[1]<b[3]<=wh[1]
                cx,cy,bw,bh=map(float,v[1:]);back=[(cx-bw/2)*wh[0],(cy-bh/2)*wh[1],(cx+bw/2)*wh[0],(cy+bh/2)*wh[1]]
                assert max(abs(a-z) for a,z in zip(back,b))<1e-6
            if idx<4836:
                assert digest==sha(B/x[mod+'_image'])
                rel=Path(mod)/'labels_yolo'/(x['sample']+'.txt');assert sha(D/rel)==sha(B/rel)
            elif mod=='camera':assert digest==sha(x['camera_source'])
            else:
                # PIL decodes raw PGM independently of the exporter's OpenCV path.
                raw=np.array(Image.open(x['sonar_source']));assert raw.dtype==np.uint8
                assert np.array_equal(raw,np.array(im)) and sha(x['sonar_source'])==x['sonar_raw_sha256']
        if idx<4836:assert sha(D/x['camera_original_label'])==x['camera_original_label_sha256']==sha(B/x['camera_original_label'])
        else:
            assert 'camera_original_label' not in x
            assert sha(D/x['camera_annotation'])==x['camera_annotation_sha256']
            ann=read(D/x['camera_annotation']);assert ann['boxes_xyxy']==x['camera_boxes_xyxy'] and ann['class_name']==x['category']
            assert ann['annotation_origin']=='assistant_new_visible_target_annotation' and not ann['expert_verified']
            for evidence in x['review']['visual_evidence']:assert sha(evidence['sheet'])==evidence['sha256']
            assert sha(D/x['review_sheet'])==x['review']['final_sheet_sha256']
        if idx%1500==0:print('verified',idx,flush=True)
    assert all(len(v)==1 for v in recroles.values()) and all(len(v)==1 for v in grouproles.values())
    assert len(recroles)==42 and len(grouproles)==35
    for mode in (encoded,pixels):assert all(len(v)==1 for m in mode.values() for v in m.values())
    for role in ROLES:
        for mod in ('camera','sonar'):
            c=read(D/mod/f'coco_{role}.json');ims={i['id']:i for i in c['images']}
            assert len(ims)==len(roles[role]) and {i['sample'] for i in ims.values()}==roles[role]
            assert [z['name'] for z in c['categories']]==CATEGORIES
            assert len({a['id'] for a in c['annotations']})==len(c['annotations'])
            count=Counter()
            for a in c['annotations']:
                im=ims[a['image_id']];x=byid[im['sample']];assert im['file_name']==x[mod+'_image']
                bb=x['camera_boxes_xyxy'] if mod=='camera' else [x['sonar_bbox_xyxy']]
                b=a['bbox'];assert [b[0],b[1],b[0]+b[2],b[1]+b[3]] in bb
                assert a['category_id']==CATEGORIES.index(x['category'])+1 and a['area']==b[2]*b[3] and a['iscrowd']==0
                count[im['id']]+=1
            assert all(count[i]==1 for i in ims)
            if role!='train':assert sha(D/mod/f'coco_{role}.json')==sha(B/mod/f'coco_{role}.json')
        if role!='train':assert sha(D/f'{role}.txt')==sha(B/f'{role}.txt')
    for mod in ('camera','sonar'):
        c=read(D/mod/'coco_added_train.json');assert {im['sample'] for im in c['images']}=={x['sample'] for x in added}
        assert len(c['annotations'])==393
    for x in unresolved:
        assert x['role']=='unresolved' and not x['training_ready']
        assert x['recording']=='2023-09-21_124440' and 17<=x['ordinal']<=23
        for mod in ('camera','sonar'):
            assert sha(D/x[mod+'_image'])==x[mod+'_image_sha256']
            Image.open(D/x[mod+'_image']).load()
            assert not (D/mod/'labels_yolo'/(x['sample']+'.txt')).exists()
    # Recompute the mapping independently using Decimal timestamps and exact fps.
    matches={Path(m['aris_file']).name:m for m in csv.DictReader((DATA/'data_processed/matches.csv').open(encoding='utf-8-sig'))}
    probes={r['recording']:r for r in read(R/'recordings.json')};mapping_count=0;extractions=[]
    qa=R/'independent_sd_extraction';assert not qa.exists(),'Preserve earlier verification outputs';qa.mkdir()
    for rec,rr in probes.items():
        match=matches[rec];metadata=DATA/'data_processed/aris'/rec/(rec+'_frames.csv')
        md={int(m['FrameIndex']):m for m in csv.DictReader(metadata.open(encoding='utf-8-sig'))}
        onset=int(md[int(match['aris_onset'])]['FrameTime']);num,den=map(int,rr['probe']['avg_frame_rate'].split('/'))
        xx=sorted([x for x in added+unresolved if x['recording']==rec],key=lambda x:x['ordinal'])
        for x in xx:
            delta=int(md[x['frame']]['FrameTime'])-onset
            expected=int(Decimal(delta)*Decimal(num)/Decimal(1000000*den))+int(match['gopro_offset'])
            assert expected==x['sd_index'] and 0<=expected<int(rr['probe']['nb_frames']);mapping_count+=1
        for j in (0,50,99):
            x=xx[j];out=qa/f'{rec}-{j}.jpg'
            run(['ffmpeg','-hide_banner','-loglevel','error','-threads','2','-i',rr['source_clip'],
                 '-vf',f'select=eq(n\\,{x["sd_index"]})','-fps_mode','passthrough','-frames:v','1','-q:v','2',str(out)])
            assert sha(out)==x['camera_sha256'],(rec,j,'independent SD extraction differs')
            extractions.append(dict(sample=x['sample'],sd_index=x['sd_index'],sha256=sha(out)))
    assert mapping_count==400 and len(extractions)==12
    for path,h in p['original_input_sha256'].items():
        check=Path(p['original_plan_snapshot']) if path.endswith('four-recording-paired-annotation-plan.md') else Path(path)
        assert sha(check)==h
    assert all(sha(path)==h for path,h in p['input_sha256'].items())
    links=0
    for page in D.glob('*.html'):
        parser=Links();parser.feed(page.read_text(encoding='utf-8'))
        for path in parser.paths:
            if path=='independent-verification.json':continue
            assert (page.parent/path).is_file(),(page,path)
            links+=1
    report=dict(passed=True,pairs=5229,added_pairs=393,unresolved=7,recordings=42,conservative_source_groups=35,
        previous_4836_rows_images_labels_roles_preserved=True,val_test_indices_and_coco_byte_identical=True,
        all_10458_admitted_images_decoded_and_hashed=True,new_raw_png_pixels_equal_PIL_independent_decoder=True,
        all_coco_yolo_roundtrips=True,new_camera_annotation_origin_explicit=True,
        source_groups_disjoint=True,cross_role_encoded_and_decoded_pixel_hash_duplicates=0,
        published_timing_mapping_recomputed=400,independent_exact_SD_extractions=extractions,
        unresolved_not_negative_or_training_samples=True,source_and_base_input_hashes_unchanged=True,
        static_html_links_checked=links,browser_render_verified=False,
        original_research_test_opened=False,existing_test_copy_decode_integrity_only=True,
        model_inference=False,training=False,expert_verified=False,precision_sync_certified=False,
        manifest_sha256=sha(D/'manifest.json'),protocol_sha256=sha(D/'protocol.json'))
    save(D/'independent-verification.json',report);print({k:v for k,v in report.items() if k!='independent_exact_SD_extractions'},flush=True)


if __name__=='__main__':main()
