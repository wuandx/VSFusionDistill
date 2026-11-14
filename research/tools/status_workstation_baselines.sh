#!/bin/bash
for p in /root/wzl/workflow_baselines/runs/*-preflight.log /root/wzl/workflow_baselines/runs/*-train.log /root/wzl/workflow_baselines/runs/*-resume.log; do
  echo "$p"
  tail -n 4 "$p"
done
find /root/wzl/workflow_baselines/runs -name status.json -exec cat {} \;
nvidia-smi --query-gpu=memory.used,memory.free,utilization.gpu --format=csv,noheader
