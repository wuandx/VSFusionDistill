"""Catalog public archive headers only to locate SD/FHD and annotation projects."""
import importlib.util
import json
import re
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("uxo_header", ROOT / "tools/check_uxo_release_metadata.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
BASE = ROOT / "related_work/uxo/sd-fhd-trace"


def main():
    meta = json.loads((BASE / "zenodo-record.json").read_text())
    files_meta = {x["key"]: x for x in meta["files"]}
    summaries = []
    for name in ["data_export_recordings.7z", "data_processed.7z"]:
        folder = BASE / name.replace(".7z", "")
        folder.mkdir(parents=True, exist_ok=True)
        module.URL = f"https://zenodo.org/records/13778485/files/{name}?download=1"
        module.SIZE = files_meta[name]["size"]
        module.OUT = folder
        reader = module.HeaderRangeReader()
        cache = ROOT / "related_work/uxo/source-check" if name == "data_export_recordings.7z" else folder
        for path in cache.glob("header-range-*.bin"):
            begin = int(re.match(r"header-range-(\d+)-", path.name).group(1))
            reader.parts.append((begin, path.read_bytes()))
        with module.py7zr.SevenZipFile(reader, "r") as archive:
            listed = archive.list()
            streams = archive.header.main_streams
            blocks = len(streams.unpackinfo.folders) if streams else 0
            solid = bool(streams and archive._is_solid())
            catalog = [{"name": f.filename.replace('\\', '/'), "size": f.uncompressed,
                        "compressed": f.compressed, "crc32": f.crc32,
                        "directory": f.is_directory} for f in listed]
            summary = {"archive": name, "archive_size": module.SIZE,
                       "members": len(catalog), "solid": solid,
                       "blocks": blocks,
                       "new_bytes_transferred": reader.transferred,
                       "operation": "list only; no members extracted", "new_ranges": reader.log,
                       "extension_counts": dict(Counter(Path(f["name"]).suffix.lower() for f in catalog if not f["directory"]))}
        (folder / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
        (folder / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        summaries.append(summary)
        candidates = [f for f in catalog if not f["directory"] and (re.search(r"\.(mp4|avi|mov|mkv|yaml|yml|xml|csv|txt|py|bash|sh)$", f["name"], re.I) or re.search(r"labelme|cvat|annotation|\.vott|\.label", f["name"], re.I))]
        (folder / "source-candidates.json").write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False), flush=True)
        print("Video/config candidates:", [f["name"] for f in candidates if re.search(r"clips_|match|config\.yaml|labelme|cvat", f["name"], re.I)][:65], flush=True)
    (BASE / "catalog-summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
