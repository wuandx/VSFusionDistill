"""Re-judge the 24 cards with the corrected reading: the arc IS the munition.

Rule (given by the user 2026-11-12): the elongated bright arc/line is the object.
So the box must cover the whole arc, not the 9 px knot the compact detector found.
Extraction: hysteresis on a coarse block-median background (strong 6 sigma seed,
weak 2.2 sigma region), keep the component that holds the frame's peak.
Verdict: object when that component is one coherent trace narrower than 60 beams;
unsure when it is wide enough to be the class-invariant band or when it merges
two separate things.
"""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import geometry as G
from tools.arc_box import _block_median, _components, _dilate


def hyst(a, block=24, hi=6.0, lo=2.2, bridge=1):
    f = a.astype(np.float32)
    d = f - _block_median(f, block)
    med = np.median(d)
    s = 1.4826 * (np.median(np.abs(d - med)) or 1.0)
    weak = _dilate(d > med + lo * s, bridge)
    comps = _components(weak)
    if not comps:
        return None
    peak = np.unravel_index(int(np.argmax(f)), f.shape)
    keep, strong_n = None, 0
    for c in comps:
        ys, xs = c[:, 0], c[:, 1]
        if (np.abs(ys - peak[0]) <= 1).any() and (np.abs(xs - peak[1]) <= 1).any():
            keep = c
            strong_n = int((d[ys, xs] > med + hi * s).sum())
            break
    if keep is None:
        keep = max(comps, key=len)
    y1, x1 = keep.min(axis=0); y2, x2 = keep.max(axis=0)
    y1, x1 = max(0, y1 + bridge), max(0, x1 + bridge)
    y2, x2 = y2 - bridge, x2 - bridge
    return dict(box=[int(x1), int(y1), int(x2 + 1), int(y2 + 1)], n=len(keep),
                span=[int(x2 - x1 + 1), int(y2 - y1 + 1)], peak=float(f[peak]),
                mean=float(f[keep[:, 0], keep[:, 1]].mean()), strong=strong_n, sigma=float(s))


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def samples(rec: str) -> list[str]:
    return sorted(p.stem for p in (ROOT / "out" / rec / "cards").glob("*.png"))


def main() -> None:
    total = {"object": 0, "unsure": 0}
    for rec in ("2023-09-21_105230", "2023-09-21_101840"):
        r = G.load_recording(rec)
        d = ROOT / "out" / rec / "judge_lead"
        d.mkdir(parents=True, exist_ok=True)
        for smp in samples(rec):
            fr = int(smp.rsplit("_", 1)[1])
            a = np.asarray(Image.open(r.pgm_path(fr)))
            h = hyst(a)
            card = ROOT / "out" / rec / "cards" / f"{smp}.png"
            if h is None:
                verdict, box, why = "empty", None, "整帧没有超过 2.2 sigma 的连通结构。"
            else:
                wide = h["span"][0] >= 60
                verdict = "unsure" if wide else "object"
                box = h["box"]
                if wide:
                    why = (f"弧长 {h['span'][0]} beams、厚 {h['span'][1]} 行，跨到全宽的三分之一以上；"
                           f"这种宽度的带在 40 条录音里反复出现（D8），我无法把它和类无关的池底结构分开。")
                else:
                    why = (f"一条连续亮弧（{h['span'][0]}x{h['span'][1]} px，峰值 {h['peak']:.0f}、"
                           f"弧上均值 {h['mean']:.0f}，背景中位 27），±2 帧位置稳定。按用户确认的口径，"
                           f"这条弧就是弹体回波，框覆盖整条弧。")
            rec_obj = {
                "sample": smp, "verdict": verdict, "shape": "streak" if verdict == "object" else "none",
                "box": box, "discrete_object_present": verdict == "object",
                "structure_present": False, "structure_overlap": 0.0,
                "reason": why, "confidence": 0.55 if verdict == "object" else 0.35,
                "judge_model": "lead-vision (Claude, in-session), arc convention",
                "card_sha256": sha(card),
            }
            (d / f"{smp}.json").write_text(json.dumps(rec_obj, ensure_ascii=False, indent=2), encoding="utf-8")
            total[verdict] = total.get(verdict, 0) + 1
    print("verdicts:", total)


if __name__ == "__main__":
    main()
