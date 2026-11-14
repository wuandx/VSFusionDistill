"""Frozen sonar-only YOLOX-S student baseline; fresh COCO and no distillation."""
import os
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime,timezone
from prepare_scene_baselines import sha,dump,CLASSES

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'DataSet/sonar_weak_coverage_trainval'
BASE=ROOT/'runs/weak_coverage_sonar_s_student'
COUNTS={'train':4138,'val':573}
CKPT_SHA='4592a793b95f18f62fd73fbb6cfe61dd445f71a8e072366e114e7134d4492760'
IMPLEMENTATION=['run_weak_coverage_sonar_student.py','weak_coverage_sonar_runtime.py',
    'scene_baseline_runtime.py','camera_baseline_runtime.py','run_scene_baseline.py','prepare_scene_baselines.py']

def configure(args):
    from mmengine.config import Config
    cfg=Config.fromfile(str(args.repo/'configs/repro_cmold/teachers/t_camera_s_yoloxs.py'))
    cfg.model.sonar_backbone.init_cfg=deepcopy(cfg.model.camera_backbone.init_cfg)
    cfg.model.sonar_neck.init_cfg=deepcopy(cfg.model.camera_neck.init_cfg)
    cfg.model.uncoupled_sonar_head=deepcopy(cfg.model.camera_head)
    cfg.model.camera_backbone=cfg.model.camera_neck=cfg.model.camera_head=None
    for suffix in ['backbone','neck']:cfg.model['sonar_'+suffix].init_cfg.checkpoint=str(args.checkpoint)
    cfg.model.fused_sonar_head=None;cfg.model.fusion=dict(type='NoneFusion')
    cfg.model.loss_weights=dict(camera=0.,fused_sonar=0.,uncoupled_sonar=1.)
    cfg.model.data_preprocessor.update(mean=None,std=None,bgr_to_rgb=False,pad_value=114.)
    pipe=[dict(type='AOLoadPaired'),dict(type='AOPairedResize',sonar_size=(640,640),keep_ratio=True),
          dict(type='AOPackPairedInputs'),dict(type='SceneFixedCanvas')]
    def loader(role,shuffle):
        assert role in COUNTS
        return dict(batch_size=8,num_workers=2,persistent_workers=True,
            sampler=dict(type='DefaultSampler',shuffle=shuffle),collate_fn=dict(type='pseudo_collate'),
            dataset=dict(type='SceneSingleModalDataset',ann_file=str(DATA/f'sonar-{role}-dataset.json'),
                         pipeline=deepcopy(pipe),serialize_data=False))
    cfg.train_dataloader=loader('train',True)
    cfg.val_dataloader=cfg.val_evaluator=cfg.val_cfg=None
    cfg.test_dataloader=cfg.test_evaluator=cfg.test_cfg=None
    cfg.train_pipeline=deepcopy(pipe);cfg.test_pipeline=deepcopy(pipe)
    cfg.randomness=dict(seed=0,deterministic=False);cfg.load_from=None;cfg.resume=False
    cfg.custom_hooks=list(cfg.custom_hooks)+[dict(type='FiniteCameraLossHook'),dict(type='SceneWeightIdentityHook'),
        dict(type='WeakCoverageSonarValHook',data_root=str(DATA),expected_count=573,interval=10)]
    cfg.default_hooks.checkpoint=dict(type='CheckpointHook',interval=10,max_keep_ckpts=2,save_last=True)
    cfg.default_hooks.logger.interval=20
    cfg.custom_imports=dict(imports=['aodet.datasets','aodet.models','aodet.engine','camera_baseline_runtime',
        'scene_baseline_runtime','weak_coverage_sonar_runtime'],allow_failed_imports=False)
    cfg.experiment_name='weak_coverage_sonar_s_student'
    cfg.known_deviations=dict(data='frozen paired weak-scene coverage split sonar4138train/573val',
        initialization='fresh COCO-S backbone/neck; random 3-class head; no UXO resume',augmentation=False,
        geometry='native sonar PNG, keep_ratio fixed640, right/bottom pad114, BGR0-255',
        annotation='assistant reviewed visible sonar echo boxes, not projected or expert GT',
        distillation=False,development_history='old val/test used to define coverage; not untouched blind evaluation',
        primary_weights='epoch200 explicit actual raw; EMA separate')
    cfg.work_dir=str(args.work_dir)
    return cfg,loader

