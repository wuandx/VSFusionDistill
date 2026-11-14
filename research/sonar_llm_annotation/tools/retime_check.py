"""Put one sonar frame next to the camera frame that really happened then, and move the label with it.

The released JPG for sonar frame f is at SD frame `a*f + b`, not at the simultaneous frame
`a*f + b - offset` (see out/CAMERA-RETIMED.md).  A label drawn on the released JPG therefore describes a
moment |offset| frames away: the object in it sits at a different pixel position than in the simultaneous
frame, because the platform has moved in between.

This tool shows the three things side by side for a handful of frames:
    left   released JPG + its label box (what the operator actually drew)
    right  SD frame at the simultaneous index + the same box translated by the measured shift
and reports the shift it found.  If the shifted box lands on the object, the label survives the retiming,
and the only thing wrong was which frame the picture came from.  If it does not, the label itself is the
problem.

usage: python -m tools.retime_check --recording NAME [--frames 213,301,389] [--n 4]
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import geometry as G  # noqa: E402

FF = ROOT / "tools" / "bin" / "ffmpeg-win-x86_64-v9.0.2.exe"
PROCESSED = Path(r"D:\pby\data_processed")
REC_ROOT = Path(r"D:\pby\uxo-full\extracted\recordings")
CAT = {"100lbs_aircraft_bomb": "100lbs_bomb", "incindiary_grenade": "20lbs_incendiary",
       "mortar_shell": "15cm_mortar"}
W, H = 640, 360
SMALL = (320, 180)


def grab(clip: Path, n: int, fps: float, size: tuple[int, int] = (W, H)) -> Image.Image | None:
    if n < 0:
        return None
    p = subprocess.run([str(FF), "-hide_banner", "-loglevel", "error", "-ss", f"{n / fps:.3f}",
                        "-i", str(clip), "-frames:v", "1", "-vf", f"scale={size[0]}:{size[1]}",
                        "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    if not p.stdout:
        return None
    return Image.open(io.BytesIO(p.stdout)).convert("RGB")


def best_shift(a: np.ndarray, b: np.ndarray, reach: int = 40) -> tuple[int, int, float]:
    """Integer shift (dx, dy) that best aligns a onto b, searching +-reach at half resolution."""
    best, bx, by = -2.0, 0, 0
    h, w = a.shape
    for dy in range(-reach // 2, reach // 2 + 1, 2):
        for dx in range(-reach // 2, reach // 2 + 1, 2):
            y0a, y1a = max(0, dy), min(h, h + dy)
            x0a, x1a = max(0, dx), min(w, w + dx)
            if y1a - y0a < h // 2 or x1a - x0a < w // 2:
                continue
            sub_a = a[y0a - dy:y1a - dy, x0a - dx:x1a - dx]
            sub_b = b[y0a:y1a, x0a:x1a]
            av, bv = sub_a.ravel().astype(np.float32), sub_b.ravel().astype(np.float32)
            av -= av.mean(); bv -= bv.mean()
            d = float(np.sqrt((av * av).sum() * (bv * bv).sum()))
            if not d:
                continue
            c = float((av * bv).sum() / d)
            if c > best:
                best, bx, by = c, dx * 2, dy * 2
    return bx, by, best


def main(argv: list[str]) -> int:
    recording, n_frames, want = None, 4, []
    i = 1
    while i < len(argv):
        if argv[i] == "--recording":
            recording = argv[i + 1]; i += 2
        elif argv[i] == "--n":
            n_frames = int(argv[i + 1]); i += 2
        elif argv[i] == "--frames":
            want = [int(x) for x in argv[i + 1].split(",") if x.strip()]; i += 2
        else:
            i += 1
    if not recording:
        print("need --recording"); return 2

    payload = json.loads((ROOT / "out" / "camera_retimed.json").read_text(encoding="utf-8"))
    rec_fit = next((r for r in payload["recordings"] if r["recording"] == recording), None)
    if rec_fit is None or "a_measured" not in rec_fit:
        print("no verified fit for", recording); return 1
    a, b, off = rec_fit["a_measured"], rec_fit["b"], rec_fit["offset_frames"]
    sd_fps = rec_fit["sd_fps"]
    clip = PROCESSED / "gopro" / "clips_sd" / rec_fit["clip"]

    rec = G.load_recording(recording)
    rd = REC_ROOT / CAT[rec.category] / recording
    frames = sorted(rec.frames)
    if not want:
        lab = sorted(int(p.stem) for p in (rd / "labels").glob("*.json"))
        step = max(1, len(lab) // (n_frames + 1))
        want = [lab[min(step * k, len(lab) - 1)] for k in range(1, n_frames + 1)]

    outdir = ROOT / "out" / "retime_check"
    outdir.mkdir(parents=True, exist_ok=True)
    print(f"{recording}: a={a} b={b} off={off:+d}  clip={clip.name}")
    for f in want:
        lab = rd / "labels" / f"{f:04d}.json"
        jpg = rd / "gopro" / f"{f:04d}.jpg"
        if not lab.exists() or not jpg.exists():
            print(f"  f{f}: missing label or jpg"); continue
        o = json.loads(lab.read_text(encoding="utf-8"))
        box = (o["x_min"], o["y_min"], o["x_max"], o["y_max"])
        rel = int(round(a * f + b))
        sim = int(round(a * f + b - off))
        released = Image.open(jpg).convert("RGB").resize((W, H), Image.LANCZOS)
        sim_img = grab(clip, sim, sd_fps)
        if sim_img is None:
            print(f"  f{f}: no SD frame at {sim}"); continue
        A = np.asarray(released.convert("L").resize(SMALL, Image.LANCZOS), dtype=np.float32)
        B = np.asarray(sim_img.convert("L").resize(SMALL, Image.LANCZOS), dtype=np.float32)
        dx, dy, score = best_shift(A, B)
        box_s = (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)

        def tile(img, title, bx):
            c = Image.new("RGB", (W, H + 34), (248, 248, 248))
            c.paste(img, (0, 34))
            d = ImageDraw.Draw(c)
            d.text((6, 11), title, fill=(15, 15, 15))
            d.rectangle([bx[0], bx[1] + 34, bx[2], bx[3] + 34], outline=(220, 40, 40), width=2)
            return c

        left = tile(released, f"released gopro/{f:04d}.jpg = SD {rel}  (label drawn here)", box)
        right = tile(sim_img, f"SD {sim} = simultaneous with sonar {f}  (box moved {dx:+d},{dy:+d}, ncc {score:.3f})", box_s)
        sheet = Image.new("RGB", (W * 2 + 8, H + 34), (232, 232, 232))
        sheet.paste(left, (0, 0)); sheet.paste(right, (W + 8, 0))
        path = outdir / f"{recording}_f{f:04d}.png"
        sheet.save(path)
        print(f"  f{f}: released SD {rel} -> simultaneous SD {sim}  shift ({dx:+d},{dy:+d}) ncc {score:.3f}  {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
