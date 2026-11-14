"""Rebuild all explicitly approved development recordings, without touching originals."""
from pathlib import Path
from fractions import Fraction
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import hashlib
import json
import os
import subprocess
import time
import traceback
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'DataSet/camera_temporal_all'
SOURCE=Path(r'D:\pby\data_processed')
GALLERY=ROOT/'DataSet/camera_annotation_review/manifest.json'


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):
            h.update(b)
    return h.hexdigest()


def save(path,data):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(data,ensure_ascii=True,indent=2),encoding='utf-8')
    temporary.replace(path)


def run(args,folder,tag):
    p=subprocess.run(args,capture_output=True)
    (folder/'logs'/(tag+'.stderr')).write_bytes(p.stderr)
    if p.returncode:
        raise RuntimeError(tag+': '+p.stderr.decode(errors='replace')[-1600:])
    return p.stdout


def video(path,folder,res):
    data=json.loads(run(['ffprobe','-v','error','-select_streams','v:0','-show_streams',
        '-show_frames','-show_entries','stream=width,height,avg_frame_rate,nb_frames,start_time:frame=best_effort_timestamp_time',
        '-of','json',str(path)],folder,res+'-probe'))
    save(folder/'logs'/(res+'-probe.json'),data)
    s=data['streams'][0]
    pts=np.array([float(x['best_effort_timestamp_time']) for x in data['frames']])
    raw=run(['ffmpeg','-hide_banner','-loglevel','error','-threads','2','-i',str(path),
        '-vf','scale=160:90','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','gray','pipe:1'],folder,res+'-decode')
    a=np.frombuffer(raw,np.uint8).reshape((-1,14400)).astype(np.float32)
    assert len(pts)==len(a)==int(s['nb_frames'])
    assert np.all(np.diff(pts)>0)
    a-=a.mean(axis=1)[:,None]
    return s,pts,a


def extract(path,indices,dest,folder,res):
    dest.mkdir()
    indices=sorted(set(indices))
    if not indices:return {}
    def balanced(terms):
        if len(terms)==1:return terms[0]
        k=len(terms)//2
        return '('+balanced(terms[:k])+'+'+balanced(terms[k:])+')'
    expression=balanced([f'eq(n,{i})' for i in indices]).replace(',',r'\,')
    (folder/'logs'/(res+'-select.txt')).write_text(expression,encoding='ascii')
    # The expression is balanced to avoid the evaluator recursion limit.
    command=['ffmpeg','-hide_banner','-loglevel','error','-threads','2','-i',str(path),
        '-vf','select='+expression,'-fps_mode','passthrough','-q:v','2','-start_number','0',str(dest/'%06d.jpg')]
    run(command,folder,res+'-extract')
    files=sorted(dest.glob('*.jpg'))
    assert len(files)==len(indices),(res,len(files),len(indices))
    return dict(zip(indices,files))


def gray_query(path):
    with Image.open(path) as im:
        a=np.array(im.convert('L').resize((160,90),Image.Resampling.BICUBIC),np.float32).reshape(-1)
    return a-a.mean()


def relative(path):return str(path.relative_to(OUT)).replace('\\','/')


def compare(r,folder,font):
    choices=[('Published JPG / original GT',Path(r['original_image'])),
        ('Rebuilt FHD / unchanged GT',OUT/r['image'] if r.get('image') else None),
        ('Reference SD / original GT',OUT/r['reference_sd'] if r.get('reference_sd') else None)]
    canvas=Image.new('RGB',(1440,340),'#101821')
    for k,(title,path) in enumerate(choices):
        x=k*480;d=ImageDraw.Draw(canvas);d.text((x+6,5),title,font=font,fill='white')
        if path:
            with Image.open(path) as im:
                im=im.convert('RGB').resize((480,270),Image.Resampling.LANCZOS)
            dd=ImageDraw.Draw(im)
            for bx,by,bw,bh in r['boxes_fhd_xywh']:
                dd.rectangle((bx/4,by/4,(bx+bw)/4,(by+bh)/4),outline='#ffcb3b',width=2)
            canvas.paste(im,(x,31))
        else:d.text((x+10,125),'NO RELIABLE COVERAGE / PENDING',font=font,fill='#ffad7a')
    d=ImageDraw.Draw(canvas)
    d.text((8,309),f"{r['sample']} | {r['status']} | SD {r['sd_index']} -> FHD {r.get('fhd_index')}",font=font,fill='#ffda70')
    path=folder/'comparisons'/(r['sample']+'.jpg');canvas.save(path,quality=88)
    return relative(path)


