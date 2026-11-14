"""Extract the *simultaneous* SD camera frames for one recording.

Why this exists
---------------
The published `gopro/<frame>.jpg` files were cut from the FHD clips using indices
that were matched on the SD clips, without compensating the clips' different start
times (`out/CAMERA-RETIMED.md`: |offset| median 75 frames, max 201).  So for most
recordings the published JPEG does **not** show the same moment as the same-numbered
sonar frame.  `out/camera_retimed_index.csv` carries, per sonar frame, the SD frame
index that is actually simultaneous.

This tool decodes the SD clip once and keeps only the frames the index asks for, so
the review service can serve a correctly-timed camera view without needing ffmpeg at
request time.

Output
------
    out/camera_sd/<recording>/<sd_frame:04d>.jpg   (only frames with in_clip == 1)
    out/camera_sd/<recording>/manifest.json        (clip, luma-independent facts, sha256 of index)

usage
-----
    python -m tools.sd_frames --recording 2023-09-21_105230
    python -m tools.sd_frames --recording 2023-09-21_105230 --check 400
    python -m tools.sd_frames --recording 2023-09-21_105230 --width 1280 --force

`--check F` compares the extracted SD frame that the index calls simultaneous for
sonar frame F against the published `gopro/F.jpg`, and also against the SD frame the
release actually used.  If the index is right, the published JPEG should match the
*released* index better than the *simultaneous* one.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
FFMPEG = ROOT / "tools" / "bin" / "ffmpeg-win-x86_64-v9.0.2.exe"
INDEX_CSV = OUT / "camera_retimed_index.csv"
RETIMED_JSON = OUT / "camera_retimed.json"
CACHE = OUT / "camera_sd"
REC_ROOT = Path(r"D:\pby\uxo-full\extracted\recordings")
CLIP_ROOT = Path(r"D:\pby\data_processed\gopro\clips_sd")
CATEGORY_DIR = {
    "100lbs_aircraft_bomb": "100lbs_bomb",
    "incindiary_grenade": "20lbs_incendiary",
    "mortar_shell": "15cm_mortar",
    "100lbs_aircraft_bomb_floor": "100lbs_bomb_(floor)",
}


def load_index(recording: str) -> list[dict]:
    rows = []
    with open(INDEX_CSV, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["recording"] != recording:
                continue
            rows.append({
                "aris_frame": int(row["aris_frame"]),
                "sd_simultaneous": int(row["sd_simultaneous"]),
                "sd_released": int(row["sd_released"]),
                "in_clip": int(row["in_clip"]),
                "tier": row["tier"],
            })
    rows.sort(key=lambda r: r["aris_frame"])
    return rows


def load_record(recording: str) -> dict:
    data = json.loads(RETIMED_JSON.read_text(encoding="utf-8"))
    for rec in data["recordings"]:
        if rec["recording"] == recording:
            return rec
    raise SystemExit(f"{recording}: not in {RETIMED_JSON.name} (never anchored)")


def decode_all(clip: Path, tmp: Path, width: int) -> int:
    """Decode the whole clip to JPEGs numbered from 00000, return the frame count."""
    if not clip.is_file():
        raise SystemExit(f"missing SD clip: {clip}")
    cmd = [
        str(FFMPEG), "-nostdin", "-v", "error", "-y",
        "-i", str(clip),
        "-vf", f"scale={width}:-2:flags=area",
        "-q:v", "4",
        "-start_number", "0",
        "-f", "image2", str(tmp / "%05d.jpg"),
    ]
    t0 = time.time()
    subprocess.run(cmd, check=True)
    n = len(list(tmp.glob("*.jpg")))
    print(f"decoded {n} frames in {time.time() - t0:.1f}s -> {tmp}")
    return n


def thumb(path: Path, size=(160, 90)) -> np.ndarray:
    with Image.open(path) as im:
        a = np.asarray(im.convert("L").resize(size, Image.BILINEAR), dtype=np.float32)
    a -= a.mean()
    s = a.std()
    return a / s if s > 1e-6 else a


def ncc(a: np.ndarray, b: np.ndarray) -> float:
    return float((a * b).mean())


def check(recording: str, frame: int, cache_dir: Path, width: int) -> int:
    rows = {r["aris_frame"]: r for r in load_index(recording)}
    row = rows.get(frame)
    if row is None:
        raise SystemExit(f"{recording}: frame {frame} not in index")
    rec = load_record(recording)
    cat_dir = CATEGORY_DIR[rec["category"]]
    pub = REC_ROOT / cat_dir / recording / "gopro" / f"{frame:04d}.jpg"
    sim_p = cache_dir / f"{row['sd_simultaneous']:04d}.jpg"
    rel_p = cache_dir / f"{row['sd_released']:04d}.jpg"
    if not pub.is_file():
        raise SystemExit(f"no published jpg: {pub}")
    t = thumb(pub)
    out = {"recording": recording, "aris_frame": frame, "sd_simultaneous": row["sd_simultaneous"],
           "sd_released": row["sd_released"], "width": width, "ncc": {}}
    for name, p in (("simultaneous", sim_p), ("released", rel_p)):
        out["ncc"][name] = round(ncc(t, thumb(p)), 4) if p.is_file() else None
    out["verdict"] = ("index_not_a_match" if out["ncc"]["released"] is None
                      else "published_matches_released_slot" if out["ncc"]["released"] > out["ncc"]["simultaneous"]
                      else "published_matches_simultaneous_slot")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["verdict"] == "published_matches_released_slot" else 1


def extract(recording: str, width: int, force: bool) -> int:
    rows = load_index(recording)
    if not rows:
        raise SystemExit(f"{recording}: no rows in {INDEX_CSV.name}")
    rec = load_record(recording)
    clip = CLIP_ROOT / rec["clip"]
    # keep both slots: the simultaneous one is what we serve, the released one lets --check
    # prove that the published JPEG really sits on the other slot (and is therefore mis-timed).
    want = sorted({r["sd_simultaneous"] for r in rows if r["in_clip"] == 1}
                  | {r["sd_released"] for r in rows if r["in_clip"] == 1})
    want = [k for k in want if k >= 0]          # a few early frames map before the clip start
    outside = sum(1 for r in rows if r["in_clip"] == 0)

    cache_dir = CACHE / recording
    manifest_p = cache_dir / "manifest.json"
    if manifest_p.is_file() and not force:
        have = {int(p.stem) for p in cache_dir.glob("*.jpg")}
        if set(want) <= have:
            print(f"{recording}: cache already complete ({len(have)} frames); use --force to redo")
            return 0

    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="sdframes_"))
    try:
        n = decode_all(clip, tmp, width)
        missing = [k for k in want if not (tmp / f"{k:05d}.jpg").is_file()]
        if missing:
            print(f"warning: {len(missing)} of {len(want)} wanted frames are past the decoded clip "
                  f"({n} frames); they will be skipped (first {missing[:5]})")
            want = [k for k in want if k not in set(missing)]
        for k in want:
            dst = cache_dir / f"{k:04d}.jpg"
            shutil.copyfile(tmp / f"{k:05d}.jpg", dst)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    manifest = {
        "recording": recording,
        "category": rec["category"],
        "clip": rec["clip"],
        "sd_clip_root": str(CLIP_ROOT),
        "width": width,
        "n_sd_frames_decoded": n,
        "n_wanted": len(want),
        "n_simultaneous": len({r["sd_simultaneous"] for r in rows if r["in_clip"] == 1}),
        "n_outside_clip": outside,
        "sd_frame_min": min(want) if want else None,
        "sd_frame_max": max(want) if want else None,
        "a_measured": rec.get("a_measured"),
        "b": rec.get("b"),
        "offset_frames": rec.get("offset_frames"),
        "tier": rec.get("tier"),
        "index_csv_sha256": hashlib.sha256(INDEX_CSV.read_bytes()).hexdigest()[:16],
        "extracted_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "note": ("SD frames are indexed per the retime fit; 'simultaneous' means same wall moment as the "
                 "sonar frame. The published gopro/<f>.jpg is NOT checked in here on purpose: it carries the "
                 "release-time offset and would reintroduce the bug."),
    }
    manifest_p.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{recording}: kept {len(want)} frames ({outside} sonar frames fall outside the clip) -> {cache_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--recording", required=True)
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--check", type=int, default=None, metavar="SONAR_FRAME")
    a = ap.parse_args(argv)
    if a.check is not None:
        return check(a.recording, a.check, CACHE / a.recording, a.width)
    return extract(a.recording, a.width, a.force)


if __name__ == "__main__":
    raise SystemExit(main())
