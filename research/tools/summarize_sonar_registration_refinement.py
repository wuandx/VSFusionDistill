"""Close the completed 120-frame experiment without changing source labels."""
from pathlib import Path
import json,hashlib,collections,re,subprocess,urllib.request
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'DataSet/sonar_fixed_registration_refinement'
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    target=OUT/'run-summary.json'
    if target.exists():raise RuntimeError('Preserve completed experiment summary')
    gallery=read(OUT/'gallery-data.json');assert len(gallery)==120 and len({f['sample'] for f in gallery})==120
    recs=collections.Counter(f['recording'] for f in gallery);assert len(recs)==40 and set(recs.values())=={3}
    assert all(f['new_status']!='pending' for f in gallery)
    total={k:dict(collections.Counter(f[k+'_status'] for f in gallery)) for k in ['old','new']}
    grouped={m:{k:dict(collections.Counter(f[k+'_status'] for f in gallery if f['model']==m)) for k in ['old','new']} for m in ['100lbs','incindiary','mortar_shell']}
    role_counts={r:{k:dict(collections.Counter(f[k+'_status'] for f in gallery if f['role']==r)) for k in ['old','new']} for r in ['fit','development_check']}
    paths=[]
    for f in gallery:
        for key in ['raw','comparison']:
            p=OUT/f[key];assert p.is_file();paths.append(p)
    from PIL import Image
    for p in paths:
        with Image.open(p) as im:im.verify()
    source=(OUT/'index.html').read_text('utf-8');js=re.search(r'<script>(.*?)</script>',source,re.S).group(1)
    check=OUT/'gallery-syntax-check.js';check.write_text(js,encoding='utf-8');s=subprocess.run(['node','--check',str(check)],capture_output=True,text=True);assert s.returncode==0,s.stderr
    frozen={m:{'path':str(OUT/m/'freeze-model.json'),'sha256':sha(OUT/m/'freeze-model.json'),'candidate_id':read(OUT/m/'freeze-model.json')['candidate_id']} for m in grouped}
    journal=ROOT/'DataSet/sonar_manual_curation/reviews.jsonl'
    with urllib.request.urlopen('http://127.0.0.1:8765/api/catalog',timeout=10) as r:catalog=json.load(r)
    result=dict(run='sonar_fixed_registration_refinement',status='completed_experiment; overall automatic box quality did not improve enough; not deployed as default',
      recordings=40,frames=120,fit_frames=9,development_check_frames=111,models=frozen,summary=total,by_model=grouped,by_role=role_counts,
      every_recording_counts={r:{k:dict(collections.Counter(f[k+'_status'] for f in gallery if f['recording']==r)) for k in ['old','new']} for r in recs},
      assistant_qa_not_expert_truth=True,not_user_acceptance=True,
      reviewer_boundary='bomb36 independent agent; grenade36 root; mortar36 independent comparisons plus root12 after agent runtime failure; all48 mortar unboxed notes independently saved',
      solver_calls=53340,candidates=9,full_projection_diagnostic=dict(frames=120,empty_7deg=10,empty_full=0,changed_boxes=74,unchanged_boxes=46,visual_spot_checks=6,not_in_main_visual_counts=True),
      verification=dict(image_files_decoded=len(paths),all_images_valid=True,gallery_javascript_syntax=True,gallery_assets_exist=True,physical_alignment_approved=False,
        independent_numeric_file=str(OUT/'expanded-numeric-verification.json'),independent_numeric_sha256=sha(OUT/'expanded-numeric-verification.json')),
      production=dict(review_count=catalog['review_count'],accepted_count=catalog['accepted_count'],journal_exists=journal.exists(),journal_sha256=sha(journal) if journal.exists() else None,new_candidate_deployed=False),
      browser_preview=dict(verified=False,reason='New localhost preview server rejected by automatic approval: blocked by policy. Built-in browser rejects file protocol; no workaround attempted.'),
      new_formal_gt=0,training_runs=0,test_access=False,split_changed=False)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'summary':total,'by_model':grouped,'by_role':role_counts,'production':result['production'],'images_verified':len(paths)},ensure_ascii=False))
if __name__=='__main__':main()
