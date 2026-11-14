set -eu
ls -la /root/wzl
df -h /root/wzl
ps -eo pid,args | grep -E 'python|train|systemd' | head -35
ls -ld /root/pby/code/VSFusionDistill/.venv-gpu /root/wzl/workflow_baselines/source
/root/pby/code/VSFusionDistill/.venv-gpu/bin/python -c 'import sys,torch,mmcv,mmengine,mmdet; print(sys.version); print(torch.__version__,mmcv.__version__,mmengine.__version__,mmdet.__version__); print(torch.cuda.get_device_name(0))'
systemctl is-system-running || true
