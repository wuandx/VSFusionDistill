"""Diagnose SD/FHD frame correspondence using approved clips only."""
from pathlib import Path
from fractions import Fraction
import csv
import json
import subprocess
import hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "related_work/uxo/sd-fhd-trace"
OUT = ROOT / "复现/camera-baseline/annotation-issues/sd-fhd"
DATA = Path(r"D:\pby\uxo-full\extracted\recordings\15cm_mortar")
CLIPS = ROOT / "DataSet/camera_annotation_trace/sd_clips"
FONT = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 18)
RECS = ["2023-09-21_101622", "2023-09-21_103140"]
EXTRA = {"2023-09-21_101622": [822], "2023-09-21_103140": [223, 309]}


def command(args):
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout


def sd_frame(clip, index):
    data = command(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(clip),
                    "-vf", f"select=eq(n\\,{index})", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"])
    return Image.frombytes("RGB", (640, 360), data)


def draw_box(im, box, title):
    im = im.copy().convert("RGB")
    d = ImageDraw.Draw(im)
    x, y, x2, y2 = box
    d.rectangle((x, y, x2, y2), outline="#ffcb3b", width=2)
    result = Image.new("RGB", (640, 408), "#101821")
    result.paste(im, (0, 48))
    d = ImageDraw.Draw(result)
    d.text((8, 7), title, fill="white", font=FONT)
    d.text((8, 28), "native SD box xyxy: " + str(box), fill="#ffcb3b", font=FONT)
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    overview = json.loads((ROOT / "复现/camera-baseline/annotation-issues/overview-sampling.json").read_text())
    with (BASE / "matches.csv").open(encoding="utf-8", newline="") as stream:
        matches = {row["aris_file"].split("/")[-1]: row for row in csv.DictReader(stream)}
    all_results = []
    for rec in RECS:
        match = matches[rec]
        clip = CLIPS / Path(match["gopro_file"]).name
        probe = json.loads(command(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(clip)]))
        (OUT / (rec + "-ffprobe.json")).write_text(json.dumps(probe, indent=2), encoding="utf-8")
        stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
        assert (stream["width"], stream["height"]) == (640, 360)
        fps = float(Fraction(stream["avg_frame_rate"]))
        raw = command(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(clip),
                       "-vf", "scale=160:90", "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"])
        pixels = np.frombuffer(raw, dtype=np.uint8).reshape((-1, 90*160)).astype(np.float32)
        means = np.mean(pixels, axis=1)
        centered = pixels - means[:, None]
        squares = np.mean(centered * centered, axis=1)
        rows = next(x for x in overview if x["recording"] == rec)["selected_samples"]
        frames = sorted({int(x.rsplit("_", 1)[1]) for x in rows} | set(EXTRA[rec]))
        queries = []
        for frame in frames:
            with Image.open(DATA / rec / "gopro" / f"{frame:04d}.jpg") as image:
                q = np.asarray(image.convert("L").resize((160, 90), Image.Resampling.BICUBIC), dtype=np.float32).reshape(-1)
            queries.append(q - q.mean())
        queries = np.stack(queries)
        scores = squares[:, None] + np.mean(queries*queries, axis=1)[None, :] - 2 * (centered @ queries.T) / (160*90)
        times = {}
        with (DATA / rec / "aris_frame_meta.csv").open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                times[int(r["FrameIndex"])] = int(r["FrameTime"])
        onset, offset = int(match["aris_onset"]), int(match["gopro_offset"])
        indices = sorted(times)
        interval = float(np.median([times[b]-times[a] for a,b in zip(indices, indices[1:])]))
        onset_exact = onset in times
        origin = times[onset] if onset_exact else times[indices[0]] - (indices[0]-onset)*interval
        results = []
        for column, frame in enumerate(frames):
            order = np.argsort(scores[:, column])[:5]
            best = int(order[0])
            predicted = int((times[frame]-origin)/1e6*fps) + offset
            results.append({"recording": rec, "frame": frame, "best_sd_index": best,
                            "predicted_sd_index": predicted, "difference": best-predicted,
                            "top5": [{"sd_index": int(k), "centered_mse": float(scores[k,column])} for k in order]})
        selected = []
        for frame in EXTRA[rec]:
            row = next(r for r in results if r["frame"] == frame)
            label = json.loads((DATA / rec / "labels" / f"{frame:04d}.json").read_text())
            box = [label[k] for k in ["x_min", "y_min", "x_max", "y_max"]]
            best = sd_frame(clip, row["best_sd_index"])
            candidate = sd_frame(clip, max(0, row["predicted_sd_index"]))
            with Image.open(DATA / rec / "gopro" / f"{frame:04d}.jpg") as original:
                fhd = original.resize((640, 360), Image.Resampling.LANCZOS)
            panels = [draw_box(candidate, box, f"SD at time-rule index {row['predicted_sd_index']}"),
                      draw_box(best, box, f"SD nearest-image index {row['best_sd_index']}"),
                      draw_box(fhd, box, f"Published FHD JPG / 3, frame {frame}")]
            canvas = Image.new("RGB", (1920, 408))
            for i, panel in enumerate(panels): canvas.paste(panel, (640*i, 0))
            name = f"{rec}_{frame:04d}-sd-fhd.jpg"
            canvas.save(OUT / name, quality=94)
            selected.append(name)
        result = {"recording": rec, "clip": str(clip), "clip_sha256": hashlib.sha256(clip.read_bytes()).hexdigest(),
                  "fps": fps, "sd_frame_count": len(pixels), "decode_fps_mode": "passthrough", "match_row": match,
                  "aris_onset_time_available": onset_exact, "onset_time_method": "exact" if onset_exact else "median-interval extrapolation from exported metadata; not exact",
                  "median_aris_interval_us": interval, "frames": results, "diagnostic_images": selected,
                  "interpretation_limit": "Centered low-resolution MSE is a correspondence clue, not annotation quality or a label-repair rule."}
        all_results.append(result)
        print(json.dumps({"recording":rec,"fps":fps,"frames":len(results),"differences":[r["difference"] for r in results]}), flush=True)
        del pixels, centered, raw, scores
    (OUT / "frame-correspondence.json").write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
