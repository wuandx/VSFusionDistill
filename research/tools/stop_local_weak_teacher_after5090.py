"""Stop only this local attempt after verified remote optimizer progress."""
import json,subprocess
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'runs/weak_coverage_camera_m_teacher'
OUT=ROOT/'DataSet/weak_coverage_camera_m_5090_deployment'
proof=json.loads((OUT/'startup-verification.json').read_text())
assert proof['passed'] and proof['last_iteration']['iteration']>=100
record=BASE/'migration-to5090.json';assert not record.exists()
unit='weak-coverage-camera-m-teacher.service'
before=subprocess.check_output(['systemctl','--user','show',unit,'-p','MainPID','-p','ActiveState','-p','ExecStart'],text=True)
pid=int(subprocess.check_output(['systemctl','--user','show',unit,'-p','MainPID','--value'],text=True))
cmd=Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0',b' ').decode()
assert 'launch_weak_coverage_camera_teacher.py' in cmd,cmd
latest=[x for x in (BASE/'train.log').read_text().splitlines() if 'Epoch(train)' in x][-1]
status_before={k:json.loads((BASE/k).read_text()) for k in ['train/status.json','launch-status.json']}
subprocess.run(['systemctl','--user','stop',unit],check=True)
after=subprocess.check_output(['systemctl','--user','show',unit,'-p','MainPID','-p','ActiveState','-p','SubState'],text=True)
assert 'ActiveState=inactive' in after and 'MainPID=0' in after,after
now=datetime.now(timezone.utc).isoformat()
for name,meta in status_before.items():
    meta.update(status='stopped_deployed_to5090',stopped_at=now,remote_run='/root/wzl/weak_coverage_camera_m_teacher/runs/weak_coverage_camera_m_teacher',
        migration_mode='remote fresh COCO run; local attempt retained, not resumed')
    (BASE/name).write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
evidence=dict(stopped_at=now,unit=unit,before=before,cmdline=cmd,after=after,last_local_iteration=latest,
    completed_checkpoints=[p.name for p in (BASE/'train').glob('epoch_*.pth')],
    remote_verified_iteration=proof['last_iteration'],status_before=status_before)
record.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in evidence.items() if k!='status_before'},ensure_ascii=False))