def process(rec,items,paired,match):
    recroot=OUT/'recordings'/rec;recroot.mkdir(parents=True,exist_ok=True)
    ready=recroot/'manifest.json'
    if ready.exists():
        existing=json.loads(ready.read_text(encoding='utf-8'))
        assert {r['sample'] for r in existing['items']}=={i['sample'] for i in items}
        assert all(digest(Path(k))==v for k,v in existing['fixed_inputs_sha256'].items())
        return existing
    attempt=recroot/f'attempt_{len(list(recroot.glob("attempt_*")))+1}'
    attempt.mkdir();(attempt/'logs').mkdir();(attempt/'comparisons').mkdir()
    (attempt/'images').mkdir();(attempt/'labels_sd_original').mkdir()
    started=time.time();font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',17)
    try:
        clip=Path(match['gopro_file']).name
        sdpath=SOURCE/'gopro/clips_sd'/clip;fhpath=SOURCE/'gopro/clips_fhd'/clip
        arispath=SOURCE/'aris'/rec/(rec+'_frames.csv')
        fixed={str(p):digest(p) for p in [sdpath,fhpath,arispath]}
        save(attempt/'fixed-inputs-before.json',fixed)
        ss,sp,sg=video(sdpath,attempt,'sd');fs,fp,fg=video(fhpath,attempt,'fhd')
        assert ss['avg_frame_rate']==fs['avg_frame_rate']
        assert (ss['width'],ss['height'])==(640,360) and (fs['width'],fs['height'])==(1920,1080)
        fps=float(Fraction(ss['avg_frame_rate']));period=1/fps
        with arispath.open(encoding='utf-8',newline='') as f:aris=list(csv.DictReader(f))
        assert all(int(r['FrameIndex'])==i for i,r in enumerate(aris))
        timestamps={int(r['FrameIndex']):int(r['FrameTime']) for r in aris}
        origin=timestamps[int(match['aris_onset'])]
        delta=round((float(fs['start_time'])-float(ss['start_time']))*fps)
        rows=[]
        for item in sorted(items,key=lambda x:x['frame']):
            lab=Path(item['annotation_source']);src=Path(item['source'])
            blob=lab.read_bytes();label=json.loads(blob);h=hashlib.sha256(blob).hexdigest()
            assert h==item['annotation_sha256']
            boxes=[[label['x_min']*3,label['y_min']*3,(label['x_max']-label['x_min'])*3,(label['y_max']-label['y_min'])*3]]
            assert boxes==item['boxes'] and label['class']==item['category']
            pair=paired.get(item['sample'])
            if pair:assert pair['boxes']==boxes and pair['split'] in ['train','val','val_id']
            original_sha=digest(src)
            i=int((timestamps[item['frame']]-origin)/1e6*fps)+int(match['gopro_offset'])
            r={'sample':item['sample'],'recording':rec,'aris_frame':item['frame'],
                'aris_time_us':timestamps[item['frame']],'aris_onset_time_us':origin,
                'original_image':str(src),'original_image_sha256_before':original_sha,
                'original_label':str(lab),'original_label_sha256_before':h,
                'boxes_fhd_xywh':boxes,'category':label['class'],'sd_index':i,'metadata_delta_frames':delta,
                'paired_id':pair['id'] if pair else None,'paired_role':pair['split'] if pair else None,
                'status':'pending'}
            if pair:
                r['paired_original_image']=pair['source'];r['paired_original_image_sha256_before']=digest(Path(pair['source']))
                r['paired_image_matches_native']=r['paired_original_image_sha256_before']==original_sha
            if not 0<=i<len(sp):r['status']='sd_reference_missing'
            else:
                t=float(sp[i]);j=int(np.argmin(np.abs(fp-t)));residual=float(abs(fp[j]-t))
                r.update(sd_pts=t,fhd_index=j,fhd_pts=float(fp[j]),time_residual_s=residual)
                if t<fp[0]-period/2 or t>fp[-1]+period/2:r['status']='fhd_coverage_missing'
                elif residual>period/2 or i-j!=delta:r['status']='time_pending'
                elif not 0<=i<len(fg):r['status']='old_export_index_missing'
                else:
                    lineage=float(np.mean((gray_query(src)-fg[i])**2))
                    aligned=float(np.mean((sg[i]-fg[j])**2));old=float(np.mean((sg[i]-fg[i])**2))
                    r.update(old_jpg_predicted_index_mse=lineage,sd_to_rebuilt_mse=aligned,sd_to_old_mse=old)
                    r['status']='candidate' if lineage<=4 and aligned<=9 else ('lineage_pending' if lineage>4 else 'content_pending')
            rows.append(r)
        save(attempt/'rows-before-export.json',rows)
        sdimgs=extract(sdpath,[r['sd_index'] for r in rows if 0<=r['sd_index']<len(sp)],attempt/'reference_sd',attempt,'sd')
        fimgs=extract(fhpath,[r['fhd_index'] for r in rows if r['status']=='candidate'],attempt/'decoded_fhd',attempt,'fhd')
        for n,r in enumerate(rows,1):
            label_copy=attempt/'labels_sd_original'/(r['sample']+'.json')
            label_copy.write_bytes(Path(r['original_label']).read_bytes());r['label_copy']=relative(label_copy)
            if r['sd_index'] in sdimgs:r['reference_sd']=relative(sdimgs[r['sd_index']])
            if r['status']=='candidate':
                image=attempt/'images'/(r['sample']+'.jpg')
                os.link(fimgs[r['fhd_index']],image)
                r['image']=relative(image);r['image_sha256']=digest(image)
            r['comparison']=compare(r,attempt,font)
            assert digest(Path(r['original_label']))==r['original_label_sha256_before']
            assert digest(Path(r['original_image']))==r['original_image_sha256_before']
            if r['paired_id']:assert digest(Path(r['paired_original_image']))==r['paired_original_image_sha256_before']
            r['original_inputs_unchanged']=True
            if n%200==0:save(attempt/'progress.json',{'status':'rendering','done':n,'total':len(rows)})
        assert all(digest(Path(k))==v for k,v in fixed.items())
        good=[r for r in rows if r['status']=='candidate']
        summary={'recording':rec,'total':len(rows),'status_counts':dict(Counter(r['status'] for r in rows)),
            'category':rows[0]['category'],'exact_aris_onset':True,'FrameIndex_equals_row_number':True,
            'sd_frames':len(sp),'fhd_frames':len(fp),'fps_fraction':ss['avg_frame_rate'],'fps':fps,
            'metadata_delta_frames':delta,'paired_total':sum(bool(r['paired_id']) for r in rows),
            'paired_candidates':sum(bool(r['paired_id']) and r['status']=='candidate' and r.get('paired_image_matches_native') for r in rows),
            'paired_original_image_mismatches':sum(bool(r['paired_id']) and not r['paired_image_matches_native'] for r in rows),
            'max_time_residual_s':max((r['time_residual_s'] for r in good),default=None),
            'candidate_content_mse_median':float(np.median([r['sd_to_rebuilt_mse'] for r in good])) if good else None,
            'old_content_mse_median_same_candidates':float(np.median([r['sd_to_old_mse'] for r in good])) if good else None,
            'attempt':relative(attempt),'seconds':round(time.time()-started,1)}
        record={'summary':summary,'fixed_inputs_sha256':fixed,'items':rows}
        save(ready,record);save(attempt/'progress.json',{'status':'complete','samples':len(rows)})
        print(json.dumps(summary),flush=True)
        return record
    except Exception:
        error=traceback.format_exc();(attempt/'failure.txt').write_text(error,encoding='utf-8')
        save(attempt/'progress.json',{'status':'failed_preserved','error':error})
        raise


