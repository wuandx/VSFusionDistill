from pathlib import Path
import json,hashlib,re,html,ast,subprocess
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'DataSet/gopro_imaging_model';SRC=ROOT/'related_work/gopro-imaging-model'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
meta=read(OUT/'metadata-audit.json');tags=read(OUT/'apriltag-controls.json')
changes=[dict(path=p,old_sha256=h,new_sha256=sha(Path(p))) for p,h in meta['input_hashes'].items() if sha(Path(p))!=h]
assert all(Path(x['path']).name=='gopro-imaging-model-plan.md' for x in changes)
assert all(sha(Path(p))==h for p,h in tags['input_hashes'].items())
assert all(Path(p).stat().st_size==s['bytes'] and Path(p).stat().st_mtime_ns==s['mtime_ns'] for p,s in meta['video_stats'].items())
for name in ['audit_gopro_imaging_model.py','check_independent_apriltag_controls.py','finalize_gopro_imaging_audit.py']:ast.parse((ROOT/'tools'/name).read_text(encoding='utf-8'))
report=ROOT/'复现/camera-baseline/gopro-imaging-model.md'
links=re.findall(r'\]\(([^)]+)\)',report.read_text(encoding='utf-8'));assert all('://' in x or (report.parent/x).resolve().exists() for x in links)
parts=['<!doctype html><html lang="zh"><meta charset="utf-8"><title>GoPro模式与独立控制</title><style>body{max-width:1200px;margin:28px auto;background:#151b22;color:#edf1f5;font:17px system-ui;padding:16px}p{line-height:1.8}img{width:100%}article{margin:30px 0}a{color:#98ceff}</style><h1>GoPro模式与独立几何控制</h1><p>实际镜头模式与水下畸变模型尚未认证；18份视频无可用模式遥测。发现AprilTag立方体，但边长/布置缺实测依据，本轮未估计同步或姿态修正。</p><p><a href="../../复现/camera-baseline/gopro-imaging-model.md">完整报告</a> · <a href="metadata-audit.json">18份元数据</a> · <a href="apriltag-controls.json">全部检测（含阴性）</a></p><p>31张既有开发副本检测，12张阳性=6个身份各SD/FHD；下图为FHD结果，全部为自动检测候选。未使用mesh和旧框。</p>']
for x in tags['outputs']:
    if x['status']=='detected' and x['resolution']=='fhd':
        rel=Path(x['overlay']).relative_to(OUT).as_posix();assert (OUT/rel).exists()
        parts.append('<article><h2>'+html.escape(x['sample'])+' · tag '+str(x['ids'])+'</h2><img loading="lazy" src="'+rel+'"></article>')
parts.append('</html>');(OUT/'index.html').write_text('\n'.join(parts),encoding='utf-8')
status=subprocess.check_output(['git','-C',str(ROOT.parent/'声呐目标检测/code/VSFusionDistill'),'status','--porcelain'],text=True);assert status==''
result=dict(metadata_videos=18,metadata_only=True,images_detected=31,positive_images=12,positive_identities=6,metadata_inputs_unchanged_except_documented_plan_append=True,documented_plan_change=changes,tag_input_hashes_unchanged=True,video_stats_unchanged=True,local_report_links=len(links),report_sha256=sha(report),original_repo_status=status,physical_camera_model_certified=False,sync_pose_certified=False,training_runs=0,formal_gt=0,test_access=False)
(OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
# Capture successful route and retrieval limits, alongside original failed attempt logs.
route=SRC/'paper-route-geomar.html'
(SRC/'supplemental-retrieval.json').write_text(json.dumps(dict(geomar=dict(url='https://oceanrep.geomar.de/id/eprint/61225/',status=200,command='curl.exe --ssl-no-revoke -L --max-time 25',sha256=sha(route),access='landing page only; full text restricted, not fetched'),failed_attempts=['urllib GEOMAR certificate-chain validation','curl default revocation service offline','requests module unavailable','DFKI HTTP403']),indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
