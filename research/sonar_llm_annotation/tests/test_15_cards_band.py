"""engine/cards.py: the range band a card draws, and what it claims about it.

A band on a card is dangerous in exactly one way: a reader may take it for a prediction when
it is only the spread of our own detections.  The card is therefore checked at the level of
the text it actually draws (every ``ImageDraw.text`` call is recorded, no OCR):

  * with a band attached, the card draws a caption that starts "range band" and, for a
    rejected model, says "model rejected" / "NOT a prediction";
  * with no band attached, no amber band is drawn at all (the control, so the check cannot
    pass on an unrelated amber pixel);
  * the footer provenance names the engine that produced the record ("compact/v0") and never
    points at a dry-run fixture ("dryrun");
  * the render is recorded in ``meta["band"]``, so the judgement can be audited later.

If ``engine/cards.py`` does not know the ``band`` key at all, the case is SKIPped with the
reason recorded -- a card renderer that has not shipped the feature is not a test failure.
"""
from __future__ import annotations

import json
import sys

import numpy as np
from PIL import Image, ImageDraw

import _util as U

REC_BAD = "2023-09-21_110229"     # observed band, model rejected
REC_OK = "2023-09-21_105230"      # predicted band


def _cards():
    return U.eng("cards")


def _band(rec):
    path = U.REPO / "out" / rec / "band.json"
    if not path.is_file():
        raise U.SkipTest("no %s yet: run `python -m tools.rangeband --recording %s`"
                         % (U.rel(path), rec))
    return json.loads(path.read_text(encoding="utf-8"))


def _require_band_support(cards):
    import inspect
    src = inspect.getsource(cards.render_with_meta)
    if 'frame_data.get("band")' not in src and "frame_data.get('band')" not in src:
        raise U.SkipTest("engine/cards.py render_with_meta has no `band` support yet "
                         "(t-cards not delivered)")


