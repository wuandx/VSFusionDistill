"""Read only ISO-BMFF metadata for the exact development recording."""
from pathlib import Path
import hashlib
import json
import struct

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'DataSet/sonar_tag_continuous_camera'
PLAN=ROOT/'experiment/sonar-tag-clip-metadata-plan.md'


def boxes(f, start, stop):
    while start+8<=stop:
        f.seek(start)
        size,kind=struct.unpack('>I4s',f.read(8)); h=8
        if size==1:size=struct.unpack('>Q',f.read(8))[0];h=16
        if size==0:size=stop-start
        assert h<=size<=stop-start
        yield kind.decode('ascii',errors='replace'),start+h,start+size
        start+=size


def probe(p):
    before=p.stat();tracks=[]
    with p.open('rb') as f:
        top=list(boxes(f,0,before.st_size)); a,b=next((a,b) for k,a,b in top if k=='moov'); assert b-a<20_000_000
        f.seek(a);data=f.read(b-a)
        for typ,l,r in boxes(f,a,b):
            if typ!='trak':continue
            for kind,i,j in boxes(f,l,r):
                if kind!='mdia':continue
                for atom,u,v in boxes(f,i,j):
                    if atom=='hdlr':
                        f.seek(u+8); code=f.read(4).decode('ascii',errors='replace');f.read(12);raw=f.read(v-u-24).rstrip(b'\x00');raw=raw[1:] if raw and raw[0]==len(raw)-1 else raw;tracks.append(dict(type=code,name=raw.decode('utf-8',errors='replace')))
    after=p.stat(); assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    return dict(path=str(p),bytes=before.st_size,mtime_ns=before.st_mtime_ns,moov_sha256=hashlib.sha256(data).hexdigest(),handlers=tracks,token_counts={t:data.lower().count(t.encode()) for t in ['gpmd','gpmf','lens','fov','eis','hypersmooth','gopro','tmcd']},top_level=[k for k,_,_ in top])


def main():
    folder=ROOT/'DataSet/camera_temporal_all/recordings/2023-09-21_123500/attempt_1'
    paths=json.loads((folder/'fixed-inputs-before.json').read_text(encoding='utf-8'));clip=next(Path(p) for p in paths if 'clips_fhd' in p and p.endswith('.mp4'))
    assert clip.name=='20230921_GX020014_05.mp4'; res=[probe(clip.parent.parent/f'clips_{r}'/clip.name) for r in ('sd','fhd','uhd')]
    (OUT/'clip-metadata.json').write_text(json.dumps(dict(plan_sha256=hashlib.sha256(PLAN.read_bytes()).hexdigest(),videos=res,read_mdat=False,frames_decoded=0,lens_mode_certified=False,stabilization_certified=False),ensure_ascii=False,indent=2),encoding='utf-8')
    for v in res:print(v['handlers'],v['token_counts'])


if __name__=='__main__':main()
