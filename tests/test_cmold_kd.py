"""Unit tests for CMOLD rank-paired object-level distillation.

Contract: ``doc/logs/2026-11-08-cmold-paper-repro-plan.md`` section 6.  The
paper's equations are cited by their line numbers in
``docs/investigation/cmold_numbered.txt``.

Covered here: K = min of both retained counts (eq. 10), rank-monotone pairing
and its geometry-freeness (eq. 11), the tau^2 scaling (eq. 18), gradients
reaching only the student, alpha = 0 / beta = 0 arms without special casing,
a sonar<-camera route across three levels with *different* spatial sizes, and
the additivity of the wiring in ``two_stream_yolox.py``.
"""

import math

import pytest

torch = pytest.importorskip("torch")

from aodet.models.losses.cmold_kd import (  # noqa: E402
    cmold_kd_losses, objectness_kd_rank, score_kd_rank, select_topk)


# -- helpers ---------------------------------------------------------------

def _logit(p):
    """Logit of a probability, so tests can speak in confidences."""
    return math.log(p / (1.0 - p))


def _grid(scores):
    """Objectness logits B=1x1x1xN (one cell per confidence score)."""
    scores = torch.as_tensor(scores, dtype=torch.float32)
    t = torch.tensor([_logit(float(s)) for s in scores], dtype=torch.float32)
    return t.reshape(1, 1, 1, -1).clone()     # clone: a leaf for requires_grad_


def _cls(cells):
    """Class logits B=1xCx1xN from a list of per-cell class-logit lists."""
    arr = torch.as_tensor(cells, dtype=torch.float32)
    if arr.dim() == 1:
        arr = arr.reshape(-1, 1)
    return arr.transpose(0, 1).reshape(1, arr.shape[1], 1, arr.shape[0]).clone()


def _branch(cls, obj):
    return ([cls], [torch.zeros(1, 4, *cls.shape[-2:])], [obj])


def _conf(obj):
    return obj.sigmoid().flatten()


# -- eq. (10)(11): selection and rank pairing -------------------------------

def test_select_topk_sorts_descending_and_honours_threshold():
    obj = _grid([0.10, 0.90, 0.50, 0.95, 0.20])          # 5 cells
    idx, count = select_topk(obj, score_thr=0.3, max_dets=100)
    assert int(count) == 3                                # 0.90, 0.50, 0.95
    order = [float(_conf(obj)[i]) for i in idx[0][:3]]
    assert order == sorted(order, reverse=True)
    assert set(idx[0][:3].tolist()) == {1, 2, 3}


def test_select_topk_caps_at_max_dets_and_topk():
    obj = _grid([0.4, 0.5, 0.6, 0.7, 0.8])
    _, count = select_topk(obj, score_thr=0.0, max_dets=3)
    assert int(count) == 3
    _, count = select_topk(obj, score_thr=0.0, max_dets=100, topk=2)
    assert int(count) == 2


def test_k_is_the_min_of_both_retained_counts():
    """eq. (10): K = min(|P_T|, |P_S|) -- and the surplus teacher candidate
    must not enter the loss."""
    t_obj = _grid([0.90, 0.80, 0.70, 0.05])              # 3 retained
    s_obj = _grid([0.95, 0.60, 0.05, 0.05])              # 2 retained
    idx_t, cnt_t = select_topk(t_obj, score_thr=0.3)
    idx_s, cnt_s = select_topk(s_obj, score_thr=0.3)
    assert (int(cnt_t), int(cnt_s)) == (3, 2)
    loss = objectness_kd_rank([s_obj], [t_obj], score_thr=0.3)
    ts, ss = _conf(t_obj), _conf(s_obj)
    expect = ((float(ss[idx_s[0][0]]) - float(ts[idx_t[0][0]])) ** 2
              + (float(ss[idx_s[0][1]]) - float(ts[idx_t[0][1]])) ** 2) / 2
    assert float(loss) == pytest.approx(expect, rel=1e-6)
    # the 3rd-ranked teacher candidate is outside K: perturbing it changes
    # nothing, perturbing the 2nd-ranked one does
    t_moved = t_obj.clone()
    t_moved[0, 0, 0, 2] = _logit(0.50)                   # still 3rd, past K
    torch.testing.assert_close(objectness_kd_rank([s_obj], [t_moved],
                                                 score_thr=0.3), loss)
    t_2nd = t_obj.clone()
    t_2nd[0, 0, 0, 1] = _logit(0.85)                     # 2nd rank moves up
    assert float(objectness_kd_rank([s_obj], [t_2nd],
                                    score_thr=0.3)) > float(loss)


