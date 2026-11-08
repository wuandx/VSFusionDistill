"""CMOLD reproduction, data side: frame-level 8:2 split + letterbox input.

Base of the R0-R4 ladder in
doc/logs/2026-11-08-cmold-paper-repro-plan.md (§2 platform and split,
§3 undisclosed items, §5 data wiring).  Model and schedule live in
r0_baseline_yoloxs.py; R1-R3 inherit from that.

What this file changes relative to the mainline data config
(configs/_base_/datasets/paired_uxo.py):

1. Split.  Frame-level random 8:2 (seed 0, per-class stratified) instead of
   the recording-level hold-out, because the paper has no "recording"
   concept (plan §2).  The two protocols are not comparable: the same
   weights lose 34.1 AP50 points when the split changes
   (doc/logs/2026-11-05-literature-comparison-blob.md:21).  The frozen
   artifact is /mnt/d/pby/uxo-full/repro/frame_split.json
   ({"seed": 0, "counts": {"train": 3322, "val": 830}, "train": [...],
   "val": [...]}, written by tools/make_frame_split.py).  It is applied
   through `split_file` by FrameSplitPairedSonarCameraDataset (task-5); the
   mainline dataset cannot apply it, since it filters on frame_meta.csv's
   recording-level `split` column (aodet/datasets/paired_dataset.py:105) and
   no loader reads images[].split (aodet/datasets/paired_format.py:84;
   tools/make_frame_split.py:28-43).  data_root therefore stays the complete
   paired root: repro/ holds only frame_split.json plus ann copies, no
   frame_meta.csv / pairs.csv / images/ (tools/make_frame_split.py:38-43).
   The test split (10 recordings) is never opened; evaluation reads "val".

2. Letterbox.  AOPairedResize(keep_ratio=True) on both streams instead of
   the mainline keep_ratio=False squeeze (paired_uxo.py:18-19).  The paper
   states no resolution at all (docs/investigation/01_CMOLD论文规格.md:14,
   92,343), so this follows the YOLOX convention -- 640x640, keep_ratio=True
   plus pad (mmdet 3.3.0 configs/yolox/yolox_s_8xb8-300e_coco.py) -- and is
   deviation 2 of the plan.  What keep_ratio=True actually does here: an
   aspect-preserving cv2.resize with NO pad to a fixed canvas
   (aodet/datasets/transforms/paired_geometric.py:77-82); the padding is the
   batch-time one from PairedDataPreprocessor (pad_size_divisor=32,
   pad_value=114 set in r0), i.e. to the batch maximum, not to a fixed
   640x640 canvas.  Boxes stay valid because scale_factor is the uniform
   resize factor (aodet/datasets/transforms/pack_paired.py:145).

3. No degradation sampling and no camera fork: AOSampleDegLevel and
   AOStudentCameraView are both dropped from the pipelines (plan §5).  The
   camera stream reaches the model undegraded and no camera_clear copy is
   made; only R2-R4 build a camera-consuming teacher, and it reads
   batch_inputs["camera"] (two_stream_yolox.py:363-364).  The sonar student
   never sees the camera.

Registered deviations (plan §3; Lead decision 2026-11-08).  Mosaic and MixUp
are NOT implemented: the paper only says the augmentation is "applied to
increase the robustness", a paired double-stream Mosaic is a data-semantics
change, and aodet/ carries three explicit prohibitions
(configs/_base_/datasets/paired_uxo.py:6,
aodet/datasets/transforms/paired_geometric.py:10,
aodet/models/detectors/two_stream_yolox.py:16).  YOLOX's own recipe, for the
record: Mosaic(prob=1.0, pad_val=114) -> RandomAffine(scaling_ratio_range=
(0.1, 2)) -> MixUp(ratio_range=(0.8, 1.6), pad_val=114) ->
YOLOXHSVRandomAug -> RandomFlip(prob=0.5).  None of it runs in this branch.
Synchronized flips stay at prob=0.0: the 0-degree-centred bearing-axis
precondition has not been re-verified (paired_uxo.py:6-8), and the flag that
would gate them is never injected into results anyway
(paired_geometric.py:116 reads results["sonar_zero_centred"], which no
dataset or transform sets).
"""

_base_ = "../_base_/datasets/paired_uxo.py"

dataset_type = "FrameSplitPairedSonarCameraDataset"

# One path style for the whole branch: WSL absolute paths, because both
# training and evaluation run under WSL.  Never mix a Windows path in.
paired_root = "/mnt/d/pby/uxo-full/paired"
split_file = "/mnt/d/pby/uxo-full/repro/frame_split.json"
data_root = paired_root

img_scale = (640, 640)
keep_ratio = True

# Logged by the run chain; also asserted by tests/test_repro_configs.py.
known_deviations = dict(
    mosaic_mixup="not implemented: no paired Mosaic/MixUp in aodet/",
    sync_flip="off (prob=0.0): 0-degree-centred bearing axis not re-verified",
    multiscale="off: PairedDataPreprocessor never runs batch_augments "
              "(paired_preprocessor.py:53 bypasses DetDataPreprocessor)"
              ", so YOLOX's BatchSyncRandomResize(480, 800) is unavailable",
)

train_pipeline = [
    dict(type="AOLoadPaired"),
    # letterbox: aspect-preserving resize; the pad is the batch-time one
    dict(type="AOPairedResize",
         camera_size=img_scale, sonar_size=img_scale, keep_ratio=keep_ratio),
    # explicitly off -- see the module docstring
    dict(type="AOPairedSyncFlip", prob=0.0, allow=True),
    dict(type="AOPackPairedInputs"),
]

test_pipeline = [
    dict(type="AOLoadPaired"),
    dict(type="AOPairedResize",
         camera_size=img_scale, sonar_size=img_scale, keep_ratio=keep_ratio),
    dict(type="AOPackPairedInputs"),
]

train_dataloader = dict(
    batch_size=8,
    num_workers=4,
    persistent_workers=True,
    sampler=dict(type="DefaultSampler", shuffle=True),
    dataset=dict(
        type=dataset_type,
        data_root=data_root,
        split="train",
        split_file=split_file,
        sonar_zero_centred=True,
        # both sonar GT sources (plan §2): the paper's labels come from a
        # hand-annotated subset this platform has no equivalent for
        sonar_gt_sources=("blob", "projected"),
        pipeline=train_pipeline,
    ),
)

test_dataloader = dict(
    batch_size=1,
    num_workers=2,
    sampler=dict(type="DefaultSampler", shuffle=False),
    dataset=dict(
        type=dataset_type,
        data_root=data_root,
        split="val",
        split_file=split_file,
        sonar_zero_centred=True,
        sonar_gt_sources=("blob", "projected"),
        pipeline=test_pipeline,
    ),
)
