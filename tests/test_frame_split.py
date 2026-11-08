"""Tests for tools/make_frame_split.py (R0 paper-style frame split).

Covers, in the order of the plan's contract (doc/logs/
2026-11-08-cmold-paper-repro-plan.md §2/§6):

1. per-class stratification ratio ~80/20 and disjoint, fully covering
   the pool;
2. seed determinism (same seed -> same split) and seed sensitivity;
3. pool = frame_meta ``split`` in (train, val) only: no ``test`` /
   ``val_id`` frame, and no ``test`` recording, ever enters train/val;
4. product rewriting: ``images[].split`` becomes train/val on the pool
   and keeps the original split elsewhere, with every other image and
   annotation field byte-identical;
5. ``--check`` is read-only, and catches drift between the artifact on
   disk and a fresh build of the frozen seed;
6. the frozen platform numbers (4,152 frames / 37 recordings ->
   3,322 / 830, per class 912/228, 1,061/265, 1,349/337).

Run with the repo venv: pytest tests/test_frame_split.py
"""

import csv
import importlib.util
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATEGORIES = ((1, "alpha"), (2, "beta"), (3, "gamma"))
CAMERA_ID_OFFSET = 1000  # camera and sonar keep separate id spaces


def _tool():
    spec = importlib.util.spec_from_file_location(
        "make_frame_split", os.path.join(ROOT, "tools", "make_frame_split.py"))
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


