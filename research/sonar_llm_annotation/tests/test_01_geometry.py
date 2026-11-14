"""Unit tests for engine/geometry.py.

Covers: frame inventory per recording, row<->range round trip, the audited header
constants (780 vs 441 -- a hardcoded 780 must fail here), the degraded gantry
``predict()`` contract, and the error paths (unknown recording, missing frame).
"""
from __future__ import annotations

import math

import _util as U


def _geom():
    return U.eng("geometry")


def test_frame_inventory_matches_disk():
    G = _geom()
    for rec in U.RECORDINGS:
        r = G.load_recording(rec)
        on_disk = sorted(int(p.stem) for p in U.rec_dir(rec).glob("aris_raw/*.pgm"))
        assert r.n_frames == len(on_disk), (
            "%s: Recording says %d frames, disk has %d" % (rec, r.n_frames, len(on_disk)))
        assert list(r.frames) == on_disk, "%s: frames are not the sorted on-disk list" % rec
        assert r.frame_start == on_disk[0] and r.frame_end == on_disk[-1], (
            "%s: frame_start/end %s/%s != %s/%s"
            % (rec, r.frame_start, r.frame_end, on_disk[0], on_disk[-1]))


def test_header_per_recording_not_hardcoded():
    """2023-09-20_171105 is 780 rows; the two 2023-09-21 recordings are 441."""
    G = _geom()
    for rec in U.RECORDINGS:
        r = G.load_recording(rec)
        want_h = U.FRAME_HEIGHT[rec]
        assert int(r.header["SamplesPerBeam"]) == want_h, (
            "%s: SamplesPerBeam %s, expected %d (hardcoded 780?)"
            % (rec, r.header["SamplesPerBeam"], want_h))
        assert int(r.n_rows) == want_h, "%s: n_rows=%s expected %d" % (rec, r.n_rows, want_h)
        assert int(r.n_beams) == U.FRAME_WIDTH[rec], (
            "%s: n_beams=%s expected %d" % (rec, r.n_beams, U.FRAME_WIDTH[rec]))
        # the geometry must agree with the pixels on disk, not with a constant
        hdr_w, hdr_h = U.read_pgm_header(U.pgm_path(rec, r.frame_start))
        assert int(r.header["SamplesPerBeam"]) == hdr_h, (
            "%s: header says %s rows, PGM says %d" % (rec, r.header["SamplesPerBeam"], hdr_h))
        assert int(r.n_beams) == hdr_w, "%s: beam count %s vs PGM width %d" % (
            rec, r.n_beams, hdr_w)


def test_window_start_length_per_recording():
    G = _geom()
    want = {U.REC_BOMB: (0.6949365, 2.3263969),
            U.REC_GRENADE: (0.6951, 1.3156),
            U.REC_MORTAR: (0.6949, 1.3153)}
    for rec, (ws, wl) in want.items():
        h = G.header_of(rec)
        U.assert_close(h["WindowStart"], ws, 1e-6, "%s WindowStart" % rec)
        U.assert_close(h["WindowLength"], wl, 1e-6, "%s WindowLength" % rec)


def test_range_window_span_per_recording():
    """The 441-row recordings must not report the 780-row (3.02 m) window."""
    G = _geom()
    for rec in U.RECORDINGS:
        r = G.load_recording(rec)
        lo, hi = r.range_window            # a (start, end) tuple on the Recording
        assert (lo, hi) == G.range_window(rec), (
            "%s: Recording.range_window %r != geometry.range_window(rec) %r"
            % (rec, (lo, hi), G.range_window(rec)))
        U.assert_close(lo, float(r.header["WindowStart"]), 1e-9, "%s window start" % rec)
        want_hi = float(r.header["WindowStart"]) + (r.n_rows - 1) * r.res_m
        U.assert_close(hi, want_hi, 1e-9, "%s window end" % rec)
        if U.FRAME_HEIGHT[rec] == 441:
            assert 1.99 < hi < 2.03, "%s: 441-row window ends at %.4f m (780-row constant?)" % (rec, hi)
        else:
            assert 3.00 < hi < 3.04, "%s: 780-row window ends at %.4f m" % (rec, hi)


