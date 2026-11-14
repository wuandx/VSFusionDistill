"""Locate a world-fixed echo from sonar ranges + the gantry path (and recover the FOV).

Why this exists
---------------
The user's proposal: "we know where the camera and the sonar sit relative to each other,
and we know the camera intrinsics -- so we should be able to compute roughly where the
target lands in the sonar image, then let the model look there."

That is right, and the original repository already implements the full version of it in
``aodet/datasets/converters/uxo_projection.py`` (GoPro linear intrinsics, translations
from ``gantry.csv`` + ``calibration/transforms.yaml``, per-recording least squares for the
target position, the camera offset rotation, the sonar rotation and a range bias). Reading
it also settles what ``gantry.csv`` is: **the platform's own path**, not the target's.

This module is the smallest piece of that model that can be tested without scipy: if the
echo we detect belongs to one fixed point in the gantry frame, then its slant range in
every frame must equal ``|P - c_i| + b``, where ``c_i`` is the sonar origin for frame ``i``.
Fitting ``P`` (3) and ``b`` (1) to a few hundred observed ranges either works -- and then we
know where the echo is, how big the residual is, and we can regress beam angle against the
predicted azimuth to *measure* the horizontal FOV -- or it fails, and we learn that the
echo is not a single fixed point.

What it cannot do: decide what the echo is. ``identity`` stays ``unresolved``.

Usage
-----
    python tools/locate.py --recording 2023-09-21_105230
    python tools/locate.py --recording 2023-09-21_105230 --max-frames 200 --min-snr 6
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics as st
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import geometry  # noqa: E402

# static chain calibration/transforms.yaml: child <- parent, (translation, quat x,y,z,w)
T_PC_AR3 = ((0.0, 0.174, -0.338), (0.0, 1.0, 0.0, 0.0))
T_ARIS_AR3 = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))
T_SONAR_ARIS = ((-0.108725, 0.0, 0.0), (0.5, 0.5, 0.5, 0.5))


def quat_to_R(q):
    x, y, z, w = q
    n = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
    x, y, z, w = x / n, y / n, z / n, w / n
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def chain_offset():
    """Sonar origin in the portal_crane frame (translation only, as the repo does)."""
    t1, q1 = T_PC_AR3
    t2, q2 = T_ARIS_AR3
    t3, q3 = T_SONAR_ARIS
    R1, R2 = quat_to_R(q1), quat_to_R(q2)
    return np.array(t1) + R1 @ (np.array(t2) + R2 @ np.array(t3))


def load_gantry(rec_dir: Path):
    out = {}
    with open(rec_dir / "gantry.csv", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[int(row["aris_frame_idx"])] = (float(row["x"]), float(row["y"]), float(row["z"]))
    return out


def load_proposals(path: Path):
    """Top-1 blob per frame from a proposals.jsonl written by engine.compact."""
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        blobs = r.get("blobs") or ([r["candidate"]] if r.get("candidate") else [])
        if not blobs:
            continue
        b = blobs[0]
        # engine.compact writes centroid as (row, col); the image is (rows, beams)
        row, col = b["centroid"]
        rows.append({"frame": int(r["frame"]), "cx": float(col), "cy": float(row),
                     "snr": float(b.get("snr", 0)), "beam_span": int(b.get("beam_span", 0)),
                     "row_span": int(b.get("row_span", 0)), "area": int(b.get("area", 0))})
    return rows


B_LO, B_HI = -0.30, 0.30        # a real echo offset is bounded by half the longest target
P_XY_MAX, P_Z_LO, P_Z_HI = 2.5, -2.0, -0.30


def _clamp(th):
    th[:2] = np.clip(th[:2], -P_XY_MAX, P_XY_MAX)
    th[2] = np.clip(th[2], P_Z_LO, P_Z_HI)
    th[3] = np.clip(th[3], B_LO, B_HI)
    return th


def fit_point(C, r_obs, b0=0.0, iters=200):
    """Bounded Levenberg-Marquardt for ``r_i = |P - c_i| + b``; Huber weights.

    The bounds are not cosmetic.  With the target near the arc centre the range profile is
    almost flat, so ``b`` and the radial distance of ``P`` trade off against each other; left
    free, the fit runs away to b = -64 m (observed here) or b = -16 m (observed by the
    authors of uxo_projection.py, who bound it the same way).
    """
    centres = C.mean(axis=0)
    starts = [centres + np.array([0.0, 0.0, dz]) for dz in (-0.5, -1.0, -1.5)]
    best = None
    for P0 in starts:
        th, cost = _fit_from(C, r_obs, np.concatenate([P0, [b0]]))
        if best is None or cost < best[1]:
            best = (th, cost)
    return best[0][:3], float(best[0][3]), _resid(C, r_obs, best[0])


def _resid(C, r_obs, th):
    return np.linalg.norm(C - th[:3], axis=1) + th[3] - r_obs


def _fit_from(C, r_obs, theta):
    theta = _clamp(theta.copy())
    iters = 200

    def resid(th):
        P, b = th[:3], th[3]
        d = np.linalg.norm(C - P, axis=1)
        return d + b - r_obs

    lam = 1e-3
    prev = None
    for _ in range(iters):
        r = _resid(C, r_obs, theta)
        # Huber weights (delta = 0.05 m): a handful of wrong blobs cannot drag the fit
        a = np.abs(r)
        w = np.where(a <= 0.05, 1.0, 0.05 / np.maximum(a, 1e-9))
        d = np.linalg.norm(C - theta[:3], axis=1)
        d = np.maximum(d, 1e-6)
        J = np.column_stack([-(C - theta[:3]) / d[:, None], np.ones(len(C))])
        Jw = J * w[:, None]
        rw = r * w
        A = Jw.T @ J + lam * np.eye(4)
        g = Jw.T @ rw
        step = np.linalg.solve(A, -g)
        theta_new = _clamp(theta + step)
        cost, cost_new = float((r ** 2).sum()), float((_resid(C, r_obs, theta_new) ** 2).sum())
        if cost_new < cost:
            theta, lam = theta_new, max(lam * 0.5, 1e-9)
        else:
            lam *= 4.0
        if prev is not None and abs(prev - cost_new) < 1e-12:
            theta = theta_new if cost_new <= cost else theta
            break
        prev = min(cost, cost_new)
    return theta, float((_resid(C, r_obs, theta) ** 2).sum())


def analyse(recording: str, proposals: Path, min_snr: float, max_frames: int):
    rec = geometry.load_recording(recording)
    rec_dir = geometry._rec_dir(recording)
    gantry = load_gantry(rec_dir)
    off = chain_offset()
    rows = [r for r in load_proposals(proposals) if r["snr"] >= min_snr and r["frame"] in gantry]
    if max_frames and len(rows) > max_frames:
        step = len(rows) / max_frames
        rows = [rows[int(i * step)] for i in range(max_frames)]

    C = np.array([np.array(gantry[r["frame"]]) + off for r in rows])
    res_m = rec.res_m
    ws = float(rec.header["WindowStart"])
    rng = np.array([ws + r["cy"] * res_m for r in rows])
    P, b, resid = fit_point(C, rng)

    # --- does the beam angle follow the predicted azimuth?  (this is the FOV measurement)
    horiz = P[None, :2] - C[:, :2]
    az = np.degrees(np.arctan2(horiz[:, 1], horiz[:, 0]))
    az_u = np.unwrap(np.radians(az)) * 180 / math.pi
    beam = np.array([r["cx"] for r in rows])
    A = np.vstack([az_u, np.ones_like(az_u)]).T
    (slope, icpt), *_ = np.linalg.lstsq(A, beam, rcond=None)
    pred = A @ np.array([slope, icpt])
    ss_res = float(((beam - pred) ** 2).sum())
    ss_tot = float(((beam - beam.mean()) ** 2).sum())
    r2 = 1 - ss_res / max(ss_tot, 1e-12)
    fov_deg = abs(128.0 / slope) if abs(slope) > 1e-9 else float("inf")

    return {
        "schema": "sonar-llm-annotation/locate/v1",
        "recording": recording,
        "category": rec.category,
        "n_frames": len(rows),
        "params": {"min_snr": min_snr, "res_m": res_m, "window_start_m": ws,
                   "chain_offset_m": [round(float(v), 4) for v in off]},
        "fit": {
            "target_P_odom_m": [round(float(v), 4) for v in P],
            "range_bias_b_m": round(b, 4),
            "residual_m": {"median": round(float(np.median(np.abs(resid))), 4),
                           "p90": round(float(np.percentile(np.abs(resid), 90)), 4),
                           "max": round(float(np.max(np.abs(resid))), 4)},
        },
        "beam_vs_azimuth": {
            "slope_beams_per_deg": round(float(slope), 4),
            "intercept_beams": round(float(icpt), 2),
            "r2": round(float(r2), 4),
            "implied_fov_deg": round(float(fov_deg), 1) if math.isfinite(fov_deg) else None,
            "note": ("if r2 is high, the head is NOT re-aimed (beam tracks the world azimuth) -- "
                     "then 128/slope is a direct FOV measurement; if r2 is low the head is "
                     "stabilised and the beam carries no azimuth information"),
        },
        "observed": {"range_m": {"min": round(float(rng.min()), 3), "max": round(float(rng.max()), 3)},
                     "beam": {"min": int(beam.min()), "max": int(beam.max())}},
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recording", required=True)
    ap.add_argument("--proposals", default=None)
    ap.add_argument("--min-snr", type=float, default=6.0)
    ap.add_argument("--max-frames", type=int, default=300)
    a = ap.parse_args(argv)
    proposals = Path(a.proposals) if a.proposals else ROOT / "out" / a.recording / "proposals.jsonl"
    res = analyse(a.recording, proposals, a.min_snr, a.max_frames)
    out = ROOT / "out" / ("locate_%s.json" % a.recording)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    f = res["fit"]
    print("%s  n=%d" % (a.recording, res["n_frames"]))
    print("  P = %s  b = %.3f m" % (f["target_P_odom_m"], f["range_bias_b_m"]))
    print("  |residual| median %.4f  p90 %.4f  max %.4f m"
          % (f["residual_m"]["median"], f["residual_m"]["p90"], f["residual_m"]["max"]))
    bv = res["beam_vs_azimuth"]
    print("  beam vs azimuth: slope %.3f beams/deg  r2 %.3f  -> FOV %s deg"
          % (bv["slope_beams_per_deg"], bv["r2"], bv["implied_fov_deg"]))
    print("  -> %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
