"""Run the arc detector on EVERY frame of every recording a human already signed.

Why this exists
---------------
The review sheets only carried 100 frames per recording (5 sheets x 20 tiles). That
is a sampling decision, not a property of the data: 26 signed recordings hold 19,254
frames in total, and on the good ones the arc is present on essentially every frame.
So the candidate pool is ~20k, not ~1k -- the 1k was simply what a human looked at.

This script produces that full pool. It does NOT touch the 100-sample review, the
decisions, or the sheets; it writes a separate proposals_full.jsonl per recording so
the signed material stays exactly as it was.

Chaining matters: detect_arc() picks the component that contains the window's
brightest pixel, so a fresh call each frame can hop onto the pool-bottom arc. Passing
prev_center forward keeps the same object frame to frame (same rule as the sheets).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import _bootstrap  # noqa: F401
from engine import arc as A
from engine import geometry as G
from PIL import Image
import numpy as np


def run_one(rec_root: Path, verbose: bool = False) -> dict:
    rec = rec_root.name
    spec = G.load_recording(rec, with_meta=False)
    frames = sorted(spec.frames)
    out = rec_root / "candidates" / "proposals_full.jsonl"
    prev = None
    hits = 0
    t0 = time.time()
    with out.open("w", encoding="utf-8") as fh:
        for i, fr in enumerate(frames):
            img = np.asarray(Image.open(spec.pgm_path(fr)))
            blob = A.detect_arc(img, prev_center=prev)
            if blob:
                hits += 1
                # detect_arc reads prev_center as (x, y) = (beam, row); the
                # centroid is stored (row, beam). Swapping them put the search
                # window off-image and killed the chain after frame 1.
                b = blob["box_xyxy"]
                prev = ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)
            row = {
                "recording": rec,
                "frame": int(fr),
                "mode": "arc-full",
                "shape_hw": [int(img.shape[0]), int(img.shape[1])],
                "blobs": [blob] if blob else [],
                "provenance": {"engine_version": A.ENGINE_VERSION, "chained": True,
                               "prev_center_in": None if i == 0 else "carried"},
            }
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            if verbose and i % 200 == 0:
                print(f"  {rec} {i}/{len(frames)} hits={hits}", flush=True)
    return {"recording": rec, "frames": len(frames), "hits": hits,
            "pct": round(100.0 * hits / max(1, len(frames)), 1),
            "secs": round(time.time() - t0, 1), "out": str(out)}


def main(argv=None) -> int:
    root = Path("out/sonar_arc_annotation")
    todo = []
    for d in sorted(root.glob("2023-*")):
        dec = d / "review" / "decisions.json"
        if dec.exists() and json.loads(dec.read_text(encoding="utf-8")):
            todo.append(d)
    res = [run_one(d) for d in todo]
    (root / "full_run.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in res:
        print(f'{r["recording"]} frames {r["frames"]:5d} hits {r["hits"]:5d} ({r["pct"]:5.1f}%) {r["secs"]}s', flush=True)
    print("total frames", sum(r["frames"] for r in res), "hits", sum(r["hits"] for r in res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
