"""Survey the approved recordings with ``engine.compact`` and rank them (v2).

The question this answers is narrow and honest: *among the 40 approved development
recordings, which ones show a compact, high-SNR, smoothly-moving return* - i.e. the
shape a target echo would have - as opposed to the class-invariant full-width arc
that dominates the three recordings picked in the first pass.

It does **not** decide what that return is. ``identity`` stays ``unresolved``: there
is no sonar GT in this dataset, so "rank 1" means "look at this one first", not
"this one contains UXO".

v2 changes (why)
----------------
v1 counted a frame as "banded" only when the candidate's row had a contiguous bright run
>= 60 beams.  A 3-6 row thick band that crosses the fan is therefore invisible to that
test, which is why ``2023-09-21_100927`` - a recording we already know is a thin band -
ranked 6th.  v2 replaces the run length with two gates that look at the whole frame and at
the geometry:

    beam coverage   fraction of beams touched by any pixel >= p99.5 of the frame, measured
                    on a 5x5-smoothed copy so single-pixel speckle cannot light a beam.
                    A band crossing the fan touches most beams; a compact echo touches a
                    handful.  Unsmoothed coverage is NOT usable: it tracks the far-field
                    noise level (105230: 0.76 raw vs 0.29 smoothed).
    geometry        the longest continuous range track is fitted to one world point P with
                    ``tools.locate.fit_point`` (bounded LM, Huber).  A fixed echo gives a
                    small residual; something that rides with the platform forces the range
                    bias b to its +-0.30 m bound (2023-09-21_110229: b = +0.30, residual
                    0.09 m).  b at the bound means the fit is not a measurement.

Score (multiplicative gates, stated so a reader can disagree explicitly):

    presence    = track_len / n_frames_sampled      how much of the recording the best
                                                    continuous return actually covers
    continuity  = 1 - jumps / (n_top1 - 1)          stability of the top-1 range, whole run
    shape       = 0.35*continuity + 0.35*compactness + 0.15*smoothness + 0.15*brightness
    base        = presence * shape                  presence is a PREcondition, so it
                                                    multiplies instead of adding
    band_factor = 1 - band_gate_frac        (fraction of sampled frames whose coverage
                                             >= band_gate; 1 = never banded)
    geo_factor  = 1.00 / 0.70 / 0.50 / 0.35 (tiered, see the v2 section; never a constant)
    score       = base * band_factor * geo_factor

Why presence multiplies: the first full run put ``101622`` on top with a 20/768-frame chain
(``track_frac`` 0.026) because compactness, smoothness and brightness describe a *blob* and
cannot see that the blob is absent from 97 % of the frames.  Adding presence as one term of
a sum does not fix that - 0.3*presence still leaves 0.7 of shape score for a three-frame
blip.  "There is a return" is a precondition for "the return looks good", so it multiplies.
``compactness``/``smoothness``/``brightness`` keep their v1 definitions, measured on the
associated blobs when a fit exists (those lie on the fitted track), else on the seed chain,
with the step divided by the sampling gap so ``--every 1`` and ``--every 12`` are comparable.

Caveats that travel with every number here: the band gate cannot see a *dim* thin band
whose coverage sits under the threshold (documented per recording), and the geometry gate
says "this track is consistent with one fixed point", not "this fixed point is a target".

Usage
-----
    python tools/census.py --every 12 --refine-top 10
    python tools/census.py --only 2023-09-21_105230 --every 1
    python tools/census.py --legacy --every 12        # reproduce v1 (census.json/CENSUS.md)

Outputs (under ``--out``):
    census_v2.json one record per recording (metrics + score + rank + v1 rank)
    CENSUS-V2.md   the ranked table + method + counterexamples, ready to paste into docs/
    top2/          montage PNGs for the best few recordings
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import compact, geometry  # noqa: E402
from engine.echo import read_pgm_cached  # noqa: E402

sys.path.insert(0, str(ROOT / "tools"))
import locate  # noqa: E402  (reuses fit_point / load_gantry / chain_offset; read-only here)

MANIFEST = ROOT.parent / "DataSet" / "camera_temporal_all" / "manifest-resolved.json"

# Beam span above which a connected component is a full-width structure rather than
# a compact return.  Matches engine.compact.DEFAULTS["band_beams"].
WIDE = 70


def approved_recordings():
    """All 40 approved recordings, each flagged with how many items carry a split role.

    The manifest's scope line says "40 approved development recordings".  Three of them
    have no item with a ``paired_role`` at all - they can be *inspected* but they can never
    be exported into a split, so the flag travels with the record instead of the recording
    being silently dropped from the census.
    """
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    out = {}
    for it in man["items"]:
        rec = it["recording"]
        e = out.setdefault(rec, {"recording": rec, "category": it["category"],
                                 "roles": set(), "n_with_role": 0})
        if it.get("paired_role") in ("train", "val", "val_id"):
            e["roles"].add(it["paired_role"])
            e["n_with_role"] += 1
    for e in out.values():
        e["has_role"] = bool(e["roles"])
        e["roles"] = sorted(e["roles"])
    return out


def beam_coverage(img: np.ndarray, pct: float = 99.0) -> float:
    """Fraction of beams that contain any pixel above the frame's ``pct`` percentile.

    A band crossing the fan lights up *every* beam; a compact return lights up a handful.
    This is the discriminator that separates "structure" from "object-shaped", and unlike a
    contiguous-run length it is not fooled by a thin diagonal line.
    """
    thr = np.percentile(img, pct)
    hit = (img >= thr).any(axis=0)
    return float(hit.mean())


def row_extent(img: np.ndarray, row: int, col: int, pct: float = 90.0) -> int:
    """Length of the contiguous bright run through (row, col) along the beam axis.

    This is the discriminator that actually works: a blob sitting on a line that spans the
    fan has a huge extent (the thi arc case), while a compact return has a short one.  It is
    measured on the blob's own row, so it cannot be fooled by brightness elsewhere.
    """
    row = int(np.clip(row, 0, img.shape[0] - 1))
    col = int(np.clip(col, 0, img.shape[1] - 1))
    line = img[row]
    thr = np.percentile(line, pct)
    hit = line >= thr
    if not hit[col]:
        return 0
    a = col
    while a > 0 and hit[a - 1]:
        a -= 1
    b = col
    while b < len(hit) - 1 and hit[b + 1]:
        b += 1
    return int(b - a + 1)


def arc_width(img: np.ndarray) -> int:
    """Longest run of beams whose column max exceeds p99.5 - the 'full-width band' test.

    Deliberately crude: it is here to separate "a band spanning the frame" from
    "something compact", not to detect anything.
    """
    thr = np.percentile(img, 99.5)
    colmax = (img >= thr).sum(axis=0)
    best = cur = 0
    for v in colmax:
        cur = cur + 1 if v > 0 else 0
        best = max(best, cur)
    return int(best)


def survey(rec: geometry.Recording, every: int, **kw) -> dict:
    frames = list(rec.frames)[:: max(1, every)]
    tops, det, allblobs, wide, covs, exts = [], 0, 0, 0, [], []
    beams, rows, areas, snrs = [], [], [], []
    for f in frames:
        img = read_pgm_cached(rec.pgm_path(f))
        res = compact.detect_compact(img, **kw)
        blobs = res.get("blobs") or []
        covs.append(beam_coverage(img, pct=99.5))
        if blobs:
            b0 = blobs[0]
            r0, c0 = b0["centroid"]          # (row, col)
            ext = row_extent(img, int(round(r0)), int(round(c0)))
            exts.append(ext)
            if ext >= 60:
                wide += 1
        if blobs:
            det += 1
            allblobs += len(blobs)
            b = blobs[0]
            row, col = b["centroid"]          # compact writes (row, col)
            cx, cy = float(col), float(row)
            tops.append((int(f), cx, cy, float(b["snr"]),
                         int(b["beam_span"]), int(b["row_span"]), int(b["area"])))
            beams.append(b["beam_span"])
            rows.append(b["row_span"])
            areas.append(b["area"])
            snrs.append(b["snr"])
    steps = [float(np.hypot(tops[i][1] - tops[i - 1][1], tops[i][2] - tops[i - 1][2]))
             for i in range(1, len(tops))]
    step_med = st.median(steps) if steps else float("nan")
    step_p90 = float(np.percentile(steps, 90)) if steps else float("nan")
    mid = frames[len(frames) // 2]
    aw = arc_width(read_pgm_cached(rec.pgm_path(mid)))
    return {
        "recording": rec.recording,
        "category": rec.category,
        "n_frames": rec.n_frames,
        "n_sampled": len(frames),
        "rows": rec.n_rows,
        "det_rate": det / max(1, len(frames)),
        "blobs_per_frame": allblobs / max(1, len(frames)),
        "beam_span_med": st.median(beams) if beams else None,
        "row_span_med": st.median(rows) if rows else None,
        "area_med": st.median(areas) if areas else None,
        "snr_med": st.median(snrs) if snrs else None,
        "step_med_px": step_med,
        "step_p90_px": step_p90,
        "arc_width_beams": aw,
        "band_frame_frac": wide / max(1, len(frames)),
        "beam_coverage_med": st.median(covs) if covs else None,
        "row_extent_med": st.median(exts) if exts else None,
        "top_track": tops,
    }


def score(r: dict) -> float:
    """Rank by 'looks like a compact, bright, smoothly moving return'.

    Every term is bounded 0..1 and the weights are stated so a reader can disagree
    with them explicitly rather than with a black box:

        det_rate            how consistently something is found (0.35)
        compactness         1 at <=25 beams wide, 0 at >=WIDE (0.35)
        smoothness          1 at <=2 px frame-to-frame, 0 at >=12 (0.20)
        brightness          snr/8 clipped (0.10)

    A recording whose arc is already WIDE beams wide cannot score high even if its
    detector keeps firing - which is the point: that is the structure signature.
    """
    if not r["det_rate"]:
        return 0.0
    bs = r["beam_span_med"] or WIDE
    compactness = max(0.0, min(1.0, (WIDE - bs) / (WIDE - 25)))
    step = r["step_med_px"]
    smoothness = 0.0 if step != step else max(0.0, min(1.0, (12 - step) / 10))
    bright = min(1.0, (r["snr_med"] or 0) / 8.0)
    base = 0.35 * r["det_rate"] + 0.35 * compactness + 0.20 * smoothness + 0.10 * bright
    # A recording whose frames are mostly full-width bands is structure-dominated: the
    # detector is firing on the band, however compact the piece it latches onto.
    return round(base * (1.0 - r.get("band_frame_frac", 0.0)), 4)


# --------------------------------------------------------------------------------------
# v2 - beam-coverage gate, continuous range track, three geometry gates
# --------------------------------------------------------------------------------------
#
# The three geometry gates come from a correction that has to be stated up front: a small
# fit residual is NOT evidence that the fit found anything.  ``fit_point`` clips its
# parameters, and when the data carry no information about a parameter the optimiser simply
# sits on the wall.  On 2023-09-21_105230 the residual is 7 mm -- and b is clipped at
# -0.300 m and P_z at -2.0 m, i.e. the data did not choose that point.  Hence:
#
#   1. bounds_active            any of b / P_z / P_xy at its bound  => not identifiable.
#   2. holdout_p90              fit on the even-indexed frames, score on the odd ones (and
#                               the other way round); the worse fold is reported.  A point
#                               that only exists because the fit was free to bend shows up
#                               here.
#   3. fixed-object-impossible  over the track, the platform moves by D; for a fixed object
#                               the observed range must vary by at least |D . u| (u = mean
#                               line of sight).  2023-09-21_110229 keeps r ~ 1.85 m while
#                               the head moves 0.87 m -- no fixed object in the pool can do
#                               that, so the return is not a point at all.
#
# geo_factor is tiered rather than a single multiplier, so a reader can see which gate moved
# the score:
#   1.00  identifiable, holdout ok, range varies as a fixed point requires
#   0.70  fit usable but the holdout residual is too large (unstable point)
#   0.50  parameters at their bounds (not identifiable)
#   0.35  range variation below half the fixed-object lower bound (positive evidence the
#         return follows the platform / is a standing structure, not a point)
#   0.70  track too short or no gantry to evaluate (unknown, never a pass)

V2 = dict(every=12, cov_pct=99.5, cov_smooth=5, band_gate=0.45,
          gate_m_per_frame=0.025, jump_m_per_frame=0.030,
          holdout_p90_max=0.15, min_track=8, refine_top=10,
          snr=5.5, min_area=12, open_w=0)

GEO_FACTORS = (("ok", 1.00), ("holdout", 0.70), ("bounds", 0.50),
               ("impossible", 0.35), ("unknown", 0.70))


def box_mean(img: np.ndarray, k: int) -> np.ndarray:
    """k x k box mean with edge-clipped windows, via one summed-area table."""
    k = int(k)
    if k <= 1:
        return img.astype(np.float64)
    h, w = img.shape
    a = np.zeros((h + 1, w + 1), np.float64)
    a[1:, 1:] = np.cumsum(np.cumsum(img.astype(np.float64), axis=0), axis=1)
    r = np.arange(h)
    c = np.arange(w)
    r0 = np.clip(r - k // 2, 0, h)
    r1 = np.clip(r - k // 2 + k, 0, h)
    c0 = np.clip(c - k // 2, 0, w)
    c1 = np.clip(c - k // 2 + k, 0, w)
    s = a[r1][:, c1] - a[r0][:, c1] - a[r1][:, c0] + a[r0][:, c0]
    n = np.maximum(1, np.outer(r1 - r0, c1 - c0))
    return s / n


def beam_coverage_p995(img: np.ndarray, pct: float = 99.5, smooth: int = 5) -> float:
    """Fraction of beams touched by a smoothed pixel >= the frame's ``pct`` percentile.

    Deliberately *not* ``beam_coverage`` above: unsmoothed coverage measures the far-field
    speckle level, not structure.  2023-09-21_105230 reads 0.76 unsmoothed and 0.29 after a
    5x5 box mean -- the raw number would put every noisy recording behind the band gate.
    """
    im = box_mean(img, smooth) if smooth and smooth > 1 else img.astype(np.float64)
    thr = np.percentile(im, pct)
    return float((im >= thr).any(axis=0).mean())


def chain_candidates(cands, gate_m_per_frame: float, max_gap: int = 240):
    """Greedy nearest-neighbour chains over (frame, range): the continuity requirement.

    A target echo moves smoothly in range; a band edge that the detector latches onto jumps
    between rows.  Chains are built in frame order, each candidate joins the closest open
    track whose range step is within ``gate_m_per_frame * gap``.  Returns tracks sorted by
    length (longest first).
    """
    tracks, active = [], []
    for c in sorted(cands, key=lambda c: c["frame"]):
        best, bestd, keep = None, None, []
        for t in active:
            gap = c["frame"] - t[-1]["frame"]
            if gap <= 0 or gap > max_gap:
                continue
            keep.append(t)
            d = abs(c["range_m"] - t[-1]["range_m"])
            if d <= max(0.02, gate_m_per_frame * gap) and (bestd is None or d < bestd):
                best, bestd = t, d
        active = keep
        if best is None:
            t = [c]
            tracks.append(t)
        else:
            t = best
            t.append(c)
        active.append(t)
    tracks.sort(key=lambda t: (len(t), -t[0]["frame"]), reverse=True)
    return tracks


def _bound_hit(v: float, lo: float, hi: float, tol: float = 1e-3) -> bool:
    return abs(v - lo) <= tol or abs(v - hi) <= tol


def _associate(C_all, frames_all, by_frame, P, b, tol=0.05):
    """Per-frame candidate nearest to the predicted range |P-c|+b, within ``tol``.

    The tolerance is deliberately tighter than the structure's radial thickness: it is there
    to keep the *association* honest, not to let the fit choose the widest possible set.  A
    loose tolerance manufactures spread (2023-09-21_110229: every candidate sits at
    1.851 m, but a 0.10 m tolerance pulled in enough strays to report a 0.16 m span).
    """
    pts = []
    for c, f in zip(C_all, frames_all):
        pred = float(np.linalg.norm(P - c)) + b
        best, bestd = None, tol
        for bl in by_frame.get(f, ()):
            d = abs(bl["range_m"] - pred)
            if d <= bestd:
                best, bestd = bl, d
        if best is not None:
            pts.append((c, best["range_m"], best))
    return pts


def geo_gates(seed_pts, gantry, off, p: dict, by_frame=None):
    """Fit one world point to the echo and run the three gates.

    The seed is the longest continuous chain, but the fit does not stay inside it: a chain
    that breaks (the detector jumps rows for a few frames) would leave a short arc, and on a
    short arc b and P_z are degenerate - which is exactly how a recording gets a 7 mm
    residual from a fit that chose nothing.  So the fit is re-associated over the whole
    window: every frame contributes the candidate nearest to the predicted range, twice.
    """
    by_frame = by_frame or {}
    frames_all = [c for c in sorted(by_frame)]
    if not frames_all:
        frames_all = [c["frame"] for c in seed_pts]
    C_all = [np.asarray(gantry[f], float) + off for f in frames_all if f in gantry]
    frames_all = [f for f in frames_all if f in gantry]
    if len(seed_pts) < p["min_track"] or len(C_all) < p["min_track"]:
        return {"status": "track_too_short", "n": len(seed_pts), "geo_ok": False,
                "geo_fixed_object_impossible": False, "geo_factor": 0.70,
                "reason": "track_too_short"}

    r0 = np.array([c["range_m"] for c in seed_pts], float)
    C0 = np.array([np.asarray(gantry[c["frame"]], float) + off for c in seed_pts])
    P, b, resid = locate.fit_point(C0, r0)
    P, b = np.asarray(P, float), float(b)

    picked = []
    for _ in range(2):  # track -> associate over the window -> refit
        picked = _associate(C_all, frames_all, by_frame, P, b)
        if len(picked) < p["min_track"]:
            break
        Cp = np.array([q[0] for q in picked])
        rp = np.array([q[1] for q in picked])
        P, b, resid = locate.fit_point(Cp, rp)
        P, b = np.asarray(P, float), float(b)
    if len(picked) < p["min_track"]:
        picked = [(np.asarray(gantry[c["frame"]], float) + off, c["range_m"], c)
                  for c in seed_pts if c["frame"] in gantry]
    Cp = np.array([q[0] for q in picked])
    rp = np.array([q[1] for q in picked])
    blobs = [q[2] for q in picked]
    resid = np.abs(np.asarray(resid, float))
    if len(resid) != len(rp):
        resid = np.abs(np.linalg.norm(P[None, :] - Cp, axis=1) + b - rp)

    steps = [float(np.hypot(b2["row"] - b1["row"], b2["beam"] - b1["beam"])) /
             max(1, b2["frame"] - b1["frame"])
             for b1, b2 in zip(blobs, blobs[1:]) if b2["frame"] > b1["frame"]]
    assoc = {"n": len(rp), "frac": round(len(rp) / float(len(frames_all)), 4),
             "beam_span_med": round(float(np.median([b["beam_span"] for b in blobs])), 1),
             "row_span_med": round(float(np.median([b["row_span"] for b in blobs])), 1),
             "snr_med": round(float(np.median([b["snr"] for b in blobs])), 2),
             "area_med": round(float(np.median([b["area"] for b in blobs])), 1),
             "step_med_px": round(float(np.median(steps)), 3) if steps else None}

    bounds = {"b": bool(_bound_hit(b, locate.B_LO, locate.B_HI)),
              "z": bool(_bound_hit(P[2], locate.P_Z_LO, locate.P_Z_HI)),
              "xy": bool(abs(P[0]) >= locate.P_XY_MAX - 1e-3 or
                         abs(P[1]) >= locate.P_XY_MAX - 1e-3)}
    bounds_active = any(bounds.values())

    folds, hold = [], None
    idx = np.arange(len(rp))
    for par in (0, 1):
        fit_idx, ev = idx % 2 == par, idx % 2 != par
        if fit_idx.sum() < 4 or ev.sum() < 4:
            folds, hold = [], None
            break
        Pf, bf, _ = locate.fit_point(Cp[fit_idx], rp[fit_idx])
        err = np.abs(np.linalg.norm(Pf[None, :] - Cp[ev], axis=1) + bf - rp[ev])
        folds.append(float(np.percentile(err, 90)))
    hold = max(folds) if folds else None
    holdout_ok = bool(hold is not None and hold <= p["holdout_p90_max"])

    # (3) over the whole window the platform moves by D; for a fixed point the observed
    # range must vary by at least |D . u| (u = mean line of sight).  For a platform orbiting
    # the point, D is perpendicular to u and the bound is ~0 - the test only fires when the
    # platform translates along the line of sight, which is the case it is meant to catch.
    Call = np.array(C_all)
    D = Call[-1] - Call[0]
    los = P[None, :] - Call
    los /= np.maximum(1e-9, np.linalg.norm(los, axis=1))[:, None]
    u = los.mean(axis=0)
    u /= max(1e-9, float(np.linalg.norm(u)))
    move = float(np.linalg.norm(D))
    min_req = float(abs(D @ u))
    # Robust spread: the association tolerance bounds how far the matched set may stray, so
    # a min-max span is an upper bound produced by the matching, not by the echo.
    span = float(np.percentile(rp, 95) - np.percentile(rp, 5))
    span_minmax = float(rp.max() - rp.min())
    # Gate 3 needs a credible point to exist in the first place: if the fit does not hold up
    # (bounded, but with residuals far above the pixel), "range did not vary" says nothing.
    credible = bool(holdout_ok and np.median(resid) <= p["holdout_p90_max"])
    impossible = bool(credible and min_req > 0.10 and span < 0.5 * min_req)

    geo_ok = bool((not bounds_active) and holdout_ok)
    if not credible:
        factor, reason = (0.50 if bounds_active else 0.70), "fit_not_meaningful"
    elif impossible:
        factor, reason = 0.35, "range_variation_below_fixed_object_lower_bound"
    elif bounds_active:
        factor, reason = 0.50, "parameters_at_bounds"
    elif not holdout_ok:
        factor, reason = 0.70, "holdout_p90_too_large"
    else:
        factor, reason = 1.00, "ok"
    return {"status": "ok", "n_seed": len(seed_pts), "n": len(rp), "assoc": assoc,
            "P": [round(float(v), 3) for v in P], "b": round(b, 3),
            "resid_med": round(float(np.median(resid)), 4),
            "resid_p90": round(float(np.percentile(resid, 90)), 4),
            "bounds": bounds, "bounds_active": bounds_active,
            "holdout_p90": None if hold is None else round(hold, 4),
            "holdout_folds": [round(f, 4) for f in folds],
            "holdout_ok": holdout_ok, "geo_ok": geo_ok, "fit_credible": credible,
            "window_span_m": round(float(np.linalg.norm(Call[-1] - Call[0])), 3),
            "platform_move_m": round(move, 3),
            "min_required_variation_m": round(min_req, 3),
            "range_span_m": round(span, 3), "range_span_minmax_m": round(span_minmax, 3),
            "variation_ratio": None if min_req <= 1e-6 else round(span / min_req, 3),
            "geo_fixed_object_impossible": impossible,
            "geo_factor": factor, "reason": reason}


def run_v2(rec: geometry.Recording, every: int = 12, **kw) -> dict:
    """One recording -> v2 metrics: coverage, chain, jumps, geometry gates, score parts."""
    p = dict(V2)
    p.update(kw)
    frames = list(rec.frames)[:: max(1, every)]
    try:
        gantry = locate.load_gantry(geometry._rec_dir(rec.recording))
        off = locate.chain_offset()
    except Exception as exc:  # a recording without gantry is a finding, not a crash
        gantry, off = {}, None
        print("  no gantry for %s: %s" % (rec.recording, exc), file=sys.stderr)
    ws, res = float(rec.header["WindowStart"]), rec.res_m

    cands, covs, tops, per_frame, by_frame = [], [], [], [], {}
    for f in frames:
        img = read_pgm_cached(rec.pgm_path(f))
        covs.append(beam_coverage_p995(img, p["cov_pct"], p["cov_smooth"]))
        d = compact.detect_compact(img, snr_thr=p["snr"], min_area=p["min_area"],
                                   open_w=p["open_w"])
        blobs = d.get("blobs") or []
        per_frame.append(len(blobs))
        rs = []
        for b in blobs:
            row, col = b["centroid"]
            rng = ws + float(row) * res
            cand = {"frame": int(f), "range_m": rng,
                    "row": float(row), "beam": float(col),
                    "snr": float(b["snr"]), "score": float(b["score"]),
                    "beam_span": int(b["beam_span"]), "row_span": int(b["row_span"]),
                    "area": int(b["area"])}
            cands.append(cand)
            rs.append(cand)
        by_frame[int(f)] = rs
        if blobs:
            b0 = max(blobs, key=lambda b: b["score"])
            tops.append({"frame": int(f), "range_m": ws + float(b0["centroid"][0]) * res})

    tracks = chain_candidates(cands, p["gate_m_per_frame"])
    tr = tracks[0] if tracks else []
    jumps = 0
    for a, b in zip(tops, tops[1:]):
        gap = max(1, b["frame"] - a["frame"])
        if abs(b["range_m"] - a["range_m"]) > p["jump_m_per_frame"] * gap:
            jumps += 1

    if tr:
        steps = [float(np.hypot(b["row"] - a["row"], b["beam"] - a["beam"])) /
                 max(1, b["frame"] - a["frame"]) for a, b in zip(tr, tr[1:])]
        step_med = float(np.median(steps)) if steps else float("nan")
        bs = float(np.median([c["beam_span"] for c in tr]))
        rs = float(np.median([c["row_span"] for c in tr]))
        ar = float(np.median([c["area"] for c in tr]))
        snr = float(np.median([c["snr"] for c in tr]))
    else:
        step_med, bs, rs, ar, snr = float("nan"), 0.0, 0.0, 0.0, 0.0

    geo = geo_gates(tr, gantry, off, p, by_frame) if (tr and off is not None) else \
        {"status": "no_gantry", "n": 0, "geo_ok": False,
         "geo_fixed_object_impossible": False, "geo_factor": 0.70, "reason": "no_gantry"}

    cov_med = float(np.median(covs)) if covs else 0.0
    band_frac = float(np.mean([c >= p["band_gate"] for c in covs])) if covs else 0.0
    track_frac = len(tr) / float(len(frames)) if frames else 0.0
    det_rate = float(np.mean([n > 0 for n in per_frame])) if per_frame else 0.0

    # Presence is *multiplicative*, not another term in a sum: the run that produced v2's
    # first table showed why.  101622 got 0.66 from a 20/768-frame chain because compactness,
    # smoothness and brightness describe a blob and cannot see that the blob is not there in
    # 97 % of the frames.  "There is a return" is a precondition for "the return looks good",
    # so it multiplies.  Continuity is the stability of the top-1 range across the whole
    # recording (1 - jumps per step), which is not degenerate on a chain: a chain is
    # continuous by construction, so only the global jump rate adds information.
    assoc = geo.get("assoc") or {}
    n_assoc = int(assoc.get("n") or 0)
    presence = (len(tr) / float(len(frames))) if (tr and frames) else 0.0
    n_steps = max(1, len(tops) - 1)
    continuity = max(0.0, 1.0 - jumps / float(n_steps)) if tops else 0.0
    shape_bs = assoc.get("beam_span_med") if n_assoc else bs
    shape_step = assoc.get("step_med_px") if n_assoc else step_med
    shape_snr = assoc.get("snr_med") if n_assoc else snr
    have_shape = bool(tr) or bool(n_assoc)
    compactness = (float(np.clip((WIDE - float(shape_bs)) / float(WIDE - 25), 0.0, 1.0))
                   if (have_shape and shape_bs is not None) else 0.0)
    smoothness = (float(np.clip((12.0 - float(shape_step)) / 10.0, 0.0, 1.0))
                  if (have_shape and shape_step is not None) else 0.0)
    brightness = (float(np.clip((float(shape_snr) - 3.0) / 5.0, 0.0, 1.0))
                  if (have_shape and shape_snr is not None) else 0.0)
    shape_quality = (0.35 * continuity + 0.35 * compactness +
                     0.15 * smoothness + 0.15 * brightness)
    base = presence * shape_quality
    band_factor = 1.0 - band_frac
    score = base * band_factor * geo["geo_factor"]

    return {"recording": rec.recording, "category": rec.category, "sampled_every": every,
            "n_frames_sampled": len(frames), "n_candidates": len(cands),
            "track_len": len(tr), "track_frac": round(track_frac, 4),
            "track_frames": [c["frame"] for c in tr][:200], "fit_n": geo.get("n"),
            "jumps": jumps, "blob_det_rate": round(det_rate, 4),
            "blobs_per_frame": round(float(np.mean(per_frame)), 3) if per_frame else 0.0,
            "step_med_px": None if step_med != step_med else round(step_med, 3),
            "beam_span_med": round(bs, 1), "row_span_med": round(rs, 1),
            "area_med": round(ar, 1), "snr_med": round(snr, 2),
            "cov_med": round(cov_med, 4),
            "cov_p10": round(float(np.percentile(covs, 10)), 4) if covs else 0.0,
            "cov_p90": round(float(np.percentile(covs, 90)), 4) if covs else 0.0,
            "band_gate_frac": round(band_frac, 4),
            "presence": round(presence, 4), "continuity": round(continuity, 4),
            "base": round(base, 4), "band_factor": round(band_factor, 4),
            "geo": geo, "geo_factor": geo["geo_factor"],
            "score": round(score, 4)}


def render_v2_md(rows_a, rows_b, params, v1_rank, stats) -> str:
    """Two tables: recordings that clear every gate, then everything else.

    Ranking key is ``base`` - does the return exist, and does it look like a compact object.
    The gates are printed as warnings and as an eligibility test, never multiplied in: the
    previous version multiplied them into the score and the whole table collapsed into
    0.000-0.058, so the order was decided by which gate fired rather than by the echo.
    """
    lines = ["# 40 条录音的形状普查 v2（排序主键 base；闸门只做资格与告警）", "",
             "> 只回答**先看哪一条**。声呐侧没有 GT，`identity` 仍是 `unresolved`；"
             "base 高不等于\"有目标\"。", "",
             "生成：`python tools/census.py --every %d`（40 条全部逐帧，`sampling: 1`）"
             % params["every"], "",
             "排序主键是 `base`；`score（旧乘法）` 只作对照，不参与名次。闸门只决定 A/B 资格"
             "与最右列的告警。",
             "`split_role` 指该录音在 manifest 里有没有任何 `paired_role`：无的可以看，"
             "但**不能导出成数据集**。", ""]

    def table(rows, title, note):
        out = ["## " + title, ""]
        if note:
            out += [note, ""]
        if not rows:
            return out + ["（空）", ""]
        out += ["| # | recording | 类 | split_role | base | score（旧乘法） | presence | "
                "track_frac | 覆盖闸 | geo | v1 | 触发 |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            g = r["geo"]
            v1 = v1_rank.get(r["recording"])
            out.append("| %s%d | `%s` | %s | %s | %.3f | %.4f | %.3f | %.3f | %.2f | %s | %s | %s |"
                       % (r["group"], r["rank"], r["recording"], r["category"],
                          r.get("split_role", "-"), r["base"],
                          r.get("score_old", r["score"]), r["presence"], r["track_frac"],
                          r["band_gate_frac"],
                          "%.2f %s" % (g["geo_factor"], g["reason"]),
                          v1 if v1 is not None else "-",
                          r.get("change_reason") or "无"))
        return out + [""]

    lines += table(rows_a, "A. 推荐先看",
                   "条件：`geo_ok` 且 `band_gate_frac < 0.45` 且 `track_frac >= 0.5`，按 base 降序。")
    if not rows_a:
        lines += ["> **A 段为空，这不是漏排。** 40 条里没有一条同时满足三条：最高的 "
                  "`track_frac` = %.3f（`%s`），而它触发了几何闸；`geo_ok` 只有 %d 条。"
                  "换句话说，没有一条录音给出覆盖半条录音的连续回波——这是本报告的主要结论之一。"
                  % (stats["max_track_frac"], stats["max_track_frac_rec"], stats["n_geo_ok"]), "",
                  "如果一定要挑一条先看，B 段第 1 名 `%s` 的 base 最高；先读它最右列的触发项，"
                  "再决定值不值得花时间。" % (rows_b[0]["recording"] if rows_b else "-"), ""]
    lines += table(rows_b, "B. 其余（按 base 降序）",
                   "不满足 A 的资格条件；最右列是触发的闸。反例必须留在表里。")
    lines += ["## 口径（写死在这里，便于反驳）", "",
              "`base = presence * (0.35*continuity + 0.35*compactness + 0.15*smoothness + 0.15*brightness)`",
              "",
              "- `presence = track_len / n_frames_sampled`：最长连续链覆盖的采样帧比例"
              "（全部 40 条都按 `--every 1` 算，`sampling` 列恒为 1）。\"有回波\"是\"回波形状好\""
              "的前提，所以它乘进去而不是加成——加成项曾把一个 20/768 帧的碎片抬到榜首。",
              "- `continuity = 1 - jumps/(top1 步数)`：整条录音 top-1 距离的稳定度；链本身连续，"
              "所以只有全局跳变率带信息。",
              "- `compactness = clip((70 - beam_span)/(70-25))`，span 取关联 blob 中位。",
              "- `smoothness = clip((12 - step_px_per_frame)/10)`，已按采样间隔归一。",
              "- `brightness = clip((snr_med - 3)/5)`。",
              "- `覆盖闸` = 覆盖率 >= %.2f 的帧占比；覆盖率 = 5x5 平滑后 >= p%.1f 的像素触到的 "
              "beam 比例。它只做资格判定与告警，不乘进 base。"
              % (params["band_gate"], params["cov_pct"]),
              "- `geo` = 三项几何闸的分档：1.00 可辨识且留出通过；0.70 留出残差过大或样本不足；"
              "0.50 参数撞界；0.35 距离变化低于固定物体下界（回波跟着平台走，更像结构）。"
              "只做资格判定与告警，不乘进 base。",
              "- `score（旧乘法）= base * (1 - 覆盖闸) * geo_factor`：上一版的排名口径，"
              "保留它只为让新旧读数可对照。",
              "",
              "## 反例（必须留在表里）", ""]
    return "\n".join(lines) + "\n"


def montage(rec: geometry.Recording, out_png: Path, n: int = 6, **kw) -> dict:
    """Six evenly spaced frames, each shown with its top-1 blob box drawn."""
    from PIL import Image, ImageDraw

    frames = list(rec.frames)
    pick = [frames[int(i * (len(frames) - 1) / (n - 1))] for i in range(n)]
    tiles = []
    for f in pick:
        img = read_pgm_cached(rec.pgm_path(f))
        res = compact.detect_compact(img, **kw)
        lo, hi = np.percentile(img, 0.5), np.percentile(img, 99.5)
        g = np.clip((img - lo) / max(1e-6, hi - lo), 0, 1)
        rgb = np.repeat((g * 255).astype(np.uint8)[:, :, None], 3, axis=2)
        tile = Image.fromarray(rgb).resize((rgb.shape[1] * 2, rgb.shape[0] * 2), Image.NEAREST)
        d = ImageDraw.Draw(tile)
        for b in res.get("blobs") or []:
            x0, y0, x1, y1 = b["box_xyxy"]
            d.rectangle([x0 * 2, y0 * 2, x1 * 2, y1 * 2], outline=(0, 255, 255))
        d.text((6, 6), "f%d  n=%d" % (f, len(res.get("blobs") or [])), fill=(255, 180, 0))
        tiles.append(tile)
    w = sum(t.width for t in tiles) + 4 * (len(tiles) - 1)
    h = max(t.height for t in tiles)
    sheet = Image.new("RGB", (w, h), (10, 10, 10))
    x = 0
    for t in tiles:
        sheet.paste(t, (x, 0)); x += t.width + 4
    sheet.save(out_png)
    return {"png": str(out_png), "frames": pick}


def main_v1(argv=None) -> int:
    """v1 (kept for reproduction): "banded frame" = contiguous run >= 60 beams on the blob's row.

    This is the test that could not see a 3-6 row thin band, which is why 2023-09-21_100927
    ranked 6th in v1.  Kept verbatim so the old ranking stays re-derivable.
    """
    ap = argparse.ArgumentParser(description="Survey recordings with engine.compact and rank them")
    ap.add_argument("--every", type=int, default=8)
    ap.add_argument("--out", default="out/census")
    ap.add_argument("--only", default=None, help="comma-separated recording ids")
    ap.add_argument("--montage", type=int, default=6, help="montage the top N")
    ap.add_argument("--snr", type=float, default=5.5)
    ap.add_argument("--min-area", type=int, default=12)
    a = ap.parse_args(argv)

    kw = dict(snr_thr=a.snr, min_area=a.min_area, open_w=0)
    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)

    flags = approved_recordings()
    if a.only:
        recs = [geometry.load_recording(r.strip()) for r in a.only.split(",")]
    else:
        recs = []
        for rec_id in sorted(flags):
            try:
                recs.append(geometry.load_recording(rec_id))
            except Exception as exc:  # a recording that cannot even be opened is a finding
                print("skip %s: %s" % (rec_id, exc), file=sys.stderr)

    rows = []
    for i, rec in enumerate(recs, 1):
        try:
            r = survey(rec, a.every, **kw)
        except Exception as exc:
            print("skip %s: %s" % (rec.recording, exc), file=sys.stderr)
            continue
        r["score"] = score(r)
        r["has_role"] = flags[r["recording"]]["has_role"]
        r["n_items_with_role"] = flags[r["recording"]]["n_with_role"]
        r["roles"] = flags[r["recording"]]["roles"]
        rows.append(r)
        print("[%2d/%d] %-22s %-18s det=%.2f bs=%-5s step=%-5s arc=%-3d score=%.3f"
              % (i, len(recs), r["recording"], r["category"], r["det_rate"],
                 r["beam_span_med"], None if r["step_med_px"] != r["step_med_px"] else round(r["step_med_px"], 1),
                 r["arc_width_beams"], r["score"]), flush=True)

    rows.sort(key=lambda r: -r["score"])
    for k, r in enumerate(rows, 1):
        r["rank"] = k
        r["top_track"] = r["top_track"][:200]

    (out / "census.json").write_text(json.dumps({
        "schema": "sonar-llm-annotation/census/v1",
        "manifest": str(MANIFEST.relative_to(ROOT.parent)),
        "params": {"every": a.every, "snr": a.snr, "min_area": a.min_area, "open_w": 0},
        "score_definition": ("(0.35*det_rate + 0.35*compactness + 0.20*smoothness + 0.10*brightness) * (1 - band_frame_frac); "
                             "compactness = (70-beam_span)/(70-25) clipped, minus the WIDE=70 beams "
                             "structure width; identity unresolved - this is a reading order, not a label"),
        "n_recordings": len(rows),
        "recordings": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 40 条录音的形状普查（按\"像不像一个紧凑回波\"排序）", "",
             "> 排序只回答**先看哪一条**，不回答\"是不是目标\"。声呐侧没有 GT，`identity` 仍是 `unresolved`。",
             "> 生成：`python tools/census.py --every %d`（每 %d 帧采样一次）" % (a.every, a.every), "",
             "| # | recording | 类 | 检出率 | 横向 span | 相邻帧位移 | 行向连续长度 | 分数 |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        step = "-" if r["step_med_px"] != r["step_med_px"] else "%.1f px" % r["step_med_px"]
        lines.append("| %d | `%s` | %s | %.2f | %s | %s | %s | %.3f |"
                     % (r["rank"], r["recording"], r["category"], r["det_rate"],
                        r["beam_span_med"], step, "%s" % r["row_extent_med"], r["score"]))
    lines += ["", "阈值：横向 span < 25 beams 记满分，>= %d beams（结构宽）记 0 分；" % WIDE,
              "行向连续长度 = 候选所在那一行上、含该像元的连续亮段长度（阈值取该行 p90）。",
              "它 >= 60 beams 的帧记为「带状帧」，带状帧占比直接乘进分数——检测器咬住的如果是",
              "贯穿扇面的细线，这条就会很长，分数因此被压低。"]
    (out / "CENSUS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    if a.montage:
        (out / "top").mkdir(exist_ok=True)
        for r in rows[: a.montage]:
            try:
                rec = geometry.load_recording(r["recording"])
                montage(rec, out / "top" / ("%02d_%s.png" % (r["rank"], r["recording"])), **kw)
            except Exception as exc:
                print("montage %s: %s" % (r["recording"], exc), file=sys.stderr)

    print("\n-> %s" % (out / "census.json"))
    print("-> %s" % (out / "CENSUS.md"))
    return 0


def _v1_ranks() -> dict:
    p = ROOT / "out" / "census" / "census.json"
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {r["recording"]: r.get("rank") for r in d.get("recordings", []) if "rank" in r}


def _why(r) -> str:
    """One line naming the gate(s) that moved this recording, so the delta is auditable."""
    bits = []
    if r["band_gate_frac"] >= 0.5:
        bits.append("覆盖闸：%.0f%% 帧覆盖 >= %.2f" % (100 * r["band_gate_frac"], V2["band_gate"]))
    g = r["geo"]
    if not g["geo_ok"]:
        bits.append("几何闸：%s" % g["reason"])
    if g.get("geo_fixed_object_impossible"):
        bits.append("距离变化不足下界的 50%")
    return "；".join(bits) if bits else "未触发任何闸（base 排序）"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Census v2: whole-frame coverage gate + track continuity + three geometry gates")
    ap.add_argument("--every", type=int, default=12)
    ap.add_argument("--refine-top", type=int, default=10,
                    help="re-survey the top N at --every 1 (default 10; 0 disables)")
    ap.add_argument("--out", default="out/census")
    ap.add_argument("--only", default=None, help="comma-separated recording ids")
    ap.add_argument("--montage", type=int, default=2, help="montage the top N into top2/")
    ap.add_argument("--snr", type=float, default=5.5)
    ap.add_argument("--min-area", type=int, default=12)
    ap.add_argument("--legacy", action="store_true", help="run v1 (census.json / CENSUS.md)")
    a = ap.parse_args(argv)
    if a.legacy:
        return main_v1(["--every", str(a.every), "--out", a.out, "--snr", str(a.snr),
                        "--min-area", str(a.min_area), "--montage", str(a.montage)]
                       + (["--only", a.only] if a.only else []))

    kw = dict(snr=a.snr, min_area=a.min_area, open_w=0)
    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)

    flags = approved_recordings()
    ids = ([r.strip() for r in a.only.split(",") if r.strip()] if a.only else sorted(flags))
    rows = []
    for i, rec_id in enumerate(ids, 1):
        try:
            rec = geometry.load_recording(rec_id)
            r = run_v2(rec, a.every, **kw)
        except Exception as exc:  # a recording that cannot be opened is a finding
            print("skip %s: %s" % (rec_id, exc), file=sys.stderr)
            continue
        f = flags.get(rec_id, {})
        r["has_role"] = f.get("has_role", True)
        r["n_items_with_role"] = f.get("n_with_role", 0)
        r["roles"] = f.get("roles", [])
        rows.append(r)
        g = r["geo"]
        print("[%2d/%d] %-22s cov=%.2f band=%.2f trk=%-3d/%d jumps=%-2d geo=%.2f(%s) score=%.3f"
              % (i, len(ids), rec_id, r["cov_med"], r["band_gate_frac"], r["track_len"],
                 r["n_frames_sampled"], r["jumps"], g["geo_factor"], g["reason"], r["score"]),
              flush=True)
    if not rows:
        print("no recordings surveyed", file=sys.stderr)
        return 2

    rows.sort(key=lambda r: -r["score"])

    # The refinement exists because track length and the geometry gates are sampling-sensitive:
    # at --every 12 a 0.3 m/frame gate spans 0.3 m per step, so only slow echoes chain at all.
    if a.refine_top and a.every > 1 and not a.only:
        refined = []
        for r in rows[: a.refine_top]:
            try:
                r2 = run_v2(geometry.load_recording(r["recording"]), 1, **kw)
            except Exception as exc:
                print("refine %s: %s" % (r["recording"], exc), file=sys.stderr)
                refined.append(r)
                continue
            for k in ("has_role", "n_items_with_role", "roles"):
                r2[k] = r.get(k)
            r2["refined_from_every"] = a.every
            refined.append(r2)
            print("  refine %-22s trk=%-3d/%d geo=%.2f(%s) score=%.3f"
                  % (r2["recording"], r2["track_len"], r2["n_frames_sampled"],
                     r2["geo"]["geo_factor"], r2["geo"]["reason"], r2["score"]), flush=True)
        rows = refined + rows[a.refine_top:]

    # Ranking key is base.  The gates are disqualifiers and warnings, not multipliers: when
    # they were multiplied in, the table collapsed into 0.000-0.058 and the order was set by
    # which gate fired rather than by the echo.  score_old is kept for comparison only.
    v1 = _v1_ranks()
    for r in rows:
        r["score_old"] = r["score"]
        r["sampling"] = a.every
        r["split_role"] = "有" if r.get("has_role") else "无"
        r["eligible"] = bool(r["geo"].get("geo_ok") and r["band_gate_frac"] < 0.45
                             and r["track_frac"] >= 0.5)
        r["v1_rank"] = v1.get(r["recording"])
        r["change_reason"] = _why(r)
    rows.sort(key=lambda r: -r["base"])
    a_rows = [r for r in rows if r["eligible"]]
    b_rows = [r for r in rows if not r["eligible"]]
    for k, r in enumerate(a_rows, 1):
        r["rank"], r["group"] = k, "A"
    for k, r in enumerate(b_rows, 1):
        r["rank"], r["group"] = k, "B"
    rows = a_rows + b_rows
    for pos, r in enumerate(rows, 1):
        r["pos"] = pos
        r["delta_vs_v1"] = None if r["v1_rank"] is None else r["v1_rank"] - pos
    best = max(rows, key=lambda r: r["track_frac"]) if rows else None
    stats = {"max_track_frac": best["track_frac"] if best else 0.0,
             "max_track_frac_rec": best["recording"] if best else "-",
             "n_geo_ok": sum(1 for r in rows if r["geo"].get("geo_ok")),
             "n_eligible": len(a_rows)}

    params = {"rank_key": "base", "every": a.every, "refine_top": a.refine_top, "snr": a.snr,
              "min_area": a.min_area, "open_w": 0, "cov_pct": V2["cov_pct"],
              "cov_smooth": V2["cov_smooth"], "band_gate": V2["band_gate"],
              "gate_m_per_frame": V2["gate_m_per_frame"],
              "jump_m_per_frame": V2["jump_m_per_frame"],
              "holdout_p90_max": V2["holdout_p90_max"], "min_track": V2["min_track"]}
    (out / "census_v2.json").write_text(json.dumps({
        "schema": "sonar-llm-annotation/census/v2",
        "manifest": str(MANIFEST.relative_to(ROOT.parent)),
        "params": params,
        "score_definition": {
            "base": "presence * (0.35*continuity + 0.35*compactness + 0.15*smoothness "
                    "+ 0.15*brightness)",
            "score": "base * (1 - band_gate_frac) * geo_factor",
            "presence": "track_len / n_frames_sampled: fraction of sampled frames covered by "
                        "the longest continuous chain. Multiplicative precondition, not a term "
                        "in a sum: a 20/768-frame blip cannot be rescued by shape quality.",
            "continuity": "1 - jumps / (n_top1_steps): stability of the top-1 range across the "
                          "whole recording",
            "compactness": "clip((70 - assoc beam_span median) / (70 - 25))",
            "smoothness": "clip((12 - assoc step_px_per_frame) / 10)",
            "brightness": "clip((assoc snr median - 3) / 5)",
            "band_gate_frac": "fraction of sampled frames whose 5x5-smoothed p99.5 beam "
                              "coverage >= band_gate",
            "geo_factor_tiers": {"1.00": "not bounds_active and holdout_p90 <= 0.15 and "
                                        "range varies as a fixed point requires",
                                 "0.70": "holdout_p90 too large, or track too short / no gantry",
                                 "0.50": "b, P_z or P_xy at their bounds",
                                 "0.35": "range_span < 0.5 * |D . u| (follows the platform)"},
            "identity": "unresolved - a reading order, not a label",
        },
        "n_recordings": len(rows),
        "recordings": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = render_v2_md(a_rows, b_rows, params, v1, stats).rstrip("\n").split("\n")
    by_id = {r["recording"]: r for r in rows}
    notes = {
        "2023-09-21_100927":
            "  - 覆盖闸只压掉 %.0f%% 的帧，**不足以把它排除**——它的回波是贯穿扇面的细带，"
            "视觉上不是物体；这条留在表里就是要说明\"闸门不是判决\"。"
            % (100 * by_id.get("2023-09-21_100927", {}).get("band_gate_frac", 0.0)),
        "2023-09-21_110229":
            "  - **与人工判读的冲突要保留**：t-cards 判读员把它判成 object，而几何闸说"
            "距离不随平台位移变化（平台移动 0.87 m、range 只动了很小的量），固定池内物体"
            "给不出这种信号。两种读数并列写在这里，不强行统一。\n"
            "  - 数据侧确认有两个近恒定的距离簇：1.85 m 贯穿全程，1.03–1.17 m 出现在中段"
            "（约 f300–f550，每帧 3–5 个候选）；t-cards 另报 12 帧里有 5 帧\"候选行与行带不在一处\"。"
            "距离不随平台位移变化，正是\"回波跟着平台/是环形结构\"的样子。",
        "2023-09-21_105230":
            "  - 上一轮被当作\"2 cm 残差证明固定点\"的例子；打开边界后 b 与 P_z 都撞界，"
            "留出 p90 只有几厘米——是小残差但不可辨识，不能当作解出来的位置。",
        "2023-09-20_171105":
            "  - 亮带横跨 92–128 beams，覆盖闸 %.0f%%；轨迹链被带的边缘反复打断（jumps 很多），"
            "几何拟合残差远大于像元，任何\"点\"的说法都不成立。"
            % (100 * by_id.get("2023-09-20_171105", {}).get("band_gate_frac", 0.0)),
    }
    for rec_id in ("2023-09-21_100927", "2023-09-21_105230", "2023-09-21_110229",
                   "2023-09-20_171105"):
        r = by_id.get(rec_id)
        if not r:
            continue
        g = r["geo"]
        lines.append("- `%s`（%s 段第 %d 名；base %.3f，旧乘法分 %.4f）：cov 中位 %.2f，覆盖闸 %.2f；"
                     "轨迹 %d/%d，geo %s"
                     % (rec_id, r["group"], r["rank"], r["base"], r["score_old"],
                        r["cov_med"], r["band_gate_frac"],
                        r["track_len"], r["n_frames_sampled"], g["reason"]))
        if g.get("status") == "ok":
            lines.append("  - b=%s（撞界 %s），留出 p90=%s，平台位移 %.2f m，"
                         "理论最小距离变化 %.2f m，实测 range 跨度 p5–p95 %.3f m（min–max %.3f，比值 %s）"
                         % (g["b"], g["bounds"]["b"], g["holdout_p90"], g["platform_move_m"],
                            g["min_required_variation_m"], g["range_span_m"],
                            g["range_span_minmax_m"], g["variation_ratio"]))
        if rec_id in notes:
            lines.append(notes[rec_id])
    no_role = [r for r in rows if not r.get("has_role")]
    if no_role:
        lines += ["", "## 不能导出成数据集的录音（split_role=无）", "",
                  "manifest 里没有任何 `paired_role` 的录音可以**看**，但不能进 train/val 划分。"
                  "挑之前先看表里 `split_role` 列："]
        for r in no_role:
            lines.append("  - `%s`：B 段第 %d 名，base %.3f（%s）"
                         % (r["recording"], r["rank"], r["base"],
                            r["change_reason"] or "无"))
    lines += ["", "## 采样与可比性", ""]
    if not a.refine_top or a.every <= 1:
        lines += ["全部 %d 条都按 `--every 1` 逐帧计算，名次之间可比。" % len(rows),
                  "更早的一版是 `--every 12` 只 refine 前 10 名，那版有个可比性缺陷：`presence` "
                  "的分母是采样帧数，every=12 下同一段回波被算成约 12 倍的出现率，refine 过的"
                  "录音反而被压低。这一版不再混用两种采样。"]
    else:
        lines += ["前 %d 名用 `--every 1` 复算（`refined_from_every=%d`），其余用 `--every %d`。"
                  % (a.refine_top, a.every, a.every),
                  "`presence` 的分母是采样帧数，两种采样下的数值不可直接比较——区块内部可比，"
                  "区块边界只是近似。"]
    lines += ["`step_px` 已按采样间隔归一；`cov_*` 逐帧计算，与采样无关。",
              "", "## 不回答的问题", "",
              "这里没有 GT：分数只表示\"这条录音里的回波更像一个紧凑、连续、几何上说得通的"
              "回波\"，不表示\"这是 UXO\"。三条已被看清的录音（100927 细带、105230/110229 "
              "近恒定距离）仍留在表里当反例。"]
    (out / "CENSUS-V2.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    if a.montage:
        (out / "top2").mkdir(exist_ok=True)
        for r in rows[: a.montage]:
            try:
                rec = geometry.load_recording(r["recording"])
                montage(rec, out / "top2" / ("%s%02d_%s.png"
                                             % (r["group"], r["rank"], r["recording"])), **kw)
            except Exception as exc:
                print("montage %s: %s" % (r["recording"], exc), file=sys.stderr)

    print("\n-> %s" % (out / "census_v2.json"))
    print("-> %s" % (out / "CENSUS-V2.md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
