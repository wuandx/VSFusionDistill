"""plugin/sonarllm CLI: status / manifest / check / export behave as documented.

Read-only subcommands run as a real ``python -m sonarllm`` process.  The subcommands that
write into ``out/`` run in-process with the package's OUT redirected into out/_qa/, so the
shared out/<recording>/ tree is never touched by QA.  Export is run as a real subprocess
against a destination inside out/_qa/ (it only reads the real out/).
"""
from __future__ import annotations

import contextlib
import io
import json

import yaml

import _util as U


def _pkg():
    return U.plugin()


def _call(argv, pkg=None):
    """Run cli.main(argv) in-process, capturing stdout/stderr and the exit code."""
    pkg = pkg or _pkg()
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = pkg.cli.main(argv)
    return rc, out.getvalue(), err.getvalue()


def _with_out(tmp):
    """Point the package (and the modules that copied OUT) at *tmp*."""
    pkg = _pkg()
    saved = {"cli": pkg.cli.OUT, "judge": pkg.judge.OUT, "ds": pkg.dataset.OUT}
    pkg.cli.OUT = tmp
    pkg.judge.OUT = tmp
    pkg.dataset.OUT = tmp
    return saved


def _restore(saved):
    pkg = _pkg()
    pkg.cli.OUT = saved["cli"]
    pkg.judge.OUT = saved["judge"]
    pkg.dataset.OUT = saved["ds"]


def _fake_card(tmp, sample):
    root = tmp / "cards"
    root.mkdir(parents=True, exist_ok=True)
    p = root / (sample + ".png")
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + sample.encode())
    return p


def _fake_judgment(tmp, rec, sample, **over):
    d = tmp / rec / "judgments"
    d.mkdir(parents=True, exist_ok=True)
    obj = {"sample": sample, "verdict": "structure", "shape": "short_arc", "box": None,
           "confidence": 0.8, "reason": "贯穿扇面的亮弧", "judge_model": "qa"}
    obj.update(over)
    (d / (sample + ".json")).write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return obj


def test_version_and_status_run_as_real_processes():
    cp = U.run_py(["-m", "sonarllm", "--version"], cwd=U.REPO / "plugin")
    assert cp.returncode == 0, "'--version' failed:\n%s\n%s" % (cp.stdout, cp.stderr)
    assert _pkg().__version__ in cp.stdout, "--version printed %r" % cp.stdout

    cp = U.run_py(["-m", "sonarllm", "status"], cwd=U.REPO / "plugin")
    assert cp.returncode == 0, "'status' failed:\n%s\n%s" % (cp.stdout, cp.stderr)
    assert "sonarllm" in cp.stdout
    assert "recording" in cp.stdout, "status did not print its header:\n%s" % cp.stdout
    assert "proposals" in cp.stdout and "judged" in cp.stdout and "reviews" in cp.stdout
    assert U.REC_BOMB in cp.stdout, (
        "status did not list the recording that has out/ artifacts:\n%s" % cp.stdout)


def test_unknown_subcommand_exits_nonzero():
    cp = U.run_py(["-m", "sonarllm", "nonsense"], cwd=U.REPO / "plugin")
    assert cp.returncode != 0, "an unknown subcommand exited 0"


def test_manifest_lists_cards_and_fails_loudly_without_them():
    tmp = U.fresh_dir("cli", "manifest")
    saved = _with_out(tmp)
    try:
        _fake_card(tmp, "2023-09-20_171105_0622")
        _fake_card(tmp, "2023-09-20_171105_0900")
        rc, out, err = _call(["manifest", "--recording", U.REC_BOMB])
        m = json.loads((tmp / U.REC_BOMB / "judgments" / "_manifest.json").read_text(
            encoding="utf-8"))
        assert rc == 0, "manifest returned %d\n%s\n%s" % (rc, out, err)
        assert m["n_items"] == 2, "n_items=%r (cards present: 2)" % (m["n_items"],)
        assert m["missing_cards"] == []
        assert m["items"][0]["card_sha256"], "manifest item carries no card_sha256"
        printed = json.loads(out)
        assert printed["n_items"] == 2

        rc, out, err = _call(["manifest", "--recording", "1999-01-01_000000"])
        assert rc == 1, "manifest without cards returned %d, expected 1\n%s" % (rc, out)
        assert "没有找到卡片" in err, "no stderr hint about missing cards: %r" % (err,)
    finally:
        _restore(saved)


