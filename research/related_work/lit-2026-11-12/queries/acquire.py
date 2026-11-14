#!/usr/bin/env python3
"""Acquire arXiv papers (PDF + LaTeX source + metadata) into related_work/<slug>/.

Every byte comes through Windows curl.exe (WSL has no egress); responses are
captured on stdout and written by Python, because curl.exe silently produces
0-byte output when -o points inside this unicode workspace path.

Usage: python3 acquire.py [id ...]     (defaults to ../selected.json)
Writes: related_work/<slug>/{paper.pdf,source/**,meta.json}
        ../acquisition-log.jsonl  (one line per attempt, failures included)
"""
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import time
import datetime as dt

CURL = "/mnt/c/Windows/System32/curl.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
LIT = os.path.dirname(HERE)
RW = os.path.dirname(LIT)
LOG = os.path.join(LIT, "acquisition-log.jsonl")


def curl(url, tries=3, timeout=180):
    last = ""
    for i in range(tries):
        r = subprocess.run([CURL, "-sL", "--max-time", str(timeout),
                            "-A", "Mozilla/5.0 (research; contact via arxiv)", url],
                           capture_output=True)
        if r.returncode == 0 and len(r.stdout) > 500:
            return r.stdout, ""
        last = f"rc={r.returncode} bytes={len(r.stdout)} {r.stderr[:120]!r}"
        # arXiv throttles bursts: back off hard
        time.sleep(6 * (i + 1))
    return b"", last


def sha256(b):
    return hashlib.sha256(b).hexdigest()


RE_TITLE = re.compile(r'<meta name="citation_title" content="([^"]*)"')
RE_AUTH = re.compile(r'<meta name="citation_author" content="([^"]*)"')
RE_DATE = re.compile(r'<meta name="citation_date" content="([^"]*)"')
RE_ABS = re.compile(r'<meta name="citation_abstract" content="([^"]*)"')
RE_DOI = re.compile(r'<meta name="citation_doi" content="([^"]*)"')
RE_JR = re.compile(r'<meta name="citation_journal_title" content="([^"]*)"')
RE_VER = re.compile(r'\[v(\d+)\]</a>\s*</strong>|Submission history', re.S)
RE_HIST = re.compile(r"\[v(\d+)\]\s*<strong>.*?</strong>\s*(.*?)</li>", re.S)


def slugify(t):
    t = re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-").lower()
    return re.sub(r"-{2,}", "-", t)[:60]


def get_abs(arxiv_id):
    body, err = curl(f"https://arxiv.org/abs/{arxiv_id}")
    if not body:
        return None, err
    h = body.decode("utf-8", "replace")
    out = {
        "arxiv_id": arxiv_id,
        "title": (RE_TITLE.search(h) or [None, ""])[1] if RE_TITLE.search(h) else "",
        "authors": RE_AUTH.findall(h),
        "date": (RE_DATE.search(h).group(1) if RE_DATE.search(h) else ""),
        "doi": (RE_DOI.search(h).group(1) if RE_DOI.search(h) else ""),
        "journal": (RE_JR.search(h).group(1) if RE_JR.search(h) else ""),
        "versions": [m[0] for m in RE_HIST.findall(h)],
    }
    m = re.search(r'<blockquote class="abstract[^"]*">(.*?)</blockquote>', h, re.S)
    if m:
        out["abstract"] = " ".join(re.sub(r"<[^>]+>", " ", m.group(1)).split())
    m = re.search(r'<td class="tablecell comments[^"]*">(.*?)</td>', h, re.S)
    if m:
        out["comments"] = " ".join(re.sub(r"<[^>]+>", " ", m.group(1)).split())
    return out, ""


