"""Run the label-carrier over every labelled frame of one or more recordings.

The panel asks `tools.cam_track` for a frame at a time (~0.6 s cold).  This walks the whole
recording once and leaves the answers in `out/camera_track/<recording>/<frame>.json`, so the
panel is instant afterwards and we get a coverage number instead of a spot check.

Failures are written too (with their reason) so a second run does not recompute them; delete
the directory to force a re-run after changing the tracker.

usage
-----
    python -m tools.cam_track_batch --recording 2023-09-21_105230
    python -m tools.cam_track_batch --all
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from tools.cam_track import OUT, SD_CACHE, find_category, label_path, load_index, track

TRACK_DIR = OUT / "camera_track"


def labelled_frames(recording: str) -> list[int]:
    """Every frame that has a JSON label, in order."""
    cat = find_category(recording)
    if not cat:
        return []
    p = label_path(recording, 1, cat).parent
    if not p.is_dir():
        return []
    return sorted(int(f.stem) for f in p.glob("*.json") if f.stem.isdigit())


def run(recording: str, force: bool = False, stride: int = 1) -> dict:
    rows = load_index(recording)
    if not rows:
        return {"recording": recording, "error": "no retime rows"}
    cache = SD_CACHE / recording
    if not cache.is_dir():
        return {"recording": recording, "error": "no SD frames extracted"}
    have = {int(p.stem) for p in cache.glob("*.jpg")}

    frames = labelled_frames(recording)
    if stride > 1:                      # a stratified estimate, not the whole recording
        frames = frames[::stride]
    tout = TRACK_DIR / recording
    tout.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    ok = skipped = failed = 0
    reasons: dict[str, int] = {}
    shifts: list[float] = []
    for n, f in enumerate(frames, 1):
        dst = tout / ("%04d.json" % f)
        if dst.is_file() and not force:
            try:
                r = json.loads(dst.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                r = {}
            if r:
                if r.get("ok"):
                    ok += 1
                    shifts.append(max(abs(v) for v in r.get("shift_px_fhd", [0, 0])))
                else:
                    failed += 1
                    reasons[r.get("reason", "?")] = reasons.get(r.get("reason", "?"), 0) + 1
                skipped += 1
                continue
        row = rows.get(f)
        if not row or row["in_clip"] != 1 or row["rel"] not in have or row["sim"] not in have:
            r = {"ok": False, "reason": "no_slot", "frame": f, "recording": recording}
        else:
            r = track(recording, f)
        dst.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
        if r.get("ok"):
            ok += 1
            shifts.append(max(abs(v) for v in r.get("shift_px_fhd", [0, 0])))
        else:
            failed += 1
            reasons[r.get("reason", "?")] = reasons.get(r.get("reason", "?"), 0) + 1
        if n % 50 == 0:
            print(f"  {recording} {n}/{len(frames)} ok={ok} failed={failed} {time.time()-t0:.0f}s", flush=True)

    shifts.sort()
    summary = {
        "recording": recording,
        "n_labelled": len(labelled_frames(recording)),
        "n_evaluated": len(frames),
        "stride": stride,
        "ok": ok,
        "failed": failed,
        "ok_rate": round(ok / len(frames), 4) if frames else 0.0,
        "reasons": dict(sorted(reasons.items(), key=lambda kv: -kv[1])),
        "shift_fhd_median": shifts[len(shifts) // 2] if shifts else None,
        "shift_fhd_p90": shifts[int(0.9 * (len(shifts) - 1))] if shifts else None,
        "seconds": round(time.time() - t0, 1),
    }
    (tout / "_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def all_recordings() -> list[str]:
    return sorted({p.name for p in SD_CACHE.iterdir() if p.is_dir()})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="carry label boxes over every labelled frame")
    ap.add_argument("--recording", action="append", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--stride", type=int, default=1, help="sample every N labelled frames")
    a = ap.parse_args(argv)
    recs = a.recording or (all_recordings() if a.all else [])
    if not recs:
        ap.error("give --recording (repeatable) or --all")
    out = []
    for r in recs:
        print(f"[{r}]", flush=True)
        s = run(r, force=a.force, stride=max(1, a.stride))
        print(json.dumps(s, ensure_ascii=False), flush=True)
        out.append(s)
    (TRACK_DIR / "_all_summary.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
