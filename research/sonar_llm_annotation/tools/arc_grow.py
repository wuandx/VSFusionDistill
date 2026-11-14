"""Grow the box along a faint trace.

A thin specular arc is 1-3 px wide and fades out at both ends. Thresholding at a
level that keeps it connected also floods into noise elsewhere; keeping the
threshold high clips the ends. So grow the box side by side and ask only "is
there still echo just beyond this edge?" - using the strip's 90th percentile
against the local background, so a few bright pixels are enough to continue.
"""
from __future__ import annotations
import numpy as np


def _strip_p90(d: np.ndarray, ys: slice, xs: slice) -> float:
    seg = d[ys, xs]
    return float(np.percentile(seg, 90)) if seg.size else -1e9


def grow_box(d: np.ndarray, box: list[int], sigma: float, k: float = 1.0,
             step: int = 2, cap: int = 90) -> dict:
    H, W = d.shape
    x1, y1, x2, y2 = box
    grew = {"up": 0, "down": 0, "left": 0, "right": 0}
    for _ in range(cap // step):
        moved = False
        if y1 - step >= 0 and grew["up"] < cap:
            if _strip_p90(d, slice(y1 - step, y1), slice(max(0, x1), min(W, x2))) > k * sigma:
                y1 -= step; grew["up"] += step; moved = True
        if y2 + step <= H and grew["down"] < cap:
            if _strip_p90(d, slice(y2, y2 + step), slice(max(0, x1), min(W, x2))) > k * sigma:
                y2 += step; grew["down"] += step; moved = True
        if x1 - step >= 0 and grew["left"] < cap:
            if _strip_p90(d, slice(max(0, y1), min(H, y2)), slice(x1 - step, x1)) > k * sigma:
                x1 -= step; grew["left"] += step; moved = True
        if x2 + step <= W and grew["right"] < cap:
            if _strip_p90(d, slice(max(0, y1), min(H, y2)), slice(x2, x2 + step)) > k * sigma:
                x2 += step; grew["right"] += step; moved = True
        if not moved:
            break
    return {"box": [int(max(0, x1)), int(max(0, y1)), int(min(W, x2)), int(min(H, y2))],
            "grew": grew}
