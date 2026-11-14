"""engine/arc.py: the arc extractor must reproduce the boxes a human signed off.

The convention was agreed with the user on 2026-11-12: on these recordings the
munition shows up as a thin specular arc, and the box covers the visible bright
run of that arc plus a 1.6x margin. The 24 boxes in ``out/<rec>/judge_lead/``
are the reference. They were produced by hand-run scripts; this module is the
same rule wearing an engine's clothes, so:

  * on the same 24 frames it lands on the same pixels (IoU median >= 0.9);
  * running it twice gives byte-identical boxes -- no hidden state;
  * a frame with no bright structure yields ``None`` rather than the largest
    speck of noise (the detector must be able to say "nothing here");
  * the margin is the only thing that inflates the box, and switching it off
    returns the raw component, so a reader can always see what was measured
    versus what was added.

The last one matters for honesty: the padded box is an annotation convention,
not a measurement of the shell.
"""
from __future__ import annotations

import json
import sys

import numpy as np

import _util as U

RECS = ("2023-09-21_105230", "2023-09-21_101840")


def _arc():
    sys.path.insert(0, str(U.REPO))
    from engine import arc  # noqa: E402
    return arc


def _iou(a, b) -> float:
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua else 0.0


def _reference(rec):
    d = U.REPO / "out" / rec / "judge_lead"
    out = []
    for p in sorted(d.glob("*.json")):
        j = json.loads(p.read_text(encoding="utf-8"))
        if j.get("box"):
            out.append((int(p.stem.rsplit("_", 1)[1]), j["box"]))
    return sorted(out)


def test_the_extractor_reproduces_the_twenty_four_hand_boxes():
    arc = _arc()
    all_ious = []
    for rec in RECS:
        ref = _reference(rec)
        assert len(ref) == 12, f"{rec}: expected 12 reference boxes, found {len(ref)}"
        prev = None
        for frame, box in ref:
            row = arc.analyse(rec, frame, prev_center=prev)
            assert row["blobs"], f"{rec} f{frame}: extractor returned nothing"
            got = row["blobs"][0]["box_xyxy"]
            all_ious.append(_iou(got, box))
            prev = ((got[0] + got[2]) / 2.0, (got[1] + got[3]) / 2.0)
    med = float(np.median(all_ious))
    assert med >= 0.90, f"IoU median {med:.3f} against the hand boxes"
    assert min(all_ious) >= 0.85, f"worst frame IoU {min(all_ious):.3f}"


def test_the_same_frame_gives_the_same_box_twice():
    arc = _arc()
    a = arc.analyse("2023-09-21_105230", 386)["blobs"][0]["box_xyxy"]
    b = arc.analyse("2023-09-21_105230", 386)["blobs"][0]["box_xyxy"]
    assert a == b, f"two runs disagree: {a} vs {b}"


def test_a_frame_without_bright_structure_returns_nothing():
    arc = _arc()
    flat = np.full((441, 128), 27, dtype=np.uint8)
    assert arc.detect_arc(flat) is None, "flat frame produced a box"


def test_the_margin_is_the_only_thing_that_inflates_the_box():
    arc = _arc()
    rec = "2023-09-21_105230"
    a = arc.analyse(rec, 386, margin=1.0, min_pad=0)
    b = arc.analyse(rec, 386, margin=1.6)
    ba, bb = a["blobs"][0]["box_xyxy"], b["blobs"][0]["box_xyxy"]
    assert ba == a["arc"]["raw_box_xyxy"], f"margin 1.0 should equal raw: {ba} vs {a['arc']['raw_box_xyxy']}"
    assert (bb[2] - bb[0]) > (ba[2] - ba[0]), f"margin 1.6 did not widen: {ba} -> {bb}"
    assert (bb[3] - bb[1]) > (ba[3] - ba[1]), f"margin 1.6 did not heighten: {ba} -> {bb}"
