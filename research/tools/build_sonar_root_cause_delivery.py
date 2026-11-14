"""Independent checks and comparison gallery for completed diagnostic controls."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import sys,json,html
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
import cv2
from PIL import Image,ImageDraw
from verify_box_guided_sonar_registration import independent_iou,read,sha
from check_official_sonar_coordinates import load_beam_tables
from fit_sonar_fixed_registration_refinement import prepare_model
CAUSE=ROOT/'DataSet/sonar_projection_root_cause';BASE=ROOT/'DataSet/sonar_box_guided_full_trajectory'

def project(points,T,ws,g,tables):
    world=(T[:3,:3]@points.T).T+T[:3,3];p=(world-ws[:3,3])@ws[:3,:3]
    ang=np.rad2deg(np.arctan2(-p[:,0],p[:,2]));dist=np.sqrt((p*p).sum(1));h,w=g['raw_shape_hw'];b=tables[w]
    xp=np.r_[np.column_stack([b[:,1],b[:,0]]).ravel(),b[-1,2]];fp=np.arange(len(xp))/2;u=np.interp(ang,xp,fp)
    for mask,i,j in [(ang<xp[0],0,1),(ang>xp[-1],-2,-1)]:u[mask]=fp[i]+(ang[mask]-xp[i])*(fp[j]-fp[i])/(xp[j]-xp[i])
    return np.column_stack([u,(dist-g['range_start_m'])/g['sample_bin_m']]),p

def main():
    out=CAUSE/'comparison';assert not out.exists();out.mkdir();(out/'frames').mkdir();(out/'qa').mkdir()
    rows=read(BASE/'results.json')['frames'];cur={r['sample']:r for r in read(CAUSE/'curve_control/results.json')['frames']};enc={r['sample']:r for r in read(CAUSE/'encoder_control/results.json')['frames']};env={r['sample']:r for r in read(CAUSE/'return_envelope_control/results.json')['frames']}
    assert set(cur)==set(enc)==set(env)=={r['sample'] for r in rows};assert len(rows)==505
    selected=set()
    for rec,role in sorted({(r['recording'],r['role']) for r in rows}):
        rr=sorted([r for r in rows if (r['recording'],r['role'])==(rec,role)],key=lambda r:r['sample'])
        selected.update(rr[i]['sample'] for i in {0,len(rr)//2,len(rr)-1})
    tables=load_beam_tables();registry=read(ROOT/'DataSet/sonar_fixed_mesh/fixed-mesh-transforms.json')['models'];points={};poses={};checks=[];max_iou=0.;count=0;records=[]
    for model in ['mortar_shell','incindiary']:
        points[model]=prepare_model(registry[model])[1];poses[model]={}
        for key,path in [('baseline',BASE),('curve',CAUSE/'curve_control')]:
            f=read(path/model/'freeze-model.json');T=np.array(f['chosen']['world_from_model']);poses[model][key]=T
            assert abs(np.linalg.det(T[:3,:3])-1)<1e-10;assert np.max(abs(T[:3,:3].T@T[:3,:3]-np.eye(3)))<1e-10
            assert f['chosen']['fit_cost']==min(c['fit_cost'] for c in f['candidates'])
            assert set(f.get('fit_samples',f.get('fit_sample_ids')))=={r['sample'] for r in rows if r['model']==model and r['role']=='fit'}
    for r in rows:
        sid=r['sample'];c=cur[sid];e=enc[sid];v=env[sid];ref=r['reference_bbox'];h,w=c['geometry']['raw_shape_hw']
        for q in [c,e,v]:assert q['reference_bbox']==ref and q['role']==r['role']
        preds={'baseline':r['predictions']['box_guided'],'curve':c['new'],'encoder':e['new'],'front':v['variants']['box_only_front']}
        for p in list(preds.values())+list(v['variants'].values()):
            value=independent_iou(p['bbox_xyxy'],ref);stored=p.get('iou',p.get('agreement',{}).get('iou'));max_iou=max(max_iou,abs(value-stored));count+=1
        contours={}
        if sid in selected:
            for key,ws in [('baseline',r['world_from_sonar']),('curve',c['world_from_sonar']),('encoder',e['world_from_sonar'])]:
                T=poses[r['model']]['curve' if key=='curve' else 'baseline'];uv,p=project(points[r['model']],T,np.array(ws),c['geometry'],tables)
                b=np.r_[uv.min(0),uv.max(0)];err=float(abs(b-np.array(preds[key]['unclipped_bbox'])).max());assert err<1e-8
                checks.append(dict(sample=sid,variant=key,max_edge_error_px=err));contours[key]=cv2.convexHull(uv.astype('float32')).reshape(-1,2).tolist()
                if key=='baseline':
                    # Independent direct masks rather than the production sorted-window implementation.
                    line=[]
                    for u in np.arange(.125,w,.25):
                        pp=uv[(abs(uv[:,0]-u)<=.75)&(p[:,2]>0)]
                        if len(pp)>=3:line.append([float(u),float(pp[:,1].min())])
                    line=np.array(line);stored=np.array(v['variants']['box_only_front']['curve']);assert line.shape==stored.shape and np.max(abs(line-stored))<1e-8
                    b=np.r_[line.min(0)-[2,5],line.max(0)+[2,5]];b=np.r_[np.maximum(b[:2],[0,0]),np.minimum(b[2:],[w,h])]
                    assert np.max(abs(b-v['variants']['box_only_front']['bbox_xyxy']))<1e-8
        for prov in r['provenance'].values():assert sha(prov['path'])==prov['sha256']
        raw=np.array(Image.open(r['provenance']['raw']['path']));camera=Image.open(r['provenance']['camera']['path']).convert('RGB');assert raw.shape==(h,w)
        bounds=[ref]+[p['bbox_xyxy'] for p in preds.values() if p['bbox_xyxy'] is not None];lo=max(0,int(min(b[1] for b in bounds))-20);hi=min(h,int(max(b[3] for b in bounds))+20)
        for gain in [1,2.5]:
            canvas=Image.new('RGB',(1600,510),'#f6f6f6');d=ImageDraw.Draw(canvas);canvas.paste(camera.resize((320,180)),(0,65));d.text((8,8),sid+' | '+r['role'],fill='black');d.text((8,260),'Raw gain '+str(gain)+'; range down',fill='black');d.text((8,280),'Green: assistant reference',fill='black');d.text((8,300),'Color: diagnostic projection',fill='black');d.text((8,320),'Hull is NOT acoustic silhouette',fill='black')
            base=Image.fromarray(np.minimum(raw.astype(float)*gain,255).astype('uint8')).convert('RGB').crop((0,lo,w,hi)).resize((320,420))
            for j,(key,pred) in enumerate(preds.items()):
                color={'baseline':'cyan','curve':'#ffae42','encoder':'#c180ff','front':'#ff7185'}[key];im=base.copy();dd=ImageDraw.Draw(im)
                def xy(p):return (p[0]*320/w,(p[1]-lo)*420/(hi-lo))
                for b,col in [(ref,'lime'),(pred['bbox_xyxy'],color)]:
                    if b is not None:dd.rectangle((*xy(b[:2]),*xy(b[2:])),outline=col,width=2)
                if key in contours:
                    poly=[xy(p) for p in contours[key]];dd.line(poly+[poly[0]],fill=color,width=1)
                if key=='front':dd.line([xy(p) for p in v['variants']['box_only_front']['curve']],fill=color,width=1)
                x=(j+1)*320;canvas.paste(im,(x,65));d.text((x+8,30),key+f' IoU {independent_iou(pred["bbox_xyxy"],ref):.3f}',fill='black')
            d.text((8,492),'Same crop and gain across variants. Fixed class model; no per-frame fitting. Development diagnostics, NOT approved GT.',fill='black')
            canvas.save(out/'frames'/f'{sid}-g{gain}.jpg',quality=90)
        records.append(dict(sample=sid,recording=r['recording'],role=r['role'],qa=sid in selected,ious={k:independent_iou(p['bbox_xyxy'],ref) for k,p in preds.items()}))
        if len(records)%100==0:print('rendered',len(records),flush=True)
    assert max_iou<1e-12
    summaries=[]
    for rec in sorted({r['recording'] for r in records}):
        rr=sorted([r for r in records if r['recording']==rec and r['role']!='fit'],key=lambda r:r['sample']);parts=[]
        for label,ids in zip(['early','middle','late'],np.array_split(np.arange(len(rr)),3)):
            part=[rr[i] for i in ids];parts.append(dict(segment=label,n=len(part),median_iou={k:float(np.median([r['ious'][k] for r in part])) for k in rr[0]['ious']}))
        summaries.append(dict(recording=rec,n=len(rr),median_iou={k:float(np.median([r['ious'][k] for r in rr])) for k in rr[0]['ious']},fraction_iou_ge_05={k:float(np.mean([r['ious'][k]>=.5 for r in rr])) for k in rr[0]['ious']},segments=parts))
        selected_rows=[r for r in records if r['recording']==rec and r['qa'] and r['role']!='fit'];sheet=Image.new('RGB',(1600,510*len(selected_rows)),'white')
        for i,r in enumerate(selected_rows):sheet.paste(Image.open(out/'frames'/f'{r["sample"]}-g1.jpg'),(0,i*510))
        sheet.save(out/'qa'/f'{rec}.jpg',quality=92)
    for r in records:
        for gain in [1,2.5]:
            with Image.open(out/'frames'/f'{r["sample"]}-g{gain}.jpg') as im:im.verify()
    def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),'utf-8')
    save(out/'manifest.json',records);save(out/'summary.json',summaries)
    save(CAUSE/'verification.json',dict(frames=len(rows),images_verified=len(rows)*2,iou_comparisons=count,max_iou_error=max_iou,independent_dense_projection_checks=checks,front_envelope_replays=len(selected),source_hashes_verified=True,rigid_matrices_and_fit_selection=True,browser_rendering_verified=False,physical_geometry_certified=False))
    page='''<!doctype html><meta charset="utf-8"><title>声呐投影原因核查</title><style>body{font:16px system-ui;margin:24px;background:#eee}img{width:100%;max-width:1600px}article{background:white;padding:12px;margin:16px 0}select,button{font:inherit;margin:6px}header{position:sticky;top:0;background:#fff;padding:8px}table{border-collapse:collapse}td,th{padding:8px;border:1px solid #bbb}</style><h1>声呐投影原因核查 · 505 帧</h1><p>绿色是既有助手框；四列依次为旧固定模型、增加曲线约束、编码器姿态控制、近表面框控制。它们均未通过物理注册认证。IoU 是与助手框的一致度。前中后抽查显示模型凸包，不是声学轮廓预测。</p><p><a href="../proposal_provenance/boundary-review-queue.json">标注边界复核队列</a> · <a href="../proposal_provenance/results.json">58 帧候选重放证据</a> · <a href="../verification.json">独立验证</a> · <a href="summary.json">分段统计</a></p><header><select id="rec"><option value="">全部录音</option></select><select id="mode"><option value="qa">固定首中尾抽查</option><option value="all">全部505帧</option><option value="worst">旧模型IoU最差优先</option></select><select id="gain"><option value="1">原始亮度 ×1</option><option value="2.5">显示增益 ×2.5</option></select><span id="count"></span></header><main id="list"></main><script>const data=DATA;for(const r of [...new Set(data.map(x=>x.recording))])rec.add(new Option(r,r));function render(){let a=data.filter(x=>(!rec.value||x.recording===rec.value)&&(mode.value!=='qa'||x.qa));if(mode.value==='worst')a.sort((a,b)=>a.ious.baseline-b.ious.baseline);count.textContent=a.length+' 帧';list.innerHTML=a.map(x=>`<article><b>${x.sample} · ${x.role}</b><img loading="lazy" src="frames/${x.sample}-g${gain.value}.jpg"></article>`).join('')}rec.onchange=mode.onchange=gain.onchange=render;render();</script>'''.replace('DATA',json.dumps(records))
    (out/'index.html').write_text(page,'utf-8')
    (CAUSE/'index.html').write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=comparison/index.html"><a href="comparison/index.html">打开505帧对照</a>','utf-8')
    print(json.dumps(dict(frames=len(rows),checks=len(checks),max_projection_error=max(x['max_edge_error_px'] for x in checks)),indent=2))

if __name__=='__main__':main()
