"""100 stratified proposals per new recording; all require actual visual review."""
from expand_paired_recording_pool import *

BANDS={'2023-09-20_174200':(80,300), '2023-09-20_174711':(80,330), '2023-09-21_124735':(160,380),
       '2023-09-21_155609':(40,270), '2023-09-21_160146':(100,340),
       '2023-09-21_161916':(280,550),'2023-09-21_162055':(330,620)}

def proposal(a, rec):
    y0,y1=BANDS[rec];s=cv2.GaussianBlur(a.astype(np.float32),(3,5),0);roi=s[y0:y1]
    bg=float(np.median(roi));mad=float(np.median(abs(roi-bg)));threshold=bg+max(8,2.5*mad)
    mask=cv2.morphologyEx((roi>threshold).astype(np.uint8),cv2.MORPH_CLOSE,np.ones((5,3),np.uint8))
    n,lab,stats,_=cv2.connectedComponentsWithStats(mask)
    opts=[]
    for k in range(1,n):
        x,y,w,h,area=map(int,stats[k]);
        if area<12:continue
        energy=float(np.maximum(roi[lab==k]-threshold,0).sum())
        opts.append((energy,[max(0,x-2),max(0,y+y0-4),min(128,x+w+2),min(a.shape[0],y+y0+h+4)]))
    return max(opts)[1] if opts else None

def main():
    rows=read(OUT/'inventory.json');matches={Path(x['aris_file']).name:x for x in csv.DictReader((DATA/'data_processed/matches.csv').open(encoding='utf-8-sig'))}
    dest=OUT/'full-review';dest.mkdir(exist_ok=True);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',15)
    for row in rows:
        rec=row['recording']
        if rec not in BANDS:continue
        folder=dest/rec
        if (folder/'spec.json').exists():continue
        folder.mkdir(exist_ok=True);(folder/'sd').mkdir(exist_ok=True)
        root=Path(row['source_root']);match=matches[rec];p=read(OUT/'pilots'/rec/'pilot.json');fps=float(Fraction(p['probe']['avg_frame_rate']));nf=int(p['probe']['nb_frames'])
        meta={int(x['FrameIndex']):x for x in csv.DictReader((DATA/'data_processed/aris'/rec/(rec+'_frames.csv')).open(encoding='utf-8-sig'))}
        origin=int(meta[int(match['aris_onset'])]['FrameTime']);available=[]
        for label in sorted((root/'labels').glob('*.json'),key=lambda p:int(p.stem)):
            f=int(label.stem);si=int((int(meta[f]['FrameTime'])-origin)/1e6*fps)+int(match['gopro_offset']);raw=root/'aris_raw'/f'{f:04d}.pgm'
            if 0<=si<nf and raw.exists():available.append((label,raw,f,si))
        take=[available[round(j*(len(available)-1)/99)] for j in range(100)]
        indices=sorted({x[3] for x in take});expr='+'.join(f'eq(n\\,{x})' for x in indices)
        run(['ffmpeg','-hide_banner','-loglevel','error','-threads','2','-i',p['source_clip'],'-vf','select='+expr,'-fps_mode','passthrough','-q:v','2',str(folder/'sd/%03d.jpg')])
        extracted=sorted((folder/'sd').glob('*.jpg'));assert len(extracted)==len(indices);lookup=dict(zip(indices,extracted));items=[]
        for ordinal,(label,raw,f,si) in enumerate(take):
            a=cv2.imdecode(np.frombuffer(raw.read_bytes(),np.uint8),cv2.IMREAD_UNCHANGED);lab=read(label);b=[lab[k] for k in ['x_min','y_min','x_max','y_max']]
            assert lab['class']==row['category'] and 0<=b[0]<b[2]<=640 and 0<=b[1]<b[3]<=360
            box=proposal(a,rec)
            items.append(dict(ordinal=ordinal,sample=f'{rec}_{f:04d}',recording=rec,category=row['category'],frame=f,sd_index=si,camera_image=str(lookup[si].relative_to(OUT)),camera_boxes_xyxy=[b],
                              camera_sha256=sha(lookup[si]),original_label=str(label),original_label_sha256=sha(label),sonar_source=str(raw),sonar_sha256=sha(raw),sonar_shape=list(a.shape),proposal_xyxy=box,
                              decision='unreviewed',metadata=meta[f],precision_sync_certified=False,expert_verified=False))
        sheets=[]
        for start in range(0,100,20):
            canvas=Image.new('RGB',(1800,2300),'#f4f6f8');d=ImageDraw.Draw(canvas)
            d.text((5,5),rec+' | ORIGINAL CAMERA GT + PROPOSED SONAR BOX; review required; sonar display gain2.5',font=font,fill='black')
            for j,x in enumerate(items[start:start+20]):
                ox=(j%4)*450;oy=30+(j//4)*450;d.text((ox+2,oy),f"{x['ordinal']} f{x['frame']} {x['proposal_xyxy']}",font=font,fill='black')
                cam=Image.open(OUT/x['camera_image']).convert('RGB');ImageDraw.Draw(cam).rectangle(x['camera_boxes_xyxy'][0],outline='#00ff60',width=2);canvas.paste(cam.resize((446,251)),(ox,oy+22))
                a=cv2.imdecode(np.frombuffer(Path(x['sonar_source']).read_bytes(),np.uint8),cv2.IMREAD_UNCHANGED);son=Image.fromarray(np.clip(a.astype(float)*2.5,0,255).astype(np.uint8)).convert('RGB');b=x['proposal_xyxy']
                full=son.copy()
                if b:ImageDraw.Draw(full).rectangle(b,outline='#00ff60',width=2)
                canvas.paste(full.resize((112,167)),(ox,oy+280));lo=max(0,b[1]-25) if b else 0;hi=min(a.shape[0],b[3]+25) if b else a.shape[0]
                zoom=son.crop((0,lo,128,hi)).resize((330,167))
                if b:ImageDraw.Draw(zoom).rectangle((b[0]*330/128,(b[1]-lo)*167/(hi-lo),min(329,b[2]*330/128),min(166,(b[3]-lo)*167/(hi-lo))),outline='#00ff60',width=2)
                canvas.paste(zoom,(ox+115,oy+280))
            sheet=folder/f'page-{start:03d}.jpg';canvas.save(sheet,quality=95);sheets.append(dict(start=start,path=str(sheet.relative_to(OUT)),sha256=sha(sheet)))
        save(folder/'spec.json',dict(recording=rec,source_clip=p['source_clip'],source_clip_sha256=sha(p['source_clip']),items=items,sheets=sheets,
                                    method='image-only component proposals in broad band chosen from actual pilots; no auto acceptance; original camera GT retained'))
        print(rec,'100 candidates, 5 sheets',flush=True)

if __name__=='__main__':main()
