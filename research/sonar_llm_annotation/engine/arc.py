"""Arc-shaped returns: the shape this data actually produces.

``engine/compact.py`` finds 5x5 px blobs and ``engine/echo.py`` subtracts a
temporal median. Neither describes what is on these recordings: a thin specular
arc, 1-3 px wide, tens of rows long, with a bright core and faint ends. On
2023-09-21_105230 the compact detector's boxes cover about a tenth of the
visible return, and the temporal median deletes the arc entirely because the
head keeps re-aiming at it.

The convention here (agreed with the user on 2026-11-12):
  box = connected bright region that contains the frame's brightest pixel,
        grown along the trace, plus a 1.6x margin.
  the arc IS the munition's return; identity is still not a measurement.

Frame-to-frame the extractor follows the previous box (window +-40 px), so a
series is a track, not twelve independent argmaxes: on 105230 an independent
argmax jumps onto the 1.85 m band at f735/f876, 75 px away from the arc.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import numpy as np

ENGINE_VERSION = "arc/v0"
DEFAULTS = dict(block=24, lo=2.2, hi=6.0, radius=40, margin=1.6, min_pad=2, win=70, extend=False)


def _block_median(img: np.ndarray, block: int) -> np.ndarray:
    h, w = img.shape
    bh, bw = int(np.ceil(h / block)), int(np.ceil(w / block))
    pad = np.pad(img, ((0, bh * block - h), (0, bw * block - w)), mode="edge")
    tiles = pad.reshape(bh, block, bw, block).transpose(0, 2, 1, 3).reshape(bh, bw, -1)
    med = np.median(tiles, axis=2)
    return np.repeat(np.repeat(med, block, axis=0), block, axis=1)[:h, :w]


def _components(mask: np.ndarray) -> List[np.ndarray]:
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out: List[np.ndarray] = []
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys, xs):
        if seen[y0, x0]:
            continue
        stack = [(y0, x0)]
        seen[y0, x0] = True
        pix = []
        while stack:
            y, x = stack.pop()
            pix.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        out.append(np.array(pix))
    return out


def _pad_box(box: Sequence[int], w: int, h: int, scale: float, min_pad: int) -> List[int]:
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    bw, bh = x2 - x1, y2 - y1
    nw = max(bw * scale, bw + 2 * min_pad)
    nh = max(bh * scale, bh + 2 * min_pad)
    return [int(round(max(0, cx - nw / 2))), int(round(max(0, cy - nh / 2))),
            int(round(min(w, cx + nw / 2))), int(round(min(h, cy + nh / 2)))]


def _dilate(mask: np.ndarray, r: int = 1) -> np.ndarray:
    out = mask.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dy == 0 and dx == 0:
                continue
            out |= np.roll(np.roll(mask, dy, axis=0), dx, axis=1)
    return out


def _extend_ridge(d: np.ndarray, thr: float, raw: Sequence[int],
                  max_ext: int = 80, max_dev: int = 4, gap: int = 3) -> List[int]:
    """Walk a thin ridge left and right from the box, column by column.

    The search window above is only +-40 px, so a long specular streak gets cut
    at the window edge: on 2023-09-21_101840 the box covered less than half of a
    return that is visibly continuous.  This walks the ridge outwards while the
    column keeps a pixel above ``thr`` within ``max_dev`` rows of the running
    centre, and stops at ``gap`` consecutive empty columns (or ``max_ext``).
    It deliberately does not grow rows: only the trace is extended, so the faint
    fan under the arc is still excluded.
    """
    x1, y1, x2, y2 = [int(v) for v in raw]
    H, W = d.shape
    mask = d > thr

    def col_centre(x: int, cy: float):
        lo = max(0, int(round(cy)) - max_dev)
        hi = min(H, int(round(cy)) + max_dev + 1)
        rows = np.nonzero(mask[lo:hi, x])[0]
        if rows.size == 0:
            return None
        w = d[lo:hi, x][rows]
        return float(lo + float((rows * w).sum() / max(w.sum(), 1e-6)))

    cy = float(np.average(np.arange(y1, y2), weights=np.maximum(d[y1:y2, x1:x2].sum(axis=1), 1e-6))) if y2 > y1 else (y1 + y2) / 2.0
    out = list(raw)
    for step, direction in ((1, -1), (1, 1)):
        c = cy
        miss = 0
        x = x1 - 1 if direction < 0 else x2
        moved = 0
        while 0 <= x < W and moved < max_ext:
            nxt = col_centre(x, c)
            if nxt is None:
                miss += 1
                if miss > gap:
                    break
            else:
                miss = 0
                c = 0.7 * c + 0.3 * nxt
                moved += 1
                if direction < 0:
                    out[0] = min(out[0], x)
                else:
                    out[2] = max(out[2], x + 1)
            x += direction
    return out


def detect_arc(img: np.ndarray, prev_center: Optional[tuple] = None, **kw) -> Optional[dict]:
    """One arc in one frame.

    Order matters and was fixed against the 24 hand boxes: threshold at ``lo``
    inside the search window, bridge with a 1 px dilation, take the component
    holding the window's brightest pixel (not the largest one -- the largest is
    usually the faint fan under the arc), shrink the box back by the bridge, then
    apply the margin.  Removing the dilation under-reports the arc by ~2 px a
    side; selecting by area instead of intensity jumps onto the fan.
    """
    p = dict(DEFAULTS); p.update(kw)
    f = img.astype(np.float32)
    d = f - _block_median(f, p["block"])
    med = float(np.median(d))
    sigma = 1.4826 * (float(np.median(np.abs(d - med))) or 1.0)
    H, W = f.shape
    if prev_center is None:
        cy, cx = np.unravel_index(int(np.argmax(f)), f.shape)
        rad = p["win"]
    else:
        cx, cy = int(prev_center[0]), int(prev_center[1])
        rad = p["radius"]
    y0, y1 = max(0, cy - rad), min(H, cy + rad)
    x0, x1 = max(0, cx - rad), min(W, cx + rad)
    sub = np.zeros_like(d, dtype=bool)
    sub[y0:y1, x0:x1] = d[y0:y1, x0:x1] > med + p["lo"] * sigma
    if not sub.any():
        return None
    comps = _components(_dilate(sub, 1))
    if not comps:
        return None
    peak_local = float(f[y0:y1, x0:x1].max())
    best = max(comps, key=lambda c: float(f[c[:, 0], c[:, 1]].max()))
    if float(f[best[:, 0], best[:, 1]].max()) < peak_local * 0.75:
        return None
    ya, xa = best.min(axis=0); yb, xb = best.max(axis=0)
    ya, xa = max(0, int(ya) + 1), max(0, int(xa) + 1)
    yb, xb = int(yb) - 1, int(xb) - 1
    raw = [int(xa), int(ya), int(xb + 1), int(yb + 1)]
    if p["extend"]:
        raw = _extend_ridge(d, med + p["lo"] * sigma, raw)
    box = _pad_box(raw, W, H, p["margin"], p["min_pad"])
    vals = f[best[:, 0], best[:, 1]]
    core = f[raw[1]:raw[3], raw[0]:raw[2]]
    return {
        "box_xyxy": box,
        "raw_box_xyxy": raw,
        "area": int(len(best)),
        "beam_span": int(box[2] - box[0]),
        "row_span": int(box[3] - box[1]),
        "fill": round(float(len(best)) / max(1.0, (raw[2] - raw[0]) * (raw[3] - raw[1])), 3),
        "peak": int(round(float(vals.max()))),
        "snr": round(float((vals.max() - med) / sigma), 2),
        "snr_mean": round(float((vals.mean() - med) / sigma), 2),
        "centroid": [round(float(best[:, 0].mean()), 1), round(float(best[:, 1].mean()), 1)],
        "role": "candidate",
        "structure_overlap": 0.0,
        "rank": 1,
        "score": round(float((vals.max() - med) / sigma) * float(np.sqrt(len(best))), 2),
        "noise": {"median": round(med, 3), "sigma": round(sigma, 3)},
        "core_mean": round(float(core.mean()), 2) if core.size else None,
    }


def analyse(recording: str, frame: int, prev_center: Optional[tuple] = None, **kw) -> dict:
    from engine import geometry as G  # local import: geometry is optional for tests
    from PIL import Image
    rec = G.load_recording(recording, with_meta=False)
    img = np.asarray(Image.open(rec.pgm_path(frame)))
    det = detect_arc(img, prev_center=prev_center, **kw)
    row = {
        "recording": recording, "frame": int(frame), "mode": "arc",
        "category": getattr(rec.spec, "category", None),
        "n_rows": int(img.shape[0]), "n_beams": int(img.shape[1]),
        "range_window_m": list(rec.range_window),
        "bg": {"block": kw.get("block", DEFAULTS["block"]), "mode": "spatial-block-median"},
        "blobs": [] if det is None else [{k: det[k] for k in
                 ("area", "beam_span", "box_xyxy", "centroid", "fill", "peak", "rank", "role",
                  "row_span", "score", "snr", "snr_mean", "structure_overlap")}],
        "arc": None if det is None else {k: det[k] for k in ("raw_box_xyxy", "core_mean", "noise")},
        "provenance": {"engine_version": ENGINE_VERSION, "shape": "arc", "margin": kw.get("margin", DEFAULTS["margin"])},
    }
    return row


def run(recording: str, frames: Iterable[int], out_path: Path, **kw) -> dict:
    rows = []
    prev = None
    hits = 0
    for fr in frames:
        row = analyse(recording, fr, prev_center=prev, **kw)
        if row["blobs"]:
            hits += 1
            b = row["blobs"][0]["box_xyxy"]
            prev = ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)
        rows.append(row)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    return {"n": len(rows), "hits": hits, "out": str(out_path)}


def _frames(spec: str, rec) -> List[int]:
    return [int(x) for x in spec.split(",")] if spec else sorted(rec.frames)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="arc-shaped returns -> proposals.jsonl (arc/v0)")
    ap.add_argument("--recording", required=True)
    ap.add_argument("--frames", default="")
    ap.add_argument("--every", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--margin", type=float, default=DEFAULTS["margin"])
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    from engine import geometry as G
    rec = G.load_recording(a.recording, with_meta=False)
    frames = _frames(a.frames, rec)
    if a.every > 1:
        frames = frames[::a.every]
    if a.limit:
        frames = frames[:a.limit]
    res = run(a.recording, frames, Path(a.out), margin=a.margin)
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
