"""Fetch official shared calibration/model assets; no dataset samples."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'related_work/sonar-projection-audit-assets'
OUT.mkdir(parents=True, exist_ok=True)
record = json.loads((ROOT/'related_work/uxo/sd-fhd-trace/zenodo-record.json').read_text(encoding='utf-8'))
sources = [(name, item['links']['self'], item) for item in record['files']
           for name in [item['key']] if name in ('data_export_3dmodels.7z', 'data_export_calibration.7z')]
sources += [(name.replace('/', '__'), 'https://raw.githubusercontent.com/dfki-ric/uxo-dataset2024/main/'+name, None)
            for name in ['calibration/transforms.yaml', 'demo/transforms.py', 'demo/snippet_for_pose_gt.ipynb',
                         'calibration/camera_parameters/camera_parameter_linear.txt']]

def fetch(task):
    name, url, metadata = task
    entry = dict(url=url, checked_at_utc=datetime.now(timezone.utc).isoformat(), local_path=str(OUT/name))
    try:
        with urllib.request.urlopen(url, timeout=50) as r:
            data = r.read()
            entry.update(status=r.status, final_url=r.url)
        if metadata:
            assert len(data) == metadata['size']
            alg, expected = metadata['checksum'].split(':')
            assert hashlib.new(alg, data).hexdigest() == expected
            entry['official_checksum_verified'] = metadata['checksum']
        (OUT/name).write_bytes(data)
        entry.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    except Exception as exc:
        entry['error'] = str(exc)
    return entry

with ThreadPoolExecutor(max_workers=4) as pool:
    log = list(pool.map(fetch, sources))
(OUT/'acquisition-log.json').write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(log, ensure_ascii=False, indent=2))

sys.path.insert(0, str(ROOT/'tools/_audit_deps'))
import py7zr
for filename in ('data_export_calibration.7z', 'data_export_3dmodels.7z'):
    archive = OUT/filename
    if not archive.exists():
        continue
    with py7zr.SevenZipFile(archive) as reader:
        names = reader.getnames()
        assert all(not Path(name).is_absolute() and '..' not in Path(name).parts and ':' not in name for name in names)
        reader.extractall(OUT/filename.replace('.7z',''))
    (OUT/(filename+'.members.json')).write_text(json.dumps(names, ensure_ascii=False, indent=2), encoding='utf-8')
    print(filename, len(names), 'members', names[:30])
