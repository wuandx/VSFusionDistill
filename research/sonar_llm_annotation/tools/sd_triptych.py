"""Three-way compare: the published JPG, and the SD frames that could be 'the same moment'.

Given an ARIS frame N, the release published gopro/N.jpg.  We measured (by content) which SD frame
that picture actually is -- call it S.  The official matching table would have wanted ARIS N to be
taken at a different index, call it N itself.  Showing both side by side makes the disagreement
visible: same label box, two different moments of the pool.

usage: python -m tools.sd_triptych <recording> <frame> <sd_index> [...] [--out name.png]
"""
from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FF = ROOT / "tools" / "bin" / "ffmpeg-win-x86_64-v9.0.2.exe"
PROCESSED = Path(r"D:\pby\data_processed")
REC_ROOT = Path(r"D:\pby\uxo-full\extracted\recordings")
CAT_DIR = {"100lbs_aircraft_bomb": "100lbs_bomb", "incindiary_grenade": "20lbs_incendiary",
           "mortar_shell": "15cm_mortar"}
W, H = 640, 360


def match_row(recording: str) -> dict | None:
    with open(PROCESSED / "matches.csv", encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            if Path((r.get("aris_file") or "").strip()).name == recording:
                return r
    return None


def grab(clip: Path, index: int) -> Image.Image | None:
    if index < 0:
        return None
    proc = subprocess.run(
        [str(FF), "-hide_banner", "-loglevel", "error", "-i", str(clip),
         "-vf", f"select=eq(n\\,{index}),scale={W}:{H}", "-fps_mode", "passthrough",
         "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    if not proc.stdout:
        return None
    return Image.open(io.BytesIO(proc.stdout)).convert("RGB")


def label_box(rec_dir: Path, frame: int):
    for pad in (4, 5):
        p = rec_dir / "labels" / f"{frame:0{pad}d}.json"
        if p.exists():
            o = json.loads(p.read_text(encoding="utf-8"))
            return (o["x_min"], o["y_min"], o["x_max"], o["y_max"])
    return None


def tile(img, title, box, colour):
    c = Image.new("RGB", (W, H + 30), (248, 248, 248))
    c.paste(img, (0, 30))
    d = ImageDraw.Draw(c)
    d.text((6, 9), title, fill=(15, 15, 15))
    if box:
        d.rectangle([box[0], box[1] + 30, box[2], box[3] + 30], outline=colour, width=2)
    return c


def main(argv: list[str]) -> int:
    args, name, i = [], "sd_triptych.png", 1
    while i < len(argv):
        if argv[i] == "--out":
            name, i = argv[i + 1], i + 2
        else:
            args.append(argv[i]); i += 1
    if len(args) < 3:
        print(__doc__)
        return 2
    recording, frame, sd_ids = args[0], int(args[1]), [int(a) for a in args[2:]]

    row = match_row(recording)
    if row is None:
        raise SystemExit(f"{recording}: no row in matches.csv")
    clip = PROCESSED / (row.get("gopro_file") or "").strip()
    cat = None
    for c, d in CAT_DIR.items():
        if (REC_ROOT / d / recording).exists():
            cat = REC_ROOT / d / recording
    if cat is None:
        raise SystemExit(f"{recording}: no recording directory")

    box = label_box(cat, frame)
    tiles = []
    jpg = cat / "gopro" / f"{frame:04d}.jpg"
    if jpg.exists():
        tiles.append(tile(Image.open(jpg).convert("RGB").resize((W, H), Image.LANCZOS),
                          f"published gopro/{frame:04d}.jpg   (what the release shipped)", box, (220, 30, 30)))
    for s in sd_ids:
        img = grab(clip, s)
        if img is None:
            continue
        tiles.append(tile(img, f"SD n={s}   ({clip.name})", box, (30, 200, 60)))

    sheet = Image.new("RGB", (len(tiles) * (W + 8), H + 30), (232, 232, 232))
    for k, t in enumerate(tiles):
        sheet.paste(t, (k * (W + 8), 0))
    out = ROOT / "out" / name
    sheet.save(out)
    print("wrote", out.relative_to(ROOT), sheet.size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