def extract_eprint(blob, dest):
    """Return kind: 'tar' | 'tex' | 'pdf' | 'gz'; write source tree into dest."""
    os.makedirs(dest, exist_ok=True)
    head = blob[:4]
    if blob[:2] == b"\x1f\x8b":
        try:
            tf = tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz")
            members = [m for m in tf.getmembers() if m.isfile()]
            for m in members:
                name = m.name.replace("\\", "/")
                if name.startswith("/") or ".." in name.split("/"):
                    continue
                target = os.path.join(dest, name)
                os.makedirs(os.path.dirname(target) or dest, exist_ok=True)
                f = tf.extractfile(m)
                if f:
                    with open(target, "wb") as out:
                        out.write(f.read())
            return "tar", [m.name for m in members]
        except tarfile.TarError:
            # single gzipped tex
            import gzip
            try:
                data = gzip.decompress(blob)
            except OSError:
                return "gz", []
            name = "main.tex"
            with open(os.path.join(dest, name), "wb") as f:
                f.write(data)
            return "tex-gz", [name]
    if head == b"%PDF":
        return "pdf", []
    if b"\\documentclass" in blob[:4000] or blob.lstrip()[:200].startswith(b"%") or b"\\begin{document}" in blob:
        with open(os.path.join(dest, "main.tex"), "wb") as f:
            f.write(blob)
        return "tex", ["main.tex"]
    return "unknown", []


def main(entries):
    os.makedirs(LIT, exist_ok=True)
    results = []
    for ent in entries:
        aid = ent["id"] if isinstance(ent, dict) else ent
        t0 = time.time()
        meta, err = get_abs(aid)
        if not meta:
            results.append({"arxiv_id": aid, "ok": False, "stage": "abs", "error": err})
            print(f"[abs-fail] {aid} {err}", file=sys.stderr)
            open(LOG, "a", encoding="utf-8").write(json.dumps(results[-1], ensure_ascii=False) + "\n")
            continue
        slug = (ent.get("slug") if isinstance(ent, dict) else "") or slugify(meta["title"]) or aid.replace(".", "-")
        outdir = os.path.join(RW, slug)
        os.makedirs(outdir, exist_ok=True)
        rec = {"arxiv_id": aid, "slug": slug, "ok": True, "fetched_at": dt.datetime.now().isoformat(timespec="seconds")}
        if isinstance(ent, dict):
            rec["tier"] = ent.get("tier", "")
            rec["why_relevant"] = ent.get("why", "")
        rec.update({k: meta[k] for k in ("title", "authors", "date", "doi", "journal", "abstract", "comments", "versions") if k in meta})

        ver = meta["versions"][-1] if meta.get("versions") else ""
        pdf_url = f"https://arxiv.org/pdf/{aid}" + (f"v{ver}" if ver else "")
        pdf, perr = curl(pdf_url)
        if pdf and pdf[:4] == b"%PDF":
            p = os.path.join(outdir, "paper.pdf")
            with open(p, "wb") as f:
                f.write(pdf)
            rec["pdf"] = {"url": pdf_url, "bytes": len(pdf), "sha256": sha256(pdf)}
        else:
            rec["pdf"] = {"url": pdf_url, "error": perr or "not a pdf"}
        time.sleep(2)

        ep, eerr = curl(f"https://arxiv.org/e-print/{aid}")
        srcdir = os.path.join(outdir, "source")
        if ep:
            kind, files = extract_eprint(ep, srcdir)
            rec["eprint"] = {"url": f"https://arxiv.org/e-print/{aid}", "bytes": len(ep),
                             "sha256": sha256(ep), "kind": kind, "n_files": len(files)}
            texs = []
            for root, _, fs in os.walk(srcdir):
                for fn in fs:
                    if fn.endswith(".tex"):
                        texs.append(os.path.relpath(os.path.join(root, fn), srcdir))
            rec["eprint"]["tex_files"] = sorted(texs)
            if kind == "pdf":
                os.remove(os.path.join(srcdir, "main.tex")) if os.path.exists(os.path.join(srcdir, "main.tex")) else None
                rec["eprint"]["note"] = "e-print was a PDF, no LaTeX available"
        else:
            rec["eprint"] = {"url": f"https://arxiv.org/e-print/{aid}", "error": eerr}

        with open(os.path.join(outdir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=1)
        open(LOG, "a", encoding="utf-8").write(json.dumps(rec, ensure_ascii=False) + "\n")
        results.append(rec)
        texn = len(rec.get("eprint", {}).get("tex_files", []) or [])
        print(f'[ok] {aid} {slug} pdf={rec["pdf"].get("bytes",0)//1024}KB tex={texn} ({time.time()-t0:.0f}s)', file=sys.stderr)
        time.sleep(4)
    return results


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        args = json.load(open(os.path.join(LIT, "selected.json"), encoding="utf-8"))
    else:
        args = [{"id": a} for a in args]
    main(args)
