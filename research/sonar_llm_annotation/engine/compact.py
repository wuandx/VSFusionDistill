"""Compact-echo detector: a spatial CFAR for targets that barely move relative to sonar.

Why this module exists
----------------------
`engine/echo.py` suppresses the background with a *local temporal median*.  That is the
right tool for a stationary rig and a moving scene, and it is what produced the honest
"no discrete echo" reading for the first three recordings we picked
(`2023-09-20_171105`, `2023-09-21_120653`, `2023-09-21_100927`).

A survey of all 40 approved recordings (`tmp/lead_survey.py`) showed the bright return
sitting at very different range rows, and in several recordings peaking on only 5-25
beams - the signature of a compact object rather than a full-width band.  Looking at
`2023-09-21_105230` and `2023-09-21_101840` confirms it, and shows *why* the temporal
median missed them: the object is a bright blob at a nearly fixed (row, beam) across
+-10 frames, so the median background contains it and subtraction deletes it.

So this detector is deliberately spatial and single-frame:

  1. 3x3 box smoothing      -> kill single-pixel speckle
  2. 31x31 local mean       -> the background it must beat
  3. robust sigma (1.4826*MAD) -> SNR in units of the frame's own noise
  4. threshold + 3x3 open   -> candidate pixels
  5. connected components   -> boxes; a component wider than 70 beams is called the
                               class-invariant band ("structure"), never a candidate

No scipy / cv2 / skimage.  Everything here is numpy, deterministic, and runs in ~ms/frame.

The output row is the same working format `engine/echo.py` writes, so `engine/cards.py`
consumes it unchanged (`proposal_to_record`).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import geometry as G  # noqa: E402

ENGINE_VERSION = "compact/v0"
DEFAULTS = dict(
    smooth=3,          # box smoothing side
    block=16,          # block-median background block side
    bg_k=31,           # local-mean background side (kept for the energy/noise report)
    snr_thr=6.0,       # detection threshold, in robust sigma
    min_area=30,       # smaller than this is speckle
    open_w=2,          # 3x3 opening after threshold (0 = off)
    band_beams=70,     # a component this wide is the class-invariant band
    max_blobs=5,
)


# --------------------------------------------------------------------------- primitives
def box_mean(img: np.ndarray, k: int) -> np.ndarray:
    """Mean over a k x k window via an integral image, edges replicated.

    A plain cumsum trick: the integral image makes the cost independent of k, which
    matters because we run this on every frame of a 839-frame recording.
    """
    if k <= 1:
        return img.astype(np.float32)
    p = k // 2
    pad = np.pad(img.astype(np.float64), ((p, p), (p, p)), mode="edge")
    ii = pad.cumsum(0).cumsum(1)
    ii = np.pad(ii, ((1, 0), (1, 0)), mode="constant")
    h, w = img.shape
    s = ii[k:k + h, k:k + w] - ii[0:h, k:k + w] - ii[k:k + h, 0:w] + ii[0:h, 0:w]
    return (s / float(k * k)).astype(np.float32)


def _erode(mask: np.ndarray, w: int) -> np.ndarray:
    """Binary erosion with a (2w+1)-square structuring element."""
    if w <= 0:
        return mask
    out = mask.copy()
    h, wd = mask.shape
    for dy in range(-w, w + 1):
        for dx in range(-w, w + 1):
            if dy == 0 and dx == 0:
                continue
            shifted = np.zeros_like(mask)
            ys0, ys1 = max(0, dy), min(h, h + dy)
            xs0, xs1 = max(0, dx), min(wd, wd + dx)
            shifted[ys0:ys1, xs0:xs1] = mask[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
            out &= shifted
    return out


def open_square(mask: np.ndarray, w: int) -> np.ndarray:
    """Opening = erosion then dilation, both with a square element."""
    if w <= 0:
        return mask
    e = _erode(mask, w)
    out = e.copy()
    h, wd = mask.shape
    for dy in range(-w, w + 1):
        for dx in range(-w, w + 1):
            if dy == 0 and dx == 0:
                continue
            shifted = np.zeros_like(e)
            ys0, ys1 = max(0, dy), min(h, h + dy)
            xs0, xs1 = max(0, dx), min(wd, wd + dx)
            shifted[ys0:ys1, xs0:xs1] = e[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
            out |= shifted
    return out


def components(mask: np.ndarray, connectivity: int = 4) -> List[dict]:
    """Connected components by iterative flood fill, with bounding boxes."""
    h, w = mask.shape
    seen = np.zeros_like(mask, bool)
    out: List[dict] = []
    ys, xs = np.nonzero(mask)
    neigh = ((1, 0), (-1, 0), (0, 1), (0, -1))
    if connectivity == 8:
        neigh = neigh + ((1, 1), (1, -1), (-1, 1), (-1, -1))
    for y0, x0 in zip(ys.tolist(), xs.tolist()):
        if seen[y0, x0]:
            continue
        stack = [(y0, x0)]
        seen[y0, x0] = True
        pix_y, pix_x = [], []
        while stack:
            y, x = stack.pop()
            pix_y.append(y)
            pix_x.append(x)
            for dy, dx in neigh:
                yy, xx = y + dy, x + dx
                if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True
                    stack.append((yy, xx))
        ay = np.asarray(pix_y)
        ax = np.asarray(pix_x)
        out.append({
            "area": int(ay.size),
            "row0": int(ay.min()), "row1": int(ay.max()),
            "beam0": int(ax.min()), "beam1": int(ax.max()),
            "cy": float(ay.mean()), "cx": float(ax.mean()),
        })
    return out


# --------------------------------------------------------------------------- detector
def block_median_background(img: np.ndarray, block: int = 16) -> np.ndarray:
    """Robust background: median inside each block, then smoothed back up.

    A 31x31 *mean* is dragged upward by a blob wider than the window, which is exactly
    the case here (the object spans 10-40 beams).  A block median ignores the blob as
    long as it covers less than half a block, so it stays at the water level.
    """
    a = img.astype(np.float32)
    h, w = a.shape
    bh, bw = (-(-h // block)) * block, (-(-w // block)) * block
    pad = np.full((bh, bw), np.nan, np.float32)
    pad[:h, :w] = a
    blocks = pad.reshape(bh // block, block, bw // block, block).transpose(0, 2, 1, 3)
    med = np.nanmedian(blocks.reshape(bh // block, bw // block, block * block), axis=2)
    # upsample by repeat, then soften so block edges do not create false gradients
    up = np.repeat(np.repeat(med, block, axis=0), block, axis=1)[:h, :w]
    return box_mean(up, max(3, block | 1))


def detect_compact(img: np.ndarray, **kw) -> dict:
    """One frame -> structure boxes + compact candidate blobs (engine row fragment)."""
    p = dict(DEFAULTS)
    p.update(kw)
    a = img.astype(np.float32)
    smooth = box_mean(a, int(p["smooth"]))
    bg = block_median_background(smooth, int(p["block"]))
    d = smooth - bg
    med = float(np.median(d))
    mad = float(np.median(np.abs(d - med)))
    sigma = max(1.4826 * mad, 1e-6)
    snr = (d - med) / sigma

    raw = open_square(snr >= float(p["snr_thr"]), int(p["open_w"]))
    comps = components(raw, connectivity=4)

    structures: List[dict] = []
    blobs: List[dict] = []
    for c in comps:
        beam_span = c["beam1"] - c["beam0"] + 1
        row_span = c["row1"] - c["row0"] + 1
        sub = snr[c["row0"]:c["row1"] + 1, c["beam0"]:c["beam1"] + 1]
        if beam_span >= int(p["band_beams"]):
            structures.append({
                "role": "structure", "class_invariant": True,
                "excluded_from_candidates": True, "source": "wide_band",
                "box_xyxy": [c["beam0"], c["row0"], c["beam1"], c["row1"]],
                "area": c["area"], "beam_span": beam_span, "row_span": row_span,
                "sigma": "large" if beam_span >= 90 else "medium",
                "snr_peak": round(float(sub.max()), 2),
            })
            continue
        if c["area"] < int(p["min_area"]):
            continue
        peak = float(sub.max())
        if peak < float(p["snr_thr"]) + 1.0:
            continue
        blobs.append({
            "role": "candidate",
            "box_xyxy": [c["beam0"], c["row0"], c["beam1"], c["row1"]],
            "area": c["area"], "beam_span": beam_span, "row_span": row_span,
            "fill": round(c["area"] / float(beam_span * row_span), 3),
            "snr": round(peak, 2),
            "snr_mean": round(float(sub.mean()), 2),
            "peak": int(img[c["row0"]:c["row1"] + 1, c["beam0"]:c["beam1"] + 1].max()),
            "centroid": [round(c["cy"], 1), round(c["cx"], 1)],
            "structure_overlap": 0.0,
            "score": round(peak * float(np.sqrt(c["area"])), 2),
        })
    blobs.sort(key=lambda b: b["score"], reverse=True)
    for b in blobs:
        b["rank"] = blobs.index(b) + 1
    return {
        "mode": "compact",
        "params": {k: p[k] for k in ("smooth", "block", "snr_thr", "min_area", "open_w",
                                     "band_beams")},
        "noise": {"median": round(med, 3), "sigma": round(sigma, 3)},
        "structures": structures,
        "blobs": blobs[: int(p["max_blobs"])],
        "n_candidates": min(len(blobs), int(p["max_blobs"])),
        "n_components": len(comps),
    }


def analyse(recording: str, frame: int, **kw) -> dict:
    """Full engine row for one frame, shaped exactly like engine/echo.py's proposals."""
    rec = G.load_recording(recording, with_meta=False)
    img = np.asarray(_read_pgm(rec.pgm_path(frame)))
    res = detect_compact(img, **kw)
    rw = list(rec.range_window)
    return {
        "frame": int(frame),
        "recording": recording,
        "category": rec.category,
        "mode": res["mode"],
        "n_rows": int(rec.n_rows),
        "n_beams": int(rec.n_beams),
        "range_window_m": [float(rw[0]), float(rw[1])],
        "bg": {"mode": "spatial-block-median", "block": res["params"]["block"]},
        "energy": {"noise": res["noise"], "n_components": res["n_components"]},
        "structures": res["structures"],
        "blobs": res["blobs"],
        "n_candidates": res["n_candidates"],
        "top": res["blobs"][0] if res["blobs"] else None,
        "provenance": {"engine_version": ENGINE_VERSION, "params": res["params"]},
    }


