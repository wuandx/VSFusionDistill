"""Freeze only confirmed camera train/val, preserving paired sample identities."""
from expand_paired_recording_pool import *
import copy
import shutil
from datetime import datetime,timezone

SOURCE=ROOT/'DataSet/paired_weak_scene_coverage_pan_split'
DEST=ROOT/'DataSet/camera_weak_coverage_trainval'
RUN=ROOT/'runs/weak_coverage_camera_m_teacher'
COUNTS={'train':4138,'val':573}


def main():
    assert not DEST.exists() and not RUN.exists(),'Preserve named attempts'
    verification=read(SOURCE/'independent-verification.json');assert verification['passed']
    assert sha(SOURCE/'manifest.json')==verification['manifest_sha256']
    assert sha(SOURCE/'protocol.json')==verification['protocol_sha256']
    allrows=read(SOURCE/'manifest.json');rows=[x for x in allrows if x['role'] in COUNTS]
    assert len(rows)==4711
    byid={x['sample']:x for x in rows};rs=[r for r in read(SOURCE/'recordings.json') if r['role'] in COUNTS]
    recs={r['recording']:r for r in rs}
    groups={role:{r['group_id'] for r in rs if r['role']==role} for role in COUNTS}
    assert len(groups['train'])==27 and len(groups['val'])==5 and not groups['train']&groups['val']
    DEST.mkdir();RUN.mkdir()
    inputs={str(p):sha(p) for p in [SOURCE/'manifest.json',SOURCE/'recordings.json',SOURCE/'protocol.json',
        SOURCE/'independent-verification.json',ROOT/'experiment/archive/weak-coverage-camera-m-training-plan.md',
        ROOT/'assets/checkpoints/yolox_m_coco_backbone_neck.pth']}
    files={};members={};summary={};encoded=defaultdict(set);pixels=defaultdict(set)
    for role,count in COUNTS.items():
        ann=SOURCE/'camera'/f'coco_{role}.json';inputs[str(ann)]=sha(ann)
        coco=read(ann);assert coco['categories']==[dict(id=i+1,name=c) for i,c in enumerate(CLASSES)]
        assert len(coco['images'])==len(coco['annotations'])==count
        annotations=defaultdict(list)
        for a in coco['annotations']:annotations[a['image_id']].append(a)
        coco=copy.deepcopy(coco);dataset=[];identity=[]
        for im in coco['images']:
            x=byid[im['sample']];rec=recs[x['recording']]
            assert x['role']==role and rec['role']==role and x['category']==rec['category']
            src=(SOURCE/im['file_name']).resolve();assert src.is_relative_to(SOURCE.resolve())
            assert im['file_name']==x['camera_image']
            image=Image.open(src);image.load();assert image.size==(640,360) and image.mode=='RGB'
            digest=sha(src);assert digest==x['camera_image_sha256']
            encoded[digest].add(role);pixels[hashlib.sha256(image.tobytes()).hexdigest()].add(role)
            aa=annotations[im['id']];assert len(aa)==1;a=aa[0]
            b=a['bbox'];xyxy=[b[0],b[1],b[0]+b[2],b[1]+b[3]]
            assert xyxy==x['camera_boxes_xyxy'][0]
            assert 0<=xyxy[0]<xyxy[2]<=640 and 0<=xyxy[1]<xyxy[3]<=360
            assert list(CLASSES)[a['category_id']-1]==x['category']
            rel=Path('camera/images')/(x['sample']+'.jpg');target=DEST/rel;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(src,target);assert sha(target)==digest;files[rel.as_posix()]=digest
            label_field='camera_original_label' if 'camera_original_label' in x else 'camera_annotation'
            label=SOURCE/x[label_field];label_rel=Path('provenance_labels')/('original' if label_field=='camera_original_label' else 'assistant')/(x['sample']+'.json')
            (DEST/label_rel).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(label,DEST/label_rel)
            files[label_rel.as_posix()]=sha(label)
            origin='original_released_SD_label' if label_field=='camera_original_label' else 'assistant_new_visible_target_annotation'
            ident=dict(sample=x['sample'],recording=x['recording'],group_id=x['group_id'],
                category=x['category'],role=role,scene_id=x['scene_id'],camera_annotation_origin=origin,
                provenance_label=label_rel.as_posix(),image_sha256=digest)
            identity.append(ident)
            dataset.append(dict(sample_id=x['sample'],recording=x['recording'],group_id=x['group_id'],
                scene_id=x['scene_id'],role=role,width=640,height=360,fp_camera=rel.as_posix(),fp_sonar=None,
                boxes_camera=[b],labels_camera=[a['category_id']-1],boxes_sonar=[],labels_sonar=[],
                coco_camera_image_id=im['id'],deg_level='d0',deg_seed=0,source_image_sha256=digest,
                camera_annotation_origin=origin))
            im['file_name']=rel.as_posix();im.update(group_id=x['group_id'],scene_id=x['scene_id'])
        assert {x['sample'] for x in identity}=={x['sample'] for x in rows if x['role']==role}
        for suffix,value in [('dataset',dataset),('coco',coco)]:
            p=DEST/f'camera-{role}-{suffix}.json';save(p,value);files[p.name]=sha(p)
        members[role]=identity;summary['camera-'+role]=dict(images=count,boxes=count,
            original_labels=sum(x['camera_annotation_origin']=='original_released_SD_label' for x in identity),
            assistant_labels=sum(x['camera_annotation_origin']!='original_released_SD_label' for x in identity))
    assert all(len(v)==1 for v in encoded.values()) and all(len(v)==1 for v in pixels.values())
    save(DEST/'trainval-members.json',members);files['trainval-members.json']=sha(DEST/'trainval-members.json')
    save(DEST/'files-sha256.json',files)
    assert all(sha(k)==h for k,h in inputs.items())
    result=dict(passed=True,classes=list(CLASSES),counts=summary,
        source=str(SOURCE),input_sha256=inputs,trainval_images=4711,source_groups={k:len(v) for k,v in groups.items()},
        all_images_decoded=True,all_copy_hashes_match=True,all_boxes_match_source=True,
        source_groups_disjoint=True,cross_role_file_and_pixel_duplicates=0,
        only_camera_trainval=True,sonar_included=False,test_content_read=False,test_included=False,
        dataset_sha256=sha(DEST/'files-sha256.json'))
    save(DEST/'verification.json',result)
    confirmation=dict(registered_at=datetime.now(timezone.utc).isoformat(),
        user_instruction='确定好数据集就开始训练吧先只训练教师模型的相机，yoloxm',
        confirmed_source=str(SOURCE),source_manifest_sha256=sha(SOURCE/'manifest.json'),
        source_protocol_sha256=sha(SOURCE/'protocol.json'),camera_trainval=str(DEST),train=4138,val=573,
        train_recordings=33,val_recordings=5,train_groups=27,val_groups=5,
        dataset_sha256=result['dataset_sha256'],model='camera-only YOLOX-M',
        fresh_coco=True,epochs=200,batch=8,steps_per_epoch=518,total_updates=103600,
        augmentation=False,seed=0,training_authorized=True,sonar_training_authorized=False,test_evaluation_authorized=False,
        old_val_test_development_history=True,untouched_final_test=False)
    save(RUN/'dataset-freeze.json',confirmation)
    (DEST/'README.md').write_text('# 相机教师训练输入：4138train / 573val\n\n源自已确认paired_weak_scene_coverage_pan_split，保留配对身份，仅复制相机train/val。相机原标签与助手新标注血缘在provenance_labels和trainval-members.json中分别标明。test与sonar不在此包，类别沿用原项目顺序，COCO file_name相对此目录。冻结依据在runs/weak_coverage_camera_m_teacher/dataset-freeze.json。\n',encoding='utf-8')
    print(result,flush=True)


if __name__=='__main__':main()
