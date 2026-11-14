"""Export reviewed sheets (reference format) into a YOLO tree.

Input is what a human actually signed off: `candidates/proposals.json` plus
`review/decisions.json` (decision in {retained, revised, rejected, uncertain},
final_xyxy, review_sheet_sha256).  Output is the usual layout:

    images/<split>/<sample>.png      P5 -> PNG, one image per accepted sample
    labels/<split>/<sample>.txt      `<cls> <cx> <cy> <w> <h>`, all normalised
    data.yaml                        class names, in the manifest's order
    provenance.json                  what this is and what it is not

Three rules, same as the plugin's exporter, for the same reasons:

1. The split is the manifest's per-sample `paired_role`.  A sample with no role
   goes to `unassigned`; it is never silently dropped into `train`.  A sample
   with two different roles is refused (`mixed_paired_role`) rather than
   guessed at.
2. `rejected` and `uncertain` are not exported, and neither is a `retained`
   row without a box: a review that says "I don't know" is a result, not a
   label to train on.
3. `provenance.json` says `candidate_only_not_training_ready: true`.  These
   boxes are the reviewer's answer to "is that the return", not a survey of
   what the object is; there is still no sonar ground truth in this project.

Image height is read per recording from the PGM header: 780 rows on
2023-09-20_171105, 441 on the others.  Hard-coding 780 silently shifts every
y coordinate on a 441-row recording.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin"
if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))

from sonarllm import dataset as D  # noqa: E402

ACCEPTED = ("retained", "revised")
CLASS_ID = {name: i for i, name in enumerate(D.CLASSES)}


def _records(rec_root: Path, full: bool = False) -> tuple[list, dict]:
    if full:
        # interval-signed frames: one blob per frame from proposals_full.jsonl.
        # kind is "arc" by construction (the full pass only ran the arc detector).
        head = json.loads((rec_root / "candidates" / "proposals.json").read_text(encoding="utf-8"))
        cat = head[0].get("category") if head else None
        rows = []
        for line in (rec_root / "candidates" / "proposals_full.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            b = (r["blobs"] or [None])[0]
            if not b:
                continue
            rows.append({"sample": f'{r["recording"]}_{int(r["frame"]):04d}',
                         "recording": r["recording"], "category": cat, "frame": int(r["frame"]),
                         "proposal_xyxy": b["box_xyxy"], "shape_hw": r["shape_hw"],
                         "sheet": None,
                         "source": str(D.REC_ROOT / D.CATEGORY_TO_DIR[cat] / r["recording"]
                                        / "aris_raw" / f'{int(r["frame"]):04d}.pgm'),
                         "diagnostics": {"kind": "arc", "snr": b.get("snr"), "area": b.get("area")}})
        dec_path = rec_root / "review" / "decisions_full.json"
        dec = json.loads(dec_path.read_text(encoding="utf-8")) if dec_path.exists() else {}
        return rows, dec
    props = json.loads((rec_root / "candidates" / "proposals.json").read_text(encoding="utf-8"))
    dec_path = rec_root / "review" / "decisions.json"
    dec = json.loads(dec_path.read_text(encoding="utf-8")) if dec_path.exists() else {}
    return props, dec


def _recording_splits(rec_roots: list[Path]) -> dict:
    """Recording-level split we choose ourselves (D19).

    Every recording lands in exactly one split, so no frame of a recording can
    appear on both sides.  Per category, the recording whose sample count is
    closest to 20% of that category's samples goes to `val`; ties break on
    md5(recording).  The rule is reproducible, and it keeps `val` from being,
    say, one 11-sample recording while 300 mortar samples sit in train.
    """
    counts: dict = {}
    for rec_root in rec_roots:
        props, dec = _records(rec_root)
        if not props:
            continue
        accepted = sum(1 for row in dec.values() if row.get("decision") in ACCEPTED)
        if not accepted:
            continue
        cat = props[0]["category"]
        counts.setdefault(cat, {})[props[0]["recording"]] = accepted
    out: dict = {}
    for _cat, recs in counts.items():
        ordered = sorted(recs, key=lambda r: hashlib.md5(r.encode()).hexdigest())
        if len(ordered) < 2:
            for rec in ordered:
                out[rec] = "train"
            continue
        target = 0.2 * sum(recs.values())
        val_rec = min(ordered, key=lambda r: (abs(recs[r] - target), hashlib.md5(r.encode()).hexdigest()))
        for rec in ordered:
            out[rec] = "val" if rec == val_rec else "train"
    return out


def _keep_balanced(rec_roots: list[Path], full: bool, cap: int | None) -> set | None:
    """Deterministic per-class subsample, so the three classes come out level.

    The material itself is lopsided: the mortar recordings simply run longer and
    their arc is signed over more frames.  Rather than delete the surplus, we keep
    every k-th accepted sample of each over-represented class (k chosen per class,
    sorted by recording then frame), so a rerun picks exactly the same frames.
    """
    if not cap:
        return None
    by_cls: dict = {}
    for rec_root in rec_roots:
        props, dec = _records(rec_root, full=full)
        cat = props[0]["category"] if props else None
        cls = CLASS_ID.get(cat)
        if cls is None:
            continue
        for sample, row in dec.items():
            if row["decision"] in ACCEPTED:
                by_cls.setdefault(cls, []).append(sample)
    keep = set()
    for cls, samples in by_cls.items():
        samples.sort()
        k = max(1, len(samples) // cap)
        keep.update(samples[::k][:cap])
    return keep


def export(dst: Path, rec_roots: list[Path], force: bool = False,
           split_mode: str = "manifest", require_kind: str = "arc",
           full: bool = False, max_per_class: int | None = None) -> dict:
    if dst.exists() and any(dst.iterdir()):
        if not force:
            raise D.ExportRefused(f"{dst} is not empty; pass --force to overwrite")
        # force means "rebuild", not "merge": a stale val/ from an earlier split
        # would silently contaminate the new one.
        shutil.rmtree(dst)

    keep = _keep_balanced(rec_roots, full, max_per_class)
    roles = D.sample_roles()
    rec_split = _recording_splits(rec_roots) if split_mode == "recording" else {}
    sizes: dict = {}
    written = 0
    per_rec: Counter = Counter()
    per_split: Counter = Counter()
    refused: Counter = Counter()
    skipped: Counter = Counter()

    for rec_root in rec_roots:
        props, dec = _records(rec_root, full=full)
        by_sample = {p["sample"]: p for p in props}
        for sample, row in dec.items():
            prop = by_sample.get(sample)
            if prop is None:
                refused["no_proposal"] += 1
                continue
            if keep is not None and sample not in keep:
                skipped["balanced_out"] += 1
                continue
            kind = (prop.get("diagnostics") or {}).get("kind")
            if require_kind not in ("", "any") and kind != require_kind:
                # a signed-off decision on a sample the detector now calls
                # "band"/"noise" would put a whole-sector box in the dataset
                refused[f"kind_{kind}"] += 1
                continue
            if row["decision"] not in ACCEPTED:
                skipped[row["decision"]] += 1
                continue
            box = row.get("final_xyxy") or row.get("original_xyxy")
            if not box:
                refused["accepted_without_box"] += 1
                continue
            if split_mode == "recording":
                split = rec_split.get(prop["recording"], "unassigned")
            else:
                role = roles.get(sample, set())
                if len(role) > 1:
                    refused["mixed_paired_role"] += 1
                    continue
                split = next(iter(role)) if role else "unassigned"
            cls_id = CLASS_ID.get(prop["category"])
            if cls_id is None:
                refused["unknown_category"] += 1
                continue
            src = Path(prop["source"])
            if not src.exists():
                refused["missing_pgm"] += 1
                continue

            img_dir = dst / "images" / split
            lbl_dir = dst / "labels" / split
            img_dir.mkdir(parents=True, exist_ok=True)
            lbl_dir.mkdir(parents=True, exist_ok=True)
            png = img_dir / f"{sample}.png"
            Image.open(src).save(png)
            w, h = D.pgm_size(src)
            sizes[prop["recording"]] = [w, h]
            (lbl_dir / f"{sample}.txt").write_text(D.yolo_line(cls_id, box, w, h) + "\n", encoding="utf-8")
            written += 1
            per_rec[prop["recording"]] += 1
            per_split[split] += 1

    dst.mkdir(parents=True, exist_ok=True)
    if written:
        (dst / "data.yaml").write_text(
            "path: .\ntrain: images/train\nval: images/val\n\nnames:\n"
            + "".join(f"  {i}: {n}\n" for i, n in enumerate(D.CLASSES)),
            encoding="utf-8")
    else:
        (dst / "_EMPTY_DO_NOT_TRAIN.txt").write_text(
            "No accepted review decisions: this export has no images and no labels.\n", encoding="utf-8")

    (dst / "provenance.json").write_text(json.dumps({
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "tool": "tools/export_visible.py",
        "source": "review/decisions.json over candidates/proposals.json",
        "candidate_only_not_training_ready": True,
        "split_source": "ours_recording_level" if split_mode == "recording" else "manifest_paired_role",
        "split_note": ("Recording-level split chosen by this project (D19): each recording is "
                       "entirely in one split, 20% of each category's recordings go to val, picked "
                       "by md5 of the recording id.  The original manifest keeps its own per-sample "
                       "paired_role untouched; this is our division, not the repository's."
                       if split_mode == "recording" else
                       "Split taken from the manifest's per-sample paired_role; samples with no role "
                       "land in unassigned and are not trainable."),
        "recording_split": rec_split,
        "note": ("Candidate boxes reviewed by a human on 20-frame sheets; they answer "
                 "'is this the return', not 'what object is this'. Sonar ground truth "
                 "does not exist in this project (DataSet/mesh-registration.json keeps "
                 "mesh_to_target on HOLD), so these must not be reported as GT."),
        "n_written": written,
        "per_recording": dict(per_rec),
        "per_split": dict(per_split),
        "skipped_by_decision": dict(skipped),
        "refused_by_reason": dict(refused),
        "image_size_by_recording": sizes,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return dict(n_written=written, per_recording=dict(per_rec), per_split=dict(per_split),
                skipped=dict(skipped), refused=dict(refused))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="export reviewed sheets into a YOLO tree")
    ap.add_argument("--root", default=str(ROOT / "out" / "sonar_arc_annotation"),
                    help="folder holding <recording>/candidates + <recording>/review")
    ap.add_argument("--recordings", nargs="*", default=[], help="default: every folder that has decisions")
    ap.add_argument("--dst", required=True)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--max-per-class", type=int, default=None,
                    help="cap each class at N frames (deterministic stride); for a balanced set")
    ap.add_argument("--full", action="store_true", help="export interval-signed frames (proposals_full + decisions_full)")
    ap.add_argument("--require-kind", default="arc",
                    help="only export samples the detector calls this kind; 'any' disables")
    ap.add_argument("--split-mode", choices=("manifest", "recording"), default="manifest",
                    help="manifest = the repository's per-sample paired_role (default); "
                         "recording = our own recording-level split (D19), every recording in one split")
    a = ap.parse_args(argv)
    root = Path(a.root)
    if a.recordings:
        rec_roots = [root / r for r in a.recordings]
    else:
        rec_roots = sorted(p.parent.parent for p in root.glob("*/review/decisions.json")
                           if any(json.loads(p.read_text(encoding="utf-8")).values()))
    if not rec_roots:
        print("no reviewed recordings found", file=sys.stderr)
        return 2
    try:
        res = export(Path(a.dst), rec_roots, force=a.force, split_mode=a.split_mode,
                 require_kind=a.require_kind, full=a.full,
                 max_per_class=a.max_per_class)
    except D.ExportRefused as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
