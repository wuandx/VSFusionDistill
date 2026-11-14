"""Freeze only sonar train/val from the same paired split as the camera teacher."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
from collections import defaultdict,Counter
from datetime import datetime,timezone
from PIL import Image
from prepare_scene_baselines import sha,dump,CLASSES

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'DataSet/paired_weak_scene_coverage_pan_split'
DEST=ROOT/'DataSet/sonar_weak_coverage_trainval'
RUN=ROOT/'runs/weak_coverage_sonar_s_student'
COUNTS={'train':4138,'val':573}
CKPT=ROOT/'assets/checkpoints/yolox_s_coco.pth'
CKPT_SHA='4592a793b95f18f62fd73fbb6cfe61dd445f71a8e072366e114e7134d4492760'

def main():
    assert not DEST.exists() and not RUN.exists(),'Preserve named attempts'
    sourceproof=json.loads((SOURCE/'independent-verification.json').read_text(encoding='utf-8'))
    assert sourceproof['passed']
    teacher=json.loads((ROOT/'runs/weak_coverage_camera_m_teacher/dataset-freeze.json').read_text(encoding='utf-8'))
    assert sha(SOURCE/'manifest.json')==sourceproof['manifest_sha256']==teacher['source_manifest_sha256']
    assert sha(SOURCE/'protocol.json')==sourceproof['protocol_sha256']==teacher['source_protocol_sha256']
    cached=Path('/home/ty/.cache/torch/hub/checkpoints/yolox_s_8x8_300e_coco_20211121_095711-4592a793.pth')
    assert sha(cached)==CKPT_SHA
    if CKPT.exists():assert sha(CKPT)==CKPT_SHA
    else:shutil.copyfile(cached,CKPT)
    allrows=json.loads((SOURCE/'manifest.json').read_text(encoding='utf-8'))
    rows=[r for r in allrows if r['role'] in COUNTS];assert len(rows)==4711
    byid={r['sample']:r for r in rows};assert len(byid)==4711
    camera_members=json.loads((ROOT/'DataSet/camera_weak_coverage_trainval/trainval-members.json').read_text(encoding='utf-8'))
    inputs={str(p):sha(p) for p in [SOURCE/'manifest.json',SOURCE/'protocol.json',SOURCE/'recordings.json',SOURCE/'independent-verification.json',
        ROOT/'experiment/archive/weak-coverage-sonar-s-student-training-plan.md',ROOT/'DataSet/camera_weak_coverage_trainval/trainval-members.json',CKPT]}
    DEST.mkdir();RUN.mkdir()
    files={};members={};summary={};enc=defaultdict(set);pixels=defaultdict(set)
    for role,count in COUNTS.items():
        ann=SOURCE/'sonar'/f'coco_{role}.json';inputs[str(ann)]=sha(ann)
        coco=copy.deepcopy(json.loads(ann.read_text(encoding='utf-8')))
        assert coco['categories']==[dict(id=i+1,name=n) for i,n in enumerate(CLASSES)]
        assert len(coco['images'])==len(coco['annotations'])==count
        annotations=defaultdict(list)
        for a in coco['annotations']:annotations[a['image_id']].append(a)
        ds=[];identity=[];shapes=Counter()
        for im in coco['images']:
            r=byid[im['sample']];assert r['role']==role and im['file_name']==r['sonar_image']
            src=(SOURCE/im['file_name']).resolve();assert src.is_relative_to(SOURCE.resolve())
            image=Image.open(src);image.load();w,h=image.size
            assert [w,h]==r['sonar_size_wh']==[im['width'],im['height']]
            digest=sha(src);assert digest==r['sonar_image_sha256']
            enc[digest].add(role);pixels[hashlib.sha256(image.tobytes()).hexdigest()].add(role)
            aa=annotations[im['id']];assert len(aa)==1;a=aa[0];b=a['bbox']
            assert [b[0],b[1],b[0]+b[2],b[1]+b[3]]==r['sonar_bbox_xyxy']
            assert 0<=b[0]<b[0]+b[2]<=w and 0<=b[1]<b[1]+b[3]<=h
            assert CLASSES[a['category_id']-1]==r['category']
            label=SOURCE/'sonar/labels_yolo'/(r['sample']+'.txt')
            fields=label.read_text().split();assert len(fields)==5 and int(fields[0])+1==a['category_id']
            cx,cy,bw,bh=map(float,fields[1:]);recovered=[(cx-bw/2)*w,(cy-bh/2)*h,bw*w,bh*h]
            assert max(abs(v-z) for v,z in zip(recovered,b))<1e-6
            rel=Path('sonar/images')/(r['sample']+'.png');target=DEST/rel
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,target)
            assert sha(target)==digest;files[rel.as_posix()]=digest
            label_rel=Path('sonar/labels_yolo')/label.name;(DEST/label_rel).parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(label,DEST/label_rel);files[label_rel.as_posix()]=sha(label)
            provenance=Path('provenance_labels')/(r['sample']+'.json');(DEST/provenance).parent.mkdir(exist_ok=True)
            dump(DEST/provenance,dict(sample=r['sample'],annotation_origin='assistant_reviewed_visible_sonar_echo_box',
                review=r.get('review'),sonar_bbox_xyxy=r['sonar_bbox_xyxy'],source_manifest_sha256=teacher['source_manifest_sha256'],
                expert_verified=False,precision_sync_certified=False))
            files[provenance.as_posix()]=sha(DEST/provenance)
            identity.append(dict(sample=r['sample'],recording=r['recording'],group_id=r['group_id'],category=r['category'],
                role=role,scene_id=r['scene_id'],image_sha256=digest,provenance_label=provenance.as_posix(),label_yolo=label_rel.as_posix()))
            ds.append(dict(sample_id=r['sample'],recording=r['recording'],group_id=r['group_id'],scene_id=r['scene_id'],role=role,
                width=w,height=h,fp_sonar=rel.as_posix(),fp_camera=None,boxes_sonar=[b],labels_sonar=[a['category_id']-1],
                boxes_camera=[],labels_camera=[],coco_sonar_image_id=im['id'],deg_level='d0',deg_seed=0,source_image_sha256=digest))
            im['file_name']=rel.as_posix();im.update(group_id=r['group_id'],scene_id=r['scene_id']);shapes[f'{w}x{h}']+=1
        expected={(m['sample'],m['recording'],m['group_id'],m['category'],m['role']) for m in camera_members[role]}
        assert {(m['sample'],m['recording'],m['group_id'],m['category'],m['role']) for m in identity}==expected
        for suffix,value in [('dataset',ds),('coco',coco)]:
            path=DEST/f'sonar-{role}-{suffix}.json';dump(path,value);files[path.name]=sha(path)
        members[role]=identity;summary[role]=dict(images=count,boxes=count,shapes=dict(shapes),
            recordings=len({x['recording'] for x in identity}),groups=len({x['group_id'] for x in identity}))
    for field in ['sample','recording','group_id']:
        assert not ({m[field] for m in members['train']}&{m[field] for m in members['val']})
    assert all(len(v)==1 for v in enc.values()) and all(len(v)==1 for v in pixels.values())
    dump(DEST/'trainval-members.json',members);files['trainval-members.json']=sha(DEST/'trainval-members.json')
    dump(DEST/'files-sha256.json',files)
    assert all(sha(p)==h for p,h in inputs.items())
    proof=dict(passed=True,classes=CLASSES,counts=summary,trainval_images=4711,source=str(SOURCE),input_sha256=inputs,
        all_images_decoded=True,all_copy_hashes_match=True,all_boxes_match_source=True,yolo_coco_roundtrip=True,
        teacher_sample_roles_groups_match=True,source_groups_disjoint=True,cross_role_file_and_pixel_duplicates=0,
        only_sonar_trainval=True,camera_included=False,test_content_read=False,test_included=False,dataset_sha256=sha(DEST/'files-sha256.json'))
    dump(DEST/'verification.json',proof)
    dump(RUN/'dataset-freeze.json',dict(registered_at=datetime.now(timezone.utc).isoformat(),user_instruction='我本地再跑一个吧，跑一个单声呐的学生模型',
        confirmed_source=str(SOURCE),source_manifest_sha256=teacher['source_manifest_sha256'],source_protocol_sha256=teacher['source_protocol_sha256'],
        dataset_sha256=proof['dataset_sha256'],initialization_sha256=CKPT_SHA,model='sonar-only YOLOX-S student baseline',
        train=4138,val=573,train_recordings=33,val_recordings=5,train_groups=27,val_groups=5,
        fresh_coco=True,epochs=200,batch=8,seed=0,augmentation=False,steps_per_epoch=518,total_updates=103600,
        sonar_training_authorized=True,distillation=False,test_evaluation_authorized=False,old_val_test_development_history=True,untouched_final_test=False))
    (DEST/'README.md').write_text('# 单声呐学生输入：4138train / 573val\n\n与相机教师共用paired_weak_scene_coverage_pan_split身份与角色；声呐原PNG、可见回波框及助手审核血缘保持。仅声呐train/val，无相机或test图。YOLO/COCO类别bomb/mortar/grenade；不等于专家GT、投影框或精密同步认证。\n',encoding='utf-8')
    print(json.dumps(proof,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
