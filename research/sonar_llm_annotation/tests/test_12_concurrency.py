"""Concurrency: append-only reviews must survive two writers and 20 parallel HTTP posts."""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer

import _util as U

PORT = 8772
FRAMES: list[int] = []
def _frames(rec, n=20):
    """Real frames present on disk (the bomb recording has gaps)."""
    d = U.rec_dir(rec) / "aris_raw"
    frames = sorted(int(p.stem) for p in d.glob("*.pgm") if p.stem.isdigit())
    assert len(frames) >= n, "only %d pgm frames in %s" % (len(frames), rec)
    step = max(1, len(frames) // n)
    return frames[::step][:n]


def _tree(root, rec=U.REC_BOMB, frames=None):
    prop = root / "proposals" / rec
    prop.mkdir(parents=True, exist_ok=True)
    lines = []
    for f in (frames or FRAMES):
        pgm = U.pgm_path(rec, f)
        w, h = U.read_pgm_header(pgm)
        box = [40.0, float(int(h * 0.35)), 90.0, float(int(h * 0.5))]
        lines.append(json.dumps({
            "sample": "%s_%04d" % (rec, f), "recording": rec,
            "category": U.CATEGORY[rec], "aris_frame": f,
            "candidate": {"box_xyxy": box},
            "predicted": {"available": False, "reason": "gantry_not_sonar_frame"},
            "image": {"path": str(pgm), "width": w, "height": h},
            "n_beams": w, "n_rows": h}, ensure_ascii=False))
    (prop / "proposals.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return prop


def test_two_processes_append_without_torn_lines():
    root = U.fresh_dir("conc", "append")
    rec = U.REC_BOMB
    n = 150
    procs = []
    for prefix in ("a", "b"):
        cmd = [sys.executable, str(U.REPO / "tests" / "_child_append.py"),
               str(root), rec, str(n), prefix]
        procs.append(subprocess.Popen(cmd, cwd=str(U.REPO),
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      env={**__import__("os").environ,
                                           "PYTHONIOENCODING": "utf-8"}))
    for p in procs:
        out, err = p.communicate(timeout=180)
        assert p.returncode == 0, "child appender failed: %r" % (err.decode("utf-8", "replace")[-800:])
    path = root / rec / "reviews.jsonl"
    raw = path.read_text(encoding="utf-8")
    lines = [l for l in raw.splitlines() if l.strip()]
    assert len(lines) == 2 * n, "expected %d lines, got %d" % (2 * n, len(lines))
    bad = []
    seen = set()
    for i, line in enumerate(lines):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            bad.append((i, str(exc), line[:120]))
            continue
        assert row["payload"] == "x" * 200, "line %d has a truncated payload" % i
        seen.add((row["sample"], row["i"]))
    assert not bad, "torn/interleaved lines: %r" % (bad[:3],)
    assert len(seen) == 2 * n, "duplicate or missing rows: %d unique of %d" % (len(seen), 2 * n)
    assert raw.count("\n") == 2 * n, "file must end with exactly one newline per row"


def test_twenty_parallel_posts_all_land_as_valid_json():
    if not U.port_is_free(PORT):
        raise AssertionError("port %d is in use; refusing to test" % PORT)
    root = U.fresh_dir("conc", "http")
    rec = U.REC_BOMB
    frames = _frames(rec, 20)
    prop = _tree(root, rec, frames)
    srv = U.server_mod()
    srv.OUT_DIR = root
    srv.CFG.port = PORT
    srv.CFG.operator = "qa-conc"
    srv.CFG.store = srv.ProposalStore(prop.parent)
    srv.CFG.cards_dir = root / "cards"
    srv.CFG.judgments_root = root
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), srv.Handler)
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()

    def post(f):
        sample = "%s_%04d" % (rec, f)
        _w, h = U.read_pgm_header(U.pgm_path(rec, f))
        body = json.dumps({"sample": sample, "recording": rec, "status": "uncertain",
                           "final_box": [40.0, float(int(h * 0.35)), 90.0,
                                         float(int(h * 0.5))],
                           "operator": "qa-conc"}).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:%d/api/review" % PORT, data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return sample, r.status
        except urllib.error.HTTPError as exc:
            return sample, exc.code

    try:
        with ThreadPoolExecutor(max_workers=10) as ex:
            results = list(ex.map(post, frames))
        assert all(code == 201 for _, code in results), (
            "non-201 statuses: %r" % ([(s, c) for s, c in results if c != 201],))
        httpd.shutdown()
    finally:
        httpd.shutdown()
        httpd.server_close()
        th.join(timeout=10)
    assert U.port_is_free(PORT), "port %d is still bound" % PORT

    path = root / rec / "reviews.jsonl"
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == len(frames), "expected %d review lines, got %d" % (len(frames), len(lines))
    samples = []
    for line in lines:
        row = json.loads(line)  # must never raise: every line is complete JSON
        assert row["recording"] == rec
        assert row["grid"]["height"] == 780, "bomb reviews must carry height 780"
        samples.append(row["sample"])
    assert sorted(samples) == sorted("%s_%04d" % (rec, f) for f in frames), (
        "lost or duplicated samples: %d unique" % len(set(samples)))
