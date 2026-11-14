"""Predicted range band for one recording -- "target sits somewhere on this ring".

What this is
------------
A *range-only* prior.  Given the platform track (`gantry.csv`), the sensor offset from the
rotation centre, and the detections of one recording, we fit a single world point P and a
range bias b to  ``range_i = |P - c_i| + b``.  If that model explains the detections, then
for *any* frame we can predict which row the return must land on::

    row = (|P - c_f| + b - WindowStart) / res_m

What this is **not**
--------------------
It predicts no azimuth.  The beam index cannot be recovered from this data: the sonar head
is stabilised (|beam vs world azimuth| r2 < 0.01) and the camera box centre moves only a few
pixels across a whole recording, so there is no lever arm to identify the beam-per-degree
factor.  A card drawn from this file therefore shows a horizontal *band*, never a box.

Honesty gate
------------
If the single-point model cannot explain the detections (p90 residual > 0.15 m), we do not
invent a tight band.  We report ``status: "unreliable_model"`` and fall back to the *observed*
range spread trimmed by MAD, which is a statement about our detections, not about the target.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import geometry                      # noqa: E402
from tools import locate as L                    # noqa: E402

SCHEMA = "sonar_llm_annotation/rangeband/v0"
MODEL_P90_LIMIT = 0.15          # metres; above this the single-point model is not believed
MIN_ROWS = 6                    # a band narrower than this is not worth drawing


def _load_props(path: Path) -> List[dict]:
    """Flattened detections (one row per blob) -- the same loader `locate.py` uses.

    A proposals file holds one JSON object per *frame* with a ``blobs`` list; reading it as
    one row per line silently yields zero detections, because the top level has no ``snr``.
    """
    if not path.exists():
        return []
    return L.load_proposals(path)


def build(recording: str, min_snr: float = 6.0, max_frames: Optional[int] = None) -> dict:
    rec = geometry.load_recording(recording)
    rec_dir = geometry._rec_dir(recording)
    props = [r for r in _load_props(ROOT / "out" / recording / "proposals.jsonl")
             if r.get("snr", 0.0) >= min_snr]
    if max_frames:
        props = props[:max_frames]

    gantry = L.load_gantry(rec_dir)
    offset = L.chain_offset()
    use = [r for r in props if r["frame"] in gantry]
    out: Dict[str, object] = {
        "schema": SCHEMA,
        "recording": recording,
        "source": "fit_point(gantry track + compact detections)",
        "n_detections": len(use),
        "res_m": rec.res_m,
        "window_start_m": float(rec.header["WindowStart"]),
        "azimuth": "not predicted (see module docstring)",
    }
    if len(use) < 12:
        out.update(status="insufficient_detections", frames={})
        return out

    C = np.array([np.array(gantry[r["frame"]]) + offset for r in use])
    ranges = np.array([float(rec.header["WindowStart"]) + r["cy"] * rec.res_m for r in use])
    P, b, resid = L.fit_point(C, ranges)
    absr = np.abs(resid)
    med, p90 = float(np.median(absr)), float(np.percentile(absr, 90))

    # --- is the fit even identifiable?  A parameter resting on its bound means the data did
    # not choose it, and the small in-sample residual then proves nothing.
    bounds = {
        "b": abs(abs(b) - L.B_HI) < 1e-3,
        "z": abs(float(P[2]) - L.P_Z_LO) < 1e-3 or abs(float(P[2]) - L.P_Z_HI) < 1e-3,
        "xy": bool(np.any(np.abs(P[:2]) >= L.P_XY_MAX - 1e-3)),
    }
    at_bound = any(bounds.values())

    # --- out-of-sample check: fit on alternating frames, predict the rest.  The in-sample
    # residual is optimistic whenever P and b trade off (the head moves ~0.2 m inside a
    # 1.5 m range, so the profile is nearly flat -- the degeneracy uxo_projection.py bounds).
    idx = np.arange(len(use))
    even, odd = idx % 2 == 0, idx % 2 == 1
    ho = []
    for tr, te in ((even, odd), (odd, even)):
        if tr.sum() >= 8 and te.sum() >= 4:
            P2, b2, _ = L.fit_point(C[tr], ranges[tr])
            ho.append(np.abs(np.linalg.norm(C[te] - P2, axis=1) + b2 - ranges[te]))
    ho_all = np.concatenate(ho) if ho else np.array([np.inf])
    ho_med, ho_p90 = float(np.median(ho_all)), float(np.percentile(ho_all, 90))

    out.update(P=[float(v) for v in P], b_m=float(b),
               residual_m={"median": med, "p90": p90, "max": float(absr.max())},
               holdout_m={"median": ho_med, "p90": ho_p90},
               bounds_active=bounds)
    frames: Dict[str, dict] = {}
    if (not at_bound) and ho_p90 <= MODEL_P90_LIMIT:
        p90 = ho_p90          # band width is judged on the hold-out, never on the in-sample fit
        out["status"] = "model_ok"
        half = max(MIN_ROWS, int(np.ceil(p90 / rec.res_m)))   # p90, not 3*p90: a prior that
        # covers 80% of the returns is what narrows attention; 3*p90 would cover half the image.
        for f in sorted({r["frame"] for r in props}):
            if f not in gantry:
                continue
            c = np.array(gantry[f]) + offset
            rng = float(np.linalg.norm(np.array(P) - c) + b)
            row = int(round((rng - float(rec.header["WindowStart"])) / rec.res_m))
            frames[str(f)] = {"range_m": round(rng, 4), "row": row,
                              "row_lo": row - half, "row_hi": row + half}
        out["band_rows"] = half
        out["note"] = ("row band = fitted range +- p90 residual (80% of returns); "
                       "azimuth unresolved")
    else:
        out["status"] = "unreliable_model"
        spread = float(np.median(np.abs(ranges - np.median(ranges))))
        half = max(MIN_ROWS, int(np.ceil(3 * spread / rec.res_m)))
        row0 = int(round((float(np.median(ranges)) - float(rec.header["WindowStart"])) / rec.res_m))
        for f in sorted({r["frame"] for r in props}):
            frames[str(f)] = {"range_m": round(float(np.median(ranges)), 4), "row": row0,
                              "row_lo": row0 - half, "row_hi": row0 + half}
        out["band_rows"] = half
        why = ("parameter on its bound (%s)" % ", ".join(k for k, v in bounds.items() if v)
               if at_bound else f"hold-out p90 {ho_p90:.2f} m > {MODEL_P90_LIMIT} m")
        out["note"] = ("single fixed point does not explain this recording "
                       f"({why}); band is the OBSERVED range spread, not a prediction")
    out["frames"] = frames
    return out


def write(recording: str, **kw) -> dict:
    data = build(recording, **kw)
    path = ROOT / "out" / recording / "band.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, sort_keys=False), encoding="utf-8")
    return data


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="predicted range band for one recording")
    ap.add_argument("--recording", required=True)
    ap.add_argument("--min-snr", type=float, default=6.0)
    ap.add_argument("--max-frames", type=int, default=None)
    a = ap.parse_args(argv)
    d = write(a.recording, min_snr=a.min_snr, max_frames=a.max_frames)
    print(f"[rangeband] {a.recording} status={d['status']} n={d['n_detections']} "
          f"band_rows={d.get('band_rows')}")
    if "P" in d:
        print(f"  P={[round(v,3) for v in d['P']]} b={d['b_m']:.3f} "
              f"resid med {d['residual_m']['median']:.3f} holdout med "
              f"{d['holdout_m']['median']:.3f} p90 {d['holdout_m']['p90']:.3f} m")
    if d["status"] != "model_ok":
        print(f"  {d.get('note','')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
