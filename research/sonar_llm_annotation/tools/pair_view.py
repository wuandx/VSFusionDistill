"""Camera and sonar, same frame, side by side.

Why this exists
---------------
Everything up to now was judged on the sonar panel alone.  The recording carries a GoPro clip and
one LabelMe-style box per labelled frame, so the honest way to look at a candidate is: what did the
camera see at that instant, and what did the sonar see.  They are not registered to each other (no
pose solution survives), so this is NOT a projection -- it is a paired view, frame for frame.

Panel A (left)  : the GoPro frame, with the recorded label box drawn if that frame has one.
Panel B (right) : the sonar frame on the card stretch, with compact candidates drawn.

A recording whose notes.txt says "impossible to match" is exactly a recording where this pairing
should not be trusted; that string is printed on the sheet when present.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import geometry as G  # noqa: E402

REC_ROOT = Path(r"D:\pby\uxo-full\extracted\recordings")
CAT_DIR = {
    "100lbs_aircraft_bomb": "100lbs_bomb",
    "incindiary_grenade": "20lbs_incendiary",
    "mortar_shell": "15cm_mortar",
}

CAM_W = 640          # panel width for the camera image
SONAR_SCALE = 2      # sonar upsample factor


def rec_dir(recording: str) -> Path:
    rec = G.load_recording(recording)
    return REC_ROOT / CAT_DIR[rec.category] / recording


def notes(d: Path) -> list[str]:
    p = d / "notes.txt"
    if not p.exists():
        return []
    return [ln.strip("- ").strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def find_file(folder: Path, frame: int, ext: str) -> Path | None:
    for pad in (4, 5):
        p = folder / f"{frame:0{pad}d}{ext}"
        if p.exists():
            return p
    return None


def build(recording: str, frames: list[int], dst: Path) -> Path:
    d = rec_dir(recording)
    props = {}
    pfile = ROOT / "out" / recording / "proposals.jsonl"
    if pfile.exists():
        for line in pfile.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            props[r["frame"]] = r.get("blobs", [])

    caveats = [n for n in notes(d) if any(k in n.lower() for k in
               ("impossible", "lost", "missing", "could not", "couldn't", "not sure", "bad", "incorrect"))]

    tiles = []
    for f in frames:
        cam_p = find_file(d / "gopro", f, ".jpg")
        son_p = find_file(d / "aris_raw", f, ".pgm")
        if cam_p is None or son_p is None:
            continue
        cam = Image.open(cam_p).convert("RGB")
        cam = cam.resize((CAM_W, int(cam.height * CAM_W / cam.width)), Image.LANCZOS)
        dc = ImageDraw.Draw(cam)
        lab_p = find_file(d / "labels", f, ".json")
        if lab_p is not None:
            lab = json.loads(lab_p.read_text(encoding="utf-8"))
            # label json coordinates are in a 640x360 space, NOT in the 1920x1080 jpg space.
            # See the research repo's tools/check/offset_diagnose.py: "annotation coords are in
            # 640x360 space, scaled x3 to 1920x1080".
            sx = cam.width / 640.0
            sy = cam.height / 360.0
            dc.rectangle([lab["x_min"] * sx, lab["y_min"] * sy, lab["x_max"] * sx, lab["y_max"] * sy],
                         outline=(0, 255, 0), width=2)
            dc.text((4, 4), f"camera f{f}  label {lab['class']}", fill=(0, 255, 0))
        else:
            dc.text((4, 4), f"camera f{f}  (no label)", fill=(255, 180, 0))

        son = G.load_recording(recording)
        arr = np.asarray(Image.open(son_p).convert("L"), dtype=np.float32)
        lo, hi = np.percentile(arr, 0.5), np.percentile(arr, 99.5)
        arr = (np.clip((arr - lo) / max(1e-6, hi - lo), 0, 1) * 255).astype(np.uint8)
        img = Image.fromarray(arr)
        son_img = img.resize((img.width * SONAR_SCALE, img.height * SONAR_SCALE), Image.NEAREST).convert("RGB")
        ds = ImageDraw.Draw(son_img)
        for b in props.get(f, []):
            x0, y0, x1, y1 = b["box_xyxy"]
            ds.rectangle([x0 * SONAR_SCALE, y0 * SONAR_SCALE, x1 * SONAR_SCALE, y1 * SONAR_SCALE],
                         outline=(0, 255, 255), width=1)
        ds.text((4, 4), f"sonar f{f}  n={len(props.get(f, []))}", fill=(0, 255, 255))

        h = max(cam.height, son_img.height)
        tile = Image.new("RGB", (cam.width + 8 + son_img.width, h + 22), (0, 0, 0))
        tile.paste(cam, (0, 22))
        tile.paste(son_img, (cam.width + 8, 22))
        ImageDraw.Draw(tile).text((4, 4), recording, fill=(255, 255, 0))
        if caveats:
            ImageDraw.Draw(tile).text((cam.width + 12, 4), "notes: " + " | ".join(caveats), fill=(255, 80, 80))
        tiles.append(tile)

    if not tiles:
        raise SystemExit("no paired frames found")
    w = max(t.width for t in tiles)
    h = sum(t.height for t in tiles) + 6 * (len(tiles) - 1)
    sheet = Image.new("RGB", (w, h), (0, 0, 0))
    y = 0
    for t in tiles:
        sheet.paste(t, (0, y))
        y += t.height + 6
    sheet.save(dst)
    return dst


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("usage: pair_view.py <recording> <frame,frame,...> [out.png]")
        return 2
    recording = argv[1]
    frames = [int(x) for x in argv[2].split(",") if x.strip()]
    dst = Path(argv[3]) if len(argv) > 3 else ROOT / "tmp" / f"pair_{recording}.png"
    print("wrote", build(recording, frames, dst))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
