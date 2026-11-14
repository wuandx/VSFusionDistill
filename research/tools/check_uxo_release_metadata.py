"""Compare selected non-test source files to CRC/size in the official 7z header.

HTTP range reads + SevenZipFile.list() only: never extract archive members.
This is a release file-identity check, not a model or annotation-quality test.
"""
import io
import json
import sys
import urllib.request
import hashlib
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/_audit_deps"))
import py7zr

OUT = ROOT / "related_work/uxo/source-check"
URL = "https://zenodo.org/records/13778485/files/data_export_recordings.7z?download=1"
SIZE = 16658054765
EXAMPLES = ["2023-09-21_101622_0822", "2023-09-21_103140_0223", "2023-09-21_103140_0309"]


class HeaderRangeReader(io.RawIOBase):
    def __init__(self):
        self.pos = 0
        self.parts = []
        self.log = []
        self.transferred = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else SIZE + offset
        if self.pos < 0:
            raise ValueError("negative seek")
        return self.pos

    def read(self, n=-1):
        if n < 0 or n > 32 * 1024 * 1024:
            raise RuntimeError("refuse unbounded/large archive read")
        if n == 0 or self.pos >= SIZE:
            return b""
        start, end = self.pos, min(SIZE, self.pos + n)
        for begin, payload in self.parts:
            if begin <= start and end <= begin + len(payload):
                self.pos = end
                return payload[start - begin:end - begin]
        if self.transferred + end - start > 64 * 1024 * 1024:
            raise RuntimeError("header-only network budget exceeded")
        req = urllib.request.Request(URL + f"&audit_range={start}-{end - 1}", headers={"Range": f"bytes={start}-{end - 1}"})
        with urllib.request.urlopen(req, timeout=30) as response:
            if response.status != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end - 1}/{SIZE}":
                raise RuntimeError("server did not honor exact range")
            payload = response.read(n + 1)
        if len(payload) != end - start:
            raise RuntimeError("unexpected response size")
        name = f"header-range-{start}-{end - 1}.bin"
        (OUT / name).write_bytes(payload)
        self.log.append({"start": start, "end_inclusive": end - 1, "bytes": len(payload),
                         "path": name, "sha256": hashlib.sha256(payload).hexdigest()})
        self.parts.append((start, payload))
        self.transferred += len(payload)
        self.pos = end
        print(f"Archive header range {start}:{end}; transferred {self.transferred} bytes", flush=True)
        return payload


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    reader = HeaderRangeReader()
    with py7zr.SevenZipFile(reader, "r") as archive:
        files = archive.list()
    selected = []
    for sample in EXAMPLES:
        recording, frame = sample.rsplit("_", 1)
        for folder, ext in [("gopro", "jpg"), ("labels", "json")]:
            suffix = f"15cm_mortar/{recording}/{folder}/{frame}.{ext}"
            matches = [f for f in files if f.filename.replace('\\', '/').endswith(suffix)]
            if len(matches) != 1:
                raise RuntimeError(f"expected one entry for {suffix}, got {len(matches)}")
            f = matches[0]
            path = Path(r"D:\pby\uxo-full\extracted\recordings") / suffix
            data = path.read_bytes()
            selected.append({"sample": sample, "archive_member": f.filename, "local_path": str(path),
                             "archive_size": f.uncompressed, "local_size": len(data),
                             "archive_crc32": f.crc32, "local_crc32": zlib.crc32(data),
                             "size_matches": len(data) == f.uncompressed,
                             "crc_matches": f.crc32 == zlib.crc32(data),
                             "local_sha256": hashlib.sha256(data).hexdigest()})
    result = {"url": URL, "py7zr": py7zr.__version__, "archive_size": SIZE,
              "archive_members_listed": len(files), "bytes_transferred": reader.transferred,
              "operation": "header metadata only; list, not extract", "ranges": reader.log,
              "selected_non_test_files": selected,
              "all_selected_size_crc_match": all(r["size_matches"] and r["crc_matches"] for r in selected),
              "limit": "CRC32+size identity evidence is not a full cryptographic comparison of remote member bytes."}
    (OUT / "release-header-comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"matched": result["all_selected_size_crc_match"], "selected": len(selected), "bytes_transferred": reader.transferred}), flush=True)


if __name__ == "__main__":
    main()
