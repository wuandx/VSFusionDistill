"""Extract only the two approved SD clips from a bounded archive prefix.

The solid archive decoder passes preceding MP4/container bytes without opening
or decoding their videos. Only the two selected clips are materialized.
"""
from pathlib import Path
import json
import urllib.request
import lzma
import zlib
import hashlib

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "related_work/uxo/sd-fhd-trace"
DEST = ROOT / "DataSet/camera_annotation_trace/sd_clips"


def main():
    rows = json.loads((BASE / "selected-video-packs.json").read_text())
    selected = [r for r in rows if "/clips_sd/" in r["name"]]
    assert len(selected) == 2 and {r["folder"] for r in selected} == {16}
    DEST.mkdir(parents=True, exist_ok=True)
    if all((DEST / Path(r["name"]).name).is_file() for r in selected):
        for r in selected:
            b = (DEST / Path(r["name"]).name).read_bytes()
            assert len(b) == r["size"] and zlib.crc32(b) == r["crc32"]
        print("Selected SD clips already extracted and CRC verified")
        return
    start = selected[0]["pack_start"]
    budget = 160 * 1024 * 1024
    url = f"https://zenodo.org/records/13778485/files/data_processed.7z?download=1&sd_trace_prefix={start}"
    req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{start + budget - 1}"})
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=[{"id": lzma.FILTER_LZMA2, "dict_size": 1 << 24}])
    buffers = {r["name"]: bytearray() for r in selected}
    stop = max(r["preceding_unpacked"] + r["size"] for r in selected)
    unpacked = transferred = 0
    with urllib.request.urlopen(req, timeout=45) as response:
        assert response.status == 206
        while unpacked < stop:
            packed = response.read(1024 * 1024)
            if not packed:
                raise RuntimeError("archive prefix ended before targets")
            transferred += len(packed)
            content = decoder.decompress(packed)
            end = unpacked + len(content)
            for r in selected:
                lo, hi = r["preceding_unpacked"], r["preceding_unpacked"] + r["size"]
                left, right = max(lo, unpacked), min(hi, end)
                if left < right:
                    buffers[r["name"]].extend(content[left - unpacked:right - unpacked])
            unpacked = end
            if transferred % (32 * 1024 * 1024) == 0:
                print(f"Read {transferred // (1024*1024)} MiB archive stream; selected video bytes {[len(v) for v in buffers.values()]}", flush=True)
            if transferred >= budget and unpacked < stop:
                raise RuntimeError("bounded network budget exhausted")
    results = []
    for r in selected:
        data = bytes(buffers[r["name"]])
        assert len(data) == r["size"] and zlib.crc32(data) == r["crc32"]
        path = DEST / Path(r["name"]).name
        path.write_bytes(data)
        results.append({**r, "path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "size_crc_matches": True})
    (BASE / "sd-clip-extraction.json").write_text(json.dumps({
        "scope": "two approved SD clips only; no other MP4 materialized or decoded; no test frames decoded",
        "range_start": start, "maximum_range_bytes": budget, "actual_bytes_read": transferred,
        "archive_bytes_processed_note": "preceding compressed/container bytes in the same solid block are passed by archive decompression and discarded; this is not zero access to all unrelated binary payload",
        "selected": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"sd_clips_verified": len(results), "archive_bytes_read": transferred}), flush=True)


if __name__ == "__main__":
    main()
