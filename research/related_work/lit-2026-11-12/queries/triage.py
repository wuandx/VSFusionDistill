#!/usr/bin/env python3
"""Rank the arXiv candidate pool against the CMOLD frame (camera/optical teacher
-> sonar student, object-level distillation, UXO detection) and emit a shortlist.

Scoring is deliberately transparent: a coarse gate (must touch sonar/underwater
OR be an object-level distillation paper) plus additive topical weights. Every
weight is printed alongside the row so the ranking can be argued with.
"""
import json
import os
import re
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))

EXCLUDE = set("""2503.22880 2504.10974 2505.06694 2506.01445 2507.20651 2508.18293
2510.25797 2512.01291 2512.13542 2601.12715 2602.15555 2602.22674 2605.19712
2605.24928 2606.01398 2606.23006 2607.10575 2607.18075 2607.18700 2607.25937
2607.29393 2608.05365 2608.08106 2608.12436 2608.19710 2608.20206 2608.22072
2608.23215 2608.23479 2608.24325 2608.24756 2608.25367 2608.27793 2608.27795
2608.29433 2609.01800 2609.04411 2609.06253 2609.06261 2609.14025 2609.17929
2609.18100 2609.18893 2609.21061 2609.21123 2609.24195 2609.25271 2609.39898
2609.40085 2609.40178 2610.01644 2610.07472 2610.10877 2610.19097 2610.22549
2610.23759 2610.25044 2610.31490 2610.35038 2610.36454 2611.00763 2611.02419
2611.10770""".split())

W = [
    ("uxo", r"unexploded ordnance|\buxo\b|unexploded", 6),
    ("sonar", r"sonar", 5),
    ("fls", r"forward[- ]looking|multibeam|side[- ]scan|synthetic aperture sonar", 3),
    ("underwater", r"underwater|subsea|marine|ocean", 2),
    ("kd", r"knowledge distillation|distill", 4),
    ("crossmodal", r"cross[- ]modal|cross[- ]modality", 4),
    ("modalitygap", r"missing modalit|modality gap|modality hallucination|privileged information", 3),
    ("det", r"object detection|detector|yolo|bounding box", 3),
    ("teacher", r"teacher[- ]student|teacher model|student model", 2),
    ("imagetrans", r"image[- ]to[- ]image|image translation|synthetic aperture|simulat", 1),
    ("enhance", r"enhance|restor|degrad|denois", 1),
    ("kd_obj", r"object[- ]level|logit|feature[- ]level|relation", 1),
]

GATE = re.compile(r"sonar|underwater|subsea|marine|unexploded|\buxo\b|distill|cross[- ]modal", re.I)


def score(rec):
    text = (rec["title"] + " " + rec["summary"]).lower()
    hits, total = [], 0
    for name, pat, w in W:
        if re.search(pat, text):
            hits.append(name)
            total += w
    return total, hits


def date_of(rec):
    m = re.search(r"(\d{1,2}) (\w+),? (\d{4})", rec.get("submitted", ""))
    if not m:
        return dt.date(1900, 1, 1)
    d, mon, y = m.groups()
    try:
        return dt.datetime.strptime(f"{d} {mon} {y}", "%d %B %Y").date()
    except ValueError:
        return dt.date(1900, 1, 1)


def main():
    d = json.load(open(os.path.join(HERE, "candidates.json"), encoding="utf-8"))
    rows = []
    seen = set()
    for r in d["pool"]:
        if r["id"] in EXCLUDE or r["id"] in seen:
            continue
        seen.add(r["id"])
        if not GATE.search(r["title"] + " " + r["summary"]):
            continue
        s, hits = score(r)
        r["score"] = s
        r["hits"] = hits
        r["date"] = date_of(r).isoformat()
        rows.append(r)
    rows.sort(key=lambda r: (-r["score"], r["date"]), reverse=False)
    rows.sort(key=lambda r: (-r["score"], -dt.date.fromisoformat(r["date"]).toordinal()))
    json.dump(rows, open(os.path.join(HERE, "ranked.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"gated={len(rows)} of pool={len(d['pool'])} (excluded {len(EXCLUDE)})")
    for r in rows[:70]:
        print(f'{r["score"]:2d} {r["id"]} {r["date"]} [{",".join(r["hits"])}] {r["title"][:110]}')
        print(f'      {r["summary"][:230]}')


if __name__ == "__main__":
    main()
