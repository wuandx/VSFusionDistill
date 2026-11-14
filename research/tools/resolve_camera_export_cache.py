"""Add a separately evidenced EOF-cache lineage branch; preserve initial manifests."""
from pathlib import Path
from bisect import bisect_left
from fractions import Fraction
from collections import Counter
import copy
import csv
import io
import json
import subprocess
import numpy as np
from PIL import Image,ImageFont
from rebuild_camera_temporal_all import OUT,SOURCE,digest,save,video,extract,gray_query,compare,write_viewer


def main():
    base_path=OUT/'manifest.json';verification_path=OUT/'verification.json'
    base=json.loads(base_path.read_text());verified=json.loads(verification_path.read_text())
    assert verified['status']=='automated_checks_passed' and digest(base_path)==verified['manifest_sha256']
    base_sha=digest(base_path);verify_sha=digest(verification_path)
    assert not (OUT/'manifest-resolved.json').exists()
    dest=OUT/'cache_resolution';dest.mkdir();(dest/'logs').mkdir();(dest/'comparisons').mkdir()
    with (SOURCE/'matches.csv').open(encoding='utf-8',newline='') as f:
        matches={r['aris_file'].split('/')[-1]:r for r in csv.DictReader(f)}
    updated=copy.deepcopy(base);rows=updated['items']
    for r in rows:r['initial_status']=r['status']
    pending=[r for r in rows if r['initial_status']=='old_export_index_missing']
    results=[];font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',17)
    for rec in sorted({r['recording'] for r in pending}):
        clip=Path(matches[rec]['gopro_file']).name
        rec_manifest=json.loads((OUT/'recordings'/rec/'manifest.json').read_text())
        assert all(digest(Path(k))==v for k,v in rec_manifest['fixed_inputs_sha256'].items())
        folder=dest/rec;folder.mkdir();(folder/'logs').mkdir();(folder/'comparisons').mkdir()
        ss,sp,sg=video(SOURCE/'gopro/clips_sd'/clip,folder,'sd')
        fs,fp,fg=video(SOURCE/'gopro/clips_fhd'/clip,folder,'fhd')
        fps=float(Fraction(ss['avg_frame_rate']))
        ordered=sorted([r for r in rows if r['recording']==rec],key=lambda r:r['aris_frame'])
        accepted=[]
        for n,r in enumerate(ordered):
            if r['initial_status']!='old_export_index_missing':continue
            proof={'sample':r['sample'],'initial_status':r['initial_status'],'recovered':False}
            if n==0:
                proof['reason']='no previous native sample';results.append(proof);continue
            prev=ordered[n-1];i=r['sd_index'];old=prev['sd_index']
            if not (i==len(fp) and 0<=old<len(fp) and 0<=i<len(sp)):
                proof['reason']='cache preconditions not met';results.append(proof);continue
            assert digest(Path(prev['original_image']))==prev['original_image_sha256_before']
            same=digest(Path(r['original_image']))==digest(Path(prev['original_image']))
            k=bisect_left(fp,sp[i]);near=[j for j in [k-1,k] if 0<=j<len(fp)];j=min(near,key=lambda z:abs(fp[z]-sp[i]))
            residual=float(abs(fp[j]-sp[i]));lineage=float(np.mean((gray_query(Path(r['original_image']))-fg[old])**2))
            aligned=float(np.mean((sg[i]-fg[j])**2))
            proof.update(previous_sample=prev['sample'],old_requested_index=i,previous_requested_index=old,
                original_jpg_equals_previous_bytes=same,cache_lineage_mse=lineage,sd_to_rebuilt_mse=aligned,
                sd_index=i,fhd_index=j,time_residual_s=residual)
            if not (same and lineage<=4 and aligned<=9 and residual<=.5/fps):
                proof['reason']='evidence gate failed';results.append(proof);continue
            assert r['fhd_index']==j
            assert digest(Path(r['original_label']))==r['original_label_sha256_before']
            assert digest(Path(r['original_image']))==r['original_image_sha256_before']
            r.update(status='candidate',recovery_method='verified_previous_export_frame_cache',
                cache_previous_sample=prev['sample'],cache_previous_fhd_index=old,cache_lineage_mse=lineage,
                sd_to_rebuilt_mse=aligned,sd_to_old_mse=float(np.mean((sg[i]-fg[old])**2)))
            accepted.append((r,proof))
        images=extract(SOURCE/'gopro/clips_fhd'/clip,[r['fhd_index'] for r,_ in accepted],folder/'images',folder,'fhd')
        for r,proof in accepted:
            path=images[r['fhd_index']];r['image']=str(path.relative_to(OUT)).replace('\\','/');r['image_sha256']=digest(path)
            actual=gray_query(path);export_mse=float(np.mean((actual-fg[r['fhd_index']])**2));assert export_mse<=9
            command=['ffmpeg','-hide_banner','-loglevel','error','-threads','2','-i',str(SOURCE/'gopro/clips_fhd'/clip),
                '-vf',f"select=eq(n\\,{r['fhd_index']})",'-frames:v','1','-fps_mode','passthrough','-f','image2pipe','-vcodec','png','pipe:1']
            p=subprocess.run(command,capture_output=True);(folder/'logs'/(r['sample']+'-single-frame.stderr')).write_bytes(p.stderr);assert p.returncode==0
            with Image.open(io.BytesIO(p.stdout)) as im:exact=np.array(im.convert('RGB'),np.float32)
            with Image.open(path) as im:actual=np.array(im.convert('RGB'),np.float32)
            rgb_mse=float(np.mean((exact-actual)**2));assert rgb_mse<64
            assert digest(OUT/r['label_copy'])==r['original_label_sha256_before']
            r['comparison']=compare(r,folder,font)
            proof.update(recovered=True,actual_export_gray_mse=export_mse,independent_single_frame_rgb_mse=rgb_mse,
                output_sha256=r['image_sha256'],source_gt_unchanged=True)
            r['cache_evidence']=proof.copy()
            results.append(proof)
        assert all(digest(Path(k))==v for k,v in rec_manifest['fixed_inputs_sha256'].items())
    assert len(rows)==26761 and len({r['sample'] for r in rows})==26761
    assert sum(bool(r['paired_id']) for r in rows)==4746
    original={r['sample']:r for r in base['items']}
    for r in rows:
        before=original[r['sample']]
        assert r['boxes_fhd_xywh']==before['boxes_fhd_xywh'] and r['original_label_sha256_before']==before['original_label_sha256_before']
        if not r.get('recovery_method'):assert r['status']==before['status'] and r.get('image')==before.get('image')
    assert digest(base_path)==base_sha and digest(verification_path)==verify_sha
    updated['revision']='verified_eof_cache_lineage_addition';updated['initial_manifest_sha256']=base_sha
    updated['recordings']=[dict(rec,status_counts=dict(Counter(r['status'] for r in rows if r['recording']==rec['recording'])),
        paired_candidates=sum(bool(r['paired_id']) and r['status']=='candidate' and r.get('paired_image_matches_native') for r in rows if r['recording']==rec['recording']),
        max_time_residual_s=max(r['time_residual_s'] for r in rows if r['recording']==rec['recording'] and r['status']=='candidate'),
        candidate_content_mse_median=float(np.median([r['sd_to_rebuilt_mse'] for r in rows if r['recording']==rec['recording'] and r['status']=='candidate'])),
        old_content_mse_median_same_candidates=float(np.median([r['sd_to_old_mse'] for r in rows if r['recording']==rec['recording'] and r['status']=='candidate']))) for rec in base['recordings']]
    save(OUT/'manifest-resolved.json',updated)
    verification={'status':'automated_checks_passed','initial_manifest_sha256':base_sha,'initial_verification_sha256':verify_sha,
        'final_manifest_sha256':digest(OUT/'manifest-resolved.json'),'native_samples':26761,'paired_samples':4746,
        'status_counts':dict(Counter(r['status'] for r in rows)),
        'paired_status_counts':dict(Counter(r['status'] for r in rows if r['paired_id'])),
        'cache_cases_examined':len(pending),'cache_cases_recovered':sum(p['recovered'] for p in results),'proofs':results,
        'all_gt_unchanged':True,'initial_manifests_unchanged':True,
        'limit':'Adds EOF-boundary cases with byte-identical previous-native JPEG and valid source-frame lineage. Consistent with cache reuse, not unique reconstruction of historical intervening export requests. Does not fill real time coverage gaps or accept every bbox.'}
    save(OUT/'verification-resolved.json',verification)
    with (OUT/'correspondence-resolved.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['sample','recording','category','aris_frame','sd_index','sd_pts','fhd_index','fhd_pts','time_residual_s','initial_status','status',
            'recovery_method','cache_previous_sample','cache_lineage_mse','sd_to_rebuilt_mse','paired_id','paired_role']
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    (OUT/'index-initial.html').write_bytes((OUT/'index.html').read_bytes())
    write_viewer(rows)
    print(json.dumps(verification),flush=True)


if __name__=='__main__':main()
