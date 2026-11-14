#!/bin/bash
date '+%F %T %Z'
uptime
pgrep -af run_workstation_baseline || true
for run in camera_s_fixed640 sonar_s; do
  echo "$run"
  ls -lh /root/wzl/workflow_baselines/runs/$run/train/epoch_*.pth
  cat /root/wzl/workflow_baselines/runs/$run/train/last_checkpoint
  tail -n 8 /root/wzl/workflow_baselines/runs/$run/train/*.log 2>/dev/null || true
done
dmesg -T 2>/dev/null | grep -Ei 'out of memory|killed process|oom' | tail -n 5 || true
