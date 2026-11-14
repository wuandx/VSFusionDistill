import os
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT/'source'
sys.path.insert(0,str(REPO))
sys.path.insert(0,str(ROOT/'tools'))
import torch
torch.set_num_threads(8)
from mmengine.config import Config
from mmengine.runner import Runner
import aodet.datasets, aodet.models, aodet.engine
import camera_baseline_runtime as runtime
import workstation_baseline_runtime
from aodet.torch_load_compat import trusted_torch_load
from aodet.cuda_compat import install_nms_cpu_fallback

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

class BranchAdapter:
    def __init__(self,model,branch): self.model=model; self.branch=branch
    def eval(self): self.model.eval()
    def test_step(self,batch): return {'camera':self.model.test_step(batch)[self.branch]}

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--smoke',action='store_true'); parser.add_argument('--modality',choices=['camera','sonar'],required=True); args=parser.parse_args()
    name='camera_s_fixed640' if args.modality=='camera' else 'sonar_s'
    branch='camera' if args.modality=='camera' else 'sonar_uncoupled'
    work=ROOT/'runs'/name/('preflight' if args.smoke else 'train')
    work.mkdir(parents=True,exist_ok=True)
    cfg=Config.fromfile(str(REPO/'configs/repro_cmold/teachers/t_camera_s_yoloxs.py'))
    data=Path('/root/wzl/dataset/paired_recording_trainval')
    ckpt=Path('/root/.cache/torch/hub/checkpoints/yolox_s_8x8_300e_coco_20211121_095711-4592a793.pth')
    for side in ['camera_backbone','camera_neck']:
        cfg.model[side].init_cfg.checkpoint=str(ckpt)
    if args.modality=='sonar':
        model=cfg.model
        model.sonar_backbone.init_cfg=model.camera_backbone.init_cfg
        model.sonar_neck.init_cfg=model.camera_neck.init_cfg
        model.uncoupled_sonar_head=model.camera_head
        model.camera_backbone=None; model.camera_neck=None; model.camera_head=None
        model.loss_weights=dict(camera=0.,fused_sonar=0.,uncoupled_sonar=1.)
    cfg.experiment_name=name
    pipeline=[dict(type='AOLoadPaired'),dict(type='AOPairedResize',**{args.modality+'_size':(640,640)},keep_ratio=True),dict(type='AOPackPairedInputs'),dict(type='WorkflowFixedCanvas')]
    def loader(role,batch,shuffle):
        return dict(batch_size=batch,num_workers=2,persistent_workers=True,sampler=dict(type='DefaultSampler',shuffle=shuffle),
                    collate_fn=dict(type='pseudo_collate'),dataset=dict(type='WorkflowCameraDataset',ann_file=str(data/f'{args.modality}-{role}-dataset.json'),pipeline=pipeline,serialize_data=False))
    cfg.train_dataloader=loader('train',8,True)
    # Offline val only. Remove inherited paired loaders and frame split paths.
    cfg.val_dataloader=None; cfg.val_evaluator=None; cfg.val_cfg=None
    cfg.test_dataloader=None; cfg.test_evaluator=None; cfg.test_cfg=None
    cfg.work_dir=str(work); cfg.randomness=dict(seed=0,deterministic=False)
    cfg.custom_hooks=list(cfg.custom_hooks)+[dict(type='FiniteCameraLossHook')]
    cfg.default_hooks.checkpoint=dict(type='CheckpointHook',interval=10,max_keep_ckpts=2,save_last=True)
    cfg.custom_imports=dict(imports=['aodet.datasets','aodet.models','aodet.engine','camera_baseline_runtime','workstation_baseline_runtime'],allow_failed_imports=False)
    assert not args.smoke, 'Resume is training only'
    resume_path=work/'epoch_50.pth'
    checkpoint=torch.load(resume_path,map_location='cpu',weights_only=False)
    assert checkpoint['meta']['epoch']==50 and checkpoint['meta']['iter']==11250
    assert all(k in checkpoint for k in ['optimizer','param_schedulers','ema_state_dict','state_dict'])
    assert int(checkpoint['ema_state_dict']['steps'])==11250
    resume_hash=sha(resume_path)
    del checkpoint
    cfg.resume=True
    cfg.load_from=str(resume_path)
    cfg.dump(str(work/'resume_config.py'))
    meta=dict(name=name,status='preflight_running' if args.smoke else 'training',seed=0,epochs=200,batch=8,iterations=45000,
              initialized_from=str(ckpt),initialization_sha256=sha(ckpt),source_repo=str(REPO),
              source_git='4fadd06829c6c738977639a55b6e44ad0e35ac44 (local source snapshot; per-file hashes saved)',
              torch=torch.__version__,gpu=torch.cuda.get_device_name(0),checkpoint_selection='epoch200 raw from ema_state_dict module.*; state_dict is EMA',
              split_protocol_sha256=sha(data/'trainval-members.json'),
              train_dataset_sha256=sha(data/f'{args.modality}-train-dataset.json'),val_dataset_sha256=sha(data/f'{args.modality}-val-dataset.json'))
    meta.update(resume_from=str(resume_path),resume_checkpoint_sha256=resume_hash,resume_epoch=50,resume_iter=11250)
    if (work/'status.json').exists():
        import shutil
        shutil.copy2(work/'status.json',work/'status_before_resume.json')
    (work/'status.json').write_text(json.dumps(meta,indent=2)+'\n')
    (work/'resume-pip-freeze.txt').write_text(subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True))
    runner=Runner.from_cfg(cfg)
    try:
        with trusted_torch_load():
            if args.smoke:
                runner.model.init_weights()
                pretrained=torch.load(ckpt,map_location='cpu',weights_only=False)['state_dict']
                checks={}
                for side,prefix in [(args.modality+'_backbone','backbone.'),(args.modality+'_neck','neck.')]:
                    state=getattr(runner.model,side).state_dict()
                    checks[side]=all(torch.equal(v.cpu(),pretrained[prefix+k]) for k,v in state.items())
                assert all(checks.values()), checks
                batch=next(iter(runner.train_dataloader))
                transformed=runner.model.data_preprocessor(batch,training=True)
                assert transformed['inputs']['sonar' if args.modality=='camera' else 'camera'] is None
                assert tuple(transformed['inputs'][args.modality].shape)==(8,3,640,640)
                for ds in transformed['data_samples'][args.modality]:
                    sx,sy=ds.metainfo['scale_factor']
                    assert sx>0 and sy>0
                    if args.modality=='camera': assert (sx,sy)==(1.,1.)
                    assert torch.isfinite(ds.gt_instances.bboxes).all()
                    assert tuple(ds.metainfo['ori_shape'])==(360,640) if args.modality=='camera' else True
                runner.model.train()
                losses=runner.model(**transformed,mode='loss')
                loss,logs=runner.model.parse_losses(losses)
                assert torch.isfinite(loss); loss.backward()
                assert all(p.grad is None for p in runner.model.sonar_backbone.parameters()) if args.modality=='camera' else True
                assert any(p.grad is not None for p in getattr(runner.model,'camera_head' if args.modality=='camera' else 'uncoupled_sonar_head').parameters())
                runner.model.zero_grad(set_to_none=True)
                install_nms_cpu_fallback()
                val=Runner.build_dataloader(loader('val',2,False),seed=0)
                runner.model.eval()
                with torch.no_grad(): pred=runner.model.test_step(next(iter(val)))
                assert len(pred[branch])==2
                meta.update(status='preflight_passed',initialization_checks=checks,loss=float(loss.detach()),input_shape=[8,3,640,640],modality=args.modality,inference_passed=True)
            else:
                runner.train()
                final=work/'epoch_200.pth'
                checkpoint=torch.load(final,map_location='cpu',weights_only=False)
                raw={k[7:]:v for k,v in checkpoint['ema_state_dict'].items() if k.startswith('module.')}
                runner.model.load_state_dict(raw,strict=True)
                torch.save(dict(state_dict=raw),work/'raw_epoch_200.pth')
                install_nms_cpu_fallback()
                val=Runner.build_dataloader(loader('val',8,False),seed=0)
                metrics=runtime.evaluate_val(BranchAdapter(runner.model,branch),val,data/f'{args.modality}-val-coco.json',work/'val_raw_epoch200')
                meta.update(status='completed',checkpoint_sha256=sha(final),val_pooled=metrics['pooled'])
    except BaseException as e:
        meta.update(status='failed',error=repr(e)); raise
    finally:
        (work/'status.json').write_text(json.dumps(meta,indent=2)+'\n')

if __name__=='__main__': main()
