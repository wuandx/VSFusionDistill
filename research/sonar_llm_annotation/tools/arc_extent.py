"""Arc extent from a seed that is guaranteed to lie on the arc.

Seed = the brightest pixel inside the tracked box (the box centre can fall in the
gap between the bright core and the faint tail). Then take the connected region
above a low threshold that contains that seed, so the faint ends come along, and
pad by PAD px because a label should not cut the visible return in half.
"""
from __future__ import annotations
import numpy as np
from tools.arc_box import _block_median, _components

PAD = 2


def arc_extent(img: np.ndarray, seed_box: list[int], lo: float = 1.5, win: int = 70) -> dict | None:
    f = img.astype(np.float32)
    bg = _block_median(f, 24)
    d = f - bg
    med = float(np.median(d))
    sigma = 1.4826 * (float(np.median(np.abs(d - med))) or 1.0)
    x1, y1, x2, y2 = seed_box
    inner = f[y1:y2, x1:x2]
    if inner.size == 0:
        return None
    dy, dx = np.unravel_index(int(np.argmax(inner)), inner.shape)
    cy, cx = y1 + int(dy), x1 + int(dx)
    H, W = f.shape
    y0, y_1 = max(0, cy - win), min(H, cy + win)
    xx0, xx1 = max(0, cx - win), min(W, cx + win)
    mask = np.zeros_like(d, dtype=bool)
    mask[y0:y_1, xx0:xx1] = d[y0:y_1, xx0:xx1] > med + lo * sigma
    if not mask[cy, cx]:
        return None
    comps = _components(mask)
    pick = None
    for c in comps:
        if ((c[:, 0] == cy) & (c[:, 1] == cx)).any():
            pick = c
            break
    if pick is None:
        return None
    ya, xa = pick.min(axis=0); yb, xb = pick.max(axis=0)
    return {
        "box": [int(max(0, xa - PAD)), int(max(0, ya - PAD)), int(min(W, xb + 1 + PAD)), int(min(H, yb + 1 + PAD))],
        "seed": [int(cx), int(cy)], "area_px": int(len(pick)), "sigma": round(sigma, 2),
        "peak": float(f[cy, cx]),
    }
