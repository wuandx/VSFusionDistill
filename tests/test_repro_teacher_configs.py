"""Config tests for the two CMOLD-ladder teacher runs.

configs/repro_cmold/teachers/ holds runs, not methods: each must reproduce
R0's recipe item by item, change only the supervised branch, and leave a
checkpoint that loads strictly into the KD rung that consumes it
(r1_kd_yoloxs.py:60 / r2_cmold_yoloxs.py:65).  Every check here is CPU-only;
no training is started and nothing is written outside pytest's tmp_path.

The topology/param numbers asserted below were measured on this tree
(forward + parameter probe of 2026-11-08) and are geometry-determined, so
they are pinned exactly rather than in a range.

Run: ./.venv/bin/python -m pytest tests/test_repro_teacher_configs.py -q
"""

import inspect
import os
import sys

import numpy as np
import pytest
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aodet.datasets  # noqa: F401,E402  (registry side effects)
import aodet.models  # noqa: F401,E402
from mmengine.config import Config  # noqa: E402
from mmengine.registry import init_default_scope  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join("configs", "repro_cmold")
TEACHERS = os.path.join(CFG, "teachers")

R0 = os.path.join(CFG, "r0_baseline_yoloxs.py")
R1 = os.path.join(CFG, "r1_kd_yoloxs.py")
R2 = os.path.join(CFG, "r2_cmold_yoloxs.py")
T_SONAR_M = os.path.join(TEACHERS, "t_sonar_m_yoloxs.py")
T_CAMERA_S = os.path.join(TEACHERS, "t_camera_s_yoloxs.py")

TEACHER_CONFIGS = [T_SONAR_M, T_CAMERA_S]
# path, the rung that distils from it, that rung's block key, the branches
# FrozenTeacher.forward_head_outputs emits for it.  The sonar teacher emits
# "sonar" as well: with no fused head the uncoupled output is aliased under
# that name (frozen_teacher.py:136-138), and "sonar" is the key R1's
# _kd_losses reads.
RUNGS = [
    (T_SONAR_M, R1, "distillation", {"sonar", "sonar_uncoupled"}),
    (T_CAMERA_S, R2, "cmold", {"camera"}),
]

# what the detector's own predict() emits -- no alias there
# (two_stream_yolox.py:393-410)
DETECTOR_BRANCHES = {T_SONAR_M: {"sonar_uncoupled"},
                     T_CAMERA_S: {"camera"}}

# neck output width: M neck out=192, S neck out=128
NECK_OUT = {T_SONAR_M: 192, T_CAMERA_S: 128}

# the agreed convention: one directory per teacher run
CKPT_SONAR_M = "work_dirs/repro_cmold_teacher/t_sonar_m/epoch_200.pth"
CKPT_CAMERA_S = "work_dirs/repro_cmold_teacher/t_camera_s/epoch_200.pth"

# measured (2026-11-08 probe): geometry-determined, pinned exactly
N_SONAR_M = 25_281_912
N_SONAR_M_PARTS = {"sonar_backbone": 12_352_992,
                   "sonar_neck": 8_938_368,
                   "uncoupled_sonar_head": 3_990_552}
N_CAMERA_S_TOTAL = 16_101_272   # includes the dead sonar stream
N_CAMERA_S_LIVE = 8_938_456     # camera backbone + neck + head
N_CAMERA_S_DEAD = 7_162_816     # sonar backbone + neck, no head

# the student config, source of the init the camera teacher must copy
BASE_MODEL = os.path.join("configs", "_base_", "models",
                          "two_stream_yolox_s.py")

# each teacher's starting point, and the registered note must say so
EXPECTED_INIT = {T_SONAR_M: "from scratch", T_CAMERA_S: "COCO"}
OTHER_SIDE = {T_SONAR_M: "t_camera_s_yoloxs.py",
              T_CAMERA_S: "t_sonar_m_yoloxs.py"}

YOLOX_PAD_VALUE = 114.0
IMG_SHAPE = (640, 640)


def _load(rel_path):
    return Config.fromfile(rel_path)


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


def _plain(obj):
    """ConfigDict/list -> plain dict/list, so equality is content equality."""
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    return obj


def _build(model_cfg):
    from mmdet.registry import MODELS

    init_default_scope("mmdet")
    return MODELS.build(dict(model_cfg))


