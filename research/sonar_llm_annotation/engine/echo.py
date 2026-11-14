"""Echo extraction: motion-compensated background, class-invariant structures, candidates.

Three layers, deliberately kept apart
-------------------------------------
``background_model()``  temporal median + per-beam gain compensation (vertical stripes),
                        plus a **motion-compensated** aligned background: each reference
                        frame is shifted back to the anchor pose before the median, so the
                        slowly moving bright band is cancelled too (BRIEF §2.2: the band is
                        class-invariant structure, present in 100 % of frames, and it is NOT
                        the target).
``structures()``        the large, class-invariant echo structure.  Role ``structure``,
                        ``class_invariant: True``, ``excluded_from_candidates: True``.
``perturbations()``     small, bright, sharp residual blobs after the structure domain is
                        removed.  Role ``candidate`` - only these may become proposal boxes.

Nothing here assumes a FOV, a range, or a sonar pose: geometry is degraded (BRIEF §2.2) and
``geometry.FrameGeom.predict()`` is unavailable by design.  ``detect()`` ignores
``predicted`` except to keep the T-GEOM signature.

Pure numpy (+PIL/yaml only via geometry). No cv2/scipy/skimage. Deterministic: same frame,
same parameters -> byte-identical output (no randomness, no dict-order dependence).
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

try:  # keep importable both as ``engine.echo`` and as a plain script
    from . import geometry as G
except ImportError:  # pragma: no cover
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import geometry as G

REPO = Path(__file__).resolve().parents[1]

# ----------------------------------------------------------------------------------
# io
# ----------------------------------------------------------------------------------


def read_pgm(path) -> np.ndarray:
    """P5 PGM -> float32 (H=rows=samples, W=beams). Tolerant of comments."""
    data = Path(path).read_bytes()
    if data[:2] != b"P5":
        raise ValueError(f"{path}: not a binary PGM")
    toks, i = [], 2
    while len(toks) < 3:
        while i < len(data) and data[i:i + 1].isspace():
            i += 1
        if data[i:i + 1] == b"#":
            while i < len(data) and data[i:i + 1] not in (b"\n", b"\r"):
                i += 1
            continue
        j = i
        while not data[j:j + 1].isspace():
            j += 1
        toks.append(int(data[i:j]))
        i = j
    w, h, _ = toks
    i += 1
    buf = np.frombuffer(data[i:i + w * h], dtype=np.uint8)
    if buf.size != w * h:
        raise ValueError(f"{path}: truncated ({buf.size} != {w * h})")
    return buf.reshape(h, w).astype(np.float32)


# ----------------------------------------------------------------------------------
# filters (numpy only)
# ----------------------------------------------------------------------------------


def _sum_windows(a: np.ndarray, k: int, axis: int) -> np.ndarray:
    """s[i] = sum(a[i:i+k]) along ``axis``; length n-k+1 (zero padded tail)."""
    m = a.shape[axis]
    pads = [(0, k - 1) if ax == axis else (0, 0) for ax in range(a.ndim)]
    c = np.cumsum(np.pad(a.astype(np.float64), pads), axis=axis)
    n = m - k + 1
    hi = [slice(None)] * a.ndim
    lo = [slice(None)] * a.ndim
    hi[axis] = slice(k, k + n)
    lo[axis] = slice(0, n)
    return c[tuple(hi)] - c[tuple(lo)]


def box_mean(img: np.ndarray, k: int, axis: int) -> np.ndarray:
    """k-wide moving average along ``axis`` (k odd, edge padding)."""
    if k <= 1:
        return np.asarray(img, dtype=np.float32).copy()
    assert k % 2 == 1, "box_mean expects an odd window"
    pad = k // 2
    pads = [(pad, pad) if ax == axis else (0, 0) for ax in range(np.ndim(img))]
    p = np.pad(np.asarray(img, dtype=np.float32), pads, mode="edge")
    return (_sum_windows(p, k, axis) / k).astype(np.float32)


def sliding_median(img: np.ndarray, k: int, axis: int) -> np.ndarray:
    """exact k-wide moving median along ``axis`` (edge padding)."""
    img = np.asarray(img, dtype=np.float32)
    pad = k // 2
    pads = [(pad, pad) if ax == axis else (0, 0) for ax in range(img.ndim)]
    p = np.pad(img, pads, mode="edge")
    win = np.lib.stride_tricks.sliding_window_view(p, k, axis=axis)
    return np.median(win, axis=-1).astype(np.float32)


def local_background(img: np.ndarray, k: int = 31) -> np.ndarray:
    """Robust rolling median along the range axis, independently per beam."""
    return sliding_median(img, int(k), axis=0)


# ----------------------------------------------------------------------------------
# morphology (rectangular structuring elements, pure numpy)
# ----------------------------------------------------------------------------------


def _open_axis(mask: np.ndarray, w: int, axis: int) -> np.ndarray:
    """binary opening with a length-w line along ``axis`` (edge padding)."""
    if w <= 1:
        return mask.copy()
    pad = w // 2
    m = mask.astype(np.float32)
    pads = [(pad, pad) if ax == axis else (0, 0) for ax in range(m.ndim)]
    e = _sum_windows(np.pad(m, pads, mode="edge"), w, axis) > (w - 0.5)
    d = _sum_windows(np.pad(e.astype(np.float32), pads, mode="edge"), w, axis) > 0.5
    return d


def open_h(mask: np.ndarray, w: int = 5) -> np.ndarray:
    """Horizontal opening: removes structures narrower than ``w`` beams (stripes)."""
    return _open_axis(np.asarray(mask, dtype=bool), int(w), axis=1)


def open_square(mask: np.ndarray, w: int = 3) -> np.ndarray:
    """Square opening: removes specks thinner than ``w`` px in either direction."""
    return _open_axis(_open_axis(np.asarray(mask, dtype=bool), int(w), axis=1), int(w), axis=0)


def dilate(mask: np.ndarray, r: int = 1) -> np.ndarray:
    """Square dilation by r (used to merge fragments of one structure)."""
    m = np.asarray(mask, dtype=bool)
    if r <= 0:
        return m.copy()
    w = 2 * r + 1
    p = np.pad(m.astype(np.float32), [(r, r), (r, r)])
    return _box_or(p, w, m.shape)


def _box_or(p: np.ndarray, w: int, shape: Tuple[int, int]) -> np.ndarray:
    """True where any w x w window of p is set (p already padded by r=(w-1)/2)."""
    s = _sum_windows(p, w, axis=1)
    s = _sum_windows(s, w, axis=0)
    return s[:, : shape[1]] > 0.5


# ----------------------------------------------------------------------------------
# connected components (union-find over row runs, deterministic)
# ----------------------------------------------------------------------------------


def label_numpy(mask: np.ndarray, connectivity: int = 8):
    """8- (or 4-) connected labelling. Returns (int32 labels, n).

    Labels are numbered by the raster order of each component's first pixel, so the
    result does not depend on hash order anywhere.
    """
    mask = np.asarray(mask, dtype=bool)
    H, W = mask.shape
    parent = [-1]

    def find(a: int) -> int:
        r = a
        while parent[r] != r:
            r = parent[r]
        while parent[a] != r:
            nxt = parent[a]
            parent[a] = r
            a = nxt
        return r

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            if ra < rb:
                parent[rb] = ra
            else:
                parent[ra] = rb

    runs_per_row: List[List[Tuple[int, int, int]]] = []
    for y in range(H):
        row = mask[y]
        d = np.diff(np.concatenate(([0], row.astype(np.int8), [0])))
        starts = np.flatnonzero(d == 1).tolist()
        ends = (np.flatnonzero(d == -1) - 1).tolist()
        cur = []
        for s, e in zip(starts, ends):
            lab = len(parent)
            parent.append(lab)
            cur.append((s, e, lab))
        for ps, pe, plab in (runs_per_row[-1] if runs_per_row else []):
            for s, e, lab in cur:
                if (ps <= e + 1 and s <= pe + 1) if connectivity == 8 else (ps <= e and s <= pe):
                    union(plab, lab)
        runs_per_row.append(cur)

    roots: Dict[int, int] = {}
    for cur in runs_per_row:
        for _s, _e, lab in cur:
            r = find(lab)
            if r not in roots:
                roots[r] = len(roots) + 1
    labels = np.zeros((H, W), dtype=np.int32)
    for y, cur in enumerate(runs_per_row):
        for s, e, lab in cur:
            labels[y, s:e + 1] = roots[find(lab)]
    return labels, len(roots)


# ----------------------------------------------------------------------------------
# motion estimation
# ----------------------------------------------------------------------------------


GLOBAL_ROW_CAP, GLOBAL_BEAM_CAP = 160, 24


def masked_mean_profile(img: np.ndarray, band: np.ndarray, axis: int) -> np.ndarray:
    """Mean of the band members along one axis, mean-removed.

    The *median* must not be used here: the band covers ~11 % of the frame, so a median
    along an axis is 0 almost everywhere (measured: 0/128 non-zero on the beam axis),
    the profile collapses to a constant, the correlation denominator is 0, and
    ``best_lag`` returns the first lag of the search window - i.e. ``drow=-max_row`` with
    ``score=-1.0`` on every frame.  That bug was reported by lead (m00328) and this is the
    fix; the same helper exists in ``engine/track.py`` (which imports this module, so the
    canonical copy has to live here).
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
    """Lag such that ``a[lag + k] ~ b[k]`` (i.e. r_a = r_b + lag), max normalised corr."""
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


