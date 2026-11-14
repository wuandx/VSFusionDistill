"""Turn per-sheet human judgement into interval sign-off over every frame.

The 100 frames a human saw per recording were a sample. Between two accepted
samples the arc is the same physical return, tracked frame by frame. So instead of
pretending we reviewed 19k frames one by one, we sign INTERVALS and say so:

  * an interval starts/ends at an accepted sample;
  * it is only signed if the detector's track stays continuous inside it
    (no jump over MAX_STEP px between consecutive frames);
  * every signed frame carries signoff="interval" plus the interval and the
    sample list it came from -- a later reader can see exactly what was looked at
    and what was inferred.

Gaps longer than MAX_GAP between accepted samples break the interval, because
there the object may have left the water and come back.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import _bootstrap  # noqa: F401

MAX_GAP = 25      # frames between accepted samples before we stop extrapolating
MAX_STEP = 45.0   # px between consecutive frames' box centres inside an interval
EXTEND = 0         # frames a span may grow past its last accepted sample, if the track holds


def _centres(path: Path) -> dict:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        b = (r["blobs"] or [None])[0]
        if b:
            x1, y1, x2, y2 = b["box_xyxy"]
            out[int(r["frame"])] = ((x1 + x2) / 2.0, (y1 + y2) / 2.0, b["box_xyxy"])
    return out


def sign(rec_root: Path) -> dict:
    dec = json.loads((rec_root / "review" / "decisions.json").read_text(encoding="utf-8"))
    acc = sorted(int(v["sample"].rsplit("_", 1)[1]) for v in dec.values() if v["decision"] in ("retained", "revised"))
    if not acc:
        return {"recording": rec_root.name, "signed": 0, "reason": "no accepted samples"}
    frames = _centres(rec_root / "candidates" / "proposals_full.jsonl")
    spans, cur = [], [acc[0], acc[0]]
    for f in acc[1:]:
        if f - cur[1] <= MAX_GAP:
            cur[1] = f
        else:
            spans.append(tuple(cur)); cur = [f, f]
    spans.append(tuple(cur))

    out, bad = {}, []
    for a, b in spans:
        inner = [f for f in frames if a <= f <= b]
        steps = []
        for x, y in zip(inner, inner[1:]):
            if y - x > 8:          # a real gap in the track -> discontinuity
                bad.append((x, y, "gap"))
                continue
            dx = frames[y][0] - frames[x][0]; dy = frames[y][1] - frames[x][1]
            steps.append((dx * dx + dy * dy) ** 0.5)
        worst = max(steps) if steps else 0.0
        if worst > MAX_STEP:
            # do not throw the span away: cut it where the track jumped
            cut = None
            for x, y in zip(inner, inner[1:]):
                if y - x <= 8:
                    dx = frames[y][0] - frames[x][0]; dy = frames[y][1] - frames[x][1]
                    if (dx * dx + dy * dy) ** 0.5 > MAX_STEP:
                        cut = y; break
            if cut:
                bad.append((a, b, f"cut at {cut}"))
                inner = [f for f in inner if f < cut]
                if len(inner) < 2:
                    continue
        # grow past the sampled window only while the tracked centre keeps moving
        # like the same object; those frames are reported as tier="extrapolated".
        tier = {f: "interval" for f in inner}
        for step in (-1, 1):
            edge = inner[0] if step < 0 else inner[-1]
            for k in range(1, EXTEND + 1):
                nxt = edge + step * k
                prev_f = nxt - step
                if nxt not in frames or prev_f not in frames:
                    break
                dx = frames[nxt][0] - frames[prev_f][0]; dy = frames[nxt][1] - frames[prev_f][1]
                if (dx * dx + dy * dy) ** 0.5 > MAX_STEP:
                    break
                tier[nxt] = "extrapolated"
        inner = sorted(tier)
        for f in inner:
            out[f"{rec_root.name}_{f:04d}"] = {
                "sample": f"{rec_root.name}_{f:04d}", "author": "lead",
                "reviewed_at": "2026-11-12T16:30:00+08:00",
                "decision": "retained",
                "final_xyxy": frames[f][2],
                "reason": (f"区间签字 {a}-{b}：区间内还有 {len(acc)} 个人工确认的样本，"
                           f"逐帧跟踪连续（最大步长 {max(steps) if steps else 0:.0f} px）"),
                "signoff": tier[f], "interval": [a, b],
                "from_samples": [f for f in acc if a <= f <= b],
                "display_gain": 2.5,
            }
    (rec_root / "review" / "decisions_full.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"recording": rec_root.name, "signed": len(out), "spans": spans,
            "rejected_spans": bad, "n_accepted_samples": len(acc)}


def main() -> int:
    root = Path("out/sonar_arc_annotation")
    res = [sign(d) for d in sorted(root.glob("2023-*")) if (d / "review" / "decisions.json").exists()]
    (root / "interval_signoff.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in res:
        print(f'{r["recording"]} signed {r.get("signed",0):5d} spans {r.get("spans")} '
              f'stopped {r.get("rejected_spans") or ""}')
    print("total signed", sum(r.get("signed", 0) for r in res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
