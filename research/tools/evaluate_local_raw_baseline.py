import os
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import run_camera_recording_baseline as common
import torch
from mmengine.config import Config
from mmengine.runner import Runner
from aodet.cuda_compat import install_nms_cpu_fallback
from aodet.torch_load_compat import trusted_torch_load
from camera_baseline_runtime import evaluate_val

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',default='camera_recording_baseline',choices=['camera_recording_baseline','camera_recording_m']);parser.add_argument('--split',default='val',choices=['train','val','test']);args=parser.parse_args()
    work=ROOT/'runs'/args.run/'train'
    output=work/f'{args.split}_actual_raw_epoch200'
    assert not (output/'metrics.json').exists(),'Raw metrics already exist'
    cfg=Config.fromfile(str(work/'resolved_config.py'))
    cfg.work_dir=str(work/f'{args.split}_raw_evaluation_runtime')
    runner=Runner.from_cfg(cfg)
    checkpoint=work/'epoch_200.pth'
    with trusted_torch_load():
        saved=torch.load(checkpoint,map_location='cpu',weights_only=False)
        assert saved['meta']['epoch']==200
        raw={k[7:]:v for k,v in saved['ema_state_dict'].items() if k.startswith('module.')}
        runner.model.load_state_dict(raw,strict=True)
        spec=dict(cfg.train_dataloader)
        spec['sampler']=dict(type='DefaultSampler',shuffle=False)
        spec['dataset']=dict(cfg.train_dataloader.dataset)
        spec['dataset']['ann_file']=str(ROOT/f'DataSet/camera_recording_baseline/{args.split}-dataset.json')
        loader=Runner.build_dataloader(spec,seed=0)
        count=1800 if args.split=='train' else 600
        assert len(loader.dataset)==count
        install_nms_cpu_fallback()
        metrics=evaluate_val(runner.model,loader,ROOT/f'DataSet/camera_recording_baseline/{args.split}-coco.json',output)
        (output/'weight-identity.json').write_text(json.dumps(dict(checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),weight_source='ema_state_dict.module.* (actual raw)',epoch=200,images=count,split=args.split,test_used=args.split=='test'),indent=2)+'\n')
        print(json.dumps(metrics['pooled']))

if __name__=='__main__':main()
