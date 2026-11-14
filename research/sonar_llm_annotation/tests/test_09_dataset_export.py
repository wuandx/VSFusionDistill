"""plugin/sonarllm/dataset.py: the three export rules, on a patched out/ tree.

The tree below is synthetic (reviews.jsonl written by this test), but every frame it
names is a real PGM from the real recordings, so image sizes, YOLO normalisation and the
unassigned rule are exercised against the true 128x780 / 128x441 grids.

Rule 1  split comes from the manifest's per-sample paired_role and nowhere else;
        samples without a role go to images/unassigned/, never to train.
Rule 2  provenance.json is always written and never claims training readiness.
Rule 3  fixture self-test rows are skipped unless explicitly allowed.
"""
from __future__ import annotations

import json

import yaml

import _util as U


def _ds():
    return U.plugin().dataset


def _row(rec, sample, frame, box, status="accept", **over):
    row = {"sample": sample, "recording": rec, "category": U.CATEGORY[rec],
           "aris_frame": frame, "candidate_box": box, "final_box": box,
           "status": status, "operator": "qa", "data_source": "human"}
    row.update(over)
    return row


def _build_tree():
    out = U.fresh_dir("ds", "out")
    bomb, mortar, grenade = U.REC_BOMB, U.REC_MORTAR, U.REC_GRENADE
    samples = {
        "val_780": ("%s_0622" % bomb, bomb, 622, [40, 260, 90, 380], "val"),
        "train_441": ("%s_0400" % grenade, grenade, 400, [30, 120, 70, 300], "train"),
        "unassigned_441": ("%s_0300" % mortar, mortar, 300, [30, 120, 70, 300], ""),
        "mixed_780": ("%s_0900" % bomb, bomb, 900, [20, 100, 60, 200], "mixed"),
    }
    rows = {}
    for key, (sample, rec, frame, box, _role) in samples.items():
        rows[key] = _row(rec, sample, frame, box)
    rows["fixture"] = _row(bomb, "%s_1000" % bomb, 1000, [10, 10, 40, 40],
                           data_source="fixture")
    rows["unknown_cat"] = _row(bomb, "%s_1100" % bomb, 1100, [10, 10, 40, 40],
                               category="mystery_object")
    rows["missing_pgm"] = _row(bomb, "%s_99999" % bomb, 99999, [10, 10, 40, 40])
    rows["rejected"] = _row(bomb, "%s_1200" % bomb, 1200, [10, 10, 40, 40], status="reject")
    for rec in (bomb, mortar, grenade):
        d = out / rec
        d.mkdir(parents=True)
        (d / "reviews.jsonl").write_text("", encoding="utf-8")
    by_rec: dict[str, list] = {}
    for r in rows.values():
        by_rec.setdefault(r["recording"], []).append(r)
    for rec, rs in by_rec.items():
        (out / rec / "reviews.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rs) + "\n", encoding="utf-8")
    roles = {"": set(), "val": {"val"}, "train": {"train"}, "mixed": {"train", "val"}}
    sample_roles = {t[0]: roles[t[4]] for t in samples.values()}
    return out, rows, samples, sample_roles


def _export(out, sample_roles, dst):
    ds = _ds()
    saved = (ds.OUT, ds.sample_roles, ds.recording_roles)
    ds.OUT = out
    ds.sample_roles = lambda: dict(sample_roles)
    ds.recording_roles = lambda: {}
    try:
        prov = ds.export(dst)
    finally:
        ds.OUT, ds.sample_roles, ds.recording_roles = saved
    return prov


def test_export_writes_splits_from_roles_and_unassigned_for_the_rest():
    out, rows, samples, sample_roles = _build_tree()
    dst = U.fresh_dir("ds", "export")
    prov = _export(out, sample_roles, dst)

    val_sample = samples["val_780"][0]
    train_sample = samples["train_441"][0]
    unassigned = samples["unassigned_441"][0]
    assert (dst / "labels" / "val" / (val_sample + ".txt")).is_file(), "val label missing"
    assert (dst / "labels" / "train" / (train_sample + ".txt")).is_file(), "train label missing"
    assert (dst / "labels" / "unassigned" / (unassigned + ".txt")).is_file(), (
        "a sample with no paired_role did not go to unassigned/: %s"
        % sorted(p.name for p in (dst / "labels").iterdir()))
    assert not (dst / "images" / "train" / (unassigned + ".png")).exists(), (
        "an unassigned sample was dumped into train/")
    for split in ("train", "val", "unassigned"):
        assert (dst / "images" / split / ({"train": train_sample, "val": val_sample,
                                           "unassigned": unassigned}[split] + ".png")).is_file()
    # fixture / unknown category / missing pgm / rejected must not appear anywhere
    for bad in (rows["fixture"]["sample"], rows["unknown_cat"]["sample"],
                rows["missing_pgm"]["sample"], rows["rejected"]["sample"]):
        hits = list((dst / "labels").rglob(bad + ".txt"))
        assert not hits, "%s was exported" % bad
    n_unassigned_files = len(list((dst / "labels" / "unassigned").glob("*.txt")))
    assert prov["n_unassigned"] == n_unassigned_files == 1, (
        "n_unassigned=%r but %d unassigned labels are on disk"
        % (prov["n_unassigned"], n_unassigned_files))
    assert prov["recordings_per_split"].get("unassigned") == 1, (
        "recordings_per_split=%r" % (prov["recordings_per_split"],))


def test_export_records_every_refusal_reason():
    out, rows, samples, sample_roles = _build_tree()
    dst = U.fresh_dir("ds", "refusals")
    prov = _export(out, sample_roles, dst)
    reasons = {r["reason"] for r in prov["refusals"]}
    assert "mixed_paired_role" in reasons, (
        "a sample with two roles was not refused: %r" % (prov["refusals"],))
    assert "unknown_category" in reasons, "unknown category was not refused: %r" % (
        prov["refusals"],)
    assert "pgm_missing" in reasons, "missing PGM was not refused: %r" % (prov["refusals"],)
    mixed = [r for r in prov["refusals"] if r["reason"] == "mixed_paired_role"]
    assert mixed and mixed[0]["roles"] == ["train", "val"], "refusal did not name the roles: %r" % (
        mixed,)
    on_disk = sorted(p.name for p in dst.rglob("*.txt"))
    assert len(on_disk) == 3, "expected the three legal rows on disk, got %r" % (on_disk,)
    assert prov["n_exported"] == len(on_disk), (
        "provenance claims n_exported=%r but %d labels exist on disk; a row refused after "
        "staging (pgm_missing) is still being counted as exported"
        % (prov["n_exported"], len(on_disk)))


def test_yolo_lines_have_five_normalized_fields_at_the_recording_size():
    out, rows, samples, sample_roles = _build_tree()
    dst = U.fresh_dir("ds", "yolo")
    _export(out, sample_roles, dst)
    bomb = samples["val_780"]
    grenade = samples["train_441"]
    mortar = samples["unassigned_441"]
    cases = [(dst / "labels" / "val" / (bomb[0] + ".txt"), bomb[3], 128, 780),
             (dst / "labels" / "train" / (grenade[0] + ".txt"), grenade[3], 128, 441),
             (dst / "labels" / "unassigned" / (mortar[0] + ".txt"), mortar[3], 128, 441)]
    for path, box, fw, fh in cases:
        parts = path.read_text(encoding="utf-8").strip().split()
        assert len(parts) == 5, "%s: %d fields, expected 5: %r" % (
            path.name, len(parts), parts)
        cls = int(parts[0])
        vals = [float(v) for v in parts[1:]]
        assert 0 <= cls < 3, "%s: class id %d outside the three classes" % (path.name, cls)
        for v in vals:
            assert 0.0 <= v <= 1.0, "%s: normalized value %r outside [0,1]" % (path.name, v)
        x1, y1, x2, y2 = box
        want = [(x1 + x2) / 2.0 / fw, (y1 + y2) / 2.0 / fh,
                (x2 - x1) / fw, (y2 - y1) / fh]
        for got, exp in zip(vals, want):
            assert abs(got - exp) < 1e-6, (
                "%s: %r != %r (frame %dx%d; a 780 constant would give %.6f)"
                % (path.name, vals, want, fw, fh, (y1 + y2) / 2.0 / 780))


def test_images_keep_the_recording_height():
    out, rows, samples, sample_roles = _build_tree()
    dst = U.fresh_dir("ds", "sizes")
    _export(out, sample_roles, dst)
    from PIL import Image
    with Image.open(dst / "images" / "val" / (samples["val_780"][0] + ".png")) as im:
        assert im.size == (128, 780), "780-row PNG is %r" % (im.size,)
    with Image.open(dst / "images" / "train" / (samples["train_441"][0] + ".png")) as im:
        assert im.size == (128, 441), "441-row PNG is %r" % (im.size,)


def test_provenance_and_data_yaml_never_claim_training_readiness():
    out, rows, samples, sample_roles = _build_tree()
    dst = U.fresh_dir("ds", "prov")
    prov = _export(out, sample_roles, dst)
    assert (dst / "provenance.json").is_file(), "provenance.json was not written"
    disk = json.loads((dst / "provenance.json").read_text(encoding="utf-8"))
    for key in ("schema", "candidate_only_not_training_ready", "sonar_gt_status",
                "split_source", "split_policy", "n_unassigned", "unassigned_note",
                "n_exported", "per_recording", "recordings_per_split", "classes",
                "image_size_by_recording", "image_size_default", "coordinate_frame",
                "refusals"):
        assert key in disk, "provenance is missing %r" % (key,)
    assert disk["candidate_only_not_training_ready"] is True
    assert "HOLD" in disk["sonar_gt_status"]
    assert "manifest-resolved.json" in disk["split_source"], (
        "split_source does not name the manifest: %r" % (disk["split_source"],))
    assert "不得被默认塞进 train" in disk["unassigned_note"]
    assert disk["image_size_default"] == {"width": 128, "height": 780}
    assert disk["schema"] == "sonarllm/dataset-provenance/v1"
    y = yaml.safe_load((dst / "data.yaml").read_text(encoding="utf-8"))
    assert set(y) >= {"path", "train", "val", "names"}
    assert y["train"] == "images/train" and y["val"] == "images/val"
    assert "unassigned" not in json.dumps(y), "data.yaml advertises an unassigned split"
    assert len(y["names"]) == 3


def test_real_manifest_roles_are_sparse_and_per_sample():
    """The 20%-coverage claim behind the unassigned rule, measured on the real manifest."""
    ds = _ds()
    roles = ds.sample_roles()
    assert len(roles) > 1000, "sample_roles returned only %d samples" % len(roles)
    with_role = sum(1 for rs in roles.values() if rs)
    frac = with_role / float(len(roles))
    manifest = json.loads(ds.MANIFEST.read_text(encoding="utf-8"))
    items = manifest["items"] if isinstance(manifest, dict) else manifest
    n_items = len(items)
    n_role = sum(1 for it in items if it.get("paired_role"))
    item_frac = n_role / float(n_items)
    assert 0.05 < item_frac < 0.45, (
        "only %.1f%% of manifest items carry a paired_role; the unassigned path is not "
        "the minority case anymore" % (100.0 * item_frac))
    rec_roles = ds.recording_roles()
    assert rec_roles, "recording_roles() is empty"
    assert all(isinstance(v, set) for v in rec_roles.values())
    assert len(rec_roles) > 10, "recording_roles covers only %d recordings" % len(rec_roles)
    print("      manifest: %d items, %d with a role (%.1f%%); %d unique samples, "
          "%d with a role (%.1f%%); %d recordings spanning roles"
          % (n_items, n_role, 100.0 * item_frac, len(roles), with_role, 100.0 * frac,
             sum(1 for v in rec_roles.values() if len(v) > 1)))
