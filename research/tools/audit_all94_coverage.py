"""Audit all94 metadata, fixed pilots for84 allowed sources and unassigned clips."""
from expand_paired_recording_pool import *
from expand_scene_stratified_pairs import raw_array
from fractions import Fraction
from datetime import datetime,timezone
D=ROOT/'DataSet/all94_recording_coverage_audit'
CURRENT=ROOT/'DataSet/paired_expanded_resplit_candidate'
CATS={'100lbs_bomb':'100lbs_aircraft_bomb','100lbs_bomb_(floor)':'100lbs_aircraft_bomb','15cm_mortar':'mortar_shell','20lbs_incendiary':'incindiary_grenade'}

def probe(p):
    q=json.loads(run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=avg_frame_rate,nb_frames,duration,width,height:format=duration','-of','json',str(p)]))
    s=q['streams'][0];return dict(s,duration=float(s.get('duration') or q['format']['duration']),fps=float(Fraction(s['avg_frame_rate'])))
def extract(clip,indices,folder):
    folder.mkdir(parents=True,exist_ok=True);indices=sorted(set(indices));expr='+'.join(f'eq(n\\,{i})' for i in indices)
    run(['ffmpeg','-hide_banner','-loglevel','error','-threads','2','-i',str(clip),'-vf','select='+expr,'-fps_mode','passthrough','-q:v','2','-start_number','0',str(folder/'%03d.jpg')])
    files=sorted(folder.glob('*.jpg'));assert len(files)==len(indices),(clip,indices,files);return dict(zip(indices,files))
def main():
    assert not (D/'inventory.json').exists(),'Preserve completed audit';D.mkdir(exist_ok=True);(D/'sheets').mkdir(exist_ok=True)
    paths=[DATA/'uxo-full/inventory.json',DATA/'uxo-full/split_manifest.json',DATA/'data_processed/matches.csv',CURRENT/'manifest.json',CURRENT/'recordings.json',ROOT/'experiment/archive/all94-recording-coverage-audit-plan.md']
    fixed={str(p):sha(p) for p in paths};inv=read(paths[0])['recordings'];legacy=read(paths[1])['recordings'];matches={Path(r['aris_file']).name:r for r in csv.DictReader(paths[2].open(encoding='utf-8-sig'))};current={r['recording']:r for r in read(paths[4])};items=read(paths[3]);prior={r['recording']:r for r in read(ROOT/'DataSet/recording_expansion_94_audit/inventory.json')}
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16);rows=[];pilots=[];sheet_records=[]
    for rec,m in sorted(inv.items()):
        match=matches[rec];native=DATA/'uxo-full/extracted/recordings'/m['category_dir']/rec;clip=DATA/'data_processed'/match['gopro_file'] if match['gopro_file'] else None;category=CATS.get(m['category_dir'],'test_cylinder');n=nominal(match['notes']);sid='|'.join((category,n['placement'],n['trajectory']))
        row=dict(recording=rec,category=category,category_dir=m['category_dir'],original_role=legacy[rec]['split'],current_role=current.get(rec,{}).get('role'),in_current=rec in current,**n,scene_id=sid,notes=match['notes'],camera_clip=str(clip) if clip else None,camera_clip_exists=bool(clip and clip.is_file()),original_labels_metadata=m['n_annotated'],native_gopro_metadata=m['n_gopro'],prior_review=prior[rec]['prior_review'],prior_state=prior[rec]['state'],sampled_frames=[],pilot_sheet=None,pilot_viewed=False)
        # Do not enumerate/open original test image/annotation content.
        if legacy[rec]['split']=='test':row['audit_scope']='metadata_only_original_test_closed';rows.append(row);continue
        raws=sorted((native/'aris_raw').glob('*.pgm'),key=lambda p:int(p.stem));labels=sorted((native/'labels').glob('*.json'));row.update(local_raw_count=len(raws),local_label_count=len(labels),local_native_camera_count=len(list((native/'gopro').glob('*.jpg'))))
        validlabels={};invalid=[]
        for lab in labels:
            a=read(lab);b=[a[k] for k in ('x_min','y_min','x_max','y_max')]
            if 0<=b[0]<b[2]<=640 and 0<=b[1]<b[3]<=360:validlabels[int(lab.stem)]=(lab,b)
            else:invalid.append(int(lab.stem))
        row['valid_original_sd_boxes']=len(validlabels);row['invalid_original_sd_box_frames']=invalid
        pp=[]
        if rec in current:
            xx=sorted([x for x in items if x['recording']==rec],key=lambda x:x['sample']);take=[xx[round(f*(len(xx)-1))] for f in (.1,.5,.9)]
            for x in take:pp.append(dict(recording=rec,frame=int(x.get('aris_frame',x['sample'].rsplit('_',1)[1])),camera_source=str(CURRENT/x['camera_image']),sonar_source=str(CURRENT/x['sonar_image']),camera_boxes=x['camera_boxes_xyxy'],sonar_box=x['sonar_bbox_xyxy'],sd_index=x.get('sd_index'),mapping='existing_accepted_pair',original_label=str(CURRENT/x['camera_original_label'])))
        elif row['camera_clip_exists']:
            pr=probe(clip);row['clip_probe']=pr;md={int(r['FrameIndex']):r for r in csv.DictReader((DATA/'data_processed/aris'/rec/(rec+'_frames.csv')).open(encoding='utf-8-sig'))};onset=int(md[int(match['aris_onset'])]['FrameTime']);nframes=int(pr['nb_frames']);pool=[]
            for raw in raws:
                f=int(raw.stem)
                if f not in md:continue
                si=int((int(md[f]['FrameTime'])-onset)/1e6*pr['fps'])+int(match['gopro_offset'])
                if 0<=si<nframes:pool.append((f,si,raw))
            row['published_mapping_in_clip_raw_frames']=len(pool)
            selected=[pool[round(f*(len(pool)-1))] for f in (.1,.5,.9)];lookup=extract(clip,[p[1] for p in selected],D/'sd'/rec)
            for f,si,raw in selected:
                lab=native/'labels'/f'{f:04d}.json';box=read(lab) if lab.is_file() else None;b=[box[k] for k in ('x_min','y_min','x_max','y_max')] if box else None
                pp.append(dict(recording=rec,frame=f,camera_source=str(lookup[si]),sonar_source=str(raw),camera_boxes=[b] if b else [],sonar_box=None,sd_index=si,mapping='published_SD_FrameTime_onset_fps_offset_NOT_sync_certificate',original_label=str(lab) if box else None))
        else:
            for f in (.1,.5,.9):
                raw=raws[round(f*(len(raws)-1))];pp.append(dict(recording=rec,frame=int(raw.stem),camera_source=None,sonar_source=str(raw),camera_boxes=[],sonar_box=None,sd_index=None,mapping='no_published_camera_match',original_label=None))
        assert len(pp)==3
        ri=len(sheet_records)%4
        if ri==0:canvas=Image.new('RGB',(1920,2400),'#f4f6fa');draw=ImageDraw.Draw(canvas)
        oy=ri*600;draw.text((4,oy+3),rec+' | '+m['category_dir']+' | '+('CURRENT' if rec in current else 'NEW SOURCE AUDIT')+' | 3 fixed pilots, NOT whole recording GT review',font=font,fill='black')
        for j,p in enumerate(pp):
            ox=j*640;draw.text((ox+4,oy+27),f'ARIS {p["frame"]}, SD {p["sd_index"]}; published mapping',font=font,fill='black')
            if p['camera_source']:
                im=Image.open(p['camera_source']).convert('RGB');assert im.size==(640,360)
                for b in p['camera_boxes']:ImageDraw.Draw(im).rectangle(b,outline='#00ff40' if b[3]<=360 and b[2]<=640 else '#ff3030',width=2)
                canvas.paste(im,(ox,oy+50));p['camera_sha256']=sha(p['camera_source'])
            else:
                draw.rectangle((ox,oy+50,ox+639,oy+409),fill='#253047');draw.text((ox+20,oy+180),'NO PUBLISHED CAMERA MATCH',font=font,fill='white')
            a=raw_array(p['sonar_source']);s=Image.fromarray(np.clip(a.astype(float)*2.5,0,255).astype(np.uint8)).convert('RGB');b=p['sonar_box']
            if b:ImageDraw.Draw(s).rectangle(b,outline='#00ff40',width=1)
            canvas.paste(s.resize((128,180)),(ox,oy+415))
            # Existing accepted box crop; no guessed new target localization.
            crop=s.crop((0,max(0,b[1]-20),128,min(s.height,b[3]+20))) if b else s
            canvas.paste(crop.resize((500,180)),(ox+134,oy+415));p['sonar_sha256']=sha(p['sonar_source']);p['raw_size']=list(s.size);p['original_label_sha256']=sha(p['original_label']) if p['original_label'] else None
        sheet=f'sheets/page-{len(sheet_records)//4:02d}.jpg';row.update(sampled_frames=[p['frame'] for p in pp],pilot_sheet=sheet,audit_scope='three_fixed_dual_pilots' if row['camera_clip_exists'] else 'three_fixed_sonar_only_pilots')
        for p in pp:p['sheet']=sheet
        sheet_records.append(rec);rows.append(row);pilots.extend(pp)
        if ri==3:canvas.save(D/sheet,quality=94)
        print('record',rec,flush=True)
    if len(sheet_records)%4:canvas.save(D/sheet,quality=94)
    used={Path(r['gopro_file']).name for r in matches.values() if r['gopro_file']};videos=[]
    for clip in sorted((DATA/'data_processed/gopro/clips_sd').glob('*.mp4')):
        if clip.name in used:continue
        pr=probe(clip);n=int(pr['nb_frames']);indices=[round(f*(n-1)) for f in (.05,.25,.5,.75,.95)];lookup=extract(clip,indices,D/'unassigned'/clip.stem);im=Image.new('RGB',(1920,245),'#f4f6fa');draw=ImageDraw.Draw(im);draw.text((4,2),clip.name+f' duration={pr["duration"]:.2f}s | UNASSIGNED, correspondence unknown',font=font,fill='black')
        for j,i in enumerate(indices):im.paste(Image.open(lookup[i]).resize((384,216)),(j*384,27))
        sheet=D/'unassigned'/f'{clip.stem}.jpg';im.save(sheet,quality=95);videos.append(dict(clip=str(clip),name=clip.name,probe=pr,indices=indices,sheet=str(sheet.relative_to(D)),sheet_sha256=sha(sheet),viewed=False,other_resolutions={sub:str(DATA/'data_processed/gopro'/sub/clip.name) for sub in ('clips_fhd','clips_uhd') if (DATA/'data_processed/gopro'/sub/clip.name).exists()}))
    assert len(rows)==94 and len(sheet_records)==84 and len(pilots)==252
    save(D/'inventory.json',rows);csvout(D/'inventory.csv',rows);save(D/'pilots.json',pilots);save(D/'unassigned-clips.json',videos);save(D/'inputs.json',fixed);save(D/'sheet-sha256.json',{str(p.relative_to(D)):sha(p) for p in (D/'sheets').glob('*.jpg')})
    assert all(sha(p)==v for p,v in fixed.items())
    (D/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>All94 audit</title><style>body{font:16px sans-serif;max-width:1500px;margin:auto}img{width:100%}pre{white-space:pre-wrap}</style><h1>94 metadata; 84 fixed recording pilots; original10test closed</h1><p>Prepared pilots are not yet acceptance. See decisions.json for actual viewing and conclusions.</p>'+''.join('<h2>'+p.name+'</h2><img loading="lazy" src="'+str(p.relative_to(D)).replace('\\','/')+'">' for p in sorted((D/'sheets').glob('*.jpg')))+'<h1>Unassigned camera clips</h1>'+''.join('<h2>'+v['name']+'</h2><img loading="lazy" src="'+v['sheet'].replace('\\','/')+'">' for v in videos),encoding='utf-8')
    print(dict(metadata=94,pilot_recordings=84,pilots=252,unassigned=len(videos)),flush=True)
if __name__=='__main__':main()
