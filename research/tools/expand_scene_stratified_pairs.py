"""Expand paired frames in fixed scene-stratified recording roles; explicit review only."""
from expand_paired_recording_pool import *
from datetime import datetime, timezone
import argparse

BASE=ROOT/'DataSet/scene_stratified_recording_candidate'
DEST=ROOT/'DataSet/scene_stratified_paired_expansion'
CAM=ROOT/'DataSet/camera_temporal_all'
GREEN='#00ff60'

def raw_array(path):
    a=cv2.imdecode(np.frombuffer(Path(path).read_bytes(),np.uint8),cv2.IMREAD_UNCHANGED)
    assert a.ndim==2 and a.dtype==np.uint8 and a.shape[1]==128
    return a

def suggest(a,anchor):
    h,w=a.shape;sm=cv2.GaussianBlur(a.astype(np.float32),(3,5),0)
    x0,y0,x1,y1=anchor
    lo=max(0,y0-50);hi=min(h,y1+50);roi=sm[lo:hi]
    bg=float(np.median(roi));mad=float(np.median(abs(roi-bg)))
    thr=bg+max(8,2.5*mad)
    mask=cv2.morphologyEx((roi>thr).astype(np.uint8),cv2.MORPH_CLOSE,np.ones((5,3),np.uint8))
    n,lab,stats,_=cv2.connectedComponentsWithStats(mask)
    opts=[]
    for k in range(1,n):
        x,y,bw,bh,area=map(int,stats[k]);y+=lo
        if area<12:continue
        inter=max(0,min(x+bw,x1)-max(x,x0))*max(0,min(y+bh,y1)-max(y,y0))
        if not inter:continue
        score=inter+float(np.maximum(roi[lab==k]-thr,0).sum())*.01
        opts.append((score,[max(0,x-2),max(0,y-4),min(w,x+bw+2),min(h,y+bh+4)]))
    return max(opts)[1] if opts else None

