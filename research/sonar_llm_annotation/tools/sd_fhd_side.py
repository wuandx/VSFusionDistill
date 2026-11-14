"""Put the published camera JPG next to the SD video frames it could have come from.

The release numbered its JPGs by ARIS frame but pulled them out of `clips_fhd`, whose start time
differs from the `clips_sd` the matching table was built on.  This tool shows, for one ARIS frame,
the published JPG and several SD frames around the predicted match, all at the same size and all
carrying the same label box, so the moment can be judged by eye instead of by a statistic.

Nothing is inferred from "the box sits on the object": the camera re-aims, so a wrong moment still
has the target near the box.  The cue that does work is the background -- the pool floor, the board,
the calibration card -- which moves with the platform.

usage: python -m tools.sd_fhd_side <recording> <frame> [<frame> ...] [--out name.png]
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import geometry as G  # noqa: E402

FFMPEG = ROOT / "tools" / "bin" / "ffmpeg-win-x86_64-v9.0.2.exe"
PROCESSED = Path(r"D:\pby\data_processed")
REC_ROOT = Path(r"D:\pby\uxo-full\extracted\recordings")
CAT_DIR = {"100lbs_aircraft_bomb": "100lbs_bomb", "incindiary_grenade": "20lbs_incendiary",
           "mortar_shell": "15cm_mortar"}
W, H = 640, 360          # label coordinate space == SD resolution


def match_row(recording: str) -> dict | None:
    with open(PROCESSED / "matches.csv", encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            if Path((r.get("aris_file") or "").strip()).name == recording:
                return r
    return None


def offset_frames(recording: str) -> int | None:
    p = ROOT / "out" / "sd_fhd_audit.json"
    if not p.exists():
        return None
    for r in json.loads(p.read_text(encoding="utf-8"))["recordings"]:
        if r["recording"] == recording:
            return r.get("offset_frames")
    return None


def grab(clip: Path, index: int) -> Image.Image | None:
    """one frame, by decode-order index, scaled to 640x360."""
    if index < 0:
        return None
    proc = subprocess.run(
        [str(FFMPEG), "-hide_banner", "-loglevel", "error", "-i", str(clip),
         "-vf", f"select=eq(n\\,{index}),scale={W}:{H}", "-fps_mode", "passthrough", "-frames:v", "1",
         "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True)
    if proc.returncode != 0 or not proc.stdout:
        return None
    import io
    return Image.open(io.BytesIO(proc.stdout)).convert("RGB")


def label_box(rec_dir: Path, frame: int) -> tuple | None:
    for pad in (4, 5):
        p = rec_dir / "labels" / f"{frame:0{pad}d}.json"
        if p.exists():
            o = json.loads(p.read_text(encoding="utf-8"))
            return (o["x_min"], o["y_min"], o["x_max"], o["y_max"])
    return None


def published_jpg(rec_dir: Path, frame: int) -> Image.Image | None:
    for pad in (4, 5):
        p = rec_dir / "gopro" / f"{frame:0{pad}d}.jpg"
        if p.exists():
            return Image.open(p).convert("RGB").resize((W, H), Image.LANCZOS)
    return None


def tile(img: Image.Image, title: str, box: tuple | None, note: str = "") -> Image.Image:
    canvas = Image.new("RGB", (W, H + 26), (250, 250, 250))
    canvas.paste(img, (0, 26))
    d = ImageDraw.Draw(canvas)
    d.text((6, 7), title, fill=(20, 20, 20))
    if note:
        d.text((W - 260, 7), note, fill=(180, 40, 20))
    if box:
        d.rectangle([box[0], box[1] + 26, box[2], box[3] + 26], outline=(0, 220, 60), width=2)
    return canvas


def build(recording: str, frames: list[int], out_name: str) -> Path:
    rec = G.load_recording(recording)
    rec_dir = REC_ROOT / CAT_DIR[rec.category] / recording
    row = match_row(recording)
    if row is None:
        raise SystemExit(f"{recording}: no row in matches.csv")
    sd_clip = PROCESSED / (row.get("gopro_file") or "").strip()
    off = offset_frames(recording)
    rows = []
    for f in frames:
        pub = published_jpg(rec_dir, f)
        box = label_box(rec_dir, f)
        base = []
        if pub is not None:
            base.append(tile(pub, f"published gopro/{f:04d}.jpg  (FHD, N={f})", box, "FHD"))
        # SD candidates: the same number, and the number the container offset predicts
        cands = [("same number", f), ("same number + off", None if off is None else f + off)]
        if off is not None:
            cands.append(("one sd frame later", f + off + 1))
        for label, idx in cands:
            if idx is None:
                continue
            img = grab(sd_clip, idx)
            if img is None:
                base.append(tile(Image.new("RGB", (W, H), (30, 30, 30)), f"SD n={idx}", None, "no frame"))
                continue
            base.append(tile(img, f"SD n={idx}  ({label})", box, "SD"))
        rows.append(base)

    cols = max(len(r) for r in rows)
    sheet = Image.new("RGB", (cols * (W + 8), len(rows) * (H + 26 + 8)), (235, 235, 235))
    for ri, r in enumerate(rows):
        for ci, im in enumerate(r):
            sheet.paste(im, (ci * (W + 8), ri * (H + 26 + 8)))
    out = ROOT / "out" / out_name
    sheet.save(out)
    print("wrote", out.relative_to(ROOT), sheet.size)
    return out


def main(argv: list[str]) -> int:
    args, name, i = [], "sd_fhd_side.png", 1
    while i < len(argv):
        if argv[i] == "--out":
            name = argv[i + 1]
            i += 2
        else:
            args.append(argv[i])
            i += 1
    if len(args) < 2:
        print("usage: python -m tools.sd_fhd_side <recording> <frame> [...] [--out name.png]")
        return 2
    build(args[0], [int(a) for a in args[1:]], name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