def structure_band(ref: np.ndarray, pct: float = 97.0) -> np.ndarray:
    """Compact mask of the persistent bright band (the class-invariant structure).

    A plain percentile cut is NOT compact here: the far-field speckle crosses p90 on
    almost every row (measured: band pixels on 737/780 rows, ~13 per row), so the mask is
    salt-and-pepper and a 5x5 dilation turns it into 58 % of the frame - the structure mask
    then suppresses every candidate and the detector silently returns nothing.  So: smooth,
    cut high (p97 of the smoothed copy, where the band core sits at p99 ~ 44 vs a 13
    background), then keep only band-sized components.
    """
    ref = np.asarray(ref, dtype=np.float32)
    sm = box_mean(box_mean(ref, 5, 0), 5, 1)
    m = sm >= np.percentile(sm, pct)
    labels, n = label_numpy(m)
    keep = np.zeros(m.shape, dtype=bool)
    for lab in range(1, n + 1):
        ys, xs = np.nonzero(labels == lab)
        if ys.size < 150:
            continue
        if (xs.max() - xs.min() + 1) < 24 and (ys.max() - ys.min() + 1) < 40:
            continue
        keep[ys, xs] = True
    if keep.sum() < 200:
        keep = sm >= np.percentile(sm, 90)
    return keep


MIN_BAND_FRAC = 0.25


def _dilate_rows(mask: np.ndarray, r: int) -> np.ndarray:
    """Pad a mask along rows only (keeps the beam extent of the band)."""
    m = np.asarray(mask, dtype=bool)
    r = int(r)
    if r <= 0:
        return m.copy()
    w = 2 * r + 1
    p = np.pad(m.astype(np.float32), [(r, r), (0, 0)])
    return _sum_windows(p, w, axis=0) > 0.5


def _dilate_beams(mask: np.ndarray, r: int) -> np.ndarray:
    """Pad a mask along beams only."""
    m = np.asarray(mask, dtype=bool)
    r = int(r)
    if r <= 0:
        return m.copy()
    w = 2 * r + 1
    p = np.pad(m.astype(np.float32), [(0, 0), (r, r)])
    return _sum_windows(p, w, axis=1) > 0.5


def widen_band(band: np.ndarray, max_row: int = GLOBAL_ROW_CAP, max_beam: int = GLOBAL_BEAM_CAP,
               min_frac: float = MIN_BAND_FRAC) -> Tuple[np.ndarray, float, int, int]:
    """Grow ``band`` until it covers ``min_frac`` of the frame (lead F1, QA 02).

    A default ``structure_band`` hugs the bright band (~10 % of the pixels).  Used as a
    correlation *template* that is too tight: when the same feature moved by +-7 rows in the
    other frame, the profile of the reference is truncated at the band edge and the peak is
    pulled toward 0 (QA measured +7 -> +3 and -7 -> -3 / -4, while an explicit
    ``band=np.ones`` was exact).  Padding along rows restores the support the lag needs.

    Returns ``(band, frac, pad_rows, pad_beams)``.  A band that already covers >= min_frac is
    returned untouched, so an explicit ``np.ones`` band keeps the exact (unbiased) behaviour.
    """
    b = np.asarray(band, dtype=bool)
    frac = float(b.mean()) if b.size else 0.0
    pad_r = pad_b = 0
    if frac >= min_frac:
        return b, frac, 0, 0
    r = 0
    while float(b.mean()) < min_frac and r < int(max_row):
        r = min(int(max_row), max(4, r * 2))
        b = _dilate_rows(b, r)
        pad_r = r
    r = 0
    while float(b.mean()) < min_frac and r < int(max_beam):
        r = min(int(max_beam), max(2, r * 2))
        b = _dilate_beams(b, r)
        pad_b = r
    return b, float(b.mean()), pad_r, pad_b


