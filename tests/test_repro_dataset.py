"""Tests for FrameSplitPairedSonarCameraDataset (frame-level split overlay).

The contract under test (frozen; configs/repro_cmold depends on the names):

    type="FrameSplitPairedSonarCameraDataset"
    data_root=<platform paired root>, split_file=<repro/frame_split.json>
    split="train" | "val"

Two layers: synthetic paired roots for the error paths and the
"frame_meta column is ignored" rule, then one pass over the real platform
tree to pin 3,322 / 830 and the exact id sets.
"""

import json
import os

import pytest

pytest.importorskip("mmdet")

from aodet.datasets import (  # noqa: E402
    FrameSplitPairedSonarCameraDataset,
    PairedSonarCameraDataset,
)
from aodet.datasets.paired_format import PairedData, write_paired  # noqa: E402

PAIRED_ROOT = next(
    (p for p in ("/mnt/d/pby/uxo-full/paired", "D:/pby/uxo-full/paired")
     if os.path.isdir(p)), None)
SPLIT_FILE = next(
    (p for p in ("/mnt/d/pby/uxo-full/repro/frame_split.json",
                 "D:/pby/uxo-full/repro/frame_split.json")
     if os.path.isfile(p)), None)

NEEDS_PLATFORM = pytest.mark.skipif(
    PAIRED_ROOT is None or SPLIT_FILE is None,
    reason="platform tree D:/pby/uxo-full/{paired,repro} not mounted")

KW = dict(serialize_data=False, lazy_init=False)


