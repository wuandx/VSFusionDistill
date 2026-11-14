"""Independent checks of pilot files, timestamps and sampled decoded frame identity."""
from pathlib import Path
from collections import Counter
from bisect import bisect_left
from fractions import Fraction
import csv
import hashlib
import io
import json
import subprocess
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'DataSet/camera_temporal_pilot_rebuilt'
SOURCE=Path(r'D:\pby\data_processed')


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(4*1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    m=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    g=json.loads((ROOT/'DataSet/camera_annotation_review/manifest.json').read_text(encoding='utf-8'))
    expected={x['sample']:x for x in g['items'] if x['dataset']=='native' and x['recording'] in ['2023-09-21_101622','2023-09-21_103140']}
    assert len(expected)==len(m['items'])==1482
    assert set(expected)=={x['sample'] for x in m['items']}
    assert len({x['sample'] for x in m['items']})==1482
    assert all(sha(Path(k))==v for k,v in m['fixed_inputs_sha256'].items())
    assert {x['paired_role'] for x in m['items']}<={None,'train','val','val_id'}
    candidates=[x for x in m['items'] if x['status']=='candidate']
    assert len(list((OUT/'images').glob('*/*.jpg')))==len(candidates)
    assert len(list((OUT/'labels_sd_original').glob('*/*.json')))==1482
    assert len(list((OUT/'comparisons').glob('*.jpg')))==1482
    with (SOURCE/'matches.csv').open(encoding='utf-8',newline='') as f:
        matches={r['aris_file'].split('/')[-1]:r for r in csv.DictReader(f)}
    per_rec=[];sampled=[]
    for rec in ['2023-09-21_101622','2023-09-21_103140']:
        match=matches[rec];clip=Path(match['gopro_file']).name
        with (SOURCE/'aris'/rec/(rec+'_frames.csv')).open(encoding='utf-8',newline='') as f:
            aris=list(csv.DictReader(f))
        assert all(int(r['FrameIndex'])==i for i,r in enumerate(aris)), 'iloc/key equivalence'
        s=json.loads((OUT/'logs'/(rec+'-sd-probe.json')).read_text())
        f=json.loads((OUT/'logs'/(rec+'-fhd-probe.json')).read_text())
        sp=[float(r['best_effort_timestamp_time']) for r in s['frames']]
        fp=[float(r['best_effort_timestamp_time']) for r in f['frames']]
        fps=float(Fraction(s['streams'][0]['avg_frame_rate']))
        onset=int(aris[int(match['aris_onset'])]['FrameTime'])
        rows=[r for r in m['items'] if r['recording']==rec]
        for r in rows:
            assert r['boxes_fhd_xywh']==expected[r['sample']]['boxes']
            assert sha(Path(r['original_label']))==sha(OUT/r['label_copy'])==r['original_label_sha256_before']==expected[r['sample']]['annotation_sha256']
            assert sha(Path(r['original_image']))==r['original_image_sha256_before']
            original=json.loads((OUT/r['label_copy']).read_text())
            assert original['class']==r['category']
            i=int((int(aris[r['aris_frame']]['FrameTime'])-onset)/1e6*fps)+int(match['gopro_offset'])
            assert i==r['sd_index']
            if r['status']=='candidate':
                k=bisect_left(fp,sp[i]);neighbors=[j for j in [k-1,k] if 0<=j<len(fp)]
                j=min(neighbors,key=lambda z:abs(fp[z]-sp[i]))
                assert j==r['fhd_index'] and abs(fp[j]-sp[i])<=.5/fps
                assert abs(r['time_residual_s']-abs(fp[j]-sp[i]))<1e-10
                assert sha(OUT/r['image'])==r['image_sha256']
                with Image.open(OUT/r['image']) as im:
                    assert im.size==(1920,1080)
        good=[r for r in rows if r['status']=='candidate']
        fixed={good[0]['sample'],good[len(good)//2]['sample'],good[-1]['sample']}
        fixed.update(r['sample'] for r in good if r['aris_frame'] in ([822] if rec.endswith('101622') else [223,309]))
        for r in good:
            if r['sample'] not in fixed:
                continue
            command=['ffmpeg','-hide_banner','-loglevel','error','-i',str(SOURCE/'gopro/clips_fhd'/clip),
                     '-vf',f"select=eq(n\\,{r['fhd_index']})",'-frames:v','1','-fps_mode','passthrough',
                     '-f','image2pipe','-vcodec','png','pipe:1']
            result=subprocess.run(command,capture_output=True)
            (OUT/'logs'/(r['sample']+'-independent-frame.stderr')).write_bytes(result.stderr)
            assert result.returncode==0
            with Image.open(io.BytesIO(result.stdout)) as im:
                exact=np.asarray(im.convert('RGB'),dtype=np.float32)
            with Image.open(OUT/r['image']) as im:
                exported=np.asarray(im.convert('RGB'),dtype=np.float32)
            mse=float(np.mean((exact-exported)**2))
            assert mse<64,(r['sample'],mse)
            sampled.append({'sample':r['sample'],'fhd_index':r['fhd_index'],'export_vs_independently_decoded_frame_rgb_mse':mse,
                            'verification':'independent single-frame PNG decode vs saved JPEG; compression tolerance 64'})
        per_rec.append({'recording':rec,'total':len(rows),'status_counts':dict(Counter(r['status'] for r in rows)),
                        'paired_total':sum(bool(r['paired_id']) for r in rows),
                        'paired_candidates':sum(bool(r['paired_id']) and r['status']=='candidate' for r in rows),
                        'candidate_mse_median':float(np.median([r['sd_to_rebuilt_mse'] for r in good])),
                        'old_mse_median_same_candidate_samples':float(np.median([r['sd_to_old_mse'] for r in good])),
                        'candidate_content_lower_than_old':sum(r['sd_to_rebuilt_mse']<r['sd_to_old_mse'] for r in good),
                        'max_time_residual_s':max(r['time_residual_s'] for r in good),
                        'csv_FrameIndex_equals_row_number':True})
    overview=Image.new('RGB',(1440,340*6),'#101821')
    for k,rec in enumerate(['2023-09-21_101622','2023-09-21_103140']):
        good=[r for r in candidates if r['recording']==rec]
        for n,r in enumerate([good[0],good[len(good)//2],good[-1]]):
            with Image.open(OUT/r['comparison']) as im:
                overview.paste(im,(0,(k*3+n)*340))
    overview.save(OUT/'verification-overview.jpg',quality=93)
    result={'status':'automated_checks_passed','samples':1482,'candidate_images':len(candidates),
            'all_labels_copied_byte_identically':True,'all_fhd_boxes_equal_original_gallery':True,
            'all_original_sample_inputs_hash_unchanged':True,'fixed_inputs_hash_unchanged':True,
            'manifest_sha256':sha(OUT/'manifest.json'),'independent_script_sha256':sha(Path(__file__)),
            'recordings':per_rec,'independently_decoded_export_checks':sampled,
            'limit':'Timestamp/content reconstruction checks; not manual acceptance of every bbox or model performance validation.'}
    (OUT/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    main()
