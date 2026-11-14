#!/bin/bash
set -eu
cd /root/wzl/workflow_baselines
export PYTHONDONTWRITEBYTECODE=1
PY=/root/pby/code/VSFusionDistill/.venv-gpu/bin/python
for mode in camera sonar; do
  "$PY" -u tools/run_workstation_resume.py --modality "$mode" >> "runs/${mode}-resume.log" 2>&1 &
  echo $! > "runs/${mode}-persistent.pid"
done
set +e
for mode in camera sonar; do
  wait "$(cat runs/${mode}-persistent.pid)"
  echo $? > "runs/${mode}-persistent.exit"
done
