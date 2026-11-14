"""Build a reversible two-recording camera candidate; sources and GT stay read-only."""
from pathlib import Path
from fractions import Fraction
from collections import Counter
import csv
import hashlib
import html
import json
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'DataSet/camera_temporal_pilot_rebuilt'
SOURCE = Path(r'D:\pby\data_processed')
RECS = ['2023-09-21_101622', '2023-09-21_103140']
FONT = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 17)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=True, indent=2), encoding='utf-8')


def run(args, tag):
    p = subprocess.run(args, capture_output=True)
    (OUT / 'logs' / (tag+'.stderr')).write_bytes(p.stderr)
    if p.returncode:
        raise RuntimeError(tag + ': ' + p.stderr.decode(errors='replace')[-1000:])
    return p.stdout


def video(path, tag):
    data = json.loads(run(['ffprobe','-v','error','-select_streams','v:0',
        '-show_streams','-show_frames','-show_entries',
        'stream=width,height,avg_frame_rate,nb_frames,start_time:frame=best_effort_timestamp_time',
        '-of','json',str(path)], tag+'-probe'))
    save(OUT/'logs'/(tag+'-probe.json'), data)
    stream = data['streams'][0]
    pts = np.array([float(r['best_effort_timestamp_time']) for r in data['frames']])
    raw = run(['ffmpeg','-hide_banner','-loglevel','error','-threads','2','-i',str(path),
        '-vf','scale=160:90','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','gray','pipe:1'],tag+'-decode')
    gray = np.frombuffer(raw,np.uint8).reshape((-1,14400)).astype(np.float32)
    assert len(pts)==len(gray)==int(stream['nb_frames'])
    assert np.all(np.diff(pts)>0)
    gray -= gray.mean(axis=1)[:,None]
    return stream,pts,gray


def extract(path, indices, folder, tag):
    folder.mkdir(parents=True)
    indices=sorted(set(indices))
    if not indices:
        return {}
    # Keep evaluator recursion shallow for hundreds of selected frame indices.
    def balanced(terms):
        if len(terms)==1:
            return terms[0]
        middle=len(terms)//2
        return '('+balanced(terms[:middle])+'+'+balanced(terms[middle:])+')'
    expression=balanced([f'eq(n,{i})' for i in indices]).replace(',',r'\,')
    run(['ffmpeg','-hide_banner','-loglevel','error','-threads','2','-i',str(path),
         '-vf','select='+expression,'-fps_mode','passthrough','-q:v','2',
         '-start_number','0',str(folder/'%06d.jpg')],tag+'-extract')
    files=sorted(folder.glob('*.jpg'))
    assert len(files)==len(indices),(tag,len(files),len(indices))
    return dict(zip(indices,files))


def query_image(path):
    with Image.open(path) as im:
        q=np.array(im.convert('L').resize((160,90),Image.Resampling.BICUBIC),np.float32).reshape(-1)
    return q-q.mean()


def comparison(item):
    names=[('Published JPG / original GT',Path(item['original_image'])),
           ('Rebuilt FHD / unchanged GT',OUT/item['image'] if item.get('image') else None),
           ('Reference SD / original GT',OUT/item['reference_sd'] if item.get('reference_sd') else None)]
    canvas=Image.new('RGB',(1440,340),'#101821')
    for k,(title,path) in enumerate(names):
        x=k*480
        draw=ImageDraw.Draw(canvas)
        draw.text((x+7,5),title,font=FONT,fill='white')
        if path:
            with Image.open(path) as im:
                im=im.convert('RGB');w,h=im.size
                im=im.resize((480,270),Image.Resampling.LANCZOS)
            d=ImageDraw.Draw(im)
            for bx,by,bw,bh in item['boxes_fhd_xywh']:
                d.rectangle((bx/4,by/4,(bx+bw)/4,(by+bh)/4),outline='#ffcb3b',width=2)
            canvas.paste(im,(x,31))
        else:
            draw.text((x+10,125),'NO RELIABLE COVERAGE / PENDING',font=FONT,fill='#ffad7a')
    draw=ImageDraw.Draw(canvas)
    draw.text((8,309),f"{item['sample']} | {item['status']} | SD {item.get('sd_index')} -> FHD {item.get('fhd_index')}",font=FONT,fill='#ffda70')
    path=OUT/'comparisons'/(item['sample']+'.jpg')
    canvas.save(path,quality=88)
    return str(path.relative_to(OUT)).replace('\\','/')


