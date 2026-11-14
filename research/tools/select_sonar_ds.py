"""Vision chooses explicitly drawn image candidates; conversion stays deterministic."""
from annotate_sonar_ds import *
from prepare_sonar_visible_candidates import propose
from datetime import datetime,timezone
PROMPT_SELECT='''你是ARIS声呐目标框审核员。每张图含同一帧的无框视图和A/B/C/D/E候选（一些候选可能缺省）；图是raw图，只为显示改变横纵比例及亮度。不用读像素或换算坐标，只选择最合适的候选字母。规则：框覆盖可辨的UXO本体、可辨尾部及内部暗区，不包括分离支架、下方独立亮斑、声影、多径或大片背景；允许框内因矩形不可避免包含少量背景。贴边截断可以保留可见部分。看不清主体、多个物体无法区分或所有框都不好时选unresolved。不能按类别补出不可见形状。请以整条可见回波为准，不能仅框最亮局部。候选来自图像连通区域/修订，不是正确答案。无须偏好A或任何字母。返回严格JSON: {"items":[{"sample":"...","choice":"A/B/C/D/E/unresolved","confidence":"high/medium/low","reason":"简短中文"}]}。只有主体及框边界明确才选框，否则unresolved。不要输出坐标。'''
def options(r,decisions):
    a=arr(r['source']);h,w=a.shape
    opts={}
    b=r['proposal_xyxy']
    if b:opts['A']=b
    low,_=propose(a,r['overview_index'],8,2)
    weaker,_=propose(a,r['overview_index'],6,1.5)
    if low:opts['B']=low
    if weaker:opts['C']=weaker
    if b:opts['D']=[max(0,b[0]-3),max(0,b[1]-2),min(w,b[2]+3),min(h,b[3]+8)]
    d=decisions.get(r['sample'])
    if d and d['decision']!='unresolved':opts['E']=d['final_xyxy']
    return opts
def choice_panel(r,opts):
    a=arr(r['source']);h,w=a.shape
    # Six square full-image views. No crop hides possible target continuation.
    canvas=Image.new('RGB',(1200,860),'white');d=ImageDraw.Draw(canvas)
    d.text((5,4),r['sample']+' '+r['category'],fill='black')
    gain=np.clip(a.astype(float)*2.5,0,255).astype(np.uint8)
    base=Image.fromarray(gain).convert('RGB').resize((400,400))
    for k,key in enumerate(['RAW','A','B','C','D','E']):
        ox=(k%3)*400;oy=35+(k//3)*415
        canvas.paste(base,(ox,oy));d.text((ox+5,oy-15),key,fill='black')
        if key in opts:
            b=opts[key];d.rectangle((ox+b[0]*400/w,oy+b[1]*400/h,min(ox+399,ox+b[2]*400/w),min(oy+399,oy+b[3]*400/h)),outline='#00ff60',width=2)
        elif key!='RAW':d.text((ox+8,oy+5),'UNAVAILABLE',fill='red')
    return canvas
def choose(rows,key,model,base,dest,decisions):
    name=hashlib.sha256('|'.join(r['sample'] for r in rows).encode()).hexdigest()[:16]
    rp=dest/(name+'.response.json')
    if rp.exists():
        previous=read(rp)
        try:
            ch=previous['response']['choices'][0]
            parsed=json.loads(ch['message']['content'])
            assert ch.get('finish_reason')=='stop'
            assert {x['sample'] for x in parsed['items']}=={r['sample'] for r in rows}
            return previous
        except (KeyError,ValueError,AssertionError,TypeError):
            archive=dest/'invalid_responses';archive.mkdir(exist_ok=True)
            target=archive/(rp.stem+'_'+sha(rp)[:10]+'.json')
            if not target.exists():target.write_bytes(rp.read_bytes())
    content=[{'type':'text','text':PROMPT_SELECT+'\n以下为依次输入图像的精确sample标识，必须逐字使用，不能从图中OCR猜测：'+json.dumps([r['sample'] for r in rows])}];spec=[]
    for r in rows:
        opts=options(r,decisions);p=dest/(r['sample']+'.jpg');choice_panel(r,opts).save(p,quality=96)
        spec.append(dict(sample=r['sample'],options=opts,source_sha256=r['source_sha256'],image_sha256=sha(p),image_path=str(p)))
        content.append({'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(p.read_bytes()).decode()}})
    (dest/(name+'.request-info.json')).write_text(json.dumps(dict(model=model,base_url=base,prompt=PROMPT_SELECT,samples=spec),ensure_ascii=False,indent=2),'utf-8')
    payload=dict(model=model,messages=[{'role':'user','content':content}],temperature=0,max_tokens=16000,thinking={'type':'disabled'},reasoning_effort='low')
    req=urllib.request.Request(base+'/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    t=time.monotonic()
    try:
        with urllib.request.urlopen(req,timeout=240) as res:data=json.load(res)
        result=dict(elapsed_seconds=time.monotonic()-t,response=data,spec=spec)
        rp.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
        return result
    except Exception as e:
        error=str(e)
        if isinstance(e,urllib.error.HTTPError):error=e.read().decode(errors='replace')[:2000]
        result=dict(error=error,samples=[r['sample'] for r in rows]);(dest/(name+'.error.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8');return result
def main():
    p=argparse.ArgumentParser();p.add_argument('--model',default='deepseek-v4-pro');p.add_argument('--base',default='http://127.0.0.1:8788/v1');p.add_argument('--batch',action='store_true');p.add_argument('--workers',type=int,default=3);p.add_argument('--batch-size',type=int,default=5);args=p.parse_args()
    key=sys.stdin.readline().strip();assert key
    rows=read(OUT/'candidates/proposals.json');decisions=read(OUT/'review/decisions.json')
    if not args.batch:
        pick=[(2,0),(18,0),(34,0),(1,40),(0,43)]
        selected=[next(r for r in rows if r['overview_index']==idx and r['ordinal']==o) for idx,o in pick]
    else:selected=rows
    dest=OUT/(('ds_selection_batch_' if args.batch else 'ds_selection_pilot_')+args.model);dest.mkdir(exist_ok=True)
    chunks=[selected[i:i+args.batch_size] for i in range(0,len(selected),args.batch_size)]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        tasks={pool.submit(choose,chunk,key,args.model,args.base,dest,decisions):chunk for chunk in chunks}
        for future in as_completed(tasks):
            r=future.result()
            if 'response' in r:
                content=r['response']['choices'][0]['message']['content']
                print(json.dumps(dict(samples=[x['sample'] for x in r['spec']],seconds=round(r['elapsed_seconds'],1),content=content),ensure_ascii=True),flush=True)
            else:print(json.dumps(r,ensure_ascii=True),flush=True)
if __name__=='__main__':main()
