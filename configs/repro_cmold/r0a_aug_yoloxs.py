"""R0-aug (diagnostic arm): R0 plus the augmentations this repository owns.

WHY THIS ARM EXISTS.  R0 finished 200 epochs at 0.5347 AP@[.50:.95] on the
830-frame val split while scoring 0.9947 on its own 3,322 training frames
(results/repro_cmold/r0/eval_train, tools/oneshot/diagA_train_ap.sh).  The
gap is memorisation, not an upstream bug: the network can express the task,
and the recipe in this config has no regulariser at all -- the inherited
train pipeline is Load -> letterbox Resize -> SyncFlip(prob=0.0) -> Pack, and
the paper's own words on augmentation stop at "applied to increase the
robustness" (docs/investigation/01_CMOLD论文规格.md, §3 augmentation).  YOLOX's
published recipe (Mosaic 1.0, MixUp 0.5, HSV, RandomAffine, flip 0.5,
mmdet 3.3.0 configs/yolox/yolox_s_8xb8-300e_coco.py) is therefore mostly
absent from this branch.

WHAT THIS ARM ADDS.  Only the two transforms that already exist here:
AOPairedSyncFlip(prob=0.5) and AOSonarScaleJitter((0.8, 1.25), prob=0.8) --
i.e. left-right mirroring of both streams and a range-axis scale jitter on
the sonar stream alone (paired_geometric.py:137-156: column axis, camera
stream and camera GT stay untouched).  Both are geometrically exact label
transformations, so no label noise is introduced.  The two augs YOLOX leans
on hardest -- Mosaic and MixUp -- are still missing (plan §3: the paired
two-stream Mosaic is a data-semantics change, not a switch).

STATUS.  Diagnostic arm, NOT a rung of the repro ladder: its result never
enters the ladder table and R2/R3 do not inherit it.  Its only job is to
measure how much of the R0 shortfall is missing regularisation.  Reading
rule, fixed before the run: if val AP@[.50:.95] stays below 0.58 the two
cheap augs are not the answer and Mosaic/MixUp becomes the candidate; if it
lands at or above 0.58 the ladder's R0 should be redefined with them (a
pre-data revision, i.e. a plan change to be approved, not a silent swap).

Everything else -- topology, schedule, data split, label space, letterbox,
evaluation -- is inherited unchanged from r0_baseline_yoloxs.py.
"""

_base_ = ["./r0_baseline_yoloxs.py"]

# literal copies of uxo_frame_split.py's img_scale / keep_ratio: a _base_
# merge carries dicts, not the variables those dicts were built from
train_pipeline = [
    dict(type="AOLoadPaired"),
    dict(type="AOPairedResize",
         camera_size=(640, 640), sonar_size=(640, 640), keep_ratio=True),
    # §4.4(2) bans the flip on the deployed model; this arm buys
    # regularisation, not a deployed transform
    dict(type="AOPairedSyncFlip", prob=0.5, allow=True),
    # must run after the fixed-size resize (paired_geometric.py:147-149)
    dict(type="AOSonarScaleJitter", scale_range=(0.8, 1.25), prob=0.8),
    dict(type="AOPackPairedInputs"),
]

train_dataloader = dict(dataset=dict(pipeline=train_pipeline))

known_deviations = dict(
    mosaic_mixup="not implemented anywhere in this repo; still absent here",
    sync_flip="train-time flip prob 0.5 in this diagnostic arm only "
              "(R0 and every ladder rung keep it at 0.0)",
    multiscale="BatchSyncRandomResize unavailable, unchanged",
    augmentation="flip + range-axis scale jitter are the only two augs "
                 "this repo owns; the paper's augmentation set is "
                 "unspecified (plan §3)",
)