def test_check_exit_codes_and_error_reporting():
    tmp = U.fresh_dir("cli", "check")
    saved = _with_out(tmp)
    try:
        rc, out, _err = _call(["check", "--recording", U.REC_BOMB])
        assert rc == 1, "check with no judgments returned %d, expected 1\n%s" % (rc, out)
        assert "没有判定文件" in out, out

        _fake_card(tmp, "2023-09-20_171105_0622")
        _fake_judgment(tmp, U.REC_BOMB, "2023-09-20_171105_0622")
        rc, out, _err = _call(["check", "--recording", U.REC_BOMB])
        assert rc == 0, "a valid judgment was rejected:\n%s" % out

        _fake_judgment(tmp, U.REC_BOMB, "2023-09-20_171105_0900", verdict="definitely")
        rc, out, _err = _call(["check", "--recording", U.REC_BOMB])
        assert rc == 2, "an invalid judgment did not return 2 (got %d):\n%s" % (rc, out)
        assert "FAIL" in out and "2023-09-20_171105_0900" in out, (
            "check did not name the offending sample:\n%s" % out)
    finally:
        _restore(saved)


def _export(dst):
    """Run `python -m sonarllm export --dst <dst>` from the repo root (module on PYTHONPATH)."""
    return U.run_py(["-m", "sonarllm", "export", "--dst", str(dst.relative_to(U.REPO))],
                    cwd=U.REPO, env_extra={"PYTHONPATH": str(U.REPO / "plugin")})


def test_export_writes_a_dataset_with_provenance():
    dst = U.fresh_dir("cli", "export")
    cp = _export(dst)
    assert cp.returncode == 0, "export failed:\n%s\n%s" % (cp.stdout, cp.stderr)
    prov = json.loads((dst / "provenance.json").read_text(encoding="utf-8"))
    assert prov["schema"] == "sonarllm/dataset-provenance/v1"
    assert prov["candidate_only_not_training_ready"] is True, (
        "the export claims to be training ready")
    assert "HOLD" in prov["sonar_gt_status"], "GT status is not the HOLD statement"
    assert prov["split_source"].startswith(str(U.REPO.parent / "DataSet")), (
        "split_source does not name the manifest: %r" % (prov["split_source"],))
    assert prov["image_size_default"] == {"width": 128, "height": 780}
    # Fixture review rows are the only thing out/ has ever held for the smoke run, and
    # they must never be exported. Two outcomes are legitimate, and both must be safe:
    #   0 exported -> no data.yaml at all, plus the do-not-train marker
    #  >0 exported -> a data.yaml whose splits come from the manifest
    if prov["n_exported"] == 0:
        assert not (dst / "data.yaml").exists(), (
            "an empty export still wrote data.yaml; a trainer would read it as a "
            "legitimate dataset and silently learn to detect nothing")
        assert (dst / "_EMPTY_DO_NOT_TRAIN.txt").is_file(), (
            "an empty export left no marker explaining why there is no data.yaml")
    else:
        y = yaml.safe_load((dst / "data.yaml").read_text(encoding="utf-8"))
        assert y["train"] == "images/train" and y["val"] == "images/val"
        assert list(y["names"].values()) == list(_pkg().dataset.CLASSES), (
            "class names wrong: %r" % (y["names"],))
        assert "unassigned" not in str(y).lower(), (
            "unassigned leaked into data.yaml splits: %r" % (y,))
    if prov["n_exported"] == 0:
        # Nothing may land on disk when nothing is exportable - a stray train/ dir would
        # make an empty run look like a partial dataset.
        assert not (dst / "images").exists() or not list(
            (dst / "images").rglob("*.png")), "images/ is not empty but nothing is exportable"
    else:
        # out/ now holds real human reviews, so a non-empty export is legitimate: every
        # split directory that data.yaml names must actually hold files.
        for split in ("train", "val"):
            if (dst / "images" / split).is_dir():
                n_img = len(list((dst / "images" / split).glob("*.png")))
                n_lbl = len(list((dst / "labels" / split).glob("*.txt")))
                assert n_img == n_lbl and n_img > 0, (
                    "split %r has %d images but %d labels" % (split, n_img, n_lbl))
    print("      export provenance: n_exported=%r refusals=%r"
          % (prov["n_exported"], prov["refusals"]))


def test_export_refuses_to_write_into_a_nonempty_destination():
    """task-5 asks for an explicit error when the destination already exists.

    Silently merging a second run into a half-written dataset is how a split gets
    corrupted; the export must either refuse or record the merge in provenance.
    """
    dst = U.fresh_dir("cli", "export_twice")
    (dst / "README.txt").write_text("pre-existing dataset\n", encoding="utf-8")
    cp = _export(dst)
    refused = cp.returncode != 0
    if not refused:
        prov_path = dst / "provenance.json"
        prov = json.loads(prov_path.read_text(encoding="utf-8")) if prov_path.exists() else {}
        refused = bool(prov.get("dst_preexisting") or prov.get("merged_into_existing"))
    assert refused, (
        "export wrote into a non-empty destination without refusing or recording it "
        "(exit %d): %s" % (cp.returncode, cp.stdout.strip()[:200]))
