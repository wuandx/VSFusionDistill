"""Carry a camera label box from the published JPEG onto the retimed SD frame.

Why the box is in the wrong place
---------------------------------
`labels/<frame>.json` was drawn on the published `gopro/<frame>.jpg`.  That JPEG shows an
earlier moment than the sonar frame it is named after (`out/CAMERA-RETIMED.md`: the release
cut the FHD clips with indices matched on the SD clips).  When the review panel shows the
correctly-timed SD frame, the label no longer sits on the object.

What this does
--------------
Starts from the SD frame the release actually used (there the label IS correct), takes a
small patch around the box centre, and follows that patch frame by frame to the SD frame
that is simultaneous with the sonar frame.

Two decisions that came out of measurement, not preference
----------------------------------------------------------
* **The template is never refreshed.**  Refreshing made the track drift onto water: five
  frames gave round-trip errors of 47-214 cache px, while the same runs with a fixed anchor
  came home within 1-5 px.
* **Every result must round-trip.**  Track forward, then take the patch at the end and track
  it back; a drifted track does not return to the label centre.  Only tracks that come home
  are reported as usable.

It is a *translation* track of one small patch.  It says "the patch you boxed is here now",
not "this is the object's silhouette", and a failed track returns ok=false with the reason
instead of a plausible-looking wrong box.

usage
-----
    python -m tools.cam_track --recording 2023-09-21_105230 --frame 400 --shot tmp/t400.png
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
INDEX = OUT / "camera_retimed_index.csv"
SD_CACHE = OUT / "camera_sd"
REC_ROOT = Path(r"D:\pby\uxo-full\extracted\recordings")
CAT_DIR = {
    "100lbs_aircraft_bomb": "100lbs_bomb",
    "incindiary_grenade": "20lbs_incendiary",
    "mortar_shell": "15cm_mortar",
}

PATCH = 28            # template edge, cache pixels (cache is 960 wide, so 2x at FHD)
SEARCH = 9            # +/- per step, cache pixels
MIN_MEAN_NCC = 0.80   # mean step correlation
MAX_ROUND_TRIP = 6.0  # cache px; beyond this the track is treated as drifted
MAX_SHIFT_FHD = 200.0 # a shell resting on the floor does not cross the frame in 5 s


def load_index(recording: str) -> dict[int, dict]:
    rows: dict[int, dict] = {}
    with open(INDEX, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["recording"] != recording:
                continue
            rows[int(r["aris_frame"])] = {
                "sim": int(r["sd_simultaneous"]),
                "rel": int(r["sd_released"]),
                "in_clip": int(r["in_clip"]),
                "tier": r["tier"],
            }
    return rows


_GRAY_CACHE: dict[str, np.ndarray] = {}


def gray(path: Path) -> np.ndarray:
    """Decoded frame, cached. A track reads each frame twice (forward, then back)."""
    key = str(path)
    hit = _GRAY_CACHE.get(key)
    if hit is None:
        with Image.open(path) as im:
            hit = np.asarray(im.convert("L"), dtype=np.float32)
        _GRAY_CACHE[key] = hit
    return hit


def find_category(recording: str) -> str | None:
    """Which class directory holds this recording (the panels do not always know)."""
    for cat, d in CAT_DIR.items():
        if (REC_ROOT / d / recording / "labels").is_dir():
            return cat
    return None


def label_path(recording: str, frame: int, category: str | None = None) -> Path:
    cat = category or find_category(recording)
    if not cat:
        return REC_ROOT / "_unknown_" / recording / "labels" / f"{frame:04d}.json"
    return REC_ROOT / CAT_DIR[cat] / recording / "labels" / f"{frame:04d}.json"


def label_centre(recording: str, frame: int, category: str | None = None) -> tuple[float, float] | None:
    p = label_path(recording, frame, category or find_category(recording) or "")
    if not p.is_file():
        return None
    o = json.loads(p.read_text(encoding="utf-8"))
    # label JSON is 640x360; the cache is 960 wide (half of FHD) => 1.5x the label space
    return ((o["x_min"] + o["x_max"]) / 2 * 1.5, (o["y_min"] + o["y_max"]) / 2 * 1.5)


def ncc_at(img: np.ndarray, tpl: np.ndarray, cx: float, cy: float, search: int) -> tuple[float, int, int]:
    """Best NCC of tpl inside img near (cx, cy). Returns (ncc, dx, dy)."""
    h, w = tpl.shape
    r = h // 2
    x0, y0 = int(round(cx)) - r, int(round(cy)) - r
    th = tpl - tpl.mean()
    tn = np.sqrt((th * th).sum()) + 1e-6

    def score(dx: int, dy: int) -> float:
        yy, xx = y0 + dy, x0 + dx
        if yy < 0 or xx < 0 or yy + h > img.shape[0] or xx + w > img.shape[1]:
            return -2.0
        patch = img[yy:yy + h, xx:xx + w]
        ph = patch - patch.mean()
        return float((th * ph).sum() / (tn * (np.sqrt((ph * ph).sum()) + 1e-6)))

    # coarse lattice (step 3) then refine +-3 around the winner: ~100 evaluations instead of
    # (2*search+1)^2 = 361, and on this data it lands on the same pixel
    best = (-2.0, 0, 0)
    for dy in range(-search, search + 1, 3):
        for dx in range(-search, search + 1, 3):
            c = score(dx, dy)
            if c > best[0]:
                best = (c, dx, dy)
    c0, bx, by = best
    for dy in range(by - 3, by + 4):
        for dx in range(bx - 3, bx + 4):
            c = score(dx, dy)
            if c > best[0]:
                best = (c, dx, dy)
    return best


def _chain(cache: Path, path_idx: list[int], start: int, end: int,
           centre: tuple[float, float], tpl: np.ndarray) -> tuple[float, float, list[float]]:
    order = path_idx if end >= start else list(reversed(path_idx))
    x, y = centre
    nccs: list[float] = []
    for k in [i for i in order if i != start]:
        img = gray(cache / f"{k:04d}.jpg")
        c, dx, dy = ncc_at(img, tpl, x, y, SEARCH)
        nccs.append(round(c, 3))
        x += dx
        y += dy
    return x, y, nccs


def track(recording: str, frame: int, category: str | None = None) -> dict:
    row = load_index(recording).get(frame)
    if row is None:
        return {"ok": False, "reason": "no_retime_row", "frame": frame}
    if row["in_clip"] != 1:
        return {"ok": False, "reason": "outside_sd_clip", "frame": frame}
    c0 = label_centre(recording, frame, category)
    if c0 is None:
        return {"ok": False, "reason": "no_label", "frame": frame}

    cache = SD_CACHE / recording
    start, end = row["rel"], row["sim"]
    have = sorted(int(p.stem) for p in cache.glob("*.jpg"))
    lo, hi = min(start, end), max(start, end)
    path_idx = [i for i in have if lo <= i <= hi]
    if start not in path_idx or end not in path_idx:
        return {"ok": False, "reason": "sd_slot_missing", "frame": frame}

    r = PATCH // 2
    img0 = gray(cache / f"{start:04d}.jpg")
    if not (r <= c0[0] < img0.shape[1] - r and r <= c0[1] < img0.shape[0] - r):
        return {"ok": False, "reason": "label_outside_frame", "frame": frame}
    anchor = img0[int(c0[1]) - r:int(c0[1]) + r, int(c0[0]) - r:int(c0[0]) + r].copy()

    x1, y1, nccs = _chain(cache, path_idx, start, end, c0, anchor)
    img1 = gray(cache / f"{end:04d}.jpg")
    p1 = img1[int(y1) - r:int(y1) + r, int(x1) - r:int(x1) + r].copy()
    bx, by, back_nccs = _chain(cache, path_idx, end, start, (x1, y1), p1)
    round_trip = float(np.hypot(bx - c0[0], by - c0[1]))

    mean_ncc = float(np.mean(nccs)) if nccs else 0.0
    shift_cache = [round(x1 - c0[0], 2), round(y1 - c0[1], 2)]
    shift_fhd = [round(shift_cache[0] * 2.0, 1), round(shift_cache[1] * 2.0, 1)]
    drift = max(abs(shift_fhd[0]), abs(shift_fhd[1]))

    ok = bool(nccs) and mean_ncc >= MIN_MEAN_NCC and round_trip <= MAX_ROUND_TRIP and drift <= MAX_SHIFT_FHD
    reason = ""
    if not ok:
        if not nccs:
            reason = "no_steps"
        elif drift > MAX_SHIFT_FHD:
            reason = "implausible_shift"
        elif mean_ncc < MIN_MEAN_NCC:
            reason = "low_ncc"
        else:
            reason = "round_trip_failed"

    return {
        "ok": ok,
        "reason": reason,
        "recording": recording,
        "frame": frame,
        "sd_from": start,
        "sd_to": end,
        "n_steps": len(nccs),
        "shift_px_cache": shift_cache,
        "shift_px_fhd": shift_fhd,
        "start_centre_cache": [round(c0[0], 2), round(c0[1], 2)],
        "end_centre_cache": [round(x1, 2), round(y1, 2)],
        "ncc_mean": round(mean_ncc, 3),
        "ncc_min": round(min(nccs), 3) if nccs else None,
        "round_trip_px_cache": round(round_trip, 2),
        "method": "anchor+roundtrip",
    }


def shot(recording: str, frame: int, category: str, res: dict, path: Path) -> None:
    """Left: published frame, label where it was drawn. Right: simultaneous frame, box moved."""
    row = load_index(recording)[frame]
    cache = SD_CACHE / recording
    a = Image.open(cache / f"{row['rel']:04d}.jpg").convert("RGB")
    b = Image.open(cache / f"{row['sim']:04d}.jpg").convert("RGB")
    bx = json.loads(label_path(recording, frame, category).read_text(encoding="utf-8"))
    scale = a.width / 640.0

    out = Image.new("RGB", (a.width * 2 + 8, a.height + 26), (16, 16, 16))
    out.paste(a, (0, 26))
    out.paste(b, (a.width + 8, 26))
    d = ImageDraw.Draw(out)

    def rect(ox: int, dx: float, dy: float, colour: tuple[int, int, int]) -> None:
        d.rectangle([bx["x_min"] * scale + ox + dx, bx["y_min"] * scale + dy + 26,
                     bx["x_max"] * scale + ox + dx, bx["y_max"] * scale + dy + 26],
                    outline=colour, width=3)

    rect(0, 0, 0, (120, 220, 120))
    dx, dy = res.get("shift_px_cache", [0, 0])
    rect(a.width + 8, dx, dy, (250, 200, 80))
    d.text((6, 7), f"{recording} f{frame} - published sd{row['rel']} (label drawn here)", fill=(160, 240, 160))
    verdict = "tracked" if res.get("ok") else f"track FAILED ({res.get('reason')})"
    d.text((a.width + 16, 7),
           f"simultaneous sd{row['sim']} - {verdict} shift {res.get('shift_px_fhd')} FHD px "
           f"ncc {res.get('ncc_mean')} round-trip {res.get('round_trip_px_cache')} px",
           fill=(255, 230, 150))
    path.parent.mkdir(parents=True, exist_ok=True)
    out.save(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="carry a label box onto the retimed SD frame")
    ap.add_argument("--recording", required=True)
    ap.add_argument("--frame", type=int, required=True)
    ap.add_argument("--category", default="mortar_shell")
    ap.add_argument("--shot", default="")
    a = ap.parse_args(argv)
    res = track(a.recording, a.frame, a.category)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if a.shot and res.get("sd_from") is not None:
        p = Path(a.shot)
        shot(a.recording, a.frame, a.category, res, p if p.is_absolute() else ROOT / p)
        print("shot:", a.shot)
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
