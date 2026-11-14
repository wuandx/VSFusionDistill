"""Uniform full-trajectory candidates for four unlabeled development recordings."""
from audit_all94_coverage import *
D=ROOT/'DataSet/four_recording_paired_annotation'
RECS=['2023-09-20_180126','2023-09-21_124241','2023-09-21_124440','2023-09-21_125924']
def main():
    D.mkdir(exist_ok=False);(D/'overview').mkdir()
    inv={x['recording']:x for x in read(ROOT/'DataSet/all94_recording_coverage_audit/inventory-reviewed.json')}
    legacy=read(DATA/'uxo-full/split_manifest.json')['recordings']
    matches={Path(x['aris_file']).name:x for x in csv.DictReader((DATA/'data_processed/matches.csv').open(encoding='utf-8-sig'))}
    fixed={str(p):sha(p) for p in [DATA/'data_processed/matches.csv',CURRENT/'manifest.json',CURRENT/'recordings.json',ROOT/'experiment/archive/four-recording-paired-annotation-plan.md']}
    items=[];summaries=[];font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',17)
    for rec in RECS:
        assert legacy[rec]['split']!='test'
        r=inv[rec];match=matches[rec];root=NATIVE/r['category_dir']/rec
        assert not list((root/'labels').glob('*.json'))
        clip=Path(r['camera_clip']);pr=probe(clip);fps=pr['fps'];nf=int(pr['nb_frames'])
        meta=DATA/'data_processed/aris'/rec/(rec+'_frames.csv');md={int(x['FrameIndex']):x for x in csv.DictReader(meta.open(encoding='utf-8-sig'))};onset=int(md[int(match['aris_onset'])]['FrameTime'])
        for p in [clip,meta,root/'notes.txt']:fixed[str(p)]=sha(p)
        pool=[];seen=set()
        for raw in sorted((root/'aris_raw').glob('*.pgm'),key=lambda p:int(p.stem)):
            f=int(raw.stem)
            if f not in md:continue
            si=int((int(md[f]['FrameTime'])-onset)/1e6*fps)+int(match['gopro_offset'])
            if 0<=si<nf and si not in seen:pool.append((f,si,raw));seen.add(si)
        selected=[pool[round(j*(len(pool)-1)/99)] for j in range(100)]
        folder=D/rec;folder.mkdir();lookup=extract(clip,[x[1] for x in selected],folder/'sd');rr=[]
        for j,(f,si,raw) in enumerate(selected):
            a=raw_array(raw);r0=dict(sample=f'{rec}_{f:04d}',recording=rec,category=r['category'],frame=f,sd_index=si,ordinal=j,camera_source=str(lookup[si]),camera_sha256=sha(lookup[si]),sonar_source=str(raw),sonar_sha256=sha(raw),sonar_size_wh=list(a.shape[::-1]),camera_size_wh=[640,360],camera_boxes_xyxy=[],sonar_bbox_xyxy=None,decision='unreviewed',mapping='published_SD_FrameTime_onset_fps_offset',precision_sync_certified=False,expert_verified=False,annotation_origin='assistant_new_visible_target_annotation',role='pending',group_id='grenade_roll90_124241_124440' if rec.endswith(('124241','124440')) else rec,scene_id=r['scene_id'],nominal={k:r[k] for k in ['z','tilt','roll','placement','trajectory']})
            rr.append(r0);items.append(r0)
        for page in range(2):
            canvas=Image.new('RGB',(1920,1670),'#f4f6fa');draw=ImageDraw.Draw(canvas)
            for k in range(6):
                j=round((page*6+k)*99/11);x=k%3*640;y=k//3*830;r0=rr[j]
                draw.text((x+3,y+3),f'{rec} ordinal{j} ARIS{r0["frame"]} SD{r0["sd_index"]}',fill='black',font=font)
                canvas.paste(Image.open(r0['camera_source']).convert('RGB'),(x,y+30));a=raw_array(r0['sonar_source']);s=Image.fromarray(np.clip(a.astype(float)*2.5,0,255).astype(np.uint8)).convert('RGB')
                canvas.paste(s.resize((128,430)),(x,y+395));canvas.paste(s.resize((500,430)),(x+135,y+395))
            canvas.save(D/'overview'/f'{rec}-{page}.jpg',quality=96)
        summaries.append(dict(recording=rec,notes=r['notes'],raw_mapping_capacity=len(pool),selected=100,probe=pr,source_clip=str(clip)))
        print(rec,len(pool),flush=True)
    save(D/'proposals-unboxed.json',items);save(D/'recordings.json',summaries);save(D/'inputs-sha256.json',fixed)
    assert all(sha(p)==h for p,h in fixed.items())
if __name__=='__main__':main()
