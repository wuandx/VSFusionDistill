"""Sequential fixed-budget camera-M controls; stop on first failure, no restart."""
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runs/camera_coverage_controls/queue'
REPO=ROOT.parent/'声呐目标检测/code/VSFusionDistill'
def save(v):(OUT/'status.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    OUT.mkdir(parents=True,exist_ok=False)
    stages=[]
    # One M at a time on the 16GB GPU. Preflight must match each variant's inputs/code.
    for variant in ['expanded_plain','original_aug','expanded_aug']:
        for mode in ['preflight','train']:
            stages.append(dict(variant=variant,mode=mode,status='queued'))
    state=dict(status='running',automatic_restart=False,stages=stages,test_content_read=False)
    save(state)
    try:
        for stage in stages:
            variant,mode=stage['variant'],stage['mode'];base=ROOT/'runs/camera_coverage_controls'/variant
            base.mkdir(exist_ok=True)
            proof=base/'preflight/status.json'
            if mode=='preflight' and proof.exists():
                assert json.loads(proof.read_text())['status']=='preflight_passed'
                stage['status']='previous_preflight_available';save(state);continue
            cmd=[sys.executable,'-B','-u',str(ROOT/'tools/run_camera_coverage.py'),'--variant',variant,'--repo',str(REPO),'--checkpoint',str(ROOT/'assets/checkpoints/yolox_m_coco_backbone_neck.pth'),'--work-dir',str(base/mode),'--'+mode]
            stage.update(status='running',command=cmd,log=str(base/(mode+'.log')));save(state)
            with (base/(mode+'.log')).open('x') as log:
                p=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
            stage['returncode']=p.returncode;stage['status']='completed' if p.returncode==0 else 'failed';save(state)
            if p.returncode:raise RuntimeError(f'{variant}/{mode} failed ({p.returncode}); queue stopped')
        state['status']='completed'
    except BaseException as exc:state.update(status='failed',error=repr(exc));raise
    finally:save(state)
if __name__=='__main__':main()
