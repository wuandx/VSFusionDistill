"""Does the published camera JPG numbered N show the same moment as the label numbered N?

The object is a dark body lying on bright sand, so a box that is really on the object reads darker
than the ring just outside it.  If the JPG for frame N was pulled from a video whose start differs
from the one the labels were drawn on, the box at N lands on empty sand and that contrast collapses.

So: for every sampled frame, apply ITS label box to the image at N+k for k in -K..+K and average the
contrast.  A curve that peaks at k=0 means labels and images agree.  A peak at k=-64 means the image
numbered N actually shows the moment of label N-64 (i.e. the exported JPGs are 64 frames late).

This reads only the published JPGs and label files.  No video decoding.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import geometry as G  # noqa: E402

REC_ROOT = Path(r"D:\pby\uxo-full\extracted\recordings")
CAT_DIR = {"100lbs_aircraft_bomb": "100lbs_bomb", "incindiary_grenade": "20lbs_incendiary",
           "mortar_shell": "15cm_mortar"}
SCALE = 3.0           # labels are 640x360, images are 1920x1080
GREY = (114, 114, 114)


def find(dirpath: Path, frame: int, ext: str) -> Path | None:
    for pad in (4, 5):
        p = dirpath / f"{frame:0{pad}d}{ext}"
        if p.exists():
            return p
    return None


def load_grey(path: Path) -> np.ndarray:
    im = Image.open(path).convert("L")
    return np.asarray(im, dtype=np.float32)


def contrast(img: np.ndarray, box: tuple[float, float, float, float], ring: int = 18) -> float:
    """ring mean minus box mean; positive when the box is darker than its surroundings."""
    h, w = img.shape
    x1, y1, x2, y2 = [int(round(v)) for v in box]
    x1, x2 = max(0, min(x1, x2)), min(w, max(x1, x2))
    y1, y2 = max(0, min(y1, y2)), min(h, max(y1, y2))
    if x2 - x1 < 3 or y2 - y1 < 3:
        return float("nan")
    inner = img[y1:y2, x1:x2]
    ox1, oy1 = max(0, x1 - ring), max(0, y1 - ring)
    ox2, oy2 = min(w, x2 + ring), min(h, y2 + ring)
    outer = img[oy1:oy2, ox1:ox2]
    # ring = outer minus inner, computed on sums so we never build a mask image
    s_out, n_out = float(outer.sum()), outer.size
    s_in, n_in = float(inner.sum()), inner.size
    if n_out == n_in:
        return float("nan")
    ring_mean = (s_out - s_in) / (n_out - n_in)
    return ring_mean - s_in / n_in


def run(recording: str, max_lag: int = 96, step: int = 12, ring: int = 18) -> dict:
    rec = G.load_recording(recording)
    d = REC_ROOT / CAT_DIR[rec.category] / recording
    lab_dir, jpg_dir = d / "labels", d / "gopro"

    labelled = [f for f in sorted(rec.frames) if find(lab_dir, f, ".json") is not None]
    if not labelled:
        print(f"{recording}: no labels")
        return {}
    jpg_frames = {f for f in rec.frames if find(jpg_dir, f, ".jpg") is not None}
    picks = labelled[:: max(1, len(labelled) // step)][:step]

    boxes: dict[int, tuple] = {}
    for f in labelled:
        o = json.loads(find(lab_dir, f, ".json").read_text(encoding="utf-8"))
        boxes[f] = (o["x_min"] * SCALE, o["y_min"] * SCALE, o["x_max"] * SCALE, o["y_max"] * SCALE)

    # cache the images we will touch once
    need = {f + k for f in picks for k in range(-max_lag, max_lag + 1, 8) if f + k in jpg_frames}
    cache: dict[int, np.ndarray] = {}

    def img(frame: int):
        if frame not in cache:
            cache[frame] = load_grey(find(jpg_dir, frame, ".jpg"))
        return cache[frame]

    lags = list(range(-max_lag, max_lag + 1, 8))
    curve = {}
    for k in lags:
        vals = [contrast(img(f + k), boxes[f], ring) for f in picks if f + k in jpg_frames]
        vals = [v for v in vals if v == v]
        curve[k] = (float(np.mean(vals)) if vals else float("nan"), len(vals))

    best = max((v for v in curve.items() if v[1][0] == v[1][0]), key=lambda kv: kv[1][0], default=(0, (float("nan"), 0)))
    at0 = curve.get(0, (float("nan"), 0))[0]
    print(f"{recording}: {len(labelled)} labelled, {len(jpg_frames)} jpg, {len(picks)} sampled "
          f"(n per lag ~{curve[lags[0]][1]})")
    print("   " + "  ".join(f"{k:+d}:{curve[k][0]:5.1f}" for k in lags if curve[k][0] == curve[k][0]))
    print(f"   contrast at lag 0 = {at0:.2f}; best lag {best[0]:+d} = {best[1][0]:.2f}")

    out = ROOT / "out" / f"cam_offset_{recording}.json"
    out.write_text(json.dumps({
        "recording": recording, "n_labelled": len(labelled), "n_jpg": len(jpg_frames),
        "n_sampled": len(picks), "label_scale": SCALE, "ring_px": ring,
        "contrast_by_lag": {str(k): (None if v[0] != v[0] else round(v[0], 3)) for k, v in curve.items()},
        "contrast_at_lag0": None if at0 != at0 else round(at0, 3),
        "best_lag": best[0], "best_contrast": None if best[1][0] != best[1][0] else round(best[1][0], 3),
        "method": ("label boxes of sampled frames applied to the JPG at frame+k; the objective object is "
                   "darker than the sand, so ring_mean-box_mean peaks where the image really shows that "
                   "moment. A peak away from 0 means the published JPGs are offset from their labels."),
        "caveat": ("a flat curve (no clear peak) means this recording's images cannot answer the question "
                   "either way -- do not read it as 'synchronised'."),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("   wrote", out.name)
    return curve


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("-")]
    if not args:
        print("usage: python -m tools.box_offset <recording> [<recording> ...] [--lag 96] [--step 12]")
        return 2
    lag = 96
    step = 12
    for i, a in enumerate(argv):
        if a == "--lag":
            lag = int(argv[i + 1])
        if a == "--step":
            step = int(argv[i + 1])
    for name in args:
        run(name, max_lag=lag, step=step)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
