"""Do the sonar candidate and the camera box move together?

If the camera and the sonar are rigidly mated and the head is not re-aimed, the target's bearing
in the camera (box x) and its beam in the sonar should move together over a traverse.  This asks
that question per recording, using only frames that have both a label and a candidate, and reports
it as a correlation -- not as a registration.

Two bearings are compared:
  cam_x  : label box centre x, as an angle from the image centre (atan((x - cx) / f))
  beam   : sonar candidate beam, as an angle about the fan centre (unvalidated FOV, 130 deg)

A strong |r| would mean the two views co-move.  A weak one means either the mated rig is not what
we think, or the candidate we picked is not the target.
"""
from __future__ import annotations

import json
import math
import statistics as st
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import geometry as G  # noqa: E402

REC_ROOT = Path(r"D:\pby\uxo-full\extracted\recordings")
CAT_DIR = {"100lbs_aircraft_bomb": "100lbs_bomb", "incindiary_grenade": "20lbs_incendiary",
           "mortar_shell": "15cm_mortar"}
CX, CY, F = 960.0, 540.0, 1473.0   # GoPro Linear 1920x1080, focal from the deprecated projection tool constants
FOV_DEG = 130.0


def find(path: Path, frame: int, ext: str) -> Path | None:
    for pad in (4, 5):
        p = path / f"{frame:0{pad}d}{ext}"
        if p.exists():
            return p
    return None


def main(recording: str) -> int:
    rec = G.load_recording(recording)
    d = REC_ROOT / CAT_DIR[rec.category] / recording
    props = {}
    for line in (ROOT / "out" / recording / "proposals.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r.get("blobs"):
            props[r["frame"]] = r["blobs"][0]     # rank 1 by score

    cam_a, son_a, frames = [], [], []
    for f in sorted(props):
        lp = find(d / "labels", f, ".json")
        if lp is None:
            continue
        lab = json.loads(lp.read_text(encoding="utf-8"))
        # label json coordinates live in a 640x360 space (see docs/DECISIONS.md D9); CX is in
        # 1920x1080 pixels, so the box centre has to be scaled before it means anything.
        cxx = (lab["x_min"] + lab["x_max"]) / 2.0 * 3.0
        cam_a.append(math.degrees(math.atan((cxx - CX) / F)))
        beam = props[f]["centroid"][1]
        son_a.append((beam - 64.0) * FOV_DEG / 128.0)
        frames.append(f)

    if len(frames) < 10:
        print(f"{recording}: only {len(frames)} paired frames, skip")
        return 0
    a = np.array(cam_a)
    b = np.array(son_a)
    r = float(np.corrcoef(a, b)[0, 1])
    # a slope is only meaningful if there is spread in both
    slope = float(np.polyfit(a, b, 1)[0]) if a.std() > 0.05 else float("nan")
    print(f"{recording}: n={len(frames)}  cam_angle sd={a.std():.2f} deg  sonar_angle sd={b.std():.2f} deg  "
          f"r={r:+.3f}  slope={slope:+.2f}")
    print(f"   cam range {a.min():+.2f}..{a.max():+.2f} deg   sonar range {b.min():+.2f}..{b.max():+.2f} deg")
    out = ROOT / "out" / f"co_motion_{recording}.json"
    out.write_text(json.dumps({
        "recording": recording, "n": len(frames), "r": round(r, 4), "slope": round(slope, 3),
        "cam_angle_sd_deg": round(float(a.std()), 3), "sonar_angle_sd_deg": round(float(b.std()), 3),
        "caveat": ("paired view only; no registration. camera focal 1473.05 px and sonar FOV 130 deg are "
                   "both assumptions, and the FOV was never validated (see DECISIONS D6). A weak r means "
                   "'these two did not co-move', not 'the rig is wrong'."),
        "pairs": [{"frame": f, "cam_deg": round(x, 3), "sonar_deg": round(y, 3)}
                  for f, x, y in zip(frames, cam_a, son_a)],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: co_motion.py <recording> [recording...]")
        raise SystemExit(2)
    for name in sys.argv[1:]:
        main(name)
