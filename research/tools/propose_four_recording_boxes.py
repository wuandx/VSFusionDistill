"""Image-processing proposals only. Review and decisions are separate."""
from prepare_four_recording_annotations import *
def camera_box(r):
    a=np.asarray(Image.open(r['camera_source']).convert('RGB')).astype(float)
    red,g,b=a[:,:,0],a[:,:,1],a[:,:,2]
    ratio=.82 if r['recording'].endswith('125924') else 1.035
    mask=((red>g*ratio)&(g>b*1.13)&(red>43)&(g>35)).astype(np.uint8)
    mask[:65]=0;mask[350:]=0;mask[:,:190]=0;mask[:,465:]=0
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
    n,lab,stats,_=cv2.connectedComponentsWithStats(mask)
    opts=[(int(s[4]),s) for s in stats[1:] if s[4]>200]
    _,s=max(opts,key=lambda v:v[0]);x,y,w,h,area=map(int,s)
    return [max(0,x-4),max(0,y-5),min(640,x+w+5),min(360,y+h+6)]
def sonar_box(r):
    a=raw_array(r['sonar_source']);sm=cv2.GaussianBlur(a.astype(np.float32),(3,5),0);rec=r['recording'][-6:]
    lo,hi,thr={'180126':(110,335,12),'124241':(230,365,65),'124440':(230,365,8),'125924':(120,260,9)}[rec]
    roi=sm[lo:hi];bg=float(np.median(roi));threshold=thr if rec=='124241' else bg+thr
    mask=(roi>threshold).astype(np.uint8)
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    n,lab,stats,_=cv2.connectedComponentsWithStats(mask)
    opts=[]
    for k,s in enumerate(stats[1:],1):
        x,y,w,h,area=map(int,s)
        if area<12:continue
        score=float(np.maximum(roi[lab==k]-threshold,0).sum())
        opts.append((score,[max(0,x-2),max(0,y+lo-4),min(128,x+w+2),min(a.shape[0],y+lo+h+5)]))
    return max(opts)[1] if opts else None
def render(items,version):
    folder=D/version;folder.mkdir(exist_ok=False);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',15);sheets=[]
    for rec in RECS:
        rr=[r for r in items if r['recording']==rec]
        for page in range(5):
            canvas=Image.new('RGB',(1920,2360),'#f4f6fa');draw=ImageDraw.Draw(canvas)
            for k,r in enumerate(rr[page*20:(page+1)*20]):
                x=k%4*480;y=k//4*470
                draw.text((x+3,y+2),f'{rec[-6:]} #{r["ordinal"]} f{r["frame"]} SD{r["sd_index"]}',font=font,fill='black')
                cam=Image.open(r['camera_source']).convert('RGB');b=r['camera_boxes_xyxy'][0];ImageDraw.Draw(cam).rectangle(b,outline='#00ff40',width=2)
                canvas.paste(cam.resize((476,268)),(x,y+23))
                cb=Image.open(r['camera_source']).convert('RGB');pad=8;crop=cb.crop((b[0]-pad,b[1]-pad,b[2]+pad,b[3]+pad));ImageDraw.Draw(crop).rectangle((pad,pad,b[2]-b[0]+pad,b[3]-b[1]+pad),outline='#00ff40',width=1);crop.thumbnail((140,160));canvas.paste(crop,(x,y+300))
                a=raw_array(r['sonar_source']);s=Image.fromarray(np.clip(a.astype(float)*2.5,0,255).astype(np.uint8)).convert('RGB');b=r['sonar_bbox_xyxy'];full=s.copy()
                if b:ImageDraw.Draw(full).rectangle(b,outline='#00ff40',width=1)
                canvas.paste(full.resize((60,163)),(x+145,y+300))
                if b:
                    low=max(0,b[1]-18);high=min(a.shape[0],b[3]+18);crop=s.crop((0,low,128,high));ImageDraw.Draw(crop).rectangle((b[0],b[1]-low,min(127,b[2]),b[3]-low),outline='#00ff40',width=1);canvas.paste(crop.resize((265,163)),(x+210,y+300))
                r['sheet']=f'{version}/{rec}-{page}.jpg'
            p=folder/f'{rec}-{page}.jpg';canvas.save(p,quality=96);sheets.append(dict(path=str(p.relative_to(D)),sha256=sha(p)))
    save(folder/'sheet-sha256.json',sheets)
def main():
    items=read(D/'proposals-unboxed.json')
    for r in items:r['camera_boxes_xyxy']=[camera_box(r)];r['sonar_bbox_xyxy']=sonar_box(r)
    render(items,'proposal_v1');save(D/'proposals-v1.json',items)
    print('proposals',len(items),'pages',20,flush=True)
if __name__=='__main__':main()