def main():
    if OUT.exists():
        raise FileExistsError('Output exists; preserve it and use a separately named run.')
    (OUT/'logs').mkdir(parents=True)
    (OUT/'comparisons').mkdir()
    gallery_path=ROOT/'DataSet/camera_annotation_review/manifest.json'
    gallery=json.loads(gallery_path.read_text(encoding='utf-8'))
    assert set(RECS)<=set(gallery['provenance']['approved_recordings'])
    items=[x for x in gallery['items'] if x['dataset']=='native' and x['recording'] in RECS]
    paired={x['sample']:x for x in gallery['items'] if x['dataset']=='paired' and x['recording'] in RECS}
    assert len(items)==1482 and len(paired)==268
    with (SOURCE/'matches.csv').open(encoding='utf-8',newline='') as f:
        matches={r['aris_file'].split('/')[-1]:r for r in csv.DictReader(f) if r['aris_file'].split('/')[-1] in RECS}
    fixed_inputs=[gallery_path,SOURCE/'matches.csv']
    for rec in RECS:
        clip=Path(matches[rec]['gopro_file']).name
        fixed_inputs += [SOURCE/'aris'/rec/(rec+'_frames.csv')]
        fixed_inputs += [SOURCE/'gopro'/f'clips_{res}'/clip for res in ['sd','fhd']]
    fixed_before={str(p):digest(p) for p in fixed_inputs}
    rows=[];summaries=[]
    save(OUT/'progress.json',{'status':'running','done_recordings':0})
    for rec in RECS:
        match=matches[rec];clip=Path(match['gopro_file']).name
        sdpath=SOURCE/'gopro/clips_sd'/clip;fhpath=SOURCE/'gopro/clips_fhd'/clip
        ss,sp,sg=video(sdpath,rec+'-sd');fs,fp,fg=video(fhpath,rec+'-fhd')
        assert ss['avg_frame_rate']==fs['avg_frame_rate']
        fps=float(Fraction(ss['avg_frame_rate']));period=1/fps
        with (SOURCE/'aris'/rec/(rec+'_frames.csv')).open(encoding='utf-8',newline='') as f:
            timestamps={int(r['FrameIndex']):int(r['FrameTime']) for r in csv.DictReader(f)}
        origin=timestamps[int(match['aris_onset'])]
        selected=[]
        for item in sorted([x for x in items if x['recording']==rec],key=lambda x:x['frame']):
            lab=Path(item['annotation_source']);src=Path(item['source'])
            label_bytes=lab.read_bytes();label=json.loads(label_bytes)
            h=hashlib.sha256(label_bytes).hexdigest()
            assert h==item['annotation_sha256']
            box=[[label['x_min']*3,label['y_min']*3,(label['x_max']-label['x_min'])*3,(label['y_max']-label['y_min'])*3]]
            assert box==item['boxes'] and label['class']==item['category']
            i=int((timestamps[item['frame']]-origin)/1e6*fps)+int(match['gopro_offset'])
            r={'sample':item['sample'],'recording':rec,'aris_frame':item['frame'],
               'aris_time_us':timestamps[item['frame']],'aris_onset_time_us':origin,
               'original_image':str(src),'original_image_sha256_before':digest(src),
               'original_label':str(lab),'original_label_sha256_before':h,
               'boxes_fhd_xywh':box,'category':label['class'],
               'paired_id':paired.get(item['sample'],{}).get('id'),
               'paired_role':paired.get(item['sample'],{}).get('split'),
               'sd_index':i,'status':'pending'}
            if not (0<=i<len(sp)):
                r['status']='sd_reference_missing'
            else:
                t=float(sp[i]);j=int(np.argmin(np.abs(fp-t)))
                residual=float(abs(fp[j]-t));r.update(sd_pts=t,fhd_index=j,fhd_pts=float(fp[j]),time_residual_s=residual)
                if t<fp[0]-period/2 or t>fp[-1]+period/2:
                    r['status']='fhd_coverage_missing'
                elif residual>period/2:
                    r['status']='time_pending'
                elif not (0<=i<len(fg)):
                    r['status']='old_export_index_missing'
                else:
                    q=query_image(src)
                    lineage=float(np.mean((q-fg[i])**2))
                    aligned=float(np.mean((sg[i]-fg[j])**2))
                    old=float(np.mean((sg[i]-fg[i])**2))
                    r.update(old_jpg_predicted_index_mse=lineage,sd_to_rebuilt_mse=aligned,sd_to_old_mse=old,
                             metadata_delta_frames=round((float(fs['start_time'])-float(ss['start_time']))*fps))
                    assert i-j==r['metadata_delta_frames']
                    r['status']='candidate' if lineage<=4 and aligned<=9 else ('lineage_pending' if lineage>4 else 'content_pending')
            selected.append(r)
        sdimgs=extract(sdpath,[r['sd_index'] for r in selected if 0<=r['sd_index']<len(sp)],OUT/'reference_sd'/rec,rec+'-sd')
        fimgs=extract(fhpath,[r['fhd_index'] for r in selected if r['status']=='candidate'],OUT/'decoded_fhd'/rec,rec+'-fhd')
        (OUT/'images'/rec).mkdir(parents=True);(OUT/'labels_sd_original'/rec).mkdir(parents=True)
        for r in selected:
            copied=OUT/'labels_sd_original'/rec/(r['sample']+'.json')
            copied.write_bytes(Path(r['original_label']).read_bytes());r['label_copy']=str(copied.relative_to(OUT)).replace('\\','/')
            if r['sd_index'] in sdimgs:
                r['reference_sd']=str(sdimgs[r['sd_index']].relative_to(OUT)).replace('\\','/')
            if r['status']=='candidate':
                image=OUT/'images'/rec/(r['sample']+'.jpg')
                image.write_bytes(fimgs[r['fhd_index']].read_bytes());r['image']=str(image.relative_to(OUT)).replace('\\','/')
                r['image_sha256']=digest(image)
            r['comparison']=comparison(r)
            assert digest(Path(r['original_label']))==r['original_label_sha256_before']
            assert digest(Path(r['original_image']))==r['original_image_sha256_before']
            r['original_inputs_unchanged']=True
        rows+=selected
        summary={'recording':rec,'total':len(selected),'status_counts':dict(Counter(r['status'] for r in selected)),
                 'exact_aris_onset':True,'sd_frames':len(sp),'fhd_frames':len(fp),'fps':fps,
                 'paired_total':sum(bool(r['paired_id']) for r in selected),
                 'paired_candidates':sum(bool(r['paired_id']) and r['status']=='candidate' for r in selected)}
        summaries.append(summary);print(json.dumps(summary),flush=True)
        save(OUT/'progress.json',{'status':'running','done_recordings':len(summaries),'rows_completed':len(rows)})
        del sg,fg
    assert all(digest(Path(k))==v for k,v in fixed_before.items())
    save(OUT/'manifest.json',{'name':'camera_temporal_pilot','status':'candidate_only_not_training_ready',
         'scope':'two approved development recordings; no test; no model inference',
         'label_policy':'original SD JSON byte copies; boxes_fhd_xywh x3 once; no translations or clipping',
         'fixed_inputs_sha256':fixed_before,'fixed_inputs_unchanged':True,'recordings':summaries,'items':rows})
    with (OUT/'correspondence.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['sample','recording','aris_frame','sd_index','sd_pts','fhd_index','fhd_pts','time_residual_s','status',
                'old_jpg_predicted_index_mse','sd_to_rebuilt_mse','sd_to_old_mse','paired_role']
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    cards=[]
    for r in rows:
        cards.append(f'<article data-rec="{r["recording"]}" data-status="{r["status"]}"><a href="{r["comparison"]}"><img loading="lazy" src="{r["comparison"]}"></a><p>{r["sample"]} | {r["status"]}</p></article>')
    page='''<!doctype html><meta charset="utf-8"><title>Camera temporal pilot</title>
<style>body{background:#101821;color:#eee;font:16px system-ui;margin:20px}header{position:sticky;top:0;background:#101821;padding:8px}article{margin:18px 0;border-bottom:1px solid #456}img{width:100%;max-width:1440px}a{color:#8cf}select{font-size:16px}</style>
<header><h2>Camera 时间对应试点：1482个原生样本</h2><p>左：旧图/原框；中：时间对应FHD/原框；右：参考SD/原框。候选副本，框质量仍需人工验收。无FHD覆盖保留状态。</p>
<select id="rec"><option value="">全部录音</option><option>2023-09-21_101622</option><option>2023-09-21_103140</option></select>
<select id="status"><option value="">全部状态</option><option>candidate</option><option>fhd_coverage_missing</option><option>lineage_pending</option><option>content_pending</option><option>sd_reference_missing</option><option>time_pending</option><option>old_export_index_missing</option></select><span id="count"></span></header>'''
    page+=''.join(cards)+'''<script>function filter(){let n=0;for(const x of document.querySelectorAll('article')){let ok=(!rec.value||x.dataset.rec===rec.value)&&(!status.value||x.dataset.status===status.value);x.hidden=!ok;if(ok)n++}count.textContent=' '+n+' samples'}document.getElementById('rec').onchange=filter;document.getElementById('status').onchange=filter;filter()</script>'''
    # Avoid the browser window.status name collision in the standalone page.
    page=page.replace('(!status.value||x.dataset.status===status.value)',"(!document.getElementById('status').value||x.dataset.status===document.getElementById('status').value)")
    (OUT/'index.html').write_text(page,encoding='utf-8')
    save(OUT/'progress.json',{'status':'complete_candidate_export','samples':len(rows),'recordings':summaries})


if __name__=='__main__':
    main()
