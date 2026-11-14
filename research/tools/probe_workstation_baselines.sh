#!/bin/bash
set -eu
hostname
id
ls -ld /root/wzl /root/wzl/dataset
nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu --format=csv,noheader
ls /root/wzl/VSFusionDistill
ls -d /root/miniconda* /root/anaconda* /opt/conda* /root/wzl/VSFusionDistill/.*venv* 2>/dev/null || true
command -v python || true
ls -a /root
find /root /opt -maxdepth 4 -name python -type f 2>/dev/null | head -15
python3 -c 'import sys,torch,mmcv,mmengine,mmdet; print(sys.executable,torch.__version__,mmcv.__version__,mmengine.__version__,mmdet.__version__); print(torch.cuda.is_available())' || true
find /root/wzl/ckpt /root/.cache/torch/hub/checkpoints -maxdepth 2 -name '*yolox*s*.pth' 2>/dev/null || true
find /root/wzl/VSFusionDistill -name AGENTS.md -o -name CLAUDE.md
git -C /root/wzl/VSFusionDistill rev-parse HEAD
df -h /root/wzl/dataset
