"""Unboxed permitted grenade development sequence; never loads model candidates."""
from pathlib import Path
import sys, json, hashlib
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/_sonar_audit_deps'))
import numpy as np
import cv2
from PIL import Image, ImageDraw
from sonar_manual_curation_server import DatasetSource
from check_official_sonar_coordinates import Geometry, beam_count

OUT = ROOT/'DataSet/sonar_grenade_sequence_observations'
REC = '2023-09-21_120653'

def main():
    OUT.mkdir(exist_ok=True)
    if (OUT/'manifest.json').exists(): raise RuntimeError('Preserve existing observation run')
    ds=DatasetSource(); meta,gantry,mp,gp=ds.recording_metadata(REC)
    entries=[];skipped=[]
    for center in [163,551,933]:
        tiles=[]
        for idx in range(center-8,center+9,4):
            sid=f'{REC}_{idx:04d}'
            if sid not in ds.rows:
                skipped.append(sid);continue
            row=ds.require(sid)
            rb,rp=ds.source_bytes(ds.rec_dirs[REC]/'aris_raw'/f'{idx:04d}.pgm')
            raw=cv2.imdecode(np.frombuffer(rb,np.uint8),cv2.IMREAD_GRAYSCALE)
            m=meta[idx];assert int(m['FrameTime'])==int(row['aris_time_us'])
            geom=Geometry(m,ds.tables[beam_count(m['PingMode'])],1000.)
            assert raw.shape==(geom.h,geom.w)
            polar=geom.render(raw)
            rawname=sid+'-raw.png';polarname=sid+'-polar.png'
            Image.fromarray(raw).save(OUT/rawname);Image.fromarray(polar).save(OUT/polarname)
            rpict=Image.fromarray(np.clip(raw.astype(float)*3,0,255).astype('uint8')).convert('RGB').resize((384,geom.h*2),Image.Resampling.NEAREST)
            ppict=Image.fromarray(np.clip(polar.astype(float)*3,0,255).astype('uint8')).convert('RGB');ppict.thumbnail((500,geom.h*2))
            panel=Image.new('RGB',(950,geom.h*2+250),'#eeeeee');panel.paste(rpict,(40,40));panel.paste(ppict,(445,40))
            draw=ImageDraw.Draw(panel);draw.text((10,8),sid+' | raw gain 3 | official polar2 | NO BOXES',fill='black')
            for v in range(0,geom.h,50):draw.text((4,40+2*v),str(v),fill='black')
            for u in range(0,geom.w+1,16):draw.text((40+3*u,geom.h*2+44),str(u),fill='black')
            cp=None
            if ds.sd_paths[sid] and ds.sd_paths[sid].is_file():
                cb,cp=ds.source_bytes(ds.sd_paths[sid]);cam=cv2.imdecode(np.frombuffer(cb,np.uint8),cv2.IMREAD_COLOR)
                pic=Image.fromarray(cv2.cvtColor(cam,cv2.COLOR_BGR2RGB));pic.thumbnail((320,180));panel.paste(pic,(40,geom.h*2+65))
            panel.save(OUT/(sid+'-unboxed.jpg'),quality=95)
            tile=Image.new('RGB',(424,geom.h*2+70),'white');tile.paste(rpict,(32,30));d=ImageDraw.Draw(tile);d.text((10,8),sid,fill='black')
            for v in range(0,geom.h,50):d.text((0,30+2*v),str(v),fill='black')
            for u in range(0,geom.w+1,32):d.text((32+3*u,geom.h*2+35),str(u),fill='black')
            tiles.append(tile)
            entries.append(dict(sample=sid,center=center,raw_source=rp,metadata=mp,gantry=gp,camera_source=cp,raw_shape=list(raw.shape),raw_file=rawname,polar_file=polarname,panel=sid+'-unboxed.jpg',historical_paired_role=row.get('paired_role')))
        if tiles:
            sheet=Image.new('RGB',(424*len(tiles),max(x.height for x in tiles)),'white')
            for i,t in enumerate(tiles):sheet.paste(t,(i*424,0))
            sheet.save(OUT/f'sequence-{center:04d}.jpg',quality=96)
    data=dict(recording=REC,manifest=ds.manifest_provenance,frames=entries,skipped_not_allowed=skipped,model_candidates_read=False,review_writes=0,source_files=ds.hash_cache)
    (OUT/'manifest.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(frames=len(entries),skipped=skipped,output=str(OUT)),ensure_ascii=False))

if __name__=='__main__':main()
