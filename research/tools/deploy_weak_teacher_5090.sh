set -eu
BASE=/root/wzl/weak_coverage_camera_m_teacher
ARCHIVE=/mnt/c/Users/Administrator/weak_coverage_camera_m_teacher.tar
PY=/root/pby/code/VSFusionDistill/.venv-gpu/bin/python
test ! -e "$BASE"
echo '88fb2462ef1cebc29c2f869659327635f3b3801aa41e2b39bded8d032fa6bc2d  /mnt/c/Users/Administrator/weak_coverage_camera_m_teacher.tar' | sha256sum -c -
mkdir "$BASE"
export DEPLOY_WEAK_BASE="$BASE" DEPLOY_WEAK_ARCHIVE="$ARCHIVE"
"$PY" - <<'PY'
import hashlib,json,os,tarfile
from pathlib import Path
base=Path(os.environ['DEPLOY_WEAK_BASE'])
with tarfile.open(os.environ['DEPLOY_WEAK_ARCHIVE']) as tar:
    entries=tar.getmembers()
    assert all(m.isfile() and (base/m.name).resolve().is_relative_to(base) for m in entries)
    tar.extractall(base)
manifest=base/'deployment-files-sha256.json'
assert hashlib.sha256(manifest.read_bytes()).hexdigest()=='4404930b3e9b43e50e5dc7e2bef6e80544c053dbd9a620951b2a0072adbb08a0'
files=json.loads(manifest.read_text())
for name,expected in files.items():
    assert hashlib.sha256((base/name).read_bytes()).hexdigest()==expected,name
report=dict(passed=True,files_verified=len(files),train=4138,val=573,images=4711,test_uploaded=False,sonar_uploaded=False)
(base/'deployment-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
PY
echo 'Verified extraction; use the named one-off Windows task for a persistent foreground WSL launch.'
