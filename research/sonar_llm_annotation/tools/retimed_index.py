"""Turn the per-recording fits in out/camera_retimed.json into a frame-level index table.

One row per ARIS frame:
    sd_simultaneous  the SD camera frame that happened at the same moment as this sonar frame
    sd_released      where the released gopro/<frame>.jpg actually is (labels are drawn on it)
    tier             how well the recording's fit holds: exact (<=3 frames), approx (<=12), broken

The two columns differ by |offset_frames| for that recording, plus whatever the slope error accumulates
towards the ends of the clip.  Nothing is shared across recordings.

usage: python -m tools.retimed_index
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import geometry as G  # noqa: E402


def tier(residual: float) -> str:
    if residual <= 3.0:
        return "exact"
    if residual <= 12.0:
        return "approx"
    return "broken"


def main() -> int:
    payload = json.loads((ROOT / "out" / "camera_retimed.json").read_text(encoding="utf-8"))
    out_csv = ROOT / "out" / "camera_retimed_index.csv"
    n_rows = 0
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["recording", "category", "aris_frame", "sd_simultaneous", "sd_released",
                    "a", "offset_frames", "tier", "residual_max_frames", "in_clip"])
        for r in payload["recordings"]:
            if "a_measured" not in r:
                continue
            a, b, off = r["a_measured"], r["b"], r["offset_frames"]
            t = tier(r["residual_max_abs"])
            n_sd = int(r.get("n_sd_frames") or 0)
            try:
                frames = sorted(G.load_recording(r["recording"]).frames)
            except Exception:  # noqa: BLE001
                continue
            outside = 0
            for f in frames:
                sim = int(round(a * f + b - off))
                rel = int(round(a * f + b))
                ok = 1 if 0 <= sim < n_sd else 0
                outside += 0 if ok else 1
                w.writerow([r["recording"], r["category"], f, sim, rel,
                            f"{a:.4f}", off, t, f"{r['residual_max_abs']:.2f}", ok])
                n_rows += 1
            if outside:
                print(f"  {r['recording']}: {outside}/{len(frames)} frames outside the SD clip")
    print(f"wrote {out_csv.relative_to(ROOT)}  rows={n_rows}")
    tiers: dict[str, int] = {}
    for r in payload["recordings"]:
        if "a_measured" in r:
            tiers[tier(r["residual_max_abs"])] = tiers.get(tier(r["residual_max_abs"]), 0) + 1
    print("recordings by tier:", tiers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
