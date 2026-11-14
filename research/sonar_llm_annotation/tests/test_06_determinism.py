"""Determinism: the same input must produce byte-identical output, across processes too.

A card or a shift that changes between runs makes every later review unreproducible, so
these cases compare *separate interpreter runs* (with different PYTHONHASHSEED values),
not two calls inside one process.

Fixture paths travel in a JSON file (out/_qa/det/paths.json) rather than on the command
line, because the data root sits under a Windows path with non-ASCII parent directories.
"""
from __future__ import annotations

import json

import _util as U

PRELUDE = ("import sys, json\n"
           "sys.path.insert(0, '.')\n"
           "P = json.load(open('out/_qa/det/paths.json', encoding='utf-8'))\n")


def _fixture_paths() -> dict:
    d = U.fresh_dir("det")
    files = {
        "bomb_0622": str(U.pgm_path(U.REC_BOMB, 622)),
        "bomb_0900": str(U.pgm_path(U.REC_BOMB, 900)),
        "mortar_300": str(U.pgm_path(U.REC_MORTAR, 300)),
        "det_png": str(d / "det.png"),
    }
    (d / "paths.json").write_text(json.dumps(files, ensure_ascii=False), encoding="utf-8")
    return files


def _run_twice(code: str):
    a = U.run_py(["-c", code], env_extra={"PYTHONHASHSEED": "0"})
    b = U.run_py(["-c", code], env_extra={"PYTHONHASHSEED": "12345"})
    assert a.returncode == 0, "first run failed:\n%s\n%s" % (a.stdout, a.stderr)
    assert b.returncode == 0, "second run failed:\n%s\n%s" % (b.stdout, b.stderr)
    return a.stdout, b.stdout


def test_mesh_prior_silhouette_is_identical_across_processes():
    _fixture_paths()
    code = PRELUDE + (
        "from engine import mesh_prior as M\n"
        "meta = M.resolve_rec_meta('2023-09-20_171105', 622)\n"
        "mesh = M.load_mesh('mortar_shell', max_points=800)\n"
        "s = M.silhouette(mesh, 1.2, 0.0, 37.0, 11.0, 5.0, meta)\n"
        "print(json.dumps({k: s[k] for k in ('mask_sha256','beam_span_cont_px',"
        "'row_span_cont_px','box_xyxy','predicted_area_px')}, sort_keys=True))\n")
    a, b = _run_twice(code)
    assert a == b, "mesh_prior silhouette differs across processes:\n%s\n%s" % (a, b)


def test_cards_render_is_identical_across_processes():
    _fixture_paths()
    code = PRELUDE + (
        "from engine import cards\n"
        "rec = {'sample':'2023-09-20_171105_0622','recording':'2023-09-20_171105',\n"
        "       'aris_frame':622,'image':{'path':P['bomb_0622']},\n"
        "       'candidate':{'box_xyxy':[40,260,90,380]},\n"
        "       'predicted':{'available':False,'reason':'gantry_not_sonar_frame'}}\n"
        "p, m = cards.render_with_meta('2023-09-20_171105_0622', rec, P['det_png'])\n"
        "print(json.dumps({'sha': m['out_sha256'], 'size': m['size_px'], "
        "'zoom': m['zoom']}, sort_keys=True))\n")
    a, b = _run_twice(code)
    assert a == b, "card PNG differs across processes:\n%s\n%s" % (a, b)


def test_echo_estimate_shift_is_identical_across_processes():
    _fixture_paths()
    code = PRELUDE + (
        "from engine import echo\n"
        "a = echo.read_pgm(P['bomb_0622'])\n"
        "b = echo.shift_img(a, -7, 0)\n"
        "e = echo.estimate_shift(a, b)\n"
        "print(json.dumps({k: round(float(e[k]), 9) for k in "
        "('drow','dbeam','score_row','score_beam','score','clipped')}, sort_keys=True))\n")
    a, b = _run_twice(code)
    assert a == b, "estimate_shift differs across processes:\n%s\n%s" % (a, b)


def test_echo_structure_band_and_background_are_identical_across_processes():
    _fixture_paths()
    code = PRELUDE + (
        "from engine import echo\n"
        "a = echo.read_pgm(P['bomb_0622'])\n"
        "band = echo.structure_band(a)\n"
        "bg = echo.background_model('2023-09-20_171105', n_sample=11, n_ref=6)\n"
        "import numpy as np, hashlib\n"
        "print(json.dumps({'band_px': int(band.sum()), 'band_sha': hashlib"
        ".sha256(band.tobytes()).hexdigest(), 'gain': round(float(np.mean(bg['gain'])), 9),"
        "'median_sha': hashlib.sha256(np.asarray(bg['median'], dtype=np.float32)"
        ".tobytes()).hexdigest()}, sort_keys=True))\n")
    a, b = _run_twice(code)
    assert a == b, "structure_band/background_model differs across processes:\n%s\n%s" % (a, b)


def test_track_path_is_identical_across_processes():
    _fixture_paths()
    code = PRELUDE + (
        "from engine import track\n"
        "p = track.track_path('2023-09-20_171105', 622, frames=[622,623,624,625,626])\n"
        "rows = [{k: p['frames'][i][k] for k in ('frame','drow','dbeam','score',"
        "'source','clipped')} for i in range(len(p['frames']))]\n"
        "print(json.dumps({'rows': rows, 'n': p['n_rows'], 'band_pixels': "
        "p['band_pixels'], 'median': round(p['score_median'], 9)}, sort_keys=True))\n")
    a, b = _run_twice(code)
    assert a == b, "track_path differs across processes:\n%s\n%s" % (a, b)


def test_judge_manifest_is_byte_identical_and_ordered():
    pkg = U.plugin()
    judge = pkg.judge
    tmp = U.fresh_dir("det", "manifest")
    cards = tmp / "cards"
    cards.mkdir(parents=True)
    for s in ("2023-09-20_171105_0622", "2023-09-20_171105_0900"):
        (cards / (s + ".png")).write_bytes(b"\x89PNG\r\n\x1a\n" + s.encode())
    old = judge.OUT
    judge.OUT = tmp
    try:
        m1 = judge.build_manifest("2023-09-20_171105")
        raw1 = (tmp / "2023-09-20_171105" / "judgments" / "_manifest.json").read_bytes()
        m2 = judge.build_manifest("2023-09-20_171105")
        raw2 = (tmp / "2023-09-20_171105" / "judgments" / "_manifest.json").read_bytes()
    finally:
        judge.OUT = old
    assert raw1 == raw2, "judge manifest is not byte-identical on a re-run"
    assert m1["n_items"] == 2 and m1["missing_cards"] == [], "manifest=%r" % (m1,)
    assert m2["n_items"] == 2
    assert [i["sample"] for i in m1["items"]] == sorted(i["sample"] for i in m1["items"]), (
        "manifest items are not sorted: %r" % ([i["sample"] for i in m1["items"]],))
    assert m1["items"][0]["card_sha256"] == U.sha256_file(cards / (
        m1["items"][0]["sample"] + ".png"))
