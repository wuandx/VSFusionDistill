"""engine/track.py: profiles, lag recovery, track_path, propagate, clip_box."""
from __future__ import annotations

import numpy as np

import _util as U

REAL = ((U.REC_BOMB, 622), (U.REC_MORTAR, 300), (U.REC_GRENADE, 400))


def _track():
    return U.eng("track")


def _echo():
    return U.eng("echo")


def _frame(rec, n):
    return U.read_pgm(U.pgm_path(rec, n))


def test_profiles_are_not_degenerate_on_real_frames():
    track = _track()
    for rec, n in REAL:
        a = _frame(rec, n)
        band = track.structure_band(a, 90.0)
        assert band.dtype == np.bool_ and band.shape == a.shape
        assert int(band.sum()) > 200, "%s %d: band has %d px" % (rec, n, int(band.sum()))
        prof = track.masked_mean_profile(a, band, 1)
        assert int((np.abs(prof) > 1e-9).sum()) >= 8, (
            "%s %d: masked row profile is non-zero on %d rows"
            % (rec, n, int((np.abs(prof) > 1e-9).sum())))
        assert float(np.std(prof)) > 1.0, (
            "%s %d: profile std=%.4f (constant profile -> bound lag)"
            % (rec, n, float(np.std(prof))))


def test_masked_mean_profile_zeroes_when_band_is_too_thin():
    track = _track()
    a = _frame(U.REC_BOMB, 622)
    band = np.zeros(a.shape, dtype=bool)
    band[100:103, :] = True
    prof = track.masked_mean_profile(a, band, 1)
    assert not np.any(prof), "a 3-row band must yield the zero profile, got max %.3f" % np.abs(prof).max()


def test_best_lag_recovers_known_integer_lags():
    track = _track()
    rng = np.random.default_rng(5)
    a = rng.normal(size=200)
    for lag in (-17, -3, 0, 4, 11, 40):
        b = np.zeros_like(a)
        # b[k] = a[lag + k]
        if lag >= 0:
            b[: 200 - lag] = a[lag:]
        else:
            b[-lag:] = a[: 200 + lag]
        got, corr = track.best_lag(a, b, 41)
        assert got == lag, "known lag %+d -> best_lag=%+d (corr=%.4f)" % (lag, got, corr)
        assert corr > 0.999, "lag %+d corr=%.4f" % (lag, corr)


def test_track_estimate_shift_needs_the_band_argument():
    """track.estimate_shift(a, b, band) -- the band is required, unlike echo's."""
    track = _track()
    a = _frame(U.REC_BOMB, 622)
    U.assert_raises(TypeError, track.estimate_shift, a, a.copy())


def test_track_and_echo_shift_agree_on_the_same_band():
    track, echo = _track(), _echo()
    a = _frame(U.REC_BOMB, 622)
    band = track.structure_band(a, 90.0)
    for shift in (-9, -3, 0, 3, 9):
        b = echo.shift_img(a, -shift, 0) if shift else a.copy()
        t = track.estimate_shift(a, b, band)
        e = echo.estimate_shift(a, b, band=band)
        assert (t["drow"], t["dbeam"]) == (e["drow"], e["dbeam"]), (
            "shift %+d: track %r vs echo %r"
            % (shift, (t["drow"], t["dbeam"]), (e["drow"], e["dbeam"])))


