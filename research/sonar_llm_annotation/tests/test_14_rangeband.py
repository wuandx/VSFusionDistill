"""tools/rangeband.py: the range-only prior, and the gate that stops it lying.

The file is an honesty device as much as a geometry device: a single world point either
explains the detections (then any frame gets a *predicted* row band) or it does not (then the
band is the *observed* spread and must be labelled as such).  What is checked here:

  * ``model_ok`` really means p90 <= 0.15 m, and the band half-width is
    ``max(6, ceil(p90 / res_m))`` recomputed from the detections, not trusted from the field;
  * every frame that carries a detection gets a band, and the only frames that do not are the
    ones with no detection at all (nothing to constrain them);
  * a recording whose single-point fit fails says so in words ("does not explain ...") and
    its band comes from the MAD fallback, with one shared row for every frame -- no per-frame
    prediction is invented;
  * fewer than 12 detections is an explicit ``insufficient_detections``, never an exception
    and never an empty-but-plausible-looking band;
  * the 0.15 m switch is exact (0.15 is still believable) and stepping p90 up never makes the
    band narrower.
"""
from __future__ import annotations

import contextlib
import io
import json
import math
import shutil
import sys

import numpy as np

import _util as U

REC_OK = "2023-09-21_105230"      # single-point model explains it
REC_BAD = "2023-09-21_110229"     # it does not
SCHEMA = "sonar_llm_annotation/rangeband/v0"
P90_LIMIT = 0.15


# --------------------------------------------------------------- imports ---
def _rb():
    """Import tools.rangeband (namespace package: REPO must be on sys.path)."""
    if str(U.REPO) not in sys.path:
        sys.path.insert(0, str(U.REPO))
    import tools.rangeband as RB
    return RB


def _locate():
    _rb()
    from tools import locate as L
    return L


def _props(rec):
    """Flattened top-1 blob per frame -- the loader rangeband itself uses."""
    return _locate().load_proposals(U.REPO / "out" / rec / "proposals.jsonl")


def _raw_lines(rec):
    text = (U.REPO / "out" / rec / "proposals.jsonl").read_text(encoding="utf-8")
    return [json.loads(l) for l in text.splitlines() if l.strip()]


def _n_rows(rec):
    return int(_rb().geometry.load_recording(rec).header["SamplesPerBeam"])


