import csv
from collections import Counter,defaultdict
import html
import json
from pathlib import Path
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'DataSet/paired_assistant_truncated_review/export'
OUT=ROOT/'DataSet/camera_train_neighbor_review'
NAMES={1:'bomb',2:'grenade',3:'mortar'}

def hog(gray):
    gy,gx=np.gradient(gray.astype(np.float32))
    magnitude=np.sqrt(gx*gx+gy*gy)
    bins=(np.arctan2(gy,gx)*9/np.pi).astype(int)%9
    yy,xx=np.indices(gray.shape)
    ids=((yy//8)*12+xx//8)*9+bins
    cells=np.bincount(ids.ravel(),weights=magnitude.ravel(),minlength=12*12*9).reshape(12,12,9)
    blocks=[]
    for y in range(11):
        for x in range(11):
            b=cells[y:y+2,x:x+2].ravel();b=b/np.sqrt(np.dot(b,b)+1e-6)
            b=np.minimum(b,.2);blocks.append(b/np.sqrt(np.dot(b,b)+1e-6))
    return np.concatenate(blocks).astype(np.float32)

def image(im):
    x=cv2.imread(str(SOURCE/im['file_name']));assert x is not None;return x

def crop(im,box):
    x,y,w,h=box
    return im[max(0,int(np.floor(y))):min(im.shape[0],int(np.ceil(y+h))),max(0,int(np.floor(x))):min(im.shape[1],int(np.ceil(x+w)))]

def letterbox(im,w,h):
    scale=min(w/im.shape[1],h/im.shape[0]); nw,nh=max(1,round(im.shape[1]*scale)),max(1,round(im.shape[0]*scale))
    canvas=np.full((h,w,3),114,np.uint8);xx,yy=(w-nw)//2,(h-nh)//2
    canvas[yy:yy+nh,xx:xx+nw]=cv2.resize(im,(nw,nh));return canvas

def feature(im,box):
    f=hog(cv2.cvtColor(letterbox(crop(im,box),96,96),cv2.COLOR_BGR2GRAY))
    return f/max(1e-9,np.linalg.norm(f)),np.log(box[2]/box[3])

def tile(im,box,title,subtitle,color,pred=None):
    full=im.copy();x,y,w,h=box
    cv2.rectangle(full,(int(x),int(y)),(int(x+w),int(y+h)),(0,255,0),2)
    if pred:
        a,b,c,d=pred['bbox'];cv2.rectangle(full,(int(a),int(b)),(int(a+c),int(b+d)),(0,0,255),2)
    canvas=np.full((460,320,3),25,np.uint8)
    cv2.putText(canvas,title,(6,20),cv2.FONT_HERSHEY_SIMPLEX,.5,color,1)
    cv2.putText(canvas,subtitle,(6,40),cv2.FONT_HERSHEY_SIMPLEX,.38,(235,235,235),1)
    canvas[52:232]=cv2.resize(full,(320,180))
    canvas[240:450,55:265]=letterbox(crop(im,box),210,210)
    return canvas

def main():
    cv2.setNumThreads(2)
    OUT.mkdir(exist_ok=True)
    train=json.loads((ROOT/'DataSet/camera_recording_baseline/train-coco.json').read_text())
    val=json.loads((ROOT/'DataSet/camera_recording_baseline/val-coco.json').read_text())
    ta={a['image_id']:a for a in train['annotations']};va={a['image_id']:a for a in val['annotations']}
    vt={i['sample']:i for i in val['images']}
    rows=list(csv.DictReader((ROOT/'DataSet/camera_s_two_recording_review/errors.csv').open(encoding='utf-8-sig')))
    queries=[r for r in rows if r['status']=='wrong_class']
    predictions=defaultdict(list)
    for p in json.loads((ROOT/'runs/camera_recording_baseline/train/val_actual_raw_epoch200/predictions.json').read_text()):predictions[p['image_id']].append(p)
    features=[];ratios=[];thumbnails=[]
    for im in train['images']:
        pixels=image(im);f,r=feature(pixels,ta[im['id']]['bbox']);features.append(f);ratios.append(r)
        thumbnails.append((im,pixels))
    matrix=np.asarray(features);ratios=np.asarray(ratios)
    output=[];all_scores=[]
    for query in queries:
        im=vt[query['sample']];a=va[im['id']];pixels=image(im);f,r=feature(pixels,a['bbox'])
        score=matrix@f-.15*np.abs(ratios-r)
        top=max((p for p in predictions[im['id']] if p['score']>=.25),key=lambda p:p['score'])
        assert top['category_id']!=a['category_id']
        candidates={};tiles=[tile(pixels,a['bbox'],f"VAL GT {NAMES[a['category_id']]} -> {NAMES[top['category_id']]}",im['sample'],(90,200,255),top)]
        for category,title in [(a['category_id'],'SAME GT'),(top['category_id'],'PRED CLASS')]:
            chosen=[];seen=set()
            for j in np.argsort(-score):
                sample,_=thumbnails[int(j)]
                if ta[sample['id']]['category_id']!=category or sample['recording'] in seen:continue
                seen.add(sample['recording']);chosen.append(int(j))
                if len(chosen)==2:break
            candidates[title]=[]
            for j in chosen:
                t,p=thumbnails[j];ann=ta[t['id']]
                candidates[title].append(dict(sample=t['sample'],recording=t['recording'],category=NAMES[category],score=float(score[j]),bbox=ann['bbox']))
                tiles.append(tile(p,ann['bbox'],f'TRAIN {title} {NAMES[category]}',t['sample']+f' s={score[j]:.3f}',(100,255,100) if title=='SAME GT' else (100,180,255)))
        filename=im['sample']+'.jpg';cv2.imwrite(str(OUT/filename),np.hstack(tiles))
        output.append(dict(query=query['sample'],recording=query['recording'],GT=NAMES[a['category_id']],predicted=NAMES[top['category_id']],confidence=top['score'],candidates=candidates,image=filename))
        all_scores.append(score)
    np.savez_compressed(OUT/'retrieval-scores.npz',scores=np.array(all_scores),train_samples=np.array([x['sample'] for x in train['images']]),query_samples=np.array([q['query'] for q in output]))
    (OUT/'neighbors.json').write_text(json.dumps(output,indent=2)+'\n')
    # Representative rows: two equal-time samples per observed confusion, not picked by retrieval score.
    representative=[]
    for rec in sorted({q['recording'] for q in output}):
        for cls in sorted({q['predicted'] for q in output if q['recording']==rec}):
            group=[q for q in output if q['recording']==rec and q['predicted']==cls]
            for j in np.linspace(0,len(group)-1,2).round().astype(int):
                q=group[j];representative.append(q)
                cv2.imwrite(str(OUT/(q['query']+'-compact.jpg')),cv2.resize(cv2.imread(str(OUT/q['image'])),(1280,368)))
    for rec in sorted({q['recording'] for q in output}):
        selected=[q for q in representative if q['recording']==rec]
        cv2.imwrite(str(OUT/(rec+'-overview.jpg')),np.vstack([cv2.imread(str(OUT/(q['query']+'-compact.jpg'))) for q in selected]))
    cards=''.join(f'<figure data-rec="{q["recording"]}"><a href="{q["image"]}"><img loading="lazy" src="{q["image"]}"></a><figcaption>{q["query"]}: {q["GT"]} → {q["predicted"]}</figcaption></figure>' for q in output)
    page='''<!doctype html><meta charset="utf-8"><title>错分帧与训练近邻</title><style>body{font:16px sans-serif;background:#181818;color:#eee;margin:20px}img{width:100%}figure{margin:20px 0}[hidden]{display:none}</style><h1>错分val帧与训练样本并排</h1><p>每行：错分val图 ｜ 同GT类别训练近邻×2 ｜ 预测类别训练近邻×2。每格上为原图上下文，下为GT目标裁剪。绿框GT，红框query预测。训练近邻来自不同录音。</p><p>以保长宽比GT目标HOG外观相似度检索，不认证物理姿态或错误原因；所有检索只用1800 train，查询88个既有错类val帧。不改训练/标签/AP，不读test。</p><select onchange="document.querySelectorAll('figure').forEach(e=>e.hidden=this.value!=='all'&&e.dataset.rec!==this.value)"><option value="all">全部88帧</option value="2023-09-20_182317">182317</option><option value="2023-09-21_121539">121539</option></select>'''+cards
    (OUT/'index.html').write_text(page,encoding='utf-8')
    summary=dict(train_images=1800,queries=len(output),counts=dict(Counter(q['recording'] for q in output)),representatives=[q['query'] for q in representative],method='GT crop aspect-preserved HOG cosine - 0.15 log-aspect-distance; distinct recording top2 per class',no_training=True,test_used=False)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))

if __name__=='__main__':main()
