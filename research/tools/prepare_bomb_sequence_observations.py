"""Unboxed 11-frame ordinary-bomb sequence displays. No model, fitting or GT read."""
from pathlib import Path
import sys,json,csv,hashlib
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
from PIL import Image,ImageDraw
from check_official_sonar_coordinates import Geometry,load_beam_tables,beam_count

OUT=ROOT/'DataSet/sonar_bomb_sequence_observations'
REC='2023-09-20_171105'
CENTERS=[622,981,1336]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def gain(a):return np.minimum(a.astype(np.uint16)*3,255).astype(np.uint8)

def raw_panel(a,title,scale=(4,2),grid=True):
    sx,sy=scale;h,w=a.shape;x0,y0=45,50
    out=Image.new('RGB',(w*sx+65,h*sy+80),'white');out.paste(Image.fromarray(a).convert('RGB').resize((w*sx,h*sy),Image.Resampling.NEAREST),(x0,y0));d=ImageDraw.Draw(out)
    d.text((8,5),title,fill='black');d.text((8,23),'raw pixel-edge coordinates; no model/box',fill='black')
    if grid:
        for x in range(0,w+1,8):
            xx=x0+x*sx;d.line((xx,y0,xx,y0+h*sy),fill=(55,65,70));d.text((xx-5,y0-15),str(x),fill='black')
        for y in range(0,h+1,20):
            yy=y0+y*sy;d.line((x0,yy,x0+w*sx,yy),fill=(55,65,70));d.text((x0-30,yy-5),str(y),fill='black')
    return out

def main():
    assert not (OUT/'source-provenance.json').exists(),'Keep previous run'
    plan=ROOT/'experiment/sonar-bomb-sequence-observation-plan.md';assert plan.exists()
    selection=ROOT/'DataSet/sonar_independent_registration/selection.json'
    centers=[r['aris_frame'] for r in json.loads(selection.read_text(encoding='utf-8'))['samples'] if r['recording']==REC]
    assert sorted(centers)==CENTERS
    manifest=ROOT/'DataSet/camera_temporal_all/manifest-resolved.json'
    allowed={r['aris_frame']:r for r in json.loads(manifest.read_text(encoding='utf-8'))['items'] if r['recording']==REC}
    selected=[];skipped=[]
    for center in CENTERS:
        for off in [-8,-4,0,4,8]:
            idx=center+off
            if idx not in allowed:skipped.append(dict(frame=idx,center=center,reason='not in approved native manifest; not read'));continue
            r=allowed[idx];assert r['category']=='100lbs_aircraft_bomb' and r.get('paired_role') in [None,'train','val','val_id']
            selected.append((center,r))
    assert len(selected)==11
    srcroot=Path(selected[0][1]['original_image']).parent.parent
    assert srcroot.name==REC and srcroot.parent.name=='100lbs_bomb'
    meta=srcroot/'aris_frame_meta.csv'
    with meta.open(encoding='utf-8',newline='') as f:metadata={int(r['FrameIndex']):r for r in csv.DictReader(f)}
    inputs=[plan,selection,manifest,meta,Path(__file__),ROOT/'tools/check_official_sonar_coordinates.py',ROOT/'related_work/uxo-upstream-history/scripts/common/aris_definitions.py']
    for _,r in selected:inputs += [srcroot/'aris_raw'/f"{r['aris_frame']:04d}.pgm",ROOT/'DataSet/camera_temporal_all'/r['reference_sd']]
    hashes={str(p):sha(p) for p in inputs};OUT.mkdir(parents=True,exist_ok=True);tables=load_beam_tables();records=[];loaded={}
    for center,r in selected:
        idx=r['aris_frame'];sid=r['sample'];raw=srcroot/'aris_raw'/f'{idx:04d}.pgm';camera=ROOT/'DataSet/camera_temporal_all'/r['reference_sd']
        md=metadata[idx];assert int(md['FrameTime'])==int(r['aris_time_us'])
        a=np.asarray(Image.open(raw));g=Geometry(md,tables[beam_count(md['PingMode'])]);assert a.shape==(g.h,g.w)
        polar=g.render(a);cam=Image.open(camera).convert('RGB');assert cam.size==(640,360)
        Image.fromarray(a).save(OUT/f'{sid}-raw.png');Image.fromarray(polar).save(OUT/f'{sid}-official-polar2.png');cam.save(OUT/f'{sid}-camera.png')
        orig=raw_panel(a,sid+' gain1');bright=raw_panel(gain(a),sid+' gain3')
        display=Image.new('RGB',(orig.width*2,orig.height),'white');display.paste(orig,(0,0));display.paste(bright,(orig.width,0));display.save(OUT/f'{sid}-raw-review.png')
        loaded[sid]=(a,polar,cam)
        records.append(dict(sample=sid,recording=REC,aris_frame=idx,center=center,role='fit_observation_development',raw_source=str(raw),camera_source=str(camera),metadata_source=str(meta),raw_source_sha256=hashes[str(raw)],camera_source_sha256=hashes[str(camera)],metadata_row=md,FrameTime_matches_manifest=True,geometry=g.description(),paired_role=r.get('paired_role')))
    for center in CENTERS:
        group=[r for r in records if r['center']==center];cw=335
        for view in ['raw','polar']:
            ch=1190 if view=='raw' else 1000;sheet=Image.new('RGB',(cw*len(group),ch),'white');d=ImageDraw.Draw(sheet)
            for k,r in enumerate(group):
                x=k*cw;sid=r['sample'];a,polar,cam=loaded[sid];d.text((x+8,8),f"ARIS {r['aris_frame']:04d} | unboxed | gain3",fill='black');sheet.paste(cam.resize((320,180)),(x+8,30))
                if view=='raw':
                    panel=raw_panel(gain(a),sid,(2,2));sheet.paste(panel,(x+5,220))
                else:
                    p=Image.fromarray(gain(polar)).convert('RGB');p.thumbnail((320,740),Image.Resampling.NEAREST);sheet.paste(p,(x+8,230));d.text((x+8,213),'official-source-compatible polar2; full frame',fill='black')
            sheet.save(OUT/f'window-{center:04d}-{view}-contact.png')
    after={p:sha(Path(p)) for p in hashes};assert hashes==after,'input changed'
    save(OUT/'source-provenance.json',dict(records=records,skipped=skipped,source_hashes_before=hashes,source_hashes_after=after,inputs_unchanged=True,raw_images_read=11,camera_images_read=11,model_or_old_boxes_read=False,check_recording_read=False,polar_note='Rendered from official-source-compatible Geometry; not fetched release polar files',display_gains=[1,3]))
    print(json.dumps({'records':len(records),'skipped':skipped,'source_hashes_unchanged':True},indent=2))

if __name__=='__main__':main()
