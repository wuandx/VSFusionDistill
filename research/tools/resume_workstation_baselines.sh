#!/bin/bash
set -eu
cd /root/wzl/workflow_baselines
if pgrep -f '[p]ython.*tools/run_workstation_(baseline|resume).py' >/dev/null; then
  echo 'Existing training detected; refusing duplicate'; exit 1
fi
cp -n /mnt/c/Users/Administrator/run_workstation_resume.py tools/run_workstation_resume.py
export PYTHONDONTWRITEBYTECODE=1
PY=/root/pby/code/VSFusionDistill/.venv-gpu/bin/python
"$PY" - <<'PYCODE'
import os,subprocess,json
from pathlib import Path
pids={}
for mode in ['camera','sonar']:
    log=Path('runs')/(mode+'-resume.log')
    assert not log.exists(),'Resume log exists; refuse overwrite'
    with log.open('wb') as output:
        p=subprocess.Popen(['/root/pby/code/VSFusionDistill/.venv-gpu/bin/python','-u','tools/run_workstation_resume.py','--modality',mode],stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,start_new_session=True,close_fds=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    pids[mode]=p.pid
Path('runs/resume-pids.json').write_text(json.dumps(pids))
print(pids)
PYCODE
