"""Roll the arc sheets out over every usable recording.

"Usable" means: the recording appears in manifest-resolved.json and its
``aris_raw`` actually loads. Nothing else is required -- a recording without a
``paired_role`` still gets sheets (it just cannot be exported later), and that
fact is recorded per recording rather than used to silently drop it.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import tools._bootstrap as _bootstrap  # noqa: F401  (adds REPO to sys.path)

from engine import geometry as G
from tools import arc_sheets

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO.parent / "DataSet" / "camera_temporal_all" / "manifest-resolved.json"
OUT = REPO / "out" / "sonar_arc_annotation"


def main() -> int:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    recs = {}
    for it in m["items"]:
        r = it["recording"]
        d = recs.setdefault(r, {"recording": r, "category": it.get("category"),
                                "roles": set(), "frames": set()})
        if it.get("paired_role"):
            d["roles"].add(it["paired_role"])
        d["frames"].add(int(it["aris_frame"]))
    index = {"manifest": str(MANIFEST), "n_recordings": len(recs), "recordings": []}
    OUT.mkdir(parents=True, exist_ok=True)
    for i, (r, meta) in enumerate(sorted(recs.items()), 1):
        dst = OUT / r
        entry = {"recording": r, "category": meta["category"],
                 "paired_roles": sorted(meta["roles"]), "n_manifest_frames": len(meta["frames"])}
        try:
            if (dst / "candidates" / "proposals.json").exists():
                props = json.loads((dst / "candidates" / "proposals.json").read_text(encoding="utf-8"))
                sheets = json.loads((dst / "candidates" / "sheets.json").read_text(encoding="utf-8"))
                entry.update(samples=len(props), sheets=len(sheets),
                             with_box=sum(1 for p in props if p["proposal_xyxy"]), reused=True)
            else:
                buf = sys.stdout
                sys.stdout = open(OUT / "_rollout.log", "a", encoding="utf-8")
                try:
                    arc_sheets.main(["--recording", r, "--out", str(dst)])
                finally:
                    sys.stdout.close(); sys.stdout = buf
                props = json.loads((dst / "candidates" / "proposals.json").read_text(encoding="utf-8"))
                sheets = json.loads((dst / "candidates" / "sheets.json").read_text(encoding="utf-8"))
                entry.update(samples=len(props), sheets=len(sheets),
                             with_box=sum(1 for p in props if p["proposal_xyxy"]), reused=False)
            entry["ok"] = True
        except Exception as e:  # a broken recording must not stop the rollout
            entry.update(ok=False, error=f"{type(e).__name__}: {e}",
                         traceback=traceback.format_exc(limit=3))
        index["recordings"].append(entry)
        print(f"[{i}/{len(recs)}] {r} {entry.get('samples','-')} {entry.get('ok')}", flush=True)
    index["n_ok"] = sum(1 for e in index["recordings"] if e.get("ok"))
    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# arc sheets rollout", "",
             f"{index['n_ok']}/{index['n_recordings']} recordings, 100 samples each.", "",
             "| recording | category | role | samples | sheets | with_box | ok |",
             "|---|---|---|---|---|---|---|"]
    for e in index["recordings"]:
        lines.append(f"| `{e['recording']}` | {e['category']} | {','.join(e['paired_roles']) or '—'} | "
                     f"{e.get('samples','')} | {e.get('sheets','')} | {e.get('with_box','')} | "
                     f"{'yes' if e.get('ok') else (e.get('error') or '')[:40]} |")
    (OUT / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"ok": index["n_ok"], "total": index["n_recordings"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