def _student_init():
    """The student's own backbone/neck init_cfg, from the base config.

    A child config cannot see the base module's _yolox_s_ckpt (only its
    dict), so the camera teacher's URL is compared by value against what
    the base resolves to, not against a re-typed string.
    """
    base = _load(BASE_MODEL).model
    return base.sonar_backbone.init_cfg, base.sonar_neck.init_cfg


def _shapes(model):
    return {k: tuple(v.shape) for k, v in model.state_dict().items()}


def _count(*modules):
    return sum(p.numel() for m in modules for p in m.parameters())


def _det_sample(idx, side, size=IMG_SHAPE, with_gt=False):
    from mmdet.structures import DetDataSample

    ds = DetDataSample()
    ds.set_metainfo(dict(
        img_id=idx,
        img_path=f"{side}/{idx}.png",
        ori_shape=size,
        img_shape=size,
        pad_shape=size,
        scale_factor=(1.0, 1.0),
    ))
    if with_gt:
        from mmengine.structures import InstanceData

        # empty GT: this is a wiring test, not a detection-quality test
        ds.gt_instances = InstanceData()
        ds.gt_instances.bboxes = torch.zeros((0, 4))
        ds.gt_instances.labels = torch.zeros((0,), dtype=torch.long)
    return ds


def _packed(model, size=IMG_SHAPE, with_gt=False):
    """One letterboxed batch through the model's own data preprocessor."""
    rng = np.random.default_rng(0)
    sonar = rng.integers(0, 255, (3,) + size, dtype=np.uint8)
    camera = rng.integers(0, 255, (3,) + size, dtype=np.uint8)
    return model.data_preprocessor(dict(
        img_sonar=[sonar],
        img_camera=[camera],
        data_samples_sonar=[_det_sample(0, "sonar", size, with_gt)],
        data_samples_camera=[_det_sample(0, "camera", size, with_gt)],
    ), training=with_gt)


# ------------------------------------------------------------- inheritance ---


@pytest.mark.parametrize("path", TEACHER_CONFIGS)
def test_inherits_r0_and_nothing_else(path):
    """A teacher run is R0 plus a branch change, held by one _base_ line."""
    assert _raw_bases(path) == ["../r0_baseline_yoloxs.py"]
    cfg = _load(path)
    assert cfg.default_scope == "mmdet"
    assert cfg.train_cfg.type == "EpochBasedTrainLoop"
    assert cfg.train_cfg.max_epochs == 200
    assert cfg.val_cfg is None, "the ladder evaluates offline only"
    assert cfg.test_cfg.type == "TestLoop"
    # the weights the KD rungs will be told about
    assert "distillation" not in cfg.model
    assert "cmold" not in cfg.model


@pytest.mark.parametrize("path", TEACHER_CONFIGS)
def test_recipe_is_r0_item_by_item(path):
    """Nothing in optimiser, schedule, data or hooks may move."""
    cfg, r0 = _load(path), _load(R0)

    assert _plain(cfg.optim_wrapper) == _plain(r0.optim_wrapper)
    assert _plain(cfg.param_scheduler) == _plain(r0.param_scheduler)
    assert _plain(cfg.custom_hooks) == _plain(r0.custom_hooks)
    assert _plain(cfg.auto_scale_lr) == _plain(r0.auto_scale_lr)
    assert _plain(cfg.train_cfg) == _plain(r0.train_cfg)
    assert _plain(cfg.test_cfg) == _plain(r0.test_cfg)
    assert _plain(cfg.train_dataloader) == _plain(r0.train_dataloader)
    assert _plain(cfg.test_dataloader) == _plain(r0.test_dataloader)
    assert cfg.val_cfg == r0.val_cfg is None

    # and the numbers themselves, so a change in R0 cannot move them quietly
    opt = cfg.optim_wrapper.optimizer
    assert opt.type == "SGD"
    assert opt.lr == pytest.approx(1.25e-3)
    assert opt.momentum == 0.9 and opt.weight_decay == 5e-4
    assert opt.nesterov is True
    assert cfg.optim_wrapper.clip_grad.max_norm == 35

    sched = cfg.param_scheduler
    assert [s.type for s in sched] == [
        "QuadraticWarmupLR", "CosineAnnealingLR", "ConstantLR"]
    assert (sched[0].begin, sched[0].end) == (0, 5)
    assert (sched[1].begin, sched[1].T_max, sched[1].end) == (5, 185, 185)
    assert sched[1].eta_min == pytest.approx(6.25e-5)
    assert (sched[2].begin, sched[2].end) == (185, 200)

    assert any(h.type == "EMAHook" for h in cfg.custom_hooks)
    assert not any(h.type == "YOLOXModeSwitchHook" for h in cfg.custom_hooks)

    # letterboxed 640 batch of 8, val-only test loader (the split is frozen)
    assert cfg.train_dataloader.batch_size == 8
    assert cfg.test_dataloader.dataset.split == "val"
    assert tuple(cfg.img_scale) == IMG_SHAPE and cfg.keep_ratio is True


