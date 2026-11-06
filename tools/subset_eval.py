#!/usr/bin/env python
"""Re-score a saved prediction file on a chosen subset of recordings.

Why this exists: the val split used for the E13 teacher comparison contains
two recordings (2023-09-20_180722, 2023-09-21_105856) that were part of the
advisor's old sample-platform teacher training set.  Comparing two teachers
on the full val therefore mixes a clean subset with a leaked one; this tool
recomputes the same COCO metrics on any recording subset so both models can
be scored on exactly the same 8 clean recordings (720 frames).

The metric code is imported from the project itself, so the numbers stay
identical to tools/test.py (same gt=all / gt=blob variants, same imgIds
restriction, same pycocotools summary).

Usage::

    python tools/subset_eval.py \
        --gt data/paired/uxo_full_dense/camera.json \
        --pred ~/mycode/eval_e13_teacher_val/pred.camera.d0.json \
        --frame-meta data/paired/uxo_full_dense/frame_meta.csv \
        --side camera --split val \
        --exclude 2023-09-20_180722,2023-09-21_105856
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aodet.evaluation.per_branch_metric import (  # noqa: E402
    blob_eval_img_ids, coco_ap, filter_gt_sources)


def load_frame_meta(path: str) -> list:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def pick_ids(rows: list, side: str, split: str, keep, drop) -> list:
    col = "camera_image_id" if side == "camera" else "sonar_image_id"
    ids = []
    for r in rows:
        if r["split"] != split:
            continue
        rec = r["recording"]
        if keep and rec not in keep:
            continue
        if drop and rec in drop:
            continue
        ids.append(int(r[col]))
    return ids


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", required=True)
    ap.add_argument("--pred", required=True)
    ap.add_argument("--frame-meta", required=True)
    ap.add_argument("--side", choices=("camera", "sonar"), default="camera")
    ap.add_argument("--split", default="val")
    ap.add_argument("--keep", default="", help="comma separated recordings")
    ap.add_argument("--exclude", default="", help="comma separated recordings")
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    keep = {s for s in args.keep.split(",") if s}
    drop = {s for s in args.exclude.split(",") if s}

    rows = load_frame_meta(args.frame_meta)
    ids = pick_ids(rows, args.side, args.split, keep, drop)
    recs = sorted({r["recording"] for r in rows
                   if r["split"] == args.split
                   and int(r["camera_image_id" if args.side == "camera"
                           else "sonar_image_id"]) in set(ids)})

    with open(args.gt, encoding="utf-8") as f:
        gt = json.load(f)
    with open(args.pred, encoding="utf-8") as f:
        preds = json.load(f)

    variants = [("all", gt, ids)]
    if args.side == "sonar":
        variants.append(("blob", filter_gt_sources(gt, ("blob",)),
                         blob_eval_img_ids(gt, ids)))

    out = {"label": args.label, "side": args.side, "split": args.split,
           "recordings": recs, "n_images": len(ids), "metrics": {}}
    for name, gt_v, ids_v in variants:
        m = coco_ap(gt_v, preds, img_ids=ids_v)
        out["metrics"][name] = {k: m[k] for k in ("AP", "AP50", "AP75",
                                                 "AR@100")}
        print(f"[{args.label or args.pred}] {args.side} gt={name} "
              f"imgs={len(ids_v)} recs={len(recs)} "
              f"AP={m['AP']:.4f} AP50={m['AP50']:.4f} "
              f"AP75={m['AP75']:.4f} AR@100={m['AR@100']:.4f}")
    print("JSON " + json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
