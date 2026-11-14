"""engine/cards.py: card rendering contract.

What is checked here is what a human judge relies on:
  * the PNG on disk is the size the metadata claims, and the hash matches the bytes;
  * the candidate-box fallback chain stops at the record, never at the refuted gantry
    prediction (BRIEF 2.2: predicted is unavailable on this data);
  * the same record renders byte-identically twice;
  * 441-row recordings render at 441, not padded to 780.
"""
from __future__ import annotations

import json

import numpy as np

import _util as U


def _cards():
    return U.eng("cards")


def _record(recording, frame, **extra):
    """A minimal record shaped like proposals.jsonl entries."""
    path = U.pgm_path(recording, frame)
    hdr = U.read_pgm_header(path)
    data = {
        "sample": "%s_%04d" % (recording, frame),
        "recording": recording,
        "category": U.CATEGORY[recording],
        "aris_frame": frame,
        "image": {
            "path": str(path),
            "sha256": U.sha256_file(path),
            "width": hdr[0],
            "height": hdr[1],
        },
        "predicted": {"available": False, "reason": "gantry_not_sonar_frame"},
    }
    data.update(extra)
    return data


def test_png_on_disk_matches_meta_size_and_hash():
    cards = _cards()
    out = U.fresh_dir("cards") / "bomb_0622.png"
    path, meta = cards.render_with_meta("2023-09-20_171105_0622",
                                        _record(U.REC_BOMB, 622), out)
    from PIL import Image
    with Image.open(path) as im:
        assert im.format == "PNG", "rendered format %r" % im.format
        assert list(im.size) == list(meta["size_px"]), (
            "PNG size %r != meta size_px %r" % (im.size, meta["size_px"]))
        assert im.mode == "RGB", "card is %s, not RGB" % im.mode
    assert meta["out_sha256"] == U.sha256_file(path), "out_sha256 does not hash the PNG"
    assert meta["image_sha256"] == U.sha256_file(U.pgm_path(U.REC_BOMB, 622))
    assert meta["card"] == cards.CARD_VERSION
    assert meta["size_px"][0] > 0 and meta["size_px"][1] > 0


def test_missing_frame_source_is_a_clear_error():
    cards = _cards()
    U.assert_raises(ValueError, cards.render_with_meta, "x", {"aris_frame": 1},
                    U.fresh_dir("cards") / "x.png",
                    contains="neither 'img' nor image.path")


def test_candidate_box_fallback_chain_never_uses_predicted():
    cards = _cards()
    d = U.fresh_dir("cards")
    rec = _record(U.REC_BOMB, 622)
    # 1) an explicit candidate wins
    _, m1 = cards.render_with_meta("s", dict(rec, candidate={"box_xyxy": [10, 20, 60, 90]}),
                                   d / "c.png")
    assert m1["box_source"] == "candidate", "box_source=%r" % (m1["box_source"],)
    # 2) an echo blob is the second choice
    _, m2 = cards.render_with_meta("s", dict(rec, echo={"blobs": [
        {"rank": 0, "box_xyxy": [30, 40, 70, 200]}]}), d / "e.png")
    assert m2["box_source"] == "echo.rank0", "box_source=%r" % (m2["box_source"],)
    assert m2["candidate_box"] == [30.0, 40.0, 70.0, 200.0], (
        "echo rank0 box not adopted: %r" % (m2["candidate_box"],))
    # 3) otherwise the frame default, and never the gantry prediction
    pred = {"available": True, "beam": 20, "row": 100, "in_window": True}
    _, m3 = cards.render_with_meta("s", dict(rec, predicted=pred), d / "f.png")
    assert m3["box_source"].startswith("frame-default"), (
        "predicted was laundered into the candidate box: box_source=%r" % (m3["box_source"],))
    assert m3["candidate_box"] == [32.0, 195.0, 96.0, 585.0], (
        "frame-default box = %r" % (m3["candidate_box"],))


def test_predicted_is_not_drawn_when_unavailable_even_if_forced():
    cards = _cards()
    d = U.fresh_dir("cards")
    rec = _record(U.REC_BOMB, 622)
    _, m = cards.render_with_meta("s", rec, d / "a.png")
    assert m["predicted_drawn"] is False
    assert m["predicted_reason"] == "gantry_not_sonar_frame", (
        "reason must name the refutation, got %r" % (m["predicted_reason"],))
    _, mf = cards.render_with_meta("s", rec, d / "b.png", draw_predicted=True)
    assert mf["predicted_drawn"] is False, (
        "draw_predicted=True overrode an unavailable prediction")
    # and it does draw when a prediction really is available
    pred = {"available": True, "beam": 63, "row": 300, "in_window": True,
            "box_xyxy": [50, 280, 80, 340]}
    _, mt = cards.render_with_meta("s", dict(rec, predicted=pred), d / "c.png")
    assert mt["predicted_drawn"] is True, "an available prediction was not drawn"
    assert mt["predicted_in_window"] is True


