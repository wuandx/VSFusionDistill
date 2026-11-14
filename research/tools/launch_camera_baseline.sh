#!/bin/bash
set -eu
task_root=/mnt/d/agent_workspace/水下/声呐目标检测_workflow
mkdir -p "$task_root/runs/camera_recording_baseline"
nohup env PYTHONDONTWRITEBYTECODE=1 /home/ty/mycode/VSFusionDistill/.venv-gpu/bin/python -u "$task_root/tools/run_camera_recording_baseline.py" > "$task_root/runs/camera_recording_baseline/train.log" 2>&1 < /dev/null &
echo $! > "$task_root/runs/camera_recording_baseline/launcher.pid"
cat "$task_root/runs/camera_recording_baseline/launcher.pid"
