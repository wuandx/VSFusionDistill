"""R1: traditional logit distillation, sonar-only YOLOX-M -> YOLOX-S (rung 1).

Paper anchor (plan §0, Table 1/5 row R1): AP@[.50:.95] 0.671, i.e. +1.0 over
R0 -- the paper's own "KD alone barely helps" control, which is what makes
the CMOLD jump (0.797) attributable to the cross-modal ranking term rather
than to distillation as such.  Optional rung: if its number drifts, R2 has
no explanation to lean on.

What changes against r0_baseline_yoloxs.py: nothing in the student, the data,
the augmentation or the 200-epoch schedule.  A frozen sonar-only YOLOX-M
teacher is added through `model.distillation`, the mainline path
(two_stream_yolox.py:276-278), and KD runs on the sonar head's logits only.
YOLOX-M is used because the paper's R1 pairs S with M (plan §0), so capacity
-- not modality -- is the one variable against R0.

Teacher topology: the same TwoStreamYOLOX class, sonar-only (camera backbone,
neck, head and fused head all None), M depth (mmdet 3.3.0
configs/yolox/yolox_m_8xb8-300e_coco.py: deepen 0.67, widen 0.75, neck
in [192, 384, 768] / out 192 / 2 csp blocks, head 192).  No COCO init: the
teacher is loaded strictly from `teacher_checkpoint`
(aodet/models/teachers/frozen_teacher.py:87-95), so a pretrained backbone
would be overwritten anyway.  The frozen sonar backbone still runs on every
step (frozen_teacher.py:127) -- its camera branch is skipped because
camera_backbone is None (:123).

`teacher_input="clear"` is inert here and kept for symmetry with R2: it only
selects which camera tensor the teacher would read, and a sonar-only teacher
has none, so it neither reads batch_inputs["camera"] nor raises on a missing
camera_clear (two_stream_yolox.py:296-305).  routes are explicit rather than
defaulted: student head "sonar_uncoupled" -> teacher's sonar-only head, which
FrozenTeacher also exposes as "sonar" (frozen_teacher.py:136-137).

TODO(待对齐): teacher_checkpoint points at a run that does not exist yet; the
R1 teacher (sonar-only YOLOX-M, 200 epochs, same data/schedule) must be
trained and the path fixed before this rung is run.
"""

_base_ = "./r0_baseline_yoloxs.py"

_teacher_backbone_m = dict(
    type="CSPDarknet",
    deepen_factor=0.67,
    widen_factor=0.75,
    out_indices=(2, 3, 4),
)
_teacher_neck_m = dict(
    type="YOLOXPAFPN",
    in_channels=[192, 384, 768],
    out_channels=192,
    num_csp_blocks=2,
)
_teacher_head_m = dict(
    type="YOLOXHead",
    num_classes=3,
    in_channels=192,
    feat_channels=192,
)

# placeholder path -- 待对齐, see the module docstring
teacher_checkpoint = "work_dirs/repro_cmold_teacher/t_sonar_m/epoch_200.pth"

model = dict(
    distillation=dict(
        teacher=dict(
            type="TwoStreamYOLOX",
            data_preprocessor=dict(type="PairedDataPreprocessor",
                                   pad_size_divisor=32),
            sonar_backbone=_teacher_backbone_m,
            sonar_neck=_teacher_neck_m,
            camera_backbone=None,
            camera_neck=None,
            camera_head=None,
            uncoupled_sonar_head=_teacher_head_m,
            fused_sonar_head=None,
            fusion=dict(type="NoneFusion"),
            loss_weights=dict(camera=0.0, fused_sonar=0.0,
                              uncoupled_sonar=1.0),
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
        teacher_checkpoint=teacher_checkpoint,
        teacher_input="clear",
        # logit KD: objectness and classification, both at full weight
        # (plan §4 R1 is "traditional KD"; the CMOLD weights arrive in R2)
        obj_weight=1.0,
        score_weight=1.0,
        tau=2.0,
        bg_floor=0.01,
        routes=dict(sonar_uncoupled="sonar_uncoupled"),
    ),
)
