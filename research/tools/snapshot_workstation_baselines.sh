#!/bin/bash
set -eu
cd /root/wzl/workflow_baselines
files=(remote-data-verification.json source-sha256.json)
for mode in camera_s_fixed640 sonar_s; do
  for stage in preflight train; do
    files+=(runs/$mode/$stage/status.json runs/$mode/$stage/resolved_config.py)
  done
done
files+=(runs/camera-preflight.log runs/sonar-preflight.log runs/camera-train.log runs/sonar-train.log runs/camera.pid runs/sonar.pid)
tar -cf /mnt/c/Users/Administrator/workstation_baselines_status.tar "${files[@]}"
for mode in camera sonar; do tail -n 2 runs/$mode-train.log; done
