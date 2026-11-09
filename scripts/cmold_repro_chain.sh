#!/usr/bin/env bash
# CMOLD paper-style repro chain -- branch exp/cmold-paper-repro, 2026-11-08.
#
# Scope: the four ladder arms of doc/logs/2026-11-08-cmold-paper-repro-plan.md
#   §4 ladder   R0 sonar-only / R2 CMOLD / R3a obj-only / R3b cls-only
#   §7 roles    this script is the repro-run deliverable
#   §8 criteria smoke = finite losses, VRAM peak; R0 gate |AP-0.661| <= 0.05
#
# Recorded deviations (lead, 2026-11-08):
#   * R0 runs WITHOUT Mosaic/MixUp.  The repo has no implementation of
#     either (only the three prohibitive comments in paired_uxo.py:6,
#     paired_geometric.py:10, two_stream_yolox.py:16) and adding one to a
#     paired two-stream pipeline is a data-semantics change.  Logged as a
#     known deviation; if R0 lands below 0.611 the question is reopened.
#   * Data contract: data_root = /mnt/d/pby/uxo-full/paired (that is where
#     frame_meta.csv, pairs.csv and images/ live); the frame-level split
#     arrives as split_file=/mnt/d/pby/uxo-full/repro/frame_split.json on a
#     PairedSonarCameraDataset subclass.  /repro/ holds only that JSON --
#     preflight must not wait for images/ or frame_meta.csv there.
#
# Discipline (CLAUDE.md "无人值守长任务"):
#   * one .ok breakpoint per stage, kept OUTSIDE the working tree
#     ($HOME/mycode/cmold_repro_state) so no marker is ever committed;
#   * two attempts per stage, then the chain stops (never loops forever);
#   * per-arm log file, every stage appends, never truncates;
#   * the training step is launched in the background and must still be
#     alive 10 minutes later, otherwise the attempt counts as failed;
#   * heartbeat every 10 min: nvidia-smi memory + newest checkpoint.
#
# Write scopes (plan §5): everything this script produces lands in
#   work_dirs/repro_cmold/<arm>/        training artifacts (git-ignored)
#   results/repro_cmold/<arm>/          preflight, eval dumps, smoke numbers
#   $HOME/mycode/cmold_repro_<arm>.log  per-arm log
#   $HOME/mycode/cmold_repro_state/     .ok breakpoints
#
# Environment note (measured 2026-11-08, differs from the plan's §0 line):
#   the Windows-side checkout /mnt/d/agent_workspace/.../code/VSFusionDistill
#   has NO .venv-gpu of its own; the only GPU interpreter is the old
#   checkout's /home/ty/mycode/VSFusionDistill/.venv-gpu/bin/python.  That
#   interpreter imports aodet from the CURRENT working directory (tools/
#   train.py:53-54 puts the repo root on sys.path), so running it from the
#   Windows-side checkout executes the Windows-side code.  Verified: aodet
#   resolves to /mnt/d/.../code/VSFusionDistill/aodet/__init__.py.
#   Resolution order below: $CMOLD_PY, $REPO/.venv-gpu, old checkout.
#
# Usage:
#   scripts/cmold_repro_chain.sh --arm r0 --dry-run
#   scripts/cmold_repro_chain.sh --arm r0 --stages gate,preflight
#   scripts/cmold_repro_chain.sh --arm r0 --smoke       # 1 epoch, 64 frames
#   scripts/cmold_repro_chain.sh --arm r0 --full        # real run, lead OK first
#   scripts/cmold_repro_chain.sh --arm r0 --stages eval,summary
#
# Guards: the train stage runs the config's own schedule only when --full is
# given; every tools/test.py call pins the val split (the test split stays
# sealed, CLAUDE.md hard rule).

set -uo pipefail

# ------------------------------------------------------------------ defaults
REPO_DEFAULT="/mnt/d/agent_workspace/水下/声呐目标检测/code/VSFusionDistill"
PY_FALLBACK="$HOME/mycode/VSFusionDistill/.venv-gpu/bin/python"
DATA_ROOT_DEFAULT="/mnt/d/pby/uxo-full/repro"

ARM=""
CFG=""
STAGES=""
SMOKE=0
FULL=0
DRY=0
TRIES=2
SMOKE_SAMPLES=64
LIVENESS_S=600

usage() {
    sed -n '2,60p' "$0" | sed -n '/^# Usage:/,/^$/p' | sed 's/^# \{0,1\}//'
    cat <<'EOF'
Options:
  --arm r0|r1|r2|r3a|r3b   ladder arm (config path looked up, see config_for_arm)
  --config PATH            override the arm's config (relative to $REPO)
  --stages a,b,c           subset of gate,preflight,train,smoke_report,eval,summary
  --smoke                  short run: 1 epoch over the first SMOKE_SAMPLES frames
  --full                   allow the train stage to run the config's own schedule
  --dry-run                print resolved paths and exact commands, touch nothing
  --samples N              smoke subset size (default 64)
  --retries N              attempts per stage (default 2; the chain stops after)
  --repo PATH              repo root (default $REPO_DEFAULT or $CMOLD_REPO)
  -h, --help               this text
EOF
}

die() { echo "cmold_repro_chain: $*" >&2; exit 2; }

