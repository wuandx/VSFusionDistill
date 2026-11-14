"""Local visual review sheets; explicit per-sample decisions are required to accept."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import json
import hashlib
import expand_paired_visible as e
e.BODY_MODE=True;e.ZOOM_MODE=True
ROOT=e.ROOT;OUT=ROOT/'DataSet/paired_local_review';CAM=e.CAM
CANDIDATES_PATH=ROOT/'DataSet/paired_visible_expansion/candidates.json'

def save(p,obj):e.save(p,obj)

def build(rec,start,count,proposal="E"):
    allrows=[r for r in e.read(CANDIDATES_PATH) if r['recording']==rec]
    assert len({r['sample'] for r in allrows})==len(allrows)
    # Primary 100 uniformly spaced over allowed full source span, remaining interleaved identities afterward.
    n=min(100,len(allrows))
    positions=[round(j*(len(allrows)-1)/(n-1)) for j in range(n)] if n>1 else list(range(n))
    order=positions+[j for j in range(len(allrows)) if j not in set(positions)]
    rows=[allrows[j] for j in order[start:start+count]]
    folder=OUT/rec;folder.mkdir(parents=True,exist_ok=True)
    for page in range(0,len(rows),12):
        selected=rows[page:page+12];canvas=e.Image.new('RGB',(1500,1840),'white');d=e.ImageDraw.Draw(canvas)
        specs=[]
        for j,r in enumerate(selected):
            a=e.arr(r['source']);h,w=a.shape;opts=e.body_options(r,a,shuffle=False)
            chosen=proposal if proposal in opts else None
            b=opts.get(chosen)
            ox=(j%3)*500;oy=(j//3)*460
            cam=e.Image.open(CAM/r['reference_sd']).convert('RGB');cd=e.ImageDraw.Draw(cam)
            for cb in r['camera_boxes_xyxy']:cd.rectangle(cb,outline='#00ff60',width=2)
            canvas.paste(cam.resize((400,225)),(ox,oy+28))
            full=e.Image.fromarray(e.np.clip(a.astype(float)*2.5,0,255).astype(e.np.uint8)).convert('RGB')
            canvas.paste(full.resize((140,200)),(ox,oy+256))
            if b:lo=max(0,b[1]-40);hi=min(h,b[3]+60)
            else:lo,hi=0,h
            zoom=full.crop((0,lo,w,hi)).resize((360,200));zd=e.ImageDraw.Draw(zoom)
            if b:zd.rectangle((b[0]*360/w,(b[1]-lo)*200/(hi-lo),min(359,b[2]*360/w),min(199,(b[3]-lo)*200/(hi-lo))),outline='#00ff60',width=2)
            canvas.paste(zoom,(ox+140,oy+256));d.text((ox+3,oy+3),f"{start+page+j} {r['sample']} {chosen} {b}",fill='black')
            d.text((ox+403,oy+40),'SD',fill='black');d.text((ox+403,oy+60),'640x360',fill='black')
            specs.append(dict(**r,review_ordinal=start+page+j,proposed_box=b,options=opts,
                              crop_y=[lo,hi],source_sha256=e.sha(r['source']),camera_sha256=e.sha(CAM/r['reference_sd']),
                              camera_label_sha256=e.sha(CAM/r['label_copy']),proposal_family=proposal))
        stem=f'page-{start+page:04d}';p=folder/(stem+'.jpg');assert not p.exists()
        canvas.save(p,quality=97);save(folder/(stem+'.json'),dict(sheet_sha256=e.sha(p),items=specs))
    print(json.dumps(dict(recording=rec,start=start,count=len(rows),pages=(len(rows)+11)//12)))

def decide(rec,page,accept,reason):
    folder=OUT/rec;p=folder/f'page-{page:04d}.json';spec=e.read(p)
    assert e.sha(p.with_suffix('.jpg'))==spec['sheet_sha256']
    ids=set(int(x) for x in accept.split(',')) if accept else set()
    assert ids <= {x['review_ordinal'] for x in spec['items']}
    path=OUT/'decisions.json';old=e.read(path) if path.exists() else {}
    events=OUT/'review-events.jsonl'
    with events.open('a',encoding='utf-8') as f:
        for r in spec['items']:
            accepted=r['review_ordinal'] in ids
            assert not accepted or r['proposed_box'] is not None
            d=dict(sample=r['sample'],recording=rec,category=r['category'],decision='accepted' if accepted else 'unresolved',
                bbox_xyxy=r['proposed_box'] if accepted else None,author='assistant',
                reviewed_at=datetime.now(timezone.utc).isoformat(),reason=reason,sheet=str(p.with_suffix('.jpg').relative_to(OUT)),
                sheet_sha256=spec['sheet_sha256'],source_sha256=r['source_sha256'],camera_sha256=r['camera_sha256'],
                camera_box_reviewed=True,cross_view_review='consistent_visible_target' if accepted else 'unresolved',
                precision_sync_certified=False,expert_verified=False)
            old[r['sample']]=d;f.write(json.dumps(d,ensure_ascii=False)+'\n')
    save(path,old)
    print(json.dumps(dict(reviewed=len(old),accepted=sum(x['decision']=='accepted' for x in old.values()))))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('recording');p.add_argument('--start',type=int,default=0);p.add_argument('--count',type=int,default=100);p.add_argument('--page',type=int);p.add_argument('--accept');p.add_argument('--reason');p.add_argument('--proposal',default='E');p.add_argument('--review-root');args=p.parse_args()
    if args.review_root:OUT=ROOT/'DataSet'/args.review_root
    if args.page is None:build(args.recording,args.start,args.count,args.proposal)
    else:decide(args.recording,args.page,args.accept or '',args.reason)
