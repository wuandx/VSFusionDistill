import hashlib
import json
from pathlib import Path
import tarfile
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'DataSet/paired_assistant_truncated_review/export'
OUT=ROOT/'DataSet/workstation_baselines'
REMOTE='/root/wzl/dataset/paired_recording_trainval'
CLASSES=['100lbs_aircraft_bomb','incindiary_grenade','mortar_shell']
YOLO=['100lbs_aircraft_bomb','mortar_shell','incindiary_grenade']

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v): p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())

def main():
    OUT.mkdir(exist_ok=True)
    rows=json.loads((ROOT/'DataSet/paired_recording_split/manifest.json').read_text())
    rows=[x for x in rows if x['membership']=='selected' and x['role'] in ['train','val']]
    assert len(rows)==2400
    files={}; reports={}
    package=OUT/'workstation_baselines.tar'
    with tarfile.open(package,'w') as tar:
        for role,count in [('train',1800),('val',600)]:
            subset=sorted([x for x in rows if x['role']==role],key=lambda x:x['sample'])
            assert len(subset)==count
            for modality in ['camera','sonar']:
                ds=[]; coco=dict(info={},images=[],annotations=[],categories=[dict(id=i+1,name=n) for i,n in enumerate(CLASSES)])
                for i,x in enumerate(subset,1):
                    sample=x['sample']; rel=x[modality+'_image']; p=SOURCE/rel
                    assert sha(p)==x[modality+'_image_sha256']
                    img=cv2.imread(str(p)); assert img is not None
                    h,w=img.shape[:2]
                    if modality=='camera':
                        lp=SOURCE/'camera/original_labels'/f'{sample}.json'
                        a=json.loads(lp.read_text()); assert a['class']==x['category']
                        b=[a[k] for k in ['x_min','y_min','x_max','y_max']]
                        label_rel=f'camera/original_labels/{sample}.json'
                    else:
                        lp=SOURCE/'sonar/labels_yolo'/f'{sample}.txt'
                        fields=lp.read_text().split(); assert len(fields)==5
                        label_id=int(fields[0]); assert YOLO[label_id]==x['category']
                        cx,cy,bw,bh=map(float,fields[1:]); b=[round((cx-bw/2)*w,6),round((cy-bh/2)*h,6),round((cx+bw/2)*w,6),round((cy+bh/2)*h,6)]
                        label_rel=f'sonar/labels_yolo/{sample}.txt'
                    assert np.isfinite(b).all() and 0<=b[0]<b[2]<=w and 0<=b[1]<b[3]<=h,(sample,b,w,h)
                    bbox=[b[0],b[1],b[2]-b[0],b[3]-b[1]]; cat=CLASSES.index(x['category'])
                    for path,target in [(p,rel),(lp,label_rel)]:
                        arc='paired_recording_trainval/'+target
                        tar.add(path,arcname='dataset/'+arc)
                        files[arc]=sha(path)
                    coco['images'].append(dict(id=i,file_name=rel,width=w,height=h,sample=sample,recording=x['recording']))
                    coco['annotations'].append(dict(id=i,image_id=i,category_id=cat+1,bbox=bbox,area=bbox[2]*bbox[3],iscrowd=0))
                    ds.append(dict(sample_id=sample,fp_camera=f'{REMOTE}/{rel}' if modality=='camera' else None,fp_sonar=f'{REMOTE}/{rel}' if modality=='sonar' else None,
                                   **{f'coco_{modality}_image_id':i,f'boxes_{modality}':[bbox],f'labels_{modality}':[cat]},deg_level='d0',deg_seed=0,recording=x['recording'],width=w,height=h))
                for suffix,value in [('dataset',ds),('coco',coco)]:
                    p=OUT/f'{modality}-{role}-{suffix}.json';dump(p,value)
                    target='paired_recording_trainval/'+p.name
                    tar.add(p,arcname='dataset/'+target);files[target]=sha(p)
                reports[f'{modality}-{role}']=dict(images=len(ds),boxes=len(ds),image_hashes_match=True,all_decoded=True,native_bounds_valid=True)
        split=[dict(sample=x['sample'],recording=x['recording'],group_id=x['group_id'],category=x['category'],role=x['role']) for x in rows]
        p=OUT/'trainval-members.json';dump(p,split);tar.add(p,arcname='dataset/paired_recording_trainval/'+p.name);files['paired_recording_trainval/'+p.name]=sha(p)
        p=OUT/'files-sha256.json';dump(p,files);tar.add(p,arcname='dataset/paired_recording_trainval/'+p.name)
        repo=Path('/mnt/d/agent_workspace/水下/声呐目标检测/code/VSFusionDistill')
        source_hashes={}
        for folder in ['aodet','configs']:
            for p in (repo/folder).rglob('*.py'):
                rel=str(p.relative_to(repo));tar.add(p,arcname='workflow_baselines/source/'+rel);source_hashes[rel]=sha(p)
        p=OUT/'source-sha256.json';dump(p,source_hashes);tar.add(p,arcname='workflow_baselines/'+p.name)
        for name in ['camera_baseline_runtime.py','workstation_baseline_runtime.py','run_workstation_baseline.py','launch_workstation_baselines.sh']:
            tar.add(ROOT/'tools'/name,arcname='workflow_baselines/tools/'+name)
    dump(OUT/'verification.json',dict(passed=True,data=reports,file_count=len(files),test_uploaded=False,reserve_uploaded=False,package_sha256=sha(package),package_bytes=package.stat().st_size,sonar_bbox_source='delivered YOLO coordinates, native pixels reconstructed to 1e-6'))
    print(package,package.stat().st_size)

if __name__=='__main__':main()
