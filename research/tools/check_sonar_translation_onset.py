"""Pan-stable, model-free image-motion diagnostic on six fixed source windows."""
from pathlib import Path
import sys,csv,json,hashlib,subprocess,shutil
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np,cv2
from PIL import Image,ImageDraw
BASE=Path('D:/pby/data_processed');OUT=ROOT/'DataSet/sonar_translation_onset'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    OUT.mkdir(exist_ok=True);assert not (OUT/'results.json').exists()
    auditpath=ROOT/'DataSet/sonar_motion_timing/results.json';audit=json.loads(auditpath.read_text('utf-8'));hashes={str(auditpath):sha(auditpath)};outputs=[]
    for a in audit['records']:
        rec=a['recording'];folder=BASE/a['match']['aris_file'];mp=folder/(rec+'_frames.csv');hashes[str(mp)]=sha(mp)
        with mp.open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
        onset=next(int(r['FrameTime']) for r in rows if int(r['FrameIndex'])==a['aris_match_onset']);selected=[r for r in rows if -2<=(int(r['FrameTime'])-onset)/1e6<=8];times=np.array([(int(r['FrameTime'])-onset)/1e6 for r in selected]);angles=np.array([[float(r[k]) for k in ['SonarPan','SonarTilt','SonarRoll']] for r in selected]);reference_angles=np.median(angles[(times>=-1.5)&(times<=-.5)],axis=0);raws=[]
        for r in selected:
            p=folder/(f"{int(r['FrameIndex']):04d}.pgm");hashes[str(p)]=sha(p);raws.append(cv2.imdecode(np.frombuffer(p.read_bytes(),np.uint8),cv2.IMREAD_GRAYSCALE))
        smoothed=[cv2.GaussianBlur(im.astype('float32'),(5,9),0) for im in raws];reference=np.mean([im for im,t in zip(smoothed,times) if -1.5<=t<=-.5],axis=0).astype('float32');h,w=reference.shape;window=cv2.createHanningWindow((w,h),cv2.CV_32F);metrics=[]
        for im,t,r,angle in zip(smoothed,times,selected,angles):
            shift,response=cv2.phaseCorrelate(reference.copy(),im.copy(),window.copy());length=float(np.hypot(shift[0]*4,shift[1]));metrics.append(dict(frame=int(r['FrameIndex']),t_s=float(t),shift_raw_u=float(shift[0]),shift_raw_v=float(shift[1]),display_scaled_displacement=length,response=float(response),pan_tilt_roll=angle.tolist(),max_angle_change_deg=float(np.max(abs(angle-reference_angles)))))
        baseline=[m['display_scaled_displacement'] for m in metrics if m['t_s']<0 and m['response']>=.1];threshold=max(2.,float(np.quantile(baseline,.99)*3)) if baseline else None
        for m in metrics:m['motion_flag']=bool(threshold is not None and m['t_s']>=0 and m['response']>=.1 and m['max_angle_change_deg']<=.05 and m['display_scaled_displacement']>threshold)
        trigger=None
        for i in range(len(metrics)-4):
            if all(m['motion_flag'] for m in metrics[i:i+5]):trigger=metrics[i]['t_s'];break
        stable=[m for m in metrics if m['t_s']>=0 and m['max_angle_change_deg']<=.05];windows={}
        for name,lo,hi in [('before',-1,0),('early',0,1),('next',1,2)]:
            mm=[m for m in metrics if lo<=m['t_s']<hi];windows[name]=dict(count=len(mm),median_displacement=float(np.median([m['display_scaled_displacement'] for m in mm])),median_response=float(np.median([m['response'] for m in mm])),max_angle_change_deg=max(m['max_angle_change_deg'] for m in mm))
        record=dict(recording=rec,window_seconds=[-2,8],frames_read=len(raws),reference_pan_tilt_roll=reference_angles.tolist(),threshold_display_scaled_pixels=threshold,first_5_frame_motion_start_s=trigger,last_angle_stable_sample_s=max(m['t_s'] for m in stable) if stable else None,old_match_predicted_gantry_motion_s=-a['match_minus_vector_onset_seconds'],source_onset_predicted_motion_s=0,windows=windows,metrics=metrics)
        if '2023-09-20' in rec:
            dest=OUT/rec;dest.mkdir(exist_ok=True);rendered=[];reference_image=Image.fromarray(np.minimum(np.mean([im for im,t in zip(raws,times) if -1.5<=t<=-.5],axis=0)*3,255).astype('uint8')).convert('RGB').resize((384,520))
            for index,tt in enumerate(np.arange(-2,8,.1)):
                ix=int(np.argmin(abs(times-tt)));r=selected[ix];m=metrics[ix];pic=Image.fromarray(np.minimum(raws[ix].astype('uint16')*3,255).astype('uint8')).convert('RGB').resize((384,520));canvas=Image.new('RGB',(800,630),'#f0f0f0');d=ImageDraw.Draw(canvas);canvas.paste(reference_image,(10,80));canvas.paste(pic,(406,80));d.text((12,8),rec+' | no boxes, no mesh, fixed gain x3',fill='black');d.text((12,29),'LEFT: mean reference -1.5 to -0.5 s   RIGHT: source frame',fill='black');d.text((12,49),f't = {m["t_s"]:+.3f} s   frame={m["frame"]}   pan/tilt/roll = '+str([round(x,3) for x in m['pan_tilt_roll']]),fill='black');d.text((12,608),'t=0: published ARIS motion mark; display stretch only; no stabilization.',fill='black');canvas.save(dest/f'{index:04d}.png');rendered.append(canvas)
            cmd=[shutil.which('ffmpeg'),'-hide_banner','-loglevel','error','-y','-framerate','10','-i',str(dest/'%04d.png'),'-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/(rec+'.mp4'))];subprocess.run(cmd,check=True)
            # Compact review artifact for the pan-stable early interval.
            early=[rendered[i].resize((640,504)) for i,t in enumerate(np.arange(-2,8,.1)) if -.5<=t<1.3];early[0].save(OUT/(rec+'-early.gif'),save_all=True,append_images=early[1:],duration=150,loop=0)
            ids=[int(np.argmin(abs(times-v))) for v in [-1,0,.5,1,2,6]];sheet=Image.new('RGB',(3*384,2*440),'white');sd=ImageDraw.Draw(sheet)
            for i,k in enumerate(ids):
                p=Image.fromarray(np.minimum(raws[k].astype('uint16')*3,255).astype('uint8')).convert('RGB').resize((384,400));x=(i%3)*384;y=(i//3)*440;sheet.paste(p,(x,y+30));sd.text((x+5,y+5),f't={times[k]:+.3f}s; pan={angles[k,0]:.3f}; frame={selected[k]["FrameIndex"]}',fill='black')
            sheet.save(OUT/(rec+'-contact.png'))
        outputs.append(record);print(rec,'threshold',threshold,'motion',trigger,'stable_until',record['last_angle_stable_sample_s'],'windows',windows,flush=True)
    assert all(sha(Path(p))==v for p,v in hashes.items())
    result=dict(run='sonar_translation_onset',records=outputs,input_hashes=hashes,inputs_unchanged=True,formal_time_version_frozen=False,no_mesh_or_box_used=True,source_images_newly_read=sum(r['frames_read'] for r in outputs))
    (OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    doc='<!doctype html><meta charset="utf-8"><title>运动起点人工核查</title><style>body{font:18px system-ui;max-width:1050px;margin:30px auto}video{width:100%}article{margin:40px 0}</style><h1>两段运动起点核查：无需画框</h1><p>左侧为静止参考，右侧为实际连续帧。t=0是原ARIS运动标记。观察整体回波/背景何时持续移动；不要把闪烁或散斑变化当移动。画面未叠加模型、预测框或运动补偿。</p><p>只需分别判断：t=0后1秒内是否已经持续移动？可回答“是 / 否 / 看不清”。数字pan不变只能排除记录到的转向，不能单独证明平移。</p>'
    for rec in ['2023-09-20_171105','2023-09-20_173329']:doc+=f'<article><h2>{rec}</h2><video controls loop preload="metadata" src="{rec}.mp4"></video><p><a href="{rec}-contact.png">六帧对照</a> · <a href="{rec}-early.gif">早期慢放</a></p></article>'
    (OUT/'index.html').write_text(doc,encoding='utf-8')
if __name__=='__main__':main()