def _support_profile(img: np.ndarray, band: np.ndarray, axis: int,
                     pad: int) -> Tuple[Optional[np.ndarray], int, int]:
    """Profile along ``axis`` over the band's *support*, fully averaged across the other axis.

    Returns ``(profile, n_support_lines, n_lines_used)``; ``profile`` is ``None`` when the
    support is empty.

    Why not a masked mean over the band pixels (the previous version, still available as
    :func:`masked_mean_profile`): ``structure_band`` hugs the brightest ridge and covers
    only ~3-10 % of the frame, so its per-row sample is a *narrow column subset*.  The
    profile then keeps only the flat core of the ridge and the cross-correlation peak is
    pulled by the truncation — QA measured +7 -> +3 and -7 -> -3/-4 with the default band
    while ``band=np.ones`` was exact, and a constructed 58-row band shifted by +7 came out
    as +4.  Averaging the whole orthogonal extent of the support restores the full dynamic
    range of the ridge (exact again on all four QA fixtures and on the synthetic frames),
    and padding the support by the search range keeps the moved feature inside the profile
    on both sides instead of clipping one of them.
    """
    band = np.asarray(band, dtype=bool)
    img = np.asarray(img, dtype=np.float64)
    if band.ndim != 2 or img.ndim != 2 or band.shape != img.shape:
        return None, 0, 0
    support = band.any(1) if axis == 1 else band.any(0)
    idx = np.where(support)[0]
    if idx.size == 0:
        return None, 0, 0
    lo = max(0, int(idx[0]) - int(pad))
    hi = min(int(support.size), int(idx[-1]) + int(pad) + 1)
    sub = img[lo:hi, :] if axis == 1 else img[:, lo:hi]
    if sub.size == 0:
        return None, 0, 0
    return sub.mean(axis=axis), int(idx.size), int(hi - lo)


def _shift_failure(reason: str, band_frac: float = 0.0, pad_rows: int = 0,
                   pad_beams: int = 0) -> dict:
    """Explicit failure record: never a plausible-looking number (lead F1, item 2)."""
    return {
        "ok": False, "reason": reason,
        "drow": 0, "dbeam": 0,
        "score_row": -1.0, "score_beam": -1.0, "score": -1.0,
        # a failed estimate is *not* a measurement, so it is flagged clipped as well (the
        # QA test for a degenerate band requires exactly this; lead F1 item 2 wants an
        # explicit failure instead of a plausible-looking number).
        "clipped": True, "beam_flat": True,
        "band_frac": float(band_frac), "band_pad_rows": int(pad_rows),
        "band_pad_beams": int(pad_beams),
        "align_score": -1.0, "align_score_beam": -1.0,
    }


def estimate_shift(a: np.ndarray, b: np.ndarray, band: Optional[np.ndarray] = None,
                   max_row: int = GLOBAL_ROW_CAP, max_beam: int = GLOBAL_BEAM_CAP,
                   min_band_frac: float = MIN_BAND_FRAC) -> dict:
    """Shift of ``b`` relative to ``a`` on the structure band; ``a`` is the reference.

    ``drow`` satisfies ``row_a = row_b + drow``: a feature at row 780 in ``b`` sits at
    ``780 + drow`` in ``a``.  Therefore the background (in ``a``'s pose) is brought to
    ``b``'s pose by ``shift_img(bg, -drow)``, and ``b`` is brought to ``a``'s pose by
    ``shift_img(b, +drow)``.

    ``clipped`` is true when the optimum sits on the search bound (within 1 px): the true
    shift is then outside the window and the number is a floor, not a measurement (lead:
    bomb reaches |drow| ~ 40+, grenade +53, so a +-40 window silently clipped).  A failed
    estimate (``ok=False``) is also flagged ``clipped``: it is not a measurement either.

    ``band`` is used as a *locator*, not as a per-pixel template: only the rows (beams) it
    touches matter, and the profile averages the whole other axis (see
    :func:`_support_profile`).  So the result no longer degrades when ``structure_band``
    covers 3 % instead of 60 % of the frame — which was the F1 defect (QA: +-7 -> 3/4).
    """
    band = structure_band(b) if band is None else np.asarray(band, dtype=bool)
    if band.ndim != 2 or band.shape != np.shape(a) or band.shape != np.shape(b):
        raise ValueError("band shape %r does not match frames %r/%r"
                         % (band.shape, np.shape(a), np.shape(b)))
    band_frac = float(band.mean()) if band.size else 0.0
    n_rows_total = int(band.shape[0])
    pad_r = int(max_row)

    # ---- row profile (lead F1 item 1: coverage must be enough for the lag) ----
    pa, n_rows, rows_used = _support_profile(a, band, 1, max_row)
    pb, _, _ = _support_profile(b, band, 1, max_row)
    if pa is None or pb is None or n_rows < 8:
        # < 8 supporting rows is the legacy "undefined correlation" floor: report a failure
        # instead of widening a 3-row band into a plausible-looking answer.
        return _shift_failure("degenerate_band", band_frac, pad_r, 0)
    if float(np.std(pa)) < 0.5 or float(np.std(pb)) < 0.5:
        # no intensity variation inside the profile at all: the correlation has no signal,
        # and the previous code returned the first lag of the search window (-max_row).
        return _shift_failure("degenerate_profile", band_frac, rows_used, 0)
    drow, crow = best_lag(pa, pb, max_row)
    if not (crow > 0.0):
        return _shift_failure("degenerate_band", band_frac, rows_used, 0)

    # ---- beam profile (only if the band has a real column support) ----
    qa, n_cols, cols_used = _support_profile(a, band, 0, max_beam)
    qb, _, _ = _support_profile(b, band, 0, max_beam)
    if qa is None or qb is None or n_cols < 4:
        dbeam, cbeam, beam_flat = 0, 0.0, True
    else:
        dbeam, cbeam = best_lag(qa, qb, max_beam)
        beam_flat = bool(float(np.std(qa)) < 1.0 or float(np.std(qb)) < 1.0)
    # a flat profile (the band spans every beam) carries no lag information; accepting a
    # lag there would smear the aligned background.  Measured: beam profile std ~3 gray
    # levels once masked-mean is used, so only a truly degenerate case is zeroed.
    if beam_flat:
        dbeam, cbeam = 0, 0.0
    # "on the search bound" must include the 1-px neighbourhood: a lag of max_row-1 is a
    # floor too (QA: a large shift was reported as +92 with clipped=False).
    clipped = bool(abs(drow) >= max(1, max_row - 1)
                   or (not beam_flat and abs(dbeam) >= max(1, max_beam - 1)))
    return {
        "ok": True, "reason": None,
        "drow": int(drow), "dbeam": int(dbeam),
        "score_row": float(crow), "score_beam": float(cbeam),
        "score": float(min(crow, cbeam)) if not beam_flat else float(crow),
        "clipped": clipped, "beam_flat": beam_flat,
        "band_frac": float(band_frac), "band_pad_rows": int(pad_r),
        "band_pad_beams": int(max_beam),
        "profile_rows": int(rows_used), "profile_row_frac": float(rows_used) / float(n_rows_total),
        "profile_cols": int(cols_used),
        "align_score": float(crow), "align_score_beam": float(cbeam),
    }


