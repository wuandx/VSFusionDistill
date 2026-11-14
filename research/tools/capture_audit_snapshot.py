"""Record explicit, non-test audit inputs without importing research code.

Reads only this allowlist. Does not load checkpoints, mixed annotation files,
images, frame_meta.csv, test predictions, or test metrics. Git is read-only.
"""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess

WORKFLOW = Path(__file__).resolve().parents[1]
RESEARCH = WORKFLOW.parent / "声呐目标检测"
REPO = RESEARCH / "code" / "VSFusionDistill"
FILES = [
    "configs/repro_cmold/teachers/t_camera_s_yoloxs.py",
    "configs/repro_cmold/teachers/t_camera_s_stretch_yoloxs.py",
    "configs/repro_cmold/r0_baseline_yoloxs.py",
    "configs/repro_cmold/uxo_frame_split.py",
    "aodet/datasets/repro_frame_split.py",
    "aodet/datasets/transforms/paired_geometric.py",
    "aodet/models/data_preprocessors/paired_preprocessor.py",
    "tools/test.py",
    "work_dirs/repro_cmold_teacher/t_camera_s/run_meta.txt",
    "work_dirs/repro_cmold_teacher/t_camera_s/t_camera_s_yoloxs.py",
    "results/repro_cmold/t_camera_s/eval_val/ap_summary.json",
    "results/repro_cmold/t_camera_s/eval_val/ap_breakdown.json",
    "results/repro_cmold/t_camera_s/eval_val_stretch/ap_summary.json",
    "results/repro_cmold/t_camera_s_stretch/eval_val/ap_summary.json",
    "results/xeval/e13cam_on_ourval_stretch/ap_summary.json",
]


def git(*args):
    return subprocess.check_output(
        ["git", "--no-optional-locks", "-C", str(REPO), *args],
        text=True, encoding="utf-8"
    ).strip()


def main():
    records = []
    for name in FILES:
        path = REPO / name
        row = {"path": str(path), "exists": path.is_file()}
        if path.is_file():
            data = path.read_bytes()
            row.update(size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        records.append(row)
    for relative in ["experiment/tools/prepare_camera_dataset.py",
                     "DataSet/camera_recording_disjoint_v1/progress.json"]:
        path = WORKFLOW / relative
        if path.is_file():
            data = path.read_bytes()
            records.append({"path": str(path), "exists": True,
                            "size_bytes": len(data),
                            "sha256": hashlib.sha256(data).hexdigest()})
    output = {
        "captured_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        "scope": "explicit non-test file allowlist; cached metrics, not a COCOeval rerun",
        "research_root": str(RESEARCH), "repo": str(REPO),
        "head": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "status_porcelain": git("status", "--porcelain=v1"),
        "files": records,
    }
    target = WORKFLOW / "复现" / "camera-baseline" / "evidence-snapshot-2026-11-10.json"
    if target.exists():
        raise FileExistsError("Keep the previous snapshot; use a new filename for a new audit")
    target.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"snapshot": str(target), "head": output["head"],
                      "clean": not output["status_porcelain"], "files": len(records)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
