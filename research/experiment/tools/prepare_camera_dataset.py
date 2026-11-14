#!/usr/bin/env python3
"""Prepare an auditable camera-only UXO dataset with recording-disjoint splits.

Design decisions (frozen before any training on this split):

* The split unit is the recording. Train, validation and final test share no
  recording, so near-duplicate neighbouring frames cannot cross roles.
* Roles are stratified by class x acquisition geometry from metadata only.
  No model output was used. Every (class, geometry) combination appears in
  train; validation covers all three classes and arc/aim/line geometries.
* The final test uses recordings that were never converted into any earlier
  paired dataset, never trained on and never evaluated by any earlier model.
  Their only previous role was "excluded by the sonar calibration gate",
  which is irrelevant for a camera-only task that reads no sonar data.
* The five recordings of the original development sample set are allowed in
  train only; none appears in validation or test.
* Camera labels are the native UXO labels (multiplied by 3). Boxes crossing
  the 1920x1080 border are clipped, and the native box plus a clipped flag
  are stored per annotation so the change is auditable.
* Sonar side is a placeholder: this dataset trains a camera-only model and
  must not silently reuse sonar ground truth or sonar quality gates.

The original research tree is never modified. All output goes below --out.
Interrupted runs are safe to repeat: image copies are skipped when the
destination already matches the source size, and metadata is rewritten
atomically only after every recording is processed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil

CATEGORIES = ("100lbs_aircraft_bomb", "incindiary_grenade", "mortar_shell")
GROUP_CLASSES = {
    "100lbs_bomb": "100lbs_aircraft_bomb",
    "100lbs_bomb_(floor)": "100lbs_aircraft_bomb",
    "15cm_mortar": "mortar_shell",
    "20lbs_incendiary": "incindiary_grenade",
}

# Recordings of the original 5-recording development sample (E02-E09 era).
DEV_RECORDINGS = (
    "2023-09-20_180722", "2023-09-21_100927", "2023-09-21_105856",
    "2023-09-21_123500", "2023-09-21_124735",
)

SPLITS = {
    "train": [
        "2023-09-20_171105", "2023-09-20_174439", "2023-09-20_175000",
        "2023-09-20_175506", "2023-09-20_180722", "2023-09-20_181139",
        "2023-09-20_182317",
        "2023-09-21_100927", "2023-09-21_101131", "2023-09-21_101416",
        "2023-09-21_101840", "2023-09-21_102500", "2023-09-21_103728",
        "2023-09-21_104749", "2023-09-21_110049",
        "2023-09-21_120653", "2023-09-21_121124", "2023-09-21_121539",
        "2023-09-21_123500", "2023-09-21_123841", "2023-09-21_124039",
        "2023-09-21_125048",
    ],
    "val": [
        "2023-09-20_173329", "2023-09-20_174200", "2023-09-20_174711",
        "2023-09-21_101622", "2023-09-21_105230", "2023-09-21_110411",
        "2023-09-21_122608", "2023-09-21_122855", "2023-09-21_124915",
    ],
    "test": [
        "2023-09-21_155609", "2023-09-21_160146",
        "2023-09-21_161916", "2023-09-21_162055",
    ],
}

LABEL_KEYS = ("class", "x_min", "y_min", "x_max", "y_max")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative(path: str) -> Path:
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"unsafe relative image path: {path}")
    return Path(*pure.parts)


def even_sample(items: list[str], cap: int) -> list[str]:
    if len(items) <= cap:
        return items
    step = (len(items) - 1) / (cap - 1)
    return [items[round(i * step)] for i in range(cap)]


def write_json_atomic(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".incomplete")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def write_csv_atomic(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".incomplete")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def usable_camera_frames(recording_dir: Path) -> list[str]:
    """Labelled frames whose shipped GoPro jpg exists (sorted by frame index)."""
    labelled = sorted(path for path in (recording_dir / "labels").glob("*.json")
                      if path.stem.isdigit())
    return [path.stem for path in labelled
            if (recording_dir / "gopro" / f"{path.stem}.jpg").is_file()]


def copy_verified(source: Path, destination: Path) -> bool:
    """Copy unless an identical-size file already exists; atomic per file."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size == source.stat().st_size:
        return False
    temporary = destination.with_name(destination.name + ".tmp")
    shutil.copy2(source, temporary)
    os.replace(temporary, destination)
    return True


