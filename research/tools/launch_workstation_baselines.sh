#!/bin/bash
set -eu
cd /root/wzl/workflow_baselines
export PYTHONDONTWRITEBYTECODE=1
PY=/root/pby/code/VSFusionDistill/.venv-gpu/bin/python
mkdir -p runs
for mode in camera sonar; do
  "$PY" tools/run_workstation_baseline.py --modality "$mode" --smoke > "runs/${mode}-preflight.log" 2>&1
done
for mode in camera sonar; do
  nohup "$PY" -u tools/run_workstation_baseline.py --modality "$mode" > "runs/${mode}-train.log" 2>&1 < /dev/null &
  echo $! > "runs/${mode}.pid"
done
