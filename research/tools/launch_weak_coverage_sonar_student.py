"""One persistent sonar-S preflight and training; no retry or distillation."""
from pathlib import Path
import json
import subprocess
import sys
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'runs/weak_coverage_sonar_s_student'
REPO=ROOT.parent/'声呐目标检测/code/VSFusionDistill'

def main():
    status=BASE/'launch-status.json';assert not status.exists(),'Preserve attempts'
    state=dict(status='launching',started_at=datetime.now(timezone.utc).isoformat(),single_model='sonar-only YOLOX-S student baseline',
        automatic_restart=False,test_content_read=False,distillation=False,stages=[])
    def save():status.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save()
    try:
        for mode in ['preflight','train']:
            cmd=[sys.executable,'-B','-u',str(ROOT/'tools/run_weak_coverage_sonar_student.py'),'--repo',str(REPO),
                '--checkpoint',str(ROOT/'assets/checkpoints/yolox_s_coco.pth'),'--work-dir',str(BASE/mode),'--mode',mode]
            stage=dict(mode=mode,status='running',command=cmd,log=str(BASE/(mode+'.log')))
            state['stages'].append(stage);state['status']=mode+'_running';save()
            with (BASE/(mode+'.log')).open('x') as log:result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
            stage.update(returncode=result.returncode,status='completed' if result.returncode==0 else 'failed');save()
            if result.returncode:raise RuntimeError(f'{mode} failed; no automatic retry or recipe change')
        state['status']='completed'
    except BaseException as exc:state.update(status='failed',error=repr(exc));raise
    finally:save()

if __name__=='__main__':main()