def shift_img(img: np.ndarray, drow: int, dbeam: int) -> np.ndarray:
    """Translate by whole pixels with edge replication (no wrap)."""
    img = np.asarray(img, dtype=np.float32)
    out = img
    if drow:
        if drow > 0:
            out = np.concatenate([np.repeat(out[:1], drow, axis=0), out[:-drow]], axis=0)
        else:
            out = np.concatenate([out[-drow:], np.repeat(out[-1:], -drow, axis=0)], axis=0)
    if dbeam:
        if dbeam > 0:
            out = np.concatenate([np.repeat(out[:, :1], dbeam, axis=1), out[:, :-dbeam]], axis=1)
        else:
            out = np.concatenate([out[:, -dbeam:], np.repeat(out[:, -1:], -dbeam, axis=1)], axis=1)
    return out


# ----------------------------------------------------------------------------------
# background model
# ----------------------------------------------------------------------------------


def _frames_of(rec) -> Tuple["G.Recording", List[int], List[Path]]:
    if isinstance(rec, G.Recording):
        r = rec
    else:
        r = G.load_recording(str(rec))
    return r, r.frames, [r.pgm_path(f) for f in r.frames]


def background_model(rec, n_sample: int = 121, n_ref: int = 40, anchor: Optional[int] = None,
                     verbose: bool = False) -> dict:
    """Temporal median + per-beam gain + motion-compensated aligned background.

    ``gain``   multiplicative per-beam gain (median 1) removing vertical stripes.
    ``median`` raw temporal median (no alignment) - the classic background.
    ``aligned`` median of the reference frames after shifting each back to the anchor pose.
    ``shifts``  per-reference-frame (drow, dbeam) used for the alignment (evidence).
    ``band``    bright band mask of the aligned median (the class-invariant structure).
    """
    r, frames, paths = _frames_of(rec)
    if not frames:
        raise RuntimeError(f"no frames in {r}")
    idx_all = np.unique(np.linspace(0, len(frames) - 1, int(n_sample)).astype(int))
    stack = np.stack([read_pgm(paths[i]) for i in idx_all])
    median = np.median(stack, axis=0).astype(np.float32)

    # per-beam gain (vertical stripes) from the median image itself
    col = np.median(median, axis=0)
    gain = (col / np.median(col)).astype(np.float32)
    gain = np.clip(gain, 0.5, 2.0)

    def corr(x):
        return (x / gain[None, :]).astype(np.float32)

    anchor_frame = int(anchor) if anchor is not None else int(frames[len(frames) // 2])
    anchor_img = corr(read_pgm(r.pgm_path(anchor_frame)))
    band = structure_band(anchor_img)

    ref_idx = np.unique(np.linspace(0, len(frames) - 1, int(n_ref)).astype(int))
    ref_frames = [int(frames[i]) for i in ref_idx]
    shifts = []
    aligned = []
    failures = []
    for f in ref_frames:
        img = corr(read_pgm(r.pgm_path(f)))
        # shift of the reference frame *relative to* the anchor; move it back by drow
        s = estimate_shift(anchor_img, img, band=band)
        shifts.append({"frame": f, **s})
        if not s.get("ok", True):
            # keep the failure in the record and leave the frame OUT of the median: a
            # degenerate estimate is not a measurement (lead F1, item 2).
            failures.append({"frame": f, "reason": s.get("reason")})
            continue
        aligned.append(shift_img(img, s["drow"], s["dbeam"]))
        if verbose and len(shifts) <= 3:
            print(f"  ref {f}: drow={s['drow']} dbeam={s['dbeam']} "
                  f"score={s['align_score']:.3f} band={s['band_frac']:.2f}")
    if not aligned:
        raise RuntimeError(f"all {len(ref_frames)} reference frames failed shift estimation "
                           f"for {r.recording}: {failures[:3]}")
    aligned_bg = np.median(np.stack(aligned), axis=0).astype(np.float32)
    band_bg = structure_band(aligned_bg)
    band_med = structure_band(median / gain[None, :])
    return {
        "recording": r.recording,
        "anchor_frame": anchor_frame,
        "n_sample": int(idx_all.size),
        "n_ref": len(ref_frames),
        "gain": gain,
        "median": median,
        "aligned": aligned_bg,
        "band": band_bg,
        "band_median": band_med,
        "shifts": shifts,
        "align_ok": not failures,
        "n_align_failed": len(failures),
        "align_failures": failures,
        "frames": frames,
        "header": dict(r.header),
    }


def aligned_background(rec, n_ref: int = 40, anchor: Optional[int] = None,
                       n_sample: int = 121) -> dict:
    """The motion-compensated static model alone (lead's ``aligned_background``).

    Returns ``{"aligned", "band", "shifts", "anchor_frame"}``.  ``shifts`` are the per
    reference-frame (drow, dbeam) that were compensated - they are evidence, not tuning.
    """
    bg = background_model(rec, n_sample=n_sample, n_ref=n_ref, anchor=anchor)
    return {k: bg[k] for k in ("aligned", "band", "shifts", "anchor_frame", "gain")}


_IMG_CACHE: Dict[str, np.ndarray] = {}
_IMG_CACHE_MAX = 400


def read_pgm_cached(path) -> np.ndarray:
    """PGM reader with a small cache: a +-10 frame local median touches 21 files per frame,
    and consecutive frames share 20 of them."""
    key = str(path)
    a = _IMG_CACHE.get(key)
    if a is None:
        a = read_pgm(path)
        if len(_IMG_CACHE) >= _IMG_CACHE_MAX:
            _IMG_CACHE.clear()
        _IMG_CACHE[key] = a
    return a


def local_background_model(rec, frame: int, half: int = 10,
                          global_bg: Optional[dict] = None) -> dict:
    """Sliding-window local temporal median background for ONE frame (lead m00453).

    Why not the motion-compensated model: the bright band is not a rigid body, so aligning it
    makes the residual *worse* (measured drop -1 % … -24 %, docs §6).  A +-HALF sliding median
    tracks the band instead of aligning it (lead measured 80 % suppression at HALF=10).

    **Assumption that must travel with every reading** (lead m00453 §3): a slides+median also
    erases anything that moves slower than ~HALF frames.  This recording turns 0.32 turns, so
    a target moves 1-2 rows inside +-10 frames and would be *removed as background*.  Hence a
    low local-median residual is NOT evidence that no target is present; candidates must be
    judged against the band (outside it, or protruding from its edges).
    """
    r, frames, paths = _frames_of(rec)
    if frame not in frames:
        raise KeyError(f"frame {frame} not in {r.recording}")
    idx = frames.index(int(frame))
    lo, hi = max(0, idx - int(half)), min(len(frames) - 1, idx + int(half))
    stack = np.stack([read_pgm_cached(paths[i]) for i in range(lo, hi + 1)]).astype(np.float32)
    med = np.median(stack, axis=0).astype(np.float32)
    col = np.median(med, axis=0)
    gain = np.clip(col / max(float(np.median(col)), 1e-6), 0.5, 2.0).astype(np.float32)
    med_c = (med / gain[None, :]).astype(np.float32)
    band = structure_band(med_c)
    out = {"mode": "local", "half": int(half), "frame": int(frame),
           "window": [int(frames[lo]), int(frames[hi])], "n_window": int(hi - lo + 1),
           "gain": gain, "median": med, "aligned": med_c, "band": band,
           "band_median": band, "anchor_frame": int(frame),
           "shifts": []}
    if global_bg is not None:
        # needed for the acceptance metric: band |d| of the local model vs the GLOBAL median
        out["median_global"] = (global_bg["median"] / global_bg["gain"][None, :]).astype(np.float32)
    return out


def bg_summary(bg: dict) -> dict:
    """JSON-able digest of a background model (masks/gains left out)."""
    sh = bg.get("shifts", [])
    d = np.array([[s["drow"], s["dbeam"]] for s in sh], dtype=float) if sh else np.zeros((0, 2))
    return {
        "recording": bg["recording"],
        "anchor_frame": bg["anchor_frame"],
        "n_sample": bg["n_sample"], "n_ref": bg["n_ref"],
        "gain_min": float(bg["gain"].min()), "gain_max": float(bg["gain"].max()),
        "shift_abs_median": [float(np.median(np.abs(d[:, 0]))) if len(d) else 0.0,
                             float(np.median(np.abs(d[:, 1]))) if len(d) else 0.0],
        "shift_range": [int(d[:, 0].min()) if len(d) else 0, int(d[:, 0].max()) if len(d) else 0,
                        int(d[:, 1].min()) if len(d) else 0, int(d[:, 1].max()) if len(d) else 0],
        "align_score_median": float(np.median([s["align_score"] for s in sh])) if sh else 0.0,
    }


# ----------------------------------------------------------------------------------
# structure domain / residual
# ----------------------------------------------------------------------------------


def frame_residual(img: np.ndarray, bg: dict, shift: Optional[dict] = None,
                   model: str = "aligned") -> dict:
    """Corrected frame, shift, background at this pose, residual d.

    ``model="aligned"`` uses the motion-compensated median (default; the shift is estimated
    per frame).  ``model="median"`` uses the plain temporal median and no shift - kept
    because measurement (docs/geometry-calibration.md) shows the aligned model does NOT
    remove the bright band either, so both are reported rather than one hidden.
    """
    gain = bg["gain"]
    img_c = (np.asarray(img, dtype=np.float32) / gain[None, :]).astype(np.float32)
    if model in ("median", "local"):
        shift = {"ok": True, "drow": 0, "dbeam": 0, "align_score": None,
                 "align_score_beam": None}
        band = bg.get("band_median", bg["band"])
        bg_at = (bg["median"] / gain[None, :]).astype(np.float32)
    else:
        if shift is None:
            # drow is the background's row minus this frame's row: bring the background
            # *to this pose* by -drow (see estimate_shift docstring for the sign proof).
            shift = estimate_shift(bg["aligned"], img_c, band=bg["band"])
        if not shift.get("ok", True):
            # do not compensate with a degenerate number: keep the frame at the anchor pose
            # and carry the failure so the caller can mark the frame instead of trusting it.
            shift = {**shift, "drow": 0, "dbeam": 0}
        band = bg["band"]
        bg_at = shift_img(bg["aligned"], -int(shift["drow"]), -int(shift["dbeam"]))
    d = (img_c - bg_at).astype(np.float32)
    return {"img_corr": img_c, "bg_at": bg_at, "d": d, "shift": shift, "band": band,
            "align_ok": bool(shift.get("ok", True))}


def structures(d: np.ndarray, bg: dict, shift: dict, band: Optional[np.ndarray] = None,
               thr: float = 1.5, min_area_frac: float = 0.004,
               min_beam_span: int = 40, rim: int = 6) -> Tuple[np.ndarray, List[dict]]:
    """Large, class-invariant echo structures visible in this frame.

    Two sources are unioned: (a) the persistent bright band carried by the background model,
    shifted to this pose; (b) large low-threshold components of the residual that span many
    beams.  Everything here is role="structure" and must not become a candidate box.
    """
    H, W = d.shape
    band = bg["band"] if band is None else band
    stat = shift_img(band.astype(np.float32), -int(shift["drow"]), -int(shift["dbeam"])) > 0.5
    # ``rim`` covers the band's own intensity gradient.  With rim=2 every 3-sigma blob of
    # these recordings sat on that gradient (zoomed overlays: tmp/geom/zoom_cands.png), i.e.
    # the detector was reporting band-edge speckle as candidates; rim=6 removes them.
    stat = dilate(stat, int(rim))
    # residuals: robust per-beam scale
    scale = 1.4826 * np.median(np.abs(d - np.median(d, axis=0)), axis=0)
    floor = max(0.5, 0.35 * float(np.median(scale)))
    snr = d / np.maximum(scale, floor)[None, :]
    m = (snr > thr) & ~stat
    m = open_h(m, 9)
    labels, n = label_numpy(m)
    mask = stat.copy()
    near_band = dilate(stat, 8)
    out = []
    min_area = max(60, int(min_area_frac * H * W))
    for lab in range(1, n + 1):
        ys, xs = np.nonzero(labels == lab)
        if ys.size < min_area:
            continue
        span_b = int(xs.max() - xs.min() + 1)
        if span_b < min_beam_span:
            continue
        # only components attached to the band are structure.  A large low-threshold
        # component far below the band is unioned speckle (the residual threshold is low by
        # design), and letting it into the mask would swallow the whole frame and hide every
        # candidate - measured behaviour, not a guess (docs §6).
        attached = float(near_band[ys, xs].mean()) > 0.30
        if not attached:
            continue
        # Clip the contribution to the 8-px rim of the band.  Adding the component's whole
        # extent let one low-threshold splotch turn 50 % of the frame into "structure"
        # (measured: mask coverage 0.58 with a 0.10 band), which silently suppresses every
        # candidate below it - the failure mode lead warned about, just inverted.
        keep = near_band[ys, xs]
        ys, xs = ys[keep], xs[keep]
        if ys.size < 60:
            continue
        mask[ys, xs] = True
        out.append({"role": "structure", "class_invariant": True,
                    "excluded_from_candidates": True, "source": "residual_rim",
                    "sigma": "large", "box_xyxy": [int(xs.min()), int(ys.min()),
                                                    int(xs.max()), int(ys.max())],
                    "area": int(ys.size), "beam_span": int(xs.max() - xs.min() + 1),
                    "row_span": int(ys.max() - ys.min() + 1)})
    ys, xs = np.nonzero(stat)
    if ys.size:
        out.insert(0, {"role": "structure", "class_invariant": True,
                       "excluded_from_candidates": True, "source": "static_band",
                       "sigma": "large", "box_xyxy": [int(xs.min()), int(ys.min()),
                                                       int(xs.max()), int(ys.max())],
                       "area": int(ys.size),
                       "beam_span": int(xs.max() - xs.min() + 1),
                       "row_span": int(ys.max() - ys.min() + 1)})
    return mask, out


# ----------------------------------------------------------------------------------
# candidates
# ----------------------------------------------------------------------------------

DEF = dict(thr=3.0, bg_k=31, smooth=3, open_w=3, min_area=25, max_beam_span=64,
           max_row_span=140, struct_overlap_max=0.5, merge_r=1, static_overlap_w=0.5)


def perturbations(d: np.ndarray, struct_mask: np.ndarray,
                  band: Optional[np.ndarray] = None, **kw) -> List[dict]:
    """Small, bright, sharp residual blobs after the structure domain is removed."""
    p = dict(DEF)
    p.update(kw)
    d = np.asarray(d, dtype=np.float32)
    H, W = d.shape
    # Smooth FIRST, then normalise.  Smoothing a per-pixel SNR inflates the effective
    # threshold: box-mean of unit-variance noise has std ~1/3, so "3 sigma" on the smoothed
    # map is ~9 sigma of the raw one and the detector returns nothing at all (measured: 0
    # candidates on every frame before this fix).  Normalising after smoothing makes 3 a
    # real 3-sigma cut of the smoothed residual, i.e. the ~0.3 % tail the threshold implies.
    if p["smooth"] > 1:
        d = box_mean(box_mean(d, int(p["smooth"]), 0), int(p["smooth"]), 1)
    bg = local_background(d, int(p["bg_k"]))
    r = d - bg
    scale = 1.4826 * np.median(np.abs(r), axis=0)
    floor = max(0.5, 0.35 * float(np.median(scale)))
    snr = r / np.maximum(scale, floor)[None, :]

    mask = snr >= float(p["thr"])
    mask = open_square(mask, int(p["open_w"]))
    if p["merge_r"] > 0:
        mask = dilate(mask, int(p["merge_r"]))
    labels, n = label_numpy(mask)
    out = []
    for lab in range(1, n + 1):
        ys, xs = np.nonzero(labels == lab)
        area = int(ys.size)
        if area < int(p["min_area"]):
            continue
        y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
        w, h = x1 - x0 + 1, y1 - y0 + 1
        if w > int(p["max_beam_span"]) or h > int(p["max_row_span"]):
            continue  # structure-sized -> not a candidate
        s_overlap = float(struct_mask[ys, xs].mean())
        if s_overlap > float(p["struct_overlap_max"]):
            continue  # sits on the class-invariant structure: refuse to call it a target
        snr_v = snr[ys, xs]
        fill = area / float(w * h)
        # relation to the class-invariant band (lead m00453: rank by this, not by size)
        if band is not None and band.any():
            band_overlap = float(band[ys, xs].mean())
            cols = np.flatnonzero(band.any(axis=0))
            tops, bots = [], []
            for c in range(x0, x1 + 1):
                rows_c = np.flatnonzero(band[:, c])
                if rows_c.size:
                    tops.append(int(rows_c[0])); bots.append(int(rows_c[-1]))
            if tops:
                above = max(0, min(tops) - y0)
                below = max(0, y1 - max(bots))
                protrude = int(max(above, below))
            else:
                above = below = 0
                protrude = 0
        else:
            band_overlap, above, below, protrude = 0.0, 0, 0, 0
        score = (float(snr_v.max()) * fill / (1.0 + area / 150.0)
                 * (1.0 - p["static_overlap_w"] * s_overlap))
        out.append({
            "role": "candidate", "rank": -1,
            "box_xyxy": [x0, y0, x1, y1], "area": area,
            "peak": int(np.asarray(d)[ys, xs].max()),
            "mean": float(np.asarray(d)[ys, xs].mean()),
            "snr": float(snr_v.mean()), "snr_peak": float(snr_v.max()),
            "centroid": [float(xs.mean()), float(ys.mean())],
            "n_components_merged": 1, "fill": float(fill),
            "beam_span": w, "row_span": h,
            "structure_overlap": s_overlap,
            "band_overlap": float(band_overlap),
            "outside_band": bool(band_overlap < 0.5),
            "protrude_rows": int(protrude),
            "protrude_above": int(above), "protrude_below": int(below),
            "clipped": bool(x0 <= 0 or x1 >= W - 1 or y0 <= 0 or y1 >= H - 1),
            "score": score,
        })
    out.sort(key=lambda b: (-b["score"], b["box_xyxy"][1], b["box_xyxy"][0]))
    for i, b in enumerate(out):
        b["rank"] = i
        b["rival_second"] = float(out[1]["score"]) if (i == 0 and len(out) > 1) else None
    return out


def detect(img: np.ndarray, predicted: Optional[dict] = None, bg: Optional[dict] = None,
           mode: str = "aligned", **kw) -> List[dict]:
    """Candidates for one frame, best first (``rank=0``).

    ``mode="aligned"`` (default): motion-compensated background model, structure domain
    removed.  ``mode="raw"``: no background subtraction, only local SNR (kept for the
    earlier two-set comparison; structures are then *not* removed, so it will happily box
    the band - which is why it is not the default).

    ``predicted`` is accepted only for interface compatibility with T-GEOM; geometry is
    degraded (BRIEF §2.2) and it is ignored.
    """
    if bg is None:
        raise ValueError("detect() needs a background model; call background_model(recording)")
    img = np.asarray(img, dtype=np.float32)
    if mode in ("aligned", "median"):
        fr = frame_residual(img, bg, model=mode)
        smask, _structs = structures(fr["d"], bg, fr["shift"], band=fr["band"])
        blobs = perturbations(fr["d"], smask, **kw)
        shift = fr["shift"]
    elif mode == "raw":
        smask = np.zeros(img.shape, dtype=bool)
        blobs = perturbations(img, smask, **kw)
        shift = {"ok": True, "drow": 0, "dbeam": 0, "align_score": None,
                 "align_score_beam": None}
    else:
        raise ValueError(f"unknown mode {mode!r}")
    for b in blobs:
        b["mode"] = mode
        b["shift"] = shift
    return blobs


def analyse_frame(img: np.ndarray, bg: dict, mode: str = "aligned", **kw) -> dict:
    """Everything one frame contributes: shift, structure mask, candidates, band energy."""
    img = np.asarray(img, dtype=np.float32)
    if mode == "raw":
        fr = frame_residual(img, bg, model="median")
        smask = np.zeros(img.shape, dtype=bool)
        structs: List[dict] = []
        blobs = perturbations(img, smask, band=fr["band"], **kw)
        fr["d"] = img
    elif mode == "local":
        fr = frame_residual(img, bg, model="local")
        smask, structs = structures(fr["d"], bg, fr["shift"], band=fr["band"])
        blobs = perturbations(fr["d"], smask, band=fr["band"], **kw)
    else:
        fr = frame_residual(img, bg, model=mode)
        smask, structs = structures(fr["d"], bg, fr["shift"], band=fr["band"])
        blobs = perturbations(fr["d"], smask, **kw)
    band_at = shift_img(fr["band"].astype(np.float32), -int(fr["shift"]["drow"]),
                        -int(fr["shift"]["dbeam"])) > 0.5
    if not band_at.any():
        band_at = fr["band"]
    e_align = float(np.median(np.abs(fr["d"][band_at])))
    _ref = bg.get("median_global")
    if _ref is None:
        _ref = bg["median"] / bg["gain"][None, :]
    e_raw = float(np.median(np.abs(fr["img_corr"] - _ref)[band_at]))
    align_ok = bool(fr.get("align_ok", True))
    for b in blobs:
        b["mode"] = mode
        b["shift"] = fr["shift"]
    return {
        "shift": fr["shift"],
        "struct_mask": smask,
        "structures": structs,
        "blobs": blobs,
        "band": fr["band"],
        "energy": {"band_medabs_model": e_align, "band_medabs_median": e_raw,
                   "drop_frac": ((1.0 - e_align / e_raw)
                                 if e_raw and e_raw > 0 and align_ok else None),
                   "align_ok": align_ok,
                   "align_reason": (fr["shift"].get("reason") if not align_ok else None)},
    }


# ----------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------


def render_grid(rec, frames: Sequence[int], recs: List[dict], out_path, scale: float = 0.75,
                row_slice: Optional[Tuple[int, int]] = None, cols: int = 4) -> Path:
    """Overlay grid: grayscale frame, structure domain tinted, candidates as cyan boxes.

    One cell per frame, label strip under each cell.  ``row_slice=None`` keeps every row
    (the 441-row recordings are shorter than the old hard-coded 40..700 window).
    """
    from PIL import Image, ImageDraw

    y0, y1 = row_slice if row_slice is not None else (0, rec.n_rows)
    y0 = max(0, int(y0)); y1 = min(rec.n_rows, int(y1) or rec.n_rows)
    by_frame = {r["frame"]: r for r in recs}
    cw = max(1, int(rec.n_beams * scale))
    ch = max(1, int((y1 - y0) * scale))
    nrows = (len(frames) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * cw, nrows * (ch + 14)), (0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    for k, f in enumerate(frames):
        r = by_frame.get(f)
        if r is None:
            continue
        img = read_pgm(rec.pgm_path(f))
        a = analyse_frame(img, r["_bg"], mode=r["mode"], **r.get("_kw", {})) if "_bg" in r else None
        view = img[y0:y1]
        rgb = np.repeat(np.clip(view, 0, 255).astype(np.uint8)[:, :, None], 3, axis=2)
        if a is not None:
            sm = a["struct_mask"][y0:y1]
            rgb[sm] = (0.55 * rgb[sm] + np.array([0, 40, 60])).astype(np.uint8)
        im = Image.fromarray(rgb).resize((cw, ch), Image.NEAREST)
        cx, cy = (k % cols) * cw, (k // cols) * (ch + 14)
        canvas.paste(im, (cx, cy))
        if a is not None:
            for b in a["blobs"][:3]:
                x0, yb0, x1, yb1 = b["box_xyxy"]
                box = [cx + x0 * scale, cy + (yb0 - y0) * scale,
                       cx + (x1 + 1) * scale, cy + (yb1 + 1 - y0) * scale]
                col = (0, 255, 255) if b["rank"] == 0 else (0, 150, 150)
                draw.rectangle(box, outline=col)
            top = a["blobs"][0] if a["blobs"] else None
            txt = f"{f} n{len(a['blobs'])}"
            if top:
                txt += f" s{top['snr_peak']:.0f} {top['row_span']}x{top['beam_span']}"
        else:
            txt = str(f)
        max_chars = max(4, int(cw / 5.2))
        draw.text((cx + 2, cy + ch + 1), txt[:max_chars], fill=(235, 235, 235))
        draw.rectangle([cx, cy, cx + cw - 1, cy + ch - 1], outline=(60, 60, 60))
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="echo candidates for frames of one recording")
    ap.add_argument("--recording", required=True)
    ap.add_argument("--frames", default="", help="absolute frame numbers, comma separated")
    ap.add_argument("--mode", default="local", choices=["local", "aligned", "median", "raw"])
    ap.add_argument("--half", type=int, default=10,
                    help="local background: +-HALF frames (local mode only)")
    ap.add_argument("--bg-sample", type=int, default=121)
    ap.add_argument("--n-ref", type=int, default=40)
    ap.add_argument("--jsonl", default="", help="write one JSON record per frame here")
    ap.add_argument("--proposals", default="",
                    help="write BRIEF §4 proposal records here (out/<recording>/proposals.jsonl)")
    ap.add_argument("--overlay", default="", help="write a PNG overlay grid here")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv)

    rec = G.load_recording(args.recording)
    bg = None
    gmed = None
    if args.mode in ("local",) or args.mode in ("aligned", "median", "raw"):
        print(f"[bg] {rec.recording}: background model ({args.bg_sample} samples, "
              f"{args.n_ref} refs) ...")
        bg = background_model(rec, n_sample=args.bg_sample, n_ref=args.n_ref, verbose=True)
        print("[bg]", json.dumps(bg_summary(bg), ensure_ascii=False))
        gmed = bg
    else:
        print(f"[bg] {rec.recording}: sliding local median, half=+-{args.half} frames")

    want = [int(s) for s in args.frames.replace(" ", "").split(",") if s]
    if not want:
        step = max(1, rec.n_frames // 12)
        want = rec.frames[::step][:12]
    if args.limit:
        want = want[: args.limit]

    recs, drops, overlaps, spans, empties = [], [], [], [], 0
    for f in want:
        if not rec.has_frame(f):
            print(f"  frame {f}: NOT PRESENT")
            continue
        img = read_pgm_cached(rec.pgm_path(f))
        bg_i = (local_background_model(rec, f, half=args.half, global_bg=gmed)
                if args.mode == "local" else bg)
        a = analyse_frame(img, bg_i, mode=args.mode)
        top = a["blobs"][0] if a["blobs"] else None
        recs.append({"frame": f, "mode": args.mode, "shift": a["shift"],
                     "energy": a["energy"], "n_candidates": len(a["blobs"]),
                     "top": top, "structures": a["structures"],
                     "n_rows": int(rec.n_rows), "n_beams": int(rec.n_beams),
                     "range_window_m": [float(v) for v in rec.range_window],
                     "bg": {"mode": bg_i.get("mode", args.mode),
                            "half": bg_i.get("half"), "window": bg_i.get("window")},
                     "blobs": a["blobs"]})
        drops.append(a["energy"]["drop_frac"])
        if top:
            overlaps.append(top["structure_overlap"])
            spans.append(top["beam_span"])
        else:
            empties += 1
        print(f"  f{f}: n_cand={len(a['blobs'])} "
              f"drop={a['energy']['drop_frac']:+.2f} "
              + (f"top=({top['centroid'][0]:.0f},{top['centroid'][1]:.0f}) "
                 f"span={top['beam_span']}x{top['row_span']} snr={top['snr_peak']:.1f} "
                 f"ov={top['structure_overlap']:.2f} score={top['score']:.1f}"
                 if top else "top=None"))

    def _m(xs):
        return float(np.median(xs)) if xs else float("nan")

    summary = {"recording": rec.recording, "mode": args.mode, "n_frames": len(recs),
               "empty_frames": empties, "shift_abs_median": [
                   _m([abs(r["shift"]["drow"]) for r in recs]),
                   _m([abs(r["shift"]["dbeam"]) for r in recs])],
               "band_energy_drop_median": _m([d for d in drops if d is not None]),
               "top_structure_overlap_median": _m(overlaps),
               "top_beam_span_median": _m(spans)}
    print("[summary]", json.dumps(summary, ensure_ascii=False))
    if args.proposals and recs:
        out = Path(args.proposals)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True, default=str) + "\n")
        print(f"-> {out} ({len(recs)} records)")
    if args.overlay and recs:
        for r in recs:
            r["_bg"] = bg if bg is not None else None
            r["_kw"] = {}
        out = render_grid(rec, [r["frame"] for r in recs], recs, args.overlay)
        print(f"-> {out}")
    if args.jsonl:
        out = Path(args.jsonl)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            for r in recs:
                r = {k: v for k, v in r.items() if not k.startswith("_")}
                fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True, default=str) + "\n")
        print(f"-> {out} ({len(recs)} records)")
    return 0
    if args.jsonl:
        out = Path(args.jsonl)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True, default=str) + "\n")
        print(f"-> {out} ({len(recs)} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