@pytest.mark.parametrize("path, expected", [(T_SONAR_M, CKPT_SONAR_M),
                                            (T_CAMERA_S, CKPT_CAMERA_S)])
def test_checkpoint_path_is_the_agreed_convention(path, expected):
    """One path style, and the run that produces it must be told where."""
    cfg = _load(path)
    assert cfg.teacher_checkpoint == expected
    assert expected.startswith("work_dirs/repro_cmold_teacher/")
    assert expected.endswith("/epoch_200.pth")
    # epoch 200 is a save boundary, or the agreed file would never exist
    interval = cfg.default_hooks.checkpoint.interval
    assert 200 % interval == 0
    # tools/train.py:63-64 defaults to work_dirs/<config basename>, so the
    # agreed directory is only reachable through --work-dir
    stem = os.path.splitext(os.path.basename(path))[0]
    assert os.path.basename(os.path.dirname(expected)) != stem


@pytest.mark.parametrize("path, rung_path, block_key, _branches", RUNGS)
def test_checkpoint_path_agrees_with_the_kd_rung(
        path, rung_path, block_key, _branches):
    """The producing run and the consuming rung name the same file."""
    block = _load(rung_path).model[block_key]
    named = block.get("teacher_checkpoint", block.get("teacher_ckpt"))
    assert named == _load(path).teacher_checkpoint


# --------------------------------------------------------------- topology ---


def test_sonar_m_teacher_is_sonar_only_m():
    cfg = _load(T_SONAR_M)
    model = cfg.model

    assert model.type == "TwoStreamYOLOX"
    for key in ("camera_backbone", "camera_neck", "camera_head",
                "fused_sonar_head"):
        assert model[key] is None, key
    assert model.fusion.type == "NoneFusion"
    assert dict(model.loss_weights) == dict(
        camera=0.0, fused_sonar=0.0, uncoupled_sonar=1.0)

    bb, nk, hd = (model.sonar_backbone, model.sonar_neck,
                  model.uncoupled_sonar_head)
    assert bb.type == "CSPDarknet"
    assert bb.deepen_factor == 0.67 and bb.widen_factor == 0.75
    assert tuple(bb.out_indices) == (2, 3, 4)
    assert tuple(nk.in_channels) == (192, 384, 768)
    assert nk.out_channels == 192 and nk.num_csp_blocks == 2
    assert hd.num_classes == 3
    assert hd.in_channels == 192 and hd.feat_channels == 192

    # from scratch on purpose: the base's S-shaped Pretrained init must be
    # gone, or init_weights() would try to load 128-channel weights into 192
    assert bb.init_cfg is None and nk.init_cfg is None
    assert _plain(bb).get("init_cfg") is None

    # YOLOX's pad value, because the input is letterboxed (R0:48)
    assert model.data_preprocessor.pad_value == YOLOX_PAD_VALUE


@pytest.mark.parametrize("path", TEACHER_CONFIGS)
def test_teacher_init_deviation_is_registered(path):
    """Each teacher states where it starts, and logs it with the run.

    The two sides are deliberately asymmetric: the camera teacher copies
    the student's COCO init, the sonar M teacher cannot (no M weights
    exist) and starts from scratch, so R1's delta is a lower bound.  The
    note is what a later reader will find next to the number.
    """
    dev = _plain(_load(path).known_deviations)
    for key in ("mosaic_mixup", "sync_flip", "multiscale"):
        assert key in dev, "R0's dataset deviations must survive"
    assert dev["teacher_init"].strip(), "an empty note is not a deviation"
    assert dev["teacher_init"].startswith(EXPECTED_INIT[path])

    # and the two docstrings must point at each other, so nobody assumes
    # both teachers start the same way
    with open(path, encoding="utf-8") as f:
        text = f.read()
    assert OTHER_SIDE[path] in text


