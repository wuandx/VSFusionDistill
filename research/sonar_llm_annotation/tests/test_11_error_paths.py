"""Abnormal paths: every one of these must fail loudly, not quietly produce a dataset.

Deliberately written against the *observable contract* (exit code / exception / provenance),
so a silent skip shows up as a FAIL rather than as a green test.
"""
from __future__ import annotations

import json

import numpy as np

import _util as U


def _cards():
    return U.eng("cards")


# --------------------------------------------------------------------------- engine
def test_truncated_pgm_is_rejected():
    echo = U.eng("echo")
    d = U.fresh_dir("err", "pgm")
    good = U.pgm_path(U.REC_BOMB, 622)
    raw = good.read_bytes()
    cut = d / "cut.pgm"
    cut.write_bytes(raw[: len(raw) // 2])
    try:
        echo.read_pgm(cut)
    except ValueError as exc:
        assert "truncated" in str(exc), "unhelpful truncation error: %s" % exc
    else:
        raise AssertionError("read_pgm() accepted a truncated PGM (%d bytes)" % cut.stat().st_size)


def test_non_binary_pgm_is_rejected():
    echo = U.eng("echo")
    d = U.fresh_dir("err", "pgm2")
    p = d / "ascii.pgm"
    p.write_bytes(b"P2\n2 2\n255\n0 1 2 3\n")
    try:
        echo.read_pgm(p)
    except ValueError as exc:
        assert "binary PGM" in str(exc), "unhelpful format error: %s" % exc
    else:
        raise AssertionError("read_pgm() accepted a P2 (ASCII) PGM")


def test_detect_without_background_or_with_a_bad_mode_raises():
    echo = U.eng("echo")
    img = U.read_pgm(U.pgm_path(U.REC_BOMB, 622))
    U.assert_raises(ValueError, echo.detect, img, contains="needs a background model")
    bg = {"median": np.zeros_like(img), "band": np.zeros(img.shape, bool),
          "shifts": {}, "anchor_frame": 622, "header": {}}
    try:
        echo.detect(img, bg=bg, mode="sideways")
    except ValueError as exc:
        assert "mode" in str(exc), "unhelpful mode error: %s" % exc
    else:
        raise AssertionError("detect() accepted mode='sideways'")


def test_cards_decode_frame_without_an_image_raises():
    cards = _cards()
    try:
        cards.decode_frame({"sample": "x"})
    except ValueError as exc:
        assert "neither" in str(exc), "unhelpful error: %s" % exc
    else:
        raise AssertionError("decode_frame() accepted a record with no image")


def test_cards_cli_refuses_to_run_without_a_proposals_file():
    cards = _cards()
    d = U.fresh_dir("err", "cards")
    missing = d / "nope.jsonl"
    try:
        cards.main(["--proposals", str(missing), "--out", str(d / "out")])
    except SystemExit as exc:
        assert "not found" in str(exc), "unhelpful exit message: %r" % (str(exc),)
    else:
        raise AssertionError("cards CLI silently accepted a missing proposals file")


# --------------------------------------------------------------------------- plugin
def test_dataset_read_reviews_never_reports_a_corrupt_line():
    """A truncated reviews.jsonl line drops a sample; the operator must be told."""
    ds = U.plugin().dataset
    root = U.fresh_dir("err", "rev")
    rec = U.REC_BOMB
    good = {"sample": "%s_0622" % rec, "recording": rec, "status": "accept",
            "final_box": [40.0, 273.0, 90.0, 390.0],
            "candidate_box": [40.0, 273.0, 90.0, 390.0],
            "category": U.CATEGORY[rec], "aris_frame": 622}
    path = root / rec / "reviews.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(good) + "\n{\"sample\": \"%s_0900\", \"status\": \"acc" % rec,
                    encoding="utf-8")
    old = ds.OUT
    ds.OUT = root
    try:
        latest = ds.read_reviews(rec)
        assert list(latest) == [good["sample"]], (
            "read_reviews kept %r; the corrupt line should be reported, not silently dropped"
            % (list(latest),))
        dst = root / "export"
        prov = ds.export(dst, recordings=[rec])
        (dst / "data.yaml").read_text(encoding="utf-8")  # export ran, no exception
        assert "n_bad_review_lines" in prov or "bad_review_lines" in prov, (
            "provenance.json does not record the corrupt reviews line; the row vanished "
            "without a trace (exported %r of 2 lines, keys: %s)"
            % (prov.get("n_exported"), sorted(prov)))
    finally:
        ds.OUT = old


def test_server_read_reviews_counts_bad_lines():
    srv = U.server_mod()
    root = U.fresh_dir("err", "revsrv")
    rec = U.REC_BOMB
    path = root / rec / "reviews.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"sample": "%s_0622", "status": "accept"}\n{"sample": broken\n' % rec,
                    encoding="utf-8")
    old = srv.OUT_DIR
    srv.OUT_DIR = root
    try:
        latest, writes, bad = srv.read_reviews(rec)
        assert bad == 1, "bad line count = %r, expected 1" % (bad,)
        assert writes == 1 and "%s_0622" % rec in latest
    finally:
        srv.OUT_DIR = old


def test_empty_review_set_does_not_emit_a_trainable_dataset():
    ds = U.plugin().dataset
    root = U.fresh_dir("err", "empty")
    rec = U.REC_BOMB
    p = root / rec / "reviews.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("", encoding="utf-8")
    old = ds.OUT
    ds.OUT = root
    try:
        dst = root / "export"
        summary = ds.export(dst, recordings=[rec])
        yaml_path = dst / "data.yaml"
        assert not yaml_path.exists(), (
            "an export with zero accepted reviews still wrote data.yaml (%r) — a trainer "
            "would read an empty dataset as a valid one; summary=%r"
            % (yaml_path, summary.get("n_exported")))
    finally:
        ds.OUT = old


def test_export_into_a_populated_directory_is_refused_or_reported():
    """Re-exporting over a previous tree must not silently merge two datasets."""
    ds = U.plugin().dataset
    root = U.fresh_dir("err", "dst")
    rec = U.REC_BOMB
    dst = root / "export"
    dst.mkdir(parents=True)
    (dst / "stale.txt").write_text("left over from an earlier export", encoding="utf-8")
    p = root / rec / "reviews.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"sample": "%s_0622" % rec, "recording": rec,
                             "status": "accept", "category": U.CATEGORY[rec],
                             "aris_frame": 622, "final_box": [40.0, 273.0, 90.0, 390.0],
                             "data_source": "human"}) + "\n", encoding="utf-8")
    old = ds.OUT
    ds.OUT = root
    try:
        try:
            summary = ds.export(dst, recordings=[rec])
        except Exception:  # noqa: BLE001 - refusing is the expected behaviour
            return
        prov = json.loads((dst / "provenance.json").read_text(encoding="utf-8"))
        assert (dst / "stale.txt").exists() is False or prov.get("pre_existing_files"), (
            "export wrote into a populated directory (%d stale files) with no refusal and "
            "no provenance note" % 1)
    finally:
        ds.OUT = old
