"""P2 (diagnostic arm): the camera teacher retrained with the mainline squeeze.

Why this run exists.  Two camera readings differ by a wide margin and nobody
can say which of five things did it (doc/logs/2026-11-09-r0-first-result-and-
overfit-diagnosis.md:10):

    t_camera_s (letterbox, this branch)      AP 0.9025 / AP50 0.9897
    E13-cam   (squeeze, mainline platform)   AP 0.6401 / AP50 0.9664  (val_id)
    E13-cam   (squeeze, mainline platform)   AP 0.5228 / AP50 0.8180  (val)

The paper's own camera teacher reads AP 0.958 / AP50 0.997, and the shape of
the old gap -- AP50 nearly matched, AP@[.50:.95] far behind -- says "boxes
too loose", not "targets missed".  A test-time probe already showed the
letterbox-trained weights collapse when fed squeezed images (AP 0.9025 ->
0.2712, AP50 0.9897 -> 0.7216), so the geometry the model is trained under is
a live suspect.  But a train/test mismatch is not the same as training under
squeeze, and only a retrain can separate them.

What moves here: exactly one thing.  AOPairedResize keeps keep_ratio=False on
both streams -- 1920x1080 -> 640x640 for the camera (0.333x across, 0.593x
down, aspect 1.78x destroyed) and 128x780 -> 640x640 for the dead sonar
stream, i.e. the mainline geometry (configs/_base_/datasets/paired_uxo.py:
18-19).  Everything else is inherited unchanged from t_camera_s_yoloxs.py:
same model, same COCO init, same optimiser, same 200-epoch schedule, same
3,322-frame split, same pad value, same evaluation split.

Read it as a diagnostic, not as a rung.  The R0-R3 ladder reproduces the
paper; this arm exists only to price one of our own choices, and its number
must never be quoted as a reproduction result.  Decision rule, fixed before
the run (Lead, 2026-11-09):

    AP drops to <= 0.80  (>= 0.10)   geometry is a main cause
    AP drops  < 0.03                  geometry is excluded, look at the
                                      degradation train/test mismatch next
    in between                        partial, quote the point estimate and
                                      move to the degradation arm

One side effect worth recording: with keep_ratio=False every image is exactly
640x640, so the batch-time pad (pad_size_divisor=32, pad_value=114) never
fires.  In the letterbox arm the canvas varied with the batch; the batch-size
probe already showed that variation costs nothing (AP 0.5347 both ways, same
weights, eight per batch vs one), so the two arms differ in geometry only.

Run:

    python tools/train.py \
        configs/repro_cmold/teachers/t_camera_s_stretch_yoloxs.py \
        --work-dir work_dirs/repro_cmold_teacher/t_camera_s_stretch
"""

_base_ = ["t_camera_s_yoloxs.py"]

img_scale = (640, 640)

# the mainline geometry: no aspect preservation, no pad (paired_uxo.py:18-19)
train_pipeline = [
    dict(type="AOLoadPaired"),
    dict(type="AOPairedResize",
         camera_size=img_scale, sonar_size=img_scale, keep_ratio=False),
    dict(type="AOPairedSyncFlip", prob=0.0, allow=True),
    dict(type="AOPackPairedInputs"),
]

test_pipeline = [
    dict(type="AOLoadPaired"),
    dict(type="AOPairedResize",
         camera_size=img_scale, sonar_size=img_scale, keep_ratio=False),
    dict(type="AOPackPairedInputs"),
]

# deep merge keeps every other dataset key (data_root, split, split_file,
# sonar_gt_sources) and replaces the pipeline lists only
train_dataloader = dict(dataset=dict(pipeline=train_pipeline))
test_dataloader = dict(dataset=dict(pipeline=test_pipeline))

# its own directory: no rung may ever load this checkpoint by accident
teacher_checkpoint = (
    "work_dirs/repro_cmold_teacher/t_camera_s_stretch/epoch_200.pth")

known_deviations = dict(
    geometry_probe="P2 diagnostic arm, not a rung: keep_ratio=False (the "
                   "mainline squeeze) instead of letterbox; everything else "
                   "is t_camera_s_yoloxs.py unchanged.  Never quote its "
                   "number as a reproduction result.",
)