def verify_inputs():
    from PIL import Image
    proof=json.loads((DATA/'verification.json').read_text(encoding='utf-8'))
    freeze=json.loads((BASE/'dataset-freeze.json').read_text(encoding='utf-8'))
    assert proof['passed'] and proof['classes']==CLASSES and proof['only_sonar_trainval']
    assert sha(DATA/'files-sha256.json')==proof['dataset_sha256']==freeze['dataset_sha256']
    files=json.loads((DATA/'files-sha256.json').read_text(encoding='utf-8'))
    assert all((DATA/name).resolve().is_relative_to(DATA.resolve()) and sha(DATA/name)==h for name,h in files.items())
    members=json.loads((DATA/'trainval-members.json').read_text(encoding='utf-8'))
    camera=json.loads((ROOT/'DataSet/camera_weak_coverage_trainval/trainval-members.json').read_text(encoding='utf-8'))
    seen={};records={};groups={}
    for role,count in COUNTS.items():
        rows=json.loads((DATA/f'sonar-{role}-dataset.json').read_text(encoding='utf-8'))
        coco=json.loads((DATA/f'sonar-{role}-coco.json').read_text(encoding='utf-8'))
        assert len(rows)==len(coco['images'])==len(coco['annotations'])==count
        ims={i['id']:i for i in coco['images']};anns={a['image_id']:a for a in coco['annotations']}
        identities=lambda ms:{(m['sample'],m['recording'],m['group_id'],m['category'],m['role']) for m in ms}
        assert identities(members[role])==identities(camera[role])
        assert {r['sample_id'] for r in rows}=={r['sample'] for r in members[role]}
        for r in rows:
            assert r['role']==role and r['fp_camera'] is None and not r['boxes_camera'] and not r['labels_camera']
            im=Image.open(DATA/r['fp_sonar']);im.load();assert im.size==(r['width'],r['height'])
            ci=ims[r['coco_sonar_image_id']];a=anns[ci['id']]
            assert ci['sample']==r['sample_id'] and ci['file_name']==r['fp_sonar']
            assert r['boxes_sonar']==[a['bbox']] and r['labels_sonar']==[a['category_id']-1]
            b=a['bbox'];assert 0<=b[0]<b[0]+b[2]<=r['width'] and 0<=b[1]<b[1]+b[3]<=r['height']
            for key,mapping in [(r['sample_id'],seen),(r['recording'],records),(r['group_id'],groups)]:
                assert key not in mapping or mapping[key]==role;mapping[key]=role
    assert len(seen)==4711
    return proof

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--checkpoint',type=Path,required=True);parser.add_argument('--work-dir',type=Path,required=True)
    parser.add_argument('--mode',choices=['preflight','train'],required=True);args=parser.parse_args()
    args.repo=args.repo.resolve();args.checkpoint=args.checkpoint.resolve();args.work_dir=args.work_dir.resolve()
    args.data=DATA;args.modality='sonar';out=args.work_dir
    assert not out.exists(),'Preserve attempts';assert sha(args.checkpoint)==CKPT_SHA
    verify_inputs();sys.path.insert(0,str(args.repo))
    import torch
    torch.set_num_threads(8)
    from mmengine.runner import Runner
    import aodet.datasets,aodet.models,aodet.engine
    import camera_baseline_runtime,scene_baseline_runtime,weak_coverage_sonar_runtime
    from aodet.torch_load_compat import trusted_torch_load
    cfg,loader=configure(args);out.mkdir(parents=True);cfg.dump(str(out/'resolved_config.py'))
    cfgproof=dict(model=cfg.model.to_dict(),optimizer=cfg.optim_wrapper.to_dict(),scheduler=[dict(x) for x in cfg.param_scheduler],
        train_cfg=dict(cfg.train_cfg),pipeline=cfg.train_dataloader.dataset.pipeline)
    meta=dict(name='weak_coverage_sonar_s_student',status='configured',mode=args.mode,configured_at=datetime.now(timezone.utc).isoformat(),
        classes=CLASSES,epochs=200,batch=8,seed=0,train_images=4138,val_images=573,steps_per_epoch=518,total_updates=103600,augmentation=False,
        initialization_sha256=sha(args.checkpoint),dataset_sha256=sha(DATA/'files-sha256.json'),freeze_sha256=sha(BASE/'dataset-freeze.json'),
        torch=torch.__version__,source_repo=str(args.repo),
        source_sha256={x.relative_to(args.repo).as_posix():sha(x) for folder in ['aodet','configs'] for x in sorted((args.repo/folder).rglob('*.py'))},
        implementation_sha256={n:sha(ROOT/'tools'/n) for n in IMPLEMENTATION},
        configuration_semantics_sha256=hashlib.sha256(json.dumps(cfgproof,sort_keys=True).encode()).hexdigest(),
        checkpoint_selection='epoch200 actual raw, live identity verified; EMA separate',
        test_content_read=False,camera_input=False,distillation=False,fresh_coco=True)
    dump(out/'status.json',meta)
    assert torch.cuda.is_available();meta['gpu']=torch.cuda.get_device_name(0)
    (out/'pip-freeze.txt').write_text(subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True))
    try:
        with trusted_torch_load():
            runner=Runner.from_cfg(cfg)
            assert len(runner.train_dataloader)==518 and len(runner.train_dataloader.dataset)==4138
            assert cfg.load_from is None and not cfg.resume and cfg.train_cfg.max_epochs==200
            assert runner.model.camera_backbone is None and runner.model.camera_neck is None and runner.model.camera_head is None
            if args.mode=='preflight':
                import run_scene_baseline as baseline
                baseline.COUNTS=COUNTS
                checks=baseline.preflight(runner,loader,args,args.checkpoint,out)
                from torch.utils.data import DataLoader,Subset
                from mmengine.dataset import pseudo_collate
                dl=DataLoader(Subset(runner.train_dataloader.dataset,[4136,4137]),batch_size=2,collate_fn=pseudo_collate)
                runner.model.train();processed=runner.model.data_preprocessor(next(iter(dl)),training=True)
                assert tuple(processed['inputs']['sonar'].shape)==(2,3,640,640) and processed['inputs']['camera'] is None
                loss,_=runner.model.parse_losses(runner.model(**processed,mode='loss'));assert torch.isfinite(loss)
                loss.backward();assert all(torch.isfinite(p.grad).all() for p in runner.model.parameters() if p.grad is not None)
                runner.model.zero_grad(set_to_none=True)
                checks.update(short_batch2_loss=float(loss.detach()),short_batch2_finite_gradients=True,camera_modules_absent=True)
                meta.update(status='preflight_passed',checks=checks)
            else:
                passed=json.loads((BASE/'preflight/status.json').read_text());assert passed['status']=='preflight_passed'
                for k in ['initialization_sha256','dataset_sha256','freeze_sha256','source_sha256','implementation_sha256','configuration_semantics_sha256']:
                    assert passed[k]==meta[k],k
                meta.update(status='training',training_started_at=datetime.now(timezone.utc).isoformat());dump(out/'status.json',meta)
                runner.train()
                final=out/'epoch_200.pth';saved=torch.load(final,map_location='cpu',weights_only=False)
                assert saved['meta']['epoch']==200 and saved['meta']['iter']==103600
                for kind in ['raw','ema']:
                    torch.save(dict(state_dict=scene_baseline_runtime.identified_state(saved,kind),
                        workflow_weight_identity=dict(kind=kind,epoch=200,parent_sha256=sha(final),verified_against_live_models=True)),out/f'{kind}_epoch_200.pth')
                runner.model.load_state_dict(scene_baseline_runtime.identified_state(saved,'raw'),strict=True)
                from aodet.cuda_compat import install_nms_cpu_fallback
                install_nms_cpu_fallback()
                class Adapter:
                    def eval(self):runner.model.eval()
                    def test_step(self,batch):return {'camera':runner.model.test_step(batch)['sonar_uncoupled']}
                metrics=camera_baseline_runtime.evaluate_val(Adapter(),Runner.build_dataloader(loader('val',False),seed=0),
                    DATA/'sonar-val-coco.json',out/'val_actual_raw_epoch200')
                meta.update(status='completed',val_pooled=metrics['pooled'],checkpoint_sha256=sha(final),completed_at=datetime.now(timezone.utc).isoformat())
    except BaseException as exc:meta.update(status='failed',error=repr(exc));raise
    finally:dump(out/'status.json',meta)
    print(json.dumps(meta),flush=True)

if __name__=='__main__':main()
