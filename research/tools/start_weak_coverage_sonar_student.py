"""Start only the registered local sonar-S job as a persistent user service."""
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'runs/weak_coverage_sonar_s_student'
proof=json.loads((ROOT/'DataSet/sonar_weak_coverage_trainval/verification.json').read_text())
assert proof['passed'] and proof['teacher_sample_roles_groups_match']
assert json.loads((BASE/'recipe-comparison.json').read_text())['passed']
assert not (BASE/'launch-status.json').exists()
cmd=['systemd-run','--user','--unit=weak-coverage-sonar-s-student','--description=Frozen sonar-only YOLOX-S student baseline',
    '--property=Restart=no','--property=KillMode=control-group','--property=WorkingDirectory='+str(ROOT),
    '--property=StandardOutput=append:'+str(BASE/'service.log'),'--property=StandardError=inherit',
    '--setenv=PYTHONDONTWRITEBYTECODE=1',sys.executable,'-B','-u',str(ROOT/'tools/launch_weak_coverage_sonar_student.py')]
subprocess.run(cmd,check=True)
print(subprocess.check_output(['systemctl','--user','show','weak-coverage-sonar-s-student.service','-p','ActiveState','-p','SubState','-p','MainPID','-p','Restart'],text=True))
