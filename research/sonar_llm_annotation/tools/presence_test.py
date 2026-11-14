"""Presence/absence test: is the 110229 near-range blob special, or is it everywhere?

Why this test, and why it does not cite the old pipeline
-------------------------------------------------------
D1 in docs/DECISIONS.md says the previous project's conclusions are not evidence
here.  So the question "is this return the target or the scene?" has to be answered
by measurement on the recordings themselves.

The shape of the question that *can* be answered without any ground truth:

    110229 has a compact return at rows ~108-124, i.e. range ~1.02-1.06 m.
    Every recording shares the same range axis (WindowStart 0.6949 m,
    RES 0.002983 m/row), so row 110 means the same distance in all of them.
    If that near-range annulus is busy in most recordings, the blob is a property
    of the tank/buoy (a fixed reflector at that standoff), not of what was
    deployed that day.  If nearly every other recording is empty there, 110229
    is carrying something the others are not.

This is a *presence* test, not an identity test: it can demote "special" to
"ordinary", and cannot by itself promote a blob to "target".  Both outcomes are
written out, because the empty outcome is only suggestive -- the target could
have been off-axis that day.

Frames are sampled (every N) for speed; the detector is the same `engine.compact`
used for proposals, with its defaults untouched.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import compact as C  # noqa: E402
from engine import echo as E     # noqa: E402
from engine import geometry as G  # noqa: E402

ROW_LO, ROW_HI = 95, 155          # the near-range annulus around 110229's blob
BEAM_LO, BEAM_HI = 0, 127         # full sector unless --beams narrows it
EVERY = 12
MAX_FRAMES = 70

# Snr is mean/sigma of a block-median residual; on a frame whose residual is
# numerically flat the sigma can round to ~0 and the ratio explodes.  Those
# values are not measurements of brightness -- they are 0/0 -- so they are
# quarantined rather than reported.
SNR_ABSURD = 1000.0


def scan(rec_name: str) -> dict:
    rec = G.load_recording(rec_name)
    frames = sorted(rec.frames)[::EVERY][:MAX_FRAMES]
    hits, best = 0, None
    for f in frames:
        img = E.read_pgm(rec.pgm_path(f)).astype(np.float64)
        blobs = C.detect_compact(img)["blobs"]
        inside = [b for b in blobs
                  if ROW_LO <= b["centroid"][0] <= ROW_HI
                  and BEAM_LO <= b["centroid"][1] <= BEAM_HI
                  and b["beam_span"] <= 40
                  and b["snr"] < SNR_ABSURD]
        if inside:
            hits += 1
            top = max(inside, key=lambda b: b["snr"])
            if best is None or top["snr"] > best["snr"]:
                best = {"frame": f, "snr": round(top["snr"], 2),
                        "row": round(top["centroid"][0], 1),
                        "beam": round(top["centroid"][1], 1),
                        "beam_span": top["beam_span"], "row_span": top["row_span"]}
    return {"recording": rec_name, "n_frames": len(frames),
            "n_frames_with_blob_in_annulus": hits,
            "hit_frac": round(hits / max(1, len(frames)), 3),
            "best": best}


def main(argv=None) -> int:
    global ROW_LO, ROW_HI, BEAM_LO, BEAM_HI, EVERY
    import argparse
    ap = argparse.ArgumentParser(description="presence/absence of a compact return in one row/beam window")
    ap.add_argument("--rows", required=True, help="e.g. 95,155")
    ap.add_argument("--beams", default="0,127", help="beam window, e.g. 43,77 (default full sector)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--every", type=int, default=EVERY)
    a = ap.parse_args(argv)
    ROW_LO, ROW_HI = (int(v) for v in a.rows.split(","))
    BEAM_LO, BEAM_HI = (int(v) for v in a.beams.split(","))
    EVERY = a.every
    sys.path.insert(0, str(ROOT / "plugin"))
    from sonarllm.dataset import MANIFEST  # single source of truth for the recording list

    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    recs = sorted({it["recording"] for it in man["items"]})
    rows = []
    for i, r in enumerate(recs, 1):
        try:
            rows.append(scan(r))
        except Exception as e:  # noqa: BLE001 - a broken recording must not stop the sweep
            rows.append({"recording": r, "error": f"{type(e).__name__}: {e}"})
        print(f"[{i:2d}/{len(recs)}] {r}  {rows[-1].get('n_frames_with_blob_in_annulus')}"
              f"/{rows[-1].get('n_frames')}  {rows[-1].get('error','')}", flush=True)

    ok = [r for r in rows if "error" not in r]
    ok.sort(key=lambda r: -r["hit_frac"])
    dst = ROOT / "out" / a.out
    dst.write_text(json.dumps({
        "schema": "sonar_llm_annotation/presence_test/v1",
        "question": (f"is a compact return at rows {ROW_LO}-{ROW_HI}, beams {BEAM_LO}-{BEAM_HI} "
                     f"common across recordings?"),
        "window": {"rows": [ROW_LO, ROW_HI], "beams": [BEAM_LO, BEAM_HI]},
        "every": EVERY, "max_frames": MAX_FRAMES,
        "detector": "engine.compact defaults",
        "caveat": ("presence only; an empty recording does not prove the target was absent. "
                   "Beam index is body-fixed: comparing the same beam across recordings assumes "
                   "the head pointed the same way, which is NOT established. "
                   f"blobs with snr>={SNR_ABSURD} are quarantined as 0/0, not as brightness."),
        "recordings": rows,
        "ranking": [{"recording": r["recording"], "hit_frac": r["hit_frac"],
                     "best_snr": (r["best"] or {}).get("snr")} for r in ok],
        "caveat": ("presence only; an empty recording does not prove the target was absent. "
                   f"blobs with snr>={SNR_ABSURD} are quarantined as 0/0, not as brightness."),
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n%-24s %-7s %-8s %s" % ("recording", "hit", "best_snr", "best row/beam"))
    for r in ok:
        b = r["best"] or {}
        print("%-24s %-7.2f %-8s %s/%s" % (r["recording"], r["hit_frac"],
                                           b.get("snr"), b.get("row"), b.get("beam")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
