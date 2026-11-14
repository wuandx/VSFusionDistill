"""Render all proposals with fixed per-recording context, track explicit review decisions."""
from prepare_sonar_visible_candidates import *
import argparse
from datetime import datetime, timezone
def archive_sheet(path):
    dest=OUT/'review/sheets';dest.mkdir(exist_ok=True)
    target=dest/(sha(path)+'.jpg')
    if not target.exists():target.write_bytes(Path(path).read_bytes())
def record_review(idx,pages,reason,corrections=None,reject=None,expand=None):
    """Called only with explicit assistant observations after viewing each listed sheet."""
    rows=read(OUT/'candidates/proposals.json');dest=OUT/'review';dest.mkdir(exist_ok=True)
    path=dest/'decisions.json'; decisions=read(path) if path.exists() else {}
    corrections=corrections or {};reject=reject or {}
    events=[]
    for r in rows:
        if r['overview_index']!=idx or r['ordinal']//20 not in pages:continue
        o=r['ordinal'];b=r['proposal_xyxy'];final=list(b) if b else None
        if expand and final:
            final=[max(0,final[0]-expand[0]),max(0,final[1]-expand[1]),min(r['shape_hw'][1],final[2]+expand[2]),min(r['shape_hw'][0],final[3]+expand[3])]
        final=corrections.get(o,final)
        d=dict(sample=r['sample'],author='assistant',reviewed_at=datetime.now(timezone.utc).isoformat(),decision='revised' if final!=b else 'retained',final_xyxy=final,reason=reason,review_sheet=f'r{idx:02d}_p{o//20}.jpg',review_sheet_sha256=sha(dest/f'r{idx:02d}_p{o//20}.jpg'),display_gain=2.5,original_xyxy=b)
        archive_sheet(dest/f'r{idx:02d}_p{o//20}.jpg')
        if o in reject:d.update(decision='unresolved',final_xyxy=None,reason=reject[o])
        if final is None and o not in reject:raise ValueError('Null box cannot be accepted')
        decisions[r['sample']]=d;events.append(d)
    with (dest/'review-events.jsonl').open('a',encoding='utf-8') as f:
        for e in events:f.write(json.dumps(e,ensure_ascii=False)+'\n')
    path.write_text(json.dumps(decisions,ensure_ascii=False,indent=2),'utf-8')
    print('reviewed',idx,pages,len(events))
def render(indices,original=False):
    rows=read(OUT/'candidates/proposals.json')
    dest=OUT/'review';dest.mkdir(exist_ok=True)
    decisions=read(dest/'decisions.json') if (dest/'decisions.json').exists() else {}
    if original:decisions={}
    for idx in indices:
        rr=[r for r in rows if r['overview_index']==idx]
        boxes=[r['proposal_xyxy'] for r in rr if r['proposal_xyxy']]
        y0=max(0,min(b[1] for b in boxes)-35);y1=min(rr[0]['shape_hw'][0],max(b[3] for b in boxes)+40)
        for page in range(5):
            canvas=Image.new('RGB',(1600,960),'white')
            for k,r in enumerate(rr[page*20:page*20+20]):
                a=arr(r['source']);h,w=a.shape
                dec=decisions.get(r['sample'],{})
                b=dec.get('final_xyxy',r['proposal_xyxy'])
                im=Image.fromarray(np.clip(a[y0:y1].astype(float)*2.5,0,255).astype(np.uint8)).convert('RGB').resize((320,205))
                t=Image.new('RGB',(320,240),'white');t.paste(im,(0,35));d=ImageDraw.Draw(t)
                d.text((2,0),f"r{idx:02d} #{r['ordinal']:02d} f={r['frame']} y{y0}:{y1}",fill='black')
                d.text((2,17),str(b)+' '+dec.get('decision','pending'),fill='black')
                if b:
                    d.rectangle((b[0]*2.5,35+(b[1]-y0)*205/(y1-y0),min(319,b[2]*2.5),35+(b[3]-y0)*205/(y1-y0)),outline='#00ff60',width=1)
                canvas.paste(t,((k%5)*320,(k//5)*240))
            target=dest/f'r{idx:02d}_p{page}.jpg'
            if target.exists():archive_sheet(target)
            canvas.save(target,quality=95)
            archive_sheet(target)
    print('rendered',indices)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('indices',nargs='*',type=int);a=p.parse_args();render(a.indices or SELECTED)
