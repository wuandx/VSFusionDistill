"""Additional bright-body proposal, always requiring saved visual decisions."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'_sonar_audit_deps'))
import review_paired_local as r
e=r.e
base=e.body_options

def proposals(row,a,shuffle=False):
    opts=base(row,a,shuffle=False)
    seed=opts.get('E') or opts.get('F')
    if seed:
        sm=e.cv2.GaussianBlur(a.astype(e.np.float32),(3,5),0)
        mask=(sm>max(50,float(e.np.percentile(sm,30))+40)).astype(e.np.uint8)
        mask=e.cv2.morphologyEx(mask,e.cv2.MORPH_CLOSE,e.np.ones((5,3),e.np.uint8))
        n,lab,stats,_=e.cv2.connectedComponentsWithStats(mask)
        candidates=[]
        x0,y0,x1,y1=seed
        for k in range(1,n):
            x,y,w,h,area=map(int,stats[k]);overlap=int((lab[y0:y1,x0:x1]==k).sum())
            if area>=12 and overlap>=6:candidates.append((overlap,k))
        if candidates:
            _,k=max(candidates);x,y,w,h,area=map(int,stats[k])
            opts['G']=[max(0,x-2),max(0,y-5),min(a.shape[1],x+w+2),min(a.shape[0],y+h+5)]
    return opts

e.body_options=proposals
r.OUT=r.ROOT/'DataSet/paired_assistant_grenade_remaining_body'

if __name__=='__main__':
    r.build(sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),'G')