def _record(rec, frame):
    """A minimal record shaped like a proposals.jsonl line, with real image metadata."""
    g = U.eng("geometry").load_recording(rec)
    path = g.pgm_path(frame)
    hdr = U.read_pgm_header(path)
    prov = None
    for line in (U.REPO / "out" / rec / "proposals.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if int(r["frame"]) == int(frame):
            prov = r.get("provenance")
            break
    return {
        "sample": "%s_%04d" % (rec, frame),
        "recording": rec,
        # not U.CATEGORY (only the three audited recordings): 110229/105230 were discovered
        # from disk by engine.geometry, so ask the recording itself for its category
        "category": g.spec.category,
        "aris_frame": frame,
        "image": {"path": str(path), "sha256": U.sha256_file(path),
                  "width": hdr[0], "height": hdr[1]},
        "predicted": {"available": False, "reason": "gantry_not_sonar_frame"},
        "provenance": prov or {},
    }


def _band_entry(band, frame):
    e = dict(band["frames"][str(frame)])
    e["status"] = band["status"]
    e["band_rows"] = band["band_rows"]
    return e


def _render(rec, frame, band, out_name):
    """Render one card while recording every string drawn on it."""
    cards = _cards()
    _require_band_support(cards)
    drawn = []
    orig = ImageDraw.ImageDraw.text

    def spy(self, xy, text, *a, **kw):
        drawn.append(str(text))
        return orig(self, xy, text, *a, **kw)

    out = U.fresh_dir("cards_band") / out_name
    ImageDraw.ImageDraw.text = spy
    try:
        path, meta = cards.render_with_meta("%s_%04d" % (rec, frame),
                                            dict(_record(rec, frame), band=band), out)
    finally:
        ImageDraw.ImageDraw.text = orig
    return cards, path, meta, drawn


def _amber_pixels(path, colour):
    arr = np.asarray(Image.open(path).convert("RGB")).reshape(-1, 3)
    return int((arr == np.array(colour)).all(axis=1).sum())


def test_rejected_band_is_drawn_and_labelled_not_a_prediction():
    band = _band(REC_BAD)
    frame = int(sorted(band["frames"], key=int)[0])
    entry = _band_entry(band, frame)
    assert entry["row_lo"] < entry["row"] < entry["row_hi"]

    cards, path, meta, drawn = _render(REC_BAD, frame, entry, "bad_band.png")

    band_meta = meta.get("band")
    assert band_meta, "card meta does not record the band it drew: keys=%r" % (sorted(meta),)
    label = band_meta.get("label") or ""
    assert label.startswith("range band"), "band label=%r" % (label,)
    assert "model rejected" in label, "rejected model is not named on the card: %r" % (label,)
    assert "NOT a prediction" in label, "card does not refuse the prediction reading: %r" % (label,)

    captions = [t for t in drawn if "range band" in t]
    assert captions, "no 'range band' caption was drawn (drawn=%r)" % (drawn[:6],)
    assert any("NOT a prediction" in t for t in captions), (
        "drawn band captions never say NOT a prediction: %r" % (captions,))

    # the defect this guards: the legend was fitted by ellipsizing its tail, so the
    # card printed "range band (observed, ..." -- the qualifier the reader needs was
    # the part that got cut.  The legend must keep the refusal, unabridged, and state
    # the width it actually drew (read back from band.json, not hard-coded here).
    legend_lines = [t for t in drawn if t.startswith("legend")]
    assert legend_lines, "no legend line was drawn"
    leg = legend_lines[0]
    assert "amber dash = range band (NOT a prediction" in leg, (
        "legend does not qualify the band first: %r" % (leg,))
    assert "..." not in leg, "the legend is ellipsized: %r" % (leg,)
    band_rows = int(round(float(entry["row_hi"]) - float(entry["row_lo"])))
    assert "observed +-%d rows" % band_rows in leg, (
        "legend does not state the %d-row band it drew: %r" % (band_rows, leg))
    assert not any("dryrun" in t.lower() for t in drawn), (
        "card text mentions a dry-run fixture: %r"
        % ([t for t in drawn if "dryrun" in t.lower()],))

    assert band_meta["row_lo"] == float(entry["row_lo"])
    assert band_meta["row_hi"] == float(entry["row_hi"])
    assert band_meta["status"] == band["status"]
    assert _amber_pixels(path, cards.C_BAND) > 0, (
        "band was labelled but no amber band pixels are on the card")


def test_predicted_band_is_labelled_predicted():
    """The labelling rule is a pure function of the band entry, so drive it directly.

    Whether ``2023-09-21_105230`` currently earns ``model_ok`` is decided by the
    identifiability gate and is asserted in test_14; here the question is only that a band
    reported as a prediction is worded as one, and a rejected one is not.
    """
    band = _band(REC_OK)
    frame = int(sorted(band["frames"], key=int)[0])
    entry = _band_entry(band, frame)
    half = int((entry["row_hi"] - entry["row_lo"]) // 2)
    assert half > 0
    entry.update(status="model_ok", band_rows=half)
    entry.pop("rows_pm", None)

    _cards_mod, _path, meta, drawn = _render(REC_OK, frame, entry, "ok_band.png")
    label = (meta.get("band") or {}).get("label") or ""
    assert label.startswith("range band"), "band label=%r" % (label,)
    assert "predicted" in label, "model_ok band is not labelled as a prediction: %r" % (label,)
    assert "NOT a prediction" not in label
    assert "%d" % half in label, (
        "predicted band does not state its half-width of %d rows: %r" % (half, label))
    assert any("range band" in t and "predicted" in t for t in drawn), (
        "drawn captions: %r" % ([t for t in drawn if "range band" in t],))


def test_no_band_means_no_amber_band_on_the_card():
    """The control: the pixel check above must be able to fail."""
    band = _band(REC_BAD)
    frame = int(sorted(band["frames"], key=int)[0])
    cards = _cards()
    _require_band_support(cards)
    out = U.fresh_dir("cards_band") / "no_band.png"
    _path, meta = cards.render_with_meta("%s_%04d" % (REC_BAD, frame),
                                         _record(REC_BAD, frame), out)
    assert not meta.get("band"), "a card rendered without a band recorded one: %r" % (meta.get("band"),)
    n = _amber_pixels(out, cards.C_BAND)
    assert n == 0, "%d amber band pixels drawn although no band was given" % n


def test_card_provenance_names_the_compact_engine_and_the_real_frame():
    band = _band(REC_BAD)
    frame = int(sorted(band["frames"], key=int)[0])
    cards, path, meta, drawn = _render(REC_BAD, frame, _band_entry(band, frame), "prov.png")

    assert any("engine_version compact/v0" in t for t in drawn), (
        "footer never names compact/v0 (drawn engine_version lines: %r)"
        % ([t for t in drawn if "engine_version" in t],))
    assert cards.ENGINE_VERSION != "compact/v0", (
        "cards.ENGINE_VERSION is %r, so the footer string could come from the renderer "
        "instead of the record's provenance" % (cards.ENGINE_VERSION,))

    src = meta["input"]
    text = json.dumps(src, ensure_ascii=False)
    assert "dryrun" not in text.lower(), "card input points at a dry-run fixture: %s" % text
    assert REC_BAD in text, "card input does not name the recording: %s" % text
    assert "aris_raw" in text.replace("\\\\", "/"), "card input is not the raw frame: %s" % text
    assert meta["image_sha256"] == U.sha256_file(
        U.eng("geometry").load_recording(REC_BAD).pgm_path(frame))
    assert meta["out_sha256"] == U.sha256_file(path)
