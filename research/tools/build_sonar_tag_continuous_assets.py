"""Build auditable plots and a compact verification record for the tag run."""
import json
from pathlib import Path
import hashlib
import numpy as np
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "_sonar_audit_deps"))
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "DataSet" / "sonar_tag_continuous_camera"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def angle_deg(a, b):
    return float(Rotation.from_matrix(np.asarray(b) @ np.asarray(a).T).magnitude() * 180 / np.pi)


def main():
    selection = read(OUT / "selection.json")
    detections = read(OUT / "detections.json")
    evaluation = read(OUT / "camera_models" / "evaluation.json")
    rows = {r["sample"]: r for r in selection["frames"]}
    detections_by_id = {r["sample"]: r for r in detections["frames"]}

    # Confirm the old two-frame observation was replayed byte-for-byte in the new detector.
    old = read(ROOT / "DataSet" / "sonar_rgb_pose_pilot" / "tag-rotation.json")
    replay = []
    for sid, old_corners in zip(old["samples"], old["corners_fhd"]):
        tag = next(t for t in detections_by_id[sid]["tags"] if t["id"] == 141)
        delta = np.max(np.abs(np.asarray(old_corners) - np.asarray(tag["corners"])))
        replay.append({"sample": sid, "max_corner_difference_px": float(delta)})

    # World-from-tag orientation, using the image-best and the continuity branch.
    series = {}
    for item in evaluation["models"]:
        name = item["model"]["name"]
        # The absolute orientation is arbitrary; report deviation from the first observed view.
        first_r = None
        values = []
        for frame in item["frames"]:
            row = rows[frame["sample"]]
            branch = int(frame["image_continuity_branch"])
            rct = np.asarray(frame["solutions"][branch]["rotation_camera_from_tag"], dtype=float)
            rwct = np.asarray(row["world_from_camera"], dtype=float)[:3, :3] @ rct
            if first_r is None:
                first_r = rwct
            values.append({
                "sample": frame["sample"],
                "aris_frame": int(frame["aris_frame"]),
                "time_s": float(frame["time_s"]),
                "deviation_from_first_world_tag_deg": angle_deg(first_r, rwct),
                "image_continuity_branch": branch,
                "image_best_rms_px": float(frame["solutions"][0]["reprojection_rms_px"]),
            })
        series[name] = values

    (OUT / "temporal-pose-series.json").write_text(
        json.dumps(series, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Plot the diagnostic only. It is deliberately labelled as model-conditional.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True, constrained_layout=True)
    for name, vals in series.items():
        x = [v["aris_frame"] for v in vals]
        y = [v["deviation_from_first_world_tag_deg"] for v in vals]
        label = name.replace('_', ' ') + (' (sparse)' if name.startswith('image_fit') else '')
        axes[0].plot(x, y, ".-", ms=2, lw=.8, label=label)
        axes[1].plot(x, [v["image_best_rms_px"] for v in vals], ".-", ms=2, lw=.8, label=label)
    for ax in axes:
        ax.axvline(392, color="k", ls="--", lw=.7)
        ax.axvline(788, color="k", ls="--", lw=.7)
        ax.grid(alpha=.25)
        ax.legend(fontsize=7, ncol=2)
    axes[0].set_ylabel("world-from-tag deviation from first (deg)")
    axes[1].set_ylabel("tag corner RMS (px)")
    axes[1].set_xlabel("ARIS frame; dashed lines are old anchors 392/788")
    fig.suptitle("Conditional AprilTag temporal diagnostic; no static-world claim")
    fig.savefig(OUT / "temporal-pose-diagnostic.png", dpi=160)
    plt.close(fig)

    solver = read(OUT / "camera_solver_control" / "results.json")
    solver_summary = []
    for group in solver["models"]:
        for run in group["refined"]:
            solver_summary.append({
                "kind": group["kind"], "run": run["run"], "fit_rms_px": run["fit_rms_px"],
                "nfev": run["nfev"], "success": run["success"],
                "anchor_difference_deg": run["anchor_difference_deg"],
                "profile_condition_ratio": run["profile_condition_ratio"],
                "near_intrinsic_bound": run["near_intrinsic_bound"],
                "view_residuals": run["view_residuals"],
            })

    verification = {
        "source": {
            "selection_sha256": sha(OUT / "selection.json"),
            "detections_sha256": sha(OUT / "detections.json"),
            "camera_evaluation_sha256": sha(OUT / "camera_models" / "evaluation.json"),
            "solver_control_sha256": sha(OUT / "camera_solver_control" / "results.json"),
        },
        "counts": {
            "selected_frames": len(selection["frames"]),
            "full_recording_frames": selection["full_manifest_count"],
            "ready_frames": sum(r["status"] == "ready" for r in selection["frames"]),
            "tag141_frames": sum(any(t["id"] == 141 for t in r["tags"]) for r in detections["frames"]),
            "tag_negative_frames": sum(not r["tags"] for r in detections["frames"]),
        },
        "anchor_replay": replay,
        "calibration_selection": {
            "frames": len(read(OUT / "camera_models" / "selection-before-fit.json")["frames"]),
            "fit": sum(r["role"] == "fit" for r in read(OUT / "camera_models" / "selection-before-fit.json")["frames"]),
            "check": sum(r["role"] == "check" for r in read(OUT / "camera_models" / "selection-before-fit.json")["frames"]),
            "all_eligible": read(OUT / "camera_models" / "selection-before-fit.json")["all_eligible_count"],
        },
        "solver_control": solver_summary,
        "interpretation": {
            "pose_series_is_conditional": True,
            "physical_tag_staticness_proven": False,
            "physical_camera_model_identified": False,
            "registration_candidate_approved": False,
            "reason": "Free tag poses absorb tag motion and camera-model errors; background F checks are conditional and mostly planar/low-parallax."
        },
    }
    (OUT / "verification-camera.json").write_text(
        json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
