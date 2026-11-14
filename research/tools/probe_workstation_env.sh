#!/bin/bash
set -eu
/root/pby/code/VSFusionDistill/.venv-gpu/bin/python -c 'import sys,torch,mmcv,mmengine,mmdet; print(sys.executable,torch.__version__,mmcv.__version__,mmengine.__version__,mmdet.__version__); print(torch.cuda.is_available()); print((torch.ones(2,device="cuda")*2).cpu())'
sha256sum /root/.cache/torch/hub/checkpoints/yolox_s*.pth
