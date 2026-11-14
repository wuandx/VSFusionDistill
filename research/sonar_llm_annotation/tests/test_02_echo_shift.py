"""Regression tests for engine/echo.py's structure-band shift estimator.

The bug this file exists for: ``masked_mean_profile`` used a **median** projection.
The structure band covers ~11 % of the frame, so the per-row median was 0 on
essentially every row, the profile collapsed to a constant, the correlation
denominator vanished and ``best_lag`` returned the first lag of the search window --
i.e. a constant ``drow = -max_row`` (score -1.0) on every frame.  A +7 row shift came
back as the search-window floor.

Two distinct claims are tested separately, because they have different verdicts:

* **estimator contract** -- given a band that covers whole rows (so the masked row
  profile is an exact shifted copy), a known integer shift must be recovered exactly
  over the whole +-40 window.  This is the math of ``best_lag``/``masked_mean_profile``
  and it must hold on both 780-row and 441-row frames.
* **default band path** -- ``band=None`` derives the band from ``b`` with
  ``structure_band``, whose mask has a different column subset on every row.  There the
  masked mean is *not* an exact shifted copy, and accuracy is a measured property, not
  a guarantee.  The acceptance criterion quoted by the task owner (+7 rows -> 7 +- 1) is
  asserted here as-is; where real frames miss it the test fails and the numbers are
  printed.

Sign convention under test (echo.estimate_shift docstring): ``row_a = row_b + drow``,
i.e. ``b[y] == a[y + drow]``, i.e. ``b = shift_img(a, -drow)``.
"""
from __future__ import annotations

import numpy as np

import _util as U

# Real frames used for the default-band measurements: two 780-row and two 441-row,
# chosen from the audited recordings (bomb is 780 rows, mortar/grenade are 441).
REAL_FRAMES = (
    (U.REC_BOMB, 622),
    (U.REC_BOMB, 900),
    (U.REC_MORTAR, 300),
    (U.REC_GRENADE, 400),
)


def _echo():
    return U.eng("echo")


def _frame(rec, n):
    return U.read_pgm(U.pgm_path(rec, n))


def test_explicit_band_recovers_known_shifts_on_780_and_441():
    """Contract: with a row-complete band the estimator is exact over the whole window."""
    echo = _echo()
    real = [(rec, n) for rec, n in REAL_FRAMES]
    for rec, n in real:
        a = _frame(rec, n)
        band = np.ones(a.shape, dtype=bool)
        for shift in (-41, -31, -17, -13, -7, -5, -3, 0, 3, 5, 7, 13, 17, 31, 41):
            b = echo.shift_img(a, -shift, 0) if shift else a.copy()
            est = echo.estimate_shift(a, b, band=band)
            assert est["drow"] == shift, (
                "%s frame %d, known %+d row shift -> drow=%+d (score_row=%.4f)"
                % (rec, n, shift, est["drow"], est["score_row"]))
            assert est["score_row"] > 0.999, (
                "%s frame %d, shift %+d: score_row=%.4f for an exact integer shift"
                % (rec, n, shift, est["score_row"]))
            assert not est["clipped"], (
                "%s frame %d, shift %+d reported clipped inside a +-160 window"
                % (rec, n, shift))


def test_default_band_recovers_plus_seven_within_one_row():
    """The headline regression, stated as the task owner did: +7 must come back 7 +- 1.

    Uses the *default* band path (``band=None``) on real frames, which is how every
    caller in engine/ uses it.
    """
    echo = _echo()
    bad = []
    for rec, n in REAL_FRAMES:
        a = _frame(rec, n)
        b = echo.shift_img(a, -7, 0)          # b[y] = a[y+7]  ->  drow = +7
        est = echo.estimate_shift(a, b)
        if abs(est["drow"] - 7) > 1:
            bad.append("%s frame %d: drow=%+d (score_row=%.3f, band_rows=%d)"
                       % (rec, n, est["drow"], est["score_row"],
                          int((echo.structure_band(b).sum(1) > 0).sum())))
    assert not bad, (
        "default-band estimate missed the known +7 shift by more than 1 row "
        "(criterion: 7 +- 1):\n  " + "\n  ".join(bad))


def test_default_band_recovers_minus_seven_within_one_row():
    echo = _echo()
    bad = []
    for rec, n in REAL_FRAMES:
        a = _frame(rec, n)
        b = echo.shift_img(a, 7, 0)           # b[y] = a[y-7]  ->  drow = -7
        est = echo.estimate_shift(a, b)
        if abs(est["drow"] + 7) > 1:
            bad.append("%s frame %d: drow=%+d (score_row=%.3f)"
                       % (rec, n, est["drow"], est["score_row"]))
    assert not bad, (
        "default-band estimate missed the known -7 shift by more than 1 row "
        "(criterion: -7 +- 1):\n  " + "\n  ".join(bad))


