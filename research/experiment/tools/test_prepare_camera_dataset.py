#!/usr/bin/env python3
"""Test the camera dataset preparation in an isolated temporary directory."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile


def load_module():
    path = Path(__file__).with_name("prepare_camera_dataset.py")
    spec = importlib.util.spec_from_file_location("camera_preparation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_recording(root: Path, group: str, name: str, count: int,
                     out_of_bounds: int = 0) -> None:
    category = root / group / name
    (category / "labels").mkdir(parents=True)
    (category / "gopro").mkdir()
    classes = {
        "100lbs_bomb": "100lbs_aircraft_bomb",
        "100lbs_bomb_(floor)": "100lbs_aircraft_bomb",
        "15cm_mortar": "mortar_shell",
        "20lbs_incendiary": "incindiary_grenade",
    }
    for index in range(count):
        # last `out_of_bounds` frames have a box extending past the image:
        # label space is 640x360; x_max 700 -> 2100 clips to 1920, and
        # y_min 400 -> 1200 clips to above y_max 600 (clipped empty box).
        if index >= count - out_of_bounds:
            # x_max 700 -> 2100 clips to 1920 (still a valid box);
            # y_min 400 -> 1200 clips above y_max 600 (empty after clip).
            x_max, y_min, y_max = (700, 400, 180) if index % 2 else (700, 100, 200)
        else:
            x_max, y_min, y_max = 200, 100, 200
        (category / "labels" / f"{index:04d}.json").write_text(json.dumps({
            "class": classes[group], "x_min": 100, "y_min": y_min,
            "x_max": x_max, "y_max": y_max,
        }))
        (category / "gopro" / f"{index:04d}.jpg").write_bytes(b"image-bytes")


def group_for(name: str) -> str:
    if name.startswith("2023-09-20"):
        return "100lbs_bomb"
    if name in ("2023-09-21_155609", "2023-09-21_160146",
                "2023-09-21_161916", "2023-09-21_162055"):
        return "100lbs_bomb_(floor)"
    if name < "2023-09-21_12":
        return "15cm_mortar"
    return "20lbs_incendiary"


def build_fixture(tmp: Path):
    module = load_module()
    src = tmp / "recordings"
    src.mkdir()
    manifest = {"recordings": {}}
    for split, names in module.SPLITS.items():
        for name in names:
            group = group_for(name)
            write_recording(src, group, name, 7, out_of_bounds=2)
            manifest["recordings"][name] = {
                "category": module.GROUP_CLASSES[group],
                "geometry": "arc", "split": "excluded" if split == "test" else "train",
                "exclude_reason": "sonar calibration",
            }
    old_manifest = tmp / "old.json"
    old_manifest.write_text(json.dumps(manifest))
    return module, src, old_manifest


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        module, src, old_manifest = build_fixture(tmp)
        out = tmp / "dataset"
        summary = module.prepare(src, old_manifest, out, 5)
        n_train = summary["counts"]["train"]["frames"]
        n_val = summary["counts"]["val"]["frames"]
        n_test = summary["counts"]["test"]["frames"]
        assert (n_train, n_val, n_test) == (110, 45, 20), (n_train, n_val, n_test)
        camera = json.loads((out / "camera.json").read_text())
        assert len(camera["images"]) == len(camera["annotations"]) == 175
        assert all(a["area"] > 0 for a in camera["annotations"])
        clipped = [a for a in camera["annotations"] if a["bbox_was_clipped"]]
        assert len(clipped) == 35, len(clipped)
        assert all(a["bbox"][2] + a["bbox"][0] <= 1920 for a in clipped)
        sonar = json.loads((out / "sonar.json").read_text())
        assert len(sonar["images"]) == len(camera["images"])
        assert sonar["annotations"] == []
        progress = json.loads((out / "progress.json").read_text())
        assert progress["status"] == "complete"
        manifest = json.loads((out / "manifest.json").read_text())
        assert manifest["clipped_annotations"] == 35
        assert manifest["counts"]["val"]["classes"] == {
            "100lbs_aircraft_bomb": 15, "incindiary_grenade": 15,
            "mortar_shell": 15}
        # the even sampling of 7 frames capped at 5 keeps indices 0,2,3,4,6;
        # index 6 is one of the out-of-bounds frames -> clipped
        assert not (out / "images" / "camera").joinpath(
            "2023-09-20_171105_0005.jpg").exists()

        try:
            module.prepare(src, old_manifest, out, 5)
        except FileExistsError:
            pass
        else:
            raise AssertionError("refused to overwrite complete output")

        # Interrupted run: completion markers removed -> preparation resumes,
        # image copies are reused, metadata is rebuilt identically.
        (out / "manifest.json").unlink()
        (out / "progress.json").write_text(json.dumps({"status": "incomplete"}))
        (out / "camera.json").unlink()
        summary2 = module.prepare(src, old_manifest, out, 5)
        assert summary2["images_reused"] == 175, summary2["images_reused"]
        assert summary2["images_copied"] == 0
        camera2 = json.loads((out / "camera.json").read_text())
        assert len(camera2["images"]) == 175
    print("camera dataset preparation: all assertions passed")


if __name__ == "__main__":
    main()
