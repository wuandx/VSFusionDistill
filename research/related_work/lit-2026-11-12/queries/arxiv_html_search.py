#!/usr/bin/env python3
"""arXiv discovery via the HTML search page (API returns 429 from this egress).

Network goes through Windows curl.exe: WSL itself has no egress, and curl.exe
cannot write into the unicode workspace path (silent 0-byte output), so every
response is captured from stdout and written by this script instead.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from html import unescape

CURL = "/mnt/c/Windows/System32/curl.exe"
BASE = "https://arxiv.org/search/"
HERE = os.path.dirname(os.path.abspath(__file__))
RAWDIR = os.path.join(HERE, "html")
os.makedirs(RAWDIR, exist_ok=True)

BUCKETS = {
    "cross_modal_kd": '"cross-modal knowledge distillation"',
    "cross_modality_kd2": '"cross-modality" AND "knowledge distillation"',
    "cross_modality_objdet": '"cross-modality" AND "object detection"',
    "missing_modality_kd": '"missing modality" AND distillation',
    "objdet_kd": '"object detection" AND "knowledge distillation"',
    "privileged_information": '"privileged information"',
    "sonar_objdet": 'sonar AND "object detection"',
    "fls_detection": '"forward-looking sonar" AND detection',
    "sas_detection": '"synthetic aperture sonar" AND detection',
    "uxo": '"unexploded ordnance"',
    "underwater_fusion": 'underwater AND detection AND multimodal',
    "sonar_distill": 'sonar AND distillation',
    "sidescan": '"side-scan sonar" AND detection',
    "mine_detection": '"mine countermeasures" OR "mine detection"',
    "thermal_kd": '"RGB-T" AND distillation',
    "underwater_multimodal_det": '"underwater object detection" AND multimodal',
    "underwater_kd": 'underwater AND "knowledge distillation"',
    "sonar_translation": 'sonar AND "image translation"',
}

RE_ID = re.compile(r"arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5})")
RE_BLOCK = re.compile(r'<li class="arxiv-result">(.*?)</li>', re.S)
RE_TITLE = re.compile(r'<p class="title is-5 mathjax">(.*?)</p>', re.S)
RE_ABS = re.compile(r'<span class="abstract-full has-text-grey-dark mathjax"[^>]*>(.*?)</span>', re.S)
RE_DATE = re.compile(r'Submitted</span>\s*([^;<]+);', re.S)
RE_COMMENTS = re.compile(r'<p class="comments is-size-7">(.*?)</p>', re.S)
RE_AUTHORS = re.compile(r'<p class="authors">(.*?)</p>', re.S)


def clean(s):
    s = re.sub(r"<[^>]+>", "", s)
    s = unescape(s)
    return " ".join(s.split())


def curl(url, tries=3):
    for i in range(tries):
        r = subprocess.run([CURL, "-sL", "--max-time", "90", "-A", "Mozilla/5.0", url],
                           capture_output=True)
        if r.returncode == 0 and len(r.stdout) > 1000:
            return r.stdout
        time.sleep(5 * (i + 1))
    return b""


def fetch(bucket, query, max_pages=2):
    rows = []
    for page in range(max_pages):
        params = {"searchtype": "abstract", "query": query,
                  "start": str(page * 50), "size": "50",
                  "order": "-announced_date_first"}
        url = BASE + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        body = curl(url)
        if not body:
            print(f"  ! fetch failed {bucket} p{page}", file=sys.stderr)
            break
        html = body.decode("utf-8", "replace")
        with open(os.path.join(RAWDIR, f"{bucket}_p{page}.html"), "w", encoding="utf-8") as f:
            f.write(html)
        blocks = RE_BLOCK.findall(html)
        if not blocks:
            break
        for b in blocks:
            m = RE_ID.search(b)
            if not m:
                continue
            t = RE_TITLE.search(b)
            ab = RE_ABS.search(b)
            d = RE_DATE.search(b)
            c = RE_COMMENTS.search(b)
            au = RE_AUTHORS.search(b)
            rows.append({
                "id": m.group(1),
                "title": clean(t.group(1)) if t else "",
                "summary": clean(ab.group(1))[:900] if ab else "",
                "submitted": clean(d.group(1)) if d else "",
                "comment": clean(c.group(1))[:200] if c else "",
                "authors": clean(au.group(1))[:300] if au else "",
                "bucket": bucket,
            })
        time.sleep(3)
    return rows


def main():
    pool = {}
    log = []
    for bucket, q in BUCKETS.items():
        rows = fetch(bucket, q)
        log.append({"bucket": bucket, "query": q, "hits": len(rows)})
        for r in rows:
            if r["id"] in pool:
                if bucket not in pool[r["id"]]["buckets"]:
                    pool[r["id"]]["buckets"].append(bucket)
            else:
                r["buckets"] = [bucket]
                pool[r["id"]] = r
        print(f"{bucket}: {len(rows)}", file=sys.stderr)
    with open(os.path.join(HERE, "candidates.json"), "w", encoding="utf-8") as f:
        json.dump({"queries": log, "pool": list(pool.values())}, f, ensure_ascii=False, indent=1)
    print(f"pool={len(pool)}", file=sys.stderr)


if __name__ == "__main__":
    main()