def test_pairing_is_monotone_by_rank_not_by_cell():
    """eq. (11): the k-th teacher candidate pairs with the k-th student
    candidate, whatever cells they live in."""
    t_obj = _grid([0.90, 0.80, 0.05])
    s_obj = _grid([0.60, 0.95, 0.05])
    idx_t, _ = select_topk(t_obj, score_thr=0.3)
    idx_s, _ = select_topk(s_obj, score_thr=0.3)
    ts, ss = _conf(t_obj), _conf(s_obj)
    pairs = [(float(ss[idx_s[0][k]]), float(ts[idx_t[0][k]]))
             for k in range(2)]
    assert pairs[0][0] > pairs[1][0]                     # student order kept
    assert pairs[0][1] > pairs[1][1]                     # teacher order kept
    # cell-wise pairing would pair (0.60, 0.90) and (0.95, 0.80) instead
    loss = float(objectness_kd_rank([s_obj], [t_obj], score_thr=0.3))
    assert loss == pytest.approx(sum((a - b) ** 2 for a, b in pairs) / 2,
                                 rel=1e-6)
    cellwise = ((float(_conf(s_obj)[0]) - float(_conf(t_obj)[0])) ** 2
                + (float(_conf(s_obj)[1]) - float(_conf(t_obj)[1])) ** 2) / 2
    assert loss != pytest.approx(cellwise, rel=1e-3)


def test_loss_is_invariant_to_where_the_candidates_lie():
    """The cross-modal property: permuting the student's cells (a different
    geometry, same confidences) must not move the loss at all.  This is why
    branch_kd's per-cell KL cannot do this job."""
    t_obj = _grid([0.90, 0.80, 0.60, 0.10])
    s_obj = _grid([0.30, 0.85, 0.55, 0.20])
    base = float(objectness_kd_rank([s_obj], [t_obj], score_thr=0.25))
    for perm in ([3, 2, 1, 0], [1, 3, 0, 2]):
        moved = _grid([float(_conf(s_obj)[i]) for i in perm])
        torch.testing.assert_close(
            objectness_kd_rank([moved], [t_obj], score_thr=0.25),
            torch.tensor(base))


def test_objectness_term_is_mse_on_confidences_not_logits():
    """eq. (14) over "objectness (confidence) scores" (:500-501)."""
    t_obj = _grid([0.88])
    s_obj = _grid([0.12])
    loss = float(objectness_kd_rank([s_obj], [t_obj], score_thr=0.0))
    ts, ss = float(_conf(t_obj)), float(_conf(s_obj))
    assert loss == pytest.approx((ss - ts) ** 2, rel=1e-5)
    assert loss < 1.0                    # a logit MSE here would be ~5.8


def test_empty_retention_is_zero_and_finite():
    t_obj = _grid([0.10, 0.20])
    s_obj = _grid([0.30, 0.05])          # teacher retains nothing
    assert float(objectness_kd_rank([s_obj], [t_obj], score_thr=0.5)) == 0.0
    out = cmold_kd_losses(
        {"sonar": _branch(_cls([0.0]), s_obj)},
        {"camera": _branch(_cls([0.0]), t_obj)},
        cfg=dict(score_thr=0.5))
    assert set(out) == {"obj", "score"}
    for v in out.values():
        assert float(v) == 0.0 and torch.isfinite(v)


