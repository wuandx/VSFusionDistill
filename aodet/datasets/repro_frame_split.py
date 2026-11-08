"""FrameSplitPairedSonarCameraDataset: frame-level split overlay.

``PairedSonarCameraDataset`` filters on frame_meta.csv's ``split`` column
(aodet/datasets/paired_dataset.py:105), which is recording-level (train /
val / test / val_id).  The CMOLD paper protocol has only training and
validation and splits *frames*, so that partition cannot be expressed in
the column without editing the platform tree.  This class adds the overlay
instead: it reads the ``frame_split.json`` written by
tools/make_frame_split.py and keeps only the sonar image ids listed under
the requested role.

Interface (frozen, configs/repro_cmold relies on it)::

    type="FrameSplitPairedSonarCameraDataset",
    data_root="/mnt/d/pby/uxo-full/paired",     # not repro/
    split_file="/mnt/d/pby/uxo-full/repro/frame_split.json",
    split="train" | "val"

``data_root`` stays the platform root: frame_meta.csv, pairs.csv and
images/ live there, while repro/ only holds the json.  With
``split_file=None`` the class is a transparent stand-in for its parent
(same filters, same order, same metainfo); tests/test_repro_dataset.py
pins that regression.

``ds.split`` reports the role for introspection, but ``load_data_list``
never lets the frame_meta column filter: the id list from ``split_file``
is the only split source here.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from typing import List, Optional

from mmdet.registry import DATASETS

from .paired_dataset import PairedSonarCameraDataset

__all__ = ["FrameSplitPairedSonarCameraDataset", "load_frame_ids"]

ROLES = ("train", "val")


def load_frame_ids(split_file: str, split: str) -> frozenset:
    """Return the sonar_image_id set stored under ``split``.

    Raises:
        FileNotFoundError: the json does not exist.
        ValueError: the json is not an object of id lists, ``split`` has no
            id list, the list is empty, or it repeats ids.
    """
    if not os.path.isfile(split_file):
        raise FileNotFoundError(
            f"frame split file not found: {split_file!r}")
    with open(split_file, encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(
            f"{split_file}: expected a JSON object with 'train'/'val' id "
            f"lists, got {type(payload).__name__}")
    roles = sorted(k for k, v in payload.items() if isinstance(v, list))
    if split not in roles:
        raise ValueError(
            f"{split_file}: no {split!r} id list (available id lists: "
            f"{roles})")
    ids = [int(i) for i in payload[split]]
    if not ids:
        raise ValueError(f"{split_file}: the {split!r} id list is empty")
    counts = Counter(ids)
    dup = sorted(i for i, n in counts.items() if n > 1)
    if dup:
        raise ValueError(
            f"{split_file}: duplicate ids in the {split!r} list: {dup[:5]}")
    return frozenset(ids)


@DATASETS.register_module()
class FrameSplitPairedSonarCameraDataset(PairedSonarCameraDataset):
    """Paired dataset restricted to a frame-level (paper-style) split.

    Args:
        data_root: paired-format root (frame_meta.csv, pairs.csv,
            images/) -- the platform tree, not the repro/ directory.
        split: role to keep, ``"train"`` or ``"val"``, read from
            ``split_file``.  It must be given once ``split_file`` is set:
            ``None`` would silently mean "every frame", test recordings
            included.
        split_file: json written by tools/make_frame_split.py.  ``None``
            keeps the parent behaviour bit for bit.
        **kwargs: forwarded to PairedSonarCameraDataset (pipeline,
            recordings, sonar_gt_sources, ...).
    """

    def __init__(self,
                 data_root: str,
                 split: Optional[str] = "train",
                 split_file: Optional[str] = None,
                 **kwargs):
        self.split_file = None if split_file is None else str(split_file)
        self.frame_split = None
        self._frame_ids = None
        if self.split_file is None:
            super().__init__(data_root=data_root, split=split, **kwargs)
            return
        if split not in ROLES:
            raise ValueError(
                f"split_file is set, so split must be one of {ROLES}, got "
                f"{split!r}; refusing to fall back to 'every frame' "
                f"(that would admit the test recordings)")
        self.frame_split = split
        self._frame_ids = load_frame_ids(self.split_file, split)
        super().__init__(data_root=data_root, split=None, **kwargs)
        # informational only; load_data_list never lets it filter
        self.split = split

    def load_data_list(self) -> List[dict]:
        if self.split_file is None:
            return super().load_data_list()
        keep = self.split
        self.split = None           # the frame_meta column must not filter
        try:
            data_list = super().load_data_list()
        finally:
            self.split = keep
        ids = self._frame_ids
        available = {d["coco_sonar_image_id"] for d in data_list}
        missing = ids - available
        if missing:
            raise ValueError(
                f"{self.split_file}: {len(missing)} of {len(ids)} "
                f"{self.frame_split!r} sonar_image_ids are absent from "
                f"data_root {self.data_prefix.get('img')!r} "
                f"({len(available)} frames available); split_file and "
                f"data_root must describe the same protocol (recordings / "
                f"exclude_recordings also narrow the ids and do not compose "
                f"with a frame split_file); first missing: "
                f"{sorted(missing)[:5]}")
        picked = [d for d in data_list if d["coco_sonar_image_id"] in ids]
        if not picked:
            raise ValueError(
                f"{self.split_file}: the {self.frame_split!r} id list "
                f"selected no frame of data_root "
                f"{self.data_prefix.get('img')!r}")
        return picked