def test_camera_s_teacher_is_camera_only_s():
    cfg = _load(T_CAMERA_S)
    model = cfg.model

    assert model.type == "TwoStreamYOLOX"
    assert model.fused_sonar_head is None
    assert model.uncoupled_sonar_head is None, "no head reads the sonar neck"
    assert model.fusion.type == "NoneFusion"
    assert dict(model.loss_weights) == dict(
        camera=1.0, fused_sonar=0.0, uncoupled_sonar=0.0)

    # the dead sonar stream is the class invariant, not a choice
    assert model.sonar_backbone is not None
    assert model.sonar_neck is not None
    # the supervised branch starts exactly where the student starts: same
    # Pretrained URL, same prefixes (two_stream_yolox_s.py:20-22, :30-40)
    bb_init, nk_init = _student_init()
    assert bb_init.type == "Pretrained" and bb_init.prefix == "backbone."
    assert nk_init.prefix == "neck."
    assert "yolox_s_8x8_300e_coco_20211121_095711-4592a793.pth" in (
        bb_init.checkpoint)
    assert _plain(model.camera_backbone.init_cfg) == _plain(bb_init)
    assert _plain(model.camera_neck.init_cfg) == _plain(nk_init)
    # the dead stream is not COCO-initialised: nothing reads it, and COCO
    # weights there would suggest otherwise
    assert model.sonar_backbone.init_cfg is None
    assert model.sonar_neck.init_cfg is None
    for key in ("sonar_backbone", "camera_backbone"):
        assert model[key].deepen_factor == 0.33
        assert model[key].widen_factor == 0.5
    for key in ("sonar_neck", "camera_neck"):
        assert tuple(model[key].in_channels) == (128, 256, 512)
        assert model[key].out_channels == 128

    assert model.camera_head.num_classes == 3
    assert model.camera_head.in_channels == 128
    assert model.data_preprocessor.pad_value == YOLOX_PAD_VALUE


def test_camera_teacher_really_loads_the_coco_weights():
    """init_cfg is not decoration: init_weights() must land the checkpoint.

    The camera teacher's start is only "the student's start" if the
    Pretrained init actually fires with prefix "backbone."/"neck." on a
    module that lives at model.camera_backbone -- the prefix names the
    checkpoint's keys, not the attribute, so it has to be tried, not
    assumed.  Uses the locally cached file (no network needed).
    """
    from torch.hub import load_state_dict_from_url

    torch.manual_seed(0)
    fresh = _build(_load(T_CAMERA_S).model)
    torch.manual_seed(0)
    model = _build(_load(T_CAMERA_S).model)

    first = next(iter(fresh.camera_backbone.state_dict()))
    before = fresh.camera_backbone.state_dict()[first].clone()
    model.init_weights()
    after = model.camera_backbone.state_dict()[first]
    assert not torch.equal(before, after), "backbone kept its random start"

    url = model.camera_backbone.init_cfg.checkpoint
    ckpt = load_state_dict_from_url(url, map_location="cpu")
    # mmdet 2.x checkpoint: {"meta": ..., "state_dict": ...}
    ckpt = ckpt.get("state_dict", ckpt)
    assert torch.equal(after, ckpt["backbone." + first])
    # the neck took the same route (prefix "neck."): compare every tensor
    neck_url_keys = ["neck." + k for k in model.camera_neck.state_dict()]
    assert all(k in ckpt for k in neck_url_keys), "prefix is not 'neck.'"
    loaded = {k: v for k, v in model.camera_neck.state_dict().items()}
    assert all(torch.equal(loaded[k], ckpt["neck." + k]) for k in loaded)
    # and the dead sonar stream was not silently COCO-initialised
    sonar = model.sonar_backbone.state_dict()[first]
    assert not torch.equal(sonar, after)


def test_camera_teacher_cannot_drop_its_sonar_stream():
    """task-6 point 4, pinned: `sonar_backbone=None` is a code change.

    TwoStreamYOLOX builds sonar_backbone unconditionally
    (two_stream_yolox.py:124) and both it and sonar_neck are required
    positional arguments (:99-103); FrozenTeacher.forward_head_outputs also
    requires `sonar` (:101-107) and runs the sonar neck anyway (:127).  So
    the config keeps a stream that is built, unsupervised and unread -- the
    same shape R2's inline teacher has -- instead of editing either file.
    """
    from aodet.models.detectors.two_stream_yolox import TwoStreamYOLOX
    from aodet.models.teachers.frozen_teacher import FrozenTeacher

    sig = inspect.signature(TwoStreamYOLOX.__init__)
    for name in ("sonar_backbone", "sonar_neck"):
        assert name in sig.parameters
        assert sig.parameters[name].default is inspect.Parameter.empty, name

    fsig = inspect.signature(FrozenTeacher.forward_head_outputs)
    assert fsig.parameters["sonar"].default is inspect.Parameter.empty

    cfg = _load(T_CAMERA_S)
    with pytest.raises(TypeError):
        _build(dict(cfg.model, sonar_backbone=None))

    # and the built teacher really emits no sonar branch, camera or not
    tcfg = dict(teacher=dict(cfg.model), allow_random_teacher=True)
    teacher = FrozenTeacher(tcfg)
    frame = torch.zeros(1, 3, 128, 128)
    out = teacher.forward_head_outputs(camera=frame, sonar=frame)
    assert set(out) == {"camera"}