def test_multiple_levels_are_weighted_by_their_k():
    """Aggregation: sum_g sum_k(.) / sum_g K_g over levels g."""
    two_a = _grid([0.9, 0.8])
    two_b = _grid([0.7, 0.6])
    one = _grid([0.5])
    t = [two_a, one]
    s = [_grid([0.1, 0.2]), _grid([0.9])]
    loss = float(objectness_kd_rank(s, t, score_thr=0.0))
    lvl0 = float(objectness_kd_rank([s[0]], [t[0]], score_thr=0.0))
    lvl1 = float(objectness_kd_rank([s[1]], [t[1]], score_thr=0.0))
    assert loss == pytest.approx((2 * lvl0 + 1 * lvl1) / 3, rel=1e-6)
    del two_b


# -- eq. (15)-(18): the class term ----------------------------------------

def _kl(p, q):
    return float((p * (p.log() - q.log())).sum())


def test_class_term_is_softmax_kl_times_tau_squared():
    """eq. (15)-(18): KL(softmax(c_T/tau) || softmax(c_S/tau)) averaged over
    K, then multiplied by tau^2."""
    t_cls = _cls([[1.0, -0.5, 0.25]])
    s_cls = _cls([[0.2, 0.4, -1.0]])
    t_obj, s_obj = _grid([0.9]), _grid([0.8])
    tau = 2.0
    got = float(score_kd_rank([s_cls], [s_obj], [t_cls], [t_obj],
                              score_thr=0.0, tau=tau))
    p = torch.softmax(t_cls[0, :, 0, 0] / tau, -1)
    q = torch.softmax(s_cls[0, :, 0, 0] / tau, -1)
    assert got == pytest.approx(_kl(p, q) * tau ** 2, rel=1e-6)


def test_tau_squared_keeps_a_small_logit_gap_tau_invariant():
    """Without the tau^2 factor the softened KL would shrink like 1/tau^2;
    with it, a small gap gives (nearly) the same number at tau = 1 and 2."""
    torch.manual_seed(0)
    t_cls = _cls([(torch.randn(3) * 0.05).tolist()])
    s_cls = _cls([(torch.randn(3) * 0.05).tolist()])
    t_obj, s_obj = _grid([0.9]), _grid([0.8])
    a = float(score_kd_rank([s_cls], [s_obj], [t_cls], [t_obj],
                            score_thr=0.0, tau=1.0))
    b = float(score_kd_rank([s_cls], [s_obj], [t_cls], [t_obj],
                            score_thr=0.0, tau=2.0))
    assert b == pytest.approx(a, rel=0.1)                 # tau^2 present
    assert b > 0.5 * a                                    # not 1/tau^2
    with pytest.raises(ValueError):
        score_kd_rank([s_cls], [s_obj], [t_cls], [t_obj], tau=0.0)


def test_class_term_rejects_mismatched_class_spaces():
    s_cls, t_cls = _cls([[0.0, 0.0]]), _cls([[0.0, 0.0, 0.0]])
    with pytest.raises(ValueError, match="class space"):
        score_kd_rank([s_cls], [_grid([0.9])], [t_cls], [_grid([0.9])])


# -- gradients ------------------------------------------------------------

def test_gradients_reach_only_the_student():
    t_obj = _grid([0.90, 0.80, 0.70]).requires_grad_()
    t_cls = _cls([[1.0, 0.0, -1.0], [0.5, 0.5, -0.5], [0.0, 1.0, 0.0]]
                 ).requires_grad_()
    s_obj = _grid([0.60, 0.50, 0.40]).requires_grad_()
    s_cls = _cls([[0.0, 0.2, -0.2], [0.1, -0.1, 0.3], [0.0, 0.4, -0.4]]
                 ).requires_grad_()
    out = cmold_kd_losses({"sonar": _branch(s_cls, s_obj)},
                          {"camera": _branch(t_cls, t_obj)},
                          cfg=dict(score_thr=0.0))
    (out["obj"] + out["score"]).backward()
    for t in (t_obj, t_cls):
        assert t.grad is None                             # frozen teacher
    for s in (s_obj, s_cls):
        assert s.grad is not None and float(s.grad.abs().sum()) > 0


