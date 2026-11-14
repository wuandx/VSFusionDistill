"""Find, by content, which SD frame each published camera JPG actually is.

The release numbered its JPGs by ARIS frame but pulled the pixels out of `clips_fhd`.  Container
metadata tells us the two clips start at different times, but not which video index the exporter
actually used -- so this measures it: for an ARIS frame N, scan the SD clip and take the index whose
thumbnail best correlates with the published JPG N.

Sampling several frames tells us whether the relation is a constant shift or a rate, and a linear fit
gives the SD index that ARIS frame N *should* have been taken at.

usage: python -m tools.sd_content_offset <recording> [--frames 200,400,600] [--coarse 7]
"""
from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FF = ROOT / "tools" / "bin" / "ffmpeg-win-x86_64-v9.0.2.exe"
PROCESSED = Path(r"D:\pby\data_processed")
REC_ROOT = Path(r"D:\pby\uxo-full\extracted\recordings")
CAT_DIR = {"100lbs_aircraft_bomb": "100lbs_bomb", "incindiary_grenade": "20lbs_incendiary",
           "mortar_shell": "15cm_mortar"}
S = (160, 90)


def match_row(recording: str) -> dict | None:
    with open(PROCESSED / "matches.csv", encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            if Path((r.get("aris_file") or "").strip()).name == recording:
                return r
    return None


def rec_dir(recording: str) -> Path | None:
    for d in CAT_DIR.values():
        p = REC_ROOT / d / recording
        if p.exists():
            return p
    return None


def grab(clip: Path, n: int) -> np.ndarray | None:
    if n < 0:
        return None
    p = subprocess.run([str(FF), "-hide_banner", "-loglevel", "error", "-i", str(clip),
                        "-vf", f"select=eq(n\\,{n}),scale={S[0]}:{S[1]}", "-fps_mode", "passthrough",
                        "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    if not p.stdout:
        return None
    return np.asarray(Image.open(io.BytesIO(p.stdout)).convert("L"), dtype=np.float32)


def ncc(a: np.ndarray, b: np.ndarray) -> float:
    a0, b0 = a - a.mean(), b - b.mean()
    d = np.sqrt((a0 * a0).sum() * (b0 * b0).sum())
    return float((a0 * b0).sum() / d) if d else 0.0


def locate(jpg: Path, clip: Path, hi: int, coarse: int = 7) -> tuple[int, float] | None:
    a = np.asarray(Image.open(jpg).convert("L").resize(S, Image.LANCZOS), dtype=np.float32)
    scored = []
    for n in range(0, hi, coarse):
        f = grab(clip, n)
        if f is not None:
            scored.append((ncc(a, f), n))
    scored.sort(reverse=True)
    best = None
    for _, n0 in scored[:3]:
        for n in range(max(0, n0 - coarse), n0 + coarse + 1):
            f = grab(clip, n)
            if f is not None:
                c = ncc(a, f)
                if best is None or c > best[0]:
                    best = (c, n)
    return None if best is None else (best[1], round(best[0], 4))


def main(argv: list[str]) -> int:
    args, frames = [], [200, 400, 600]
    i = 1
    while i < len(argv):
        if argv[i] == "--frames":
            frames = [int(x) for x in argv[i + 1].split(",")]; i += 2
        elif argv[i] == "--coarse":
            i += 2
        else:
            args.append(argv[i]); i += 1
    recording = args[0]
    row = match_row(recording)
    rd = rec_dir(recording)
    if row is None or rd is None:
        raise SystemExit("no match row or no recording dir")
    clip = PROCESSED / (row.get("gopro_file") or "").strip()
    hi = 1200

    found = []
    for f in frames:
        jpg = rd / "gopro" / f"{f:04d}.jpg"
        if not jpg.exists():
            print(f"{f}: no jpg"); continue
        hit = locate(jpg, clip, hi)
        if hit:
            print(f"aris {f:4d}  ->  SD {hit[0]:4d}   ncc {hit[1]:.4f}   shift +{hit[0]-f}")
            found.append((f, hit[0]))

    if len(found) >= 2:
        xs = np.array([f for f, _ in found], dtype=float)
        ys = np.array([s for _, s in found], dtype=float)
        slope, icpt = np.polyfit(xs, ys, 1)
        print(f"fit: sd_index = {slope:.4f} * aris_frame + {icpt:.2f}")
        print(f"     (a slope of 1 is a constant shift; anything else means the sonar and the camera "
              f"do not advance at the same number of frames per second)")
        print(f"     at aris_onset {row.get('aris_onset')}: sd_index {slope*float(row['aris_onset'])+icpt:.1f} "
              f"vs matches.csv gopro_idx {row.get('gopro_idx')} + offset {row.get('gopro_offset')}")

    out = ROOT / "out" / f"sd_content_{recording}.json"
    out.write_text(json.dumps({
        "recording": recording, "sd_clip": str(clip),
        "pairs_aris_to_sd": [{"aris_frame": f, "sd_index": s} for f, s in found],
        "fit": (None if len(found) < 2 else {
            "slope": round(float(np.polyfit([f for f, _ in found], [s for _, s in found], 1)[0]), 4),
            "intercept": round(float(np.polyfit([f for f, _ in found], [s for _, s in found], 1)[1]), 3)}),
        "note": ("sd_index is where the released JPG for that ARIS frame actually sits in clips_sd, found "
                 "by thumbnail correlation (ncc). Labels fit these released pictures, so the label moment "
                 "is this SD index too."),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", out.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
