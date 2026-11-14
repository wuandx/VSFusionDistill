"""Label margin around the bright segment.

Two ways to make the box cover "the whole arc" were tried and rejected because
they are unstable on this data: lowering the threshold until the faint ends join
up also joins the noise (a 22x22 box became 128x174), and growing each side by
the strip's 90th percentile runs away as soon as the box gets wide enough to
include background. So the box is the visible bright segment plus a uniform
margin, and the margin is a stated rule rather than a per-frame guess.
"""
from __future__ import annotations

SCALE = 1.3
MIN_PAD = 2


def pad_box(box: list[int], w: int, h: int, scale: float = SCALE, min_pad: int = MIN_PAD) -> list[int]:
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    bw, bh = (x2 - x1), (y2 - y1)
    nw = max(bw * scale, bw + 2 * min_pad)
    nh = max(bh * scale, bh + 2 * min_pad)
    return [int(round(max(0, cx - nw / 2))), int(round(max(0, cy - nh / 2))),
            int(round(min(w, cx + nw / 2))), int(round(min(h, cy + nh / 2)))]