def test_track_path_shape_and_ranges():
    track = _track()
    for rec, n in REAL:
        frames = list(range(n, n + 6))
        p = track.track_path(rec, n, frames)
        assert p["recording"] == rec and p["keyframe"] == n
        assert p["n_rows"] == U.FRAME_HEIGHT[rec], (
            "%s: track_path n_rows=%d, frame height is %d"
            % (rec, p["n_rows"], U.FRAME_HEIGHT[rec]))
        assert p["n_beams"] == 128, "%s: n_beams=%d" % (rec, p["n_beams"])
        assert len(p["frames"]) == len(frames), "%s: %d frames for %d asked" % (
            rec, len(p["frames"]), len(frames))
        assert [f["frame"] for f in p["frames"]] == frames
        assert p["band_pixels"] > 0
        key = p["frames"][0]
        assert key["frame"] == n and key["drow"] == 0 and key["dbeam"] == 0, (
            "%s: keyframe row %r" % (rec, key))
        assert key["source"] == "keyframe", "%s: keyframe source=%r" % (rec, key["source"])
        for fr in p["frames"][1:]:
            assert fr["source"] in ("chain", "direct"), "%s: source=%r" % (rec, fr["source"])
            assert isinstance(fr["chain"], dict) and isinstance(fr["direct"], dict), (
                "%s frame %d: chain/direct must both be kept for inspection" % (rec, fr["frame"]))
            assert abs(fr["drow"]) <= 160, "%s frame %d: drow=%+d beyond the window" % (
                rec, fr["frame"], fr["drow"])
        assert 0.0 <= p["clipped_frac"] <= 1.0
        lo, hi = p["drow_range"]
        assert lo <= 0 <= hi, "%s: drow_range %r does not contain the keyframe" % (rec, (lo, hi))


def test_track_path_rejects_missing_keyframe():
    track = _track()
    U.assert_raises(KeyError, track.track_path, U.REC_BOMB, 999999, [622, 623])


def test_track_path_unknown_recording_raises():
    track = _track()
    U.assert_raises(KeyError, track.track_path, "1999-01-01_000000", 1, [1, 2])


def test_propagate_boxes_stay_inside_the_frame():
    track = _track()
    box = [40, 300, 70, 340]
    p = track.propagate(U.REC_BOMB, 622, box, list(range(622, 628)))
    assert p["recording"] == U.REC_BOMB and p["keyframe"] == 622
    assert p["keyframe_box"] == box, "keyframe_box=%r" % (p["keyframe_box"],)
    assert p["n_frames"] == 6 and len(p["frames"]) == 6
    assert 0 <= p["n_auto"] <= p["n_frames"]
    assert abs(p["auto_frac"] - p["n_auto"] / p["n_frames"]) < 1e-12
    first = p["frames"][0]
    assert first["box"] == track.clip_box(box, 780, 128), (
        "keyframe box %r != clip_box(box) %r" % (first["box"], track.clip_box(box, 780, 128)))
    for fr in p["frames"]:
        x1, y1, x2, y2 = fr["box"]
        assert 0 <= x1 < x2 <= 128, "frame %d: box x %r" % (fr["frame"], fr["box"])
        assert 0 <= y1 < y2 <= 780, "frame %d: box y %r" % (fr["frame"], fr["box"])
        assert fr["auto"] == bool(fr["align_score"] >= 0.55 and not fr["clipped"]), (
            "frame %d: auto=%r with score=%.3f clipped=%r"
            % (fr["frame"], fr["auto"], fr["align_score"], fr["clipped"]))
        assert fr["box"] == track.clip_box(
            [box[0] + fr["dbeam"], box[1] + fr["drow"],
             box[2] + fr["dbeam"], box[3] + fr["drow"]], 780, 128), (
            "frame %d: box %r != clipped shifted box" % (fr["frame"], fr["box"]))


def test_propagate_on_441_row_recording():
    track = _track()
    p = track.propagate(U.REC_MORTAR, 300, [30, 150, 60, 190], [300, 301, 302])
    assert p["n_frames"] == 3
    for fr in p["frames"]:
        assert 0 <= fr["box"][1] < fr["box"][3] <= 441, (
            "441-row recording: box %r exceeds height 441" % (fr["box"],))


def test_clip_box_clamps_to_frame():
    track = _track()
    assert track.clip_box([-5, -9, 500, 900], 780, 128) == [0, 0, 128, 780]
    assert track.clip_box([10, 20, 30, 40], 780, 128) == [10, 20, 30, 40]


def test_box_contrast_matches_manual_mean():
    track = _track()
    img = _frame(U.REC_BOMB, 622)
    box = [40, 300, 70, 340]
    got = track.box_contrast(img, box)
    assert got["n_px"] == (70 - 40) * (340 - 300), "n_px=%r" % (got["n_px"],)
    U.assert_close(got["mean"], float(img[300:340, 40:70].mean()), 1e-9, "box mean")
