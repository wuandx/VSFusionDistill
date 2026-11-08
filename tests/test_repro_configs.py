"""Config-level tests for the CMOLD reproduction ladder (configs/repro_cmold/).

Follows tests/test_f2_configs.py (parse every real config, build what
Runner.from_cfg would build), plus the assertions this branch exists to
guarantee: the frame-level split artefact is wired through `split_file`, both
streams letterbox instead of squeezing, degradation sampling is gone, the
three known deviations are registered, and R2/R3a/R3b differ only in the
CMOLD weights the plan's Table 5 ablation asks for.

Sources for the numbers asserted here: plan §3 (12 undisclosed items), §4
(R0-R4 ladder), §6 (frozen interfaces); two_stream_yolox.py:85-93 for the
distillation/cmold key names; cmold_kd.py:275-282 for the loss defaults.

Run: ./.venv/bin/python -m pytest tests/test_repro_configs.py -q
"""

import os
import sys

import pytest
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aodet.datasets  # noqa: F401,E402  (registry side effects)
import aodet.models  # noqa: F401,E402
from mmengine.config import Config  # noqa: E402
from mmengine.registry import init_default_scope  # noqa: E402

# QuadraticWarmupLR registers into mmdet's registry root, not mmengine's
from mmdet.registry import PARAM_SCHEDULERS  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join("configs", "repro_cmold")

UXO = os.path.join(CFG, "uxo_frame_split.py")
R0 = os.path.join(CFG, "r0_baseline_yoloxs.py")
R1 = os.path.join(CFG, "r1_kd_yoloxs.py")
R2 = os.path.join(CFG, "r2_cmold_yoloxs.py")
R3A = os.path.join(CFG, "r3a_obj_only.py")
R3B = os.path.join(CFG, "r3b_cls_only.py")

ALL_CONFIGS = [UXO, R0, R1, R2, R3A, R3B]
MODEL_CONFIGS = [R0, R1, R2, R3A, R3B]

PAIRED_ROOT = "/mnt/d/pby/uxo-full/paired"
SPLIT_FILE = "/mnt/d/pby/uxo-full/repro/frame_split.json"
IMG_SCALE = (640, 640)
YOLOX_PAD_VALUE = 114.0


def _load(rel_path):
    return Config.fromfile(rel_path)


def _types(pipeline):
    return [t["type"] for t in pipeline]


def _step(pipeline, name):
    hits = [t for t in pipeline if t["type"] == name]
    assert len(hits) == 1, f"expected exactly one {name} in {_types(pipeline)}"
    return hits[0]


def _raw_bases(path):
    """The file's own `_base_`, before mmengine merges it away."""
    import ast

    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=path)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "_base_"
                for t in node.targets):
            value = ast.literal_eval(node.value)
            return [value] if isinstance(value, str) else list(value)
    raise AssertionError(f"{path}: no _base_ assignment")


# ---------------------------------------------------------------- parsing ---


@pytest.mark.parametrize("path", ALL_CONFIGS)
def test_config_parses(path):
    """Every file loads through mmengine, _base_ chain included."""
    cfg = _load(path)
    assert cfg.train_dataloader
    assert cfg.test_dataloader
    if path != UXO:
        assert cfg.model
        assert cfg.param_scheduler
        assert cfg.optim_wrapper


@pytest.mark.parametrize("path", ALL_CONFIGS)
def test_base_chain_resolves(path):
    """The inheritance graph is exactly the six-file ladder."""
    bases = _raw_bases(path)
    for base in bases:
        resolved = os.path.join(os.path.dirname(os.path.abspath(path)), base)
        assert os.path.exists(resolved), f"{path}: missing base {base}"

    if os.path.abspath(path) == os.path.abspath(UXO):
        assert bases == ["../_base_/datasets/paired_uxo.py"]
    elif os.path.abspath(path) == os.path.abspath(R0):
        assert bases == [
            "./uxo_frame_split.py",
            "../_base_/models/two_stream_yolox_s.py",
            "../_base_/schedules/schedule_f2.py",
            "../_base_/default_runtime.py",
        ]
    elif os.path.abspath(path) == os.path.abspath(R1):
        assert bases == ["./r0_baseline_yoloxs.py"]
    elif os.path.abspath(path) == os.path.abspath(R2):
        assert bases == ["./r0_baseline_yoloxs.py"]
    else:  # R3a / R3b
        assert bases == ["./r2_cmold_yoloxs.py"]


