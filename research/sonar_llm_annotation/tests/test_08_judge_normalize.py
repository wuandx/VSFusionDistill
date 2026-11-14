"""plugin/sonarllm/judge.py: normalize() must reject every malformed judgment.

The judge is a model (or a human); the validator is the only thing standing between a
plausible-looking JSON and a corrupted annotation set.  Every case below therefore
asserts *both* that the result is None and that a message was produced: a silent default
would be worse than a crash.
"""
from __future__ import annotations

import _util as U


def _judge():
    return U.plugin().judge


def _base(**over):
    obj = {"sample": "2023-09-20_171105_0622", "verdict": "structure",
           "shape": "short_arc", "box": None, "confidence": 0.7,
           "reason": "贯穿扇面的亮弧", "judge_model": "qa"}
    obj.update(over)
    return obj


def _reject(obj, expect_in: str, recording=None):
    j = _judge()
    norm, errs = j.normalize(obj, recording=recording)
    joined = " | ".join(errs)
    assert norm is None, "accepted an invalid judgment: %r -> %r" % (obj, norm)
    assert errs, "rejected %r without saying why" % (obj,)
    assert expect_in in joined, (
        "error message does not mention %r; got %r" % (expect_in, joined))
    return joined


def test_frame_h_is_per_recording_not_a_constant():
    j = _judge()
    assert j.frame_h(U.REC_BOMB) == 780, "bomb frame height %r" % (j.frame_h(U.REC_BOMB),)
    assert j.frame_h(U.REC_MORTAR) == 441, "mortar frame height %r" % (j.frame_h(U.REC_MORTAR),)
    assert j.frame_h(U.REC_GRENADE) == 441, "grenade frame height %r" % (j.frame_h(U.REC_GRENADE),)


def test_a_valid_object_judgment_is_normalized():
    j = _judge()
    norm, errs = j.normalize(_base(verdict="object", shape="blob",
                                   box=[40, 260, 90, 380]), recording=U.REC_BOMB)
    assert errs == [], "a valid judgment was rejected: %r" % (errs,)
    assert norm is not None
    assert norm["_schema"] == "sonarllm/judgment/v1"
    assert norm["box"] == [40.0, 260.0, 90.0, 380.0], "box not normalized to floats: %r" % (
        norm["box"],)


def test_verdict_must_be_one_of_the_four():
    _reject(_base(verdict="maybe"), "verdict")


def test_shape_must_be_one_of_the_five():
    _reject(_base(shape="banana"), "shape")


def test_box_must_be_four_numbers():
    _reject(_base(verdict="object", box=[10, 20, 30]), "box 必须是 4 个数")
    _reject(_base(verdict="object", box=[10, 20, 30, "40"]), "box 必须是 4 个数")


def test_degenerate_box_is_rejected():
    _reject(_base(verdict="object", box=[50, 100, 50, 200]), "x2>x1")
    _reject(_base(verdict="object", box=[10, 200, 60, 200]), "y2>y1")


def test_box_outside_the_frame_is_rejected():
    # beams are 128 wide on every recording
    _reject(_base(verdict="object", box=[10, 100, 129, 200]), "越界")
    _reject(_base(verdict="object", box=[-1, 100, 60, 200]), "越界")
    # rows: 780 on the bomb recording ...
    _reject(_base(verdict="object", box=[10, 100, 60, 781]), "越界", recording=U.REC_BOMB)
    # ... and 441 on the mortar recording, where 700 is already outside the frame
    _reject(_base(verdict="object", box=[10, 100, 60, 700]), "越界", recording=U.REC_MORTAR)


def test_box_inside_441_rows_is_accepted():
    """The same box that is legal in a 441-row frame must not be judged by 780."""
    j = _judge()
    norm, errs = j.normalize(_base(sample="2023-09-21_100927_0300", verdict="object",
                                   box=[10, 100, 60, 430]), recording=U.REC_MORTAR)
    assert errs == [], "a legal 441-row box was rejected: %r" % (errs,)
    assert norm is not None
    # ... and it must be rejected on the 780-row recording for the mirror reason only:
    # it is legal there too, so the sizes must not be conflated in either direction
    norm2, errs2 = j.normalize(_base(verdict="object", box=[10, 100, 60, 430]),
                               recording=U.REC_BOMB)
    assert errs2 == [], "a legal 780-row box was rejected: %r" % (errs2,)


def test_object_without_a_box_is_rejected():
    _reject(_base(verdict="object", box=None), "没有 box")


def test_confidence_must_be_in_the_unit_interval():
    _reject(_base(confidence=1.5), "confidence")
    _reject(_base(confidence=-0.1), "confidence")
    _reject(_base(confidence="high"), "confidence")


def test_sample_must_belong_to_the_recording():
    _reject(_base(sample="2023-09-21_120653_0400"), "不属于录音", recording=U.REC_BOMB)


def test_missing_sample_is_rejected():
    _reject({"verdict": "empty", "confidence": 0.5}, "sample missing")


def test_card_sha256_mismatch_is_rejected():
    pkg = U.plugin()
    j = pkg.judge
    tmp = U.fresh_dir("judge", "sha")
    cards = tmp / "cards"
    cards.mkdir(parents=True)
    card = cards / "2023-09-20_171105_0622.png"
    card.write_bytes(b"\x89PNG\r\n\x1a\nstale-card")
    old = j.OUT
    j.OUT = tmp
    try:
        good = U.sha256_file(card)
        norm, errs = j.normalize(_base(card_sha256=good), recording=U.REC_BOMB)
        assert errs == [], "a matching card_sha256 was rejected: %r" % (errs,)
        norm, errs = j.normalize(_base(card_sha256="0" * 64), recording=U.REC_BOMB)
        assert norm is None and errs, "a stale card_sha256 was accepted"
        assert "card_sha256" in " ".join(errs), errs
    finally:
        j.OUT = old


def test_non_object_payload_is_rejected():
    j = _judge()
    norm, errs = j.normalize(["not", "a", "dict"])  # type: ignore[arg-type]
    assert norm is None and errs, "a non-dict judgment was accepted"
