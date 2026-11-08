"""R0: sonar-only YOLOX-S, no distillation (repro ladder rung 0).

Paper anchor (plan §0, Table 1/5 row R0): AP@[.50:.95] 0.661 / AP50 0.943 /
AP75 0.764.  Difference to that number is NOT a training bug until the
protocol is compared item by item -- see the plan §3 table.

Recipe (plan §4): 200 epochs, batch 8, SGD lr 1.25e-3 -> 6.25e-5, momentum
0.9, weight decay 5e-4.  Both rate values come out of the inherited
schedule arithmetic rather than being retyped: base_lr = 0.01 * 8 / 64 =
1.25e-3 (configs/_base_/schedules/schedule_f2.py:27) and the cosine floor is
base_lr * 0.05 = 6.25e-5 (:46).  Only the epoch count and the three
scheduler endpoints move, and they are written as literals (0/5, T_max=185,
begin=185) the way configs/f2/e11_b0_sonar_only_yoloxs.py:40-57 does, so a
later base change cannot silently move them.

Model: the mainline B0 topology (configs/f2/s0_b0_sonar_only_yoloxs.py) --
camera backbone/neck/head, fused head and fusion removed, det loss on the
uncoupled sonar head only, so the sonar stream runs through its own head and
nothing else.  One addition: data_preprocessor.pad_value=114.0.  That value
is YOLOX's pad value (mmdet 3.3.0 configs/yolox/yolox_s_8xb8-300e_coco.py:
Pad(pad_val=114)) and it only becomes visible now that the input is
letterboxed: AOPairedResize(keep_ratio=True) pads nothing itself
(aodet/datasets/transforms/paired_geometric.py:77-82), so
PairedDataPreprocessor's stack_batch supplies the pad
(aodet/models/data_preprocessors/paired_preprocessor.py:53,
pad_size_divisor=32).  It pads to the batch maximum, not to a fixed 640x640
canvas -- worth remembering when reading per-image results.

Evaluation: no in-loop validation (val_cfg=None inherited, plan §4 "eval
offline"), test_dataloader reads split="val" only; the 10 sealed test
recordings are never opened.  Detections come from the inherited test_cfg
(score_thr 0.01, NMS IoU 0.65, max_per_img 100), and the paper's AP needs
pycocotools' default maxDets, so evaluate the saved prediction files with
tools/test.py rather than reading test_evaluator (plan §3).
"""

_base_ = [
    "./uxo_frame_split.py",
    "../_base_/models/two_stream_yolox_s.py",
    "../_base_/schedules/schedule_f2.py",
    "../_base_/default_runtime.py",
]

max_epochs = 200

model = dict(
    # YOLOX pad value; the mainline keeps 0 because it never letterboxes
    data_preprocessor=dict(pad_value=114.0),
    # sonar-only: the camera stream is not built at all
    camera_backbone=None,
    camera_neck=None,
    camera_head=None,
    fused_sonar_head=None,
    fusion=dict(type="NoneFusion", _delete_=True),
    # spelled out rather than left to the base's 1.0/0.5/0.5: the two absent
    # heads must not be supervised, and R2/R3 inherit this student untouched
    loss_weights=dict(camera=0.0, fused_sonar=0.0, uncoupled_sonar=1.0),
)

base_lr = 0.01 * 8 / 64

train_cfg = dict(type="EpochBasedTrainLoop", max_epochs=max_epochs,
                 val_interval=10)

# Periodic in-loop validation is OFF for the whole ladder, the same way the
# mainline runs (val_cfg=None, no PeriodicValHook in custom_hooks; numbers
# come from tools/test.py --split val --levels d0 on saved predictions, plan
# §4).  Kept explicit rather than inherited because the hook fails closed:
# aodet/engine/periodic_val_hook.py:96-103 refuses any split containing
# "test", and :126-138 rebuilds the dataloader from cfg.test_dataloader and
# writes ds.split -- which for FrameSplitPairedSonarCameraDataset only
# accepts "train"/"val".  If a run ever turns it on, the split it must be
# given is "val", and the test_dataloader below already carries exactly that,
# so the hook inherits a legal value instead of the sealed test split.
val_cfg = None
test_cfg = dict(type="TestLoop")

# warmup 5 + cosine to epoch 185 + constant 15-epoch tail (plan §4)
param_scheduler = [
    dict(type="QuadraticWarmupLR",
         by_epoch=True,
         begin=0,
         end=5,
         convert_to_iter_based=True),
    dict(type="CosineAnnealingLR",
         eta_min=base_lr * 0.05,
         begin=5,
         T_max=max_epochs - 15,
         end=max_epochs - 15,
         by_epoch=True,
         convert_to_iter_based=True),
    dict(type="ConstantLR",
         by_epoch=True,
         factor=1,
         begin=max_epochs - 15,
         end=max_epochs),
]