def _write_split_json(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return path


def _toy_root(tmp_path, n=6, frame_split="train"):
    """A minimal paired root (no image files; only the json/csv matter)."""
    root = str(tmp_path / "paired")
    cam_imgs = [dict(id=i, file_name=f"images/camera/c{i}.jpg",
                     width=32, height=24) for i in range(1, n + 1)]
    son_imgs = [dict(id=i, file_name=f"images/sonar/s{i}.pgm",
                     width=32, height=24) for i in range(1, n + 1)]
    cam_anns, son_anns, meta = [], [], []
    for i in range(1, n + 1):
        cam_anns.append(dict(id=i, image_id=i, category_id=1,
                             bbox=[2, 3, 8, 6], area=48, iscrowd=0))
        son_anns.append(dict(id=i, image_id=i, category_id=1,
                             bbox=[2, 3, 8, 6], area=48, iscrowd=0,
                             source="blob"))
        meta.append(dict(sample_id=f"s{i}", camera_image_id=i,
                         sonar_image_id=i, split=frame_split,
                         deg_level="d0", deg_seed="0"))
    write_paired(root, PairedData(
        camera=dict(images=cam_imgs, annotations=cam_anns,
                    categories=[dict(id=1, name="uxo")]),
        sonar=dict(images=son_imgs, annotations=son_anns,
                   categories=[dict(id=1, name="uxo")]),
        pairs=[], frame_meta=meta))
    return root


def _ids(dataset):
    return [d["coco_sonar_image_id"] for d in dataset.data_list]


# --------------------------------------------------------------- synthetic
def test_frame_split_ignores_frame_meta_column(tmp_path):
    """frame_meta says 'val' everywhere; the json still decides."""
    root = _toy_root(tmp_path, n=6, frame_split="val")
    split = _write_split_json(str(tmp_path / "frame_split.json"),
                              {"seed": 0, "train": [1, 2, 3],
                               "val": [4, 5]})
    ds = FrameSplitPairedSonarCameraDataset(
        data_root=root, split_file=split, split="train", **KW)
    assert _ids(ds) == [1, 2, 3]
    assert ds.frame_split == "train"
    assert ds.split == "train"          # informational mirror
    val = FrameSplitPairedSonarCameraDataset(
        data_root=root, split_file=split, split="val", **KW)
    assert _ids(val) == [4, 5]
    # frame 6 is in the frame_meta but in neither role
    assert 6 not in _ids(ds) + _ids(val)


def test_split_file_none_is_the_parent(tmp_path):
    root = _toy_root(tmp_path, n=6, frame_split="train")
    parent = PairedSonarCameraDataset(data_root=root, split="train", **KW)
    child = FrameSplitPairedSonarCameraDataset(
        data_root=root, split_file=None, split="train", **KW)
    assert _ids(child) == _ids(parent) == [1, 2, 3, 4, 5, 6]
    assert child.frame_split is None and child.split_file is None


def test_split_file_requires_a_role(tmp_path):
    root = _toy_root(tmp_path)
    split = _write_split_json(str(tmp_path / "frame_split.json"),
                              {"train": [1], "val": [2]})
    for bad in (None, "test", "val_id"):
        with pytest.raises(ValueError, match="refusing to fall back"):
            FrameSplitPairedSonarCameraDataset(
                data_root=root, split_file=split, split=bad, **KW)


def test_split_file_roles_compose_with_recordings(tmp_path):
    """Recordings narrow the ids: the missing-id guard then fires."""
    root = _toy_root(tmp_path)
    split = _write_split_json(str(tmp_path / "frame_split.json"),
                              {"train": [1, 2], "val": [3]})
    ds = FrameSplitPairedSonarCameraDataset(
        data_root=root, split_file=split, split="train", **KW)
    assert _ids(ds) == [1, 2]
    with pytest.raises(ValueError, match="absent from data_root"):
        FrameSplitPairedSonarCameraDataset(
            data_root=root, split_file=split, split="val",
            recordings=["nope"], **KW)


def test_load_frame_ids_error_messages(tmp_path):
    from aodet.datasets.repro_frame_split import load_frame_ids

    with pytest.raises(FileNotFoundError, match="not found"):
        load_frame_ids(str(tmp_path / "absent.json"), "train")

    bad_type = _write_split_json(str(tmp_path / "a.json"), [1, 2])
    with pytest.raises(ValueError, match="expected a JSON object"):
        load_frame_ids(bad_type, "train")

    no_role = _write_split_json(str(tmp_path / "b.json"), {"train": [1]})
    with pytest.raises(ValueError, match="available id lists"):
        load_frame_ids(no_role, "val")

    empty = _write_split_json(str(tmp_path / "c.json"),
                              {"train": [], "val": [1]})
    with pytest.raises(ValueError, match="is empty"):
        load_frame_ids(empty, "train")

    dup = _write_split_json(str(tmp_path / "d.json"),
                            {"train": [1, 1, 2], "val": [3]})
    with pytest.raises(ValueError, match="duplicate ids"):
        load_frame_ids(dup, "train")


# ------------------------------------------------------------------- real
@NEEDS_PLATFORM
def test_real_frame_split_sizes_and_ids():
    with open(SPLIT_FILE, encoding="utf-8") as f:
        payload = json.load(f)
    train = FrameSplitPairedSonarCameraDataset(
        data_root=PAIRED_ROOT, split_file=SPLIT_FILE, split="train", **KW)
    val = FrameSplitPairedSonarCameraDataset(
        data_root=PAIRED_ROOT, split_file=SPLIT_FILE, split="val", **KW)
    assert (len(train), len(val)) == (3322, 830)
    assert sorted(_ids(train)) == sorted(payload["train"])
    assert sorted(_ids(val)) == sorted(payload["val"])
    assert not set(_ids(train)) & set(_ids(val))
    assert payload["counts"] == {"train": 3322, "val": 830}
    # no test frame (1,500) and no val_id frame (594) can appear: the
    # tool's pool was frame_meta split in (train, val) only
    seen = {d["meta"]["split"] for d in train.data_list + val.data_list}
    assert seen <= {"train", "val"}
    assert len(set(_ids(train))) == len(train)


@NEEDS_PLATFORM
def test_real_split_file_none_matches_parent():
    parent = PairedSonarCameraDataset(
        data_root=PAIRED_ROOT, split="train", **KW)
    child = FrameSplitPairedSonarCameraDataset(
        data_root=PAIRED_ROOT, split_file=None, split="train", **KW)
    assert _ids(child) == _ids(parent)
    assert len(child) == 2652
    everything = FrameSplitPairedSonarCameraDataset(
        data_root=PAIRED_ROOT, split_file=None, split=None, **KW)
    assert len(everything) == 6246


@NEEDS_PLATFORM
def test_real_roles_are_frame_level_not_recording_level():
    """A frame split shares recordings: both roles see the same 37."""
    def recs(split):
        ds = FrameSplitPairedSonarCameraDataset(
            data_root=PAIRED_ROOT, split_file=SPLIT_FILE, split=split, **KW)
        return {d["meta"]["recording"] for d in ds.data_list}

    train, val = recs("train"), recs("val")
    assert train == val
    assert len(train) == 37


@NEEDS_PLATFORM
def test_real_foreign_split_file_raises(tmp_path):
    split = _write_split_json(str(tmp_path / "frame_split.json"),
                              {"train": [10 ** 8], "val": [1]})
    with pytest.raises(ValueError, match="absent from data_root"):
        FrameSplitPairedSonarCameraDataset(
            data_root=PAIRED_ROOT, split_file=split, split="train", **KW)