def prepare(src: Path, old_manifest: Path, out: Path, cap: int) -> dict:
    progress_path = out / "progress.json"
    if progress_path.is_file():
        state = json.loads(progress_path.read_text(encoding="utf-8"))
        if state.get("status") == "complete":
            raise FileExistsError(f"complete dataset will not be overwritten: {out}")
        print(f"Resuming incomplete output at {out}", flush=True)
    out.mkdir(parents=True, exist_ok=True)
    (out / "images" / "camera").mkdir(parents=True, exist_ok=True)
    (out / "images" / "sonar").mkdir(parents=True, exist_ok=True)
    # A constant sonar placeholder lets the paired-format loader run; it is
    # not a sonar annotation and carries no acoustic signal.
    placeholder = out / "images" / "sonar" / "placeholder.pgm"
    if not placeholder.exists():
        placeholder.write_bytes(b"P5\n128 128\n255\n" + bytes(128 * 128))

    assigned = [name for names in SPLITS.values() for name in names]
    assert len(assigned) == len(set(assigned)), "duplicate recording in SPLITS"
    for left, right in (("train", "val"), ("train", "test"), ("val", "test")):
        assert not (set(SPLITS[left]) & set(SPLITS[right])), f"{left}/{right} overlap"

    old = json.loads(old_manifest.read_text(encoding="utf-8"))["recordings"]
    assert all(old[name]["split"] != "test" for name in assigned), \
        "an earlier test recording entered a new role"
    assert set(SPLITS["test"]) <= set(old), "test recordings missing from old manifest"
    assert all(old[name]["split"] == "excluded" for name in SPLITS["test"]), \
        "final test must consist of never-converted recordings"
    assert {old[name]["category"] for name in SPLITS["test"]} == {CATEGORIES[0]}
    assert not (set(SPLITS["val"]) & set(DEV_RECORDINGS)), "dev recording in val"
    assert not (set(SPLITS["test"]) & set(DEV_RECORDINGS)), "dev recording in test"

    images: list[dict] = []
    annotations: list[dict] = []
    frame_rows: list[dict] = []
    recording_rows: list[dict] = []
    image_id = annotation_id = 0
    copied = skipped = clipped = 0
    counts = {role: {"recordings": 0, "frames": 0, "classes": {},
                     "geometries": {}}
              for role in SPLITS}
    label_hashes: dict[str, str] = {}
    image_records: list[dict] = []

    for split, recordings in SPLITS.items():
        for recording in recordings:
            matches = [(group, candidate) for group in GROUP_CLASSES
                       if (candidate := src / group / recording).is_dir()]
            if len(matches) != 1:
                raise ValueError(f"{recording}: expected one source, got {matches}")
            group, rec_dir = matches[0]
            inventory = old[recording]
            usable = even_sample(usable_camera_frames(rec_dir), cap)
            if not usable:
                raise ValueError(f"{recording}: no usable labelled camera frames")
            category = GROUP_CLASSES[group]
            geometry = inventory["geometry"]
            counts[split]["recordings"] += 1
            counts[split]["frames"] += len(usable)
            counts[split]["classes"][category] = (
                counts[split]["classes"].get(category, 0) + len(usable))
            counts[split]["geometries"][geometry] = (
                counts[split]["geometries"].get(geometry, 0) + len(usable))
            recording_rows.append({
                "recording": recording, "split": split, "category": category,
                "geometry": geometry, "category_dir": group,
                "n_frames": len(usable),
                "usable_labelled_frames": len(usable_camera_frames(rec_dir)),
                "old_split": inventory["split"],
                "old_sonar_exclude_reason": inventory["exclude_reason"],
                "inclusion_reason": (
                    "never converted before; reserved final camera test"
                    if split == "test" else
                    "native camera annotations; sonar gate not applied"),
            })
            for frame_idx in usable:
                label_path = rec_dir / "labels" / f"{frame_idx}.json"
                image_path = rec_dir / "gopro" / f"{frame_idx}.jpg"
                label = json.loads(label_path.read_text(encoding="utf-8"))
                if label["class"] != category:
                    raise ValueError(f"class mismatch: {label_path}")
                raw_box = [float(label[k]) * 3 for k in LABEL_KEYS[1:]]
                # Clip boundary-crossing native boxes to the shipped image;
                # keep the native values so the edit is auditable.
                x1, y1 = max(0.0, raw_box[0]), max(0.0, raw_box[1])
                x2, y2 = min(1920.0, raw_box[2]), min(1080.0, raw_box[3])
                if not (x1 < x2 and y1 < y2):
                    raise ValueError(f"empty native camera bbox: {label_path}")
                was_clipped = [x1, y1, x2, y2] != raw_box
                clipped += int(was_clipped)
                image_id += 1
                annotation_id += 1
                sample_id = f"{recording}_{frame_idx}"
                relative = f"images/camera/{sample_id}.jpg"
                destination = out / safe_relative(relative)
                if copy_verified(image_path, destination):
                    copied += 1
                else:
                    skipped += 1
                record = {"sample_id": sample_id,
                          "size_bytes": destination.stat().st_size}
                if split == "test":
                    record["sha256"] = sha256(destination)
                image_records.append(record)
                label_hashes[f"{recording}/{frame_idx}"] = sha256(label_path)
                images.append({"id": image_id, "file_name": relative,
                               "width": 1920, "height": 1080})
                annotations.append({
                    "id": annotation_id, "image_id": image_id,
                    "category_id": CATEGORIES.index(category) + 1,
                    "bbox": [x1, y1, x2 - x1, y2 - y1],
                    "area": (x2 - x1) * (y2 - y1),
                    "iscrowd": 0, "segmentation": [],
                    "native_bbox_xyxy": raw_box,
                    "bbox_was_clipped": was_clipped,
                })
                frame_rows.append({
                    "sample_id": sample_id, "camera_image_id": image_id,
                    "sonar_image_id": image_id, "split": split,
                    "recording": recording, "frame_idx": int(frame_idx),
                    "moving_target": "false", "deg_level": "d0",
                    "source_path_camera": str(image_path.relative_to(src)),
                    "source_path_sonar": "",
                })
            write_csv_atomic(out / "recording_manifest.csv", recording_rows,
                             list(recording_rows[0]))
            write_json_atomic(progress_path, {
                "status": "incomplete", "completed_recording": recording,
                "split": split, "frames_so_far": len(frame_rows),
            })
            print(f"{split:5s} {recording}: {len(usable)} frames", flush=True)

    camera = {"images": images, "annotations": annotations,
              "categories": [{"id": i + 1, "name": name}
                             for i, name in enumerate(CATEGORIES)]}
    sonar = {"images": [{"id": im["id"],
                         "file_name": "images/sonar/placeholder.pgm",
                         "width": 128, "height": 128} for im in images],
             "annotations": [], "categories": camera["categories"]}
    write_json_atomic(out / "camera.json", camera)
    write_json_atomic(out / "sonar.json", sonar)
    write_csv_atomic(out / "pairs.csv", [],
                     ["camera_ann_id", "sonar_ann_id", "sample_id"])
    write_csv_atomic(out / "frame_meta.csv", frame_rows, list(frame_rows[0]))
    summary = {
        "protocol": "camera_recording_disjoint_v1",
        "purpose": ("Camera-only teacher with native camera annotations; "
                    "no sonar ground truth and no sonar quality gates"),
        "split_unit": "recording",
        "stratification": ("class x acquisition geometry, decided from "
                           "metadata before any training on this split"),
        "seed": 0, "cap_per_recording": cap,
        "sampling": "evenly spaced native frame indices, endpoints included",
        "splits": SPLITS, "counts": counts,
        "frames_total": len(frame_rows),
        "annotations_total": len(annotations),
        "clipped_annotations": clipped,
        "images_copied": copied, "images_reused": skipped,
        "test_history": ("all four test recordings were never converted "
                         "into any earlier paired dataset and never used by "
                         "any earlier model"),
        "test_coverage_limit": ("final test contains 100 lb aircraft bombs "
                                "only; per-class generalization must be read "
                                "from the recording-disjoint validation set"),
        "instance_diversity_limit": ("each class is one physical object; "
                                     "cross-recording generalization here is "
                                     "condition/pose generalization, not "
                                     "instance diversity"),
        "dev_recordings_allowed_only_in_train": list(DEV_RECORDINGS),
        "source_root": str(src), "old_manifest": str(old_manifest),
        "old_manifest_sha256": sha256(old_manifest),
        "label_sha256": label_hashes,
        "image_records": image_records,
    }
    write_json_atomic(out / "manifest.json", summary)
    write_json_atomic(progress_path, {"status": "complete",
                                      "frames": len(frame_rows),
                                      "annotations": len(annotations)})
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, required=True)
    parser.add_argument("--old-manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cap", type=int, default=150)
    args = parser.parse_args()
    if args.cap < 2:
        parser.error("--cap must be at least 2")
    summary = prepare(args.src, args.old_manifest, args.out, args.cap)
    print(json.dumps(summary["counts"], indent=2))


if __name__ == "__main__":
    main()