# --------------------------------------------------- parameter accounting ---


def test_sonar_m_teacher_param_count():
    model = _build(_load(T_SONAR_M).model)
    assert _count(model) == N_SONAR_M
    for name, expected in N_SONAR_M_PARTS.items():
        assert _count(getattr(model, name)) == expected, name
    assert sum(N_SONAR_M_PARTS.values()) == N_SONAR_M


def test_camera_s_teacher_param_count():
    model = _build(_load(T_CAMERA_S).model)
    live = _count(model.camera_backbone, model.camera_neck, model.camera_head)
    dead = _count(model.sonar_backbone, model.sonar_neck)
    assert live == N_CAMERA_S_LIVE
    assert dead == N_CAMERA_S_DEAD
    assert _count(model) == N_CAMERA_S_TOTAL == live + dead
    # ~8.9M live vs ~25.3M for the sonar M: capacity and modality are the
    # two variables the ladder separates (R1 vs R2)
    assert live < N_SONAR_M


@pytest.mark.parametrize("path, rung_path, block_key, _branches", RUNGS)
def test_state_dict_layout_matches_the_kd_rung(
        path, rung_path, block_key, _branches):
    """Same keys, same shapes: the strict load in frozen_teacher.py:87-95
    cannot fail on a checkpoint produced by these configs."""
    mine = _shapes(_build(_load(path).model))
    block = _load(rung_path).model[block_key]
    theirs = _shapes(_build(block.teacher))

    assert set(mine) == set(theirs)
    assert mine == theirs
    # nothing is hidden behind the loader's foreign-prefix filter
    assert not any(k.startswith(("teacher.", "kd_adapters.")) for k in mine)


# ------------------------------------------------------------- the reload ---


@pytest.mark.parametrize("path, rung_path, block_key, branches", RUNGS)
def test_epoch_200_checkpoint_reloads_into_the_rung(
        path, rung_path, block_key, branches, tmp_path):
    """Save what the run would save, load it the way R1/R2 loads it."""
    from aodet.models.teachers.frozen_teacher import FrozenTeacher

    model = _build(_load(path).model)
    ckpt = tmp_path / "epoch_200.pth"
    torch.save({"meta": {"epoch": 200, "iter": 200 * 416},
                "state_dict": model.state_dict()}, ckpt)

    tcfg = dict(_load(rung_path).model[block_key])
    tcfg["teacher_checkpoint"] = str(ckpt)
    teacher = FrozenTeacher(tcfg)

    frame = torch.zeros(1, 3, 128, 128)
    out = teacher.forward_head_outputs(camera=frame, sonar=frame)
    assert set(out) == branches
    # the inner model is eval-only and train() cannot flip it
    # (frozen_teacher.py:83, :97-98: train() always forwards False)
    assert teacher.model.training is False
    teacher.train()
    assert teacher.model.training is False
    assert all(not p.requires_grad for p in teacher.parameters())


def test_a_mismatched_checkpoint_is_rejected(tmp_path):
    """The load is strict in effect: a renamed key must raise, not be
    silently dropped (frozen_teacher.py:90-95)."""
    from aodet.models.teachers.frozen_teacher import FrozenTeacher

    model = _build(_load(T_SONAR_M).model)
    state = dict(model.state_dict())
    first = next(iter(state))
    state["backbone." + first] = state.pop(first)
    ckpt = tmp_path / "bad.pth"
    torch.save({"state_dict": state}, ckpt)

    tcfg = dict(_load(R1).model["distillation"])
    tcfg["teacher_checkpoint"] = str(ckpt)
    with pytest.raises(RuntimeError, match="does not match the teacher"):
        FrozenTeacher(tcfg)


# ------------------------------------------------------------- inference ---


