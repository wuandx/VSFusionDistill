"""Read-only source checks and explicit review for three excluded mortar flybys."""
from expand_scene_stratified_pairs import raw_array
from expand_paired_recording_pool import *
from datetime import datetime, timezone

DEST=ROOT/'DataSet/mortar_flyby_recovery'
CAM=ROOT/'DataSet/camera_temporal_all'
RECS=['2023-09-21_105856','2023-09-21_110229','2023-09-21_110411']

def sheet(items,path,title,boxes=None):
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16)
    canvas=Image.new('RGB',(1800,35+int(np.ceil(len(items)/4))*560),'white');d=ImageDraw.Draw(canvas)
    d.text((4,4),title,fill='black',font=font)
    for j,x in enumerate(items):
        ox=j%4*450;oy=35+j//4*560
        d.text((ox+2,oy),f'{x.get("ordinal",j)} f{x["aris_frame"]} t{x["t_s"]:.2f} sd{x["sd_index"]}',fill='black',font=font)
        im=Image.open(x['camera_source']).convert('RGB');dd=ImageDraw.Draw(im)
        for b in x['camera_boxes_xyxy']:dd.rectangle(b,outline='#00ff60',width=2)
        canvas.paste(im.resize((446,251)),(ox,oy+24))
        a=raw_array(x['sonar_source']);im=Image.fromarray(np.clip(a.astype(float)*2.5,0,255).astype(np.uint8)).convert('RGB')
        b=boxes.get(x['sample']) if boxes else None
        if b:ImageDraw.Draw(im).rectangle(b,outline='#00ff60',width=1)
        lo=max(0,b[1]-25) if b else 0;hi=min(im.height,b[3]+25) if b else im.height
        canvas.paste(im.resize((112,270)),(ox,oy+282));canvas.paste(im.crop((0,lo,128,hi)).resize((330,270)),(ox+115,oy+282))
    canvas.save(path,quality=96)