def _write_platform(root, plan):
    """Synthetic paired root: ``plan`` is [(category_id, split, n), ...].

    Records one sonar box and one camera box per frame (the real platform
    has exactly one of each, verified), and offsets the camera ids so the
    camera role mapping cannot accidentally be satisfied by sonar ids.
    """
    os.makedirs(root, exist_ok=True)
    rows, son_imgs, son_anns, cam_imgs, cam_anns = [], [], [], [], []
    sid = 0
    for cat, split, n in plan:
        for k in range(n):
            sid += 1
            sid_ = str(sid)
            rec = "test_rec_000" if split == "test" else "rec_%d" % (sid % 3)
            rows.append({"sample_id": rec + "_" + sid_, "camera_image_id":
                         CAMERA_ID_OFFSET + sid, "sonar_image_id": sid,
                         "recording": rec, "split": split})
            son_imgs.append({"id": sid, "file_name":
                             "images/sonar/%d.pgm" % sid, "width": 128,
                             "height": 780})
            son_anns.append({"id": sid, "image_id": sid, "category_id": cat,
                             "bbox": [1.0, 2.0, 3.0, 4.0], "area": 12.0,
                             "iscrowd": 0, "segmentation": [],
                             "source": "blob"})
            cam_imgs.append({"id": CAMERA_ID_OFFSET + sid, "file_name":
                             "images/camera/%d.jpg" % sid, "width": 1920,
                             "height": 1080})
            cam_anns.append({"id": sid, "image_id": CAMERA_ID_OFFSET + sid,
                             "category_id": cat, "bbox": [1.0, 2.0, 3.0, 4.0],
                             "area": 12.0, "iscrowd": 0, "segmentation": []})
    cols = ["sample_id", "camera_image_id", "sonar_image_id", "recording",
            "split"]
    with open(os.path.join(root, "frame_meta.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    cats = [{"id": i, "name": n} for i, n in CATEGORIES]
    for name, imgs, anns in (("sonar.json", son_imgs, son_anns),
                             ("camera.json", cam_imgs, cam_anns)):
        with open(os.path.join(root, name), "w", encoding="utf-8") as f:
            json.dump({"images": imgs, "annotations": anns,
                       "categories": cats}, f)
    return rows


def _default_plan():
    # (cat, split, n): pool = 50 + 30 + 10 = 90 frames, val = 18
    return [(1, "train", 40), (1, "val", 10),
            (2, "train", 24), (2, "val", 6),
            (3, "train", 8), (3, "val", 2),
            (1, "test", 5), (2, "val_id", 3)]


# -- 1/2/3: the split itself ------------------------------------------------

def test_stratified_ratio_disjoint_and_covering(tmp_path):
    tool = _tool()
    root = str(tmp_path / "paired")
    _write_platform(root, _default_plan())
    payload = tool.build(root, seed=0, val_frac=0.2)

    assert payload["counts"] == {"train": 72, "val": 18}
    assert payload["per_class"]["alpha"] == {"train": 40, "val": 10,
                                             "total": 50, "val_frac": 0.2}
    assert payload["per_class"]["beta"] == {"train": 24, "val": 6,
                                            "total": 30, "val_frac": 0.2}
    assert payload["per_class"]["gamma"] == {"train": 8, "val": 2,
                                             "total": 10, "val_frac": 0.2}
    train, val = payload["train"], payload["val"]
    assert not set(train) & set(val)
    pool_ids = {r["sonar_image_id"] for r in _rows(root)
                if r["split"] in ("train", "val")}
    assert set(train) | set(val) == pool_ids
    assert len(set(train)) == len(train) and len(set(val)) == len(val)


def test_seed_determinism_and_sensitivity(tmp_path):
    tool = _tool()
    root = str(tmp_path / "paired")
    rows = _write_platform(root, _default_plan())
    a = tool.build(root, seed=0, val_frac=0.2)
    b = tool.build(root, seed=0, val_frac=0.2)
    c = tool.build(root, seed=1, val_frac=0.2)
    assert a["train"] == b["train"] and a["val"] == b["val"]
    assert a["counts"] == c["counts"]
    assert a["per_class"] == c["per_class"]
    assert a["val"] != c["val"]
    # independent re-derivation of the rule: per stratum, the k lowest
    # sha256("<seed>:<id>") ids are val, k = round-half-up(0.2 * n)
    classes, _ = tool.load_frame_classes(root)
    pool = {r["sonar_image_id"] for r in _rows(root)
            if r["split"] in ("train", "val")}
    for cat in (1, 2, 3):
        ids = sorted(i for i in pool if classes.get(i) == (cat,))
        k = int(0.2 * len(ids) + 0.5)
        expect = set(sorted(ids, key=lambda i: (tool._rank(i, 0), i))[:k])
        assert expect == {i for i in ids if i in set(a["val"])}


def test_pool_is_train_plus_val_only(tmp_path):
    tool = _tool()
    root = str(tmp_path / "paired")
    rows = _write_platform(root, _default_plan())
    payload = tool.build(root, seed=0, val_frac=0.2)
    assert payload["pool"]["split_values"] == ["train", "val"]
    assert payload["pool"]["frames"] == 90
    assert payload["pool"]["excluded_splits"] == {"test": 5, "val_id": 3}
    out_of_pool = {r["sonar_image_id"] for r in rows
                   if r["split"] not in ("train", "val")}
    assert not (set(payload["train"]) | set(payload["val"])) & out_of_pool
    # the test recording never makes it into the pool bookkeeping
    assert "test_rec_000" not in payload["recordings"]["pool"]
    assert "test_rec_000" not in payload["recordings"]["train"]
    assert "test_rec_000" not in payload["recordings"]["val"]


def test_check_passes_on_frozen_protocol(tmp_path):
    tool = _tool()
    root = str(tmp_path / "paired")
    rows = _write_platform(root, _default_plan())
    payload = tool.build(root, seed=0, val_frac=0.2)
    pool = tool.pool_rows(rows)
    classes, names = tool.load_frame_classes(
        root, [r["sonar_image_id"] for r in pool])
    ok, lines = tool.check(payload, rows, classes, names)
    assert ok, "\n".join(lines)


# -- 4: products -----------------------------------------------------------

def test_products_rewrite_split_only(tmp_path):
    tool = _tool()
    root = str(tmp_path / "paired")
    rows = _write_platform(root, _default_plan())
    out = str(tmp_path / "repro")
    payload = tool.build(root, seed=0, val_frac=0.2)
    info = tool.write_products(payload, root, out)

    assert info["sonar.json"] == {"test": 5, "train": 72, "val": 18,
                                  "val_id": 3}
    assert info["camera.json"] == info["sonar.json"]

    role = {i: "train" for i in payload["train"]}
    role.update({i: "val" for i in payload["val"]})
    origin = {r["sonar_image_id"]: r["split"] for r in rows}
    cam_of = {r["sonar_image_id"]: r["camera_image_id"] for r in rows}

    with open(os.path.join(root, "sonar.json"), encoding="utf-8") as f:
        src = json.load(f)
    with open(os.path.join(out, "sonar.json"), encoding="utf-8") as f:
        dst = json.load(f)
    assert src["categories"] == dst["categories"]
    assert src["annotations"] == dst["annotations"]
    assert len(src["images"]) == len(dst["images"])
    for s, d in zip(src["images"], dst["images"]):
        expect = role.get(s["id"], origin[s["id"]])
        assert d["split"] == expect
        assert {k: v for k, v in d.items() if k != "split"} == s

    with open(os.path.join(out, "camera.json"), encoding="utf-8") as f:
        cam_dst = json.load(f)
    for im in cam_dst["images"]:
        sid = im["id"] - CAMERA_ID_OFFSET
        assert cam_of[sid] == im["id"]
        assert im["split"] == role.get(sid, origin[sid])
    with open(os.path.join(out, "frame_split.json"), encoding="utf-8") as f:
        art = json.load(f)
    assert art["seed"] == 0 and art["counts"] == {"train": 72, "val": 18}
    assert art["train"] == payload["train"] and art["val"] == payload["val"]
    assert set(art) >= {"seed", "counts", "train", "val"}


# -- 5: --check behaviour --------------------------------------------------

def _cli(tool_path, *args):
    return subprocess.run([sys.executable, tool_path] + list(args),
                          capture_output=True, text=True)


def test_check_is_read_only_and_detects_drift(tmp_path):
    _tool()
    root = str(tmp_path / "paired")
    out = str(tmp_path / "repro")
    _write_platform(root, _default_plan())
    tool_path = os.path.join(ROOT, "tools", "make_frame_split.py")

    r = _cli(tool_path, "--paired-root", root, "--out-dir", out, "--check")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "RESULT: PASS" in r.stdout
    assert not os.path.exists(out)          # --check writes nothing

    r = _cli(tool_path, "--paired-root", root, "--out-dir", out)
    assert r.returncode == 0, r.stdout + r.stderr
    assert os.path.exists(os.path.join(out, "frame_split.json"))

    r = _cli(tool_path, "--paired-root", root, "--out-dir", out, "--check")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "matches a fresh build" in r.stdout

    r = _cli(tool_path, "--paired-root", root, "--out-dir", out,
             "--check", "--seed", "1")
    assert r.returncode == 1
    assert "RESULT: FAIL" in r.stdout
    assert "fields that differ" in r.stdout


# -- 6: the frozen platform -------------------------------------------------

def _platform_root(tool):
    root = os.environ.get("UXO_PAIRED_ROOT")
    if root:
        return root
    return tool.first_existing(tool.PAIRED_ROOT_CANDIDATES)


def test_real_platform_frozen_numbers():
    tool = _tool()
    root = _platform_root(tool)
    if not root:
        import pytest
        pytest.skip("uxo-full paired platform not present")
    payload = tool.build(root, seed=0, val_frac=0.2)
    assert payload["pool"]["frames"] == 4152
    assert payload["pool"]["recordings"] == 37
    assert payload["pool"]["excluded_splits"] == {"test": 1500, "val_id": 594}
    assert payload["counts"] == {"train": 3322, "val": 830}
    assert payload["per_class"] == {
        "100lbs_aircraft_bomb": {"train": 912, "val": 228, "total": 1140,
                                 "val_frac": 0.2},
        "incindiary_grenade": {"train": 1061, "val": 265, "total": 1326,
                               "val_frac": 0.199849},
        "mortar_shell": {"train": 1349, "val": 337, "total": 1686,
                         "val_frac": 0.199881},
    }
    rows = tool.load_frame_meta(os.path.join(root, "frame_meta.csv"))
    test_recs = {r["recording"] for r in rows if r["split"] == "test"}
    used = {r["recording"] for r in rows
            if r["sonar_image_id"] in set(payload["train"]) | set(
                payload["val"])}
    assert len(test_recs) == 10
    assert not used & test_recs
    assert payload["recordings"]["shared"]       # frame-level leakage, plan §9


def test_real_artifact_matches_rebuild():
    tool = _tool()
    root = _platform_root(tool)
    if not root:
        import pytest
        pytest.skip("uxo-full paired platform not present")
    art = os.path.join(tool.default_out_dir(root), "frame_split.json")
    if not os.path.exists(art):
        import pytest
        pytest.skip("D:/pby/uxo-full/repro/frame_split.json not generated")
    with open(art, encoding="utf-8") as f:
        disk = json.load(f)
    fresh = tool.build(root, seed=disk["seed"], val_frac=disk["val_frac"])
    assert disk["train"] == fresh["train"]
    assert disk["val"] == fresh["val"]
    assert disk["counts"] == fresh["counts"]


def _rows(root):
    """frame_meta rows of a synthetic root, ids normalised to int."""
    with open(os.path.join(root, "frame_meta.csv"), newline="",
              encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["sonar_image_id"] = int(r["sonar_image_id"])
        r["camera_image_id"] = int(r["camera_image_id"])
    return rows
