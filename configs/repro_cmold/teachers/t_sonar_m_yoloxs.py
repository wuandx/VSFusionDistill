"""R1's teacher: sonar-only YOLOX-M, trained on the R0 recipe.

This file is a run, not a new method.  It writes out, as a trainable model,
the topology R1 already pins inline as `distillation.teacher`
(r1_kd_yoloxs.py:40-57), and inherits the whole R0 recipe
(r0_baseline_yoloxs.py:44, 60-63, 79-97): 200 epochs, batch 8, SGD
1.25e-3 cosine to 6.25e-5, 15-epoch constant tail, EMA, val_cfg=None.
Capacity is the only difference against the student, which is what makes
R1's delta attributable to teacher size rather than to training.

Checkpoint convention.  tools/train.py:63-64 defaults work_dir to
work_dirs/<config basename>, so the run must pass --work-dir:

    python tools/train.py \
        configs/repro_cmold/teachers/t_sonar_m_yoloxs.py \
        --work-dir work_dirs/repro_cmold_teacher/t_sonar_m

`teacher_checkpoint` below names that file and r1_kd_yoloxs.py:60 carries
the same string, so the two cannot drift.  epoch_200.pth survives because
CheckpointHook runs every 10 epochs and keeps the last 3
(configs/_base_/default_runtime.py:13).

Input.  640x640 letterboxed sonar, padded to the batch maximum with 114 by
the inherited data_preprocessor (r0_baseline_yoloxs.py:48;
keep_ratio=True in uxo_frame_split.py:76).  Same pixels the student sees,
which is what makes the frozen teacher replayable next to it.

Where it starts: from scratch -- and that is a deviation, not a choice.
mmdet 3.3 ships the YOLOX-M geometry (deepen 0.67, widen 0.75, neck
[192, 384, 768] -> 192; configs/yolox/yolox_m_8xb8-300e_coco.py) but no M
weights: its configs/yolox/metafile.yml lists yolox_tiny/s/l/x only, so an
M-shaped Pretrained init cannot be cited the way two_stream_yolox_s.py:
20-22 cites the S one, and a guessed URL would put an unverifiable file in
the init path.  The camera S teacher is the opposite case and does start
from COCO, on the student's own checkpoint (t_camera_s_yoloxs.py): each
teacher takes the best start it can actually get, so the two sides of the
ladder are not symmetric here.

Consequence for R1.  The student starts from COCO
(two_stream_yolox_s.py:14-19) and this teacher does not, so early on the M
teacher is the weaker side: whatever R1 measures is achieved *despite* a
handicapped teacher, and R1's delta is a lower bound on what a
COCO-initialised M teacher would give.  If R1's delta comes out
anomalously small or flips sign, re-examine this paragraph before
re-examining the KD code.  Registered in known_deviations["teacher_init"]
below.
"""

_base_ = ["../r0_baseline_yoloxs.py"]

# Not read by tools/train.py -- the KD rungs read it.  Kept here so the path
# is asserted next to the run that produces it
# (tests/test_repro_teacher_configs.py pins it against r1_kd_yoloxs.py:60).
teacher_checkpoint = "work_dirs/repro_cmold_teacher/t_sonar_m/epoch_200.pth"

# Logged with the run; uxo_frame_split.py:79-85 holds the dataset ones and
# mmengine merges the two dicts.  Tests assert this key exists and is set.
known_deviations = dict(
    teacher_init="from scratch: mmdet 3.3 ships no YOLOX-M COCO checkpoint "
                 "(configs/yolox/metafile.yml lists tiny/s/l/x only), so "
                 "this teacher starts weaker than the COCO-initialised "
                 "student.  If R1's delta is anomalously small or flips "
                 "sign, re-examine this deviation first.  The camera S "
                 "teacher does start from COCO (t_camera_s_yoloxs.py).",
)

model = dict(
    # YOLOX-M geometry, digit for digit r1_kd_yoloxs.py:40-57, so a
    # checkpoint trained here loads into that block with no key left over
    # (FrozenTeacher.load_teacher_state is strict, frozen_teacher.py:87-95)
    sonar_backbone=dict(
        type="CSPDarknet",
        deepen_factor=0.67,
        widen_factor=0.75,
        out_indices=(2, 3, 4),
        # mmengine merges nested dicts, so the base's S-shaped
        # init_cfg=Pretrained prefix "backbone."
        # (two_stream_yolox_s.py:30-31) would survive into M geometry and
        # break init_weights(); None also pins the from-scratch decision
        init_cfg=None,
    ),
    sonar_neck=dict(
        type="YOLOXPAFPN",
        in_channels=[192, 384, 768],
        out_channels=192,
        num_csp_blocks=2,
        # same reason, base prefix "neck." (two_stream_yolox_s.py:38-39)
        init_cfg=None,
    ),
    uncoupled_sonar_head=dict(
        type="YOLOXHead",
        num_classes=3,  # UXO categories (two_stream_yolox_s.py:12)
        in_channels=192,
        feat_channels=192,
    ),
    # camera stream, fused head and loss_weights keep R0's sonar-only
    # shape (r0_baseline_yoloxs.py:49-58): a teacher is one modality here
)