# ------------------------------------------------------------- arg parsing
while [ $# -gt 0 ]; do
    case "$1" in
        --arm)        ARM="${2:-}"; shift 2 ;;
        --arm=*)      ARM="${1#*=}"; shift ;;
        --config)     CFG="${2:-}"; shift 2 ;;
        --config=*)   CFG="${1#*=}"; shift ;;
        --stages)     STAGES="${2:-}"; shift 2 ;;
        --stages=*)   STAGES="${1#*=}"; shift ;;
        --samples)    SMOKE_SAMPLES="${2:-}"; shift 2 ;;
        --samples=*)  SMOKE_SAMPLES="${1#*=}"; shift ;;
        --retries)    TRIES="${2:-}"; shift 2 ;;
        --retries=*)  TRIES="${1#*=}"; shift ;;
        --repo)       REPO_DEFAULT="${2:-}"; shift 2 ;;
        --repo=*)     REPO_DEFAULT="${1#*=}"; shift ;;
        --smoke)      SMOKE=1; shift ;;
        --full)       FULL=1; shift ;;
        --dry-run)    DRY=1; shift ;;
        -h|--help)    usage; exit 0 ;;
        *)            die "unknown argument: $1 (try --help)" ;;
    esac
done

[ -n "$ARM" ] || die "missing --arm (r0|r1|r2|r3a|r3b); try --help"

REPO="${CMOLD_REPO:-$REPO_DEFAULT}"
[ -d "$REPO" ] || die "repo not found: $REPO"
REPO="$(cd "$REPO" && pwd)"
DATA_ROOT="${CMOLD_DATA_ROOT:-$DATA_ROOT_DEFAULT}"

config_for_arm() {
    case "$1" in
        r0)  echo "configs/repro_cmold/r0_baseline_yoloxs.py" ;;
        r1)  echo "configs/repro_cmold/r1_kd_yoloxs.py" ;;
        r2)  echo "configs/repro_cmold/r2_cmold_yoloxs.py" ;;
        r3a) echo "configs/repro_cmold/r3a_obj_only.py" ;;
        r3b) echo "configs/repro_cmold/r3b_cls_only.py" ;;
        *)   return 1 ;;
    esac
}
[ -n "$CFG" ] || CFG="$(config_for_arm "$ARM")" \
    || die "unknown arm '$ARM' (r0|r1|r2|r3a|r3b)"

