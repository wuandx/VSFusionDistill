"""Acquire public protocol evidence only; never open dataset test samples."""
import concurrent.futures
import datetime
import hashlib
import json
from pathlib import Path
import sys
import urllib.request
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "related_work" / "recording-split-review-20261111"
OUT.mkdir(parents=True, exist_ok=True)
SOURCES = [
    ("uxo-readme.md", "https://raw.githubusercontent.com/dfki-ric/uxo-dataset2024/main/README.md"),
    ("uxo-config.yaml", "https://raw.githubusercontent.com/dfki-ric/uxo-dataset2024/main/scripts/config.yaml"),
    ("uxo-release-export.py", "https://raw.githubusercontent.com/dfki-ric/uxo-dataset2024/main/scripts/release_1_export.py"),
    ("uxo-institution.html", "https://robotik.dfki-bremen.de/en/research/publications/15133"),
    ("uxo-paper.pdf", "https://www.dfki.de/fileadmin/user_upload/import/15133_20240801_oceans24_uxo_dataset_full.pdf"),
    ("cmhd-fulltext.xml", "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13417324/fullTextXML"),
    ("uatd-fulltext.xml", "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9715547/fullTextXML"),
    ("marine-debris.html", "https://arxiv.org/html/2503.22880v1"),
]


def fetch(item):
    filename, url = item
    record = {"url": url, "checked_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        with urllib.request.urlopen(url, timeout=35) as response:
            data = response.read()
            record.update(status=response.status, final_url=response.url,
                          content_type=response.headers.get("Content-Type"))
        if filename.endswith(".pdf") and not data.startswith(b"%PDF"):
            raise ValueError("Response is not a PDF")
        target = OUT / filename
        target.write_bytes(data)
        record.update(path=str(target.relative_to(ROOT)), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    except Exception as exc:
        record["error"] = str(exc)
    return record


with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
    records = list(pool.map(fetch, SOURCES))
(OUT / "acquisition-log.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
for record in records:
    print(json.dumps(record, ensure_ascii=False))
for filename in ("cmhd-fulltext.xml", "uatd-fulltext.xml"):
    path = OUT / filename
    if not path.exists():
        continue
    root = ET.fromstring(path.read_bytes())
    lines = []
    for element in root.iter():
        if element.tag in ("p", "title"):
            text = "".join(element.itertext())
            if any(word in text.lower() for word in ("split", "trajector", "training.zip", "test_1", "random", "data availability")):
                lines.append(text)
    (OUT / filename.replace(".xml", "-protocol-excerpts.txt")).write_text("\n\n".join(lines), encoding="utf-8")
    print("EXCERPTS", filename, "\n", "\n\n".join(lines))

manifest = json.loads((ROOT / "DataSet/camera_temporal_all/manifest-resolved.json").read_text(encoding="utf-8"))
print("MANIFEST_KEYS", list(manifest))
for key, value in manifest.items():
    if isinstance(value, list):
        print("LIST", key, len(value), "FIRST", str(value[0])[:1500] if value else "empty")
