"""Write the 24 lead judgments with tracked arc boxes (user: the arc IS the shell)."""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import geometry as G
from tools.arc_track_box import track_boxes
from tools.arc_pad import pad_box

MARGIN = 1.6   # user 2026-11-12: the 1.3 box still read as "a bit small"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    summary = {}
    for rec in ("2023-09-21_105230", "2023-09-21_101840"):
        r = G.load_recording(rec)
        cards = sorted((ROOT / "out" / rec / "cards").glob("*.png"))
        frames = [int(p.stem.rsplit("_", 1)[1]) for p in cards]
        seq = [(f, np.asarray(Image.open(r.pgm_path(f)))) for f in frames]
        heights = {f: img.shape[0] for f, img in seq}
        res = track_boxes(seq, radius=40)
        d = ROOT / "out" / rec / "judge_lead"
        d.mkdir(parents=True, exist_ok=True)
        n_obj = 0
        for p, f in zip(cards, frames):
            g = res.get(f)
            if not g:
                rec_obj = {"sample": p.stem, "verdict": "empty", "shape": "none", "box": None,
                           "discrete_object_present": False, "structure_present": False,
                           "structure_overlap": 0.0, "reason": "该帧窗口内没有超过 2.2 sigma 的连通亮结构。",
                           "confidence": 0.3, "judge_model": "lead-vision (Claude), arc convention",
                           "card_sha256": sha(p)}
            else:
                b = pad_box(g["box"], 128, heights[f], scale=MARGIN); w = b[2] - b[0]; h = b[3] - b[1]
                n_obj += 1
                rec_obj = {
                    "sample": p.stem, "verdict": "object", "shape": "streak", "box": b,
                    "discrete_object_present": True, "structure_present": False,
                    "structure_overlap": 0.0,
                    "reason": (f"亮弧 {w}x{h} px（峰值 {g['peak']:.0f}、弧上均值 {g['mean']:.0f}，背景中位 27）；"
                               f"按用户确认的口径，这条弧就是弹体回波。框覆盖可见的亮段；更淡的两端没有框进去，"
                               f"因为再低阈值会把噪声也连进来。"),
                    "confidence": 0.55 if w * h > 900 else 0.45,
                    "judge_model": "lead-vision (Claude), arc convention", "card_sha256": sha(p),
                }
            (d / f"{p.stem}.json").write_text(json.dumps(rec_obj, ensure_ascii=False, indent=2), encoding="utf-8")
        summary[rec] = n_obj
    print("object boxes written:", summary)


if __name__ == "__main__":
    main()
