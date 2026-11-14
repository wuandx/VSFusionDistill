"""Emit arc proposals in the sonar_visible_annotation sheet format.

The reference format (DataSet/sonar_visible_annotation) is: a flat
``proposals.json`` list, 100 samples per recording, and review sheets of
20 tiles on a 1600x960 white canvas (5 across, 4 down, each 320x240 with a
35 px header strip). A reviewer marks each sample in ``decisions.json``.

Same skeleton here, different boxes: this line boxes the arc that the sonar
actually returns (engine/arc.py) instead of a crop-window component.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import arc as A                       # noqa: E402
from engine import geometry as G                  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO.parent / "DataSet" / "camera_temporal_all" / "manifest-resolved.json"
GAIN = 2.5
SHEET = (1600, 960)
TILE = (320, 240)
HEAD = 35


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _items(recording: str) -> dict:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    out = {}
    for it in m["items"]:
        if it.get("recording") == recording:
            out[int(it["aris_frame"])] = it
    return out


def tile(img: np.ndarray, box, frame: int, ordinal: int, gain: float = GAIN) -> Image.Image:
    h, w = img.shape
    cy = (box[1] + box[3]) / 2.0 if box else h * 0.35
    span = max(110, (box[3] - box[1]) + 50) if box else 180
    y0 = max(0, int(cy - span / 2)); y1 = min(h, int(cy + span / 2))
    sub = np.clip(img[y0:y1].astype(np.float32) * gain, 0, 255).astype(np.uint8)
    im = Image.fromarray(sub).convert("RGB").resize((TILE[0], TILE[1] - HEAD))
    canvas = Image.new("RGB", TILE, "white")
    canvas.paste(im, (0, HEAD))
    d = ImageDraw.Draw(canvas)
    d.text((3, 2), f"{ordinal} f={frame} y={y0}:{y1}", fill="black")
    d.text((3, 18), str(list(box)) if box else "no arc", fill="black")
    if box:
        sx = TILE[0] / w
        sy = (TILE[1] - HEAD) / max(1, (y1 - y0))
        d.rectangle((box[0] * sx, HEAD + (box[1] - y0) * sy,
                     min(TILE[0] - 1, box[2] * sx), HEAD + (box[3] - y0) * sy),
                    outline="#00ff60", width=2)
    return canvas


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="arc proposals -> proposals.json + review sheets")
    ap.add_argument("--recording", required=True)
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--out", required=True)
    ap.add_argument("--gain", type=float, default=GAIN)
    a = ap.parse_args(argv)
    rec = G.load_recording(a.recording, with_meta=False)
    items = _items(a.recording)
    frames_all = sorted(rec.frames)
    lo = int(round((len(frames_all) - 1) * 0.2)); hi = int(round((len(frames_all) - 1) * 0.8))
    span = frames_all[lo:hi] or frames_all
    if len(span) < a.limit:
        span = frames_all
    pos = np.linspace(0, len(span) - 1, min(a.limit, len(span))).round().astype(int)
    frames = [span[i] for i in sorted(set(pos))]

    out = Path(a.out); cand = out / "candidates"; rev = out / "review"
    cand.mkdir(parents=True, exist_ok=True); rev.mkdir(parents=True, exist_ok=True)
    if not (rev / "decisions.json").exists():
        (rev / "decisions.json").write_text("{}\n", encoding="utf-8")
    rows=[]; prev=None
    for ordinal, fr in enumerate(frames):
        row = A.analyse(a.recording, fr, prev_center=prev)
        blob = row["blobs"][0] if row["blobs"] else None
        box = blob["box_xyxy"] if blob else None
        if box:
            prev = ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)
        bw = (box[2] - box[0]) if box else 0
        snr = blob["snr"] if blob else None
        area = blob["area"] if blob else None
        if box is None:
            kind = "none"
        elif bw >= 100:
            kind = "band"   # spans the sector: structure, not a return
        elif snr is not None and snr < 10 and (area or 0) < 40:
            kind = "noise"
        else:
            kind = "arc"
        it = items.get(fr, {})
        src = rec.pgm_path(fr)
        rows.append(dict(
            sample=f"{a.recording}_{fr:04d}", recording=a.recording,
            category=it.get("category") or row.get("category"), overview_index=None,
            ordinal=ordinal, frame=fr, source=str(src), source_sha256=sha(src),
            shape_hw=list(row["blobs"][0].get("shape") or [row["n_rows"], row["n_beams"]]),
            proposal_xyxy=box,
            diagnostics={"engine": row["provenance"]["engine_version"], "margin": row["provenance"]["margin"],
                         "snr": snr, "area": area, "kind": kind,
                         "raw_xyxy": row["arc"]["raw_box_xyxy"] if row["arc"] else None,
                         "noise": row["arc"]["noise"] if row["arc"] else None},
            reference_sd=it.get("reference_sd"), paired_role=it.get("paired_role"),
            status="pending_visual_review"))

    sheets = []
    # sheets carry only actionable samples; the rest stay in proposals.json
    sel = [r for r in rows if r["diagnostics"]["kind"] == "arc"] or rows
    for j in range(0, len(sel), 20):
        canvas = Image.new("RGB", SHEET, "white")
        for k, r in enumerate(sel[j:j + 20]):
            img = np.asarray(Image.open(r["source"]))
            canvas.paste(tile(img, r["proposal_xyxy"], r["frame"], r["ordinal"], a.gain),
                         ((k % 5) * TILE[0], (k // 5) * TILE[1]))
        p = cand / f"r_{j // 20:02d}.jpg"
        canvas.save(p, quality=94)
        sheets.append({"sheet": p.name, "sha256": sha(p), "samples": [r["sample"] for r in sel[j:j + 20]]})

    (cand / "proposals.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (cand / "sheets.json").write_text(json.dumps(sheets, ensure_ascii=False, indent=2), encoding="utf-8")
    kinds = {}
    for r in rows:
        kinds[r["diagnostics"]["kind"]] = kinds.get(r["diagnostics"]["kind"], 0) + 1
    print(json.dumps({"recording": a.recording, "samples": len(rows), "sheets": len(sheets),
                      "on_sheets": len(sel), "kinds": kinds, "out": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
