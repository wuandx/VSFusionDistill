"""Independent full-file/PTS/content checks, following completed recording manifests."""
from pathlib import Path
from collections import Counter
from bisect import bisect_left
from fractions import Fraction
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
import csv
import hashlib
import io
import json
import subprocess
import time
import traceback
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'DataSet/camera_temporal_all'
SOURCE=Path(r'D:\pby\data_processed')
DEST=OUT/'verification'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()


def save(path,obj):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(obj,indent=2),encoding='utf-8');temp.replace(path)


def load_gray(path,expected,log):
    p=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-threads','2','-i',str(path),
        '-vf','scale=160:90','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','gray','pipe:1'],capture_output=True)
    log.write_bytes(p.stderr);assert p.returncode==0
    a=np.frombuffer(p.stdout,np.uint8).reshape((-1,14400)).astype(np.float32)
    assert len(a)==expected
    a-=a.mean(axis=1)[:,None]
    return a


def image_gray(path):
    with Image.open(path) as im:
        assert im.size==(1920,1080)
        a=np.array(im.convert('L').resize((160,90),Image.Resampling.BICUBIC),np.float32).reshape(-1)
    return a-a.mean()


def check_recording(path,expected,paired,match):
    rec=path.parent.name;record=json.loads(path.read_text(encoding='utf-8'));rows=record['items'];summary=record['summary']
    manifest_sha=sha(path);cached=DEST/(rec+'.json')
    if cached.exists():
        old=json.loads(cached.read_text());assert old['recording_manifest_sha256']==manifest_sha
        return old
    assert set(expected)=={r['sample'] for r in rows} and len(rows)==len(expected)
    assert all(sha(Path(k))==v for k,v in record['fixed_inputs_sha256'].items())
    folder=OUT/summary['attempt'];assert len(list((folder/'labels_sd_original').glob('*.json')))==len(rows)
    assert len(list((folder/'comparisons').glob('*.jpg')))==len(rows)
    clip=Path(match['gopro_file']).name
    with (SOURCE/'aris'/rec/(rec+'_frames.csv')).open(encoding='utf-8',newline='') as f:aris=list(csv.DictReader(f))
    assert all(int(r['FrameIndex'])==i for i,r in enumerate(aris))
    s=json.loads((folder/'logs/sd-probe.json').read_text());f=json.loads((folder/'logs/fhd-probe.json').read_text())
    sp=[float(r['best_effort_timestamp_time']) for r in s['frames']];fp=[float(r['best_effort_timestamp_time']) for r in f['frames']]
    assert len(sp)==int(s['streams'][0]['nb_frames']) and len(fp)==int(f['streams'][0]['nb_frames'])
    assert all(b>a for a,b in zip(sp,sp[1:])) and all(b>a for a,b in zip(fp,fp[1:]))
    assert s['streams'][0]['avg_frame_rate']==f['streams'][0]['avg_frame_rate']
    fps=float(Fraction(s['streams'][0]['avg_frame_rate']));period=1/fps
    delta=round((float(f['streams'][0]['start_time'])-float(s['streams'][0]['start_time']))*fps)
    sg=load_gray(SOURCE/'gopro/clips_sd'/clip,len(sp),DEST/(rec+'-sd-decode.stderr'))
    fg=load_gray(SOURCE/'gopro/clips_fhd'/clip,len(fp),DEST/(rec+'-fhd-decode.stderr'))
    onset=int(aris[int(match['aris_onset'])]['FrameTime'])
    output_mse=[];all_pairs=[];pair_mismatches=[]
    for r in rows:
        item=expected[r['sample']]
        assert r['boxes_fhd_xywh']==item['boxes']
        assert sha(Path(r['original_label']))==sha(OUT/r['label_copy'])==r['original_label_sha256_before']==item['annotation_sha256']
        assert sha(Path(r['original_image']))==r['original_image_sha256_before']
        label=json.loads((OUT/r['label_copy']).read_text())
        assert label['class']==r['category']
        assert r['boxes_fhd_xywh']==[[label['x_min']*3,label['y_min']*3,(label['x_max']-label['x_min'])*3,(label['y_max']-label['y_min'])*3]]
        if r['sample'] in paired:
            p=paired[r['sample']];assert p['id']==r['paired_id'] and p['boxes']==r['boxes_fhd_xywh'] and p['split']==r['paired_role']
            assert p['split'] in ['train','val','val_id']
            ph=sha(Path(p['source']));assert ph==r['paired_original_image_sha256_before']
            same=ph==r['original_image_sha256_before'];assert same==r['paired_image_matches_native']
            if not same:pair_mismatches.append(r['sample'])
        else:assert r['paired_id'] is None
        i=int((int(aris[r['aris_frame']]['FrameTime'])-onset)/1e6*fps)+int(match['gopro_offset'])
        assert i==r['sd_index']
        if not 0<=i<len(sp):state='sd_reference_missing'
        else:
            k=bisect_left(fp,sp[i]);near=[j for j in [k-1,k] if 0<=j<len(fp)];j=min(near,key=lambda z:abs(fp[z]-sp[i]))
            residual=abs(fp[j]-sp[i]);assert r['fhd_index']==j
            assert abs(residual-r['time_residual_s'])<1e-10
            if sp[i]<fp[0]-period/2 or sp[i]>fp[-1]+period/2:state='fhd_coverage_missing'
            elif residual>period/2 or i-j!=delta:state='time_pending'
            elif not 0<=i<len(fp):state='old_export_index_missing'
            else:
                lineage=float(np.mean((image_gray(Path(r['original_image']))-fg[i])**2))
                aligned=float(np.mean((sg[i]-fg[j])**2));old=float(np.mean((sg[i]-fg[i])**2))
                assert abs(lineage-r['old_jpg_predicted_index_mse'])<1e-5
                assert abs(aligned-r['sd_to_rebuilt_mse'])<1e-5 and abs(old-r['sd_to_old_mse'])<1e-5
                state='candidate' if lineage<=4 and aligned<=9 else ('lineage_pending' if lineage>4 else 'content_pending')
        assert state==r['status'],(r['sample'],state,r['status'])
        if state=='candidate':
            image=OUT/r['image'];assert sha(image)==r['image_sha256']
            mse=float(np.mean((image_gray(image)-fg[r['fhd_index']])**2))
            assert mse<=9,(r['sample'],'output frame content',mse)
            output_mse.append(mse);all_pairs.append((r['sd_to_rebuilt_mse'],r['sd_to_old_mse']))
        else:assert not r.get('image')
        with Image.open(OUT/r['comparison']) as im:assert im.size==(1440,340)
    good=[r for r in rows if r['status']=='candidate']
    assert len(list((folder/'images').glob('*.jpg')))==len(good)
    fixed=set()
    if good:fixed.update([good[0]['sample'],good[len(good)//2]['sample'],good[-1]['sample']])
    if rec in ['2023-09-21_101622','2023-09-21_103140']:
        fixed.update(r['sample'] for r in good if r['aris_frame'] in ([822] if rec.endswith('101622') else [223,309]))
    sampled=[]
    for r in good:
        if r['sample'] not in fixed:continue
        p=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-threads','2','-i',str(SOURCE/'gopro/clips_fhd'/clip),
            '-vf',f"select=eq(n\\,{r['fhd_index']})",'-frames:v','1','-fps_mode','passthrough','-f','image2pipe','-vcodec','png','pipe:1'],capture_output=True)
        (DEST/(r['sample']+'-single-frame.stderr')).write_bytes(p.stderr);assert p.returncode==0
        with Image.open(io.BytesIO(p.stdout)) as im:exact=np.array(im.convert('RGB'),np.float32)
        with Image.open(OUT/r['image']) as im:exported=np.array(im.convert('RGB'),np.float32)
        mse=float(np.mean((exact-exported)**2));assert mse<64,(r['sample'],mse)
        sampled.append({'sample':r['sample'],'fhd_index':r['fhd_index'],'rgb_mse':mse})
    if good:
        overview=Image.new('RGB',(1440,1020),'#101821')
        for n,r in enumerate([good[0],good[len(good)//2],good[-1]]):
            with Image.open(OUT/r['comparison']) as im:overview.paste(im,(0,n*340))
        overview.save(DEST/(rec+'-overview.jpg'),quality=92)
    result={'recording':rec,'status':'checks_passed','recording_manifest_sha256':manifest_sha,
        'total':len(rows),'status_counts':dict(Counter(r['status'] for r in rows)),
        'all_statuses_recomputed':True,'all_original_labels_and_copies_equal':True,'all_original_inputs_unchanged':True,
        'all_actual_candidate_jpegs_content_checked':len(good),'export_content_mse_max':max(output_mse,default=None),
        'export_content_mse_median':float(np.median(output_mse)) if output_mse else None,
        'paired_total':sum(bool(r['paired_id']) for r in rows),'paired_image_mismatches':pair_mismatches,
        'fps_fraction':s['streams'][0]['avg_frame_rate'],'metadata_delta_frames':delta,
        'sampled_independent_single_frame_decodes':sampled,
        'candidate_content_lower_than_old':sum(a<b for a,b in all_pairs),'candidate_content_equal_to_old':sum(a==b for a,b in all_pairs)}
    save(cached,result);print(json.dumps({k:v for k,v in result.items() if k not in ['sampled_independent_single_frame_decodes','paired_image_mismatches']}),flush=True)
    return result


def main():
    DEST.mkdir(exist_ok=True)
    gallery=json.loads((ROOT/'DataSet/camera_annotation_review/manifest.json').read_text(encoding='utf-8'))
    recs=sorted(gallery['provenance']['approved_recordings']);assert len(recs)==40
    native={x['sample']:x for x in gallery['items'] if x['dataset']=='native' and x['recording'] in recs}
    paired={x['sample']:x for x in gallery['items'] if x['dataset']=='paired' and x['recording'] in recs}
    assert len(native)==26761 and len(paired)==4746 and set(paired)<=set(native)
    with (SOURCE/'matches.csv').open(encoding='utf-8',newline='') as f:matches={r['aris_file'].split('/')[-1]:r for r in csv.DictReader(f) if r['aris_file'].split('/')[-1] in recs}
    scheduled=set();completed=[];errors=[];running={}
    with ThreadPoolExecutor(max_workers=2) as pool:
        while len(completed)+len(errors)<40:
            for rec in recs:
                p=OUT/'recordings'/rec/'manifest.json'
                if rec not in scheduled and p.exists() and len(running)<2:
                    scheduled.add(rec);future=pool.submit(check_recording,p,{k:v for k,v in native.items() if v['recording']==rec},paired,matches[rec]);running[future]=rec
            if running:
                finished,_=wait(running,timeout=2,return_when=FIRST_COMPLETED)
                for f in finished:
                    rec=running.pop(f)
                    try:completed.append(f.result())
                    except Exception:
                        error={'recording':rec,'error':traceback.format_exc()};errors.append(error);print(json.dumps(error),flush=True)
                save(DEST/'progress.json',{'status':'running','verified_recordings':len(completed),'errors':errors})
            else:
                if (OUT/'failures.json').exists() and json.loads((OUT/'failures.json').read_text()):break
                time.sleep(2)
    save(DEST/'errors.json',errors)
    if errors or len(completed)!=40:raise RuntimeError('Verification incomplete or failed; inspect errors and builder state.')
    # Builder may still be writing the aggregate while all per-record manifests exist.
    while not (OUT/'manifest.json').exists():time.sleep(1)
    m=json.loads((OUT/'manifest.json').read_text());assert len(m['items'])==26761
    assert {r['sample'] for r in m['items']}==set(native)
    assert {r['paired_id'] for r in m['items'] if r['paired_id']}=={r['id'] for r in paired.values()}
    identity=m['identity'];assert sha(ROOT/'DataSet/camera_annotation_review/manifest.json')==identity['gallery_sha256']
    assert sha(SOURCE/'matches.csv')==identity['matches_sha256']
    result={'status':'automated_checks_passed','recordings':40,'native_samples':26761,'paired_samples':4746,
        'status_counts':dict(Counter(r['status'] for r in m['items'])),
        'paired_status_counts':dict(Counter(r['status'] for r in m['items'] if r['paired_id'])),
        'all_native_labels_copied_byte_identically':True,'all_fhd_boxes_equal_original_gallery':True,
        'all_statuses_independently_recomputed':True,'all_original_sample_and_fixed_input_hashes_unchanged':True,
        'actual_candidate_jpeg_content_checks':sum(r['all_actual_candidate_jpegs_content_checked'] for r in completed),
        'independent_single_frame_decode_checks':sum(len(r['sampled_independent_single_frame_decodes']) for r in completed),
        'paired_image_mismatches':[s for r in completed for s in r['paired_image_mismatches']],
        'manifest_sha256':sha(OUT/'manifest.json'),'records':sorted(completed,key=lambda x:x['recording']),
        'limit':'Low-resolution content for every candidate; full-resolution single-frame checks are a fixed sample. Neither proves unique neighboring frame identity or all-box manual acceptance. No model metrics.'}
    save(OUT/'verification.json',result);save(DEST/'progress.json',{'status':'complete','recordings':40,'errors':0})
    print('VERIFICATION_COMPLETE '+json.dumps({k:v for k,v in result.items() if k!='records'}),flush=True)


if __name__=='__main__':main()