def write_viewer(rows):
    payload=[{k:r.get(k) for k in ['sample','recording','category','status','paired_id','paired_role','comparison','image','sd_index','fhd_index']} for r in rows]
    for item,row in zip(payload,rows):
        item['geometryFlag']=any(x<0 or y<0 or w<=0 or h<=0 or x+w>1920 or y+h>1080 for x,y,w,h in row['boxes_fhd_xywh'])
    page=r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Camera 时间对应全量对照</title>
<style>*{box-sizing:border-box}body{margin:0;background:#101821;color:#e8edf5;font:15px system-ui}header{position:sticky;top:0;background:#172331;padding:14px;z-index:3}h2{margin:0 0 8px}p{margin:7px 0;color:#c1cbd8}select,input,button{font:inherit;background:#283b50;color:white;border:1px solid #64778c;border-radius:4px;padding:7px;margin:3px}button,a{cursor:pointer}a{color:#96cfff}.card{margin:15px auto;padding:8px;max-width:1460px;border-bottom:1px solid #475a6c}.card img{width:100%;display:block}.pager{text-align:center;padding:12px}.modal{display:none;position:fixed;inset:0;background:#0b121b;z-index:10;overflow:auto;padding:12px}.modal.open{display:block}.bar{position:sticky;top:0;background:#172331;padding:8px}.modal img{display:block;width:100%;max-width:1920px;margin:auto}textarea{width:100%;padding:10px;background:#152333;color:white}label{white-space:nowrap}</style>
<header><h2>Camera 时间对应修复 · 40条录音</h2><p>左：旧图/原框；中：时间对应FHD/原框；右：SD参考/原框。候选图已完成时间/内容筛查，原框质量请另行检查；缺覆盖和待核验样本保留显示。</p>
<select id="dataset"><option value="native">全部原生序列</option><option value="paired">当前paired样本</option></select>
<select id="category"><option value="">全部类别</option></select><select id="rec"><option value="">全部录音</option></select><select id="state"><option value="">全部处理状态</option></select><select id="geometry"><option value="">全部框范围</option><option value="flagged">仅框范围需核对</option></select><input id="search" placeholder="输入sample或帧号"><select id="markFilter"><option value="">全部检查标记</option><option value="unseen">未检查</option><option value="good">标记正常</option><option value="bad">标记待复核</option></select><button id="download">导出检查CSV</button><span id="count"></span></header>
<div class="pager"><button onclick="pageBy(-1)">上一页</button><span id="pageInfo"></span><button onclick="pageBy(1)">下一页</button></div><main id="grid"></main><div class="pager"><button onclick="pageBy(-1)">上一页</button><button onclick="pageBy(1)">下一页</button></div>
<div class="modal" id="modal"><div class="bar"><button onclick="closeViewer()">返回</button><button onclick="step(-1)">← 上一张</button><button onclick="step(1)">下一张 →</button><button onclick="mark('good')">G 正常</button><button onclick="mark('bad')">B 待复核</button><button onclick="mark('')">清除标记</button><span id="viewerCount"></span><p id="detail"></p><a id="fullImage" target="_blank">打开无框FHD原尺寸副本</a></div><img id="view"><textarea id="note" placeholder="记录框质量、目标边界等问题"></textarea></div>
<script id="payload" type="application/json">__PAYLOAD__</script><script>
const ITEMS=JSON.parse(document.getElementById('payload').textContent),$=id=>document.getElementById(id),KEY='camera-temporal-all-review';let marks={};try{marks=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}let filtered=[],page=0,current=0;const SIZE=30;
const labels={candidate:'已生成候选图',fhd_coverage_missing:'FHD无时间覆盖',sd_reference_missing:'SD参考缺失',time_pending:'时间对应待核',lineage_pending:'原图来源待核',content_pending:'内容对应待核',old_export_index_missing:'原导出索引缺失'};
function opts(id,values){for(const x of [...new Set(values)].sort()){const o=document.createElement('option');o.value=x;o.textContent=id==='state'?(labels[x]||x):x;$(id).append(o)}}opts('category',ITEMS.map(x=>x.category));opts('rec',ITEMS.map(x=>x.recording));opts('state',ITEMS.map(x=>x.status));
function filter(){const q=$('search').value.trim().toLowerCase(),mf=$('markFilter').value;filtered=ITEMS.filter(x=>($('dataset').value!=='paired'||x.paired_id)&&(!$('category').value||x.category===$('category').value)&&(!$('rec').value||x.recording===$('rec').value)&&(!$('state').value||x.status===$('state').value)&&(!$('geometry').value||x.geometryFlag)&&(!q||x.sample.toLowerCase().includes(q))&&(!mf||(mf==='unseen'?!marks[x.sample]?.status:marks[x.sample]?.status===mf)));page=0;draw()}
function draw(){$('grid').replaceChildren();let start=page*SIZE;for(let i=start;i<Math.min(start+SIZE,filtered.length);i++){const x=filtered[i],a=document.createElement('article');a.className='card';const im=document.createElement('img');im.loading='lazy';im.src=x.comparison;im.onclick=()=>show(i);const t=document.createElement('p');t.textContent=x.sample+' | '+x.category+' | '+(labels[x.status]||x.status)+' | '+(marks[x.sample]?.status||'未检查')+(x.geometryFlag?' | 框范围需核对':'');a.append(im,t);$('grid').append(a)}$('count').textContent=' '+filtered.length+' 个样本';$('pageInfo').textContent=(page+1)+' / '+Math.max(1,Math.ceil(filtered.length/SIZE))}
function pageBy(n){page=Math.max(0,Math.min(Math.ceil(filtered.length/SIZE)-1,page+n));draw();window.scrollTo(0,0)}
function show(i){if(i<0||i>=filtered.length)return;current=i;const x=filtered[i];$('modal').classList.add('open');$('view').src=x.comparison;$('viewerCount').textContent=(i+1)+' / '+filtered.length;$('detail').textContent=x.sample+' | '+(labels[x.status]||x.status)+' | SD '+x.sd_index+' → FHD '+x.fhd_index+' | 标记 '+(marks[x.sample]?.status||'未检查');$('note').value=marks[x.sample]?.note||'';$('fullImage').style.display=x.image?'inline':'none';$('fullImage').href=x.image||'#'}
function step(n){show(current+n)}function closeViewer(){$('modal').classList.remove('open');draw()}function persist(){localStorage.setItem(KEY,JSON.stringify(marks))}function mark(s){const x=filtered[current];marks[x.sample]={status:s,note:$('note').value};persist();show(current)}$('note').onchange=()=>{const x=filtered[current];marks[x.sample]={status:marks[x.sample]?.status||'',note:$('note').value};persist()};
function cell(x){return '"'+String(x??'').replaceAll('"','""')+'"'}$('download').onclick=()=>{const lines=[['sample','category','recording','processing_status','review_status','note']];for(const x of ITEMS){const m=marks[x.sample];if(m&&(m.status||m.note))lines.push([x.sample,x.category,x.recording,x.status,m.status,m.note])}const b=new Blob(['\ufeff'+lines.map(r=>r.map(cell).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}),a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='camera-temporal-all-review.csv';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)};
for(const id of ['dataset','category','rec','state','geometry','markFilter'])$(id).onchange=filter;$('search').oninput=filter;document.addEventListener('keydown',e=>{if(['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)||!$('modal').classList.contains('open'))return;if(e.key==='ArrowRight')step(1);if(e.key==='ArrowLeft')step(-1);if(e.key==='Escape')closeViewer();if(e.key.toLowerCase()==='g')mark('good');if(e.key.toLowerCase()==='b')mark('bad')});filter();
</script></html>'''
    page=page.replace('__PAYLOAD__',json.dumps(payload,ensure_ascii=True).replace('</','<\\/'))
    (OUT/'index.html').write_text(page,encoding='utf-8')


def main():
    OUT.mkdir(exist_ok=True)
    gallery=json.loads(GALLERY.read_text(encoding='utf-8'))
    recs=sorted(gallery['provenance']['approved_recordings'])
    items=[x for x in gallery['items'] if x['dataset']=='native' and x['recording'] in recs]
    paired={x['sample']:x for x in gallery['items'] if x['dataset']=='paired' and x['recording'] in recs}
    assert len(recs)==40 and len(items)==26761 and len(paired)==4746
    assert len({x['sample'] for x in items})==26761 and set(paired)<={x['sample'] for x in items}
    assert all(x['split'] in ['train','val','val_id'] for x in paired.values())
    with (SOURCE/'matches.csv').open(encoding='utf-8',newline='') as f:
        matches={r['aris_file'].split('/')[-1]:r for r in csv.DictReader(f) if r['aris_file'].split('/')[-1] in recs}
    assert set(matches)==set(recs)
    identity={'gallery_sha256':digest(GALLERY),'matches_sha256':digest(SOURCE/'matches.csv'),'recordings':recs,'native':26761,'paired':4746}
    if (OUT/'run-identity.json').exists():assert json.loads((OUT/'run-identity.json').read_text())==identity
    else:save(OUT/'run-identity.json',identity)
    completed=[];errors=[]
    save(OUT/'progress.json',{'status':'running','total_recordings':40,'done_recordings':0})
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(process,rec,[i for i in items if i['recording']==rec],paired,matches[rec]):rec for rec in recs}
        for f in as_completed(futures):
            rec=futures[f]
            try:completed.append(f.result())
            except Exception:errors.append({'recording':rec,'error':traceback.format_exc()});print(json.dumps(errors[-1]),flush=True)
            save(OUT/'progress.json',{'status':'running','total_recordings':40,'done_recordings':len(completed),
                'failed_recordings':errors,'completed_samples':sum(len(c['items']) for c in completed),
                'status_counts':dict(Counter(r['status'] for c in completed for r in c['items']))})
    save(OUT/'failures.json',errors)
    if errors:raise RuntimeError(f'{len(errors)} recordings failed; preserved logs; rerun resumes verified completed manifests')
    assert digest(GALLERY)==identity['gallery_sha256'] and digest(SOURCE/'matches.csv')==identity['matches_sha256']
    completed.sort(key=lambda c:c['summary']['recording'])
    rows=[r for c in completed for r in c['items']]
    assert len(rows)==26761 and len({r['sample'] for r in rows})==26761
    manifest={'name':'camera_temporal_all','status':'candidate_only_not_training_ready',
        'scope':'40 approved development recordings; no test; no model inference or new split',
        'label_policy':'original SD JSON byte copies; FHD boxes x3 once; no translation/clipping',
        'identity':identity,'recordings':[c['summary'] for c in completed],'items':rows}
    save(OUT/'manifest.json',manifest)
    with (OUT/'correspondence.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['sample','recording','category','aris_frame','sd_index','sd_pts','fhd_index','fhd_pts','time_residual_s',
            'status','old_jpg_predicted_index_mse','sd_to_rebuilt_mse','sd_to_old_mse','paired_id','paired_role','paired_image_matches_native']
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    write_viewer(rows)
    save(OUT/'progress.json',{'status':'complete_candidate_export','recordings':40,'samples':len(rows),
        'status_counts':dict(Counter(r['status'] for r in rows)),'paired':4746,'failures':0})
    print('COMPLETE '+json.dumps(Counter(r['status'] for r in rows)),flush=True)


if __name__=='__main__':main()
