"""R2's teacher: camera-only YOLOX-S, trained from COCO on the R0 recipe.

The CMOLD teacher has the student's architecture and width
(two_stream_yolox_s.py:25-46) because R2's variable is modality -- camera
subject matter into a sonar student -- and capacity was already spent in
R1.  Recipe, input size and pad value are R0's, inherited here unchanged
(r0_baseline_yoloxs.py:44, 60-63, 79-97); only the supervised branch moves.

Where it starts: COCO, exactly where the student starts.  The camera
backbone and neck carry the student's own pretrained init -- same URL, same
prefix (two_stream_yolox_s.py:20-22, :30-32, :38-40) -- so that R2's delta
is read as "modality changed, nothing else", and so the teacher is not
weakened by a from-scratch fit on 3,322 frames (a weak camera teacher would
cap R2's distillation signal and turn a teacher-quality problem into an
empty conclusion).  Heads stay randomly initialised (3 UXO classes,
two_stream_yolox_s.py:41-46).  The sonar M teacher is the opposite case and
starts from scratch, because mmdet ships no YOLOX-M checkpoint -- that
asymmetry is deliberate and registered on both sides (t_sonar_m_yoloxs.py
and known_deviations below).

Why a camera-only model still carries a sonar stream.  TwoStreamYOLOX
takes sonar_backbone and sonar_neck as required arguments
(two_stream_yolox.py:99-103) and builds sonar_backbone unconditionally
(:124), so sonar_backbone=None raises "cfg should be a dict" at build.
FrozenTeacher.forward_head_outputs also requires its `sonar` argument
(frozen_teacher.py:101-107) and runs the sonar neck unconditionally
(:127).  Dropping the stream is therefore a code change in two files, not
a config choice -- and it is not needed: with no sonar head built, loss()
and predict() skip the sonar neck altogether
(two_stream_yolox.py:249-251, :386-388) and forward_head_outputs emits no
"sonar_uncoupled" branch (frozen_teacher.py:129-130, :136-138).  So the
stream is built, never supervised, never read -- exactly what R2's inline
teacher already does (r2_cmold_yoloxs.py:74-75).  Price: 7.16M dead
parameters, i.e. the checkpoint is 16.10M on disk while 8.94M are trained
(tests/test_repro_teacher_configs.py pins both numbers).  Those dead
parameters get no COCO init either: init_cfg=None there keeps a stream
nobody reads from looking as if it mattered.

Checkpoint convention: same --work-dir rule as t_sonar_m_yoloxs.py
(tools/train.py:63-64), and r2_cmold_yoloxs.py:65 already names the file:

    python tools/train.py \
        configs/repro_cmold/teachers/t_camera_s_yoloxs.py \
        --work-dir work_dirs/repro_cmold_teacher/t_camera_s
"""

_base_ = ["../r0_baseline_yoloxs.py"]

# Written by the run above; r2_cmold_yoloxs.py:65 reads the same string.
teacher_checkpoint = (
    "work_dirs/repro_cmold_teacher/t_camera_s/epoch_200.pth")

# The student's checkpoint, character for character
# (two_stream_yolox_s.py:20-22).  Redefined here because a child config
# does not inherit the base module's variables, only its dict.
_YOLOX_S_COCO = ("https://download.openmmlab.com/mmdetection/v2.0/yolox/"
                 "yolox_s_8x8_300e_coco/"
                 "yolox_s_8x8_300e_coco_20211121_095711-4592a793.pth")

# Logged with the run; uxo_frame_split.py:79-85 carries the dataset ones and
# mmengine merges the two dicts.  tests assert this key exists and is set.
known_deviations = dict(
    teacher_init="COCO: same YOLOX-S checkpoint and same backbone./neck. "
                 "prefixes as the student (two_stream_yolox_s.py:20-22, "
                 ":30-40); heads random.  The dead sonar stream is not "
                 "COCO-initialised, since nothing reads it.  The sonar M "
                 "teacher starts from scratch instead (no M weights exist).",
)


def _init_coco(prefix):
    """The student's init, unchanged (two_stream_yolox_s.py:30-32, :38-40)."""
    return dict(type="Pretrained", checkpoint=_YOLOX_S_COCO, prefix=prefix)


# YOLOX-S geometry, identical to the student and to R2's inline teacher
# (two_stream_yolox_s.py:25-46, r2_cmold_yoloxs.py:45-62)
_backbone_s = dict(
    type="CSPDarknet",
    deepen_factor=0.33,
    widen_factor=0.5,
    out_indices=(2, 3, 4),
)
_neck_s = dict(
    type="YOLOXPAFPN",
    in_channels=[128, 256, 512],
    out_channels=128,
    num_csp_blocks=1,
)
_head_s = dict(
    type="YOLOXHead",
    num_classes=3,  # UXO categories (two_stream_yolox_s.py:12)
    in_channels=128,
    feat_channels=128,
)

model = dict(
    # one geometry, two modules -- two_stream_yolox_s.py:61-64 shares its
    # dicts the same way.  The sonar side is dead weight, so it gets no
    # COCO init; the camera side is the supervised branch and does.
    sonar_backbone=dict(_backbone_s, init_cfg=None),
    sonar_neck=dict(_neck_s, init_cfg=None),
    # _delete_ is required: R0 nulls these three keys
    # (r0_baseline_yoloxs.py:50-52) and mmengine refuses to merge a dict
    # into a base value of None ("set `_delete_=True` to ignore the base")
    camera_backbone=dict(_backbone_s, init_cfg=_init_coco("backbone."),
                         _delete_=True),
    camera_neck=dict(_neck_s, init_cfg=_init_coco("neck."),
                     _delete_=True),
    camera_head=dict(_head_s, _delete_=True),
    # the dead sonar stream: built (class invariant), never supervised
    uncoupled_sonar_head=None,
    fused_sonar_head=None,
    # camera branch only; R0's sonar-only weights would leave the one head
    # this model has unsupervised (r0_baseline_yoloxs.py:57)
    loss_weights=dict(camera=1.0, fused_sonar=0.0, uncoupled_sonar=0.0),
)
