"""How healthy is the camera side of one recording, and does the label survive being moved to the true moment?

Three numbers per recording, all measured from the released files:
  coverage   how many frames have a label, over which span, biggest gap
  box        size / centre drift / contrast of the labelled patch against its surroundings
  transfer   for sampled frames, whether the labelled patch can still be found in the simultaneous
             frame (local search around the moved box). High correlation means the object is visible in
             both moments and the label survives the retiming; low means it left the view or changed.

usage: python -m tools.camera_health --recording NAME [--n 6]
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import geometry as G  # noqa: E402

FF = ROOT / "tools" / "bin" / "ffmpeg-win-x86_64-v9.0.2.exe"
PROCESSED = Path(r"D:\pby\data_processed")
REC_ROOT = Path(r"D:\pby\uxo-full\extracted\recordings")
CAT = {"100lbs_aircraft_bomb": "100lbs_bomb", "incindiary_grenade": "20lbs_incendiary",
       "mortar_shell": "15cm_mortar"}
W, H = 640, 360
K = 3  # labels are 640x360 space


def grab(clip: Path, n: int, fps: float) -> np.ndarray | None:
    if n < 0:
        return None
    p = subprocess.run([str(FF), "-hide_banner", "-loglevel", "error", "-ss", f"{n / fps:.3f}",
                        "-i", str(clip), "-frames:v", "1", "-vf", f"scale={W}:{H}",
                        "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    if not p.stdout:
        return None
    return np.asarray(Image.open(io.BytesIO(p.stdout)).convert("L"), dtype=np.float32)


def ncc(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(np.float32); b = b.astype(np.float32)
    a = a - a.mean(); b = b - b.mean()
    d = float(np.sqrt((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / d) if d else 0.0


def main(argv: list[str]) -> int:
    recording, n = None, 6
    i = 1
    while i < len(argv):
        if argv[i] == "--recording":
            recording = argv[i + 1]; i += 2
        elif argv[i] == "--n":
            n = int(argv[i + 1]); i += 2
        else:
            i += 1
    payload = json.loads((ROOT / "out" / "camera_retimed.json").read_text(encoding="utf-8"))
    fit = next((r for r in payload["recordings"] if r["recording"] == recording), None)
    if fit is None or "a_measured" not in fit:
        print("no fit"); return 1
    a, b, off, sd_fps = fit["a_measured"], fit["b"], fit["offset_frames"], fit["sd_fps"]
    clip = PROCESSED / "gopro" / "clips_sd" / fit["clip"]

    rec = G.load_recording(recording)
    rd = REC_ROOT / CAT[rec.category] / recording
    lab_files = sorted(int(p.stem) for p in (rd / "labels").glob("*.json"))
    frames = sorted(rec.frames)
    span = (lab_files[0], lab_files[-1]) if lab_files else (None, None)
    gaps = [b2 - b1 for b1, b2 in zip(lab_files, lab_files[1:]) if b2 - b1 > 1]
    print(f"== {recording}  frames {frames[0]}..{frames[-1]} (n={len(frames)})")
    print(f"   labels {len(lab_files)}  span {span}  gaps>1: {len(gaps)} max gap {max(gaps) if gaps else 0}")

    boxes, centres, contrasts = [], [], []
    for f in lab_files:
        o = json.loads((rd / "labels" / f"{f:04d}.json").read_text(encoding="utf-8"))
        x0, y0 = o["x_min"] * K, o["y_min"] * K
        x1, y1 = o["x_max"] * K, o["y_max"] * K
        boxes.append((x1 - x0, y1 - y0))
        centres.append(((x0 + x1) / 2, (y0 + y1) / 2))
    if boxes:
        w_, h_ = np.array(boxes).T
        cx, cy = np.array(centres).T
        print(f"   box w {w_.min():.0f}..{w_.max():.0f} (med {np.median(w_):.0f})  "
              f"h {h_.min():.0f}..{h_.max():.0f} (med {np.median(h_):.0f})")
        print(f"   centre drift: x {cx.min():.0f}..{cx.max():.0f} sd {cx.std():.1f}  "
              f"y {cy.min():.0f}..{cy.max():.0f} sd {cy.std():.1f}")

    sample = lab_files[:: max(1, len(lab_files) // n)][:n]
    rows = []
    for f in sample:
        o = json.loads((rd / "labels" / f"{f:04d}.json").read_text(encoding="utf-8"))
        x0, y0 = o["x_min"], o["y_min"]
        x1, y1 = o["x_max"], o["y_max"]
        rel_img = (rd / "gopro" / f"{f:04d}.jpg")
        if not rel_img.exists():
            continue
        R = np.asarray(Image.open(rel_img).convert("L").resize((W, H), Image.LANCZOS), dtype=np.float32)
        sx, sy = W / 640.0, H / 360.0
        x0, y0, x1, y1 = x0 * sx, y0 * sy, x1 * sx, y1 * sy
        sim = int(round(a * f + b - off))
        S = grab(clip, sim, sd_fps)
        if S is None:
            continue
        patch = R[int(y0):int(y1), int(x0):int(x1)]
        if patch.size == 0:
            continue
        best, bdx, bdy = -2.0, 0, 0
        for dy in range(-90, 91, 6):
            for dx in range(-140, 141, 6):
                yy0, yy1 = int(y0) + dy, int(y1) + dy
                xx0, xx1 = int(x0) + dx, int(x1) + dx
                if yy0 < 0 or xx0 < 0 or yy1 > H or xx1 > W:
                    continue
                c = ncc(patch, S[yy0:yy1, xx0:xx1])
                if c > best:
                    best, bdx, bdy = c, dx, dy
        ring = R[max(0, int(y0) - 40):int(y1) + 40, max(0, int(x0) - 40):int(x1) + 40]
        contrasts.append(float(patch.mean() - ring.mean()))
        rows.append((f, sim, best, bdx, bdy))
        print(f"   f{f:4d}  released->sim SD {sim:4d}  patch found at ({bdx:+4d},{bdy:+4d})  ncc {best:.3f}")
    if rows:
        v = [r[2] for r in rows]
        print(f"   transfer ncc: min {min(v):.3f} med {np.median(v):.3f}  "
              f"(box vs surroundings: {np.mean(contrasts):+.1f} grey)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