def test_detached_teacher_gives_no_grad_even_if_it_could():
    """The teacher tensors are detached inside the loss, so an
    accidentally-trainable teacher raises no gradient."""
    t_obj = _grid([0.9, 0.8])
    t_cls = _cls([[1.0, 0.0], [0.0, 1.0]])
    s_obj = _grid([0.1, 0.2]).requires_grad_()
    s_cls = _cls([[0.0, 1.0], [1.0, 0.0]])
    t_obj_clone = t_obj.clone().detach().requires_grad_()
    out = cmold_kd_losses({"sonar": _branch(s_cls, s_obj)},
                          {"camera": _branch(t_cls.clone(), t_obj_clone)},
                          cfg=dict(score_thr=0.0))
    out["obj"].backward()
    assert t_obj_clone.grad is None


# -- eq. (19): weights, routes, additivity --------------------------------

def _pair_cfg(**kw):
    cfg = dict(score_thr=0.0, obj_weight=0.5, score_weight=0.5)
    cfg.update(kw)
    return cfg


def _out_pair():
    t_obj = _grid([0.9, 0.8, 0.7])
    s_obj = _grid([0.5, 0.4, 0.3])
    t_cls = _cls([[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]])
    s_cls = _cls([[0.0, 1.0], [1.0, 0.0], [0.2, 0.2]])
    return ({"sonar": _branch(s_cls, s_obj)},
            {"camera": _branch(t_cls, t_obj)})


def test_zero_weight_drops_the_term_without_raising():
    student, teacher = _out_pair()
    both = cmold_kd_losses(student, teacher, cfg=_pair_cfg())
    assert set(both) == {"obj", "score"}
    alpha0 = cmold_kd_losses(student, teacher, cfg=_pair_cfg(obj_weight=0))
    assert set(alpha0) == {"score"}                       # eq. (19): beta only
    torch.testing.assert_close(alpha0["score"], both["score"])
    beta0 = cmold_kd_losses(student, teacher, cfg=_pair_cfg(score_weight=0))
    assert set(beta0) == {"obj"}                          # alpha only
    torch.testing.assert_close(beta0["obj"], both["obj"])
    off = cmold_kd_losses(student, teacher,
                          cfg=_pair_cfg(obj_weight=0, score_weight=0))
    assert off == {}


def test_weights_scale_the_terms():
    student, teacher = _out_pair()
    a = cmold_kd_losses(student, teacher,
                        cfg=_pair_cfg(obj_weight=1.0, score_weight=1.0))
    b = cmold_kd_losses(student, teacher,
                        cfg=_pair_cfg(obj_weight=2.0, score_weight=2.0))
    torch.testing.assert_close(b["obj"], a["obj"] * 2.0)
    torch.testing.assert_close(b["score"], a["score"] * 2.0)


def test_default_weights_are_the_paper_alpha_beta():
    """Defaults: obj_weight = score_weight = 0.5, tau = 2, K = min."""
    student, teacher = _out_pair()
    default = cmold_kd_losses(student, teacher)
    explicit = cmold_kd_losses(student, teacher,
                              cfg=dict(obj_weight=0.5, score_weight=0.5,
                                       tau=2.0, score_thr=0.3,
                                       max_dets=100, topk=None))
    for k in ("obj", "score"):
        torch.testing.assert_close(default[k], explicit[k])


def test_cross_branch_route_sonar_from_camera_runs():
    """The paper's setting: a camera teacher distilling into the sonar
    student, three levels, *different* spatial sizes on the two sides."""
    torch.manual_seed(0)
    sizes_t = [(4, 4), (2, 2), (1, 1)]
    sizes_s = [(8, 8), (4, 4), (2, 2)]
    t_cls = [torch.randn(1, 3, *s) for s in sizes_t]
    t_obj = [torch.randn(1, 1, *s) for s in sizes_t]
    s_cls = [torch.randn(1, 3, *s) for s in sizes_s]
    s_obj = [torch.randn(1, 1, *s, requires_grad=True) for s in sizes_s]
    out = cmold_kd_losses(
        {"sonar_uncoupled": (s_cls, [None] * 3, s_obj)},
        {"camera": (t_cls, [None] * 3, t_obj)},
        cfg=dict(routes={"sonar_uncoupled": "camera"}, score_thr=0.0))
    assert set(out) == {"obj", "score"}
    for v in out.values():
        assert torch.isfinite(v) and float(v) > 0
    (out["obj"] + out["score"]).backward()
    assert all(o.grad is not None for o in s_obj)


