"""Fixed nine-frame, read-only audit of the existing sonar box formula."""
import csv
from dataclasses import replace
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import types

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[1]
REPO = Path('D:/agent_workspace/水下/声呐目标检测/code/VSFusionDistill')
OUT = ROOT/'DataSet/sonar_projection_chain_audit'
sys.path.insert(0, str(ROOT/'tools/_sonar_audit_deps'))
import cv2
import numpy as np
from PIL import Image, ImageDraw

for name in ('aodet', 'aodet.geometry', 'aodet.datasets', 'aodet.datasets.converters'):
    module = types.ModuleType(name)
    module.__path__ = []
    sys.modules[name] = module

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

beam = load_module('aodet.geometry.aris_beam_table', REPO/'aodet/geometry/aris_beam_table.py')
projection = load_module('aodet.datasets.converters.uxo_projection', REPO/'aodet/datasets/converters/uxo_projection.py')

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')

def repo_state():
    return {key:subprocess.check_output(['git','-C',str(REPO),*args],text=True).strip()
            for key,args in [('head',['rev-parse','HEAD']),('status',['status','--porcelain'])]}

def selected_cache_entries(path, recordings):
    # Parse only requested recording objects, not unrelated cache entries.
    text = path.read_text(encoding='utf-8')
    decoder = json.JSONDecoder()
    out = {}
    for rec in recordings:
        key = json.dumps(rec)+':'
        start = text.index(key)+len(key)
        out[rec] = decoder.raw_decode(text[start:].lstrip())[0]
    return out

