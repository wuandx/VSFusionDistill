"""Collect strict DS selections, prepare QA, and export an auditable annotation copy."""
from prepare_sonar_visible_candidates import *
from collections import Counter,defaultdict
import argparse,datetime,html
DS=OUT/'ds_selection_batch_deepseek-v4.1-flash'
def collect():
    proposals=read(OUT/'candidates/proposals.json');byid={r['sample']:r for r in proposals}
    decisions=read(OUT/'review/decisions.json');ds={};bad=[]
    for p in sorted(DS.glob('*.response.json')):
        try:
            v=read(p);ch=v['response']['choices'][0]
            assert v['response']['model']=='deepseek-v4.1-flash' and ch['finish_reason']=='stop'
            text=ch['message']['content'].strip()
            if text.startswith('```'):text=text.split('\n',1)[1].rsplit('```',1)[0].strip()
            items=json.loads(text)['items'];spec={r['sample']:r for r in v['spec']}
            assert len(items)==len(spec) and {x['sample'] for x in items}==set(spec)
            for x in items:
                assert x['choice'] in {*spec[x['sample']]['options'],'unresolved'}
                assert x['confidence'] in ('high','medium','low') and isinstance(x['reason'],str)
                assert x['sample'] in byid and x['sample'] not in ds
            for x in items:
                sid=x['sample'];ds[sid]=dict(**x,bbox_xyxy=spec[sid]['options'].get(x['choice']),response_file=str(p.relative_to(OUT)),response_sha256=sha(p))
        except (AssertionError,KeyError,ValueError,TypeError) as e:bad.append(dict(file=str(p.relative_to(OUT)),reason=type(e).__name__))
    rows=[]
    for r in proposals:
        sid=r['sample'];d=decisions.get(sid);m=ds.get(sid)
        o=dict(r,ds=m,assistant_review=d,bbox_xyxy=None,annotation_author=None,status='pending_ds')
        if d:
            if d['decision']=='unresolved':o.update(status='unresolved',reason=d['reason'])
            else:o.update(status='candidate',bbox_xyxy=d['final_xyxy'],annotation_author='assistant',reason=d['reason'])
        elif m:
            if m['choice']!='unresolved' and m['confidence']=='high':o.update(status='candidate',bbox_xyxy=m['bbox_xyxy'],annotation_author='deepseek-v4.1-flash',reason=m['reason'])
            else:o.update(status='unresolved',reason=m['reason'])
        rows.append(o)
    data=dict(items=rows,invalid_responses=bad,counts=dict(Counter(r['status'] for r in rows)),valid_ds_samples=len(ds),total_samples=len(rows))
    (OUT/'collected.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({k:v for k,v in data.items() if k not in ('items','invalid_responses')},ensure_ascii=True))
    return data
def iou(a,b):
    x0,y0=max(a[0],b[0]),max(a[1],b[1]);x1,y1=min(a[2],b[2]),min(a[3],b[3]);inter=max(0,x1-x0)*max(0,y1-y0)
    return inter/((a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter)
def qa(data):
    dest=OUT/'ds_qa';dest.mkdir(exist_ok=True);records=[]
    for idx in SELECTED:
        rr=[r for r in data['items'] if r['overview_index']==idx and r['status']=='candidate']
        if not rr:continue
        positions=np.linspace(0,len(rr)-1,min(5,len(rr))).round().astype(int).tolist()
        diffs=sorted(range(1,len(rr)),key=lambda i:iou(rr[i-1]['bbox_xyxy'],rr[i]['bbox_xyxy']))
        positions+= [i for i in diffs if i not in positions][:5]
        selected=[rr[i] for i in sorted(set(positions))]
        canvas=Image.new('RGB',(1600,960),'white')
        for k,r in enumerate(selected):
            canvas.paste(tile(r,box=r['bbox_xyxy'],size=(320,240),show_context=True),((k%5)*320,(k//5)*480))
            canvas.paste(tile(r,box=r['bbox_xyxy'],size=(320,240)),((k%5)*320,(k//5)*480+240))
        path=dest/f'r{idx:02d}.jpg';canvas.save(path,quality=96)
        records.append(dict(index=idx,recording=rr[0]['recording'],samples=[r['sample'] for r in selected],sheet_sha256=sha(path),candidate_count=len(rr)))
    (dest/'index.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),'utf-8')
    print('QA sheets',len(records))
def export(data):
    qa_results=read(OUT/'ds_qa/review.json');out=OUT/'export';out.mkdir(exist_ok=True)
    for directory in ['images','labels','previews']:(out/directory).mkdir(exist_ok=True)
    categories=['100lbs_aircraft_bomb','mortar_shell','incindiary_grenade']
    coco=dict(info=dict(description='Visible sonar annotations; assistant and DS Flash provenance retained; development only, no split assigned'),images=[],annotations=[],categories=[dict(id=i+1,name=c) for i,c in enumerate(categories)])
    accepted=[];exclusions=[];manifest=[]
    for r in data['items']:
        q=qa_results.get(str(r['overview_index']),{})
        if r['status']!='candidate' or q.get('decision')!='pass':
            exclusions.append(dict(sample=r['sample'],recording=r['recording'],status=r['status'],reason=r.get('reason','DS response missing/invalid') if r['status']!='candidate' else q.get('reason','recording QA not passed')));continue
        sid=r['sample'];a=arr(r['source']);h,w=a.shape;b=r['bbox_xyxy'];x0,y0,x1,y1=b
        assert sha(r['source'])==r['source_sha256'] and 0<=x0<x1<=w and 0<=y0<y1<=h
        ip=out/'images'/f'{sid}.png';Image.fromarray(a).save(ip)
        assert np.array_equal(np.array(Image.open(ip)),a)
        cls=categories.index(r['category']);bw=x1-x0;bh=y1-y0
        vals=[(x0+x1)/(2*w),(y0+y1)/(2*h),bw/w,bh/h]
        lp=out/'labels'/f'{sid}.txt';lp.write_text(str(cls)+' '+' '.join(f'{v:.10f}' for v in vals)+'\n','utf-8')
        # Side-by-side same raw with and without box; lossless source stays unaltered.
        gain=np.clip(a.astype(float)*2.5,0,255).astype(np.uint8)
        im=Image.fromarray(gain).convert('RGB').resize((384,h));preview=Image.new('RGB',(790,h+45),'white');preview.paste(im,(0,45));preview.paste(im,(406,45));d=ImageDraw.Draw(preview)
        d.text((4,3),sid+' '+r['annotation_author'],fill='black');d.text((4,20),'raw unchanged; display gain=2.5; x scale=3',fill='black');d.rectangle((406+x0*3,45+y0,min(789,406+x1*3),45+y1),outline='#00ff60',width=2)
        preview.save(out/'previews'/f'{sid}.jpg',quality=95)
        iid=len(accepted)+1
        coco['images'].append(dict(id=iid,file_name=f'images/{sid}.png',width=w,height=h,recording=r['recording']))
        coco['annotations'].append(dict(id=iid,image_id=iid,category_id=cls+1,bbox=[x0,y0,bw,bh],area=bw*bh,iscrowd=0,truncated=bool(x0==0 or x1==w or y0==0 or y1==h)))
        mr=dict(r,export_image=f'images/{sid}.png',export_image_sha256=sha(ip),yolo_file=f'labels/{sid}.txt',yolo_sha256=sha(lp),bbox_coordinates='unflipped native raw pixel-edge xyxy',truncated=bool(x0==0 or x1==w or y0==0 or y1==h),training_split=None,expert_verified=False,qa=q)
        manifest.append(mr);accepted.append(sid)
    (out/'annotations.coco.json').write_text(json.dumps(coco,ensure_ascii=False,indent=2),'utf-8')
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8')
    (out/'exclusions.json').write_text(json.dumps(exclusions,ensure_ascii=False,indent=2),'utf-8')
    (out/'classes.txt').write_text('\n'.join(categories)+'\n','utf-8')
    counts=Counter(r['recording'] for r in manifest)
    (out/'summary.json').write_text(json.dumps(dict(accepted=len(manifest),excluded=len(exclusions),by_recording=dict(counts),by_author=dict(Counter(r['annotation_author'] for r in manifest)),by_category=dict(Counter(r['category'] for r in manifest)),training_started=False,test_accessed=False),ensure_ascii=False,indent=2),'utf-8')
    cards=[]
    for r in manifest:cards.append('<article data-rec="'+r['recording']+'"><p>'+r['sample']+' · '+r['annotation_author']+'</p><a href="previews/'+r['sample']+'.jpg"><img loading="lazy" src="previews/'+r['sample']+'.jpg"></a></article>')
    page='''<!doctype html><meta charset="utf-8"><title>声呐标注副本</title><style>body{font:16px system-ui;margin:24px;background:#edf0f4}section{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:16px}article{background:white;padding:12px}img{width:100%;max-height:560px;object-fit:contain}select{font-size:18px;margin:16px}</style><h1>声呐可见目标标注</h1><p>未翻转raw图；左侧无框、右侧标注。显示增益2.5，导出PNG保持原像素。作者分为助手逐帧审阅与DS Flash，后者经录音抽查；不是专家GT。未分训练集。</p>'''+f'<p>已导出 {len(manifest)} 张；{len(counts)} 条录音。</p><select id="rec"><option value="">全部录音</option>'+''.join(f'<option>{r}</option>' for r in counts)+'</select><section>'+''.join(cards)+'''</section><script>document.getElementById('rec').onchange=e=>document.querySelectorAll('article').forEach(a=>a.hidden=!!e.target.value&&a.dataset.rec!==e.target.value)</script>'''
    (out/'index.html').write_text(page,'utf-8');print('exported',len(manifest))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--qa',action='store_true');p.add_argument('--export',action='store_true');a=p.parse_args();data=collect()
    if a.qa:qa(data)
    if a.export:export(data)
