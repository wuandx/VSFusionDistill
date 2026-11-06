#!/usr/bin/env python
"""Build the dashboard's "teacher tier" table from the saved eval artifacts.

Two YOLOX-L dual-stream teachers, identical architecture and near-identical
training steps, differ only in how many recordings they saw:

  * e13_dense   : ours, dense platform, 27 recordings / 7,960 frames, 20,895 it
  * e10_sample  : advisor's, old sample platform, 3 recordings / 1,680 frames,
                  21,000 it -- never evaluated on val on its own machine

Both were scored with the same code (tools/test.py + pycocotools) on the same
val frames.  Three arenas are reported because two of the ten val recordings
belong to the advisor teacher's training set:

  * val_all  : 900 frames / 10 recordings
  * clean8   : 720 frames / 8 recordings  (neither model ever saw them)
  * leaked2  : 180 frames / 2 recordings  (in the advisor teacher's train set)

Run inside WSL, from the repo root, with the GPU venv:

    PYTHONPATH=. .venv-gpu/bin/python tools/dashboard/gen_teachers.py
"""
from __future__ import annotations

import json
import os
import sys

REPO = os.environ.get("VSF_REPO", os.path.expanduser("~/mycode/VSFusionDistill"))
sys.path.insert(0, REPO)

from aodet.evaluation.per_branch_metric import (  # noqa: E402
    blob_eval_img_ids, coco_ap, filter_gt_sources)

DATA = os.path.join(REPO, "data/paired/uxo_full_dense")
OUT = os.environ.get(
    "DASH_TEACHERS_JSON",
    "/mnt/d/agent_workspace/水下/声呐目标检测/tools/dashboard/data/teachers.json",
)

MODELS = [
    {"key": "e13_dense",
     "label": "我的教师（dense 平台）",
     "detail": "27 条录音 / 7,960 帧 · 21 ep × 995 = 20,895 iter",
     "eval": "/home/ty/mycode/eval_e13_teacher_val"},
    {"key": "e10_sample",
     "label": "导师旧教师（sample 平台）",
     "detail": "3 条录音 / 1,680 帧 · 100 ep × 210 = 21,000 iter",
     "eval": "/home/ty/mycode/eval_5090_teacher_val"},
]

SUBSETS = [
    {"key": "val_all", "label": "全部 val", "frames": 900, "recs": 10,
     "keep": None, "drop": None,
     "note": "包含 2 条在导师旧教师训练集里的录音"},
    {"key": "clean8", "label": "干净 8 条", "frames": 720, "recs": 8,
     "keep": None, "drop": ("2023-09-20_180722", "2023-09-21_105856"),
     "note": "两个教师都没训过，唯一公平考场"},
    {"key": "leaked2", "label": "泄漏 2 条", "frames": 180, "recs": 2,
     "keep": ("2023-09-20_180722", "2023-09-21_105856"), "drop": None,
     "note": "在导师旧教师的训练集里"},
]


def split_ids(split: str) -> list:
    import csv
    path = os.path.join(DATA, "frame_meta.csv")
    with open(path, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r["split"] == split]


def ids_for(rows, subset, side):
    col = "camera_image_id" if side == "camera" else "sonar_image_id"
    out = []
    for r in rows:
        rec = r["recording"]
        if subset["keep"] and rec not in subset["keep"]:
            continue
        if subset["drop"] and rec in subset["drop"]:
            continue
        out.append(int(r[col]))
    return out


def main() -> int:
    rows = split_ids("val")
    payload = {"note": "同一份 tools/test.py + pycocotools；三档考场只改录音子集，"
                       "不改权重、不改预处理。",
               "models": [], "subsets": [], "rows": []}

    gts = {side: json.load(open(os.path.join(DATA, f"{side}.json"),
                                encoding="utf-8"))
           for side in ("camera", "sonar")}

    for m in MODELS:
        payload["models"].append({"key": m["key"], "label": m["label"],
                                  "detail": m["detail"]})
    for s in SUBSETS:
        payload["subsets"].append({k: s[k] for k in
                                   ("key", "label", "frames", "recs", "note")})

    for m in MODELS:
        for s in SUBSETS:
            cells = {}
            for side, fname in (("camera", "pred.camera.d0.json"),
                                ("sonar", "pred.sonar_uncoupled.d0.json")):
                ids = ids_for(rows, s, side)
                pred_path = os.path.join(m["eval"], fname)
                preds = json.load(open(pred_path, encoding="utf-8"))
                gt = gts[side]
                all_m = coco_ap(gt, preds, img_ids=ids)
                cells[side] = {"AP": round(all_m["AP"], 4),
                               "AP50": round(all_m["AP50"], 4),
                               "n": len(ids)}
                if side == "sonar":
                    blob_gt = filter_gt_sources(gt, ("blob",))
                    blob_ids = blob_eval_img_ids(gt, ids)
                    bm = coco_ap(blob_gt, preds, img_ids=blob_ids)
                    cells["sonar_blob"] = {"AP": round(bm["AP"], 4),
                                           "AP50": round(bm["AP50"], 4),
                                           "n": len(blob_ids)}
            payload["rows"].append({"model": m["key"], "subset": s["key"],
                                    "cells": cells})
            print(m["key"], s["key"],
                  "cam AP50", cells["camera"]["AP50"],
                  "sonar_blob AP50", cells["sonar_blob"]["AP50"])

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