def test_unmatched_route_raises():
    student, teacher = _out_pair()
    with pytest.raises(RuntimeError, match="no CMOLD route matched"):
        cmold_kd_losses(student, {"sonar": teacher["camera"]},
                        cfg=dict(routes={"sonar": "camera"}))
    # a route whose student branch is absent simply contributes nothing
    ok = cmold_kd_losses(student, teacher,
                         cfg=dict(routes={"sonar_uncoupled": "camera",
                                          "sonar": "camera"}))
    assert set(ok) == {"obj", "score"}


def test_branch_must_be_a_three_tuple():
    student, teacher = _out_pair()
    with pytest.raises(ValueError, match="three|cls_score"):
        cmold_kd_losses({"sonar": (teacher["camera"][0],)},
                        teacher, cfg=dict(score_thr=0.0))


# -- additivity of the detector wiring ------------------------------------

def _need_mmdet():
    pytest.importorskip("mmdet")
    pytest.importorskip("mmcv")
    import aodet.models  # noqa: F401  (registers the extensions)
    from mmengine.registry import init_default_scope
    init_default_scope("mmdet")


IMG = (128, 160)


def _stream_cfg(num_classes=3):
    norm = dict(type="BN", momentum=0.03, eps=0.001)
    act = dict(type="Swish")
    common = dict(norm_cfg=norm, act_cfg=act)
    backbone = dict(type="CSPDarknet", deepen_factor=0.33, widen_factor=0.25,
                    out_indices=(2, 3, 4), **common)
    neck = dict(type="YOLOXPAFPN", in_channels=[64, 128, 256],
                out_channels=64, num_csp_blocks=1, **common)
    head = dict(type="YOLOXHead", num_classes=num_classes, in_channels=64,
                feat_channels=64, stacked_convs=2, strides=(8, 16, 32),
                **common,
                loss_cls=dict(type="CrossEntropyLoss", use_sigmoid=True,
                              reduction="sum", loss_weight=1.0),
                loss_bbox=dict(type="IoULoss", mode="square", eps=1e-16,
                               reduction="sum", loss_weight=5.0),
                loss_obj=dict(type="CrossEntropyLoss", use_sigmoid=True,
                              reduction="sum", loss_weight=1.0),
                loss_l1=dict(type="L1Loss", reduction="sum", loss_weight=1.0))
    return backbone, neck, head


def _sonar_model(**kw):
    from aodet.models.detectors.two_stream_yolox import TwoStreamYOLOX
    sbb, snc, shd = _stream_cfg()
    kwargs = dict(
        sonar_backbone=sbb, sonar_neck=snc, uncoupled_sonar_head=shd,
        train_cfg=dict(assigner=dict(type="SimOTAAssigner",
                                     center_radius=2.5)),
        test_cfg=dict(score_thr=0.01,
                      nms=dict(type="nms", iou_threshold=0.65)),
        data_preprocessor=dict(type="PairedDataPreprocessor",
                               mean=[0, 0, 0], std=[1, 1, 1],
                               bgr_to_rgb=False, pad_size_divisor=32),
    )
    kwargs.update(kw)
    return TwoStreamYOLOX(**kwargs)


def _camera_teacher_cfg():
    sbb, snc, _ = _stream_cfg()
    cbb, cnc, chd = _stream_cfg()
    return dict(type="TwoStreamYOLOX", sonar_backbone=sbb, sonar_neck=snc,
                camera_backbone=cbb, camera_neck=cnc, camera_head=chd)