@pytest.mark.parametrize("path", TEACHER_CONFIGS)
def test_one_cpu_forward_at_640(path):
    """A real forward through the config's own preprocessor, on CPU."""
    model = _build(_load(path).model)
    model.eval()
    packed = _packed(model)
    assert tuple(packed["inputs"]["sonar"].shape) == (1, 3) + IMG_SHAPE
    assert tuple(packed["inputs"]["camera"].shape) == (1, 3) + IMG_SHAPE

    with torch.no_grad():
        # deterministic proof that both trunks ran at 640: three neck levels
        # with the configured width (two_stream_yolox.py:209-215)
        son_feats = model.extract_sonar_feat(packed["inputs"]["sonar"])
        assert len(son_feats) == 3
        for level in son_feats:
            assert level.shape[0] == 1
            assert level.shape[1] == NECK_OUT[path]
            assert level.shape[2] > 0 and level.shape[3] > 0
            assert bool(torch.isfinite(level).all())

        cam_feats = model.extract_camera_feat(packed["inputs"]["camera"])
        if path == T_CAMERA_S:
            assert cam_feats is not None and len(cam_feats) == 3
            assert cam_feats[0].shape[1] == NECK_OUT[path]
        else:
            assert cam_feats is None, "M teacher has no camera stream"

        out = model.predict(packed["inputs"], packed["data_samples"],
                            rescale=False)

    # a branch exists exactly when its head does (two_stream_yolox.py:393-410)
    assert set(out) == DETECTOR_BRANCHES[path]
    for sample_list in out.values():
        assert len(sample_list) == 1
        inst = sample_list[0].pred_instances
        assert inst.bboxes.dim() == 2 and inst.bboxes.shape[1] == 4
        n = inst.bboxes.shape[0]
        assert inst.scores.shape == (n,) and inst.labels.shape == (n,)
        # score_thr is applied before NMS (yolox_head.py:304-305), but
        # max_per_img is not implemented anywhere in mmdet 3.3.0's YOLOXHead,
        # so the count is bounded by the threshold only -- pycocotools caps
        # at maxDets downstream, which is why the ladder can live with it.
        # Random weights may leave nothing above the threshold, so no count
        # is asserted here.
        if n:
            assert float(inst.scores.min()) >= 0.01 - 1e-6
            assert int(inst.labels.max()) < 3


@pytest.mark.parametrize("path", TEACHER_CONFIGS)
def test_one_cpu_training_step(path):
    """loss() + backward at 128x128: the config is trainable, and the branch
    that owns no head receives no gradient at all."""
    model = _build(_load(path).model)
    model.train()
    packed = _packed(model, size=(128, 128), with_gt=True)
    losses = model.loss(packed["inputs"], packed["data_samples"])

    prefix = "camera/" if path == T_CAMERA_S else "uncoupled_sonar/"
    assert sorted(losses) == [prefix + "loss_bbox", prefix + "loss_cls",
                              prefix + "loss_obj"]
    assert all(bool(torch.isfinite(v).all()) for v in losses.values())
    assert any(float(v) > 0 for v in losses.values()), "obj loss, empty GT"

    sum(losses.values()).backward()

    if path == T_CAMERA_S:
        # the dead sonar stream is not merely unsupervised: it is untouched,
        # so the 7.16M parameters never leave their initial values
        for module in (model.sonar_backbone, model.sonar_neck):
            assert all(p.grad is None for p in module.parameters())
    else:
        for module in (model.sonar_backbone, model.sonar_neck,
                       model.uncoupled_sonar_head):
            assert any(p.grad is not None for p in module.parameters())


def test_train_set_is_the_frame_split_ladder():
    """The teacher trains on the same 3,322 frames as its student."""
    from mmdet.registry import DATASETS

    init_default_scope("mmdet")
    kwargs = dict(_load(T_SONAR_M).train_dataloader.dataset)
    kwargs.update(serialize_data=False, lazy_init=False, pipeline=[])
    dataset = DATASETS.build(kwargs)
    assert dataset.split == "train"
    assert len(dataset) == 3322


def test_configs_stay_within_79_columns():
    """The house style (flake8 default) applies to these two files too."""
    for path in TEACHER_CONFIGS:
        with open(path, encoding="utf-8") as f:
            wide = [(i, len(line.rstrip("\n")))
                    for i, line in enumerate(f, 1)
                    if len(line.rstrip("\n")) > 79]
        assert not wide, f"{path}: {wide}"
