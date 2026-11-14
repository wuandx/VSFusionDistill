"""Verify fixed compute, sampling coverage and retained original baseline comparability."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from prepare_scene_baselines import dump,sha
def main():
    from mmengine.config import Config
    from mmengine.dataset import DefaultSampler
    from camera_coverage_runtime import CameraCoverageSampler
    old=ROOT/'runs/scene_camera_m_baseline/after_pilot/train'
    new=ROOT/'runs/camera_coverage_controls/expanded_plain/preflight'
    oc=Config.fromfile(str(old/'resolved_config.py'),import_custom_modules=False);nc=Config.fromfile(str(new/'resolved_config.py'),import_custom_modules=False)
    keys=['model','optim_wrapper','param_scheduler','train_cfg','randomness','env_cfg']
    assert all(oc[k]==nc[k] for k in keys)
    os=json.loads((old/'status.json').read_text());ns=json.loads((new/'status.json').read_text())
    assert os['status']=='completed' and ns['status']=='preflight_passed'
    assert os['initialization_sha256']==ns['initialization_sha256'] and os['source_sha256']==ns['source_sha256']
    assert os['total_updates']==ns['total_updates']==61800
    for name in ['scene_baseline_runtime.py','camera_baseline_runtime.py','run_scene_baseline.py']:
        assert os['implementation_sha256'][name]==sha(ROOT/'tools'/name)
    # Original and expanded both emit exactly 2472 identities per epoch; full original order is identical.
    a=list(range(2472));b=list(range(3372));old_s=DefaultSampler(a,shuffle=True,seed=0);new_s=CameraCoverageSampler(a,seed=0);expanded=CameraCoverageSampler(b,seed=0)
    exposure=[0]*3372
    for epoch in range(200):
        old_s.set_epoch(epoch);new_s.set_epoch(epoch);expanded.set_epoch(epoch)
        assert list(old_s)==list(new_s)
        ids=list(expanded);assert len(ids)==len(set(ids))==2472
        for i in ids:exposure[i]+=1
    assert min(exposure)>0
    result=dict(passed=True,retained_original_plain_run=str(old),matching_config_keys=keys,same_initialization_and_source_hashes=True,original_sampler_all_200_epochs_identical=True,expanded_samples_per_epoch=2472,all_expanded_images_sampled_across_run=True,expanded_per_image_exposures_min=min(exposure),expanded_per_image_exposures_max=max(exposure),total_updates=61800,expanded_equivalent_full_passes=2472*200/3372,unchanged_original_implementation_hashes=True)
    dump(ROOT/'runs/camera_coverage_controls/queue/design-verification.json',result);print(json.dumps(result))
if __name__=='__main__':main()
