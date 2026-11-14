"""Record one review decision in the reference format.

Same fields as DataSet/sonar_visible_annotation/review/decisions.json:
decision in {retained, revised, rejected, uncertain}, final_xyxy, reason,
review_sheet + review_sheet_sha256 (so a decision is bound to the sheet that
was actually looked at), display_gain, original_xyxy.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

DECISIONS = ("retained", "revised", "rejected", "uncertain")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="record one review decision")
    ap.add_argument("--root", required=True, help="the recording dir holding candidates/ and review/")
    ap.add_argument("--sample", required=True)
    ap.add_argument("--decision", required=True, choices=DECISIONS)
    ap.add_argument("--box", default="", help="x1,y1,x2,y2 (required for retained/revised)")
    ap.add_argument("--reason", required=True)
    ap.add_argument("--author", default="lead")
    ap.add_argument("--gain", type=float, default=2.5)
    a = ap.parse_args(argv)
    root = Path(a.root)
    props = json.loads((root / "candidates" / "proposals.json").read_text(encoding="utf-8"))
    row = next((r for r in props if r["sample"] == a.sample), None)
    if row is None:
        raise SystemExit(f"no proposal for {a.sample}")
    sheets = json.loads((root / "candidates" / "sheets.json").read_text(encoding="utf-8"))
    sheet = next((s for s in sheets if a.sample in s["samples"]), None)
    box = None
    if a.box:
        box = [int(v) for v in a.box.split(",")]
        if len(box) != 4:
            raise SystemExit("--box wants x1,y1,x2,y2")
    elif a.decision in ("retained", "revised"):
        raise SystemExit(f"{a.decision} needs --box")
    dp = root / "review" / "decisions.json"
    dec = json.loads(dp.read_text(encoding="utf-8") or "{}")
    dec[a.sample] = dict(
        sample=a.sample, author=a.author,
        reviewed_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        decision=a.decision, final_xyxy=box, reason=a.reason,
        review_sheet=sheet["sheet"] if sheet else None,
        review_sheet_sha256=sheet["sha256"] if sheet else None,
        display_gain=a.gain, original_xyxy=row["proposal_xyxy"])
    dp.write_text(json.dumps(dec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"sample": a.sample, "decision": a.decision, "n": len(dec)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
