"""End-to-end: proposals.jsonl -> cards -> judgments -> reviews.jsonl (HTTP) -> YOLO export.

Everything is written under out/_qa/e2e; the review server runs in-process on port 8772
(the exported tree is a throw-away copy, never out/<real recording>/).
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import _util as U

PORT = 8772
CACHE: dict[str, object] = {}


# --------------------------------------------------------------------------- http
def _post(path: str, body: dict):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (PORT, path), data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8") or "{}")


# --------------------------------------------------------------------------- build
def _pipeline():
    if CACHE:
        return CACHE
    if not U.port_is_free(PORT):
        raise AssertionError("port %d is already in use; refusing to test" % PORT)
    ds = U.plugin().dataset
    cards_mod = U.eng("cards")
    geo = U.eng("geometry")
    srv = U.server_mod()

    root = U.fresh_dir("e2e")
    roles = ds.sample_roles()

    def pick(rec, frames, want_role):
        # A sample carrying two roles is legitimately refused by the exporter
        # (mixed_paired_role), so the e2e must pick an unambiguous one: exactly one
        # role for the assigned case, none for the unassigned case.
        for f in frames:
            sample = "%s_%04d" % (rec, f)
            got = roles.get(sample) or []
            if (len(got) == 1) is want_role and (want_role or not got):
                return f, sample
        raise AssertionError("no frame of %s with want_role=%r among %r"
                             % (rec, want_role, frames))

    fb, sb = pick(U.REC_BOMB, [622, 900, 300], True)
    fm, sm = pick(U.REC_MORTAR, [87, 300, 500], False)

    specs = [(U.REC_BOMB, fb, sb, U.CATEGORY[U.REC_BOMB]),
             (U.REC_MORTAR, fm, sm, U.CATEGORY[U.REC_MORTAR])]
    prop_root = root / "proposals"
    card_dir = root / "cards"
    card_dir.mkdir(parents=True, exist_ok=True)
    records = {}
    for rec, frame, sample, cat in specs:
        pgm = U.pgm_path(rec, frame)
        w, h = U.read_pgm_header(pgm)
        box = [40, int(h * 0.35), 90, int(h * 0.5)]
        rec_obj = {
            "sample": sample, "recording": rec, "category": cat, "aris_frame": frame,
            "candidate": {"box_xyxy": [float(v) for v in box]},
            "predicted": {"available": False, "reason": "gantry_not_sonar_frame"},
            "image": {"path": str(pgm), "width": w, "height": h,
                      "sha256": U.sha256_file(pgm)},
            "n_beams": w, "n_rows": h,
        }
        d = prop_root / rec
        d.mkdir(parents=True, exist_ok=True)
        (d / "proposals.jsonl").write_text(json.dumps(rec_obj, ensure_ascii=False) + "\n",
                                           encoding="utf-8")
        card_path, card_meta = cards_mod.render_with_meta(
            sample, rec_obj, card_dir / ("%s.png" % sample), scale=2)
        card_sha = U.sha256_file(card_path)
        jdir = root / rec / "judgments"
        jdir.mkdir(parents=True, exist_ok=True)
        j = {"sample": sample, "verdict": "object", "shape": "blob",
             "box": [float(v) for v in box], "confidence": 0.8,
             "note": "qa e2e", "card_sha256": card_sha}
        (jdir / ("%s.json" % sample)).write_text(
            json.dumps(j, ensure_ascii=False, indent=2), encoding="utf-8")
        records[sample] = {"recording": rec, "frame": frame, "box": box,
                           "card": card_path, "card_sha256": card_sha,
                           "size": (w, h), "record": rec_obj}

    srv.OUT_DIR = root
    srv.CFG.port = PORT
    srv.CFG.operator = "qa-e2e"
    srv.CFG.store = srv.ProposalStore(prop_root)
    srv.CFG.cards_dir = card_dir
    srv.CFG.judgments_root = root
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), srv.Handler)
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    posts = {}
    reviewed = {}
    try:
        for rec, frame, sample, cat in specs:
            box = records[sample]["box"]
            # `revise` must differ from the candidate box: the server rejects a no-op
            # revise, so the second recording's edited box is nudged by 2 px.
            edited = [float(v) for v in box] if rec == U.REC_BOMB else [
                float(box[0]) + 2, float(box[1]) + 2, float(box[2]) + 2, float(box[3]) + 2]
            body = {"sample": sample, "recording": rec, "status": "accept" if rec == U.REC_BOMB
                    else "revise", "final_box": edited,
                    "operator": "qa-e2e", "reason": "pipeline check"}
            reviewed[sample] = edited
            posts[sample] = _post("/api/review", body)
    finally:
        httpd.shutdown()
        httpd.server_close()
        th.join(timeout=10)

    ds.OUT = root
    dst = root / "export"
    summary = ds.export(dst, recordings=[U.REC_BOMB, U.REC_MORTAR])

    CACHE.update(root=root, dst=dst, records=records, posts=posts, reviewed=reviewed, summary=summary,
                 prop_root=prop_root, card_dir=card_dir, port_free_after=U.port_is_free(PORT))
    return CACHE


# --------------------------------------------------------------------------- tests
def test_reviews_are_appended_by_the_real_server():
    st = _pipeline()
    assert st["port_free_after"], "port %d still bound after shutdown" % PORT
    root = st["root"]
    posts = st["posts"]
    for sample, (code, body) in posts.items():
        assert code == 201, "POST /api/review for %s -> %r %r" % (sample, code, body)
        assert body.get("ok") is True, body
        assert body["saved"]["sample"] == sample, body["saved"]
        assert body["file"]["bytes"] > 0
        rec = st["records"][sample]["recording"]
        path = st["root"] / rec / "reviews.jsonl"
        assert path.is_file(), "no reviews.jsonl at %s" % path
        lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 1, "expected exactly one review line, got %d" % len(lines)
        row = json.loads(lines[0])
        assert row["sample"] == sample
        assert row["data_source"] == "human", (
            "a real manual review must be data_source=human, got %r" % row.get("data_source"))
        assert row["card_sha256"] == st["records"][sample]["card_sha256"], (
            "the review did not pin the card the operator saw")
        assert row["grid"]["height"] == st["records"][sample]["size"][1], (
            "review grid height %r != recording height %d"
            % (row["grid"].get("height"), st["records"][sample]["size"][1]))


def test_export_writes_the_yolo_tree_and_both_image_heights():
    from PIL import Image
    st = _pipeline()
    dst = st["dst"]
    y = (dst / "data.yaml").read_text(encoding="utf-8")
    for key in ("path:", "train:", "val:", "names:"):
        assert key in y, "data.yaml lacks %r:\n%s" % (key, y)
    files = sorted(p.relative_to(dst).as_posix() for p in dst.rglob("*.txt"))
    files = [f for f in files if f.startswith("labels/")]
    assert len(files) == 2, "expected two label files, got %r" % (files,)
    for sample, meta in st["records"].items():
        split = "val" if meta["recording"] == U.REC_BOMB else "unassigned"
        lab = dst / "labels" / split / ("%s.txt" % sample)
        img = dst / "images" / split / ("%s.png" % sample)
        assert lab.is_file(), "missing label %s" % lab
        assert img.is_file(), "missing image %s" % img
        with Image.open(str(img)) as im:
            assert im.size == meta["size"], (
                "%s exported at %r, expected %r" % (sample, im.size, meta["size"]))
        fields = lab.read_text(encoding="utf-8").split()
        assert len(fields) == 5, "YOLO line must have 5 fields, got %r" % (fields,)


def test_export_preserves_the_reviewed_box_at_the_recording_height():
    st = _pipeline()
    dst = st["dst"]
    for sample, meta in st["records"].items():
        split = "val" if meta["recording"] == U.REC_BOMB else "unassigned"
        cls, cx, cy, w, h = [float(v) for v in
                             (dst / "labels" / split / ("%s.txt" % sample))
                             .read_text(encoding="utf-8").split()]
        fw, fh = meta["size"]
        # compare against what the operator actually submitted, not the engine's candidate
        x1, y1, x2, y2 = st["reviewed"][sample]
        assert abs(cx * fw - (x1 + x2) / 2.0) <= 0.02, "%s cx %.4f" % (sample, cx)
        assert abs(cy * fh - (y1 + y2) / 2.0) <= 0.02, (
            "%s cy %.6f -> %.2f rows but the box centre is %.2f rows (height %d)"
            % (sample, cy, cy * fh, (y1 + y2) / 2.0, fh))
        assert abs(w * fw - (x2 - x1)) <= 0.02
        assert abs(h * fh - (y2 - y1)) <= 0.02
        assert all(0.0 <= v <= 1.0 for v in (cx, cy, w, h)), (sample, cx, cy, w, h)


def test_provenance_matches_the_files_actually_written():
    st = _pipeline()
    dst = st["dst"]
    prov = json.loads((dst / "provenance.json").read_text(encoding="utf-8"))
    n_labels = len([p for p in (dst / "labels").rglob("*.txt")])
    assert prov["n_exported"] == n_labels, (
        "provenance says n_exported=%r but %d label files exist"
        % (prov["n_exported"], n_labels))
    n_un = len(list((dst / "labels" / "unassigned").glob("*.txt")))
    assert prov["n_unassigned"] == n_un, (
        "provenance n_unassigned=%r but %d unassigned labels are on disk"
        % (prov["n_unassigned"], n_un))
    assert prov["candidate_only_not_training_ready"] is True
    assert "HOLD" in prov["sonar_gt_status"]
    assert prov["refusals"] == [], "unexpected refusals: %r" % (prov["refusals"],)
    by_rec = prov["image_size_by_recording"]
    got_b = by_rec[U.REC_BOMB]
    got_m = by_rec[U.REC_MORTAR]
    assert (got_b["width"], got_b["height"]) == (128, 780), "bomb size %r" % (got_b,)
    assert (got_m["width"], got_m["height"]) == (128, 441), "mortar size %r" % (got_m,)
    assert prov["image_size_default"] == {"width": 128, "height": 780}, (
        "the default must stay the documented 128x780 fallback, got %r"
        % (prov["image_size_default"],))
