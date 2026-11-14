"""Verify source-catalog conclusions and local links; no dataset member access."""
from pathlib import Path
import json,hashlib,re,subprocess
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/'related_work/gopro-control-records'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
names=read(SRC/'processed-archive-paths.json');summary=read(SRC/'processed-archive-summary.json')
assert len(names)==summary['paths']==198915
yaml=[x for x in names if x.endswith('.yaml')];assert len(yaml)==210 and all('/aris/' in x for x in yaml)
assert summary['record_candidates']==[] and summary['members_extracted']==0
assert len(read(SRC/'dfki-repos.json'))==68 and len(read(SRC/'ndahn-repos.json'))==24
for logname in ['retrieval-log.json','supplemental-retrieval.json']:
    for e in read(SRC/logname):
        if 'sha256' in e:
            if 'local_file' in e:p=SRC/e['local_file']
            else:
                url=e['url'];p=SRC/({'uxo+calibration':'search-uxo.json','oceans+user:dfki-ric':'search-paper.json'}[next(k for k in ['uxo+calibration','oceans+user:dfki-ric'] if k in url)])
            assert sha(p)==e['sha256']
prior=read(ROOT/'DataSet/gopro_imaging_model/apriltag-controls.json')
assert all(sha(Path(p))==h for p,h in prior['input_hashes'].items())
meta=read(ROOT/'DataSet/gopro_imaging_model/metadata-audit.json')
assert all(Path(p).stat().st_size==v['bytes'] and Path(p).stat().st_mtime_ns==v['mtime_ns'] for p,v in meta['video_stats'].items())
report=ROOT/'复现/camera-baseline/gopro-control-records.md';links=re.findall(r'\]\(([^)]+)\)',report.read_text(encoding='utf-8'))
assert all('://' in x or (report.parent/x).resolve().exists() for x in links)
repo=ROOT.parent/'声呐目标检测/code/VSFusionDistill'
head=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
status=subprocess.check_output(['git','-C',str(repo),'status','--porcelain'],text=True);assert not status
files=[report,ROOT/'experiment/gopro-control-records-plan.md']+[p for p in SRC.iterdir() if p.is_file() and p.name!='verification.json']
result=dict(archive_paths_verified=len(names),archive_members_extracted=0,source_snapshots_verified=True,prior_tag_input_hashes_unchanged=True,prior_video_stats_unchanged=True,report_links_verified=len(links),original_repo_head=head,original_repo_status=status,records_obtained=False,messages_sent=0,new_image_access=0,training_runs=0,new_gt=0,new_split=0,test_content_access=False,file_hashes={str(p.relative_to(ROOT)):sha(p) for p in files})
(SRC/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('Verified archive paths, source hashes, prior controls and video stats,',len(links),'report links; original repo clean.')