def prepare():
    assert not (DEST/'sources.json').exists(),'Preserve named recovery'
    DEST.mkdir(exist_ok=True)
    invpath=ROOT/'DataSet/paired_paper_scale/source-inventory.json';tmpath=CAM/'manifest-resolved.json';split=DATA/'uxo-full/split_manifest.json';matchpath=DATA/'data_processed/matches.csv'
    fixed={str(p):sha(p) for p in [invpath,tmpath,split,matchpath,ROOT/'experiment/archive/mortar-flyby-recovery-plan.md',ROOT/'DataSet/scene_stratified_paired_expansion/manifest.json']}
    inv=read(invpath);lookup={x['sample']:x for x in read(tmpath)['items']};legacy=read(split)['recordings']
    matches={Path(x['aris_file']).name:x for x in csv.DictReader(matchpath.open(encoding='utf-8-sig'))}
    sources=[];records=[]
    for rec in RECS:
        assert legacy[rec]['split']!='test';folder=DEST/rec;folder.mkdir(exist_ok=True)
        match=matches[rec];video=DATA/'data_processed'/match['gopro_file'];fixed[str(video)]=sha(video)
        mp=DATA/'data_processed'/match['aris_file']/(rec+'_frames.csv');fixed[str(mp)]=sha(mp)
        md={int(m['FrameIndex']):m for m in csv.DictReader(mp.open(encoding='utf-8-sig'))};onset=int(md[int(match['aris_onset'])]['FrameTime'])
        cap=cv2.VideoCapture(str(video));fps=cap.get(cv2.CAP_PROP_FPS);nf=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));xs=[]
        for x in [x for x in inv if x['recording']==rec]:
            assert not x['camera_issues'];m=lookup[x['sample']];t=(int(md[x['aris_frame']]['FrameTime'])-onset)/1e6
            si=int(t*fps)+int(match['gopro_offset']);assert si==m['sd_index'] and 0<=si<nf
            cp=CAM/x['reference_sd'];lp=CAM/x['label_copy'];sp=Path(m['original_image']).parent.parent/'aris_raw'/f'{x["aris_frame"]:04d}.pgm'
            lab=read(lp);assert lab['class']=='mortar_shell' and x['camera_boxes_xyxy']==[[lab[k] for k in ('x_min','y_min','x_max','y_max')]]
            y=dict(x);y.update(t_s=t,sd_index=si,camera_source=str(cp),camera_label_source=str(lp),sonar_source=str(sp),
                camera_sha256=sha(cp),camera_label_sha256=sha(lp),sonar_sha256=sha(sp),ordinal=len(xs))
            xs.append(y)
        # Fixed 12 equally spaced identities, no appearance-based selection.
        take=[xs[round(j*(len(xs)-1)/11)] for j in range(12)]
        comparisons=[]
        for x in take:
            cap.set(cv2.CAP_PROP_POS_FRAMES,x['sd_index']);ok,frame=cap.read();assert ok
            image=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB);stored=np.array(Image.open(x['camera_source']).convert('RGB'))
            mse=float(np.mean((image.astype(float)-stored.astype(float))**2));assert mse<12,mse
            comparisons.append(dict(sample=x['sample'],sd_index=x['sd_index'],decoded_video_vs_reference_sd_mse=mse))
        cap.release();sheet(take,folder/'overview.jpg',rec+' | fixed time overview | NO NEW SONAR BOXES')
        # Four samples/second across annotated span, decoded directly by published mapping.
        cap=cv2.VideoCapture(str(video));targets=np.arange(xs[0]['t_s'],xs[-1]['t_s']+.0001,.25)
        encoder=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1024x620','-r','4','-i','pipe:0','-an','-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(folder/'published-pairing.mp4')],stdin=subprocess.PIPE)
        native=Path(xs[0]['sonar_source']).parent;meta=list(md.values());times=np.array([(int(m['FrameTime'])-onset)/1e6 for m in meta]);samples=[];keys=[]
        for j,t in enumerate(targets):
            row=meta[int(np.argmin(abs(times-t)))];fr=int(row['FrameIndex']);tt=(int(row['FrameTime'])-onset)/1e6;si=int(tt*fps)+int(match['gopro_offset'])
            sp=native/f'{fr:04d}.pgm';a=raw_array(sp);cap.set(cv2.CAP_PROP_POS_FRAMES,si);ok,frame=cap.read();assert ok
            canvas=Image.new('RGB',(1024,620),'white');d=ImageDraw.Draw(canvas)
            canvas.paste(Image.fromarray(np.clip(a.astype(float)*2.5,0,255).astype(np.uint8)).convert('RGB').resize((350,520)),(4,75))
            canvas.paste(Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)),(375,150))
            d.text((8,10),f'{rec} published mapping | ARIS f{fr} t={tt:.3f}s | SD {si}',fill='black')
            d.text((8,32),'No timing adjustment / no sonar boxes. Raw display gain2.5 only.',fill='black')
            encoder.stdin.write(np.array(canvas).tobytes())
            samples.append(dict(frame=fr,t_s=tt,sd_index=si,sonar_source=str(sp),sonar_sha256=sha(sp),sd_decoded_pixel_sha256=hashlib.sha256(frame.tobytes()).hexdigest()))
            if j%4==0 or j==len(targets)-1:keys.append(canvas.resize((512,310)))
        encoder.stdin.close();assert encoder.wait()==0;cap.release()
        for start in range(0,len(keys),16):
            selected=keys[start:start+16];contact=Image.new('RGB',(1024,310*int(np.ceil(len(selected)/2))),'white')
            for j,im in enumerate(selected):contact.paste(im,(j%2*512,j//2*310))
            contact.save(folder/f'timeline-{start:03d}.jpg',quality=96)
        sources+=xs;records.append(dict(recording=rec,match=match,source_video=str(video),source_video_sha256=sha(video),fps=fps,source_frames=nf,
             annotated_count=len(xs),annotated_time_span_s=[xs[0]['t_s'],xs[-1]['t_s']],index_map_checked=len(xs),reference_sd_pixel_checks=comparisons,
             timeline_samples=samples,precision_sync_certified=False,pairing_review='pending'))
        print(rec,'source',len(xs),'timeline',len(samples),flush=True)
    for p,h in fixed.items():assert sha(p)==h,p
    save(DEST/'sources.json',sources);save(DEST/'source-recordings.json',records);save(DEST/'inputs-sha256.json',fixed)

def propose_105856():
    folder=DEST/RECS[0];assert not (folder/'proposals.json').exists()
    xs=[x for x in read(DEST/'sources.json') if x['recording']==RECS[0]]
    # Coordinates from the saved unboxed coordinate review, not production labels.
    anchors={150:[40,208,71,290],169:[39,199,71,286],187:[38,188,73,276],206:[37,174,75,267],225:[36,164,76,260],
             243:[36,152,76,253],262:[38,148,76,244],280:[40,138,76,241],299:[40,139,77,232],318:[41,144,78,227],336:[40,134,79,224],355:[40,133,79,214]}
    keys=sorted(anchors);take=[dict(xs[round(j*(len(xs)-1)/59)]) for j in range(60)]
    for j,x in enumerate(take):
        x['ordinal']=j;x['proposed_box']=[int(round(float(np.interp(x['aris_frame'],keys,[anchors[k][i] for k in keys])))) for i in range(4)]
        x['proposal_method']='interpolated_visual_coordinate_anchors_requires_per_item_review'
    for start in range(0,60,20):
        path=folder/f'proposal-{start:03d}.jpg';batch=take[start:start+20]
        sheet(batch,path,RECS[0]+' | VISUAL ANCHOR PROPOSALS, NOT ACCEPTED',boxes={x['sample']:x['proposed_box'] for x in batch})
        for x in batch:x['sheet']=str(path.relative_to(DEST));x['sheet_sha256']=sha(path)
    save(folder/'proposal-method.json',dict(anchors=anchors,coordinate_review_sha256=sha(DEST/'105856-coordinate-review.jpg'),automatically_accepted=False))
    save(folder/'proposals.json',take);print('60 explicit-review proposals prepared')

def decide_105856(start,accepted,reason):
    folder=DEST/RECS[0];items=[x for x in read(folder/'proposals.json') if start<=x['ordinal']<start+20]
    ids=set(accepted);assert ids<={x['ordinal'] for x in items}
    p=folder/'decisions.json';decisions=read(p) if p.exists() else {}
    for x in items:
        assert sha(DEST/x['sheet'])==x['sheet_sha256']
        d=dict(sample=x['sample'],ordinal=x['ordinal'],recording=RECS[0],decision='accepted' if x['ordinal'] in ids else 'unresolved',
               bbox_xyxy=x['proposed_box'] if x['ordinal'] in ids else None,reason=reason,author='assistant',reviewed_at=datetime.now(timezone.utc).isoformat(),
               sheet=x['sheet'],sheet_sha256=x['sheet_sha256'],camera_box_reviewed=True,cross_view_review='consistent_visible_target' if x['ordinal'] in ids else 'unresolved',
               precision_sync_certified=False,expert_verified=False,user_accepted=False)
        with (folder/'review-events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(dict(previous=decisions.get(x['sample']),current=d),ensure_ascii=False)+'\n')
        decisions[x['sample']]=d
    save(p,decisions);print('reviewed',len(decisions),'accepted',sum(x['decision']=='accepted' for x in decisions.values()))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','propose'],default='prepare',nargs='?');a=p.parse_args()
    if a.mode=='prepare':prepare()
    else:propose_105856()
