#!/bin/bash
for mode in camera sonar; do
  echo "$mode"
  tail -n 5 /root/wzl/workflow_baselines/runs/$mode-resume.log
  grep -E 'resum|Epoch.train' /root/wzl/workflow_baselines/runs/$mode-resume.log | tail -n 3
done
pgrep -af '[p]ython.*run_workstation_resume'
nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader
