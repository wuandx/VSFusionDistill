"""The review service: in-process on 8772 (full API) and the real main() on 8773."""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import _util as U

PORT = 8772
PORT_SUB = 8773
CACHE: dict[str, object] = {}


def _tree():
    if CACHE:
        return CACHE
    ds = U.plugin().dataset
    cards_mod = U.eng("cards")
    root = U.fresh_dir("srv")
    rec = U.REC_BOMB
    frames = [f for f in (622, 900, 300) if U.pgm_path(rec, f).is_file()]
    assert frames, "no pgm frames for %s" % rec
    prop = root / "proposals" / rec
    prop.mkdir(parents=True, exist_ok=True)
    cards_dir = root / "cards"
    cards_dir.mkdir(parents=True)
    lines = []
    for f in frames:
        pgm = U.pgm_path(rec, f)
        w, h = U.read_pgm_header(pgm)
        sample = "%s_%04d" % (rec, f)
        box = [40.0, float(int(h * 0.35)), 90.0, float(int(h * 0.5))]
        recobj = {"sample": sample, "recording": rec, "category": U.CATEGORY[rec],
                  "aris_frame": f, "candidate": {"box_xyxy": box},
                  "predicted": {"available": False, "reason": "gantry_not_sonar_frame"},
                  "image": {"path": str(pgm), "width": w, "height": h},
                  "n_beams": w, "n_rows": h}
        lines.append(json.dumps(recobj, ensure_ascii=False))
        cards_mod.render(sample, recobj, cards_dir / ("%s.png" % sample), scale=2)
        jdir = root / rec / "judgments"
        jdir.mkdir(parents=True, exist_ok=True)
        (jdir / ("%s.json" % sample)).write_text(json.dumps(
            {"sample": sample, "verdict": "object", "shape": "blob", "box": box,
             "confidence": 0.7}), encoding="utf-8")
    (prop / "proposals.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    CACHE.update(root=root, rec=rec, frames=frames, prop=prop, cards=cards_dir,
                 samples=["%s_%04d" % (rec, f) for f in frames])
    return CACHE


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


def _post(url, body):
    data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"raw": raw}


def _start():
    st = _tree()
    srv = U.server_mod()
    srv.OUT_DIR = st["root"]
    srv.CFG.port = PORT
    srv.CFG.operator = "qa-server"
    srv.CFG.store = srv.ProposalStore(st["prop"].parent)
    srv.CFG.cards_dir = st["cards"]
    srv.CFG.judgments_root = st["root"]
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), srv.Handler)
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    return httpd, th, srv


def _stop(httpd, th):
    httpd.shutdown()
    httpd.server_close()
    th.join(timeout=10)


# --------------------------------------------------------------------------- 8772
def test_static_index_health_and_unknown_routes():
    if not U.port_is_free(PORT):
        raise AssertionError("port %d is in use; refusing to test" % PORT)
    httpd, th, srv = _start()
    base = "http://127.0.0.1:%d" % PORT
    try:
        code, body, hdr = _get(base + "/")
        assert code == 200, "GET / -> %r" % code
        assert b"<" in body, "GET / returned no HTML"
        code, body, _ = _get(base + "/api/health")
        assert code == 200
        health = json.loads(body)
        assert health["ok"] is True and health["service"] == "review"
        assert health["pid"] == __import__("os").getpid()
        for bad in ("/nope", "/api/nope", "/static/missing.js"):
            code, body, _ = _get(base + bad)
            assert code == 404, "GET %s -> %r (expected 404)" % (bad, code)
    finally:
        _stop(httpd, th)
    assert U.port_is_free(PORT), "port %d still bound after shutdown" % PORT


def test_proposals_record_card_and_judgment_endpoints():
    st = _tree()
    httpd, th, srv = _start()
    base = "http://127.0.0.1:%d" % PORT
    sample = st["samples"][0]
    try:
        code, body, _ = _get(base + "/api/proposals")
        assert code == 200
        props = json.loads(body)
        assert props["count"] == len(st["samples"]), "count=%r" % props["count"]
        assert props["recordings"][0]["found"] is True
        rec0 = props["records"][0]
        assert rec0["grid"]["height"] == 780, "bomb grid height %r" % (rec0["grid"],)

        code, body, _ = _get(base + "/api/record?sample=" + sample)
        assert code == 200, "GET /api/record -> %r" % code
        assert json.loads(body)["raw"]["sample"] == sample
        code, body, _ = _get(base + "/api/record?sample=does_not_exist_9999")
        assert code == 404, "unknown sample record -> %r" % code

        code, body, hdr = _get(base + "/api/card?sample=" + sample)
        assert code == 200, "GET /api/card -> %r" % code
        assert hdr.get("Content-Type") == "image/png"
        assert body[:8] == b"\x89PNG\r\n\x1a\n", "api/card did not return a PNG"

        code, body, _ = _get(base + "/api/judgment?sample=" + sample)
        assert code == 200, "GET /api/judgment -> %r" % code
        assert json.loads(body)["judgment"]["verdict"] == "object"

        code, body, _ = _get(base + "/api/reviews?recording=" + st["rec"])
        assert code == 200, "GET /api/reviews -> %r" % code
        assert json.loads(body)["ok"] is True
        code, body, _ = _get(base + "/api/card?sample=nope")
        assert code == 404, "missing card -> %r" % code
    finally:
        _stop(httpd, th)


def test_post_validation_matrix():
    st = _tree()
    httpd, th, srv = _start()
    base = "http://127.0.0.1:%d/api/review" % PORT
    sample = st["samples"][-1]
    try:
        code, body = _post(base, {"status": "accept", "final_box": [1, 2, 3, 4]})
        assert code == 400 and "sample" in body["error"], (code, body)
        code, body = _post(base, {"sample": sample, "status": "maybe",
                                  "final_box": [1, 2, 3, 4]})
        assert code == 400 and "status" in body["error"], (code, body)
        code, body = _post(base, {"sample": sample, "status": "accept", "final_box": [1, 2, 3]})
        assert code == 400 and "final_box" in body["error"], (code, body)
        code, body = _post(base, {"sample": sample, "status": "accept",
                                  "final_box": [5, 5, 5, 9]})
        assert code == 400 and "degenerate" in body["error"], (code, body)
        code, body = _post(base, {"sample": sample, "status": "accept",
                                  "final_box": [1, float("inf"), 3, 4]})
        assert code == 400, "infinite box accepted: %r" % (body,)
        code, body = _post(base, {"sample": "2023-01-01_000000_0001", "status": "accept",
                                  "final_box": [1, 2, 3, 4]})
        assert code == 404, "unknown sample -> %r %r" % (code, body)
        code, body = _post(base, b"[]")
        assert code == 400 and "JSON object" in body["error"], (code, body)
        code, body = _post(base, {"sample": sample, "status": "reject",
                                  "final_box": [40.0, 273.0, 90.0, 390.0],
                                  "operator": "qa-server"})
        assert code == 201, "valid POST -> %r %r" % (code, body)
        assert body["saved"]["status"] == "reject"
        assert body["saved"]["data_source"] == "human"
        assert body["saved"]["grid"]["height"] == 780
    finally:
        _stop(httpd, th)
    rows = (st["root"] / st["rec"] / "reviews.jsonl").read_text(encoding="utf-8").splitlines()
    assert rows, "no review line was written"
    json.loads(rows[-1])  # last line must be complete JSON


# --------------------------------------------------------------------------- 8773
def test_real_service_process_on_8773_starts_answers_and_dies():
    st = _tree()
    if not U.port_is_free(PORT_SUB):
        raise AssertionError("port %d is in use; refusing to test" % PORT_SUB)
    cmd = [sys.executable, str(U.REPO / "tests" / "_serve_child.py"),
           str(PORT_SUB), str(st["root"])]
    proc = subprocess.Popen(cmd, cwd=str(U.REPO), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    base = "http://127.0.0.1:%d" % PORT_SUB
    try:
        deadline = time.time() + 60
        up = False
        while time.time() < deadline:
            if proc.poll() is not None:
                out, err = proc.communicate()
                raise AssertionError("service died at startup: rc=%r\n%s\n%s"
                                     % (proc.returncode,
                                        out.decode("utf-8", "replace")[-1500:],
                                        err.decode("utf-8", "replace")[-1500:]))
            try:
                code, body, _ = _get(base + "/api/health")
                if code == 200:
                    up = True
                    break
            except OSError:
                pass
            time.sleep(0.3)
        assert up, "service on %d never answered /api/health" % PORT_SUB
        health = json.loads(body)
        assert health["pid"] == proc.pid, "health reports pid %r, process is %r" % (
            health["pid"], proc.pid)
        code, _, _ = _get(base + "/")
        assert code == 200, "GET / -> %r" % code
        code, _, _ = _get(base + "/api/nope")
        assert code == 404, "GET /api/nope -> %r" % code
        code, body = _post(base + "/api/review", {"status": "accept", "final_box": [1, 2, 3, 4]})
        assert code == 400, "POST without sample -> %r %r" % (code, body)
        pid_file = st["root"] / "tmp" / ("server-%d.pid" % PORT_SUB)
        assert pid_file.is_file(), "service did not write its per-port pid record"
        assert int(pid_file.read_text(encoding="utf-8").strip()) == proc.pid
        # A second instance must refuse the busy port rather than pick another one.
        proc2 = subprocess.Popen([sys.executable, str(U.REPO / "tests" / "_serve_child.py"),
                                  str(PORT_SUB), str(st["root"])],
                                 cwd=str(U.REPO), stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,
                                 env={**__import__("os").environ,
                                      "PYTHONIOENCODING": "utf-8"})
        t2 = time.time() + 20
        while time.time() < t2 and proc2.poll() is None:
            time.sleep(0.25)
        alive2 = proc2.poll() is None
        if alive2:
            proc2.kill()
        text = proc2.communicate()[0].decode("utf-8", "replace")
        assert not alive2, (
            "a second service bound the already-used port %d and kept serving "
            "(rc=None after 20s). On Windows HTTPServer.allow_reuse_address=1 maps to "
            "SO_REUSEADDR, which lets two processes bind the same port, so the "
            "'refusing to auto-switch ports' guard never fires. Output: %s"
            % (PORT_SUB, text[-400:]))
        assert proc2.returncode == 2, "second instance on a busy port -> rc %r" % proc2.returncode
        # Two correct refusals exist: the pre-bind probe ("already in use") and the
        # bind itself failing ("cannot bind").  The port may also be held by a socket
        # that is not answering, which only the bind path sees.  Either is acceptable
        # as long as the process exits 2 and says it will not switch ports.
        assert ("cannot bind" in text or "already in use" in text) and "auto-switch" in text, (
            "unhelpful refusal message: %s" % text[-600:])
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=20)
    deadline = time.time() + 20
    while time.time() < deadline and not U.port_is_free(PORT_SUB):
        time.sleep(0.2)
    assert U.port_is_free(PORT_SUB), "port %d is still bound after terminate()" % PORT_SUB
