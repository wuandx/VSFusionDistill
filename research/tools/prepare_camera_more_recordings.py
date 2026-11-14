"""Prepare extra camera-only recordings using corrected SD timing; never auto-accept."""
import csv
from collections import Counter
from fractions import Fraction
import hashlib
import html
import json
from pathlib import Path
import shutil
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).parent/'_sonar_audit_deps'))
from PIL import Image, ImageDraw, ImageFont
from expand_paired_recording_pool import nominal

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'DataSet/camera_more_recordings_candidate'
CAM=ROOT/'DataSet/camera_temporal_all'
DATA=Path('D:/pby')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def run(cmd):
    r=subprocess.run(cmd,capture_output=True)
    if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace')[-1500:])
    return r.stdout
def take(xs,n=100):return [xs[round(i*(len(xs)-1)/(min(n,len(xs))-1))] for i in range(min(n,len(xs)))] if len(xs)>1 else xs

def main():
    OUT.mkdir(exist_ok=False)
    inv=read(ROOT/'DataSet/recording_expansion_94_audit/inventory.json')
    temporal=read(CAM/'manifest-resolved.json')['items']
    matches={Path(r['aris_file']).name:r for r in csv.DictReader((DATA/'data_processed/matches.csv').open(encoding='utf-8-sig'))}
    current=list(csv.DictReader((ROOT/'DataSet/scene_stratified_mortar_recovered_candidate/recordings.csv').open(encoding='utf-8-sig')))
    legacy=read(DATA/'uxo-full/split_manifest.json')['recordings']
    # Freeze existing conservative groups; add exact shared-source edges across all metadata.
    parent={rec:rec for rec in matches}
    def find(a):
        while parent[a]!=a:a=parent[a]
        return a
    def union(a,b):
        a,b=find(a),find(b)
        parent[max(a,b)]=min(a,b)
    for a in current:
        for b in current:
            if a['group_id']==b['group_id']:union(a['recording'],b['recording'])
    for key in ['gopro_file','gantry_file']:
        seen={}
        for rec,m in matches.items():
            if m[key]:
                if m[key] in seen:union(rec,seen[m[key]])
                seen[m[key]]=rec
    blocked={find(r['recording']) for r in current if r['role']!='train'}|{find(rec) for rec,r in legacy.items() if r['split']=='test'}
    summaries=[];rows=[];skipped=[];font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)
    for meta in inv:
        if meta['state']!='extra_existing_labels_camera_review':continue
        rec=meta['recording'];assert legacy[rec]['split']!='test'
        assert find(rec) not in blocked, rec
        folder=OUT/rec;folder.mkdir();mapped=[];reasons=Counter()
        tr=[r for r in temporal if r['recording']==rec]
        if tr:
            for t in tr:
                lab=CAM/t['label_copy'];assert sha(lab)==t['original_label_sha256_before']
                a=read(lab);box=[a[k] for k in ['x_min','y_min','x_max','y_max']]
                if not (0<=box[0]<box[2]<=640 and 0<=box[1]<box[3]<=360):reasons['bbox_out_of_bounds']+=1;continue
                if not t.get('reference_sd'):reasons['missing_sd']+=1;continue
                mapped.append(dict(sample=t['sample'],recording=rec,frame=t['aris_frame'],sd_index=t['sd_index'],source=str(CAM/t['reference_sd']),label_source=str(lab),box=box,category=a['class'],temporal_source='camera_temporal_all:reference_sd'))
        else:
            # Same published SD mapping used by the existing pilot; expand beyond its 12 frames.
            native=DATA/'uxo-full/extracted/recordings'/meta['category_dir']/rec
            clip=Path(meta['matched_sd_clip']);m=matches[rec]
            probe=json.loads(run(['ffprobe','-v','error','-select_streams','v:0','-show_streams','-of','json',str(clip)]))['streams'][0]
            assert (probe['width'],probe['height'])==(640,360)
            fps=float(Fraction(probe['avg_frame_rate']));count=int(probe['nb_frames'])
            aris=DATA/'data_processed/aris'/rec/(rec+'_frames.csv')
            md={int(x['FrameIndex']):x for x in csv.DictReader(aris.open(encoding='utf-8-sig'))}
            onset=int(md[int(m['aris_onset'])]['FrameTime'])
            for lab in sorted((native/'labels').glob('*.json'),key=lambda p:int(p.stem)):
                frame=int(lab.stem);a=read(lab);box=[a[k] for k in ['x_min','y_min','x_max','y_max']]
                si=int((int(md[frame]['FrameTime'])-onset)/1e6*fps)+int(m['gopro_offset'])
                if not (0<=box[0]<box[2]<=640 and 0<=box[1]<box[3]<=360):reasons['bbox_out_of_bounds']+=1;continue
                if not 0<=si<count:reasons['sd_outside_clip']+=1;continue
                mapped.append(dict(sample=f'{rec}_{frame:04d}',recording=rec,frame=frame,sd_index=si,source=None,label_source=str(lab),box=box,category=a['class'],temporal_source='FrameTime/onset/fps+gopro_offset',clip=str(clip)))
            save(folder/'temporal-inputs.json',dict(clip=str(clip),clip_sha256=sha(clip),metadata_sha256=sha(aris),match=m,fps=probe['avg_frame_rate']))
        unique={}
        for r in sorted(mapped,key=lambda r:r['frame']):unique.setdefault(r['sd_index'],r)
        selected=take(list(unique.values()))
        if selected and selected[0]['source'] is None:
            sd=folder/'sd';sd.mkdir();ids=sorted(r['sd_index'] for r in selected)
            expr='+'.join(f'eq(n\\,{i})' for i in ids)
            run(['ffmpeg','-hide_banner','-loglevel','error','-threads','2','-i',selected[0]['clip'],'-vf','select='+expr,'-fps_mode','passthrough','-q:v','2','-start_number','0',str(sd/'%04d.jpg')])
            files=sorted(sd.glob('*.jpg'));assert len(files)==len(ids)
            paths=dict(zip(ids,files))
            for r in selected:r['source']=str(paths[r['sd_index']])
        n=nominal(meta['notes']);sheets=[]
        for i,r in enumerate(selected):
            assert r['category']==meta['category'];r.update(ordinal=i,group_id=find(rec),scene_id='|'.join([r['category'],n['placement'],n['trajectory']]),nominal=n,role='train_candidate',decision='unreviewed',precision_sync_certified=False,expert_verified=False)
            src=Path(r['source']);im=Image.open(src).convert('RGB');assert im.size==(640,360)
            r['source_sha256']=sha(src);r['label_sha256']=sha(r['label_source'])
            dest=folder/(r['sample']+'.jpg')
            shutil.copyfile(src,dest);assert sha(dest)==r['source_sha256'];r['image']=str(dest.relative_to(OUT))
            if i%25==0:
                canvas=Image.new('RGB',(1600,1070),'#f4f6fa');d=ImageDraw.Draw(canvas)
                d.text((5,3),rec+' | corrected SD + unchanged GT | camera-only proposed',font=font,fill='black')
            x=(i%25%5)*320;y=25+(i%25//5)*208
            ImageDraw.Draw(im).rectangle(r['box'],outline='#00ff40',width=3)
            canvas.paste(im.resize((320,180)),(x,y+20));d.text((x+2,y),f'{i} ARIS {r["frame"]} SD {r["sd_index"]}',font=font,fill='black')
            if i%25==24 or i==len(selected)-1:
                p=folder/f'page-{i//25:02d}.jpg';canvas.save(p,quality=95);sheets.append(dict(path=str(p.relative_to(OUT)),sha256=sha(p)))
            rows.append(r)
        summaries.append(dict(recording=rec,category=meta['category'],nominal=n,group_id=find(rec),eligible_sd=len(mapped),unique_sd=len(unique),proposed=len(selected),excluded_reasons=dict(reasons),sheets=sheets,decision='pending_camera_visual_review' if selected else 'no_valid_unmodified_box'))
        save(folder/'manifest.json',selected)
    save(OUT/'manifest.json',rows);save(OUT/'recordings.json',summaries)
    save(OUT/'groups.json',dict(groups={rec:find(rec) for rec in matches},rule='existing conservative groups + exact nonempty gopro_file/gantry_file connected components',candidate_heldout_connections=0,source_identity_limit='Does not certify all physical capture independence beyond recorded source identifiers.'))
    save(OUT/'summary.json',dict(status='candidate_pending_visual_review',proposed_images=len(rows),extra_recordings=sum(r['proposed']>0 for r in summaries),original_train_images=2472,original_train_recordings=21,potential_train_images=2472+len(rows),potential_train_recordings=21+sum(r['proposed']>0 for r in summaries),val_images=894,test_members_unchanged=True,training=False,source_labels_modified=False,unlabelled_extra_recordings=4,records=summaries))
    blocks=[]
    for r in summaries:
        blocks.append(f'<h2>{r["recording"]} — {r["proposed"]} candidates</h2><p>{html.escape(str(r["nominal"]))}</p>'+''.join(f'<img loading="lazy" style="max-width:100%" src="{s["path"]}">' for s in r['sheets']))
    (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Extra camera-only recordings</title><h1>Corrected SD camera-only candidates; not automatically accepted</h1>'+''.join(blocks),encoding='utf-8')
    print(json.dumps(dict(proposed=len(rows),recordings=sum(r['proposed']>0 for r in summaries),pages=sum(len(r['sheets']) for r in summaries),per_recording=[(r['recording'],r['proposed']) for r in summaries])))

if __name__=='__main__':main()
