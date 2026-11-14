"""Camera apparent size vs sonar range: the one pairing test that does not need a registration.

Bearing is dead -- the head is re-aimed at the target, so the camera bearing barely moves (sd 0.2 deg
over a whole traverse) while the sonar beam swings tens of degrees.  There is no leverage there.

Range is different.  The sonar's range axis is the one thing measured in metres (`row -> WindowStart +
row * res`), and the camera's apparent size of a rigid object scales as 1/distance.  So if the sonar
candidate is the object the camera sees, then as the object gets closer in the camera (taller box),
the sonar candidate should sit at a *smaller* row.

That is a falsifiable prediction with no calibration, no projection and no FOV:
  r(row, 1/box_height)  should be clearly positive      (equivalently r(row, box_height) clearly negative)

Reported per recording, plus the same correlation against a shuffled control so the reader can see
what "no tracking" looks like on the same data.
"""
from __future__ import annotations

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
WS = 0.6949353218078613
RES = 2.326396942138672 / 780.0


def find(path: Path, frame: int, ext: str) -> Path | None:
    for pad in (4, 5):
        p = path / f"{frame:0{pad}d}{ext}"
        if p.exists():
            return p
    return None


def run(recording: str) -> dict | None:
    rec = G.load_recording(recording)
    d = REC_ROOT / CAT_DIR[rec.category] / recording
    pfile = ROOT / "out" / recording / "proposals.jsonl"
    if not pfile.exists():
        print(f"{recording}: no proposals, skip")
        return None

    rows, heights, frames = [], [], []
    for line in pfile.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if not r.get("blobs"):
            continue
        lp = find(d / "labels", r["frame"], ".json")
        if lp is None:
            continue
        lab = json.loads(lp.read_text(encoding="utf-8"))
        rows.append(r["blobs"][0]["centroid"][0])
        # label coords are 640x360 (docs/DECISIONS.md D9); the box *height* is scale-invariant but
        # converting to 1920x1080 here keeps the two panels talking in the same units.
        heights.append((lab["y_max"] - lab["y_min"]) * 3.0)
        frames.append(r["frame"])

    if len(frames) < 30:
        print(f"{recording}: only {len(frames)} paired frames, skip")
        return None

    a = np.array(rows, dtype=float)
    h = np.array(heights, dtype=float)
    inv = 1.0 / h
    r_inv = float(np.corrcoef(a, inv)[0, 1])
    rng = np.random.default_rng(0)
    shuffled = np.array([float(np.corrcoef(a, rng.permutation(inv))[0, 1]) for _ in range(200)])

    print(f"{recording}: n={len(frames)}  row {a.min():.0f}-{a.max():.0f} (sd {a.std():.1f})  "
          f"box_h {h.min():.0f}-{h.max():.0f} (sd {h.std():.1f})")
    band = abs(float(shuffled.mean())) + 1.645 * float(shuffled.std())
    print(f"   r(row, 1/h) = {r_inv:+.3f}   shuffled control mean {shuffled.mean():+.3f} "
          f"p95 |{band:.3f}|")
    print(f"   implied range {WS + a.min() * RES:.2f}-{WS + a.max() * RES:.2f} m")

    out = dict(recording=recording, n=len(frames), r_row_inv_h=round(r_inv, 4),
               control_mean=round(float(shuffled.mean()), 4), control_sd=round(float(shuffled.std()), 4),
               row_min=int(a.min()), row_max=int(a.max()), box_h_min=int(h.min()), box_h_max=int(h.max()),
               note=("1/h is only proportional to distance if the camera zoom is fixed and the object is "
                     "rigid. Neither is recorded anywhere, so a positive r is consistent with tracking, "
                     "not proof of it; a near-zero r is evidence against the candidate being the object."))
    (ROOT / "out" / f"range_pair_{recording}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main(argv: list[str]) -> int:
    for name in argv[1:]:
        run(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