@pytest.mark.parametrize("path", MODEL_CONFIGS)
def test_inherits_the_shared_bases(path):
    """R0 pulls the four shared bases in; nothing is redefined by hand."""
    cfg = _load(path)
    assert cfg.default_scope == "mmdet"
    assert cfg.custom_imports
    assert cfg.custom_hooks
    assert cfg.auto_scale_lr.enable is False
    assert cfg.train_cfg.type == "EpochBasedTrainLoop"
    assert cfg.train_cfg.max_epochs == 200
    assert cfg.train_cfg.val_interval == 10
    assert cfg.val_cfg is None, "the ladder evaluates offline only"
    assert cfg.test_cfg.type == "TestLoop"


# ------------------------------------------------------------------- data ---


@pytest.mark.parametrize("path", ALL_CONFIGS)
def test_data_side_is_frame_split(path):
    """Frame-level 8:2 artefact + complete paired root, one path style."""
    cfg = _load(path)
    train = cfg.train_dataloader.dataset
    test = cfg.test_dataloader.dataset

    assert train.type == "FrameSplitPairedSonarCameraDataset"
    assert test.type == "FrameSplitPairedSonarCameraDataset"
    assert train.data_root == PAIRED_ROOT
    assert test.data_root == PAIRED_ROOT
    assert train.split_file == SPLIT_FILE
    assert test.split_file == SPLIT_FILE
    assert cfg.data_root == PAIRED_ROOT

    assert train.split == "train"
    assert test.split == "val", "the sealed test split must not be readable"
    assert train.sonar_zero_centred is True

    # both sonar GT sources, on both sides (plan §2)
    assert tuple(train.sonar_gt_sources) == ("blob", "projected")
    assert tuple(test.sonar_gt_sources) == ("blob", "projected")

    # batch recipe: YOLOX's 8/GPU, single-stream test
    assert cfg.train_dataloader.batch_size == 8
    assert cfg.test_dataloader.batch_size == 1


@pytest.mark.parametrize("path", ALL_CONFIGS)
def test_letterbox_on_both_streams(path):
    """keep_ratio=True on camera and sonar, train and test pipelines."""
    cfg = _load(path)
    assert cfg.keep_ratio is True
    assert tuple(cfg.img_scale) == IMG_SCALE

    for pipeline in (cfg.train_dataloader.dataset.pipeline,
                     cfg.test_dataloader.dataset.pipeline):
        resize = _step(pipeline, "AOPairedResize")
        assert resize.keep_ratio is True
        assert tuple(resize.camera_size) == IMG_SCALE
        assert tuple(resize.sonar_size) == IMG_SCALE
        # nothing else is allowed to resize afterwards
        assert "AOSonarScaleJitter" not in _types(pipeline)


@pytest.mark.parametrize("path", ALL_CONFIGS)
def test_degradation_sampling_is_off(path):
    """No AOSampleDegLevel and no AOStudentCameraView anywhere (plan §5)."""
    cfg = _load(path)
    for pipeline in (cfg.train_dataloader.dataset.pipeline,
                     cfg.test_dataloader.dataset.pipeline):
        assert "AOSampleDegLevel" not in _types(pipeline)
        assert "AOStudentCameraView" not in _types(pipeline)


@pytest.mark.parametrize("path", ALL_CONFIGS)
def test_no_mosaic_mixup_and_sync_flip_off(path):
    """Deviation 1 registered, letterbox the only input change, flip off."""
    cfg = _load(path)
    train = cfg.train_dataloader.dataset.pipeline

    for name in _types(train):
        assert "Mosaic" not in name, f"{path}: Mosaic must not be built"
        assert "MixUp" not in name, f"{path}: MixUp must not be built"
    assert "MultiImageMixDataset" not in str(cfg.train_dataloader.dataset.type)

    # the deviation is registered, not silently forgotten
    note = cfg.known_deviations.mosaic_mixup
    assert "not implemented" in note
    assert "Mosaic" in note

    # synchronized flips stay off: the 0-centred bearing axis is unverified
    flip = _step(train, "AOPairedSyncFlip")
    assert flip.prob == 0.0
    assert flip.allow is True
    assert "AOPairedSyncFlip" not in _types(
        cfg.test_dataloader.dataset.pipeline)


# ---------------------------------------------------------------- student ---