def prepare():
    assert not (DEST/'proposals.json').exists(),'Keep named proposal batch'
    DEST.mkdir(exist_ok=True);(DEST/'sheets').mkdir(exist_ok=True);(DEST/'sd').mkdir(exist_ok=True)
    old=read(BASE/'manifest.json');rs=read(BASE/'recordings.json');recs={r['recording']:r for r in rs}
    inv={r['recording']:r for r in read(OUT/'inventory.json')}
    legacy=read(DATA/'uxo-full/split_manifest.json')['recordings']
    assert all(legacy[r]['split']!='test' for r in recs)
    prior={x['sample'] for x in old}
    for file in (ROOT/'DataSet').glob('paired*/**/decisions.json'):
        values=read(file);values=list(values.values()) if isinstance(values,dict) else values
        prior.update(r['sample'] for r in values if isinstance(r,dict) and 'sample' in r)
    for file in (OUT/'full-review').glob('*/spec.json'):
        prior.update(r['sample'] for r in read(file)['items'])
    source=read(ROOT/'DataSet/paired_paper_scale/source-inventory.json')
    temp=read(CAM/'manifest-resolved.json');temp={x['sample']:x for x in temp['items']}
    src=defaultdict(list)
    for x in source:
        if x['recording'] not in recs or x['sample'] in prior or x['camera_issues'] or not x['pairing']['eligible_for_review']:continue
        m=temp[x['sample']];raw=Path(m['original_image']).parent.parent/'aris_raw'/f"{m['aris_frame']:04d}.pgm"
        src[x['recording']].append(dict(sample=x['sample'],recording=x['recording'],category=x['category'],frame=x['aris_frame'],sd_index=m['sd_index'],
            camera_source=str(CAM/x['reference_sd']),camera_label_source=str(CAM/x['label_copy']),camera_boxes_xyxy=x['camera_boxes_xyxy'],sonar_source=str(raw)))
    matches={Path(x['aris_file']).name:x for x in csv.DictReader((DATA/'data_processed/matches.csv').open(encoding='utf-8-sig'))}
    fixed_paths=[BASE/'manifest.json',BASE/'protocol.json',BASE/'recordings.json',ROOT/'DataSet/paired_paper_scale/source-inventory.json',
        OUT/'inventory.json',DATA/'uxo-full/split_manifest.json',ROOT/'experiment/archive/scene-stratified-paired-expansion-plan.md']
    hashes={str(p):sha(p) for p in fixed_paths}
    for rec in recs:
        if inv[rec]['status']!='new_non_test_pilot':continue
        root=Path(inv[rec]['source_root']);pilot=read(OUT/'pilots'/rec/'pilot.json');match=matches[rec]
        fps=float(Fraction(pilot['probe']['avg_frame_rate']));nf=int(pilot['probe']['nb_frames'])
        frames={int(x['FrameIndex']):x for x in csv.DictReader((DATA/'data_processed/aris'/rec/(rec+'_frames.csv')).open(encoding='utf-8-sig'))}
        onset=int(frames[int(match['aris_onset'])]['FrameTime']);hashes[pilot['source_clip']]=sha(pilot['source_clip'])
        for label in sorted((root/'labels').glob('*.json')):
            frame=int(label.stem);sample=f'{rec}_{frame:04d}'
            if sample in prior:continue
            lab=read(label);assert lab['class']==recs[rec]['category'];b=[lab[k] for k in ('x_min','y_min','x_max','y_max')]
            if not 0<=b[0]<b[2]<=640 or not 0<=b[1]<b[3]<=360:continue
            si=int((int(frames[frame]['FrameTime'])-onset)/1e6*fps)+int(match['gopro_offset']);raw=root/'aris_raw'/f'{frame:04d}.pgm'
            if not (0<=si<nf and raw.exists()):continue
            src[rec].append(dict(sample=sample,recording=rec,category=recs[rec]['category'],frame=frame,sd_index=si,camera_label_source=str(label),
                camera_boxes_xyxy=[b],sonar_source=str(raw),source_clip=pilot['source_clip']))
    items=[];counts=[];font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16)
    for rec,r in recs.items():
        accepted=[x for x in old if x['recording']==rec];frames=np.array([x.get('aris_frame',x.get('frame')) for x in accepted]);sd=np.array([x['sd_index'] for x in accepted])
        eligible=[x for x in src[rec] if np.min(abs(frames-x['frame']))>=2 and np.min(abs(sd-x['sd_index']))>=2]
        eligible.sort(key=lambda x:x['frame']);n=min(20,len(eligible));take=[eligible[round(i*(len(eligible)-1)/max(1,n-1))] for i in range(n)]
        # Avoid selecting multiple labels mapped to one camera frame in this batch.
        seen_sd=set();take=[x for x in take if not (x['sd_index'] in seen_sd or seen_sd.add(x['sd_index']))]
        if take and 'source_clip' in take[0]:
            folder=DEST/'sd'/rec;folder.mkdir(exist_ok=True);indices=sorted({x['sd_index'] for x in take})
            expr='+'.join(f'eq(n\\,{i})' for i in indices)
            run(['ffmpeg','-hide_banner','-loglevel','error','-threads','2','-i',take[0]['source_clip'],'-vf','select='+expr,'-fps_mode','passthrough','-q:v','2',str(folder/'%03d.jpg')])
            paths=sorted(folder.glob('*.jpg'));assert len(paths)==len(indices);lookup=dict(zip(indices,paths))
            for x in take:x['camera_source']=str(lookup[x['sd_index']])
        for x in take:
            a=raw_array(x['sonar_source']);nearest=min(accepted,key=lambda t:abs(t.get('aris_frame',t.get('frame'))-x['frame']))
            x.update(role=r['role'],group_id=r['group_id'],scene_id=r['scene_id'],sonar_size_wh=[a.shape[1],a.shape[0]],anchor_sample=nearest['sample'],
                anchor_box=nearest['sonar_bbox_xyxy'],proposal_xyxy=suggest(a,nearest['sonar_bbox_xyxy']),camera_sha256=sha(x['camera_source']),
                sonar_sha256=sha(x['sonar_source']),camera_label_sha256=sha(x['camera_label_source']),decision='unreviewed',
                expert_verified=False,precision_sync_certified=False)
            im=Image.open(x['camera_source']);assert im.size==(640,360)
        sheet_path=None
        if take:
            canvas=Image.new('RGB',(1800,2330),'white');draw=ImageDraw.Draw(canvas)
            draw.text((5,4),f'{rec} {r["role"]} | NEW FRAMES. ORIGINAL CAMERA / PROPOSED SONAR. NOT ACCEPTED.',font=font,fill='black')
            for j,x in enumerate(take):
                ox=(j%4)*450;oy=35+(j//4)*458;b=x['proposal_xyxy'];draw.text((ox+2,oy),f'{j} f{x["frame"]} {b}',font=font,fill='black')
                cam=Image.open(x['camera_source']).convert('RGB');ImageDraw.Draw(cam).rectangle(x['camera_boxes_xyxy'][0],outline=GREEN,width=2)
                canvas.paste(cam.resize((446,251)),(ox,oy+22));a=raw_array(x['sonar_source']);son=Image.fromarray(np.clip(a.astype(float)*2.5,0,255).astype(np.uint8)).convert('RGB')
                full=son.copy()
                if b:ImageDraw.Draw(full).rectangle(b,outline=GREEN,width=2)
                canvas.paste(full.resize((112,175)),(ox,oy+278));lo=max(0,b[1]-30) if b else 0;hi=min(a.shape[0],b[3]+30) if b else a.shape[0]
                zoom=son.crop((0,lo,128,hi)).resize((330,175))
                if b:ImageDraw.Draw(zoom).rectangle((b[0]*330/128,(b[1]-lo)*175/(hi-lo),min(329,b[2]*330/128),min(174,(b[3]-lo)*175/(hi-lo))),outline=GREEN,width=2)
                canvas.paste(zoom,(ox+115,oy+278));x['review_ordinal']=j
            sheet_path=DEST/'sheets'/(rec+'.jpg');canvas.save(sheet_path,quality=96)
            for x in take:x.update(sheet=str(sheet_path.relative_to(DEST)),sheet_sha256=sha(sheet_path))
        items.extend(take);counts.append(dict(recording=rec,role=r['role'],scene=r['scene_id'],existing_accepted=len(accepted),unreviewed_valid=len(src[rec]),eligible_with_gap=len(eligible),proposed=len(take)))
        print(rec,'proposed',len(take),flush=True)
    save(DEST/'proposals.json',items);save(DEST/'source-counts.json',counts);save(DEST/'inputs-sha256.json',hashes)
    print('total new proposals',len(items),flush=True)

def decide(rec,accept,reason):
    items=[x for x in read(DEST/'proposals.json') if x['recording']==rec];ids={int(i) for i in accept.split(',')} if accept else set()
    assert ids<={x['review_ordinal'] for x in items}
    p=DEST/'decisions.json';decisions=read(p) if p.exists() else {}
    for x in items:
        assert sha(DEST/x['sheet'])==x['sheet_sha256'];ok=x['review_ordinal'] in ids
        assert not ok or x['proposal_xyxy']
        previous=decisions.get(x['sample'])
        decisions[x['sample']]=dict(sample=x['sample'],recording=rec,decision='accepted' if ok else 'unresolved',bbox_xyxy=x['proposal_xyxy'] if ok else None,
            reason=reason,author='assistant',reviewed_at=datetime.now(timezone.utc).isoformat(),sheet=x['sheet'],sheet_sha256=x['sheet_sha256'],
            camera_box_reviewed=True,cross_view_review='consistent_visible_target' if ok else 'unresolved',expert_verified=False,precision_sync_certified=False)
        with (DEST/'review-events.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(dict(event='explicit_review',previous=previous,current=decisions[x['sample']]),ensure_ascii=False)+'\n')
    save(p,decisions);print(rec,'accepted',len(ids),'of',len(items),'total accepted',sum(x['decision']=='accepted' for x in decisions.values()))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','decide']);p.add_argument('--recording');p.add_argument('--accept',default='');p.add_argument('--reason',default='');args=p.parse_args()
    if args.mode=='prepare':prepare()
    else:decide(args.recording,args.accept,args.reason)
