"""R0s (diagnostic arm): R0's recipe retrained in the mainline squeeze.

The sonar twin of t_camera_s_stretch_yoloxs.py.  R0 trains and is evaluated
on letterboxed input (105x640 content, batch-padded); the mainline trains and
evaluates on a 640x640 squeeze of the same 128x780 frame.  Nobody has ever
compared the two in one exam, so the cost of our own geometry choice on the
sonar side is unknown.  This arm prices it.

Only one thing moves relative to r0_baseline_yoloxs.py: AOPairedResize keeps
keep_ratio=False on both streams.  Model, COCO init, optimiser, the 200-epoch
schedule, the 3,322-frame split, the loss weights and the evaluation split are
inherited untouched.  Train and eval use the same geometry, so the number is
internally consistent and can be compared with R0's 0.5347 / 0.7429 directly.

Not a rung.  The R0-R3 ladder reproduces the paper; this arm exists only to
price a choice of ours, and its number must never be quoted as a
reproduction result.  Reference point for how badly geometry alone can bite:
the same R0 weights, evaluated on the squeezed feed they were not trained
for, read AP 0.0003 / AP50 0.0015 -- a coordinate-frame swap, not a
degradation (doc/logs/2026-11-09-r0-first-result-and-overfit-diagnosis.md
§10.2).

What it does NOT settle: the paper states no resolution and no scaling rule
(docs/investigation/01_CMOLD论文规格.md:14, 92, 343), so neither arm can be
declared "what the paper did".  This arm only says what OUR geometry choice
costs us.

Run:

    python tools/train.py configs/repro_cmold/r0_stretch_yoloxs.py \
        --work-dir work_dirs/repro_cmold/r0_stretch
"""

_base_ = ["r0_baseline_yoloxs.py"]

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

# deep merge keeps data_root / split / split_file / gt sources
train_dataloader = dict(dataset=dict(pipeline=train_pipeline))
test_dataloader = dict(dataset=dict(pipeline=test_pipeline))

known_deviations = dict(
    geometry_probe="R0s diagnostic arm, not a rung: keep_ratio=False (the "
                   "mainline squeeze) instead of letterbox; every other "
                   "ingredient is r0_baseline_yoloxs.py unchanged.  Never "
                   "quote its number as a reproduction result.",
)