def test_r0_is_sonar_only_with_yolox_pad():
    """B0 topology + YOLOX pad value, because letterbox now pads."""
    cfg = _load(R0)
    model = cfg.model
    assert model.type == "TwoStreamYOLOX"
    for key in ("camera_backbone", "camera_neck", "camera_head",
                "fused_sonar_head"):
        assert model[key] is None, key
    assert model.fusion.type == "NoneFusion"
    assert model.loss_weights["uncoupled_sonar"] == 1.0
    assert model.loss_weights["fused_sonar"] == 0.0
    assert model.loss_weights["camera"] == 0.0

    pre = model.data_preprocessor
    assert pre.type == "PairedDataPreprocessor"
    assert pre.pad_size_divisor == 32
    assert pre.pad_value == YOLOX_PAD_VALUE

    # single-modality: no KD blocks at all
    assert "distillation" not in model
    assert "cmold" not in model


def test_r0_recipe_is_the_plan_recipe():
    """200 epochs, lr 1.25e-3 -> 6.25e-5, SGD 0.9 / 5e-4, EMA."""
    cfg = _load(R0)
    opt = cfg.optim_wrapper.optimizer
    assert opt.type == "SGD"
    assert opt.lr == pytest.approx(0.01 * 8 / 64)
    assert opt.lr == pytest.approx(1.25e-3)
    assert opt.momentum == 0.9
    assert opt.weight_decay == 5e-4
    assert opt.nesterov is True
    assert cfg.optim_wrapper.paramwise_cfg.norm_decay_mult == 0.0
    assert cfg.optim_wrapper.paramwise_cfg.bias_decay_mult == 0.0
    assert cfg.optim_wrapper.clip_grad.max_norm == 35

    sched = cfg.param_scheduler
    assert [s.type for s in sched] == [
        "QuadraticWarmupLR", "CosineAnnealingLR", "ConstantLR"]
    assert sched[0].begin == 0 and sched[0].end == 5
    assert sched[1].begin == 5
    assert sched[1].T_max == 185, "200 - 15: cosine ends at epoch 185"
    assert sched[1].end == 185
    assert sched[1].eta_min == pytest.approx(0.01 * 8 / 64 * 0.05)
    assert sched[1].eta_min == pytest.approx(6.25e-5)
    assert sched[2].begin == 185 and sched[2].end == 200

    assert any(h.type == "EMAHook" for h in cfg.custom_hooks)
    assert not any(h.type == "YOLOXModeSwitchHook" for h in cfg.custom_hooks)

    # official YOLOX test thresholds, inherited from the model base
    assert cfg.model.test_cfg.score_thr == 0.01
    assert cfg.model.test_cfg.nms.iou_threshold == 0.65
    assert cfg.model.test_cfg.max_per_img == 100


def test_r1_is_logit_kd_from_an_m_teacher():
    """R1 = the paper's KD control: same-modality, larger teacher."""
    cfg = _load(R1)
    assert "cmold" not in cfg.model
    kd = cfg.model.distillation
    teacher = kd.teacher

    assert teacher.type == "TwoStreamYOLOX"
    assert teacher.camera_backbone is None
    assert teacher.camera_head is None
    assert teacher.fused_sonar_head is None
    assert teacher.uncoupled_sonar_head is not None
    assert tuple(teacher.sonar_neck.in_channels) == (192, 384, 768)
    assert teacher.sonar_neck.out_channels == 192
    assert teacher.sonar_backbone.deepen_factor == 0.67
    assert teacher.sonar_backbone.widen_factor == 0.75
    # strict-loaded from the teacher checkpoint, so no COCO init
    assert "init_cfg" not in teacher.sonar_backbone

    assert kd.obj_weight == 1.0
    assert kd.score_weight == 1.0
    assert kd.tau == 2.0
    assert dict(kd.routes) == {"sonar_uncoupled": "sonar_uncoupled"}
    assert kd.teacher_checkpoint.endswith(".pth")

    # the student is still R0's sonar-only S
    assert cfg.model.camera_backbone is None
    assert cfg.model.sonar_backbone.deepen_factor == 0.33
    assert cfg.model.data_preprocessor.pad_value == YOLOX_PAD_VALUE


