"""E11-1: B0 sonar-only baseline on the full UXO set (47 recordings).

This is the platform probe, not a method result.  The frozen split
(split_manifest.json, seed 0, sha256 2eb707c4ecb038b6...) reached the
frames through uxo_to_paired --splits-json, so every row of
frame_meta.csv carries its train/val/test role and the val_id flag;
nothing here re-derives a split.

Everything else is inherited from s0_b0_sonar_only_yoloxs.py; the
shared recipe in schedule_f2.py is untouched.  100 epochs at batch 8
over roughly 4.1k train frames is ~51k iterations, the same order as
YOLOX-S's COCO reference, so the schedule needs no rescale.

Note on sonar GT: the base dataset config trains on sonar_gt_sources
= ("blob",).  Projected boxes never reach the sonar head -- they only
define the cross-modal correspondence pi -- so the projected/row
residual that gated the split is a calibration diagnostic, not a
training-label quality knob.

Three seeds via tools/run_seeds.sh configs/f2/e11_b0_sonar_only_yoloxs.py
0 1 2.  The number that matters is the spread across seeds: it sets the
resolution of every later B0-vs-method comparison.

The evaluation split is val, not test: the frozen E11 preregistration
says "test 在本实验中不开封，E11 全部判定读 val", so the scan dataloader
points at the val split.  test stays sealed until the platform tier is
decided.
"""

_base_ = "s0_b0_sonar_only_yoloxs.py"

data_root = "data/paired/uxo-full/"

train_dataloader = dict(dataset=dict(data_root=data_root))
test_dataloader = dict(dataset=dict(data_root=data_root, split="val"))
