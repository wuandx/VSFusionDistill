"""Box the bright arc, frame to frame, staying on the same feature.

Plain thresholding jumps between features: on 105230 the arc sits near (40, 255)
for frames 247-665 and then the peak moves to the 1.85 m band at f735/f876. A
human annotator would follow the arc he is labelling. This does the same: each
frame searches a window around the previous box's centre, so the series is a
track, not twelve independent argmaxes.
"""
from __future__ import annotations
import numpy as np
from tools.arc_box import _block_median, _components, _dilate


def _hyst_in_window(f, d, s, med, y0, y1, x0, x1, lo=2.2, hi=6.0, bridge=1):
    sub = np.zeros_like(d, dtype=bool)
    sub[y0:y1, x0:x1] = d[y0:y1, x0:x1] > med + lo * s
    if not sub.any():
        return None
    m = _dilate(sub, bridge)
    comps = _components(m)
    peak_local = float(f[y0:y1, x0:x1].max())
    best = max(comps, key=lambda c: float(f[c[:, 0], c[:, 1]].max()))
    if float(f[best[:, 0], best[:, 1]].max()) < peak_local * 0.75:
        return None
    y1b, x1b = best.min(axis=0); y2b, x2b = best.max(axis=0)
    y1b, x1b = max(0, y1b + bridge), max(0, x1b + bridge)
    y2b, x2b = y2b - bridge, x2b - bridge
    return dict(box=[int(x1b), int(y1b), int(x2b + 1), int(y2b + 1)],
                span=[int(x2b - x1b + 1), int(y2b - y1b + 1)],
                peak=float(f[best[:, 0], best[:, 1]].max()),
                mean=float(f[best[:, 0], best[:, 1]].mean()))


def track_boxes(frames, radius=40, seed_center=None):
    out = {}
    prev = seed_center
    for fr, a in frames:
        f = a.astype(np.float32)
        d = f - _block_median(f, 24)
        med = float(np.median(d)); s = 1.4826 * float(np.median(np.abs(d - med)) or 1.0)
        h, w = f.shape
        if prev is None:
            cy, cx = np.unravel_index(int(np.argmax(f)), f.shape)
        else:
            cy, cx = int(prev[1]), int(prev[0])
        y0, y1 = max(0, cy - radius), min(h, cy + radius)
        x0, x1 = max(0, cx - radius), min(w, cx + radius)
        got = _hyst_in_window(f, d, s, med, y0, y1, x0, x1)
        if got is None:
            out[fr] = None
            continue
        b = got["box"]
        prev = ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)
        out[fr] = got
    return out