def test_r2_cmold_block_matches_plan_6():
    """Camera teacher -> sonar student, rank-paired, no box KD."""
    cfg = _load(R2)
    assert "distillation" not in cfg.model
    cmold = cfg.model.cmold
    teacher = cmold.teacher

    assert teacher.type == "TwoStreamYOLOX"
    assert teacher.camera_backbone.deepen_factor == 0.33
    assert teacher.camera_neck is not None
    assert teacher.camera_head.num_classes == 3
    assert teacher.camera_head.in_channels == 128
    # the sonar stream exists but no head consumes it
    assert teacher.sonar_backbone is not None
    assert teacher.uncoupled_sonar_head is None
    assert teacher.fused_sonar_head is None
    assert teacher.fusion.type == "NoneFusion"
    assert teacher.loss_weights["camera"] == 1.0

    assert cmold.teacher_ckpt.endswith(".pth")
    assert cmold.teacher_input == "camera"
    assert dict(cmold.routes) == {"sonar_uncoupled": "camera"}, \
        "a sonar-only student KD's its uncoupled head from the camera teacher"
    assert cmold.obj_weight == 0.5
    assert cmold.score_weight == 0.5
    assert cmold.tau == 2.0
    assert cmold.score_thr == 0.3
    assert cmold.max_dets == 100
    assert cmold.topk is None, "K = min of both retained sets"

    # lambda = 1.0 is structural: no weight key may appear
    for extra in ("loss_weight", "lambda", "weight"):
        assert extra not in cmold

    # the student is unchanged against R0
    r0 = _load(R0)
    assert cfg.model.uncoupled_sonar_head == r0.model.uncoupled_sonar_head
    assert cfg.model.loss_weights == r0.model.loss_weights
    assert cfg.model.data_preprocessor == r0.model.data_preprocessor


@pytest.mark.parametrize(
    "path, obj_weight, score_weight", [(R3A, 0.5, 0.0), (R3B, 0.0, 0.5)])
def test_r3_arms_differ_only_in_one_weight(path, obj_weight, score_weight):
    """Table 5 ablation: R3a drops cls, R3b drops obj, nothing else moves."""
    cfg = _load(path)
    full = _load(R2).model.cmold
    arm = cfg.model.cmold

    assert arm.obj_weight == obj_weight
    assert arm.score_weight == score_weight
    assert (arm.obj_weight, arm.score_weight) != (full.obj_weight,
                                                 full.score_weight)

    for key in full:
        if key in ("obj_weight", "score_weight"):
            continue
        if isinstance(full[key], dict):
            assert dict(arm[key]) == dict(full[key]), key
        else:
            assert arm[key] == full[key], key

    # the student and the data side are untouched by the ablation
    assert cfg.model.loss_weights == _load(R2).model.loss_weights
    assert (cfg.train_dataloader.dataset.pipeline
            == _load(R2).train_dataloader.dataset.pipeline)


# ----------------------------------------------------------------- builds ---


@pytest.mark.parametrize("path", MODEL_CONFIGS)
def test_model_builds(path):
    """Build the student as Runner.from_cfg would.

    The KD blocks are dropped first: `distillation`/`cmold` cold-start a
    FrozenTeacher, which needs the teacher checkpoint on disk.  The teacher
    sub-configs are built standalone below instead, the same split
    tests/test_f2_configs.py:39-45 uses for E10/E13.
    """
    from mmdet.registry import MODELS

    init_default_scope("mmdet")
    cfg = _load(path)
    model_cfg = dict(cfg.model)
    model_cfg.pop("distillation", None)
    model_cfg.pop("cmold", None)
    model = MODELS.build(model_cfg)
    assert model is not None
    assert not hasattr(model, "teacher") or model.teacher is None


@pytest.mark.parametrize("path", [R1, R2, R3A, R3B])
def test_teacher_builds_standalone(path):
    """The frozen teacher's own config is a valid model config."""
    from mmdet.registry import MODELS

    init_default_scope("mmdet")
    model = _load(path).model
    key = "distillation" if "distillation" in model else "cmold"
    teacher = MODELS.build(dict(model[key].teacher))
    assert teacher is not None
    assert not hasattr(teacher, "teacher") or teacher.teacher is None


@pytest.mark.parametrize("path", MODEL_CONFIGS)
def test_periodic_val_is_off_and_would_be_legal(path):
    """In-loop validation is off; the split it would inherit is "val".

    PeriodicValHook fails closed (aodet/engine/periodic_val_hook.py:96-103
    rejects any split containing "test") and rebuilds the loader from
    cfg.test_dataloader, writing ds.split (:126-138), which for
    FrameSplitPairedSonarCameraDataset only accepts "train"/"val".  The
    ladder evaluates offline instead, but the test dataloader still carries
    a legal value so enabling the hook cannot reach the sealed split.
    """
    cfg = _load(path)
    assert not any("PeriodicVal" in h["type"] for h in cfg.custom_hooks)
    assert cfg.val_cfg is None
    assert cfg.test_dataloader.dataset.split == "val"

    # the hook also reads <data_root>/{camera,sonar}.json directly
    # (periodic_val_hook.py:139-143), which repro/ does not have
    for side in ("camera", "sonar"):
        root = cfg.test_dataloader.dataset.data_root
        assert os.path.exists(os.path.join(root, f"{side}.json"))


