"""Which published camera JPGs can be trusted, and where to get the right frame instead?

The release built its camera JPGs from `clips_fhd`, but the official matching table (`matches.csv`)
was made on `clips_sd`.  The two sets are not the same length at the head: their MP4 start times
differ, so frame index N in one is a different instant from frame index N in the other.  For a
recording where that difference is non-zero, the published JPG numbered N shows another moment than
the label numbered N, and any frame-by-frame camera/sonar pairing is invalid.

This tool measures the difference per recording -- it does not assume a global value.  For every row
of matches.csv it probes both clips with the bundled ffmpeg and reports:

    start_sd, start_fhd, offset_frames = round((start_fhd - start_sd) * fps)

offset_frames > 0 means the FHD clip starts later, so FHD frame N shows what SD frame N+offset shows;
a label drawn on SD frame N therefore matches FHD frame N-offset.

It writes out/sd_fhd_audit.json and prints a table.  It decodes no video.
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FFMPEG = ROOT / "tools" / "bin" / "ffmpeg-win-x86_64-v9.0.2.exe"
PROCESSED = Path(r"D:\pby\data_processed")
MATCHES = PROCESSED / "matches.csv"


def probe(clip: Path) -> dict:
    """start time, fps and frame count straight out of the container."""
    if not clip.exists():
        return {"available": False, "reason": "missing", "path": str(clip)}
    proc = subprocess.run([str(FFMPEG), "-hide_banner", "-i", str(clip)],
                          capture_output=True, text=True, errors="replace")
    text = proc.stderr
    out = {"available": True, "path": str(clip)}
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+), start: ([\d.-]+)", text)
    if m:
        h, mi, s, start = m.group(1), m.group(2), m.group(3), m.group(4)
        out["duration_s"] = round(int(h) * 3600 + int(mi) * 60 + float(s), 3)
        out["start_s"] = round(float(start), 3)
    m = re.search(r"Video: .*?, (\d+)x(\d+) .*?, ([\d.]+) fps", text)
    if m:
        out["width"], out["height"] = int(m.group(1)), int(m.group(2))
        out["fps"] = round(float(m.group(3)), 3)
    m = re.search(r"frame=\s*(\d+)", text)
    if not m:
        # count packets without decoding
        proc2 = subprocess.run([str(FFMPEG), "-hide_banner", "-i", str(clip),
                                "-map", "0:v:0", "-c", "copy", "-f", "null", "-"],
                               capture_output=True, text=True, errors="replace")
        m = re.search(r"frame=\s*(\d+)", proc2.stderr)
    if m:
        out["nb_frames"] = int(m.group(1))
    return out


def rows() -> list[dict]:
    with open(MATCHES, encoding="utf-8-sig", newline="") as fh:
        return [r for r in csv.DictReader(fh) if (r.get("gopro_file") or "").strip()]


def recording_of(row: dict) -> str:
    # aris_file is a directory: "aris/2023-09-20_171105"
    return Path((row["aris_file"] or "").strip()).name


def main() -> int:
    data, cache = [], {}
    for row in rows():
        sd_rel = (row.get("gopro_file") or "").strip()
        if not sd_rel:
            continue
        sd = PROCESSED / sd_rel
        fhd = PROCESSED / sd_rel.replace("clips_sd", "clips_fhd")
        for key, p in (("sd", sd), ("fhd", fhd)):
            if p not in cache:
                cache[p] = probe(p)
        a, b = cache[sd], cache[fhd]
        rec = recording_of(row)
        item = {"recording": rec, "aris_idx": row.get("aris_idx"), "aris_onset": row.get("aris_onset"),
                "gopro_offset": row.get("gopro_offset"), "sd_clip": sd_rel,
                "fhd_clip": fhd.name, "sd": a, "fhd": b}
        if a.get("start_s") is not None and b.get("start_s") is not None and a.get("fps"):
            off = (b["start_s"] - a["start_s"]) * a["fps"]
            item["offset_frames"] = int(round(off))
            item["offset_s"] = round(b["start_s"] - a["start_s"], 3)
        data.append(item)

    same = [d for d in data if d.get("offset_frames") == 0]
    diff = [d for d in data if d.get("offset_frames") not in (0, None)]
    print(f"{len(data)} match rows; {len(same)} with offset 0, {len(diff)} with a non-zero offset, "
          f"{len(data) - len(same) - len(diff)} unmeasured")
    print(f"{'recording':24s} {'offset':>7s} {'offset_s':>9s}  sd start/frames      fhd start/frames")
    for d in sorted(data, key=lambda x: (x.get("offset_frames") is None, x.get("offset_frames") or 0)):
        print(f"{d['recording']:24s} {str(d.get('offset_frames')):>7s} {str(d.get('offset_s')):>9s}  "
              f"{d['sd'].get('start_s')}/{d['sd'].get('nb_frames')}   "
              f"{d['fhd'].get('start_s')}/{d['fhd'].get('nb_frames')}")

    out = ROOT / "out" / "sd_fhd_audit.json"
    out.write_text(json.dumps({
        "matches_csv": str(MATCHES), "ffmpeg": str(FFMPEG),
        "n_rows": len(data), "n_offset_zero": len(same), "n_offset_nonzero": len(diff),
        "note": ("offset_frames = (start_fhd - start_sd) * fps. Positive means the FHD clip starts later, "
                 "so the label drawn on SD frame N belongs to FHD frame N-offset. Measured per clip pair; "
                 "no global value is assumed and none should be reused across recordings."),
        "recordings": data,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", out.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
