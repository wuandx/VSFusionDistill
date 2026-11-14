"""Audit selected video container metadata and provenance; never decode images."""
from pathlib import Path
import csv,json,hashlib,subprocess,struct,urllib.request,datetime
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'DataSet/gopro_imaging_model';OUT.mkdir(exist_ok=True)
SOURCES=ROOT/'related_work/gopro-imaging-model';SOURCES.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
selection=ROOT/'DataSet/sonar_independent_registration/selection.json'
rows=read(selection)['samples'];recs=sorted({r['recording'] for r in rows})
manifest_path=ROOT/'DataSet/camera_temporal_all/manifest-resolved.json'
manifest={x['sample']:x for x in read(manifest_path)['items'] if x.get('paired_role') in ['train','val','val_id']}
assert all(x['sample'] in manifest for x in rows)
match_path=Path('D:/pby/data_processed/matches.csv')
with match_path.open(encoding='utf-8',newline='') as f:matches={Path(x['aris_file']).name:x for x in csv.DictReader(f)}
tracked=[selection,manifest_path,match_path,ROOT/'experiment/gopro-imaging-model-plan.md']
repo=ROOT/'related_work/uxo-upstream-history'
tracked.extend(repo/x for x in ['scripts/prep_7_gopro_cut.bash','scripts/prep_8_gopro_downsample.bash','README.md'])
tracked.extend((repo/'calibration/camera_parameters').glob('*.txt'))
before={str(p):sha(p) for p in tracked};stats={};videos=[]
def atoms(path):
    entries=[];moov=[]
    with path.open('rb') as f:
        end=path.stat().st_size;pos=0
        while pos+8<=end:
            f.seek(pos);header=f.read(8);size,kind=struct.unpack('>I4s',header);hs=8
            if size==1:size=struct.unpack('>Q',f.read(8))[0];hs=16
            if size==0:size=end-pos
            assert size>=hs and pos+size<=end
            name=kind.decode('latin1');entries.append(dict(type=name,offset=pos,bytes=size))
            if kind==b'moov':
                assert size<20000000
                data=f.read(size-hs);dest=OUT/(path.stem+'-'+path.parent.name+'-moov.bin');dest.write_bytes(data)
                # Presence is a bounded search of metadata only, not video packets.
                moov.append(dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),tokens={k:data.count(k.encode()) for k in ['GPMF','gpmd','GPRO','HERO','GoPro','FOV','LENS','EIS','Hypersmooth','Lavf']},local_copy=str(dest)))
            pos+=size
    return dict(top_level=entries,moov=moov)
for rec in recs:
    base=Path('D:/pby/data_processed')/matches[rec]['gopro_file']
    for resolution in ['sd','fhd','uhd']:
        path=base.parent.parent/('clips_'+resolution)/base.name
        stats[str(path)]=dict(bytes=path.stat().st_size,mtime_ns=path.stat().st_mtime_ns)
        run=subprocess.run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)],capture_output=True,check=True)
        dest=OUT/(path.stem+'-'+resolution+'-probe.json');dest.write_bytes(run.stdout)
        probe=json.loads(run.stdout);video=next(s for s in probe['streams'] if s['codec_type']=='video')
        videos.append(dict(recording=rec,resolution=resolution,path=str(path),width=video['width'],height=video['height'],fps=video['avg_frame_rate'],codec=video['codec_name'],start_time=video.get('start_time'),frames=video.get('nb_frames'),stream_types=[dict(type=s['codec_type'],tag=s.get('codec_tag_string'),tags=s.get('tags',{})) for s in probe['streams']],format_tags=probe['format'].get('tags',{}),atoms=atoms(path)))
assert all(Path(p).stat().st_size==s['bytes'] and Path(p).stat().st_mtime_ns==s['mtime_ns'] for p,s in stats.items())
assert all(sha(Path(p))==h for p,h in before.items())
save(OUT/'metadata-audit.json',dict(videos=videos,input_hashes=before,video_stats=stats,unchanged=True,decoded_images=0,test_access=False,script_sha256=sha(Path(__file__))))
# Exact local repository snapshots (no fetch / checkout mutation).
gitcmds={'calibration-addition':['show','2d5f8de','--format=fuller','--','calibration'], 'readme-calibration-addition':['show','a52d22a','--','README.md'],'metadata-removal':['show','4219e68','--stat','--format=fuller'],'history-paths':['log','--all','--format=','--name-only']}
history=[]
for name,args in gitcmds.items():
    r=subprocess.run(['git','-C',str(repo),*args],capture_output=True,timeout=90)
    p=SOURCES/(name+'.txt');p.write_bytes(r.stdout)
    history.append(dict(command=args,exit_code=r.returncode,sha256=sha(p),stderr=r.stderr.decode('utf-8',errors='replace')))
save(SOURCES/'history-capture.json',history)
urls={'issue-1-comments':'https://api.github.com/repos/dfki-ric/uxo-dataset2024/issues/1/comments','issue-5-comments':'https://api.github.com/repos/dfki-ric/uxo-dataset2024/issues/5/comments','zenodo':'https://zenodo.org/api/records/13778485','paper-crossref':'https://api.crossref.org/works/10.1109/OCEANS55160.2024.10754316','paper-openalex':'https://api.openalex.org/works/https://doi.org/10.1109/OCEANS55160.2024.10754316'}
log=[]
for name,url in urls.items():
    entry=dict(url=url,captured_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'ResearchAudit/1.0'})
        with urllib.request.urlopen(req,timeout=25) as response:
            body=response.read(10000000);p=SOURCES/(name+'.json');p.write_bytes(body)
            entry.update(status=response.status,final_url=response.url,bytes=len(body),sha256=sha(p),local_path=str(p))
    except Exception as e:entry['error']=str(e)
    log.append(entry)
save(SOURCES/'retrieval-log.json',log)
print('Video probes:',len(videos),'UHD dimensions:',sorted({(v['width'],v['height']) for v in videos if v['resolution']=='uhd'}))
print('Stream tags:',sorted({s.get('tag','') for v in videos for s in v['stream_types']}))
print('Fetch statuses:',[(x['url'],x.get('status',x.get('error'))) for x in log])
