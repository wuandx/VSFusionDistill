"""Verify the deployed run against its preflight and local frozen recipe."""
import json,re,math
from importlib.metadata import version
from pathlib import Path
from mmengine.config import Config

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'DataSet/weak_coverage_camera_m_5090_deployment'
snapshot=json.loads((OUT/'remote-confirmed-environment-snapshot.json').read_text())
local=json.loads((ROOT/'runs/weak_coverage_camera_m_teacher/train/status.json').read_text())
pre,train=snapshot['preflight'],snapshot['train']
assert snapshot['deployment']['passed'] and pre['status']=='preflight_passed' and train['status']=='training'
keys=['initialization_sha256','dataset_sha256','freeze_sha256','source_sha256','implementation_sha256','configuration_semantics_sha256']
assert all(pre[k]==train[k] for k in keys)
assert all(local[k]==train[k] for k in keys if k!='configuration_semantics_sha256')
assert train['fresh_coco'] and not train['test_content_read'] and not train['sonar_input']
assert train['train_images']==4138 and train['val_images']==573 and train['total_updates']==103600
assert pre['checks']['short_batch2_finite_gradients'] and pre['checks']['inference_passed']
rows=snapshot['iteration_logs'];assert len(rows)>=5
parsed=[]
for row in rows:
    m=re.search(r'Epoch\(train\)\s+\[(\d+)\]\[\s*(\d+)/518\].*?time: ([0-9.]+).*?loss: ([0-9.]+)',row)
    assert m,row
    epoch,iteration=int(m[1]),int(m[2]);seconds,loss=float(m[3]),float(m[4])
    assert math.isfinite(loss) and loss>0
    parsed.append(dict(epoch=epoch,iteration=iteration,seconds=seconds,loss=loss))
assert len(snapshot['processes'])>=2
config_file=OUT/'remote-resolved-config.py'
config_file.write_text(snapshot['resolved_config'])
remote=Config.fromfile(str(config_file),import_custom_modules=False)
previous=Config.fromfile(str(ROOT/'runs/weak_coverage_camera_m_teacher/train/resolved_config.py'),import_custom_modules=False)
def normalize(value,cfg):
    replacements={str(Path(cfg.train_dataloader.dataset.ann_file).parent):'DATA',
                  str(cfg.model.camera_backbone.init_cfg.checkpoint):'CHECKPOINT'}
    if isinstance(value,dict):return {k:normalize(v,cfg) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [normalize(v,cfg) for v in value]
    if isinstance(value,str):
        for source,target in replacements.items():value=value.replace(source,target)
    return value
fields=['model','optim_wrapper','param_scheduler','train_cfg','randomness','train_dataloader','custom_hooks','default_hooks','train_pipeline','test_pipeline','load_from','resume','val_cfg','test_cfg']
comparison={k:normalize(previous.to_dict()[k],previous)==normalize(remote.to_dict()[k],remote) for k in fields}
assert all(comparison.values()),comparison
deps={n:(version(n),v) for n,v in snapshot['package_versions'].items()}
assert all(a==b and a for a,b in deps.values()),deps
report=dict(passed=True,captured_at=snapshot['captured_at'],remote_root=snapshot['remote_root'],
    recipe_fields_equal_after_path_normalization=comparison,dependencies_equal=deps,
    data_source_initialization_implementation_match_local=True,preflight_train_hashes_match=True,
    iterations=parsed,last_iteration=parsed[-1],nvidia_smi=snapshot['nvidia_smi'],
    ssh_disconnected_and_reconnected=True,test_evaluated=False,sonar_trained=False,
    hardware_difference='local RTX5060Ti -> remote RTX5090D v2; fresh run, floating-point equivalence not guaranteed')
(OUT/'startup-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False))
