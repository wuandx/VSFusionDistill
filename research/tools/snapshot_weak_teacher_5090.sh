set -eu
/root/pby/code/VSFusionDistill/.venv-gpu/bin/python - <<'PY'
from pathlib import Path
import json,subprocess
from importlib.metadata import version
from datetime import datetime,timezone
root=Path('/root/wzl/weak_coverage_camera_m_teacher')
base=root/'runs/weak_coverage_camera_m_teacher'
result=dict(captured_at=datetime.now(timezone.utc).isoformat(),remote_root=str(root))
result['package_versions']={n:version(n) for n in ['torch','torchvision','mmcv','mmengine','mmdet','numpy','pycocotools','pillow']}
for name,path in [('deployment',root/'deployment-verification.json'),('launch',base/'remote-launch-status.json'),('preflight',base/'preflight/status.json'),('train',base/'train/status.json')]:
    result[name]=json.loads(path.read_text()) if path.exists() else None
for name in ['preflight','train']:
    path=base/f'{name}.log'
    lines=path.read_text(errors='replace').splitlines() if path.exists() else []
    result[name+'_last_logs']=lines[-10:]
    if name=='train':result['iteration_logs']=[x for x in lines if 'Epoch(train)' in x][-20:]
result['nvidia_smi']=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.used,utilization.gpu','--format=csv,noheader'],text=True).strip()
result['processes']=subprocess.check_output(['ps','-eo','pid,ppid,args'],text=True).splitlines()
result['processes']=[x for x in result['processes'] if 'launch_weak_teacher_5090.py' in x or 'run_weak_coverage_camera_teacher.py' in x]
result['preflight_pip_freeze']=(base/'preflight/pip-freeze.txt').read_text() if (base/'preflight/pip-freeze.txt').exists() else None
result['resolved_config']=(base/'train/resolved_config.py').read_text() if (base/'train/resolved_config.py').exists() else None
print(json.dumps(result,ensure_ascii=False,indent=2))
PY