def test_default_band_has_no_gross_failure_for_small_shifts():
    """|shift| <= 5 must not collapse to the search bound (the historic -40 symptom).

    Tolerance here is 2 rows, not 1: this case is the *gross failure* guard (does the
    estimator still work at all on real data), while the +-1 acceptance criterion is
    asserted at +-7 above.
    """
    echo = _echo()
    for rec, n in REAL_FRAMES:
        a = _frame(rec, n)
        for shift in (-5, -3, -1, 1, 3, 5):
            b = echo.shift_img(a, -shift, 0)
            est = echo.estimate_shift(a, b)
            assert abs(est["drow"] - shift) <= 2, (
                "%s frame %d, known %+d row shift -> drow=%+d (error %d)"
                % (rec, n, shift, est["drow"], est["drow"] - shift))
            assert est["drow"] not in (-160, 160), (
                "%s frame %d, shift %+d: drow=%+d is the search-window bound, i.e. the "
                "structure profile collapsed" % (rec, n, shift, est["drow"]))
            assert est["score_row"] > 0.3, (
                "%s frame %d, shift %+d: score_row=%.3f -- profile carries no signal"
                % (rec, n, shift, est["score_row"]))


def test_clipped_is_true_only_at_the_search_bound():
    echo = _echo()
    a = _frame(U.REC_BOMB, 622)
    band = np.ones(a.shape, dtype=bool)
    inside = echo.estimate_shift(a, echo.shift_img(a, -20, 0), band=band, max_row=40)
    assert inside["drow"] == 20 and not inside["clipped"], (
        "shift +20 inside +-40 window -> drow=%+d clipped=%r"
        % (inside["drow"], inside["clipped"]))
    at_bound = echo.estimate_shift(a, echo.shift_img(a, -41, 0), band=band, max_row=40)
    assert at_bound["drow"] == 40, (
        "shift +41 outside a +-40 window must saturate at the bound, got %+d"
        % at_bound["drow"])
    assert at_bound["clipped"] is True, (
        "optimum on the search bound must set clipped=True (drow=%+d)" % at_bound["drow"])


def test_degenerate_band_is_signalled_not_silently_trusted():
    """A band with almost no rows must not be reported as a usable measurement.

    Today masked_mean_profile() returns zeros for < 8 valid rows; best_lag then treats
    every lag as undefined (denominator 0) and returns the *first* lag of the window with
    score -1.0.  The estimator must at least flag that: score <= 0 and clipped=True.
    """
    echo = _echo()
    a = _frame(U.REC_BOMB, 622)
    band = np.zeros(a.shape, dtype=bool)
    band[300:303, :] = True                 # 3 rows: below the >= 8-valid-rows floor
    est = echo.estimate_shift(a, echo.shift_img(a, -7, 0), band=band)
    assert est["score_row"] <= 0.0, (
        "undefined correlation must not come back with a positive score: %r" % (est,))
    assert est["clipped"] is True, (
        "a degenerate band returned drow=%+d with clipped=False" % est["drow"])


def test_structure_band_profile_has_real_structure():
    """Direct guard on the defect class: the per-row profile must not be constant."""
    echo = _echo()
    for rec, n in REAL_FRAMES:
        a = _frame(rec, n)
        band = echo.structure_band(a)
        assert band.dtype == np.bool_, "structure_band dtype=%s" % band.dtype
        assert band.shape == a.shape, "band shape %s != frame %s" % (band.shape, a.shape)
        frac = float(band.mean())
        assert 0.01 < frac < 0.6, (
            "%s frame %d: band covers %.1f%% of the frame" % (rec, n, 100 * frac))
        prof = echo.masked_mean_profile(a, band, 1)
        assert prof.shape == (a.shape[0],), "row profile shape %s" % (prof.shape,)
        assert int((np.abs(prof) > 1e-9).sum()) >= 8, (
            "%s frame %d: row profile is non-zero on only %d rows -- it has collapsed"
            % (rec, n, int((np.abs(prof) > 1e-9).sum())))
        assert float(np.std(prof)) > 1.0, (
            "%s frame %d: row profile std=%.4f (constant profile -> search-bound lag)"
            % (rec, n, float(np.std(prof))))