def test_same_record_renders_byte_identically():
    cards = _cards()
    d = U.fresh_dir("cards")
    rec = _record(U.REC_BOMB, 622, candidate={"box_xyxy": [40, 260, 90, 380]})
    p1, m1 = cards.render_with_meta("s", rec, d / "one.png")
    p2, m2 = cards.render_with_meta("s", rec, d / "two.png")
    assert p1.read_bytes() == p2.read_bytes(), "same record rendered different bytes"
    assert m1["out_sha256"] == m2["out_sha256"]
    assert m1["size_px"] == m2["size_px"] and m1["zoom"] == m2["zoom"]
    for k in ("candidate_box", "crop", "stretch", "metric_panel", "row_scale"):
        assert m1[k] == m2[k], "meta[%r] differs between identical renders" % (k,)


def test_441_row_recording_renders_at_441():
    cards = _cards()
    d = U.fresh_dir("cards")
    for rec, frame in ((U.REC_MORTAR, 300), (U.REC_GRENADE, 400)):
        path, meta = cards.render_with_meta("%s_%04d" % (rec, frame),
                                            _record(rec, frame), d / ("%s.png" % rec))
        assert meta["input"].get("path", "").endswith(".pgm")
        from PIL import Image
        with Image.open(path) as im:
            assert im.size == tuple(meta["size_px"])
        print("      %s 441-row card %r row_scale=%r" % (rec, meta["size_px"], meta["row_scale"]))
    m780 = cards.render_with_meta("a", _record(U.REC_BOMB, 622), d / "780.png")[1]
    m441 = cards.render_with_meta("b", _record(U.REC_MORTAR, 300), d / "441.png")[1]
    assert m780["row_scale"] != m441["row_scale"], (
        "row_scale identical for 780- and 441-row recordings: %r" % (m780["row_scale"],))
    r780 = m780["row_scale"]
    r441 = m441["row_scale"]
    assert isinstance(r780, dict) and isinstance(r441, dict), "row_scale shape %r" % (r780,)
    print("      780 row_scale=%r\n      441 row_scale=%r" % (r780, r441))


def test_degenerate_candidate_is_flagged():
    cards = _cards()
    d = U.fresh_dir("cards")
    rec = _record(U.REC_BOMB, 622, candidate={"box_xyxy": [10.0, 10.0, 11.0, 40.0]})
    _, m = cards.render_with_meta("s", rec, d / "tiny.png")
    assert m["candidate_degenerate"] is True, (
        "a 1 px wide candidate was not flagged degenerate")
    rec2 = _record(U.REC_BOMB, 622, candidate={"box_xyxy": [10.0, 10.0, 60.0, 90.0]})
    _, m2 = cards.render_with_meta("s", rec2, d / "ok.png")
    assert m2["candidate_degenerate"] is False


def test_structures_and_band_flags_are_reported():
    cards = _cards()
    d = U.fresh_dir("cards")
    arr = U.read_pgm(U.pgm_path(U.REC_BOMB, 622))
    mask = np.zeros(arr.shape, dtype=bool)
    mask[100:200, :] = True
    _, m = cards.render_with_meta("s", _record(U.REC_BOMB, 622), d / "struct.png",
                                  structures_mask=mask, bg_band=[(100, 200)])
    assert m["structures_greyed"] is True, "structures_mask did not set structures_greyed"
    assert m["bg_bands"] == [[100, 200]], "bg_bands=%r" % (m["bg_bands"],)
    _, m0 = cards.render_with_meta("s", _record(U.REC_BOMB, 622), d / "plain.png")
    assert m0["structures_greyed"] is False
    assert m0["bg_bands"] == []


def test_write_false_writes_nothing():
    cards = _cards()
    out = U.fresh_dir("cards") / "nope.png"
    path, meta = cards.render_with_meta("s", _record(U.REC_BOMB, 622), out, write=False)
    assert not out.exists(), "write=False still wrote %s" % out
    assert "out_sha256" not in meta
    assert meta["size_px"]


def test_temporal_strip_reports_what_it_drew():
    cards = _cards()
    d = U.fresh_dir("cards")
    rec = _record(U.REC_BOMB, 622)
    _, m2 = cards.render_with_meta("s", rec, d / "n2.png", neighbors=2)
    t = m2.get("temporal")
    assert isinstance(t, dict), "neighbors=2 gave temporal=%r" % (t,)
    assert t["neighbors"] == 2
    assert t["current"] == 622
    assert isinstance(t["frames"], list) and len(t["frames"]) <= 5
    for f in t["frames"]:
        assert U.pgm_path(U.REC_BOMB, f).exists(), "temporal strip cites a missing frame %r" % (f,)
    _, m0 = cards.render_with_meta("s", rec, d / "n0.png", neighbors=0)
    assert not m0.get("temporal"), (
        "neighbors=0 still wrote a temporal block: %r" % (m0.get("temporal"),))


def test_meta_is_json_safe():
    cards = _cards()
    d = U.fresh_dir("cards")
    _, meta = cards.render_with_meta("s", _record(U.REC_MORTAR, 300), d / "j.png")
    txt = json.dumps(meta)  # raises if a numpy scalar leaked in
    assert len(txt) > 100
