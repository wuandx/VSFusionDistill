"""Recover only CRC-verified approved FHD movies from bounded LZMA2 windows.

Windows lie well inside the movie-only part of the solid block. Container
bytes of neighbours initialize the dictionary but are neither materialized as
movies nor decoded as images. Synthetic decoder prefixes never enter output.
"""
from pathlib import Path
import json
import urllib.request
import lzma
import zlib
import hashlib
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "related_work/uxo/sd-fhd-trace"
DEST = ROOT / "DataSet/camera_annotation_trace/fhd_clips"
CACHE = ROOT / "DataSet/camera_annotation_trace/archive-cache"


def parse_run(raw, start):
    i, chunks = start, 0
    while i < len(raw):
        b = raw[i]
        if b == 0:
            return chunks if i == len(raw) - 1 else 0
        if b in (1, 2):
            if i + 3 > len(raw): return chunks
            n = int.from_bytes(raw[i+1:i+3], "big") + 1
            i += 3 + n
        elif b >= 128:
            if i + 6 > len(raw): return chunks
            n = int.from_bytes(raw[i+3:i+5], "big") + 1
            i += (6 if b >= 192 else 5) + n
        else:
            return 0
        chunks += 1
    return chunks


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    selected = [r for r in json.loads((BASE / "selected-video-packs.json").read_text()) if "/clips_fhd/" in r["name"]]
    results = []
    for row in selected:
        target = DEST / Path(row["name"]).name
        if target.is_file():
            data = target.read_bytes()
            assert len(data) == row["size"] and zlib.crc32(data) == row["crc32"]
            results.append({**row, "path": str(target), "sha256": hashlib.sha256(data).hexdigest(),
                            "size_crc_matches": True, "method": "revalidated existing CRC-verified window recovery; caches and second-clip recovery log retained"})
            print("Existing verified " + target.name, flush=True)
            continue
        # Folder 15 first MP4 begins at unpacked 262059488; all range starts
        # below are >700M into this folder, far after its PNG/CSV prefix.
        start_in_pack = row["preceding_unpacked"] - 64 * 1024 * 1024
        end_in_pack = row["preceding_unpacked"] + row["size"] + 2 * 1024 * 1024
        assert start_in_pack > 650 * 1024 * 1024
        start = row["pack_start"] + start_in_pack
        end = row["pack_start"] + end_in_pack
        cached = CACHE / (target.stem + "-packed-window.bin")
        if cached.is_file():
            raw = cached.read_bytes()
        else:
            url = f"https://zenodo.org/records/13778485/files/data_processed.7z?download=1&fhd_trace_window={start}"
            req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end-1}"})
            with urllib.request.urlopen(req, timeout=45) as response:
                assert response.status == 206
                raw = response.read(end - start + 1)
            assert len(raw) == end - start
            cached.write_bytes(raw)
        candidates = [i for i in range(65540) if raw[i] in (1,2) and parse_run(raw, i) > 500]
        # The first compressed packet may inherit LZMA state from before the
        # window. Try restarting after early compressed packets so that a later
        # properties-reset packet follows a complete raw dictionary warmup.
        if candidates:
            pos = candidates[0]
            restarts = []
            while pos + 6 < len(raw) and pos < 40 * 1024 * 1024:
                control = raw[pos]
                if control in (1,2):
                    pos += 3 + int.from_bytes(raw[pos+1:pos+3], "big") + 1
                elif control >= 128:
                    pos += (6 if control >= 192 else 5) + int.from_bytes(raw[pos+3:pos+5], "big") + 1
                    if pos < len(raw) and raw[pos] in (1,2): restarts.append(pos)
                else: break
            candidates.extend(restarts)
        print(f"{target.name}: read {len(raw)} bytes, packet starts {candidates[:5]}", flush=True)
        found = None
        for i in dict.fromkeys(candidates):
            for pad in range(1,5):
                synthetic = b"\x01" + (pad-1).to_bytes(2,"big") + bytes(pad) + raw[i:]
                if raw[i] == 1: synthetic = raw[i:]
                try:
                    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=[{"id": lzma.FILTER_LZMA2, "dict_size": 1 << 24}])
                    content = decoder.decompress(synthetic)
                except lzma.LZMAError:
                    continue
                for match in re.finditer(b"ftyp", content):
                    begin = match.start() - 4
                    if begin < 0 or begin + row["size"] > len(content): continue
                    data = content[begin:begin+row["size"]]
                    if zlib.crc32(data) == row["crc32"]:
                        target.write_bytes(data)
                        found = {**row, "path": str(target), "sha256": hashlib.sha256(data).hexdigest(),
                                 "size_crc_matches": True, "range_start": start, "range_end_exclusive": end,
                                 "network_bytes": len(raw), "decoder_start": i, "synthetic_prefix_bytes": pad,
                                 "recovered_member_offset": begin,
                                 "method": "temporary raw-prefix LZMA2 decoder initialization; exact original MP4 selected by official size and CRC; no neighbouring movie decoded or materialized"}
                        break
                if found: break
            if found: break
        if not found:
            raise RuntimeError("Could not reconstruct exact target bytes; no unverified movie accepted")
        results.append(found)
        print("CRC verified " + target.name, flush=True)
    (BASE / "fhd-clip-extraction.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
