import os
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
REPO=Path('/mnt/d/agent_workspace/水下/声呐目标检测/code/VSFusionDistill')
sys.path.insert(0,str(REPO))
sys.path.insert(0,str(ROOT/'tools'))
import torch
torch.set_num_threads(8)
from mmengine.config import Config
from mmengine.runner import Runner
import aodet.datasets, aodet.models, aodet.engine
import camera_baseline_runtime as runtime
from aodet.torch_load_compat import trusted_torch_load
from aodet.cuda_compat import install_nms_cpu_fallback

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--smoke',action='store_true'); args=parser.parse_args()
    name='camera_recording_m'
    work=ROOT/'runs'/name/('preflight' if args.smoke else 'train')
    work.mkdir(parents=True,exist_ok=True)
    cfg=Config.fromfile(str(REPO/'configs/repro_cmold/teachers/t_camera_s_yoloxs.py'))
    data=ROOT/'DataSet/camera_recording_baseline'
    ckpt=ROOT/'assets/checkpoints/yolox_m_coco_backbone_neck.pth'
    for side in ['camera_backbone','sonar_backbone']:
        cfg.model[side].update(deepen_factor=.67,widen_factor=.75)
    for side in ['camera_neck','sonar_neck']:
        cfg.model[side].update(in_channels=[192,384,768],out_channels=192,num_csp_blocks=2)
    cfg.model.camera_head.update(in_channels=192,feat_channels=192)
    cfg.experiment_name='camera_recording_m'
    cfg.known_deviations['initialization_source']='Author YOLOX COCO M converted; S is MMDetection COCO S; capacity is confounded with pretraining source.'
    for side in ['camera_backbone','camera_neck']:
        cfg.model[side].init_cfg.checkpoint=str(ckpt)
    pipeline=[dict(type='AOLoadPaired'),dict(type='AOPairedResize',camera_size=(640,640),keep_ratio=True),dict(type='AOPackPairedInputs')]
    def loader(role,batch,shuffle):
        return dict(batch_size=batch,num_workers=2,persistent_workers=True,sampler=dict(type='DefaultSampler',shuffle=shuffle),
                    collate_fn=dict(type='pseudo_collate'),dataset=dict(type='WorkflowCameraDataset',ann_file=str(data/f'{role}-dataset.json'),pipeline=pipeline,serialize_data=False))
    cfg.train_dataloader=loader('train',8,True)
    # Offline val only. Remove inherited paired loaders and frame split paths.
    cfg.val_dataloader=None; cfg.val_evaluator=None; cfg.val_cfg=None
    cfg.test_dataloader=None; cfg.test_evaluator=None; cfg.test_cfg=None
    cfg.work_dir=str(work); cfg.randomness=dict(seed=0,deterministic=False)
    cfg.custom_hooks=list(cfg.custom_hooks)+[dict(type='FiniteCameraLossHook')]
    cfg.default_hooks.checkpoint=dict(type='CheckpointHook',interval=10,max_keep_ckpts=2,save_last=True)
    cfg.custom_imports=dict(imports=['aodet.datasets','aodet.models','aodet.engine','camera_baseline_runtime'],allow_failed_imports=False)
    cfg.dump(str(work/'resolved_config.py'))
    meta=dict(model_scale='M',initialization_source='YOLOX author COCO M converted backbone/neck',name=name,status='preflight_running' if args.smoke else 'training',seed=0,epochs=200,batch=8,iterations=45000,
              initialized_from=str(ckpt),initialization_sha256=sha(ckpt),source_repo=str(REPO),
              source_git=subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip(),
              torch=torch.__version__,gpu=torch.cuda.get_device_name(0),checkpoint_selection='epoch_200 raw state_dict; EMA separately retained',
              split_protocol_sha256=sha(ROOT/'DataSet/paired_recording_split/protocol.json'),
              train_dataset_sha256=sha(data/'train-dataset.json'),val_dataset_sha256=sha(data/'val-dataset.json'))
    (work/'status.json').write_text(json.dumps(meta,indent=2)+'\n')
    (work/'pip-freeze.txt').write_text(subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True))
    runner=Runner.from_cfg(cfg)
    try:
        with trusted_torch_load():
            if args.smoke:
                runner.model.init_weights()
                pretrained=torch.load(ckpt,map_location='cpu',weights_only=False)['state_dict']
                checks={}
                for side,prefix in [('camera_backbone','backbone.'),('camera_neck','neck.')]:
                    state=getattr(runner.model,side).state_dict()
                    checks[side]=all(torch.equal(v.cpu(),pretrained[prefix+k]) for k,v in state.items())
                assert all(checks.values()), checks
                batch=next(iter(runner.train_dataloader))
                transformed=runner.model.data_preprocessor(batch,training=True)
                assert transformed['inputs']['sonar'] is None
                assert tuple(transformed['inputs']['camera'].shape)==(8,3,384,640)
                runner.model.train()
                losses=runner.model(**transformed,mode='loss')
                loss,logs=runner.model.parse_losses(losses)
                assert torch.isfinite(loss); loss.backward()
                assert all(p.grad is None for p in runner.model.sonar_backbone.parameters())
                assert any(p.grad is not None for p in runner.model.camera_head.parameters())
                runner.model.zero_grad(set_to_none=True)
                install_nms_cpu_fallback()
                val=Runner.build_dataloader(loader('val',2,False),seed=0)
                runner.model.eval()
                with torch.no_grad(): pred=runner.model.test_step(next(iter(val)))
                assert len(pred['camera'])==2
                meta.update(status='preflight_passed',initialization_checks=checks,loss=float(loss.detach()),camera_shape=[8,3,384,640],sonar_input=None,inference_passed=True)
            else:
                runner.train()
                final=work/'epoch_200.pth'
                checkpoint=torch.load(final,map_location='cpu',weights_only=False)
                runner.model.load_state_dict(checkpoint['state_dict'],strict=True)
                install_nms_cpu_fallback()
                val=Runner.build_dataloader(loader('val',8,False),seed=0)
                metrics=runtime.evaluate_val(runner.model,val,data/'val-coco.json',work/'val_raw_epoch200')
                meta.update(status='completed',checkpoint_sha256=sha(final),val_pooled=metrics['pooled'])
    except BaseException as e:
        meta.update(status='failed',error=repr(e)); raise
    finally:
        (work/'status.json').write_text(json.dumps(meta,indent=2)+'\n')

if __name__=='__main__': main()
