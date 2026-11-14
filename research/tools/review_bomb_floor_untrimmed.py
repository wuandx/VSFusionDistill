"""Final floor proposal; no automatic labels, no energy trimming."""
import sys
sys.path[:0]=['tools','tools/_sonar_audit_deps']
import review_paired_local as r
import numpy as np
import cv2
orig=r.e.body_options
def untrimmed(row,a,shuffle=False):
    opts=orig(row,a,shuffle=False)
    sm=cv2.GaussianBlur(a.astype(np.float32),(3,7),0)
    mask=(sm>65).astype(np.uint8);mask[:80]=0;mask[420:]=0
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((9,3),np.uint8))
    n,lab,stats,_=cv2.connectedComponentsWithStats(mask)
    if n>1:
        k=max(range(1,n),key=lambda k:float(np.maximum(sm[lab==k]-65,0).sum()))
        x,y,w,h,_=map(int,stats[k]);opts['K']=[max(0,x-3),max(0,y-6),min(128,x+w+3),min(a.shape[0],y+h+6)]
    return opts
r.e.body_options=untrimmed
r.OUT=r.ROOT/'DataSet/paired_assistant_bomb_floor_untrimmed'
if __name__=='__main__':r.build('2023-09-21_160551',int(sys.argv[1]),int(sys.argv[2]),'K')
