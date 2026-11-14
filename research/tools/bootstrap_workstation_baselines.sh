#!/bin/bash
set -eu
BASE=/root/wzl
ARCHIVE=/mnt/c/Users/Administrator/workstation_baselines.tar
actual=$(sha256sum "$ARCHIVE" | cut -d ' ' -f 1)
[ "$actual" = "ddc769685797b636ae1cc692f72ca2f3d037c93f6a33d8f9890a730937eae666" ]
[ ! -e "$BASE/workflow_baselines" ]
[ ! -e "$BASE/dataset/paired_recording_trainval" ]
tar -xf "$ARCHIVE" -C "$BASE"
export PYTHONDONTWRITEBYTECODE=1
PY=/root/pby/code/VSFusionDistill/.venv-gpu/bin/python
"$PY" /mnt/c/Users/Administrator/verify_workstation_package.py
bash "$BASE/workflow_baselines/tools/launch_workstation_baselines.sh"
cat "$BASE/workflow_baselines/runs/camera.pid" "$BASE/workflow_baselines/runs/sonar.pid"