def _read_pgm(path) -> np.ndarray:
    from engine import echo  # local import: echo.py owns the PGM reader
    return echo.read_pgm_cached(str(path))


# --------------------------------------------------------------------------- CLI
def _frames_arg(s: str) -> List[int]:
    return [int(x) for x in s.replace(" ", "").split(",") if x]


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Compact-echo detector (spatial CFAR)")
    ap.add_argument("--recording", required=True)
    ap.add_argument("--frames", help="comma list; default = every --every-th frame")
    ap.add_argument("--every", type=int, default=20, help="stride when --frames is absent")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", help="proposals.jsonl path")
    ap.add_argument("--snr", type=float, default=DEFAULTS["snr_thr"])
    ap.add_argument("--min-area", type=int, default=DEFAULTS["min_area"])
    ap.add_argument("--open", dest="open_w", type=int, default=DEFAULTS["open_w"],
                    help="opening width in px (0 disables; 1 erases 1-px specks)")
    ap.add_argument("--print", action="store_true", help="one line per frame on stdout")
    args = ap.parse_args(argv)

    rec = G.load_recording(args.recording, with_meta=False)
    if args.frames:
        frames = _frames_arg(args.frames)
    else:
        frames = sorted(rec.frames)[:: max(1, args.every)]
    if args.limit:
        frames = frames[: args.limit]

    rows = []
    for f in frames:
        row = analyse(args.recording, f, snr_thr=args.snr, min_area=args.min_area,
                      open_w=args.open_w)
        rows.append(row)
        if args.print:
            top = row["top"]
            if top is None:
                print(f"  f{f:4d}  no candidate   (structures {len(row['structures'])})")
            else:
                print(f"  f{f:4d}  score {top['score']:6.2f}  snr {top['snr']:5.2f}  "
                      f"area {top['area']:4d}  span {top['beam_span']:3d}x{top['row_span']:3d}  "
                      f"box {top['box_xyxy']}  fill {top['fill']}")
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        hits = sum(1 for r in rows if r["n_candidates"])
        print(f"[compact] {len(rows)} frames, {hits} with a candidate -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
