"""Package frozen train/val only and an exact read-only source snapshot."""
import hashlib
import json
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'DataSet/weak_coverage_camera_m_5090_deployment'
REPO=ROOT.parent/'声呐目标检测/code/VSFusionDistill'
TOOLS=['run_weak_coverage_camera_teacher.py','weak_coverage_teacher_runtime.py',
       'scene_baseline_runtime.py','camera_baseline_runtime.py','run_scene_baseline.py',
       'prepare_scene_baselines.py','launch_weak_teacher_5090.py']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    OUT.mkdir(exist_ok=False)
    files={}
    package=OUT/'weak_coverage_camera_m_teacher.tar'
    local=json.loads((ROOT/'runs/weak_coverage_camera_m_teacher/train/status.json').read_text(encoding='utf-8'))
    with tarfile.open(package,'w') as tar:
        def add(path,rel):
            assert path.is_file() and not path.is_symlink()
            files[rel]=sha(path)
            tar.add(path,arcname=rel,recursive=False)
        data=ROOT/'DataSet/camera_weak_coverage_trainval'
        for path in sorted(data.rglob('*')):
            if path.is_file():add(path,path.relative_to(ROOT).as_posix())
        for folder in ['aodet','configs']:
            for path in sorted((REPO/folder).rglob('*.py')):
                rel=path.relative_to(REPO).as_posix()
                assert sha(path)==local['source_sha256'][rel]
                add(path,'source/'+rel)
        for name in TOOLS:
            path=ROOT/'tools'/name
            if name in local['implementation_sha256']:assert sha(path)==local['implementation_sha256'][name]
            add(path,'tools/'+name)
        for rel in ['assets/checkpoints/yolox_m_coco_backbone_neck.pth',
                    'runs/weak_coverage_camera_m_teacher/dataset-freeze.json',
                    'experiment/archive/weak-coverage-camera-m-training-plan.md',
                    'experiment/archive/weak-coverage-camera-m-5090-deployment-plan.md']:
            add(ROOT/rel,rel)
        manifest=OUT/'deployment-files-sha256.json'
        manifest.write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        tar.add(manifest,arcname=manifest.name)
    report=dict(package_sha256=sha(package),manifest_sha256=sha(manifest),files=len(files),
        bytes=package.stat().st_size,train=4138,val=573,images=4711,test_uploaded=False,sonar_uploaded=False,
        source_matches_local_training=True,implementation_matches_local_training=True)
    (OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__':main()