def test_beam_shift_recovered_when_profile_carries_signal():
    """dbeam follows the same convention (col_a = col_b + dbeam).

    Only frames whose row-mean beam profile clears the documented flatness floor
    (std >= 1.0 on both images) can carry lag information at all; those must be exact.
    Real frames sit at std ~0.9-1.3, i.e. on the floor -- see
    ``test_beam_shift_never_fakes_a_measurement`` and the report.
    """
    echo = _echo()
    tested = 0
    for rec, n in ((U.REC_BOMB, 622), (U.REC_GRENADE, 400)):
        a = _frame(rec, n)
        band = np.ones(a.shape, dtype=bool)
        for shift in (-7, -3, 3, 7):
            b = echo.shift_img(a, 0, -shift)
            est = echo.estimate_shift(a, b, band=band)
            qb = echo.masked_mean_profile(b, band, 0)
            if est["score_beam"] == 0.0:
                assert est["dbeam"] == 0 and float(np.std(qb)) < 1.0, (
                    "%s frame %d, shift %+d: score_beam=0 but std(qb)=%.3f and dbeam=%+d"
                    % (rec, n, shift, float(np.std(qb)), est["dbeam"]))
                continue
            tested += 1
            assert est["dbeam"] == shift, (
                "%s frame %d, known %+d beam shift -> dbeam=%+d (score_beam=%.3f)"
                % (rec, n, shift, est["dbeam"], est["score_beam"]))
    assert tested > 0, "no frame produced a usable beam profile at all"


def test_beam_shift_never_fakes_a_measurement():
    """Either a scored dbeam equal to the truth, or an explicit zero -- never a guess."""
    echo = _echo()
    for rec, n in REAL_FRAMES:
        a = _frame(rec, n)
        band = np.ones(a.shape, dtype=bool)
        for shift in (-7, -3, 3, 7):
            est = echo.estimate_shift(a, echo.shift_img(a, 0, -shift), band=band)
            if est["score_beam"] == 0.0:
                assert est["dbeam"] == 0, (
                    "%s frame %d: unscored beam lag must be 0, got dbeam=%+d"
                    % (rec, n, est["dbeam"]))
            else:
                assert est["dbeam"] == shift, (
                    "%s frame %d, known %+d beam shift -> dbeam=%+d with score_beam=%.3f"
                    % (rec, n, shift, est["dbeam"], est["score_beam"]))


def test_441_row_frame_shift_recovered_with_default_band():
    """No 780 assumption: the same estimator on a 441-row recording."""
    echo = _echo()
    a = _frame(U.REC_MORTAR, 300)
    assert a.shape[0] == 441, "fixture frame is %d rows, expected 441" % a.shape[0]
    for shift in (3, -3):
        est = echo.estimate_shift(a, echo.shift_img(a, -shift, 0))
        assert abs(est["drow"] - shift) <= 2, (
            "441-row frame, known %+d shift -> drow=%+d" % (shift, est["drow"]))
        assert abs(est["drow"]) < 160, "441-row frame returned the 160-row search bound"


def test_self_alignment_scores_one():
    echo = _echo()
    for rec, n in REAL_FRAMES:
        a = _frame(rec, n)
        est = echo.estimate_shift(a, a.copy())
        assert est["drow"] == 0 and est["dbeam"] == 0, (
            "%s frame %d self-alignment -> drow=%+d dbeam=%+d"
            % (rec, n, est["drow"], est["dbeam"]))
        assert est["score_row"] > 0.999, (
            "%s frame %d self-alignment score_row=%.4f" % (rec, n, est["score_row"]))


def test_default_band_on_constructed_band_recovers_plus_seven():
    """The constructed-fixture version of the +7 criterion, with no data dependency.

    ``synth_sonar`` draws the documented target: a persistent bright reverberation band
    whose brightness varies with range.  Shifting the whole frame by +7 rows must give
    drow = +7 (criterion from the task owner: 7 +- 1).
    """
    echo = _echo()
    bad = []
    for seed in (11, 12, 13):
        a = U.synth_sonar(780, 128, seed=seed)
        band = echo.structure_band(a)
        prof = echo.masked_mean_profile(a, band, 1)
        est = echo.estimate_shift(a, echo.shift_img(a, -7, 0))
        if abs(est["drow"] - 7) > 1:
            bad.append(
                "seed %d: drow=%+d (score_row=%.3f; band %.1f%% of frame, %d rows, "
                "profile std %.2f)"
                % (seed, est["drow"], est["score_row"], 100 * float(band.mean()),
                   int((band.sum(1) > 0).sum()), float(np.std(prof))))
    assert not bad, (
        "constructed +7 row shift missed the 7 +- 1 criterion:\n  " + "\n  ".join(bad))


def test_track_and_echo_estimators_agree():
    track = U.eng("track")
    echo = _echo()
    a = _frame(U.REC_BOMB, 622)
    band = echo.structure_band(a)
    for shift in (-9, -3, 0, 3, 9):
        b = echo.shift_img(a, -shift, 0) if shift else a.copy()
        e = echo.estimate_shift(a, b, band=band)
        t = track.estimate_shift(a, b, band)
        assert (t["drow"], t["dbeam"]) == (e["drow"], e["dbeam"]), (
            "shift %+d: track.estimate_shift %r != echo.estimate_shift %r"
            % (shift, (t["drow"], t["dbeam"]), (e["drow"], e["dbeam"])))