def _sample(n_obj=2):
    from mmdet.structures import DetDataSample
    from mmdet.structures.bbox import HorizontalBoxes
    from mmengine.structures import InstanceData
    ds = DetDataSample()
    ds.set_metainfo({"img_id": 0, "img_shape": IMG, "ori_shape": IMG,
                     "scale_factor": (1.0, 1.0),
                     "batch_input_shape": IMG, "pad_shape": IMG})
    gt = InstanceData()
    gt.bboxes = HorizontalBoxes(
        torch.tensor([[20.0, 20.0, 60.0, 50.0],
                      [80.0, 60.0, 120.0, 100.0]][:n_obj], dtype=torch.float32))
    gt.labels = torch.zeros(n_obj, dtype=torch.long)
    ds.gt_instances = gt
    return ds


def _paired_batch(b=2):
    import numpy as np
    rng = np.random.default_rng(0)
    return {
        "inputs": None,
        "img_sonar": [torch.from_numpy(
            rng.integers(0, 255, (3, *IMG), dtype=np.uint8)) for _ in range(b)],
        "img_camera": [torch.from_numpy(
            rng.integers(0, 255, (3, *IMG), dtype=np.uint8)) for _ in range(b)],
        "data_samples_sonar": [_sample() for _ in range(b)],
        "data_samples_camera": [_sample() for _ in range(b)],
    }


def _prep(model, data, training=True):
    prepped = model.data_preprocessor(data, training=training)
    return prepped["inputs"], prepped["data_samples"]


def test_wiring_without_cmold_key_is_inert():
    """The hard requirement: no ``cmold`` in the model config -> the new
    code path must not run and no parameters may appear."""
    _need_mmdet()
    model = _sonar_model()
    assert model.cmold_teacher is None and model.cmold_cfg is None
    assert not any("cmold" in n for n in model.state_dict())

    def _boom(*a, **k):
        raise AssertionError("_cmold_losses ran without a cmold config")

    model._cmold_losses = _boom
    data = _paired_batch()
    inputs, samples = _prep(model, data)
    model.train()
    losses = model.loss(inputs, samples)
    assert losses and not any(k.startswith("cmold/") for k in losses)
    sum(v for k, v in losses.items() if "loss" in k).backward()

    # explicit cmold=None is the same object as omitting the key
    again = _sonar_model(cmold=None)
    assert again.cmold_teacher is None
    assert set(again.state_dict()) == set(model.state_dict())


def test_wiring_without_cmold_is_bit_identical_across_runs():
    """Same seed, same weights, same batch -> bitwise identical losses
    (a regression here would mean an extra RNG draw or a reordered head)."""
    _need_mmdet()
    torch.manual_seed(0)
    a = _sonar_model()
    torch.manual_seed(0)
    b = _sonar_model()
    a.train(), b.train()
    data = _paired_batch()
    la = a.loss(*_prep(a, data))
    lb = b.loss(*_prep(b, data))
    assert set(la) == set(lb)
    for k in la:
        assert torch.equal(la[k], lb[k]), k


def test_wiring_cmold_route_runs_and_trains_only_the_student():
    _need_mmdet()
    model = _sonar_model(cmold=dict(
        teacher=_camera_teacher_cfg(), allow_random_teacher=True,
        routes={"sonar_uncoupled": "camera"}, teacher_input="camera",
        obj_weight=0.5, score_weight=0.5, tau=2.0, score_thr=0.3))
    assert model.cmold_teacher is not None
    assert all(not p.requires_grad for p in model.cmold_teacher.parameters())
    data = _paired_batch()
    inputs, samples = _prep(model, data)
    model.train()
    losses = model.loss(inputs, samples)
    kd = [k for k in losses if k.startswith("cmold/")]
    assert set(kd) == {"cmold/loss_obj", "cmold/loss_score"}, list(losses)
    for k in kd:
        assert torch.isfinite(losses[k]) and float(losses[k]) > 0
    _, log_vars = model.parse_losses(losses)          # keys carry "loss"
    assert all(k in log_vars for k in kd)
    model.zero_grad()
    sum(losses[k] for k in kd).backward()
    assert all(p.grad is None for p in model.cmold_teacher.parameters())
    g = sum(float(p.grad.abs().sum()) for p in model.parameters()
            if p.requires_grad and p.grad is not None)
    assert g > 0