def test_split_artifact_matches_the_config():
    """The wired split file is the frozen 8:2 artefact, seed 0."""
    import json

    cfg = _load(UXO)
    with open(cfg.train_dataloader.dataset.split_file, encoding="utf-8") as f:
        split = json.load(f)
    assert split["seed"] == 0
    assert split["counts"] == {"train": 3322, "val": 830}
    assert len(split["train"]) == 3322
    assert len(split["val"]) == 830
    # frame-level, so ids are frame ids and no recording holds out entirely
    assert set(split["train"]).isdisjoint(split["val"])


@pytest.mark.parametrize("path", [R1, R2])
def test_teacher_routes_resolve(path):
    """Every pinned route names a branch the frozen teacher really emits.

    Builds the teacher through FrozenTeacher itself (weights skipped, the
    documented unit-test escape hatch) and forwards dummy 3x128x128 frames,
    so a topology mistake -- e.g. a camera teacher without a camera head --
    fails here instead of on the training GPU.
    """
    from aodet.models.detectors.two_stream_yolox import TwoStreamYOLOX
    from aodet.models.teachers.frozen_teacher import FrozenTeacher

    init_default_scope("mmdet")
    cfg = _load(path)
    block = cfg.model["cmold"] if "cmold" in cfg.model else cfg.model[
        "distillation"]
    routes = dict(block.routes)

    # weights are skipped on purpose: the teacher checkpoint does not exist
    # yet (待对齐), and FrozenTeacher still tries to load when one is named
    tcfg = dict(block)
    tcfg.pop("teacher_checkpoint", None)
    tcfg.pop("teacher_ckpt", None)
    tcfg["allow_random_teacher"] = True
    teacher = FrozenTeacher(tcfg)
    frame = torch.zeros(1, 3, 128, 128)
    out = teacher.forward_head_outputs(camera=frame, sonar=frame)

    # the teacher only emits what its heads build
    if block.teacher.camera_head is None:
        assert "camera" not in out
    else:
        assert "camera" in out
    if block.teacher.uncoupled_sonar_head is None:
        assert "sonar_uncoupled" not in out
    else:
        assert "sonar_uncoupled" in out

    for student_branch, teacher_branch in routes.items():
        assert teacher_branch in out, teacher_branch
        # and the student really has the head that route starts from
        head_attr = TwoStreamYOLOX._BRANCHES[student_branch][2]
        assert cfg.model[head_attr] is not None, student_branch


def test_param_schedulers_build():
    """Each scheduler entry builds as the runner builds it."""
    opt = torch.optim.SGD([torch.nn.Parameter(torch.zeros(1))], lr=0.01)
    for path in MODEL_CONFIGS:
        cfg = _load(path)
        schedulers = [
            PARAM_SCHEDULERS.build(dict(s, epoch_length=100),
                                   default_args=dict(optimizer=opt))
            for s in cfg.param_scheduler
        ]
        assert len(schedulers) == len(cfg.param_scheduler)


def test_frame_split_dataset_class_pending():
    """等 task-5: the reader subclass must exist for any of this to run.

    FrameSplitPairedSonarCameraDataset applies repro/frame_split.json; the
    mainline PairedSonarCameraDataset cannot (it filters on frame_meta.csv's
    recording-level `split` column, aodet/datasets/paired_dataset.py:105).
    Skipped, not failed, until the subclass lands -- the configs already
    name it, so a mismatch will surface here.
    """
    from mmdet.registry import DATASETS

    init_default_scope("mmdet")
    try:
        DATASETS.get("FrameSplitPairedSonarCameraDataset")
    except KeyError:
        pytest.skip("等 task-5: FrameSplitPairedSonarCameraDataset 尚未交付")

    cfg = _load(UXO)
    # counts are frozen by tools/make_frame_split.py (seed 0)
    expected = {"train": 3322, "val": 830}
    for split in ("train", "val"):
        kwargs = dict(cfg.train_dataloader.dataset)
        kwargs["split"] = split
        kwargs["pipeline"] = []
        dataset = DATASETS.build(kwargs)
        assert len(dataset) == expected[split], split
