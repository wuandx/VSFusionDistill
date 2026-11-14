"""engine/mesh_prior.py: analytic silhouette spans, pose sensitivity, determinism, metadata.

The analytic reference for a sphere of radius R at range r is

    beam_span = degrees(2 * atan(R / r)) / deg_per_beam      (128 beams over 130 deg)
    row_span  = 2 * R / row_m                                (rows are range bins)

A silhouette that is half-size, that ignores the per-recording row_m (780 vs 441), or
that mixes up radians and degrees cannot pass these to 1.5 px.
"""
from __future__ import annotations

import math

import numpy as np

import _util as U

TOL_PX = 1.5


def _mp():
    return U.eng("mesh_prior")


def test_sphere_span_matches_closed_form_within_one_and_a_half_px():
    """A sphere's exact angular width is 2*asin(R/r); 2*atan(R/r) is its small-angle form.

    Both are checked: measurements must follow the exact tangent construction to 1.5 px,
    and wherever the two formulas differ by less than the tolerance the small-angle form
    (the one the task brief states) must agree too.
    """
    M = _mp()
    meta = M.resolve_rec_meta(U.REC_BOMB, 622)
    deg_per_beam = meta.fov_deg / meta.n_beams
    row_m = meta.window_length_m / meta.n_samples
    for diameter in (0.10, 0.20, 0.50):
        mesh = U.synth_sphere_mesh(diameter)
        R = diameter / 2.0
        for range_m in (0.8, 1.0, 1.5, 2.0):
            if R / range_m > 0.7:
                continue
            sil = M.silhouette(mesh, range_m, 0.0, 0.0, 0.0, 0.0, meta)
            want_beam = math.degrees(2.0 * math.asin(R / range_m)) / deg_per_beam
            small_angle = math.degrees(2.0 * math.atan(R / range_m)) / deg_per_beam
            want_row = 2.0 * R / row_m
            assert abs(sil["beam_span_cont_px"] - want_beam) <= TOL_PX, (
                "d=%.2f r=%.1f: beam_span_cont_px=%.2f, exact 2asin(R/r) %.2f "
                "(small-angle 2atan %.2f, tol %.1f)"
                % (diameter, range_m, sil["beam_span_cont_px"], want_beam, small_angle, TOL_PX))
            if abs(small_angle - want_beam) < TOL_PX:
                assert abs(sil["beam_span_cont_px"] - small_angle) <= TOL_PX, (
                    "d=%.2f r=%.1f: beam_span_cont_px=%.2f vs 2atan(L/2r) %.2f"
                    % (diameter, range_m, sil["beam_span_cont_px"], small_angle))
            assert abs(sil["row_span_cont_px"] - want_row) <= TOL_PX, (
                "d=%.2f r=%.1f: row_span_cont_px=%.2f, analytic %.2f (tol %.1f)"
                % (diameter, range_m, sil["row_span_cont_px"], want_row, TOL_PX))
            assert abs(sil["range_min_m"] - (range_m - R)) < 0.06, (
                "d=%.2f r=%.1f: range_min_m=%.3f, expected ~%.3f"
                % (diameter, range_m, sil["range_min_m"], range_m - R))
            assert abs(sil["range_max_m"] - (range_m + R)) < 0.06, (
                "d=%.2f r=%.1f: range_max_m=%.3f, expected ~%.3f"
                % (diameter, range_m, sil["range_max_m"], range_m + R))


def test_sphere_span_uses_the_recording_row_scale():
    """441-row recordings keep the 780-row spacing over a shorter window (2.01 m vs 3.02 m).

    The same object therefore spans the same number of rows; it is the frame height that
    differs, so a hard-coded 780 anywhere shows up here as a shape or offset error.
    """
    M = _mp()
    mesh = U.synth_sphere_mesh(0.20)
    m780 = M.resolve_rec_meta(U.REC_BOMB, 622)
    m441 = M.resolve_rec_meta(U.REC_MORTAR, 300)
    s780 = M.silhouette(mesh, 1.0, 0.0, 0.0, 0.0, 0.0, m780)
    s441 = M.silhouette(mesh, 1.0, 0.0, 0.0, 0.0, 0.0, m441)
    assert m441.n_samples == 441 and m780.n_samples == 780
    row780 = m780.window_length_m / 780
    row441 = m441.window_length_m / 441
    assert abs(row780 - row441) < 1e-6, (
        "row spacing differs between recordings: %.9f vs %.9f" % (row780, row441))
    want = 0.20 / row780
    for tag, sil in (("780", s780), ("441", s441)):
        assert abs(sil["row_span_cont_px"] - want) <= TOL_PX, (
            "%s-row: %.2f vs %.2f" % (tag, sil["row_span_cont_px"], want))
    assert s441["mask"].shape == (441, 128), "441 mask shape %r" % (s441["mask"].shape,)
    assert s780["mask"].shape == (780, 128), "780 mask shape %r" % (s780["mask"].shape,)


def test_long_axis_across_the_beams_matches_closed_form():
    """yaw=90 puts the 0.737 m bomb length across the beams: 2 atan(L/2r)."""
    M = _mp()
    meta = M.resolve_rec_meta(U.REC_BOMB, 622)
    mesh = M.load_mesh("100lbs_aircraft_bomb", max_points=2000)
    L = float(mesh.nominal_length_m)
    sil = M.silhouette(mesh, 1.0, 0.0, 90.0, 0.0, 0.0, meta)
    want = math.degrees(2.0 * math.atan(L / 2.0 / 1.0)) / (meta.fov_deg / meta.n_beams)
    assert abs(sil["beam_span_cont_px"] - want) <= 1.5, (
        "bomb yaw=90 r=1.0: beam_span_cont_px=%.2f, analytic %.2f"
        % (sil["beam_span_cont_px"], want))


