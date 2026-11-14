"""Fixed two-recording image-only temporal check; no geometry fitting or deployment."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/_sonar_audit_deps'))
import csv, json, hashlib, subprocess, math
import numpy as np
import cv2
from PIL import Image, ImageDraw

BASE = Path('D:/pby/data_processed')
OUT = ROOT/'DataSet/sonar_camera_continuous_timing'
RECS = ['2023-09-20_171105', '2023-09-20_173329']


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_csv(p):
    with p.open(encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def flow(a, b, dt):
    pts = cv2.goodFeaturesToTrack(a, 500, .02, 7, blockSize=7)
    if pts is None or len(pts) < 12:
        return dict(valid=False, tracks=0)
    q, ok, _ = cv2.calcOpticalFlowPyrLK(a,b,pts,None,winSize=(21,21),maxLevel=3,
                                      criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,30,.01))
    back, ok2, _ = cv2.calcOpticalFlowPyrLK(b,a,q,None,winSize=(21,21),maxLevel=3,
                                         criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,30,.01))
    p=pts.reshape(-1,2); q=q.reshape(-1,2)
    keep=(ok.ravel()>0)&(ok2.ravel()>0)&(np.linalg.norm(back.reshape(-1,2)-p,axis=1)<1)
    keep&=(q[:,0]>=0)&(q[:,0]<a.shape[1])&(q[:,1]>=0)&(q[:,1]<a.shape[0])
    p,q=p[keep],q[keep]
    if len(p)<12:
        return dict(valid=False, tracks=len(p))
    d=q-p
    hull=cv2.contourArea(cv2.convexHull(p))/(a.shape[0]*a.shape[1])
    med=np.median(d,axis=0)
    cells=np.floor(p/np.array([a.shape[1]/3,a.shape[0]/2])).astype(int)
    local=[]
    for y in range(2):
        for x in range(3):
            k=(cells[:,0]==x)&(cells[:,1]==y)
            if k.sum()>=4:
                local.append(dict(cell=[x,y],tracks=int(k.sum()),median_px=np.median(d[k],axis=0).tolist()))
    return dict(valid=bool(hull>=.05),tracks=len(p),hull_fraction=float(hull),
                median_flow_px=med.tolist(),median_magnitude_px=float(np.median(np.linalg.norm(d,axis=1))),
                speed_px_s=float(np.median(np.linalg.norm(d,axis=1))/dt),
                speed_diagonals_s=float(np.median(np.linalg.norm(d,axis=1))/dt/math.hypot(*a.shape)),
                cells=local)


def compare_activity(items, lo, hi):
    ar=[m for m in items if m.get('aris_flow',{}).get('valid')]
    ca=[m for m in items if m.get('camera_flow',{}).get('valid')]
    if not ar or not ca:
        return dict(status='insufficient_valid_flow')
    at=np.array([m['flow_mid_t_s'] for m in ar]); av=np.array([m['aris_flow']['speed_diagonals_s'] for m in ar])
    ct=np.array([m['flow_mid_t_s'] for m in ca]); cv=np.array([m['camera_flow']['speed_diagonals_s'] for m in ca])
    curves=[]
    for delta in np.arange(-8,8.001,.2):
        delta=round(float(delta),8)
        keep=(at>=lo)&(at<=hi)&(at+delta>=ct[0])&(at+delta<=ct[-1])
        t=at[keep]+delta
        # Do not interpolate across more than 0.5 seconds of missing optical-flow support.
        k=np.searchsorted(ct,t).clip(1,len(ct)-1)
        supported=(ct[k]-ct[k-1])<=.5
        x=av[keep][supported];y=np.interp(t[supported],ct,cv)
        corr=float(np.corrcoef(x,y)[0,1]) if len(x)>=30 and np.std(x)>1e-9 and np.std(y)>1e-9 else None
        curves.append(dict(delta_camera_s=round(float(delta),8),pairs=len(x),correlation=corr))
    usable=[x for x in curves if x['correlation'] is not None and np.isfinite(x['correlation'])]
    if not usable:
        return dict(status='insufficient_valid_flow',curves=curves)
    best=max(usable,key=lambda x:x['correlation']);other=[x['correlation'] for x in usable if abs(x['delta_camera_s']-best['delta_camera_s'])>=.599]
    zero=min(usable,key=lambda x:abs(x['delta_camera_s']))
    return dict(status='diagnostic_only',range_s=[lo,hi],best=best,zero=zero,
                peak_margin=float(best['correlation']-max(other)) if other else None,curves=curves)


def main():
    OUT.mkdir(exist_ok=True)
    assert not (OUT/'results.json').exists()
    audit_path=ROOT/'DataSet/sonar_motion_timing/results.json'
    audits={x['recording']:x for x in json.loads(audit_path.read_text('utf-8'))['records']}
    hashes={str(audit_path):sha(audit_path),str(BASE/'matches.csv'):sha(BASE/'matches.csv')}
    records=[]
    for rec in RECS:
        a=audits[rec];match=a['match'];folder=BASE/match['aris_file'];mp=folder/(rec+'_frames.csv');gp=BASE/match['gantry_file'];video=BASE/match['gopro_file']
        for p in [mp,gp,video]:hashes[str(p)]=sha(p)
        rows=load_csv(mp);onset=next(int(r['FrameTime']) for r in rows if int(r['FrameIndex'])==int(match['aris_onset']))
        times=np.array([(int(r['FrameTime'])-onset)/1e6 for r in rows])
        cap=cv2.VideoCapture(str(video));fps=cap.get(cv2.CAP_PROP_FPS);count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));offset=int(match['gopro_offset'])
        lower=max(0,-offset/fps);upper=min(times[-1],(count-1-offset)/fps)
        targets=np.arange(math.ceil(lower*5)/5,float(times[-1])+.001,.2)
        ids=[]
        for t in targets:
            idx=int(np.argmin(abs(times-t)))
            if not ids or idx!=ids[-1]:ids.append(idx)
        dest=OUT/rec;dest.mkdir(exist_ok=True)
        frame_dir=dest/'keyframes';frame_dir.mkdir(exist_ok=True)
        encoder=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1024x620','-r','5','-i','pipe:0','-an','-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(dest/'paired.mp4')],stdin=subprocess.PIPE)
        items=[];prev_ar=None;prev_ca=None;prev_t=None;prev_index=None;sample_canvases=[]
        for j,idx in enumerate(ids):
            row=rows[idx];t=float(times[idx]);frame=int(row['FrameIndex']);p=folder/f'{frame:04d}.pgm';hashes[str(p)]=sha(p)
            raw=cv2.imdecode(np.frombuffer(p.read_bytes(),np.uint8),cv2.IMREAD_GRAYSCALE);assert raw is not None
            ar=cv2.resize(np.minimum(raw.astype(np.uint16)*3,255).astype(np.uint8),(512,520))
            ar=cv2.GaussianBlur(ar,(3,5),0)
            ci=int(t*fps)+offset;valid=0<=ci<count;img=None;camera=None
            if valid:
                # Sequential forward decode, no frame-index clamping or recycling.
                current=int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                if current>ci:cap.set(cv2.CAP_PROP_POS_FRAMES,ci)
                while int(cap.get(cv2.CAP_PROP_POS_FRAMES))<ci:
                    assert cap.grab()
                assert int(cap.get(cv2.CAP_PROP_POS_FRAMES))==ci
                ok,img=cap.read();assert ok and img.shape[:2]==(360,640)
                camera=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
            m=dict(frame=frame,t_s=t,sd_index=ci,camera_valid=valid,
                   sd_frame_pts_relative_s=ci/fps if valid else None,
                   camera_index_quantization_s=(ci-offset)/fps-t if valid else None,
                   sonar_pan_tilt_roll=[float(row[k]) for k in ['SonarPan','SonarTilt','SonarRoll']],
                   abs_pan_tilt_roll=[float(row[k]) for k in ['PanAbsPosition','TiltAbsPosition','RollAbsPosition']],
                   decoded_raw_sha256=hashlib.sha256(raw.tobytes()).hexdigest(),
                   decoded_sd_sha256=hashlib.sha256(img.tobytes()).hexdigest() if valid else None)
            if prev_t is not None:
                dt=t-prev_t;m['flow_mid_t_s']=(t+prev_t)/2
                m['aris_flow']=flow(prev_ar,ar,dt)
                if valid and prev_ca is not None:m['camera_flow']=flow(prev_ca,camera,dt)
            prev_ar=ar;prev_ca=camera;prev_t=t
            canvas=Image.new('RGB',(1024,620),'#f2f2f2');d=ImageDraw.Draw(canvas)
            display=Image.fromarray(np.minimum(raw.astype(np.uint16)*3,255).astype(np.uint8)).convert('RGB').resize((340,520))
            canvas.paste(display,(10,76))
            if img is not None:canvas.paste(Image.fromarray(cv2.cvtColor(img,cv2.COLOR_BGR2RGB)),(374,150))
            else:d.text((390,270),'SD CAMERA OUT OF COVERAGE - no repeated frame',fill='red')
            d.text((12,10),f'{rec} | t(ARIS mark)={t:+.3f}s | ARIS frame {frame} | SD index {ci}',fill='black')
            d.text((12,31),'LEFT: ARIS raw x3 fixed gain | RIGHT: native SD, published pairing | no boxes / no mesh',fill='black')
            d.text((12,52),f'SonarPan={float(row["SonarPan"]):.3f}  PanAbs={float(row["PanAbsPosition"]):.3f}  roll={float(row["SonarRoll"]):.2f}',fill='black')
            d.text((12,602),'5 sampled frames per second; source timestamps shown. Camera absence is explicit.',fill='black')
            encoder.stdin.write(np.asarray(canvas).tobytes())
            if j%5==0 or j==len(ids)-1:
                key=frame_dir/f'{j:04d}.jpg';canvas.save(key,quality=94);sample_canvases.append((j,t,key))
            if valid and (j in [0,len(ids)//2] or (t<=upper and t+.21>upper)):
                cp=dest/f'sd-{ci:04d}.png';cp.write_bytes(cv2.imencode('.png',img)[1].tobytes());m['verification_png']=str(cp)
            items.append(m)
        encoder.stdin.close();assert encoder.wait()==0;cap.release()
        duration=len(ids)/5
        # Fixed front/middle/end windows of common coverage; no result-dependent picking.
        valid_times=[m['t_s'] for m in items if m['camera_valid']]
        lo,hi=min(valid_times),max(valid_times)
        window_starts=[lo,max(lo,(lo+hi)/2-4),max(lo,hi-8)]
        windows=[]
        for label,start in zip(['early','middle','late'],window_starts):
            chosen=[x for x in sample_canvases if start-.1<=x[1]<=start+8.1]
            sheet=Image.new('RGB',(1024,310*len(chosen)),'white')
            for k,(_,tt,key) in enumerate(chosen):
                im=Image.open(key).resize((1024,620));sheet.paste(im.resize((512,310)),((k%2)*512,(k//2)*310))
            sheet=sheet.crop((0,0,1024,math.ceil(len(chosen)/2)*310));sheet.save(dest/f'{label}-contact.jpg',quality=94)
            ss=max(0,(start-times[ids[0]]))
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(ss),'-i',str(dest/'paired.mp4'),'-t','8','-an','-c:v','libx264','-pix_fmt','yuv420p',str(dest/f'{label}.mp4')],check=True)
            windows.append(dict(name=label,start_t_s=start,end_t_s=min(start+8,hi),contact=f'{label}-contact.jpg',clip=f'{label}.mp4'))
        segments=[compare_activity(items,lo,hi)]+[compare_activity(items,lo+(hi-lo)*k/3,lo+(hi-lo)*(k+1)/3) for k in range(3)]
        supported=all(x.get('best',{}).get('correlation',-1)>=.7 and (x.get('peak_margin') or 0)>=.1 for x in segments)
        if supported:supported=(max(x['best']['delta_camera_s'] for x in segments[1:])-min(x['best']['delta_camera_s'] for x in segments[1:]))<=.4
        g=load_csv(gp);gt=np.array([float(x['timestamp_us']) for x in g]);xyz=np.array([[float(x[k]) for k in 'xyz'] for x in g]);dt=np.diff(gt)/1e6;speed=np.linalg.norm(np.diff(xyz,axis=0),axis=1)/dt;elapsed=(gt-gt[0])/1e6
        low=None;static=None
        for k in range(len(speed)):
            if elapsed[-1]-elapsed[k+1]>=1 and np.all((speed[k:]<=.005)&(dt[k:]<=.5)):
                low=k+1;break
        for k in range(len(speed)):
            if elapsed[-1]-elapsed[k+1]>=1 and np.all((np.linalg.norm(np.diff(xyz,axis=0),axis=1)[k:]<=1e-10)&(dt[k:]<=.5)):
                static=k+1;break
        offsets={'published_matches':float(match['gantry_offset'])/1e6,'source_first_change':a['gantry_vector_onset_offset_us']/1e6}
        stop=dict(low_speed_sample_elapsed_s=float(elapsed[low]) if low else None,exact_static_sample_elapsed_s=float(elapsed[static]) if static else None,
                  mappings={name:dict(low_speed_aris_t_s=float(elapsed[low]-off),exact_static_aris_t_s=float(elapsed[static]-off)) for name,off in offsets.items()},
                  source_samples=[dict(elapsed_s=float(elapsed[i+1]),speed_m_s=float(speed[i]),sample_gap_s=float(dt[i])) for i in range(len(speed))])
        records.append(dict(recording=rec,sd_video=str(video),fps=fps,sd_frame_count=count,gopro_offset=offset,
                            aris_onset_timestamp_us=onset,common_coverage_s=[lo,hi],sampled_aris_range_s=[items[0]['t_s'],items[-1]['t_s']],
                            windows=windows,activity_comparison=segments,strong_activity_support=bool(supported),gantry_stop=stop,items=items))
        print(rec,'samples',len(items),'common',[lo,hi],'activity',[(x.get('best'),x.get('peak_margin')) for x in segments],flush=True)
        print('stop',stop['mappings'],flush=True)
    assert all(sha(Path(p))==h for p,h in hashes.items())
    result=dict(run='sonar_camera_continuous_timing',records=records,input_hashes=hashes,inputs_unchanged=True,
                source_raw_frames_read=sum(len(x['items']) for x in records),selected_sd_frames=sum(sum(i['camera_valid'] for i in x['items']) for x in records),
                formal_time_version_frozen=False,model_fits=0,training_runs=0,test_access=0)
    (OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    html='<!doctype html><meta charset="utf-8"><title>连续配对核查</title><style>body{max-width:1100px;margin:25px auto;font:18px system-ui}video{width:100%}article{margin:35px 0}</style><h1>相机—ARIS 连续配对核查</h1><p>左侧 ARIS 固定增益，右侧原生 SD；沿用发布配对，不叠加模型或框。画面 t 相对 ARIS 标记，播放器时间从片段开头计算。相机缺覆盖明确留空，不复用首尾帧。当前时间版本未冻结。</p>'
    for r in records:
        rec=r['recording'];html+=f'<h2>{rec}</h2>'
        for w in r['windows']:
            html+=f'<article><h3>{w["name"]}: t≈{w["start_t_s"]:.1f}–{w["end_t_s"]:.1f}s</h3><video controls preload="metadata" src="{rec}/{w["clip"]}"></video><a href="{rec}/{w["contact"]}">逐秒对照</a></article>'
        html+=f'<p><a href="{rec}/paired.mp4">完整采样片段（包含末段相机缺覆盖提示）</a></p>'
    (OUT/'index.html').write_text(html,encoding='utf-8')


if __name__=='__main__':main()