def test_row_range_roundtrip():
    G = _geom()
    for rec in U.RECORDINGS:
        r = G.load_recording(rec)
        res = r.res_m
        U.assert_close(res, float(r.header["WindowLength"]) / float(r.header["SamplesPerBeam"]),
                       1e-15, "%s res_m != WindowLength/SamplesPerBeam" % rec)
        for j in (0, 1, 17, r.n_rows // 2, r.n_rows - 1):
            want = float(r.header["WindowStart"]) + j * res
            U.assert_close(r.row_range_m(j), want, 1e-12, "%s row_range_m(%d)" % (rec, j))
            U.assert_close(G.range_row_m(r.row_range_m(j), rec), j, 1e-6,
                           "%s range_row_m roundtrip at row %d" % (rec, j))


def test_frame_geom_agrees_with_recording():
    G = _geom()
    for rec in U.RECORDINGS:
        r = G.load_recording(rec)
        f = r.frames[3]
        g = r.frame(f)
        assert g.path == r.pgm_path(f), "%s: FrameGeom.path mismatch" % rec
        # FrameGeom may carry a per-frame WindowStart, so it is self-consistent with its
        # own header, not with the recording-level header.
        for j in (0, 10, r.n_rows - 1):
            U.assert_close(g.range_at_row(j),
                           float(g.header["WindowStart"]) + j
                           * (float(g.header["WindowLength"]) / int(g.header["SamplesPerBeam"])),
                           1e-12, "%s FrameGeom.range_at_row(%d)" % (rec, j))
        lo, hi = g.range_window()
        U.assert_close(lo, g.range_at_row(0), 1e-12, "%s FrameGeom.range_window lo" % rec)
        U.assert_close(hi, g.range_at_row(r.n_rows - 1), 1e-12,
                       "%s FrameGeom.range_window hi" % rec)
        assert int(g.header["SamplesPerBeam"]) == U.FRAME_HEIGHT[rec]


def test_predict_is_unavailable_with_reason():
    """The gantry mapping is degraded on purpose; it must say so instead of inventing a target."""
    G = _geom()
    r = G.load_recording(U.REC_BOMB)
    pred = r.frame(622).predict()
    assert pred["available"] is False, "predict() claims an estimate: %r" % (pred,)
    assert pred["reason"] == "gantry_not_sonar_frame", "reason=%r" % (pred.get("reason"),)
    for key in ("beam", "row", "range_m", "az_deg", "target_xyz_m"):
        assert pred.get(key) is None, "predict()[%r] must be None, got %r" % (key, pred.get(key))
    assert "none" in str(pred.get("convention", "")), (
        "convention should spell out that no geometric convention is in force: %r"
        % (pred.get("convention"),))


def test_beam_angle_requires_fov():
    G = _geom()
    U.assert_raises(ValueError, G.beam_angle_deg, 10, contains="fov_deg")
    # and with an explicit FOV it is a monotone, centred mapping
    vals = [G.beam_angle_deg(i, fov_deg=130.0) for i in range(0, 128, 8)]
    assert vals == sorted(vals), "beam_angle_deg is not monotone in beam index"
    U.assert_close(G.beam_angle_deg(63.5, fov_deg=130.0), 0.0, 1e-6, "centre beam angle")


def test_fov_bound_is_positive_and_ordered():
    G = _geom()
    for rec in U.RECORDINGS:
        b = G.fov_bound(beams_observed=64.0, L_m=0.737 if rec == U.REC_BOMB else 0.442,
                        window=G.range_window(rec))
        assert b["invariant_r_times_theta_rad"] > 0, "%s: non-positive invariant" % rec
        assert b["fov_deg_min"] < b["fov_deg_max"], "%s: empty fov interval" % rec
        assert b["fov_deg_min"] > 0, "%s: fov_deg_min=%.3f" % (rec, b["fov_deg_min"])


def test_intersect_bounds_narrows():
    G = _geom()
    wide = G.fov_bound(beams_observed=64.0, L_m=0.737, window=G.range_window(U.REC_BOMB))
    narrow = G.fov_bound(beams_observed=96.0, L_m=0.737, window=G.range_window(U.REC_BOMB))
    out = G.intersect_bounds([wide, narrow])
    assert out["n"] == 2, "intersect_bounds n=%r" % (out.get("n"),)
    lo, hi = out["fov_deg_interval"]
    assert lo >= max(wide["fov_deg_min"], narrow["fov_deg_min"]) - 1e-9
    assert hi <= min(wide["fov_deg_max"], narrow["fov_deg_max"]) + 1e-9
    # intersecting a bound with itself is idempotent
    same = G.intersect_bounds([wide, wide])
    assert same["fov_deg_interval"] == wide["fov_deg_interval"], (
        "intersect of identical bounds changed the interval: %r vs %r"
        % (same["fov_deg_interval"], wide["fov_deg_interval"]))


def test_unknown_recording_and_missing_frame_raise():
    G = _geom()
    U.assert_raises(KeyError, G.load_recording, "1999-01-01_000000", contains="unknown recording")
    r = G.load_recording(U.REC_MORTAR)
    U.assert_raises(KeyError, r.pgm_path, 999999)
    assert not r.has_frame(999999)
    # Recording.frame() itself is lazy, but nothing may hand out a path for a frame that
    # is not on disk.
    U.assert_raises(KeyError, lambda: r.frame(999999).path)


def test_row_zero_is_window_start_not_zero():
    """Row 0 sits at ~0.695 m, not at 0 m -- a zero-based range axis would be a bug."""
    G = _geom()
    for rec in U.RECORDINGS:
        r = G.load_recording(rec)
        assert r.row_range_m(0) > 0.69, "%s: row 0 at %.4f m" % (rec, r.row_range_m(0))
        assert r.res_m > 0.002 and r.res_m < 0.004, "%s: res_m=%r" % (rec, r.res_m)
        assert math.isfinite(r.res_m)
