"""R2: CMOLD, camera teacher -> sonar student (rung 2, the paper's method).

Paper anchor (plan §0, Table 1/5 row R2): AP@[.50:.95] 0.797 / AP50 0.949 /
AP75 0.828, i.e. +12.6 AP over R0 and +12.6 over the R1 KD control.  Of that,
R3a (obj-only 0.794) and R3b (cls-only 0.771) split the two terms apart; R2
is the pair (plan §4).

What changes against r0_baseline_yoloxs.py: only `model.cmold` is added.  The
student, data, augmentation and the 200-epoch schedule stay exactly as R0 --
the ladder is a controlled one-variable-per-rung sequence, so anything else
here would make the R2-vs-R0 delta unattributable.  There is NO box-KD term:
cmold_kd.py never touches bbox (plan §3, aodet/models/losses/cmold_kd.py).

Teacher: frozen camera-only YOLOX-S (plan §3 "teacher = YOLOX-S camera-only
(~9.0M), frozen").  Built as a TwoStreamYOLOX with the sonar backbone and
neck still present because the class always has a sonar stream
(frozen_teacher.py:127 runs it unconditionally) but with no sonar head, so
nothing consumes it; camera backbone/neck/head are the S topology, fusion is
NoneFusion (cam_feats is never None here, but the camera head does not depend
on fusion).  This is the same topology as the mainline camera-only config
(configs/f2/e11_bcam_camera_only_yoloxs.py:13-16), so a Bcam-style checkpoint
loads strictly.

Distillation semantics (plan §3 + §6): obj_weight=0.5, score_weight=0.5,
tau=2.0, score_thr=0.3, max_dets=100, topk=None (= K = min of both retained
sets, cmold_kd.py:133-139).  λ=1.0 is structural -- the returned losses are
summed at full weight (two_stream_yolox.py:279-280), so there is no extra
multiplier to configure.

routes: student "sonar_uncoupled" (its only head -- in this detector `sonar`
means the *fused* head, two_stream_yolox.py:90-93) -> teacher "camera".
teacher_input="camera" is right for THIS branch because the repro pipeline
drops AOStudentCameraView (no camera_clear exists) and the camera stream is
undegraded, which is what the paper's teacher was trained on
(two_stream_yolox.py:350-353).

TODO(待对齐): teacher_ckpt points at a run that does not exist yet; the R2
teacher (camera-only YOLOX-S, 200 epochs, camera GT from the same frame-level
split) must be trained and the path fixed before this rung is run.  This file
and r3a/r3b are otherwise complete.
"""

_base_ = "./r0_baseline_yoloxs.py"

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
    num_classes=3,
    in_channels=128,
    feat_channels=128,
)

# placeholder path -- 待对齐, see the module docstring
teacher_ckpt = "work_dirs/repro_cmold_teacher_camera_s/epoch_200.pth"

model = dict(
    cmold=dict(
        teacher=dict(
            type="TwoStreamYOLOX",
            data_preprocessor=dict(type="PairedDataPreprocessor",
                                   pad_size_divisor=32),
            # the sonar stream exists (class invariant) but has no head
            sonar_backbone=_backbone_s,
            sonar_neck=_neck_s,
            camera_backbone=_backbone_s,
            camera_neck=_neck_s,
            camera_head=_head_s,
            uncoupled_sonar_head=None,
            fused_sonar_head=None,
            fusion=dict(type="NoneFusion"),
            loss_weights=dict(camera=1.0, fused_sonar=0.0,
                              uncoupled_sonar=0.0),
            train_cfg=dict(
                assigner=dict(type="SimOTAAssigner", center_radius=2.5,
                              candidate_topk=10)),
            test_cfg=dict(
                nms_pre=1000,
                min_bbox_size=0,
                score_thr=0.01,
                nms=dict(type="nms", iou_threshold=0.65),
                max_per_img=100),
        ),
        teacher_ckpt=teacher_ckpt,
        # the paper's setting: camera teacher on the (undegraded) RGB view
        teacher_input="camera",
        obj_weight=0.5,
        score_weight=0.5,
        tau=2.0,
        score_thr=0.3,
        max_dets=100,
        topk=None,
        routes=dict(sonar_uncoupled="camera"),
    ),
)