# ------------------------------------------------------- synthetic input ---
def _write_proposals(root, rec, frames, cys, snr=9.0):
    d = root / "out" / rec
    d.mkdir(parents=True, exist_ok=True)
    lines = []
    for f, cy in zip(frames, cys):
        lines.append(json.dumps({
            "frame": int(f),
            "blobs": [{"centroid": [float(cy), 40.0], "snr": float(snr),
                       "beam_span": 8, "row_span": 6, "area": 40}],
        }))
    (d / "proposals.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _patch(module, **attrs):
    """Context manager: set module attributes, restore them afterwards."""
    class _Ctx:
        def __enter__(self):
            self.old = {k: getattr(module, k) for k in attrs}
            for k, v in attrs.items():
                setattr(module, k, v)
            return module

        def __exit__(self, *exc):
            for k, v in self.old.items():
                setattr(module, k, v)
            return False
    return _Ctx()


# ------------------------------------------------------------------ tests ---
def test_a_fit_that_rests_on_its_bounds_is_rejected_even_though_the_residuals_pass():
    """``2023-09-21_105230``: residuals fine, fit nevertheless unusable.

    Lead's ruling (2026-11-12) -- expect ``unreliable_model`` here, and never relax
    ``abs(abs(b) - B_HI) < 1e-3``; that veto is the whole point of the gate:

    * the fit lands with ``b = -0.300000`` and ``P_z = -1.9995``, i.e. exactly on two search
      bounds.  A parameter sitting on its bound was not chosen by the data -- the optimiser
      walked into the wall;
    * in that regime a pretty in-sample residual (0.078 m) and an even prettier hold-out one
      (0.118 m) do not mean "solved": ``(P_radial, b)`` are degenerate along a flat valley and
      trade off almost freely while the residual barely moves.  At ~1.5 m the platform shifts
      only ~0.2 m across the pose range, so the lever arm is too short to separate them --
      the degeneracy the original repository docstring names;
    * so the expected outcome is "hold-out passes, parameters on the bounds -> still
      ``unreliable_model``, band from the observed spread", 25 rows.
    """
    RB = _rb()
    L = _locate()
    d = RB.build(REC_OK)

    assert d["schema"] == SCHEMA, "schema=%r" % (d["schema"],)
    assert d["recording"] == REC_OK

    # --- shape of the band, whatever the verdict: every detected frame gets one ---------
    res = d["res_m"]
    n_rows = _n_rows(REC_OK)
    ws, res_m = d["window_start_m"], d["res_m"]
    frames = d["frames"]
    det = {r["frame"] for r in _props(REC_OK) if r["snr"] >= 6.0}
    assert set(det) == {int(k) for k in frames}, (
        "frames do not cover the detections: missing %r"
        % (sorted(det - {int(k) for k in frames})[:8],))
    # the only proposal lines without a band are the ones with no blob to constrain it
    raw = _raw_lines(REC_OK)
    empty = {r["frame"] for r in raw if not (r.get("blobs") or [])}
    assert set(int(r["frame"]) for r in raw) - det == empty, (
        "frames lost detections: %r" % (sorted(set(int(r["frame"]) for r in raw) - det - empty),))
    assert empty == {182, 864}, "unexpected blob-free frames: %r" % (sorted(empty),)

    for key, e in frames.items():
        f = int(key)
        assert e["row_lo"] < e["row"] < e["row_hi"], (
            "frame %d: row=%r not strictly inside [%r, %r]"
            % (f, e["row"], e["row_lo"], e["row_hi"]))
        assert e["row_hi"] - e["row_lo"] == 2 * d["band_rows"], (
            "frame %d: band height %r != 2*band_rows"
            % (f, e["row_hi"] - e["row_lo"]))
        assert 0 <= e["row_lo"] and e["row_hi"] <= n_rows, (
            "frame %d: band [%r, %r] leaves the %d-row frame"
            % (f, e["row_lo"], e["row_hi"], n_rows))
        back = ws + e["row"] * res_m
        assert abs(e["range_m"] - back) <= 2 * res_m, (
            "frame %d: range_m=%.4f does not match row %d (%.4f m)"
            % (f, e["range_m"], e["row"], back))

    # --- the verdict: rejected, and rejected for identifiability, not for accuracy ------
    assert d["status"] == "unreliable_model", (
        "status=%r (bounds_active=%r); a fit with two parameters resting on their bounds must "
        "not be sold as a prediction, however good its residuals look"
        % (d["status"], d.get("bounds_active")))
    assert d["residual_m"]["p90"] <= P90_LIMIT, (
        "this case is only meaningful while the in-sample residuals pass: p90=%.4f m"
        % (d["residual_m"]["p90"],))
    assert d["holdout_m"]["p90"] <= P90_LIMIT, (
        "this case is only meaningful while the *hold-out* passes: p90=%.4f m"
        % (d["holdout_m"]["p90"],))

    # the rejection must be *recognised*, not a lucky coincidence
    assert d["bounds_active"] == {"b": True, "z": True, "xy": False}, (
        "bounds_active=%r" % (d["bounds_active"],))
    assert abs(abs(d["b_m"]) - L.B_HI) < 1e-3, (
        "b_m=%.6f is not on the bias bound %.2f" % (d["b_m"], L.B_HI))
    assert abs(d["P"][2] - L.P_Z_LO) < 1e-3, (
        "P_z=%.6f is not on the depth bound %.2f" % (d["P"][2], L.P_Z_LO))

    # --- and the band is the observed spread, one row shared by every frame --------------
    rng = np.array([ws + p["cy"] * res for p in _props(REC_OK) if p["snr"] >= 6.0])
    spread = float(np.median(np.abs(rng - np.median(rng))))
    want = max(6, int(math.ceil(3 * spread / res)))
    assert d["band_rows"] == want, (
        "band_rows=%r but max(6, ceil(3*MAD/res))=%d" % (d["band_rows"], want))
    assert len({e["row"] for e in frames.values()}) == 1, (
        "the fallback invented per-frame rows: %r"
        % (sorted({e["row"] for e in frames.values()}),))
    assert "bound" in d["note"], "note does not name the bound: %r" % (d["note"],)
    assert "not a prediction" in d["note"].lower()


def test_rejected_model_says_so_and_falls_back_to_the_observed_spread():
    RB = _rb()
    d = RB.build(REC_BAD)

    assert d["status"] == "unreliable_model", (
        "status=%r with residual_m=%r; a bad fit must not be reported as a prediction"
        % (d["status"], d.get("residual_m")))
    p90 = d["residual_m"]["p90"]
    assert p90 > P90_LIMIT, "rejected a model whose p90=%.4f m is inside the limit" % p90

    note = d["note"]
    assert "does not explain" in note, "note does not name the failure: %r" % (note,)
    assert "not a prediction" in note.lower(), (
        "note does not refuse the prediction reading: %r" % (note,))

    # fallback = max(6, ceil(3 * MAD(range) / res)), recomputed from the detections
    use = [r for r in _props(REC_BAD) if r["snr"] >= 6.0]
    ranges = np.array([d["window_start_m"] + r["cy"] * d["res_m"] for r in use])
    mad = float(np.median(np.abs(ranges - np.median(ranges))))
    want = max(6, int(math.ceil(3 * mad / d["res_m"])))
    assert d["band_rows"] == want, (
        "band_rows=%r but the observed spread gives %d rows" % (d["band_rows"], want))

    # one shared row for every frame: the fallback is a statement about the detections,
    # so it must not vary per frame as if it were a per-frame prediction
    rows = {e["row"] for e in d["frames"].values()}
    assert len(rows) == 1, "fallback band claims per-frame rows %r" % (sorted(rows),)
    assert len(d["frames"]) == len(use), (
        "fallback frames=%d, detections=%d" % (len(d["frames"]), len(use)))
    for e in d["frames"].values():
        assert e["row_lo"] < e["row"] < e["row_hi"]


def test_too_few_detections_is_explicit_and_never_raises():
    RB = _rb()
    root = U.fresh_dir("rangeband_synth")
    frames = list(range(300, 311))              # 11 detections: one short of the threshold
    _write_proposals(root, REC_OK, frames, [200] * len(frames))
    with _patch(RB, ROOT=root):
        d = RB.build(REC_OK)
    assert d["status"] == "insufficient_detections", "status=%r" % (d["status"],)
    assert d["frames"] == {}, "an under-determined recording invented %d bands" % len(d["frames"])
    assert d["n_detections"] == 11, "n_detections=%r" % (d["n_detections"],)
    assert "band_rows" not in d, "a band width was reported without evidence"

    # a missing proposals file is the same answer, not a traceback
    empty_root = U.fresh_dir("rangeband_empty")
    with _patch(RB, ROOT=empty_root):
        d0 = RB.build(REC_OK)
    assert d0["status"] == "insufficient_detections", "status=%r" % (d0["status"],)
    assert d0["frames"] == {} and d0["n_detections"] == 0


def test_status_switch_is_exact_and_the_band_never_narrows_as_p90_grows():
    """The gate is judged on the *hold-out*, so that is what the sweep drives.

    ``fit_point`` is replaced by a stub: the in-sample call (all 30 detections) reports a
    tiny residual, the two hold-out calls (15 each) report a fixed bias ``p90``.  range_i is
    built to equal |c_i| exactly, so the hold-out residual is exactly that bias and the
    status must switch at 0.15 m and nowhere else.
    """
    RB = _rb()
    L = _locate()
    root = U.fresh_dir("rangeband_synth")
    frames = list(range(100, 130))                       # 30 detections, over the threshold
    # ranges vary from 1.30 to 1.90 m: the MAD fallback is therefore much wider than the
    # model band, so rejecting the model can never *tighten* the band
    dists = list(np.linspace(1.30, 1.90, len(frames)))
    # take window_start/res_m from the recording itself, so ws + cy*res reproduces dist
    # to float precision and the hold-out residual is the stub's bias and nothing else
    geo = RB.geometry
    ws = float(geo.load_recording(REC_OK).header["WindowStart"])
    res = float(geo.res_m(REC_OK))
    cys = [(d - ws) / res for d in dists]
    _write_proposals(root, REC_OK, frames, cys)

    offset = L.chain_offset()
    gantry = {f: np.array([d, 0.0, 0.0]) - offset for f, d in zip(frames, dists)}
    state = {"p90": 0.0, "n": len(frames), "z": 0.0}

    def fake_fit(C, r_obs, b0=0.0, iters=200):
        if len(r_obs) >= state["n"]:
            # the in-sample fit: believable-looking numbers, and no parameter on a bound
            return np.array([0.0, 0.0, state["z"]]), 0.0, np.full(len(r_obs), 0.01)
        # a hold-out fit: a pure range bias of exactly state["p90"]
        return np.zeros(3), state["p90"], np.zeros(len(r_obs))

    seen = {}
    with _patch(RB, ROOT=root), _patch(L, load_gantry=lambda rec_dir: dict(gantry),
                                       fit_point=fake_fit):
        for p90 in (0.02, 0.05, 0.10, 0.1499, 0.15, 0.1501, 0.20, 0.40):
            state.update(p90=p90, z=0.0)
            d = RB.build(REC_OK)
            seen[p90] = (d["status"], d.get("band_rows"), len(d["frames"]), d.get("note"))
            assert len(d["frames"]) == len(frames), (
                "p90=%.4f: frames=%d != %d detections"
                % (p90, len(d["frames"]), len(frames)))
            assert abs(d["holdout_m"]["p90"] - p90) < 1e-6, (
                "p90=%.4f: hold-out residual measured as %.6f"
                % (p90, d["holdout_m"]["p90"]))

    assert seen[0.15][0] == "model_ok", (
        "hold-out p90 == limit (0.15) must still be believable, got %r (%r)"
        % (seen[0.15][0], seen[0.15][3]))
    assert seen[0.1501][0] == "unreliable_model", (
        "hold-out p90 just over the limit still reported %r" % (seen[0.1501][0],))
    for p in (0.02, 0.05, 0.10, 0.1499, 0.15):
        assert seen[p][0] == "model_ok", "p90=%.4f -> %r" % (p, seen[p][0])
    for p in (0.1501, 0.20, 0.40):
        assert seen[p][0] == "unreliable_model", "p90=%.4f -> %r" % (p, seen[p][0])
    # the in-sample residual was 0.01 m in every case: the rejection must come from the
    # hold-out, and the note must say so instead of blaming `residual_m`
    assert "hold-out" in seen[0.40][3], "note does not name the hold-out: %r" % (seen[0.40][3],)
    assert "0.40" in seen[0.40][3], "note does not quote the hold-out figure: %r" % (seen[0.40][3],)

    model = [seen[p][1] for p in (0.02, 0.05, 0.10, 0.1499, 0.15)]
    assert model == sorted(model), "band narrows as p90 grows: %r" % (model,)
    assert len(set(model)) > 1, "band did not respond to p90 at all: %r" % (model,)

    fallback = [seen[p][1] for p in (0.1501, 0.20, 0.40)]
    assert fallback == [fallback[0]] * 3, (
        "the fallback moved with the rejected model's p90: %r" % (fallback,))
    assert fallback[0] >= model[-1], (
        "rejecting the model made the band narrower (%d < %d rows)"
        % (fallback[0], model[-1]))


def test_a_depth_pinned_to_its_bound_is_rejected_even_with_a_perfect_holdout():
    """Identifiability gate: b or P on a search bound means the data did not choose it.

    This is the rule that decides ``2023-09-21_105230`` (its fit lands on b = -0.30 and
    z = -2.00), so it is tested directly: a perfect hold-out fit with P pinned to its z bound
    must still be refused, and the note must name the bound.
    """
    RB = _rb()
    L = _locate()
    root = U.fresh_dir("rangeband_synth")
    frames = list(range(100, 130))
    dists = list(np.linspace(1.30, 1.90, len(frames)))
    ws, res = 0.6949, 0.0029826
    _write_proposals(root, REC_OK, frames, [(d - ws) / res for d in dists])
    offset = L.chain_offset()
    gantry = {f: np.array([d, 0.0, 0.0]) - offset for f, d in zip(frames, dists)}
    n = len(frames)

    def fake_fit(C, r_obs, b0=0.0, iters=200):
        if len(r_obs) >= n:
            return np.array([0.0, 0.0, float(L.P_Z_LO)]), 0.0, np.full(len(r_obs), 0.005)
        return np.zeros(3), 0.0, np.zeros(len(r_obs))

    with _patch(RB, ROOT=root), _patch(L, load_gantry=lambda rec_dir: dict(gantry),
                                       fit_point=fake_fit):
        d = RB.build(REC_OK)
    assert d["holdout_m"]["p90"] <= P90_LIMIT, (
        "this case is only meaningful with a good hold-out, got %.4f"
        % (d["holdout_m"]["p90"],))
    assert d["bounds_active"]["z"] is True, "the stub pinned z to its bound, bounds=%r" % (
        d["bounds_active"],)
    assert d["status"] == "unreliable_model", (
        "a fit with z on its bound was accepted as model_ok (bounds=%r)" % (d["bounds_active"],))
    assert "bound" in d["note"], "note does not name the bound: %r" % (d["note"],)
    assert "not a prediction" in d["note"].lower()


def test_the_veto_sits_exactly_on_the_bound_not_somewhere_near_it():
    """b = 0.29 is chosen by the data; b = 0.300001 is the optimiser on the wall.

    Synthetic on purpose: the same detections and the same hold-out (0.05 m, well inside the
    0.15 m limit) are used on both sides, so the *only* difference is whether ``b`` reaches
    ``B_HI``.  This pins the veto as a threshold on the bound itself rather than a heuristic
    that happens to fire on ``2023-09-21_105230``.
    """
    RB = _rb()
    L = _locate()
    root = U.fresh_dir("rangeband_synth")
    frames = list(range(100, 130))
    dists = list(np.linspace(1.30, 1.90, len(frames)))
    geo = RB.geometry
    ws = float(geo.load_recording(REC_OK).header["WindowStart"])
    res = float(geo.res_m(REC_OK))
    _write_proposals(root, REC_OK, frames, [(d - ws) / res for d in dists])
    offset = L.chain_offset()
    gantry = {f: np.array([d, 0.0, 0.0]) - offset for f, d in zip(frames, dists)}
    n = len(frames)
    state = {"b": 0.0}

    def fake_fit(C, r_obs, b0=0.0, iters=200):
        if len(r_obs) >= n:
            # the in-sample fit: report b as told -- this is what the bound check reads
            return np.zeros(3), state["b"], np.full(len(r_obs), 0.01)
        # every hold-out fit: a 0.05 m range bias, so the hold-out p90 is exactly 0.05
        return np.zeros(3), 0.05, np.zeros(len(r_obs))

    out = {}
    with _patch(RB, ROOT=root), _patch(L, load_gantry=lambda rec_dir: dict(gantry),
                                       fit_point=fake_fit):
        for b in (0.29, 0.300001):
            state["b"] = b
            out[b] = RB.build(REC_OK)

    inside = out[0.29]
    assert abs(inside["holdout_m"]["p90"] - 0.05) < 1e-6, inside["holdout_m"]
    assert inside["bounds_active"]["b"] is False, (
        "b=0.29 (1e-2 inside the bound) was flagged as resting on it")
    assert inside["status"] == "model_ok", (
        "b=0.29 inside the bound with hold-out p90 0.05 m must stay a prediction, got %r (%r)"
        % (inside["status"], inside["note"]))
    assert inside["band_rows"] == max(6, int(math.ceil(0.05 / inside["res_m"]))), (
        "model band=%r is not ceil(0.05/res)" % (inside["band_rows"],))

    wall = out[0.300001]
    assert abs(wall["holdout_m"]["p90"] - 0.05) < 1e-6, wall["holdout_m"]
    assert wall["bounds_active"]["b"] is True, (
        "b=0.300001 was not recognised as resting on the bound")
    assert wall["status"] == "unreliable_model", (
        "b=0.300001 on the wall with the identical 0.05 m hold-out was accepted as %r"
        % (wall["status"],))
    assert "bound" in wall["note"], "note does not name the bound: %r" % (wall["note"],)
    assert "not a prediction" in wall["note"].lower()


def test_cli_reports_status_and_writes_band_json():
    RB = _rb()
    rec = REC_OK
    root = U.fresh_dir("rangeband_cli")
    dst = root / "out" / rec
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy(U.REPO / "out" / rec / "proposals.jsonl", dst / "proposals.jsonl")

    expected = RB.build(rec)
    buf = io.StringIO()
    with _patch(RB, ROOT=root):
        with contextlib.redirect_stdout(buf):
            rc = RB.main(["--recording", rec])
    out = buf.getvalue()
    assert rc == 0, "CLI returned %r\nstdout:\n%s" % (rc, out)
    assert "status=" in out, "CLI stdout has no status=: %r" % (out,)
    assert "status=%s" % expected["status"] in out, (
        "CLI reported %r, build() said %r" % (out.splitlines()[:1], expected["status"]))

    written = dst / "band.json"
    assert written.is_file(), "CLI did not write %s" % U.rel(written)
    d = json.loads(written.read_text(encoding="utf-8"))
    assert d["schema"] == SCHEMA
    assert d["status"] == expected["status"]
    assert d["frames"], "written band.json has no frames"
    assert set(d["frames"]) == set(expected["frames"]), "CLI wrote a different frame set"

    # the module entry point itself must stay importable/runnable (no writes in this form)
    cp = U.run_py(["-m", "tools.rangeband", "--help"], cwd=U.REPO)
    assert cp.returncode == 0, "python -m tools.rangeband --help failed:\n%s" % (cp.stderr[-2000:],)
    assert "--recording" in cp.stdout, "CLI help does not document --recording"
