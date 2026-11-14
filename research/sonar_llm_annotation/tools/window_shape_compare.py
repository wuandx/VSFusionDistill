"""Same window, two recordings: is the thing in 110229's near field the same kind of thing as in 110411's?

The presence test counted "a compact return lands in rows 111-152 / beams 43-77" and found it in
21 of 40 recordings, with 110411 the densest.  But "a compact return" is a loose class: a small
23x16 px blob with no tail and a 40x100 px saturated cloud with a vertical streak both count.
This script puts the two side by side on the measurements that separate them.

For every recording asked for, it scans the window rows, picks the strongest blob per frame
(compact detector, default settings), and reports the distribution of:
  beam_span, row_span, peak, snr, and tail_ratio = row_extent_above_p99 / beam_extent_above_p99
A true compact target should be small in both directions; a saturated near-field return shows a
long row-extent (the range tail) relative to its beam extent.
"""
from __future__ import annotations

import json
import statistics as st
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import compact as C  # noqa: E402
from engine import echo as E  # noqa: E402
from engine import geometry as G  # noqa: E402

ROWS = (111, 152)
BEAMS = (43, 77)
RECS = [
    "2023-09-21_110229",
    "2023-09-21_110411",
    "2023-09-21_103728",
    "2023-09-21_124039",
    "2023-09-21_101622",
    "2023-09-21_105856",
]


def tail_ratio(img: np.ndarray, cy: int, cx: int) -> tuple[int, int, float]:
    """Extent of the very bright set in a 61-row/31-beam box around the peak."""
    r0, r1 = max(0, cy - 30), min(img.shape[0], cy + 31)
    c0, c1 = max(0, cx - 15), min(img.shape[1], cx + 16)
    sub = img[r0:r1, c0:c1]
    thr = np.percentile(sub, 99.0)
    m = sub >= thr
    rows = np.nonzero(m.any(axis=1))[0]
    cols = np.nonzero(m.any(axis=0))[0]
    rext = int(rows.max() - rows.min() + 1) if len(rows) else 0
    cext = int(cols.max() - cols.min() + 1) if len(cols) else 0
    return rext, cext, round(rext / max(1, cext), 2)


def main() -> int:
    out = {}
    for rec_name in RECS:
        rec = G.load_recording(rec_name)
        frames = sorted(rec.frames)
        picks = frames[:: max(1, len(frames) // 24)][:24]
        spans, rspans, peaks, snrs, ratios = [], [], [], [], []
        hits = 0
        for f in picks:
            img = E.read_pgm(rec.pgm_path(f))
            blobs = C.detect_compact(img)["blobs"]
            best = None
            for b in blobs:
                r, c = b["centroid"]
                if ROWS[0] <= r <= ROWS[1] and BEAMS[0] <= c <= BEAMS[1] and b["beam_span"] <= 40:
                    if best is None or b["score"] > best["score"]:
                        best = b
            if best is None:
                continue
            hits += 1
            r, c = int(best["centroid"][0]), int(best["centroid"][1])
            rext, cext, ratio = tail_ratio(img.astype(np.float32), r, c)
            spans.append(best["beam_span"])
            rspans.append(best["row_span"])
            peaks.append(int(best["peak"]))
            snrs.append(round(best["snr"], 1))
            ratios.append(ratio)
        out[rec_name] = dict(
            frames_sampled=len(picks), hits=hits,
            beam_span_med=st.median(spans) if spans else None,
            row_span_med=st.median(rspans) if rspans else None,
            peak_med=st.median(peaks) if peaks else None,
            snr_med=st.median(snrs) if snrs else None,
            tail_ratio_med=st.median(ratios) if ratios else None,
        )
        print(f"{rec_name}: hits {hits}/{len(picks)}  "
              f"beam_span {out[rec_name]['beam_span_med']}  row_span {out[rec_name]['row_span_med']}  "
              f"peak {out[rec_name]['peak_med']}  snr {out[rec_name]['snr_med']}  "
              f"tail {out[rec_name]['tail_ratio_med']}", flush=True)

    dst = ROOT / "out" / "window_shape_compare.json"
    dst.write_text(json.dumps({"window": {"rows": ROWS, "beams": BEAMS}, "recordings": out},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
