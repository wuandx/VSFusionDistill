"""Box the whole bright arc, not the brightest knot.

The user (2026-11-12) confirmed the elongated bright arc in these recordings IS
the mortar shell. The compact detector boxes a 5-9 px knot because a 16 px block
median absorbs a 1-2 px wide arc; that box is a fragment. This one keeps the arc:
coarse block-median background -> threshold -> the connected component that
holds the frame's brightest pixel -> bbox of that component.
"""
from __future__ import annotations

import numpy as np


def _block_median(img: np.ndarray, block: int) -> np.ndarray:
    h, w = img.shape
    bh, bw = int(np.ceil(h / block)), int(np.ceil(w / block))
    pad = np.pad(img, ((0, bh * block - h), (0, bw * block - w)), mode="edge")
    tiles = pad.reshape(bh, block, bw, block).transpose(0, 2, 1, 3).reshape(bh, bw, -1)
    med = np.median(tiles, axis=2)
    return np.repeat(np.repeat(med, block, axis=0), block, axis=1)[:h, :w]


def _components(mask: np.ndarray) -> list[np.ndarray]:
    """4-connected components, pure numpy (no scipy on this box)."""
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out = []
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


def _dilate(mask: np.ndarray, r: int = 1) -> np.ndarray:
    out = mask.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dy == 0 and dx == 0:
                continue
            out |= np.roll(np.roll(mask, dy, axis=0), dx, axis=1)
    return out


def arc_box(img: np.ndarray, block: int = 24, snr: float = 4.5, bridge: int = 1,
            min_area: int = 25) -> dict | None:
    f = img.astype(np.float32)
    bg = _block_median(f, block)
    d = f - bg
    med = float(np.median(d))
    mad = float(np.median(np.abs(d - med))) or 1.0
    sigma = 1.4826 * mad
    mask = d > med + snr * sigma
    if mask.sum() < min_area:
        return None
    mask = _dilate(mask, bridge)
    comps = _components(mask)
    if not comps:
        return None
    peak = np.unravel_index(int(np.argmax(f)), f.shape)
    pick = None
    for c in comps:
        if any(abs(int(y) - peak[0]) <= 1 and abs(int(x) - peak[1]) <= 1 for y, x in c):
            pick = c
            break
    if pick is None:
        pick = max(comps, key=len)
    if len(pick) < min_area:
        return None
    y1, x1 = pick.min(axis=0)
    y2, x2 = pick.max(axis=0)
    # the dilation grew the box by `bridge` on each side; pull it back
    y1, x1 = max(0, y1 + bridge), max(0, x1 + bridge)
    y2, x2 = y2 - bridge, x2 - bridge
    vals = f[pick[:, 0], pick[:, 1]]
    return {
        "box": [int(x1), int(y1), int(x2 + 1), int(y2 + 1)],
        "area_px": int(len(pick)),
        "beam_span": int(x2 - x1 + 1),
        "row_span": int(y2 - y1 + 1),
        "peak": float(f[peak]),
        "mean_on_arc": float(vals.mean()),
        "bg_block": block, "snr_thr": snr,
    }