def independent_boxes(calib, obs, width, height):
    # Given the centre, independently derive geometric extents from metres.
    row, col = projection.predict(calib, obs)
    length = projection.CLASS_LENGTH_M[obs.category_id]
    sensor = projection._centers(obs.gantry)[1]
    distance = max(float(np.linalg.norm(calib.P-sensor)), .3)
    half_angle = math.degrees(math.atan2(length/2, distance))
    centers = np.array([x[0] for x in beam.BEAM_WIDTHS_ARIS3000_128])
    angle = float(np.interp(col, np.arange(128), centers))
    lo = float(np.interp(angle-half_angle, centers, np.arange(128)))
    hi = float(np.interp(angle+half_angle, centers, np.arange(128)))
    radial = (length/2+.04)/(obs.sample_period*1e-6*obs.soundspeed/2)
    def box(x0,y0,x1,y1):
        x0,y0=max(x0,0),max(y0,0)
        x1,y1=min(x1,width),min(y1,height)
        return None if x1-x0<2 or y1-y0<2 else [x0,y0,x1-x0,y1-y0]
    unclamped=box(lo,row-radial,hi,row+radial)
    capped_actual=box(max(lo,col-20),max(row-radial,row-30),min(hi,col+20),min(row+radial,row+30))
    # Current code uses height=441 irrespective of the image header.
    capped_legacy=box(max(lo,col-20),max(row-radial,row-30),min(hi,col+20),min(row+radial,row+30,441))
    return unclamped,capped_actual,capped_legacy

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'images').mkdir(exist_ok=True)
    manifest_path=ROOT/'DataSet/camera_temporal_all/manifest-resolved.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    selected_recordings=[min(r['recording'] for r in manifest['recordings'] if r['category']==c)
                         for c in sorted({r['category'] for r in manifest['recordings']})]
    rows=[]
    for rec in selected_recordings:
        candidates=sorted([x for x in manifest['items'] if x['recording']==rec and x.get('paired_id')],key=lambda x:x['aris_frame'])
        assert candidates and all(x['paired_role'] in ('train','val','val_id') for x in candidates)
        rows.extend(candidates[i] for i in [0,len(candidates)//2,len(candidates)-1])
    save(OUT/'selection.json', {'rule':'first recording per category; first/middle/last existing paired identities',
                              'recordings':selected_recordings, 'samples':rows})
    cache_path=Path('D:/pby/uxo-full/paired/projection_calib.json')
    caches=selected_cache_entries(cache_path,selected_recordings)
    observed_paths={manifest_path,cache_path,REPO/'aodet/datasets/converters/uxo_projection.py',
                    REPO/'aodet/geometry/aris_beam_table.py',REPO/'tools/project_uxo_sonar.py'}
    before_repo=repo_state()
    source_rows={}
    for rec in selected_recordings:
        rd=Path(next(x['original_label'] for x in rows if x['recording']==rec)).parent.parent
        observed_paths.update([rd/'aris_frame_meta.csv',rd/'gantry.csv',rd/'aris_file_meta.yaml',rd/'notes.txt'])
        with (rd/'aris_frame_meta.csv').open(encoding='utf-8',newline='') as f:
            meta={int(r['FrameIndex']):r for r in csv.DictReader(f)}
        with (rd/'gantry.csv').open(encoding='utf-8',newline='') as f:
            gantry={int(r['aris_frame_idx']):r for r in csv.DictReader(f)}
        source_rows[rec]=(meta,gantry,rd)
    for item in rows:
        _,_,rd=source_rows[item['recording']]
        observed_paths.update([Path(item['original_label']),
                               rd/'aris_raw'/f"{item['aris_frame']:04d}.pgm",
                               Path('D:/pby/uxo-full/paired/images/sonar')/f"{item['sample']}.pgm"])
        if item.get('reference_sd'):
            observed_paths.add(ROOT/'DataSet/camera_temporal_all'/item['reference_sd'])
    before={str(p):digest(p) for p in sorted(observed_paths)}
    save(OUT/'input-snapshot-before.json', {'repo':before_repo,'sha256':before})
    results=[]
    sheets={rec:[] for rec in selected_recordings}
    cat_ids={'100lbs_aircraft_bomb':1,'incindiary_grenade':2,'mortar_shell':3}
    for item in rows:
        rec=item['recording'];idx=item['aris_frame'];meta,gantry,rd=source_rows[rec]
        m,g=meta[idx],gantry[idx]
        lab=json.loads(Path(item['original_label']).read_text(encoding='utf-8'))
        assert lab['class']==item['category']
        raw_path=rd/'aris_raw'/f'{idx:04d}.pgm'
        paired_path=Path('D:/pby/uxo-full/paired/images/sonar')/f"{item['sample']}.pgm"
        assert digest(raw_path)==digest(paired_path)
        raw=np.array(Image.open(raw_path));height,width=raw.shape
        blobs=projection.detect_blobs(raw)
        obs=projection.FrameObs(frame_idx=idx,sample_id=item['sample'],gantry=np.array([float(g[k]) for k in 'xyz']),
                                window_start=float(m['WindowStart']),sample_period=float(m['SamplePeriod']),
                                soundspeed=float(m['SoundSpeed']),category_id=cat_ids[item['category']])
        if blobs:
            _,r,c,w,h=blobs[0];obs.blob=(r,c,w,h)
            obs.theta=float(np.radians(beam.beam_center_deg(c)))
            obs.rng=float(beam.range_of_row(r,obs.window_start,obs.sample_period,obs.soundspeed))
        cd=caches[rec]['calib'].copy()
        for key in ['circle_centre','R_cam0','R_son0','P']:cd[key]=np.array(cd[key])
        calib=projection.CalibResult(**cd)
        entry=projection.sonar_bbox(calib,obs)
        pure=projection.sonar_bbox(calib,replace(obs,blob=None))
        uncapped,capped_actual,capped_legacy=independent_boxes(calib,obs,width,height)
        assert (pure is None)==(capped_legacy is None)
        if pure:assert np.allclose(pure['bbox'],capped_legacy,rtol=0,atol=1e-8)
        row,col=projection.predict(calib,obs)
        row_independent=(np.linalg.norm(calib.P-projection._centers(obs.gantry)[1])+calib.b_rng-obs.window_start)/obs.dr
        assert abs(row-row_independent)<1e-8
        result=dict(sample=item['sample'],recording=rec,category=item['category'],historical_role=item['paired_role'],
                    aris_frame=idx,raw_shape=[height,width],raw_matches_paired=True,frame_time_matches_manifest=int(m['FrameTime'])==item['aris_time_us'],
                    samples_per_beam=int(m['SamplesPerBeam']),range_m_per_row=obs.dr,
                    sonar_pan_tilt_roll=[float(m[k]) for k in ['SonarPan','SonarTilt','SonarRoll']],
                    cached_calibration_fingerprint=caches[rec].get('fingerprint'),cache_not_revalidated=True,
                    current_entry=entry,pure_projected=pure,uncapped_extent_diagnostic=uncapped,
                    capped_with_actual_height_diagnostic=capped_actual,independent_formula_agrees=True,
                    projected_center=[row,col],hardcoded_height_differs=height!=441,
                    height_441_changes_pure_box=(pure is None)!=(capped_actual is None) or (pure is not None and capped_actual is not None and not np.allclose(pure['bbox'],capped_actual)),
                    camera_sd_path=str(ROOT/'DataSet/camera_temporal_all'/item['reference_sd']) if item.get('reference_sd') else None,
                    sd_reference_missing=not bool(item.get('reference_sd')),raw_sonar_path=str(raw_path))
        assert result['frame_time_matches_manifest']
        results.append(result)
        # Full raw image is preserved; display resizing is explicitly labelled.
        canvas=Image.new('RGB',(1280,900),'#171b23');d=ImageDraw.Draw(canvas)
        d.text((16,12),f"{item['sample']} | {item['category']} | {item['paired_role']}",fill='white')
        if result['camera_sd_path']:
            cam=Image.open(result['camera_sd_path']).convert('RGB');assert cam.size==(640,360)
            draw=ImageDraw.Draw(cam);draw.rectangle((lab['x_min'],lab['y_min'],lab['x_max'],lab['y_max']),outline='#62ddff',width=2)
        else:
            cam=Image.new('RGB',(640,360),'#282c35')
            ImageDraw.Draw(cam).text((30,150),'SD REFERENCE MISSING - DEFERRED; fixed identity preserved',fill='#ff8888')
        canvas.paste(cam,(16,60));d.text((16,435),'SD camera + original camera box; no x3 scaling',fill='white')
        palette=[('#ff5858',entry['bbox'] if entry else None,'current hybrid'),('#f4d35e',pure['bbox'] if pure else None,'projected only'),
                 ('#69f0a5',uncapped,'uncapped extent: DIAGNOSTIC ONLY')]
        for panel,(color,box,title) in enumerate(palette):
            son=Image.fromarray(raw).convert('RGB').resize((170,780))
            sd=ImageDraw.Draw(son)
            if box:
                x,y,w,h=box;sd.rectangle((x*170/width,y*780/height,(x+w)*170/width,(y+h)*780/height),outline=color,width=2)
            sd.line((0,441*780/height,170,441*780/height),fill='#bf8cff',width=1)
            x0=700+panel*190;canvas.paste(son,(x0,60));d.text((x0,43),title.split(':')[0],fill=color)
        d.text((16,480),f'Raw sonar: {width} x {height}; current clip y<=441 shown in purple',fill='#bf8cff')
        d.text((16,505),f'Current source: {entry["source"] if entry else "NONE"}; fitted point, NOT 3D mesh projection',fill='white')
        d.text((16,530),f'Projected centre (row,col): {row:.2f}, {col:.2f}',fill='white')
        d.text((16,555),'Red=current box; yellow=projected only; green=uncapped size diagnostic',fill='white')
        d.text((16,580),'Cached fit reused for formula audit; no fit recomputation or GT acceptance',fill='#e9bb6a')
        d.text((16,605),'Sonar panels resized for display; boxes use actual raw pixel coordinates',fill='white')
        image_path=OUT/'images'/f"{item['sample']}.jpg"
        canvas.save(image_path,quality=94)
        sheets[rec].append(canvas)
    for rec,images in sheets.items():
        sheet=Image.new('RGB',(1280,900*len(images)))
        for i,im in enumerate(images):sheet.paste(im,(0,900*i))
        sheet.save(OUT/f'{rec}-sheet.jpg',quality=92)
    save(OUT/'results.json',results)
    fields=['sample','category','historical_role','raw_height','raw_width','current_source','current_bbox','pure_projected_bbox','uncapped_extent_diagnostic','sd_reference_missing']
    with (OUT/'frames.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for r in results:
            writer.writerow(dict(sample=r['sample'],category=r['category'],historical_role=r['historical_role'],
                raw_height=r['raw_shape'][0],raw_width=r['raw_shape'][1],
                current_source=r['current_entry']['source'] if r['current_entry'] else 'none',
                current_bbox=json.dumps(r['current_entry']['bbox'] if r['current_entry'] else None),
                pure_projected_bbox=json.dumps(r['pure_projected']['bbox'] if r['pure_projected'] else None),
                uncapped_extent_diagnostic=json.dumps(r['uncapped_extent_diagnostic']),sd_reference_missing=r['sd_reference_missing']))
    after={str(p):digest(p) for p in sorted(observed_paths)}
    after_repo=repo_state()
    verification=dict(samples=len(results),recordings=len(selected_recordings),input_files=len(before),
                      all_inputs_unchanged=before==after,repo_state_unchanged=before_repo==after_repo,
                      repo_after=after_repo,independent_formula_passed=all(r['independent_formula_agrees'] for r in results),
                      raw_matches_paired=all(r['raw_matches_paired'] for r in results),
                      frame_time_matches=all(r['frame_time_matches_manifest'] for r in results),
                      raw_shapes=sorted({tuple(r['raw_shape']) for r in results}),
                      current_source_counts={s:sum(r['current_entry'] is not None and r['current_entry']['source']==s for r in results) for s in ['blob','projected']},
                      current_empty=sum(r['current_entry'] is None for r in results),
                      sd_reference_missing=sum(r['sd_reference_missing'] for r in results),
                      height_441_changes_pure_box=sum(r['height_441_changes_pure_box'] for r in results),
                      training_gt_accepted=False,new_split=False,test_samples_accessed=False)
    save(OUT/'verification.json',verification)
    assert before==after and before_repo==after_repo
    html='<meta charset="utf-8"><title>Sonar projection audit</title><style>body{background:#171b23;color:white;font:18px sans-serif}img{max-width:100%}a{color:#62ddff}</style><h1>Sonar projection chain audit — diagnostic only</h1><p>Fixed 9 development samples. No training GT accepted. Red: current hybrid; yellow: capped projected; green: uncapped extent diagnostic.</p>'
    for r in results:html+=f'<h2>{r["sample"]}</h2><img loading="lazy" src="images/{r["sample"]}.jpg">'
    (OUT/'index.html').write_text(html,encoding='utf-8')
    print(json.dumps(verification,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
