#!/usr/bin/env python3
"""Run arXiv API queries via Windows curl.exe (WSL has no direct egress).

Writes one XML per query into ./xml/ and a merged candidates.json.
"""
import json
import os
import re
import subprocess
import sys
import urllib.parse
import xml.etree.ElementTree as ET

CURL = "/mnt/c/Windows/System32/curl.exe"
API = "https://export.arxiv.org/api/query"
HERE = os.path.dirname(os.path.abspath(__file__))
XMLDIR = os.path.join(HERE, "xml")
os.makedirs(XMLDIR, exist_ok=True)

QUERIES = {
    "cross_modal_kd": 'abs:"cross-modal knowledge distillation"',
    "cross_modality_det_distill": 'abs:"cross-modality" AND abs:"object detection" AND abs:distillation',
    "missing_modality_kd": 'abs:"missing modality" AND abs:"knowledge distillation"',
    "objdet_kd": 'abs:"object detection" AND abs:"knowledge distillation" AND abs:teacher',
    "privileged_information_det": 'abs:"privileged information" AND abs:detection',
    "sonar_objdet": 'abs:sonar AND abs:"object detection"',
    "fls_detection": 'abs:"forward-looking sonar" AND abs:detection',
    "sas_detection": 'abs:"synthetic aperture sonar" AND abs:detection',
    "uxo": 'abs:"unexploded ordnance"',
    "underwater_det_fusion": 'abs:"underwater object detection" AND (abs:multimodal OR abs:fusion)',
    "sonar_kd": 'abs:sonar AND abs:"knowledge distillation"',
    "cross_modal_distillation": 'abs:"cross-modal distillation"',
    "sidescan_detection": 'abs:"side-scan sonar" AND abs:detection',
    "mine_sonar": 'abs:"mine countermeasure" OR (abs:"mine detection" AND abs:sonar)',
    "thermal_kd": 'abs:"RGB-thermal" AND abs:distillation',
    "objdet_kd_broad": 'abs:"knowledge distillation" AND abs:"object detection"',
    "sonar_semantic": 'abs:sonar AND (abs:detection OR abs:recognition) AND abs:"deep learning"',
    "uxo_detection": 'abs:"UXO" AND abs:detection',
}


def fetch(name, query, max_results=60):
    params = {
        "search_query": query,
        "start": "0",
        "max_results": str(max_results),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = API + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    out = os.path.join(XMLDIR, f"{name}.xml")
    r = subprocess.run([CURL, "-sL", "--max-time", "90", "-o", out, url],
                       capture_output=True, text=True)
    ok = os.path.exists(out) and os.path.getsize(out) > 200
    if ok:
        with open(out, "rb") as f:
            head = f.read(400)
        ok = b"<feed" in head or b"<?xml" in head
    return {"name": name, "query": query, "url": url, "ok": ok,
            "bytes": os.path.getsize(out) if os.path.exists(out) else 0,
            "stderr": r.stderr.strip()[:200]}


NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def parse(xml_path):
    try:
        root = ET.parse(xml_path).getroot()
    except Exception as e:  # noqa: BLE001
        return [], str(e)
    rows = []
    for e in root.findall("a:entry", NS):
        aid = e.findtext("a:id", default="", namespaces=NS)
        m = re.search(r"abs/([0-9]{4}\.[0-9]{4,5})", aid)
        rows.append({
            "id": m.group(1) if m else aid,
            "title": " ".join((e.findtext("a:title", default="", namespaces=NS) or "").split()),
            "published": e.findtext("a:published", default="", namespaces=NS),
            "updated": e.findtext("a:updated", default="", namespaces=NS),
            "summary": " ".join((e.findtext("a:summary", default="", namespaces=NS) or "").split()),
            "primary": (e.find("arxiv:primary_category", NS).get("term")
                        if e.find("arxiv:primary_category", NS) is not None else ""),
            "comment": " ".join((e.findtext("arxiv:comment", default="", namespaces=NS) or "").split()),
            "authors": [a.findtext("a:name", default="", namespaces=NS)
                        for a in e.findall("a:author", NS)][:6],
        })
    return rows, None


def main():
    log = []
    pool = {}
    for name, q in QUERIES.items():
        info = fetch(name, q)
        log.append(info)
        if not info["ok"]:
            continue
        rows, err = parse(os.path.join(XMLDIR, f"{name}.xml"))
        if err:
            info["parse_error"] = err
            continue
        info["hits"] = len(rows)
        for r in rows:
            r.setdefault("buckets", [])
            if r["id"] in pool:
                pool[r["id"]]["buckets"].append(name)
            else:
                r["buckets"] = [name]
                pool[r["id"]] = r
        print(f"{name}: {len(rows)} hits", file=sys.stderr)

    with open(os.path.join(HERE, "candidates.json"), "w", encoding="utf-8") as f:
        json.dump({"queries": log, "pool": list(pool.values())}, f, ensure_ascii=False, indent=1)
    print(f"pool={len(pool)} queries_ok={sum(1 for x in log if x['ok'])}/{len(log)}", file=sys.stderr)


if __name__ == "__main__":
    main()
