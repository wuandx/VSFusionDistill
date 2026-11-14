import csv
import hashlib
from collections import Counter,defaultdict
import json
from pathlib import Path
import cv2
import numpy as np
from build_camera_two_recording_review import diagnose,iou
from build_camera_train_neighbor_review import tile,image,NAMES

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'DataSet/camera_train_self_review'
RUN=ROOT/'runs/camera_recording_baseline/train'
CLASSES=['100lbs_aircraft_bomb','incindiary_grenade','mortar_shell']

def main():
    OUT.mkdir(exist_ok=True)
    all_data={};stats={};checks=0
    for split in ['train','val']:
        gt=json.loads((ROOT/f'DataSet/camera_recording_baseline/{split}-coco.json').read_text())
        ds=json.loads((ROOT/f'DataSet/camera_recording_baseline/{split}-dataset.json').read_text())
        rowmap={x['sample_id']:x for x in ds}
        anns={a['image_id']:a for a in gt['annotations']};ims={i['sample']:i for i in gt['images']}
        preds=defaultdict(list)
        for p in json.loads((RUN/f'{split}_actual_raw_epoch200/predictions.json').read_text()):
            assert np.isfinite(p['bbox']).all() and np.isfinite(p['score'])
            assert 1<=p['category_id']<=3
            preds[p['image_id']].append(p)
        if split=='train':
            for im in gt['images']:
                row=rowmap[im['sample']];ann=anns[im['id']]
                p=ROOT/'DataSet/paired_assistant_truncated_review/export/camera/original_labels'/f"{im['sample']}.json"
                assert hashlib.sha256(p.read_bytes()).hexdigest()==row['label_sha256']
                label=json.loads(p.read_text())
                assert label['class']==CLASSES[ann['category_id']-1]==CLASSES[row['labels_camera'][0]]
                box=[label['x_min'],label['y_min'],label['x_max']-label['x_min'],label['y_max']-label['y_min']]
                assert box==ann['bbox']==row['boxes_camera'][0]
                assert row['coco_camera_image_id']==im['id'] and Path(row['fp_camera']).name==Path(im['file_name']).name
                checks+=1
        groupcounts={}
        details=[]
        for threshold in [.01,.25,.5]:
            scores=[diagnose(anns[im['id']],preds[im['id']],threshold) for im in gt['images']]
            groupcounts[str(threshold)]=dict(groups=dict(Counter(r['status'] for r in scores)),**{k:sum(r[k] for r in scores) for k in ['TP','FN','FP','predictions']})
            if threshold==.25:
                details=[dict(sample=im['sample'],recording=im['recording'],GT=NAMES[anns[im['id']]['category_id']],**r) for im,r in zip(gt['images'],scores)]
        with (OUT/f'{split}-errors.csv').open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=list(details[0]));writer.writeheader();writer.writerows(details)
        best=[max((iou(p['bbox'],anns[im['id']]['bbox']) for p in preds[im['id']] if p['category_id']==anns[im['id']]['category_id']),default=0) for im in gt['images']]
        stats[split]=dict(thresholds=groupcounts,best_same_class_iou_percentiles=dict(zip(['min','p10','median','p90'],map(float,np.percentile(best,[0,10,50,90])))))
        all_data[split]=(ims,anns,preds)
    queries=json.loads((ROOT/'DataSet/camera_train_neighbor_review/neighbors.json').read_text())
    ids=json.loads((ROOT/'DataSet/camera_train_neighbor_review/summary.json').read_text())['representatives']
    cards=[];neighbor_checks=[]
    for q in queries:
        for match in q['candidates']['SAME GT']:
            im=all_data['train'][0][match['sample']];ann=all_data['train'][1][im['id']]
            r=diagnose(ann,all_data['train'][2][im['id']],.25)
            neighbor_checks.append(dict(query=q['query'],neighbor=match['sample'],**r))
        if q['query'] not in ids:continue
        panels=[];labels=[]
        samples=[('val',q['query'])]+[('train',x['sample']) for x in q['candidates']['SAME GT']]
        for split,sample in samples:
            im=all_data[split][0][sample];ann=all_data[split][1][im['id']]
            r=diagnose(ann,all_data[split][2][im['id']],.25)
            top=max(all_data[split][2][im['id']],key=lambda p:p['score'])
            panels.append(tile(image(im),ann['bbox'],f'{split.upper()} GT={NAMES[ann["category_id"]]} P={NAMES[top["category_id"]]}',sample,(90,220,255) if split=='val' else (100,255,100),top))
            labels.append(f'{split}: top score={top["score"]:.3f}, same-class IoU={r["best_same_class_iou"]:.3f}')
        filename=q['query']+'.jpg';cv2.imwrite(str(OUT/filename),np.hstack(panels))
        cards.append(f'<figure><a href="{filename}"><img src="{filename}"></a><figcaption>{q["query"]} · '+ ' ｜ '.join(labels)+'</figcaption></figure>')
    page='''<!doctype html><meta charset="utf-8"><title>train/val真实预测对照</title><style>body{background:#181818;color:#eee;font:16px sans-serif;margin:20px}img{width:100%}figure{margin:20px 0}</style><h1>同一相机S raw权重：val错分与train近邻真实预测</h1><p>每行左侧val，右侧两张同类训练近邻；全部已叠加模型预测。绿色GT，红色最高分预测。所有推理为eval/no_grad，score展示0.25，AP另按0.01全排序。</p><p>train mAP=100%，val mAP=64.58%；训练自评不是泛化结果。HOG近邻不认证同一物理视角或因果。</p>'''+''.join(cards)
    (OUT/'index.html').write_text(page,encoding='utf-8')
    (OUT/'neighbor-predictions.json').write_text(json.dumps(neighbor_checks,indent=2)+'\n')
    stats.update(original_train_label_hash_and_mapping_checked=checks,neighbor_reference_count=len(neighbor_checks),same_class_neighbors_matched_at_025=sum(r['status']=='matched' for r in neighbor_checks),train_raw_weight=json.loads((RUN/'train_actual_raw_epoch200/weight-identity.json').read_text()),val_raw_weight=json.loads((RUN/'val_actual_raw_epoch200/weight-identity.json').read_text()))
    assert stats['train_raw_weight']['checkpoint_sha256']==stats['val_raw_weight']['checkpoint_sha256']
    (OUT/'summary.json').write_text(json.dumps(stats,indent=2)+'\n')
    print(json.dumps(stats,indent=2))

if __name__=='__main__':main()
