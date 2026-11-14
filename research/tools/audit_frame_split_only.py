"""Read only the existing train/val split artifact; never open mixed metadata.

This checks artifact consistency, not its agreement with raw images/annotations.
No dataset or model imports and no writes to the original research/data tree.
"""
import hashlib
import json
from pathlib import Path


source = Path(r"D:\pby\uxo-full\repro\frame_split.json")
raw = source.read_bytes()
split = json.loads(raw)
if "test" in split or "test_ids" in split:
    raise RuntimeError("Unexpected test identity list; refuse to process")
train, val = split["train"], split["val"]
recs = split["recordings"]
result = {
    "audit_scope": "existing train/val artifact only; no raw data verification",
    "source": str(source),
    "sha256": hashlib.sha256(raw).hexdigest(),
    "seed": split["seed"],
    "val_frac": split["val_frac"],
    "counts": {"train": len(train), "val": len(val)},
    "duplicate_ids": {"train": len(train) - len(set(train)),
                      "val": len(val) - len(set(val))},
    "frame_id_intersection": len(set(train) & set(val)),
    "counts_match_artifact": split["counts"] == {
        "train": len(train), "val": len(val)},
    "pool_count_matches_union": split["pool"]["frames"] == len(set(train) | set(val)),
    "recordings": {
        "pool": len(recs["pool"]),
        "train": len(recs["train"]),
        "val": len(recs["val"]),
        "intersection": len(set(recs["train"]) & set(recs["val"])),
        "same_train_val_set": set(recs["train"]) == set(recs["val"]),
    },
    "per_class_from_artifact": split["per_class"],
    "excluded_split_counts_from_artifact": split["pool"]["excluded_splits"],
    "source_metadata_hash_recorded_in_artifact": split["source"]["frame_meta_sha256"],
    "not_checked": [
        "current mixed frame_meta.csv or annotation files",
        "test samples or annotations",
        "recording identity accuracy against raw data",
        "frame_idx nearest-neighbour distance",
        "pixel similarity or duplicates",
    ],
}
output = Path(__file__).resolve().parents[1] / "复现" / "camera-baseline" / "frame-split-artifact-check.json"
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
