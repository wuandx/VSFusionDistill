"""Export the 900 visually reviewed camera additions, preserving original train/val."""
from prepare_camera_more_recordings import *
from datetime import datetime, timezone

BASE=ROOT/'DataSet/scene_expanded_baseline_trainval'
DEST=ROOT/'DataSet/camera_more_recordings_trainval_verified'
def main():
    DEST.mkdir(exist_ok=False);(DEST/'camera/images').mkdir(parents=True)
    proposed=read(OUT/'manifest.json');assert len(proposed)==900
    reviews=[]
    for rec in read(OUT/'recordings.json'):
        for sheet in rec['sheets']:assert sha(OUT/sheet['path'])==sheet['sha256']
        if not rec['proposed']:continue
        reviews.append(dict(recording=rec['recording'],accepted_ordinals=list(range(100)),reviewer='assistant',reviewed_at=datetime.now(timezone.utc).isoformat(),sheets=rec['sheets'],reason='Viewed all four corrected SD sheets (100 images): identifiable class target and corresponding unchanged box. Recognizable frame-edge truncation retained under existing policy.',expert_verified=False))
    save(DEST/'assistant-camera-review.json',reviews)
    files={};counts={};hashes={};train_recs={}
    for role in ['train','val']:
        ds=read(BASE/f'camera-{role}-dataset.json');coco=read(BASE/f'camera-{role}-coco.json')
        for r in ds:
            src=BASE/r['fp_camera'];dest=DEST/r['fp_camera'];shutil.copyfile(src,dest)
            assert sha(src)==sha(dest)==r['source_image_sha256']
        if role=='train':
            for r in proposed:
                src=OUT/r['image'];dest=DEST/'camera/images'/(r['sample']+'.jpg');shutil.copyfile(src,dest)
                assert sha(dest)==r['source_sha256'] and sha(r['label_source'])==r['label_sha256']
                ci=next(c['id'] for c in coco['categories'] if c['name']==r['category'])
                x,y,x2,y2=r['box'];b=[x,y,x2-x,y2-y];iid=len(coco['images'])+1
                ds.append(dict(sample_id=r['sample'],recording=r['recording'],group_id=r['group_id'],scene_id=r['scene_id'],role='train',width=640,height=360,fp_camera=str(dest.relative_to(DEST)).replace('\\','/'),fp_sonar=None,boxes_camera=[b],labels_camera=[ci-1],boxes_sonar=[],labels_sonar=[],deg_level='d0',deg_seed=0,source_image=r['source'],source_image_sha256=r['source_sha256'],coco_camera_image_id=iid))
                coco['images'].append(dict(id=iid,file_name=ds[-1]['fp_camera'],width=640,height=360,sample=r['sample'],recording=r['recording'],scene=r['scene_id'],scene_id=r['scene_id'],group_id=r['group_id']))
                coco['annotations'].append(dict(id=len(coco['annotations'])+1,image_id=iid,category_id=ci,bbox=b,area=b[2]*b[3],iscrowd=0))
        assert len(ds)==len({r['sample_id'] for r in ds})==len(coco['images'])==len(coco['annotations'])
        hashes[role]=set()
        for r in ds:
            p=DEST/r['fp_camera'];h=sha(p);files[r['fp_camera']]=h;hashes[role].add(h)
            with Image.open(p) as im:im.load();assert im.size==(640,360)
        if role=='val':
            for suffix in ['dataset','coco']:shutil.copyfile(BASE/f'camera-val-{suffix}.json',DEST/f'camera-val-{suffix}.json')
        else:
            save(DEST/f'camera-{role}-dataset.json',ds);save(DEST/f'camera-{role}-coco.json',coco)
        counts[role]=dict(images=len(ds),recordings=len({r['recording'] for r in ds}),groups=len({r['group_id'] for r in ds}))
    assert not hashes['train']&hashes['val']
    # Check new hashes against existing frozen test hashes without opening test pixels.
    test_meta=read(ROOT/'DataSet/scene_baseline_test715/files-sha256.json')
    test_hashes=set(test_meta.values());assert not hashes['train']&test_hashes
    assert sha(DEST/'camera-val-coco.json')==sha(BASE/'camera-val-coco.json')
    assert sha(DEST/'camera-val-dataset.json')==sha(BASE/'camera-val-dataset.json')
    old=read(BASE/'camera-train-dataset.json');new=read(DEST/'camera-train-dataset.json')
    assert new[:len(old)]==old
    coverage=[];current=list(csv.DictReader((ROOT/'DataSet/scene_stratified_mortar_recovered_candidate/recordings.csv').open(encoding='utf-8-sig')))
    records={r['recording']:dict(recording=r['recording'],category=r['category'],role=r['role'],scene_id=r['scene_id'],group_id=r['group_id'],nominal={k:r[k] for k in ['placement','trajectory','z','tilt','roll']}) for r in current if r['role'] in ['train','val']}
    for r in proposed:records.setdefault(r['recording'],dict(recording=r['recording'],category=r['category'],role='train',scene_id=r['scene_id'],group_id=r['group_id'],nominal=r['nominal']))
    for v in records.values():v['added']=v['recording'] not in {r['recording'] for r in current};coverage.append(v)
    save(DEST/'recording-coverage.json',coverage)
    verification=dict(passed=True,status='camera_only_assistant_reviewed_trainval',counts=counts,added_images=900,added_recordings=9,original_train_preserved=True,val_annotations_byte_identical=True,all_images_hash_decode_verified=True,cross_train_val_hash_duplicates=0,new_train_vs_frozen_test_hash_duplicates=0,test_pixels_read=False,source_labels_modified=False,paired_distillation_ready=False,expert_verified=False,candidate_manifest_sha256=sha(OUT/'manifest.json'))
    save(DEST/'verification.json',verification)
    for p in DEST.glob('*.json'):files[p.name]=sha(p)
    save(DEST/'files-sha256.json',files)
    print(json.dumps(verification,ensure_ascii=True))

if __name__=='__main__':main()
