"""Single persistent camera-M preflight then training; stop on failure, no restart."""
from pathlib import Path
import json
import subprocess
import sys
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'runs/weak_coverage_camera_m_teacher'
REPO=ROOT.parent/'声呐目标检测/code/VSFusionDistill'


def save(state):
    (BASE/'launch-status.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    assert not (BASE/'launch-status.json').exists()
    state=dict(status='preflight_running',started_at=datetime.now(timezone.utc).isoformat(),
        single_model='camera-only YOLOX-M teacher',automatic_restart=False,test_content_read=False,stages=[])
    save(state)
    try:
        for mode in ['preflight','train']:
            cmd=[sys.executable,'-B','-u',str(ROOT/'tools/run_weak_coverage_camera_teacher.py'),
                '--repo',str(REPO),'--checkpoint',str(ROOT/'assets/checkpoints/yolox_m_coco_backbone_neck.pth'),
                '--work-dir',str(BASE/mode),'--mode',mode]
            stage=dict(mode=mode,status='running',command=cmd,log=str(BASE/(mode+'.log')))
            state['stages'].append(stage);state['status']=mode+'_running';save(state)
            with (BASE/(mode+'.log')).open('x') as log:
                result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
            stage.update(returncode=result.returncode,status='completed' if result.returncode==0 else 'failed');save(state)
            if result.returncode:raise RuntimeError(f'{mode} failed; no automatic retry or recipe change')
        state['status']='completed'
    except BaseException as exc:state.update(status='failed',error=repr(exc));raise
    finally:save(state)


if __name__=='__main__':main()
