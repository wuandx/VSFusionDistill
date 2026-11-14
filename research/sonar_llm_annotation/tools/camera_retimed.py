"""Where does each ARIS frame's camera image really live, and is the released picture the wrong moment?

Every recording gets its own answer.  The released camera JPGs were cut from `clips_fhd` using an index
computed for `clips_sd`, and the two clips do not start at the same time, so the file numbered N shows a
different moment from the sonar frame numbered N.  How big that mistake is differs per recording
(measured: -201 .. +204 frames), so nothing here is shared across recordings.

The model, in camera frames, for one recording:
    released_jpg(f)  = C + a * (f - aris_onset)          with C = gopro_idx + gopro_offset + offset_frames
    simultaneous(f)  = released_jpg(f) - offset_frames
where `a` is how many camera frames pass per sonar frame and `offset_frames = (start_fhd - start_sd) * fps`
is the clip-start difference read from the containers.

Two things are checked against the pictures themselves, per recording:
  * the shape: is the released JPG of frame f the SD frame at C + a*(f-onset) for a single `a`?
    (`a` nominal = sd_fps / sonar_fps; `a` measured = fitted from content).  The nominal value is only
    trusted if it explains the pictures; on 105230 it does not (nominal 1.998 vs measured 2.031, i.e.
    1.6% -> 10 frames of drift by the end of the clip), so the measured value is what the table carries.
  * the size of the mistake: with (a, b) fitted from content, b - C is how far the released picture sits
    from where the official numbers say it should be.  That difference should equal `offset_frames` if the
    container reading is trustworthy.

Nothing is fixed silently: a recording whose pictures do not lie on a single line, or whose residual is
larger than a couple of frames, is reported as mismatch.

One decode pass per recording keeps this affordable: the clip is decoded once to 160x90 grey (rawvideo on
stdout); every comparison afterwards is array maths.  The 640x360 pictures in the comparison sheet are
grabbed with a seek, which is fast.

usage: python -m tools.camera_retimed [--only NAME] [--frames 5] [--no-png] [--search 60]
"""
from __future__ import annotations

import csv
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
MANIFEST = ROOT.parent / "DataSet" / "camera_temporal_all" / "manifest-resolved.json"
AUDIT = ROOT / "out" / "sd_fhd_audit.json"
REC_ROOT = Path(r"D:\pby\uxo-full\extracted\recordings")
THUMB = (160, 90)
BIG = (640, 360)
RESIDUAL_LIMIT = 3.0  # frames


def approved() -> list[str]:
    d = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return sorted({it["recording"] for it in d.get("items", []) if it.get("recording")})


