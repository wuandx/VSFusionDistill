"""Is the camera annotation on the same instant as the sonar frame with the same number?

The gantry file is indexed by sonar frame and records where the platform actually was.  The camera
box moves in the image as the platform moves.  So if label k really belongs to sonar frame k, the
box-centre sequence and the platform position sequence should line up at lag 0.  If the label was
drawn on a different moment (a few frames earlier or later), the best alignment moves.

This prints the correlation at every lag from -30 to +30 and names the best one.  It says nothing
about absolute synchronisation of the two devices -- only whether the labels line up with the frame
numbers they are stored under.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import geometry as G  # noqa: E402

REC_ROOT = Path(r"D:\pby\uxo-full\extracted\recordings")
CAT_DIR = {"100lbs_aircraft_bomb": "100lbs_bomb", "incindiary_grenade": "20lbs_incendiary",
           "mortar_shell": "15cm_mortar"}


def find(path: Path, frame: int, ext: str) -> Path | None:
    for pad in (4, 5):
        p = path / f"{frame:0{pad}d}{ext}"
        if p.exists():
            return p
    return None


def run(recording: str, max_lag: int = 30) -> None:
    rec = G.load_recording(recording)
    d = REC_ROOT / CAT_DIR[rec.category] / recording

    gantry = {}
    with open(d / "gantry.csv", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            try:
                gantry[int(row["aris_frame_idx"])] = (float(row["x"]), float(row["y"]))
            except (KeyError, ValueError):
                continue

    frames, bx, by = [], [], []
    for f in sorted(rec.frames):
        lp = find(d / "labels", f, ".json")
        if lp is None:
            continue
        o = json.loads(lp.read_text(encoding="utf-8"))
        frames.append(f)
        bx.append((o["x_min"] + o["x_max"]) / 2.0 * 3.0)   # 640x360 -> 1920x1080
        by.append((o["y_min"] + o["y_max"]) / 2.0 * 3.0)

    bx = np.array(bx)
    by = np.array(by)
    # platform position sampled on the same frames, split into the two image axes by fitting a
    # 2D similarity: the image displacement of a static object is *opposite* to platform motion.
    g = np.array([gantry.get(f, (np.nan, np.nan)) for f in frames])
    ok = ~np.isnan(g[:, 0])
    if ok.sum() < 30:
        print(f"{recording}: only {ok.sum()} frames with both label and gantry, skip")
        return

    # reference signal: platform travel projected on its principal direction
    gc = g[ok] - g[ok].mean(axis=0)
    u, s, vt = np.linalg.svd(gc, full_matrices=False)
    travel = gc @ vt[0]

    def corr_at(lag: int) -> float:
        if lag >= 0:
            a = bx[ok][lag:]
            b = travel[: len(travel) - lag] if lag else travel
        else:
            a = bx[ok][:len(travel) + lag]
            b = travel[-lag:]
        if len(a) < 20:
            return float("nan")
        if np.std(a) < 1e-6 or np.std(b) < 1e-6:
            return float("nan")
        return float(np.corrcoef(a, b)[0, 1])

    lags = list(range(-max_lag, max_lag + 1))
    cs = [corr_at(k) for k in lags]
    finite = [(abs(c), k, c) for k, c in zip(lags, cs) if c == c]
    finite.sort(reverse=True)
    best = finite[0] if finite else (0, 0, float("nan"))

    print(f"{recording}: n={int(ok.sum())} labelled+plotted frames, box x sd={bx.std():.1f} px, "
          f"platform travel sd={travel.std():.3f} m")
    print(f"   r at lag 0 = {corr_at(0):+.3f}")
    print(f"   best |r| at lag {best[1]:+d} = {best[2]:+.3f}   "
          f"(n neighbours: {', '.join(f'{k:+d}:{c:+.2f}' for c in cs[27:34] for k in [lags[cs.index(c)]] if c == c)})")

    out = ROOT / "out" / f"label_sync_{recording}.json"
    out.write_text(json.dumps({
        "recording": recording, "n": int(ok.sum()),
        "r_lag0": round(corr_at(0), 4), "best_lag": best[1], "best_r": round(best[2], 4),
        "lags": lags, "r_by_lag": [None if c != c else round(c, 4) for c in cs],
        "note": ("compares label box centre x with platform travel along its principal direction; a peak "
                 "away from lag 0 means the label was drawn on a different moment than the frame number "
                 "it is stored under. It does not prove the two devices were hardware-synchronised."),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("   wrote", out.name)


def main(argv: list[str]) -> int:
    for name in argv[1:]:
        run(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
