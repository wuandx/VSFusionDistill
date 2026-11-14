import csv
import html
import json
from collections import Counter,defaultdict
from pathlib import Path
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'DataSet/camera_s_test_bomb_review'
EXPORT=ROOT/'DataSet/paired_assistant_truncated_review/export'
RUN=ROOT/'runs/camera_recording_baseline/train/test_actual_raw_epoch200'
NAMES={1:'bomb',2:'grenade',3:'mortar'}

def iou(a,b):
    x,y,w,h=a;u,v,s,t=b
    inter=max(0,min(x+w,u+s)-max(x,u))*max(0,min(y+h,v+t)-max(y,v))
    return inter/(w*h+s*t-inter) if w*h+s*t-inter>0 else 0.

def diagnose(gt,preds,thr):
    ps=[p for p in preds if p['score']>=thr]
    correct=[p for p in ps if p['category_id']==gt['category_id']]
    valid=[p for p in correct if iou(p['bbox'],gt['bbox'])>=.5]
    wrong=[p for p in ps if p['category_id']!=gt['category_id'] and iou(p['bbox'],gt['bbox'])>=.5]
    best=max((iou(p['bbox'],gt['bbox']) for p in correct),default=0.)
    status='matched' if valid else 'wrong_class' if wrong else 'localization' if best>=.1 else 'unmatched'
    top=max(ps,key=lambda p:p['score']) if ps else None
    return dict(status=status,TP=int(bool(valid)),FN=int(not valid),FP=len(ps)-int(bool(valid)),predictions=len(ps),best_same_class_iou=best,
                top_class=NAMES[top['category_id']] if top else 'none',top_score=top['score'] if top else 0.,top_iou=iou(top['bbox'],gt['bbox']) if top else 0.)

def draw(img,bbox,color,label):
    x,y,w,h=bbox
    a,b=(int(round(x)),int(round(y))),(int(round(x+w)),int(round(y+h)))
    cv2.rectangle(img,a,b,color,2)
    ytext=max(13,min(355,a[1]-5))
    cv2.putText(img,label,(max(0,min(500,a[0])),ytext),cv2.FONT_HERSHEY_SIMPLEX,.42,color,1,cv2.LINE_AA)

def main():
    OUT.mkdir(exist_ok=True)
    gt=json.loads((ROOT/'DataSet/camera_recording_baseline/test-coco.json').read_text())
    metrics=json.loads((RUN/'metrics.json').read_text())
    anns={a['image_id']:a for a in gt['annotations']}
    preds=defaultdict(list)
    for p in json.loads((RUN/'predictions.json').read_text()):preds[p['image_id']].append(p)
    report={}; csvrows=[]
    for rec in ['2023-09-20_175506','2023-09-21_160551']:
        target=OUT/rec;target.mkdir(exist_ok=True)
        images=sorted([i for i in gt['images'] if i['recording']==rec],key=lambda i:i['sample'])
        assert len(images)==100
        counts={};cards=[];rendered=[]
        for threshold in [.01,.25,.5]:
            rows=[diagnose(anns[i['id']],preds[i['id']],threshold) for i in images]
            counts[str(threshold)]=dict(groups=dict(Counter(r['status'] for r in rows)),**{k:sum(r[k] for r in rows) for k in ['TP','FN','FP','predictions']})
        for im in images:
            a=anns[im['id']];ps=preds[im['id']];info=diagnose(a,ps,.25)
            csvrows.append(dict(recording=rec,sample=im['sample'],GT=NAMES[a['category_id']],**info))
            frame=cv2.imread(str(EXPORT/im['file_name']));assert frame is not None
            draw(frame,a['bbox'],(0,255,0),'GT '+NAMES[a['category_id']])
            for p in sorted(ps,key=lambda p:p['score']):
                if p['score']>=.25:draw(frame,p['bbox'],(0,0,255),f"{NAMES[p['category_id']]} {p['score']:.2f}")
            panel=cv2.copyMakeBorder(frame,52,0,0,0,cv2.BORDER_CONSTANT,value=(28,28,28))
            cv2.putText(panel,im['sample']+' | '+info['status'],(6,20),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1)
            cv2.putText(panel,f"Green GT | Red prediction >=0.25 | best same-class IoU {info['best_same_class_iou']:.2f}",(6,40),cv2.FONT_HERSHEY_SIMPLEX,.42,(255,255,255),1)
            filename=im['sample']+'.jpg';cv2.imwrite(str(target/filename),panel);rendered.append(panel)
            cards.append(f'<figure data-status="{info["status"]}"><a href="{filename}"><img loading="lazy" src="{filename}"></a><figcaption>{html.escape(im["sample"])} · {info["status"]} · same-class IoU={info["best_same_class_iou"]:.3f}</figcaption></figure>')
        indices=np.linspace(0,99,12).round().astype(int).tolist()
        tiles=[cv2.resize(rendered[j],(480,309)) for j in indices]
        cv2.imwrite(str(target/'overview.jpg'),np.vstack([np.hstack(tiles[j:j+3]) for j in range(0,12,3)]))
        controls='<select onchange="document.querySelectorAll(\'figure\').forEach(e=>e.hidden=this.value!==\'all\'&&e.dataset.status!==this.value)"><option value="all">全部帧</option><option value="matched">匹配</option><option value="wrong_class">错分类</option><option value="localization">定位不足</option><option value="unmatched">未匹配</option></select>'
        page=f'<!doctype html><meta charset="utf-8"><title>{rec}预测复核</title><style>body{{font:16px sans-serif;background:#181818;color:#eee;margin:20px}} main{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}figure{{margin:0}}img{{width:100%}}[hidden]{{display:none}}</style><h1>{rec}</h1><p>camera YOLOX-S · 640×384 · epoch200 actual raw · test100帧。绿框GT；红框预测(score≥0.25)。点击查看原尺寸；AP使用原score≥0.01，不随筛选改变。</p><p>0.25筛查统计：{html.escape(json.dumps(counts["0.25"],ensure_ascii=False))}</p>{controls}<main>'+''.join(cards)+'</main>'
        (target/'index.html').write_text(page,encoding='utf-8')
        report[rec]=dict(images=100,thresholds=counts,COCO_metrics=metrics['per_recording'][rec]['metrics'],overview_indices=indices)
    with (OUT/'errors.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(csvrows[0]));writer.writeheader();writer.writerows(csvrows)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><h1>相机S两条test炸弹录音预测复核</h1><p>epoch200 actual raw；GT绿框，预测红框。各100帧，含全部结果。</p>'+''.join(f'<p><a href="{r}/index.html">{r}：全部100帧</a> · <a href="{r}/overview.jpg">12帧概览</a></p>' for r in report),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
