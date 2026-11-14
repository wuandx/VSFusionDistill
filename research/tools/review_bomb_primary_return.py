"""Independent visible-return proposals, never automatic acceptance."""
import sys
sys.path[:0]=['tools','tools/_sonar_audit_deps']
import review_paired_local as r
import numpy as np
import cv2
orig=r.e.body_options
def primary(row,a,shuffle=False):
    opts=orig(row,a,shuffle=False)
    sm=cv2.GaussianBlur(a.astype(np.float32),(3,7),0)
    seed=opts.get('E',opts.get('B'))
    if not seed:return opts
    y0=max(0,seed[1]-15);y1=min(a.shape[0],seed[3]+60)
    points=[]
    for x in range(a.shape[1]):
        col=sm[y0:y1,x]; j=int(np.argmax(col)); peak=float(col[j])
        if peak<55:continue
        thr=max(35,peak*.42)
        lo=j;hi=j
        while lo>0 and col[lo-1]>thr:lo-=1
        while hi<len(col)-1 and col[hi+1]>thr:hi+=1
        points.extend([(x,y0+lo),(x,y0+hi)])
    if points:
        q=np.array(points); opts['G']=[max(0,int(q[:,0].min())-2),max(0,int(q[:,1].min())-5),min(a.shape[1],int(q[:,0].max())+3),min(a.shape[0],int(q[:,1].max())+6)]
    return opts
r.e.body_options=primary
r.OUT=r.ROOT/'DataSet/paired_assistant_bomb_primary_return'
if __name__=='__main__':
    r.build(sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),'G')
