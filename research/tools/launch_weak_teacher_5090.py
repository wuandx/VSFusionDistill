"""Sequential immutable preflight + fresh training on the workstation."""
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'runs/weak_coverage_camera_m_teacher'

def main():
    status=BASE/'remote-launch-status.json'
    assert not status.exists(), 'Do not restart or overwrite an existing attempt'
    def record(**values):
        status.write_text(json.dumps(dict(updated_at=datetime.now(timezone.utc).isoformat(),**values),indent=2)+'\n')
    os.environ['PYTHONDONTWRITEBYTECODE']='1'
    os.chdir(ROOT)
    record(status='launching',pid=os.getpid(),fresh_coco=True)
    for mode in ['preflight','train']:
        record(status=mode,pid=os.getpid(),fresh_coco=True)
        cmd=[sys.executable,'-B','-u',str(ROOT/'tools/run_weak_coverage_camera_teacher.py'),
             '--repo',str(ROOT/'source'),'--checkpoint',str(ROOT/'assets/checkpoints/yolox_m_coco_backbone_neck.pth'),
             '--work-dir',str(BASE/mode),'--mode',mode]
        with (BASE/f'{mode}.log').open('x') as log:
            result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:
            record(status='failed',mode=mode,returncode=result.returncode,pid=os.getpid())
            raise SystemExit(result.returncode)
    record(status='completed',pid=os.getpid())

if __name__=='__main__':main()
