"""Read-only source diagnostics: common-input scaling and stream-copy cutting."""
from pathlib import Path
import subprocess,json
ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(r'D:\pby\data_processed\gopro')
OUT=ROOT/'复现/camera-baseline/annotation-issues/full-source-timing/controls'
def run(args,tag):
    p=subprocess.run(args,capture_output=True)
    (OUT/(tag+'.stderr')).write_bytes(p.stderr)
    if p.returncode:raise RuntimeError(tag+': '+p.stderr.decode(errors='replace')[-1200:])
    return p.stdout
def probe(path):
    data=json.loads(run(['ffprobe','-v','error','-select_streams','v:0','-show_streams','-show_format','-of','json',str(path)],path.stem+'-probe'))
    (OUT/(path.stem+'-probe.json')).write_text(json.dumps(data,indent=2),encoding='utf-8')
    s=data['streams'][0]
    return {k:s.get(k) for k in ['start_time','duration','nb_frames','avg_frame_rate','width','height']}
def main():
    OUT.mkdir(parents=True,exist_ok=True);result={}
    (OUT/'ffmpeg-version.txt').write_bytes(subprocess.check_output(['ffmpeg','-version']))
    for clip in ['20230921_GX010012_04','20230921_GX020012_02']:
        copied=[]
        for seconds in [10,20]:
            for res in ['sd','fhd']:
                p=OUT/f'{clip}-{res}-copycut-{seconds}.mp4'
                command=['ffmpeg','-hide_banner','-loglevel','info','-n','-i',str(SOURCE/f'clips_{res}'/(clip+'.mp4')),'-ss',str(seconds),'-to',str(seconds+10),'-map','0:v:0','-c:v','copy','-an',str(p)]
                if not p.exists():run(command,p.stem)
                copied.append({'resolution':res,'cut_start':seconds,'command':command,'output':str(p),'probe':probe(p)})
        result[clip]={'stream_copy_cut_controls':copied}
        print('Stream-copy controls completed '+clip,flush=True)
    clip='20230921_GX010012_04'
    sd=OUT/(clip+'-common-uhd-scale-sd.mp4');fhd=OUT/(clip+'-common-uhd-scale-fhd.mp4')
    command=['ffmpeg','-hide_banner','-loglevel','info','-n','-i',str(SOURCE/'clips_uhd'/(clip+'.mp4')),'-filter_complex','[0:v]split=2[a][b];[a]scale=640:360[sd];[b]scale=1920:1080[fh]','-map','[sd]','-t','8','-c:v','libx264','-an',str(sd),'-map','[fh]','-t','8','-c:v','libx264','-an',str(fhd)]
    if not (sd.exists() and fhd.exists()):run(command,'common-uhd-scale')
    result[clip]['common_uhd_scale_control']={'command':command,'sd':probe(sd),'fhd':probe(fhd),'limit':'8s diagnostic, shared decoder/current FFmpeg; not a replay of the unpublished historical production run'}
    (OUT/'control-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
