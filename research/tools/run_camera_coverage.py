"""Fixed 61800-update camera-M coverage/augmentation controls, train/val only."""
import os
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
import math
import subprocess
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import run_scene_baseline as baseline
from prepare_scene_baselines import sha,dump

def main():
    p=argparse.ArgumentParser();p.add_argument('--variant',choices=['original_plain','original_aug','expanded_plain','expanded_aug'],required=True)
    p.add_argument('--repo',type=Path,required=True);p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--work-dir',type=Path,required=True)
    p.add_argument('--preflight',action='store_true');p.add_argument('--train',action='store_true');a=p.parse_args();assert a.preflight!=a.train
    out=a.work_dir.resolve();assert not out.exists();sys.path.insert(0,str(a.repo.resolve()))
    import torch
    torch.set_num_threads(8)
    from mmengine.runner import Runner
    import aodet.datasets,aodet.models,aodet.engine
    import camera_baseline_runtime,scene_baseline_runtime,camera_coverage_runtime
    from aodet.torch_load_compat import trusted_torch_load
    from aodet.cuda_compat import install_nms_cpu_fallback
    original=ROOT/'DataSet/scene_expanded_baseline_trainval';expanded=ROOT/'DataSet/camera_more_recordings_trainval_verified'
    data=expanded if a.variant.startswith('expanded') else original
    verification=json.loads((data/'verification.json').read_text(encoding='utf-8'));assert verification['passed']
    filehash=json.loads((data/'files-sha256.json').read_text(encoding='utf-8'))
    # Revalidate the full camera inputs, including all copied pixels, before starting.
    rows={role:json.loads((data/f'camera-{role}-dataset.json').read_text(encoding='utf-8')) for role in ['train','val']}
    for role,rs in rows.items():
        assert sha(data/f'camera-{role}-dataset.json')==filehash[f'camera-{role}-dataset.json']
        assert sha(data/f'camera-{role}-coco.json')==filehash[f'camera-{role}-coco.json']
        for r in rs:assert sha(data/r['fp_camera'])==r['source_image_sha256']
    args=argparse.Namespace(repo=a.repo,data=original,modality='camera',checkpoint=a.checkpoint,workers=2,work_dir=out)
    cfg,_=baseline.configure(args)
    aug=a.variant.endswith('_aug')
    trainpipe=deepcopy(cfg.train_dataloader.dataset.pipeline)
    if aug:trainpipe.insert(1,dict(type='CameraCoverageAugment'))
    def loader(role,shuffle):
        spec=deepcopy(cfg.train_dataloader)
        spec['dataset']['ann_file']=str(data/f'camera-{role}-dataset.json')
        spec['dataset']['pipeline']=trainpipe if role=='train' else deepcopy(cfg.train_dataloader.dataset.pipeline)
        # cfg.train_dataloader itself receives the augmented pipeline later: freeze val explicitly.
        if role=='val':spec['dataset']['pipeline']=[dict(type='AOLoadPaired'),dict(type='AOPairedResize',camera_size=(640,640),keep_ratio=True),dict(type='AOPackPairedInputs'),dict(type='SceneFixedCanvas')]
        spec['sampler']=dict(type='CameraCoverageSampler',shuffle=True,seed=0,num_samples=2472) if role=='train' and shuffle else dict(type='DefaultSampler',shuffle=False)
        return spec
    cfg.train_dataloader=loader('train',True)
    for h in cfg.custom_hooks:
        if h['type']=='ScenePeriodicValHook':h['data_root']=str(data)
    cfg.custom_imports.imports.append('camera_coverage_runtime')
    cfg.experiment_name='camera_coverage_'+a.variant
    cfg.known_deviations.update(data='camera-only original or 9-recording expansion',sampling='2472 unique samples per epoch, seeded randperm; 309 updates x200 epochs',augmentation=aug)
    cfg.work_dir=str(out)
    out.mkdir(parents=True);cfg.dump(str(out/'resolved_config.py'))
    meta=dict(name=cfg.experiment_name,status='configured',variant=a.variant,unique_train_images=len(rows['train']),val_images=894,samples_per_epoch=2472,steps_per_epoch=309,epochs=200,total_updates=61800,seed=0,batch=8,augmentation=aug,data_sha256=sha(data/'files-sha256.json'),initialization_sha256=sha(a.checkpoint),test_content_read=False,source_sha256={str(p.relative_to(a.repo)):sha(p) for d in ['aodet','configs'] for p in sorted((a.repo/d).rglob('*.py'))},implementation_sha256={n:sha(ROOT/'tools'/n) for n in ['run_camera_coverage.py','camera_coverage_runtime.py','run_scene_baseline.py','scene_baseline_runtime.py','camera_baseline_runtime.py']})
    dump(out/'status.json',meta)
    assert torch.cuda.is_available()
    with trusted_torch_load():
        runner=Runner.from_cfg(cfg)
        assert len(runner.train_dataloader)==309
        # The inherited monitor copies the training pipeline by default. Bind its
        # loader explicitly so every periodic val also stays free of augmentation.
        val_spec=loader('val',False)
        assert not any(t['type']=='CameraCoverageAugment' for t in val_spec['dataset']['pipeline'])
        for hook in runner.hooks:
            if isinstance(hook,scene_baseline_runtime.ScenePeriodicValHook):
                hook.loader=Runner.build_dataloader(val_spec,seed=0)
                assert len(hook.loader.dataset)==894
        meta['all_val_loaders_unaugmented']=True
        try:
            if a.preflight:
                # Verify the original sampler exactly matches the pre-existing protocol.
                from mmengine.dataset import DefaultSampler
                from camera_coverage_runtime import CameraCoverageSampler,geometry
                fake=list(range(2472));old=DefaultSampler(fake,shuffle=True,seed=0);new=CameraCoverageSampler(fake,seed=0)
                for epoch in [0,1,199]:old.set_epoch(epoch);new.set_epoch(epoch);assert list(old)==list(new)
                # Geometry controls are independent analytic cases (flip/involution/scale+translation).
                import numpy as np
                im=np.zeros((360,640,3),dtype=np.uint8);im[20:60,10:40]=255
                x,b=geometry(im,[[10,20,30,40]],True,1,0,0);assert b==[[600.,20.,30.,40.]]
                y,c=geometry(x,b,True,1,0,0);assert np.array_equal(im,y) and c==[[10.,20.,30.,40.]]
                _,b=geometry(im,[[100,100,40,20]],False,.9,2,3);assert np.allclose(b,[[124,111,36,18]])
                # The val pipeline has no augmentation; baseline geometry/raw-EMA preflight applies.
                baseline.COUNTS={'train':len(rows['train']),'val':894}
                def preflight_loader(role,shuffle):
                    spec=loader(role,False)
                    if role=='train':spec['dataset']['pipeline']=loader('val',False)['dataset']['pipeline']
                    return spec
                args.data=data
                checks=baseline.preflight(runner,preflight_loader,args,a.checkpoint,out)
                if aug:
                    dl=Runner.build_dataloader(loader('train',True),seed=0);batch=next(iter(dl));runner.model.train()
                    processed=runner.model.data_preprocessor(batch,training=True)
                    loss,_=runner.model.parse_losses(runner.model(**processed,mode='loss'));assert torch.isfinite(loss);loss.backward()
                    assert all(torch.isfinite(p.grad).all() for p in runner.model.parameters() if p.grad is not None)
                    checks['augmented_batch_loss']=float(loss.detach());runner.model.zero_grad(set_to_none=True)
                meta.update(status='preflight_passed',checks=checks,sampler_matches_original=True,geometry_controls_passed=True)
            else:
                proof=json.loads((out.parent/'preflight/status.json').read_text(encoding='utf-8'));assert proof['status']=='preflight_passed'
                for k in ['variant','data_sha256','initialization_sha256','implementation_sha256','source_sha256']:assert proof[k]==meta[k],k
                meta['status']='training';dump(out/'status.json',meta);runner.train()
                final=out/'epoch_200.pth';saved=torch.load(final,map_location='cpu',weights_only=False)
                assert saved['meta']['iter']==61800 and saved['meta']['epoch']==200
                for kind in ['raw','ema']:
                    torch.save(dict(state_dict=scene_baseline_runtime.identified_state(saved,kind),workflow_weight_identity=dict(kind=kind,epoch=200,parent_sha256=sha(final),verified_against_live_models=True)),out/f'{kind}_epoch_200.pth')
                runner.model.load_state_dict(scene_baseline_runtime.identified_state(saved,'raw'),strict=True)
                install_nms_cpu_fallback()
                class Adapter:
                    def eval(self):runner.model.eval()
                    def test_step(self,batch):return {'camera':runner.model.test_step(batch)['camera']}
                metrics=camera_baseline_runtime.evaluate_val(Adapter(),Runner.build_dataloader(loader('val',False),seed=0),data/'camera-val-coco.json',out/'val_actual_raw_epoch200')
                meta.update(status='completed',val_pooled=metrics['pooled'])
        except BaseException as exc:
            meta.update(status='failed',error=repr(exc));raise
        finally:dump(out/'status.json',meta)
    print(json.dumps(meta))

if __name__=='__main__':main()