def test_mask_is_a_valid_binary_mask_inside_the_frame():
    M = _mp()
    meta = M.resolve_rec_meta(U.REC_BOMB, 622)
    sil = M.silhouette(U.synth_sphere_mesh(0.2), 1.0, 0.0, 30.0, 10.0, 0.0, meta)
    mask = np.asarray(sil["mask"])
    assert mask.dtype == np.bool_, "mask dtype=%s" % mask.dtype
    assert mask.shape == (780, 128)
    assert mask.any(), "silhouette produced an empty mask"
    x1, y1, x2, y2 = sil["box_xyxy"]
    ys, xs = np.nonzero(mask)
    assert (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1) == (x1, y1, x2, y2), (
        "box_xyxy %r does not bound the mask (%r)"
        % ((x1, y1, x2, y2), (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)))
    assert 0 <= x1 < x2 <= 128 and 0 <= y1 < y2 <= 780, "box outside the frame: %r" % (sil["box_xyxy"],)
    assert sil["mask_sha256"] == U.sha256_bytes(mask.tobytes()), (
        "mask_sha256 does not hash the mask bytes (silent determinism break)")


def test_silhouette_is_deterministic_and_pose_sensitive():
    M = _mp()
    meta = M.resolve_rec_meta(U.REC_BOMB, 622)
    mesh = M.load_mesh("mortar_shell", max_points=1200)
    a = M.silhouette(mesh, 1.2, 0.0, 0.0, 0.0, 0.0, meta)
    b = M.silhouette(mesh, 1.2, 0.0, 0.0, 0.0, 0.0, meta)
    assert a["mask_sha256"] == b["mask_sha256"], "identical calls hashed differently"
    assert np.array_equal(a["mask"], b["mask"])
    assert a["beam_span_cont_px"] == b["beam_span_cont_px"]
    c = M.silhouette(mesh, 1.2, 0.0, 90.0, 0.0, 0.0, meta)
    assert c["mask_sha256"] != a["mask_sha256"], "yaw=90 produced the yaw=0 mask"


def test_pose_is_declared_assumed_not_unique():
    M = _mp()
    meta = M.resolve_rec_meta(U.REC_BOMB, 622)
    sil = M.silhouette(U.synth_sphere_mesh(0.2), 1.0, 0.0, 10.0, 5.0, 0.0, meta)
    assert sil["uniqueness"] is False, (
        "a single-view silhouette cannot claim a unique pose: uniqueness=%r" % (sil["uniqueness"],))
    assert isinstance(sil["assumption"], str) and sil["assumption"], "assumption text missing"
    assert isinstance(sil["pose_convention"], str) and sil["pose_convention"]
    assert sil["grid"]["image_shape_row_col"] == [780, 128], "grid=%r" % (sil["grid"],)


def test_resolve_rec_meta_reads_the_audited_headers():
    M = _mp()
    for rec, n, n_samples, wl in (
            (U.REC_BOMB, 622, 780, 2.3263969),
            (U.REC_MORTAR, 300, 441, 1.3153),
            (U.REC_GRENADE, 400, 441, 1.3156)):
        meta = M.resolve_rec_meta(rec, n)
        assert meta.n_samples == n_samples, "%s: n_samples=%r" % (rec, meta.n_samples)
        assert meta.n_beams == 128
        U.assert_close(meta.window_length_m, wl, 1e-3, "%s window_length_m" % rec)
        U.assert_close(meta.window_start_m, 0.6949, 1e-3, "%s window_start_m" % rec)
        assert meta.fov_deg == M.FOV_DEG


def test_plausible_sweep_and_summary_ranges():
    M = _mp()
    meta = M.resolve_rec_meta(U.REC_MORTAR, 300)
    mesh = M.load_mesh("mortar_shell", max_points=600)
    rows = M.plausible_sweep(mesh, 1.2, 0.0, meta, n_yaw=4, n_pitch=2, n_roll=2)
    assert isinstance(rows, list) and len(rows) == 4 * 2 * 2, "sweep returned %d poses" % len(rows)
    for r in rows:
        assert set(r).issuperset({"yaw_deg", "pitch_deg", "roll_deg", "beam_span_px",
                                  "row_span_px", "box_xyxy", "in_frame", "backend"})
        assert r["beam_span_px"] >= 0 and r["row_span_px"] >= 0
    summ = M.sweep_summary(rows)
    assert summ["n_poses"] == len(rows), "summary n_poses=%r" % (summ["n_poses"],)
    assert summ["beam_span_px_min"] <= summ["beam_span_px_max"]
    assert summ["row_span_px_min"] <= summ["row_span_px_max"]
    x1, y1, x2, y2 = summ["envelope_box_xyxy"]
    for r in rows:
        bx1, by1, bx2, by2 = r["box_xyxy"]
        assert x1 <= bx1 and y1 <= by1 and bx2 <= x2 and by2 <= y2, (
            "pose box %r is outside the envelope %r" % (r["box_xyxy"], summ["envelope_box_xyxy"]))
    assert "never a single pose" in summ["note"], "summary note must warn against one pose: %r" % (summ["note"],)


def test_unknown_category_is_rejected():
    M = _mp()
    U.assert_raises(KeyError, M.load_mesh, "nope", contains="unknown category")
