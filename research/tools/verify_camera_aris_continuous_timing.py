"""Check exported evidence, frame mapping and selected independent video decodes."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import json,csv,hashlib,subprocess,re
import numpy as np
import cv2

OUT=ROOT/'DataSet/sonar_camera_continuous_timing'


def main():
    r=json.loads((OUT/'results.json').read_text('utf-8'))
    checks=[]
    for a in r['records']:
        rec=a['recording'];video=a['sd_video'];fps=a['fps'];off=a['gopro_offset']
        p=Path('D:/pby/data_processed/aris')/rec/(rec+'_frames.csv')
        rows={int(x['FrameIndex']):x for x in csv.DictReader(p.open())}
        for m in a['items']:
            t=(int(rows[m['frame']]['FrameTime'])-a['aris_onset_timestamp_us'])/1e6
            assert t==m['t_s']
            assert int(t*fps)+off==m['sd_index']
            assert m['camera_valid']==(0<=m['sd_index']<a['sd_frame_count'])
            if m['camera_valid']:assert -1/fps-1e-9<=m['camera_index_quantization_s']<=1e-9
        chosen=[m for m in a['items'] if m.get('verification_png')]
        decode=[]
        for m in chosen:
            index=m['sd_index']
            # OpenCV VideoCapture uses BT.601 here; ffmpeg honors source BT.709 by default.
            # Match conversion only for byte comparison; source frame selection is unchanged.
            cmd=['ffmpeg','-hide_banner','-loglevel','error','-i',video,'-vf',f'select=eq(n\\,{index}),scale=in_color_matrix=bt601:out_color_matrix=bt601',
                 '-fps_mode','passthrough','-frames:v','1','-f','rawvideo','-pix_fmt','bgr24','pipe:1']
            raw=subprocess.check_output(cmd);assert len(raw)==640*360*3
            im=np.frombuffer(raw,np.uint8).reshape(360,640,3)
            saved=cv2.imdecode(np.frombuffer(Path(m['verification_png']).read_bytes(),np.uint8),cv2.IMREAD_COLOR)
            diff=np.abs(im.astype(float)-saved.astype(float));same=bool(np.array_equal(im,saved))
            assert same
            decode.append(dict(sd_index=index,exact_equal=same,mean_abs_difference=float(diff.mean()),p99_abs_difference=float(np.percentile(diff,99))))
        media=[]
        for p in (OUT/rec).glob('*.mp4'):
            probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,duration,avg_frame_rate','-of','json',str(p)],text=True))['streams'][0]
            assert int(probe['width'])==1024 and int(probe['height'])==620
            if p.name=='paired.mp4':assert int(probe['nb_frames'])==len(a['items'])
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(p),'-f','null','-'],check=True)
            media.append(dict(path=str(p),probe=probe,full_decode_passed=True))
        # Recompute zero-lag correlation directly over jointly valid paired interval entries.
        lo,hi=a['common_coverage_s']
        mm=[m for m in a['items'] if m.get('aris_flow',{}).get('valid') and m.get('camera_flow',{}).get('valid')
            and lo<=m['flow_mid_t_s']<=hi]
        corr=float(np.corrcoef([m['aris_flow']['speed_diagonals_s'] for m in mm],[m['camera_flow']['speed_diagonals_s'] for m in mm])[0,1])
        # Initial np.arange grid represented zero as a tiny positive number and
        # omitted the final boundary pair. Preserve original results; audit the
        # corrected exact grid separately below.
        legacy=np.corrcoef([m['aris_flow']['speed_diagonals_s'] for m in mm[:-1]],
                          [m['camera_flow']['speed_diagonals_s'] for m in mm[:-1]])[0,1]
        assert abs(legacy-a['activity_comparison'][0]['zero']['correlation'])<1e-10
        checks.append(dict(recording=rec,all_frame_mappings_verified=len(a['items']),independent_sd_decodes=decode,
                           videos=media,zero_lag_direct_correlation=corr,paired_valid_intervals=len(mm)))
    for p,h in r['input_hashes'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
    html=(OUT/'index.html').read_text('utf-8')
    links=re.findall(r'(?:src|href)="([^"]+)"',html)
    for link in links:assert (OUT/link).exists(),link
    # Synthetic control of lag sign and missing-window handling, not evidence of real synchrony.
    from check_camera_aris_continuous_timing import compare_activity
    corrections=[]
    for a,check in zip(r['records'],checks):
        lo,hi=a['common_coverage_s']
        segments=[compare_activity(a['items'],lo,hi)]+[compare_activity(a['items'],lo+(hi-lo)*k/3,lo+(hi-lo)*(k+1)/3) for k in range(3)]
        assert abs(segments[0]['zero']['correlation']-check['zero_lag_direct_correlation'])<1e-10
        strong=all(x.get('best',{}).get('correlation',-1)>=.7 and (x.get('peak_margin') or 0)>=.1 for x in segments)
        if strong:strong=(max(x['best']['delta_camera_s'] for x in segments[1:])-min(x['best']['delta_camera_s'] for x in segments[1:]))<=.4
        assert strong==a['strong_activity_support']
        corrections.append(dict(recording=a['recording'],activity_comparison=segments,strong_activity_support=strong))
    (OUT/'activity-grid-correction.json').write_text(json.dumps(dict(reason='Round diagnostic delta grid to exact 0.2 s steps before comparing boundaries; original results preserved; admission decisions unchanged',records=corrections),indent=2)+'\n',encoding='utf-8')
    ts=np.arange(0,60,.2)
    activity=lambda t:np.sin(t*1.7)+.6*np.sin(t*.43)+.25*np.cos(t*2.41)
    synthetic=[dict(flow_mid_t_s=float(t),aris_flow=dict(valid=True,speed_diagonals_s=float(activity(t))),
                    camera_flow=dict(valid=True,speed_diagonals_s=float(activity(t-1.2)))) for t in ts]
    s=compare_activity(synthetic,8,50)
    assert abs(s['best']['delta_camera_s']-1.2)<1e-8 and s['best']['correlation']>.9999
    result=dict(passed=True,records=checks,source_hashes_unchanged=True,local_links_checked=len(links),
                synthetic_lag_sign_control=s['best'],operator='main assistant, separate verification code',
                source_video_frames_decoded_for_independent_checks=sum(len(x['independent_sd_decodes']) for x in checks))
    (OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=True,records=len(checks),sd_checks=result['source_video_frames_decoded_for_independent_checks'],links=len(links))))


if __name__=='__main__':main()
