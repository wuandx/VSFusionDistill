"""Keyframe propagation: annotate one frame, get the whole recording.

This implements the idea the user pointed at in Zero2YoloYard (label frame 1, let
the machine carry it through the sequence), with the one change this data forces:

    in these recordings the *coherent* motion belongs to the structure
    (turntable / stand / tank wall), not to the target.

So the estimated path is used twice:

  1. to cancel the structure (align every frame to the keyframe before
     subtracting the background), and
  2. to carry a box drawn on ONE keyframe along the same path.

What comes out is a *candidate* box per frame plus the evidence needed to reject
it (alignment score, shift magnitude, and - crucially - the bound clip flag,
because a shift pinned at the search limit is not a measurement).

Nothing here claims a physical object. It claims "the thing you boxed on the
keyframe is still at this place in frame N, to within the alignment error".
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import echo
from . import geometry as G

# search windows: the structure drifts by tens of rows inside one recording
# (bomb: -40..+43 rows, grenade: -5..+53, mortar: -19..+15), so a +-40 window
# used for frame-to-frame steps is far too small for a keyframe-to-frame path.
LOCAL_ROW, LOCAL_BEAM = 14, 5
GLOBAL_ROW_MARGIN, GLOBAL_BEAM_MARGIN = 24, 8
GLOBAL_ROW_CAP, GLOBAL_BEAM_CAP = 160, 24


# ----------------------------------------------------------------------------------
# projections
# ----------------------------------------------------------------------------------


def masked_mean_profile(img: np.ndarray, band: np.ndarray, axis: int) -> np.ndarray:
    """Mean of the band members along one axis, mean-removed.

    Why not the median: with a band covering ~11% of the frame, the median along an
    axis is 0 almost everywhere (measured: 0/128 non-zero beam profiles), the profile
    collapses to a constant, and normalised correlation then has a zero denominator.
    That is what made ``echo.estimate_shift`` return ``drow=-max_lag`` with
    ``align_score=-1.0`` on every frame.
    """
    w = band.astype(np.float64)
    s = (np.asarray(img, dtype=np.float64) * w).sum(axis=axis)
    n = w.sum(axis=axis)
    p = np.divide(s, n, out=np.zeros_like(s), where=n > 0)
    m = n > 0
    if m.sum() < 8:
        return np.zeros_like(p)
    return np.where(m, p - p[m].mean(), 0.0)


def best_lag(a: np.ndarray, b: np.ndarray, max_lag: int) -> Tuple[int, float]:
    """Lag of ``b`` relative to ``a`` maximising normalised correlation."""
    n = len(a)
    best, best_c = 0, -2.0
    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            x, y = a[lag:], b[: n - lag]
        else:
            x, y = a[: n + lag], b[-lag:]
        if x.size < 8:
            continue
        xc, yc = x - x.mean(), y - y.mean()
        den = float(math.sqrt(float((xc * xc).sum()) * float((yc * yc).sum())))
        c = float((xc * yc).sum()) / den if den > 1e-9 else -1.0
        if c > best_c:
            best, best_c = lag, c
    return best, best_c


def structure_band(ref: np.ndarray, pct: float = 90.0) -> np.ndarray:
    """The bright structure domain of a reference frame."""
    band = np.asarray(ref) >= np.percentile(np.asarray(ref), pct)
    if band.sum() < 200:
        band = np.asarray(ref) >= np.percentile(np.asarray(ref), 75)
    return band


def estimate_shift(a: np.ndarray, b: np.ndarray, band: np.ndarray,
                   max_row: int = GLOBAL_ROW_CAP, max_beam: int = GLOBAL_BEAM_CAP) -> dict:
    """Shift of ``b`` relative to ``a`` on the structure band.

    Delegates to ``engine/echo.py``.  This module used to carry its own copy of the
    estimator, and that copy kept the original defect (a sparse band collapsed the
    profile to a constant, so ``best_lag`` returned -max_lag with score -1).  Two
    implementations of the same measurement is how the two halves of a report end up
    disagreeing, so there is now exactly one: echo's, which builds the profile from the
    full orthogonal axis and reports ``ok=False`` on a degenerate band.

    Returns the lag *and* ``clipped``: true when the optimum sits on the search bound,
    which means the real shift is outside the window and the number is a floor, not a
    measurement.
    """
    return echo.estimate_shift(a, b, band=band, max_row=max_row, max_beam=max_beam)


# ----------------------------------------------------------------------------------
# path
# ----------------------------------------------------------------------------------


def _frames_of(rec) -> Tuple["G.Recording", List[int]]:
    r = rec if isinstance(rec, G.Recording) else G.load_recording(str(rec))
    return r, list(r.frames)


def track_path(rec, keyframe: int, frames: Optional[Sequence[int]] = None,
               local_row: int = LOCAL_ROW, local_beam: int = LOCAL_BEAM,
               pct: float = 90.0) -> dict:
    """Cumulative (drow, dbeam) of every frame relative to ``keyframe``.

    Two passes:

    * pass 1 chains *local* estimates between consecutive frames (small window,
      reliable, but drifts);
    * pass 2 re-estimates every frame against the keyframe with a window sized by
      the pass-1 prediction, and overrides wherever that direct estimate is better.

    The result keeps both candidates so the disagreement is visible instead of
    being averaged away.
    """
    r, all_frames = _frames_of(rec)
    fset = list(frames) if frames else all_frames
    if keyframe not in fset:
        raise KeyError(f"keyframe {keyframe} not in recording {r.recording}")

    ref = echo.read_pgm(r.pgm_path(keyframe)).astype(np.float32)
    band = structure_band(ref, pct)

    # ---- pass 1: local chaining
    order = [f for f in fset if f >= keyframe] + [f for f in sorted(fset, reverse=True) if f < keyframe]
    path: Dict[int, dict] = {keyframe: {"drow": 0, "dbeam": 0, "score": 1.0,
                                        "source": "keyframe", "clipped": False}}
    prev = keyframe
    prev_img = ref
    for f in order:
        if f == keyframe:
            continue
        img = echo.read_pgm(r.pgm_path(f)).astype(np.float32)
        s = estimate_shift(prev_img, img, band, max_row=local_row, max_beam=local_beam)
        base = path[prev]
        path[f] = {"drow": int(base["drow"] + s["drow"]),
                   "dbeam": int(base["dbeam"] + s["dbeam"]),
                   "score": s["score"], "source": "chain", "clipped": s["clipped"],
                   "local": {"drow": s["drow"], "dbeam": s["dbeam"]}}
        prev, prev_img = f, img

    # ---- pass 2: direct vs keyframe, window around the chained prediction
    for f in fset:
        if f == keyframe:
            continue
        pred = path[f]
        mr = int(min(GLOBAL_ROW_CAP, abs(pred["drow"]) + GLOBAL_ROW_MARGIN))
        mb = int(min(GLOBAL_BEAM_CAP, abs(pred["dbeam"]) + GLOBAL_BEAM_MARGIN))
        img = echo.read_pgm(r.pgm_path(f)).astype(np.float32)
        d = estimate_shift(ref, img, band, max_row=mr, max_beam=mb)
        pred["direct"] = {k: d[k] for k in ("drow", "dbeam", "score", "clipped")}
        if d["score"] > pred["score"] and not d["clipped"]:
            pred.update({"drow": d["drow"], "dbeam": d["dbeam"],
                         "score": d["score"], "source": "direct"})

    rows = [{"frame": int(f), "drow": int(path[f]["drow"]), "dbeam": int(path[f]["dbeam"]),
             "score": float(path[f]["score"]), "source": path[f]["source"],
             "clipped": bool(path[f]["clipped"]),
             "chain": path[f].get("local", {}),
             "direct": path[f].get("direct", {})}
            for f in fset]
    scores = np.array([x["score"] for x in rows], dtype=float)
    return {
        "recording": r.recording,
        "keyframe": int(keyframe),
        "n_rows": r.n_rows, "n_beams": r.n_beams,
        "band_pixels": int(band.sum()),
        "frames": rows,
        "score_median": float(np.median(scores)),
        "score_p10": float(np.percentile(scores, 10)),
        "drow_range": [int(min(x["drow"] for x in rows)), int(max(x["drow"] for x in rows))],
        "dbeam_range": [int(min(x["dbeam"] for x in rows)), int(max(x["dbeam"] for x in rows))],
        "clipped_frac": float(np.mean([x["clipped"] for x in rows])),
    }


# ----------------------------------------------------------------------------------
# propagation
# ----------------------------------------------------------------------------------


def clip_box(box: Sequence[float], n_rows: int, n_beams: int) -> List[int]:
    x1, y1, x2, y2 = [int(round(v)) for v in box]
    x1, x2 = max(0, min(x1, n_beams - 1)), max(1, min(x2, n_beams))
    y1, y2 = max(0, min(y1, n_rows - 1)), max(1, min(y2, n_rows))
    return [x1, y1, x2, y2]


def propagate(rec, keyframe: int, box: Sequence[float], frames: Optional[Sequence[int]] = None,
              min_score: float = 0.55, **kw) -> dict:
    """Carry ``box`` (beam,row,beam,row) from ``keyframe`` to every frame.

    ``auto`` is true only where the alignment is trustworthy *and* the shift is a
    measurement rather than a clipped floor. Everything else is reported as a
    candidate that a human still has to look at.
    """
    path = track_path(rec, keyframe, frames, **kw)
    n_rows, n_beams = path["n_rows"], path["n_beams"]
    out = []
    for fr in path["frames"]:
        b = clip_box([box[0] + fr["dbeam"], box[1] + fr["drow"],
                      box[2] + fr["dbeam"], box[3] + fr["drow"]], n_rows, n_beams)
        auto = bool(fr["score"] >= min_score and not fr["clipped"])
        out.append({
            "frame": fr["frame"], "box": b,
            "drow": fr["drow"], "dbeam": fr["dbeam"],
            "align_score": fr["score"], "clipped": fr["clipped"],
            "auto": auto, "source": fr["source"],
        })
    return {
        "recording": path["recording"],
        "keyframe": path["keyframe"],
        "keyframe_box": list(map(int, box)),
        "n_frames": len(out),
        "n_auto": sum(1 for o in out if o["auto"]),
        "auto_frac": float(np.mean([o["auto"] for o in out])) if out else 0.0,
        "score_median": path["score_median"],
        "path_summary": {k: path[k] for k in ("drow_range", "dbeam_range", "clipped_frac")},
        "frames": out,
    }


def box_contrast(img: np.ndarray, box: Sequence[int]) -> dict:
    """How much the propagated box actually contains.

    ``lift`` is (mean inside) - (mean of a same-size frame, i.e. the global level);
    ``vs_static`` compares against the box kept fixed at the keyframe position,
    which is what a naive "label once, copy everywhere" would produce.
    """
    y1, x1, y2, x2 = box[1], box[0], box[3], box[2]
    inner = img[y1:y2, x1:x2]
    return {"mean": float(inner.mean()) if inner.size else 0.0,
            "n_px": int(inner.size)}


# ----------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="keyframe propagation for sonar frames")
    ap.add_argument("--recording", required=True)
    ap.add_argument("--keyframe", type=int, required=True)
    ap.add_argument("--box", required=True, help="beam1,row1,beam2,row2 at the keyframe")
    ap.add_argument("--out", default=None)
    ap.add_argument("--min-score", type=float, default=0.55)
    ap.add_argument("--limit", type=int, default=0, help="only the first N frames (debug)")
    a = ap.parse_args(argv)

    box = [int(v) for v in a.box.split(",")]
    if len(box) != 4:
        print("--box needs 4 comma separated integers")
        return 2
    rec = G.load_recording(a.recording)
    frames = rec.frames[: a.limit] if a.limit else None
    res = propagate(rec, a.keyframe, box, frames=frames, min_score=a.min_score)

    # evidence: does the propagated box keep the same content as the keyframe?
    kf_img = echo.read_pgm(rec.pgm_path(a.keyframe)).astype(np.float32)
    kf_mean = float(kf_img[box[1]:box[3], box[0]:box[2]].mean())
    sample = res["frames"][:: max(1, len(res["frames"]) // 12)]
    ev = []
    for fr in sample:
        img = echo.read_pgm(rec.pgm_path(fr["frame"])).astype(np.float32)
        moved = float(img[fr["box"][1]:fr["box"][3], fr["box"][0]:fr["box"][2]].mean())
        static = float(img[box[1]:box[3], box[0]:box[2]].mean())
        ev.append({"frame": fr["frame"], "propagated_mean": moved, "static_mean": static,
                   "keyframe_mean": kf_mean, "auto": fr["auto"],
                   "align_score": fr["align_score"]})
    res["contrast_check"] = ev

    dst = Path(a.out) if a.out else Path("out") / f"propagate_{a.recording}_{a.keyframe}.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"{res['recording']} keyframe {res['keyframe']} box {res['keyframe_box']}")
    print(f"  frames {res['n_frames']}  auto {res['n_auto']} ({res['auto_frac']*100:.1f}%)  "
          f"score median {res['score_median']:.3f}")
    print(f"  path {res['path_summary']}")
    print("  contrast check (propagated vs static box, keyframe mean):")
    print(f"    keyframe mean {kf_mean:.2f}")
    for e in ev:
        print(f"    f{e['frame']:04d}  prop {e['propagated_mean']:6.2f}  "
              f"static {e['static_mean']:6.2f}  score {e['align_score']:.3f}  "
              f"auto={e['auto']}")
    print(f"  wrote {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