case "$CFG" in
    /*) CFG_ABS="$CFG" ;;
    *)  CFG_ABS="$REPO/$CFG" ;;
esac

# ------------------------------------------------------------------ layout
WORK_ROOT="$REPO/work_dirs/repro_cmold"
RES_ROOT="$REPO/results/repro_cmold"
STATE="${CMOLD_STATE:-$HOME/mycode/cmold_repro_state}"

if [ "$SMOKE" -eq 1 ]; then
    TAG="smoke_$ARM"
    WD="$WORK_ROOT/$TAG"
    RES="$RES_ROOT/$TAG"
    LOG="${CMOLD_LOG:-$HOME/mycode/cmold_repro_${ARM}_smoke.log}"
    [ -n "$STAGES" ] || STAGES="gate,preflight,smoke_train,smoke_report"
    MARK_PREFIX="smoke_$ARM"
else
    TAG="$ARM"
    WD="$WORK_ROOT/$ARM"
    RES="$RES_ROOT/$ARM"
    LOG="${CMOLD_LOG:-$HOME/mycode/cmold_repro_${ARM}.log}"
    [ -n "$STAGES" ] || STAGES="gate,preflight,train,eval,summary"
    MARK_PREFIX="$ARM"
fi

# ------------------------------------------------------------- interpreter
pick_py() {
    local cand
    for cand in "${CMOLD_PY:-}" "$REPO/.venv-gpu/bin/python" "$PY_FALLBACK"; do
        [ -n "$cand" ] || continue
        if [ -x "$cand" ]; then echo "$cand"; return 0; fi
    done
    return 1
}
PY="$(pick_py)" || die "no GPU python found (set CMOLD_PY)"

# ------------------------------------------------------------------ helpers
say() { echo "[$(date '+%F %T')] $*"; }

gpu_mem_mib() {
    command -v nvidia-smi >/dev/null 2>&1 || { echo 0; return; }
    nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits \
        2>/dev/null | head -1 | tr -d ' '
}

newest_ckpt() {  # newest_ckpt <work_dir> -> path or empty
    ls -1t "$1"/epoch_*.pth 2>/dev/null | head -1
}

config_max_epochs() {
    "$PY" - "$CFG_ABS" <<'PY'
import sys
from mmengine.config import Config
c = Config.fromfile(sys.argv[1])
print(int(c.train_cfg.get("max_epochs", c.get("max_epochs", 0))))
PY
}

# describe_stage <stage-name> -- the exact command a dry run would issue
describe_stage() {
    case "$1" in
        gate)
            echo "    \$PY - $CFG_ABS            # Config.fromfile + data_root probe" ;;
        preflight)
            echo "    \$PY - <probe> $CFG_ABS $ARM $RES $DATA_ROOT"
            echo "      -> $RES/preflight.json, $RES/preflight_sample_sonar.png" ;;
        train)
            echo "    $PY tools/train.py $CFG --seed 0 --work-dir $WD"
            echo "      (refused without --full: runs the config's own schedule)" ;;
        smoke_train)
            echo "    $PY tools/train.py $CFG --seed 0 --work-dir $WD --cfg-options \\"
            echo "        train_cfg.max_epochs=1 train_dataloader.dataset.indices=$SMOKE_SAMPLES" ;;
        smoke_report)
            echo "    \$PY - <report> $RES $WD $SMOKE_SAMPLES $LOG"
            echo "      -> $RES/smoke.json" ;;
        eval)
            echo "    $PY tools/test.py $CFG <newest epoch_*.pth under $WD> \\"
            echo "        --cfg-options test_dataloader.dataset.split=val \\"
            echo "        --levels d0 --out-dir $RES/eval_val"
            echo "      (marker kept only if $RES/eval_val/ap_summary.json appears)" ;;
        summary)
            echo "    \$PY - <summary> $RES/eval_val/ap_summary.json $ARM" ;;
    esac
}

# run_stage <stage-name> <function> [args...]
# .ok breakpoint, TRIES attempts, stop the chain on exhaustion.
run_stage() {
    local name="$1"; shift
    local marker="$STATE/$MARK_PREFIX.$name.ok"
    if [ -f "$marker" ]; then
        say "stage $name: skip (marker $marker)"
        return 0
    fi
    if [ "$DRY" -eq 1 ]; then
        say "stage $name: DRY-RUN, would run:"
        describe_stage "$name"
        return 0
    fi
    local i rc=0
    for i in $(seq 1 "$TRIES"); do
        say "stage $name: attempt $i/$TRIES"
        "$@"
        rc=$?
        if [ "$rc" -eq 0 ]; then
            mkdir -p "$STATE"
            touch "$marker"
            say "stage $name: OK (attempt $i)"
            return 0
        fi
        say "stage $name: FAILED (rc=$rc) on attempt $i/$TRIES"
        sleep 30
    done
    say "stage $name: exhausted $TRIES attempts -- chain stops"
    exit 1
}

# --------------------------------------------------------------- training
CHILD_PID=""
cleanup() {
    if [ -n "$CHILD_PID" ] && kill -0 "$CHILD_PID" 2>/dev/null; then
        say "trap: forwarding SIGTERM to training pid $CHILD_PID"
        kill "$CHILD_PID" 2>/dev/null
    fi
}
trap cleanup EXIT INT TERM

# run_training <train.py extra args...>
# Background launch, 10-minute liveness window, heartbeat, VRAM sampling.
run_training() {
    mkdir -p "$WD" "$RES" "$(dirname "$LOG")"
    local mem_file="$RES/vram_samples.txt"
    : > "$mem_file"          # per attempt: peaks must not mix attempts
    local base_mem; base_mem="$(gpu_mem_mib)"
    say "train: launching; work_dir=$WD"
    say "train: cmd $PY tools/train.py $CFG --seed 0 --work-dir $WD $*"
    say "train: gpu memory before launch: ${base_mem} MiB"
    "$PY" tools/train.py "$CFG" --seed 0 --work-dir "$WD" "$@" &
    CHILD_PID=$!
    say "train: pid $CHILD_PID"

    # VRAM sampler runs alongside; device-wide MiB, 2 s cadence (a short smoke
    # iterates for only a few seconds, so 5 s would miss the peak)
    ( while kill -0 "$CHILD_PID" 2>/dev/null; do gpu_mem_mib >> "$mem_file"; sleep 2; done ) &
    local sampler=$!

    # Liveness: the 10-minute rule exists to catch a silent early death. A
    # short stage (smoke: 64 frames, 1 epoch) finishes inside the window with
    # exit code 0 -- that is success, not a liveness failure (2026-11-08: the
    # first smoke run trained fine in 3 s and was called dead by this loop).
    local waited=0
    while [ "$waited" -lt "$LIVENESS_S" ]; do
        if ! kill -0 "$CHILD_PID" 2>/dev/null; then
            local early_rc=0
            wait "$CHILD_PID" || early_rc=$?
            CHILD_PID=""
            kill "$sampler" 2>/dev/null; wait "$sampler" 2>/dev/null
            if [ "$early_rc" -eq 0 ] && [ -n "$(newest_ckpt "$WD")" ]; then
                say "train: finished inside the liveness window after ${waited}s (rc=0, checkpoint written) -- short run, accepted"
                say "train: exit rc=0; last_ckpt=$(newest_ckpt "$WD")"
                return 0
            fi
            say "train: process gone after ${waited}s (rc=$early_rc) -- liveness FAILED"
            return 1
        fi
        sleep 5
        waited=$((waited + 5))
    done

    say "train: alive after ${waited}s -- 10-minute liveness OK"

    local hb=0
    while kill -0 "$CHILD_PID" 2>/dev/null; do
        sleep 60
        hb=$((hb + 60))
        kill -0 "$CHILD_PID" 2>/dev/null || break
        if [ $((hb % 600)) -eq 0 ]; then
            say "train: heartbeat mem=$(gpu_mem_mib) MiB last_ckpt=$(newest_ckpt "$WD")"
        fi
    done

    local rc=0
    wait "$CHILD_PID" || rc=$?
    CHILD_PID=""
    kill "$sampler" 2>/dev/null; wait "$sampler" 2>/dev/null
    say "train: exit rc=$rc; last_ckpt=$(newest_ckpt "$WD")"
    [ "$rc" -eq 0 ] || return "$rc"
    [ -n "$(newest_ckpt "$WD")" ] || { say "train: no epoch_*.pth written"; return 1; }
    return 0
}

# ----------------------------------------------------------------- stages
stage_gate() {
    say "gate: config=$CFG_ABS"
    [ -f "$CFG_ABS" ] || { say "gate: FAILED config missing: $CFG_ABS"; return 1; }
    local branch; branch="$(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null)"
    say "gate: git branch=$branch"
    [ "$branch" = "exp/cmold-paper-repro" ] || \
        say "gate: WARN branch is '$branch', plan expects exp/cmold-paper-repro"
    [ -d "$DATA_ROOT" ] || say "gate: WARN data root missing: $DATA_ROOT"
    say "gate: python=$PY"
    "$PY" - "$CFG_ABS" "$DATA_ROOT" <<'PY'
import os
import sys
from mmengine.config import Config

import aodet   # the import win the lead asked to see, in the log itself
print(f"gate: aodet -> {aodet.__file__}")

cfg_path, data_root = sys.argv[1], sys.argv[2]
try:
    cfg = Config.fromfile(cfg_path)
except Exception as exc:                      # noqa: BLE001 - report, don't hide
    print(f"gate: LOAD FAILED {type(exc).__name__}: {exc}")
    sys.exit(3)
print(f"gate: parsed {cfg_path}")
tc = cfg.get("train_cfg", {})
bs = cfg.get("train_dataloader", {}).get("batch_size")
print(f"gate: max_epochs={tc.get('max_epochs')} bs={bs}")
root = cfg.get("train_dataloader", {}).get("dataset", {}).get("data_root", "?")
print(f"gate: config data_root={root}")
print(f"gate: resolved data_root={os.path.abspath(root)}")
root_abs = os.path.abspath(root)
for name in ("camera.json", "sonar.json", "frame_meta.csv", "images"):
    p = os.path.join(root_abs, name)
    mark = "OK  " if os.path.exists(p) else "MISS"
    print(f"gate: {mark} {p}")
print(f"gate: data_root exists: {os.path.isdir(root_abs)} ({root_abs})")
PY
    local rc=$?
    # the python block only reports; a missing data root is the preflight's job
    if [ "$rc" -eq 3 ]; then
        say "gate: FAILED Config.fromfile could not load the config"
        return 1
    fi
    [ "$rc" -eq 0 ] || { say "gate: FAILED probe error (rc=$rc)"; return 1; }
    return 0
}

stage_preflight() {
    mkdir -p "$RES"
    say "preflight: data loading / letterbox / Mosaic probe -> $RES/preflight.json"
    "$PY" - "$CFG_ABS" "$ARM" "$RES" "$DATA_ROOT" <<'PY'
"""Preflight for the CMOLD repro: can the data be read, what shape does the
letterbox produce, is Mosaic actually in the pipeline and actually firing.

Read-only: nothing here changes data semantics (plan §5 red line).  Every
finding is reported as a fact plus the place it came from; anything this
probe cannot establish is written as "unknown", never guessed.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.getcwd())

import cv2           # noqa: E402
import numpy as np   # noqa: E402
from mmengine.config import Config                       # noqa: E402
from mmengine.dataset import pseudo_collate              # noqa: E402
from mmengine.registry import DATASETS, MODELS, init_default_scope  # noqa: E402

import aodet.datasets  # noqa: F401,E402  (registers the transforms/dataset)
import aodet.models    # noqa: F401,E402

cfg_path, arm, out_dir, data_root_hint = sys.argv[1:5]
report: dict = {"arm": arm, "config": cfg_path, "unknown": []}
os.makedirs(out_dir, exist_ok=True)

cfg = Config.fromfile(cfg_path)
init_default_scope(cfg.get("default_scope", "mmdet"))

train_cfg = dict(cfg.train_dataloader.dataset)
root = train_cfg.get("data_root", data_root_hint)
root_abs = os.path.abspath(root)
report["data_root"] = root_abs
report["files"] = {n: os.path.exists(os.path.join(root_abs, n))
                   for n in ("camera.json", "sonar.json", "frame_meta.csv",
                             "pairs.csv")}
report["files"]["images/"] = os.path.isdir(os.path.join(root_abs, "images"))
report["files"]["hint_root_exists"] = os.path.isdir(data_root_hint)

pipe_cfg = train_cfg.get("pipeline") or []
names = [p.get("type") if isinstance(p, dict) else type(p).__name__
         for p in pipe_cfg]
report["pipeline"] = names
report["mosaic_entries"] = [n for n in names if "mosaic" in str(n).lower()]
report["mixup_entries"] = [n for n in names if "mixup" in str(n).lower()]
# letterbox marker: AOPairedResize with keep_ratio=True (plan §3)
report["resize"] = [p for p in pipe_cfg
                    if isinstance(p, dict) and p.get("type") == "AOPairedResize"]

ds = DATASETS.build(train_cfg)
if hasattr(ds, "full_init"):
    ds.full_init()
report["len_train"] = len(ds)
report["batch_size"] = cfg.train_dataloader.get("batch_size")
report["dataset_type"] = train_cfg.get("type")
report["aodet_file"] = aodet.__file__
print(f"preflight: dataset type = {report['dataset_type']}")
print(f"preflight: aodet -> {report['aodet_file']}")
print(f"preflight: train dataset length = {len(ds)} "
      f"(batch_size={report['batch_size']})")

# frame-level split contract (plan §6): the manifest the dataset was built from
split_file = train_cfg.get("split_file")
if split_file:
    sf_path = (split_file if os.path.isabs(split_file)
               else os.path.abspath(split_file))
    report["split_file"] = sf_path
    here = os.path.exists(sf_path)
    print(f"preflight: split_file = {sf_path} "
          f"({'exists' if here else 'MISSING'})")
    if here:
        fs = json.load(open(sf_path))
        report["split_seed"] = fs.get("seed")
        report["split_counts"] = fs.get("counts")
        report["split_len_train"] = len(fs.get("train") or [])
        report["split_len_val"] = len(fs.get("val") or [])
        print(f"preflight: split seed={fs.get('seed')} "
              f"counts={fs.get('counts')} "
              f"len(train)={report['split_len_train']} "
              f"len(val)={report['split_len_val']}")
    else:
        report["unknown"].append("split_file configured but absent: the "
                                 "dataset falls back to the split column")
else:
    report["split_file"] = None
print(f"preflight: pipeline = {names}")

# test/val side length; force the val split so the sealed test set is never
# listed here either (CLAUDE.md: test recordings stay sealed, eval reads val)
val_cfg = dict(cfg.test_dataloader.dataset)
val_cfg["split"] = "val"
try:
    vds = DATASETS.build(val_cfg)
    if hasattr(vds, "full_init"):
        vds.full_init()
    report["len_val"] = len(vds)
    print(f"preflight: val dataset length = {len(vds)}")
except Exception as exc:                      # noqa: BLE001 - report, do not hide
    report["len_val"] = None
    report["val_error"] = f"{type(exc).__name__}: {exc}"
    print(f"preflight: val dataset NOT built -> {report['val_error']}")

# plan §2 frame-level 8:2 split of the 4,152 paired frames
EXPECTED_LEN = {"train": 3322, "val": 830}
for side, expect in EXPECTED_LEN.items():
    got = report.get(f"len_{side}")
    if got is None:
        continue
    if got != expect:
        note = f"len_{side}={got} vs plan §2 expectation {expect}"
        report["unknown"].append(note + " (reported, not fatal)")
        print(f"preflight: WARN {note}")
    else:
        print(f"preflight: len_{side}={got} matches plan §2")

# ---- one sample, ten draws: shape, mosaic markers, randomness
def gt_boxes(sample, side):
    """Boxes after AOPackPairedInputs live in data_samples_<side>, not in the
    results dict (pack_paired.py:151-158); the old results["boxes_sonar"] key
    is gone by then, so reading it always said 0 boxes."""
    side_ds = sample.get(f"data_samples_{side}")
    gt = getattr(side_ds, "gt_instances", None) if side_ds is not None else None
    boxes = getattr(gt, "bboxes", None) if gt is not None else None
    return [] if boxes is None else boxes


draws = []
first = None
for i in range(10):
    s = ds[0]
    if first is None:
        first = s
    son = s.get("img_sonar")
    cam = s.get("img_camera")
    keys = [k for k in s if "mosaic" in k.lower() or "mixup" in k.lower()]
    draws.append(dict(
        draw=i,
        sonar_shape=None if son is None else list(son.shape),
        camera_shape=None if cam is None else list(cam.shape),
        n_boxes_sonar=int(gt_boxes(s, "sonar").shape[0]),
        n_boxes_camera=int(gt_boxes(s, "camera").shape[0]),
        extra_keys=keys,
        marker_values={k: str(s[k])[:80] for k in keys},
    ))
report["draws"] = draws

# ---- annotation census: labels must reach the model, not just the loader
census_idx = [0, 200, 800, 1600, 2400, 3200, 3321]
census = []
for idx in census_idx:
    if idx >= len(ds):
        continue
    s = ds[idx]
    b = gt_boxes(s, "sonar")
    labels = getattr(s["data_samples_sonar"].gt_instances, "labels", None)
    census.append(dict(index=idx,
                       n_boxes=int(b.shape[0]),
                       labels=sorted({int(v) for v in labels}) if labels is not None
                       and labels.numel() else []))
report["annotation_census"] = census
with_boxes = [c for c in census if c["n_boxes"]]
report["census_frames_with_boxes"] = f"{len(with_boxes)}/{len(census)}"
report["census_boxes_total"] = sum(c["n_boxes"] for c in census)
print(f"preflight: annotation census {report['census_frames_with_boxes']} "
      f"frames with sonar boxes, {report['census_boxes_total']} boxes total")
if census and not with_boxes:
    report["unknown"].append("no sonar boxes in any probed frame: check "
                             "sonar_gt_sources / frame_split.json ids")


seen_shapes = sorted({tuple(d["sonar_shape"]) for d in draws
                      if d["sonar_shape"]})
report["sonar_shapes_seen"] = [list(t) for t in seen_shapes]
report["marker_keys_seen"] = sorted({k for d in draws for k in d["extra_keys"]})
print(f"preflight: sonar shapes over 10 draws = {report['sonar_shapes_seen']}")
print(f"preflight: mosaic/mixup marker keys = {report['marker_keys_seen'] or 'none'}")
if not report["mosaic_entries"]:
    print("preflight: Mosaic 未配置（按计划 §3 偏离登记，lead 2026-11-08 决定"
          "本轮不实现、R0 不带 Mosaic/MixUp 跑）")
    report["mosaic_deviation"] = ("no Mosaic/MixUp entry in the pipeline; "
                                  "recorded deviation, lead decision 2026-11-08")
elif not report["marker_keys_seen"]:
    report["unknown"].append(
        "Mosaic transform is configured but emits no self-describing key; "
        "whether it fired per sample cannot be read from the sample dict")

# ---- letterbox -> preprocessor pad_shape (plan §3 input geometry)
prep = MODELS.build(dict(cfg.model.data_preprocessor))
batch = pseudo_collate([ds[0], ds[1]])
prepped = prep(batch, training=False)
sonar_t = prepped["inputs"].get("sonar")
report["sonar_batch_shape"] = None if sonar_t is None else list(sonar_t.shape)
ds_son = (prepped.get("data_samples") or {}).get("sonar") or []
if ds_son:
    report["pad_shape"] = list(ds_son[0].metainfo.get("pad_shape", []))
    report["img_shape"] = list(ds_son[0].metainfo.get("img_shape", []))
    report["batch_input_shape"] = list(
        ds_son[0].metainfo.get("batch_input_shape", []))
print(f"preflight: sonar batch tensor = {report['sonar_batch_shape']}")
print(f"preflight: pad_shape = {report.get('pad_shape')}  "
      f"img_shape = {report.get('img_shape')}")

# letterbox evidence: keep_ratio means img_shape (content) != pad_shape (canvas)
pad_h, pad_w = report.get("pad_shape") or [0, 0]
img_h, img_w = report.get("img_shape") or [0, 0]
if img_h and img_w and (img_h, img_w) != (pad_h, pad_w):
    report["letterbox"] = dict(keep_ratio_effective=True,
                               content=[img_h, img_w], canvas=[pad_h, pad_w],
                               content_aspect=round(img_w / img_h, 4))
    print(f"preflight: letterbox keep_ratio effective, content "
          f"{img_h}x{img_w} -> canvas {pad_h}x{pad_w}")
else:
    report["letterbox"] = dict(keep_ratio_effective=None, note="img==pad")
    report["unknown"].append("img_shape equals pad_shape: letterbox stretch "
                             "is indistinguishable from padding here")
    print("preflight: WARN img_shape == pad_shape, padding not observable")

# ---- one visualization (sonar side, boxes drawn)
# img_sonar is CHW (C, H, W); cv2 needs HWC. Passing CHW straight to imwrite
# makes OpenCV read W as the channel count: "libpng error: Invalid IHDR data"
# and imwrite returns False (diagnosed 2026-11-08, not a data problem).
try:
    # pick a frame that actually carries sonar boxes, otherwise the picture
    # shows nothing (sample 0 happens to be empty) -- cosmetic only
    best = max(census, key=lambda c: c["n_boxes"]) if census else None
    vis_idx = best["index"] if best and best["n_boxes"] else 0
    vis_sample = ds[vis_idx] if vis_idx else first
    report["vis_index"] = vis_idx
    arr = np.asarray(vis_sample["img_sonar"])
    if arr.ndim == 3 and arr.shape[0] in (1, 3):
        arr = np.transpose(arr, (1, 2, 0))
    if arr.ndim == 3 and arr.shape[2] == 1:
        arr = arr[:, :, 0]
    if arr.ndim == 3 and arr.shape[2] == 3:
        arr = arr[:, :, ::-1]                  # RGB -> BGR for cv2
    arr = np.ascontiguousarray(arr)
    if arr.dtype != np.uint8:
        arr = arr.astype(np.uint8)
    report["vis_shape_hwc"] = list(arr.shape)
    n_drawn = 0
    for b in gt_boxes(vis_sample, "sonar"):
        x1, y1, x2, y2 = [int(round(float(v))) for v in b.tolist()[:4]]
        cv2.rectangle(arr, (x1, y1), (x2, y2), (0, 255, 0), 2)
        n_drawn += 1
    report["vis_boxes_drawn"] = n_drawn
    vis = os.path.join(out_dir, "preflight_sample_sonar.png")
    wrote = cv2.imwrite(vis, arr)
    if not wrote or not os.path.exists(vis):
        raise RuntimeError(f"cv2.imwrite returned {wrote}")
    report["visualization"] = vis
    print(f"preflight: visualization -> {vis} (HWC {arr.shape[0]}x{arr.shape[1]})")
except Exception as exc:                      # noqa: BLE001
    report["visualization_error"] = f"{type(exc).__name__}: {exc}"
    print(f"preflight: visualization failed -> {report['visualization_error']}")

with open(os.path.join(out_dir, "preflight.json"), "w") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
print(f"preflight: wrote {os.path.join(out_dir, 'preflight.json')}")

# hard failures: the data side is unusable
missing = [k for k, v in report["files"].items()
           if not v and k in ("camera.json", "sonar.json", "frame_meta.csv")]
if missing:
    print(f"preflight: FAILED missing annotation files {missing} under {root_abs}")
    sys.exit(1)
if report["len_train"] == 0:
    print("preflight: FAILED train split is empty (split values in the ann file?)")
    sys.exit(1)
PY
}

stage_train() {
    if [ "$FULL" -ne 1 ]; then
        say "train: refused -- the config's own schedule needs --full"
        say "train: (plan §4 R0 = 200 epochs ~3-4 h; lead confirmation required)"
        exit 2   # a guard, not a transient failure: never burn retries on it
    fi
    local n; n="$(config_max_epochs)"
    say "train: full run, config max_epochs=$n"
    run_training
}

stage_smoke_train() {
    say "smoke: 1 epoch over the first $SMOKE_SAMPLES train frames"
    run_training --cfg-options \
        "train_cfg.max_epochs=1" \
        "train_dataloader.dataset.indices=$SMOKE_SAMPLES"
}

stage_smoke_report() {
    say "smoke: collecting numbers -> $RES/smoke.json"
    "$PY" - "$RES" "$WD" "$SMOKE_SAMPLES" "$LOG" <<'PY'
"""Turn one smoke run into the numbers plan §8 asks for: finite losses,
peak VRAM, seconds per iteration, and the full-run extrapolation."""
from __future__ import annotations

import json
import os
import re
import sys

res_dir, wd, samples, log_path = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
out = {"work_dir": wd, "log": log_path, "smoke_samples": samples}

# ---- VRAM samples (device-wide MiB, 5 s cadence, written by the chain)
vram_file = os.path.join(res_dir, "vram_samples.txt")
vals = []
if os.path.exists(vram_file):
    for line in open(vram_file):
        line = line.strip()
        if line.isdigit():
            vals.append(int(line))
out["vram_peak_mib"] = max(vals) if vals else None
out["vram_first_mib"] = vals[0] if vals else None
out["vram_samples"] = len(vals)
out["vram_note"] = ("device-wide nvidia-smi memory.used; not "
                    "torch.cuda.max_memory_allocated")

# ---- parse the training log
# The log also holds this stage's own JSON dump on re-runs (it ends up in the
# log because the chain tees stdout), so everything from the first
# "collecting numbers" line onwards is this report, not training output --
# scanning it made every re-run "discover" the previous run's fatal_terms.
text = open(log_path, errors="replace").read() if os.path.exists(log_path) else ""
marker = "smoke: collecting numbers"
train_text = text.split(marker)[0] if marker in text else text
iter_re = re.compile(r"Epoch\(train\)\s*\[(\d+)\]\[(\s*\d+)/(\d+)\]")
loss_re = re.compile(r"([A-Za-z0-9_]+):\s*([-+0-9.eE]+)")
iter_times = []
loss_rows = []
for line in train_text.splitlines():
    m = iter_re.search(line)
    if not m:
        continue
    cur, total = int(m.group(2)), int(m.group(3))
    row = {"epoch": int(m.group(1)), "iter": cur, "iters_per_epoch": total}
    for key, val in loss_re.findall(line):
        try:
            num = float(val)
        except ValueError:
            continue
        if key.startswith("loss") or key in (
                "time", "data_time", "lr", "memory", "grad_norm"):
            row[key] = num
    loss_rows.append(row)
    if "time" in row:
        iter_times.append(row["time"])

out["iters_logged"] = len(loss_rows)
out["iters_per_epoch_smoke"] = (loss_rows[-1]["iters_per_epoch"]
                                if loss_rows else None)
out["loss_keys"] = sorted({k for r in loss_rows for k in r
                           if k.startswith("loss")})
loss_vals = {k: [r[k] for r in loss_rows if k in r] for k in out["loss_keys"]}
out["loss_last"] = {k: v[-1] for k, v in loss_vals.items() if v}
out["loss_min"] = {k: min(v) for k, v in loss_vals.items() if v}
out["loss_max"] = {k: max(v) for k, v in loss_vals.items() if v}
finite = all(all(x == x and abs(x) != float("inf") for x in v)
             for v in loss_vals.values())
out["loss_all_finite"] = bool(finite)

# ---- torch-side peak: mmengine logs `memory:` per interval = MB allocated
# (torch.cuda.max_memory_allocated).  A 3 s smoke epoch can slip between the
# nvidia-smi samples above, so this is the number to quote for "显存峰值".
mem_vals = [r["memory"] for r in loss_rows if "memory" in r]
out["torch_max_mem_mb"] = max(mem_vals) if mem_vals else None
grads = [r["grad_norm"] for r in loss_rows if "grad_norm" in r]
out["grad_norm_max"] = max(grads) if grads else None

# ---- timing and throughput (lead asked for per-step time, imgs/s, VRAM peak)
pre = os.path.join(res_dir, "preflight.json")
pf = json.load(open(pre)) if os.path.exists(pre) else {}
if not pf:
    out["extrapolation_note"] = "no preflight.json -> no full-size estimate"
bs = int(pf.get("batch_size") or 8)
out["batch_size"] = bs
n_train = pf.get("len_train")
out["preflight_len_train"] = n_train

if iter_times:
    per_iter = sum(iter_times) / len(iter_times)
    out["sec_per_iter_mean"] = round(per_iter, 4)      # 每步耗时 (smoothed)
    out["sec_per_iter_last"] = round(iter_times[-1], 4)
    out["train_imgs_per_s"] = round(bs / per_iter, 2) if per_iter else None
    dts = [r["data_time"] for r in loss_rows if "data_time" in r]
    if dts:
        data_mean = sum(dts) / len(dts)
        out["data_time_mean"] = round(data_mean, 4)
        out["dataloader_imgs_per_s"] = (round(bs / data_mean, 1)
                                        if data_mean else None)
    smoke_iters = out.get("iters_per_epoch_smoke")
    if smoke_iters:
        out["sec_per_epoch_smoke_est"] = round(per_iter * smoke_iters, 1)
    if n_train:
        iters_full = -(-int(n_train) // bs)
        out["iters_per_epoch_full"] = iters_full
        out["sec_per_epoch_full_est"] = round(per_iter * iters_full, 1)
        epochs = 200   # plan §4 R0
        out["full_run_epochs_assumed"] = epochs
        out["full_run_hours_est"] = round(
            per_iter * iters_full * epochs / 3600, 2)
else:
    out["timing_note"] = "no 'time:' field parsed from the log"

# word-bounded on purpose: a plain `t in text` matches "INF" inside mmengine's
# own "INFO" tag and reports a divergence that never happened (2026-11-08)
out["fatal_terms"] = sorted({m.lower() for m in
                             re.findall(r"\b(?:nan|inf)\b", train_text, re.I)})
report_path = os.path.join(res_dir, "smoke.json")
with open(report_path, "w") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
print(json.dumps(out, indent=2, ensure_ascii=False))
print(f"smoke: wrote {report_path}")
PY
}

stage_eval() {
    local ckpt; ckpt="$(newest_ckpt "$WD")"
    [ -n "$ckpt" ] || { say "eval: FAILED no checkpoint under $WD"; return 1; }
    local out_dir="$RES/eval_val"
    # The split is pinned through --cfg-options, not --split: tools/test.py's
    # --split path builds the dataset with split=None ("load every split, then
    # filter the infos"), and a split_file dataset refuses None on purpose
    # (aodet/datasets/repro_frame_split.py:108 -- "that would admit the test
    # recordings").  Pinning dataset.split evaluates exactly the val id list
    # in the split file, so the sealed test recordings stay unopened, and this
    # branch leaves the shared tools/test.py untouched (mainline separation).
    say "eval: $ckpt -> $out_dir (split pinned to val in the config, test stays sealed)"
    "$PY" tools/test.py "$CFG" "$ckpt" --levels d0 \
        --cfg-options test_dataloader.dataset.split=val \
        --out-dir "$out_dir"
    [ -f "$out_dir/ap_summary.json" ] || { say "eval: FAILED no ap_summary.json"; return 1; }
}

stage_summary() {
    local f="$RES/eval_val/ap_summary.json"
    [ -f "$f" ] || { say "summary: FAILED $f missing"; return 1; }
    "$PY" - "$f" "$ARM" <<'PY'
import json
import sys
rows = json.load(open(sys.argv[1]))
arm = sys.argv[2]
print(f"summary[{arm}]: branch level gt AP AP50 AR100")
for r in rows:
    print(f"  {r['branch']:6s} {r['level']:4s} {r['gt']:4s} "
          f"{r['AP']:.4f} {r['AP50']:.4f} {r['AR@100']:.4f}")
son = [r for r in rows if r["branch"] == "sonar" and r["level"] == "d0"]
if son:
    r = son[0]
    print(f"summary[{arm}]: head-line sonar@d0 gt={r['gt']} "
          f"AP={r['AP']:.4f} AP50={r['AP50']:.4f}")
PY
}

# --------------------------------------------------------------- dispatch
say "cmold_repro_chain: arm=$ARM config=$CFG_ABS"
say "cmold_repro_chain: repo=$REPO python=$PY work_dir=$WD results=$RES"
say "cmold_repro_chain: stages=$STAGES smoke=$SMOKE full=$FULL dry_run=$DRY"

if [ "$DRY" -eq 0 ]; then
    mkdir -p "$(dirname "$LOG")" "$STATE" "$WD" "$RES"
    exec >> "$LOG" 2>&1
    say "===== chain start (pid $$) ====="
elif [ "$SMOKE" -eq 1 ]; then
    echo "--- dry run: no file is written, no marker is created ---"
    say "dry-run: parsing the smoke --cfg-options through mmengine DictAction"
    "$PY" - "train_cfg.max_epochs=1" \
        "train_dataloader.dataset.indices=$SMOKE_SAMPLES" <<'PY' \
        || die "smoke --cfg-options do not parse (argparse would reject them)"
import argparse
import sys

from mmengine.config import DictAction

# mirrors tools/train.py's own declaration (nargs='+', action=DictAction)
parser = argparse.ArgumentParser()
parser.add_argument("--cfg-options", nargs="+", action=DictAction)
ns = parser.parse_args(["--cfg-options"] + sys.argv[1:])
print("    parsed ->", ns.cfg_options)
PY
else
    echo "--- dry run: no file is written, no marker is created ---"
fi

cd "$REPO" || die "cannot cd $REPO"

IFS=',' read -r -a STAGE_LIST <<< "$STAGES"
for st in "${STAGE_LIST[@]}"; do
    case "$st" in
        gate)         run_stage gate stage_gate ;;
        preflight)    run_stage preflight stage_preflight ;;
        train)        run_stage train stage_train ;;
        smoke_train)  run_stage smoke_train stage_smoke_train ;;
        smoke_report) run_stage smoke_report stage_smoke_report ;;
        eval)         run_stage eval stage_eval ;;
        summary)      run_stage summary stage_summary ;;
        *)            die "unknown stage '$st' (gate,preflight,train,smoke_train,smoke_report,eval,summary)" ;;
    esac
done

say "===== chain: DONE $(date '+%F %T') ====="