def rows_by_recording() -> dict[str, dict]:
    out = {}
    with open(PROCESSED / "matches.csv", encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            name = Path((r.get("aris_file") or "").strip()).name
            if name and (r.get("gopro_file") or "").strip():
                out[name] = r
    return out


def audit_by_recording() -> dict[str, dict]:
    d = json.loads(AUDIT.read_text(encoding="utf-8"))
    return {r["recording"]: r for r in d.get("recordings", [])}


def load_thumbs(clip: Path) -> np.ndarray | None:
    w, h = THUMB
    p = subprocess.run([str(FF), "-hide_banner", "-loglevel", "error", "-i", str(clip),
                        "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                       capture_output=True)
    n = len(p.stdout) // (w * h)
    if n == 0:
        return None
    return np.frombuffer(p.stdout[: n * w * h], dtype=np.uint8).reshape(n, h, w)


def grab_big(clip: Path, n: int, fps: float) -> Image.Image | None:
    if n < 0:
        return None
    p = subprocess.run([str(FF), "-hide_banner", "-loglevel", "error", "-ss", f"{n / fps:.3f}",
                        "-i", str(clip), "-frames:v", "1", "-vf", f"scale={BIG[0]}:{BIG[1]}",
                        "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    if not p.stdout:
        return None
    return Image.open(io.BytesIO(p.stdout)).convert("RGB")


def ncc(a: np.ndarray, b: np.ndarray) -> float:
    a0, b0 = a.astype(np.float32) - a.mean(), b.astype(np.float32) - b.mean()
    d = float(np.sqrt((a0 * a0).sum() * (b0 * b0).sum()))
    return float((a0 * b0).sum() / d) if d else 0.0


def rec_dir(recording: str, category: str) -> Path:
    cat = {"100lbs_aircraft_bomb": "100lbs_bomb", "incindiary_grenade": "20lbs_incendiary",
           "mortar_shell": "15cm_mortar"}[category]
    return REC_ROOT / cat / recording


def sonar_fps_of(recording: str) -> float | None:
    hdr = G.header_of(recording=recording)
    for key in ("FrameRate", "frame_rate"):
        if hdr.get(key):
            return float(hdr[key])
    return None


def best_match(a: np.ndarray, thumbs: np.ndarray, centre: int, search: int) -> tuple[int, float]:
    lo, hi = max(0, centre - search), min(len(thumbs) - 1, centre + search)
    if hi <= lo:
        return centre, -1.0
    scores = np.array([ncc(a, thumbs[k]) for k in range(lo, hi + 1)])
    k = lo + int(scores.argmax())
    if (k == lo or k == hi) and search < 240:  # hit the window edge: widen once
        return best_match(a, thumbs, centre, search * 3)
    return k, float(scores.max())


def analyse(recording: str, row: dict, off: int, sd_fps: float, sonar_fps: float,
            frames: list[int], search: int, make_png: bool) -> dict:
    rec = G.load_recording(recording)
    rd = rec_dir(recording, rec.category)
    clip = PROCESSED / (row.get("gopro_file") or "").strip()
    onset = int(float(row.get("aris_onset") or 0))
    gop = int(float(row.get("gopro_idx") or 0))
    goff = int(float(row.get("gopro_offset") or 0))
    C = gop + goff + off
    a_nom = sd_fps / sonar_fps

    thumbs = load_thumbs(clip)
    hits = []
    for f in frames:
        jpg = rd / "gopro" / f"{f:04d}.jpg"
        if thumbs is None or not jpg.exists():
            continue
        a = np.asarray(Image.open(jpg).convert("L").resize(THUMB, Image.LANCZOS))
        pred_nom = int(round(C + a_nom * (f - onset)))
        got, score = best_match(a, thumbs, pred_nom, search)
        hits.append({"aris_frame": f, "predicted_sd_nominal": pred_nom,
                     "matched_sd": got, "ncc": round(score, 4)})

    out = {
        "recording": recording, "category": rec.category, "clip": clip.name,
        "n_sd_frames": 0 if thumbs is None else int(len(thumbs)),
        "aris_onset": onset, "gopro_idx": gop, "gopro_offset": goff,
        "offset_frames": off, "C": C,
        "sd_fps": round(sd_fps, 3), "sonar_fps_nominal": round(sonar_fps, 3),
        "a_nominal": round(a_nom, 4), "anchors": hits,
    }

    if len(hits) < 2:
        out.update(status="no_jpg", note="fewer than two labelled frames had a released JPG")
        return out

    xs = np.array([h["aris_frame"] for h in hits], dtype=float)
    ys = np.array([h["matched_sd"] for h in hits], dtype=float)
    a, b = np.polyfit(xs, ys, 1)
    resid = ys - (b + a * xs)
    out.update({
        "a_measured": round(float(a), 4),
        "a_measured_sonar_fps": round(sd_fps / a, 3) if a else None,
        "b": round(float(b), 3),
        # how far the fitted line sits from the official anchor at the clip start (frames)
        "residual_at_onset": round(float(b + a * onset - C), 1),
        "residual_frames": [round(float(r), 2) for r in resid],
        "residual_max_abs": round(float(np.abs(resid).max()), 2),
    })

    resid_nom = ys - (C + a_nom * (xs - onset))
    out["residual_max_abs_nominal_a"] = round(float(np.abs(resid_nom).max()), 2)

    if out["residual_max_abs"] <= RESIDUAL_LIMIT:
        status = "verified_nominal_ratio" if out["residual_max_abs_nominal_a"] <= RESIDUAL_LIMIT \
            else "verified_measured_ratio"
    else:
        status = "mismatch"
    out["status"] = status
    out["simultaneous_formula"] = f"sd = {a:.4f} * f + ({b - off:.1f})"
    out["released_formula"] = f"sd = {a:.4f} * f + {b:.1f}"
    out["offset_implied_by_fit"] = out["residual_at_onset"]

    if make_png and status != "no_jpg":
        h = hits[len(hits) // 2]
        f = h["aris_frame"]
        sd_sim = int(round(b - off + a * f))
        pub = Image.open(rd / "gopro" / f"{f:04d}.jpg").convert("RGB").resize(BIG, Image.LANCZOS)
        sim_img = grab_big(clip, sd_sim, sd_fps)
        box = None
        lp = rd / "labels" / f"{f:04d}.json"
        if lp.exists():
            o = json.loads(lp.read_text(encoding="utf-8"))
            box = (o["x_min"], o["y_min"], o["x_max"], o["y_max"])

        def tile(img, title, colour):
            c = Image.new("RGB", (BIG[0], BIG[1] + 34), (248, 248, 248))
            c.paste(img, (0, 34))
            d = ImageDraw.Draw(c)
            d.text((6, 11), title, fill=(15, 15, 15))
            if box:
                d.rectangle([box[0], box[1] + 34, box[2], box[3] + 34], outline=colour, width=2)
            return c

        tiles = [tile(pub, f"released gopro/{f:04d}.jpg = SD {h['matched_sd']} "
                           f"(labels drawn here; {abs(off)} frames early, ncc {h['ncc']})", (220, 40, 40))]
        if sim_img is not None:
            tiles.append(tile(sim_img, f"SD {sd_sim} = simultaneous with sonar {f}", (40, 120, 220)))
        sheet = Image.new("RGB", (len(tiles) * (BIG[0] + 8), BIG[1] + 34), (232, 232, 232))
        for k, t in enumerate(tiles):
            sheet.paste(t, (k * (BIG[0] + 8), 0))
        outdir = ROOT / "out" / "camera_retimed"
        outdir.mkdir(parents=True, exist_ok=True)
        sheet.save(outdir / f"{recording}_f{f:04d}.png")
        out["comparison_png"] = f"out/camera_retimed/{recording}_f{f:04d}.png"
    return out


def write_markdown(payload: dict, path: Path) -> None:
    rows = payload["recordings"]
    lines = [
        "# camera_retimed：每条录音各自的 SD 帧索引",
        "",
        "发布图（以及画在它上面的 label）来自 `clips_fhd`，索引却是按 `clips_sd` 算的，两个片段起点不同，",
        "所以第 N 号文件拍的不是第 N 号声呐帧的那一刻。起点差逐录音不同，**不能套用**。",
        "",
        "`g(f)` = 与声呐帧 f 同时刻的 SD 帧；`released(f)` = 发布图所在的 SD 帧 = `g(f) + offset_frames`。",
        "`a` 是每个声呐帧对应的相机帧数（实测拟合），`Δonset` 列 = 拟合直线在片段起点处与官方锚点的差（帧，负=发布图更早）。",
        "",
        "| 录音 | 类别 | SD 片段 | a 实测 | a 标称 | offset | Δonset | 最大残差 | 状态 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if r["status"] == "no_jpg":
            lines.append(f"| `{r['recording']}` | {r['category']} | {r['clip']} | — | — | "
                         f"{r['offset_frames']:+d} | — | — | no_jpg |")
            continue
        lines.append(
            f"| `{r['recording']}` | {r['category']} | {r['clip']} | {r['a_measured']:.4f} | "
            f"{r['a_nominal']:.4f} | {r['offset_frames']:+d} | {r['residual_at_onset']:+.1f} | "
            f"{r['residual_max_abs']:.2f} | {r['status']} |")
    lines += ["", f"verified {payload['n_verified']} / {len(rows)}，mismatch {payload['n_mismatch']}，"
                  f"no_jpg {payload['n_no_jpg']}。", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str]) -> int:
    only, nframes, make_png, search = None, 5, True, 60
    i = 1
    while i < len(argv):
        k = argv[i]
        if k == "--only":
            only = argv[i + 1]; i += 2
        elif k == "--frames":
            nframes = int(argv[i + 1]); i += 2
        elif k == "--search":
            search = int(argv[i + 1]); i += 2
        elif k == "--no-png":
            make_png = False; i += 1
        else:
            i += 1

    rows, audit = rows_by_recording(), audit_by_recording()
    names = approved() or sorted(rows)
    if only:
        names = [n for n in names if n == only]
    print(f"{len(names)} approved recordings; {len(rows)} match rows; {len(audit)} audited", flush=True)

    results, skipped = [], []
    for n, name in enumerate(names, 1):
        row, a = rows.get(name), audit.get(name)
        if row is None or a is None or a.get("offset_frames") is None:
            skipped.append((name, "no match row" if row is None else "no container offset"))
            continue
        try:
            rec = G.load_recording(name)
            sonar_fps = sonar_fps_of(name)
        except Exception as exc:  # noqa: BLE001
            skipped.append((name, f"geometry: {type(exc).__name__}"))
            continue
        if not sonar_fps:
            skipped.append((name, "no sonar frame rate"))
            continue
        sd_fps = float(a.get("sd", {}).get("fps") or 29.97)
        frames_all = sorted(rec.frames)
        step = max(1, len(frames_all) // (nframes + 1))
        picks = [frames_all[min(step * k, len(frames_all) - 1)] for k in range(1, nframes + 1)]
        res = analyse(name, row, int(a["offset_frames"]), sd_fps, sonar_fps, picks, search, make_png)
        results.append(res)
        if res["status"] == "no_jpg":
            print(f"[{n}/{len(names)}] {name} no_jpg", flush=True)
        else:
            print(f"[{n}/{len(names)}] {name} a={res['a_measured']:.4f} (nom {res['a_nominal']:.4f}) "
                  f"off={res['offset_frames']:+d} dOnset={res['residual_at_onset']:+.1f} "
                  f"res={res['residual_max_abs']:.2f} {res['status']}", flush=True)

    payload = {
        "note": ("Per-recording mapping between ARIS frame index and SD camera frame index. "
                 "sd_simultaneous(f) is the camera frame that happened at the same moment as sonar frame f; "
                 "the released JPG for f sits offset_frames away from it because the export applied an "
                 "SD-space index to the FHD clip. a is fitted from picture content, not from nominal fps: "
                 "on 105230 the nominal value drifts 10 frames by the end of the clip. "
                 "Nothing here may be reused across recordings."),
        "sd_clip_root": str(PROCESSED / "gopro" / "clips_sd"),
        "residual_limit_frames": RESIDUAL_LIMIT,
        "n_verified": sum(1 for r in results if r["status"].startswith("verified")),
        "n_mismatch": sum(1 for r in results if r["status"] == "mismatch"),
        "n_no_jpg": sum(1 for r in results if r["status"] == "no_jpg"),
        "recordings": results,
        "skipped": [{"recording": k, "why": v} for k, v in skipped],
    }
    out = ROOT / "out" / "camera_retimed.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(payload, ROOT / "out" / "CAMERA-RETIMED.md")
    print(f"\nverified {payload['n_verified']}/{len(results)}  mismatch {payload['n_mismatch']}  "
          f"skipped {len(skipped)}")
    print("wrote", out.relative_to(ROOT), "and out/CAMERA-RETIMED.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
