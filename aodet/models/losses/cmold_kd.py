"""CMOLD object-level rank-paired distillation (paper eq. 10-19).

Reference: ``docs/investigation/cmold_numbered.txt`` (line numbers of the
plain-text extraction):

* :405 eq. (10) ``K = min(|P~_T|, |P~_S|)``
* :421 eq. (11) ``P_T = P~_T[1:K]``, ``P_S = P~_S[1:K]``
* :445-446      both sides sorted by objectness confidence, descending
* :496 eq. (14) ``L_obj = 1/K sum_k (s_S^(k) - s_T^(k))^2``
* :450-451 (15) ``p~_T = softmax(c_T/tau)``, ``q~_S = softmax(c_S/tau)``
* :462-464 (16) ``L_cls = 1/K sum_k KL(p~_T || q~_S)``
* :471 eq. (17) the KL runs over the C class probabilities
* :483 eq. (18) ``L_cls_scaled = tau^2 * L_cls``
* :497 eq. (19) ``L_CMOLD = alpha * L_obj + beta * L_cls_scaled``
* :493-497      "Because geometric alignment is not used, the object-level
                distillation loss combines only the objectness and class
                distillation components" -- box regression is never
                distilled.

Why this is not :mod:`branch_kd`: ``objectness_kd``/``score_kd`` there are
per-cell KLs that require a one-to-one spatial correspondence between the
student and teacher grids.  A camera teacher and a sonar student live in
different coordinate systems (``cmold_numbered.txt:410-412``, Figure 5), so
this module pairs *candidates by objectness rank* instead: the k-th
highest-confidence teacher prediction is distilled into the k-th
highest-confidence student prediction, wherever those cells happen to be.
Nothing here resizes, aligns or indexes a spatial neighbourhood, so moving a
student peak from one corner of the image to another leaves the loss
unchanged (``tests/test_cmold_kd.py``).

Candidate set: one candidate per head cell, per FPN level.  The paper only
says "raw predictions" (``:394-398``) and never mentions FPN levels, so the
ranking is done independently per image and per level, and the per-level
per-image means are combined with weights equal to their K -- the returned
value is ``sum_g sum_k (.) / sum_g K_g`` over groups g, which is the
K-weighted average of the per-group means.

Objectness enters eq. (14) as a *confidence score* (``:500-501`` "objectness
(confidence) scores", sorted the same way at ``:401-403``), i.e.
``sigmoid(objectness logit)``, not the raw logit.
"""

from __future__ import annotations

from typing import Dict, Optional, Sequence, Tuple

import torch
import torch.nn.functional as F
from torch import Tensor

__all__ = ["select_topk", "objectness_kd_rank", "score_kd_rank",
           "cmold_kd_losses", "DEFAULT_CMOLD_ROUTES"]

# student branch -> teacher branch.  A cross-modal run is the whole point:
# the camera teacher distils into the sonar student.
DEFAULT_CMOLD_ROUTES = {"sonar": "camera"}


def _select_scores(obj: Tensor) -> Tensor:
    """Objectness logits ``B×1×H×W`` -> confidence scores ``B×(H·W)``.

    Selection only: the result is detached and never back-propagated (the
    ranking is a discrete decision, eq. 10-11).
    """
    if obj.dim() != 4 or obj.shape[1] != 1:
        raise ValueError(
            "objectness must be Bx1xHxW, got " f"{tuple(obj.shape)}")
    return obj.detach().float().sigmoid().flatten(1)


def select_topk(obj: Tensor,
                score_thr: float = 0.3,
                max_dets: int = 100,
                topk: Optional[int] = None
                ) -> Tuple[Tensor, Tensor]:
    """Retained candidates of ONE level, sorted by objectness (eq. 10-11).

    Args:
        obj: objectness logits, ``B×1×H×W``.
        score_thr: keep candidates with confidence ``>= score_thr``.  The
            paper does not disclose it (branch plan section 3: 0.3).
        max_dets: at most this many candidates per image (paper: no value;
            branch plan section 3: 100).
        topk: optional hard upper bound on K; ``cmold_numbered.txt:482``
            "can be readily adapted to enforce an upper bound on K".

    Returns:
        ``(idx, count)`` -- ``idx`` is ``B×M`` int64 flat cell indices in
        descending confidence order (``M = min(max_dets, H·W)``); ``count``
        is ``B`` int64, the number of valid *leading* entries after
        ``score_thr``/``max_dets``/``topk``.  Entries past ``count`` are
        padding and must be masked by the caller.
    """
    if int(max_dets) <= 0:
        raise ValueError(f"max_dets must be > 0, got {max_dets}")
    scores = _select_scores(obj)
    n = scores.shape[1]
    m = min(int(max_dets), n)
    masked = scores.masked_fill(scores < float(score_thr), float("-inf"))
    idx = masked.topk(m, dim=1).indices
    count = (scores >= float(score_thr)).sum(1).clamp(max=m)
    if topk is not None:
        count = count.clamp(max=int(topk))
    return idx.to(torch.int64), count.to(torch.int64)


def _gather_ranked(x: Tensor, idx: Tensor, k: Tensor
                   ) -> Tuple[Tensor, Tensor]:
    """Gather the rank-paired cells of one level.

    Args:
        x: ``B×C×H×W`` tensor (class logits or objectness logits).
        idx: ``B×M`` flat indices in descending objectness order.
        k: ``B`` -- how many leading entries of ``idx`` take part.

    Returns:
        ``(vals, mask)``: ``vals`` is ``B×Kmax×C`` with padding zeroed,
        ``mask`` is ``B×Kmax`` bool.  ``Kmax = max(k)``.
    """
    b, c, h, w = x.shape
    n = h * w
    kmax = int(k.max().item()) if k.numel() else 0
    flat = x.reshape(b, c, n).permute(0, 2, 1)          # B×n×C
    if kmax == 0:
        return flat[:, :0], torch.zeros((b, 0), dtype=torch.bool,
                                       device=x.device)
    mask = (torch.arange(kmax, device=x.device).unsqueeze(0)
            < k.unsqueeze(1))
    take = idx[:, :kmax].clamp(max=n - 1).unsqueeze(-1).expand(b, kmax, c)
    return flat.gather(1, take), mask


def _paired_k(s_obj: Sequence[Tensor], t_obj: Sequence[Tensor],
              score_thr: float, max_dets: int, topk: Optional[int],
              lvl: int) -> Tuple[Tensor, Tensor, Tensor]:
    """``(idx_s, idx_t, k)`` for one level; ``k`` is eq. (10)."""
    idx_s, cnt_s = select_topk(s_obj[lvl], score_thr, max_dets, topk)
    idx_t, cnt_t = select_topk(t_obj[lvl], score_thr, max_dets, topk)
    return idx_s, idx_t, torch.minimum(cnt_s, cnt_t)


def _zero_like(seq: Sequence[Tensor]) -> Tensor:
    return torch.zeros((), dtype=torch.float32, device=seq[0].device)


def objectness_kd_rank(s_obj: Sequence[Tensor], t_obj: Sequence[Tensor],
                       score_thr: float = 0.3,
                       max_dets: int = 100,
                       topk: Optional[int] = None) -> Tensor:
    """Eq. (14): mean squared objectness-confidence error over the pairs.

    ``L_obj = 1/K sum_k (s_S^(k) - s_T^(k))^2`` with the k-th teacher
    candidate matched to the k-th student candidate by descending
    objectness (eq. 11); ``K = min(|P_T|, |P_S|)`` (eq. 10).  Box regression
    never enters (``:493-497``).

    Args:
        s_obj / t_obj: student/teacher per-level objectness logits
            ``B×1×H×W``.  The teacher side is detached (frozen).
        score_thr / max_dets / topk: see :func:`select_topk`.

    Returns:
        Scalar, the K-weighted average of the per-image, per-level means.
        Zero when no image retains a candidate on both sides.
    """
    n = min(len(s_obj), len(t_obj))
    if n == 0:
        raise ValueError("objectness_kd_rank needs at least one level")
    num: Optional[Tensor] = None
    den = 0.0
    for lvl in range(n):
        idx_s, idx_t, k = _paired_k(s_obj, t_obj, score_thr, max_dets,
                                    topk, lvl)
        if int(k.sum()) == 0:
            continue
        vs, mask = _gather_ranked(s_obj[lvl], idx_s, k)
        vt, _ = _gather_ranked(t_obj[lvl].detach(), idx_t, k)
        diff = vs.squeeze(-1).sigmoid() - vt.squeeze(-1).float().sigmoid()
        term = (diff ** 2).masked_fill(~mask, 0.0).sum()
        num = term if num is None else num + term
        den += float(k.sum())
    if num is None:
        return _zero_like(s_obj)
    return num / den


def score_kd_rank(s_cls: Sequence[Tensor], s_obj: Sequence[Tensor],
                  t_cls: Sequence[Tensor], t_obj: Sequence[Tensor],
                  score_thr: float = 0.3,
                  max_dets: int = 100,
                  topk: Optional[int] = None,
                  tau: float = 2.0,
                  eps: float = 1e-8) -> Tensor:
    """Eq. (15)-(18): softened class-distribution KL on the ranked pairs.

    ``p~_T = softmax(c_T/tau)``, ``q~_S = softmax(c_S/tau)``,
    ``L_cls = 1/K sum_k KL(p~_T^(k) || q~_S^(k))`` over the C class
    probabilities, then ``L_cls_scaled = tau^2 * L_cls`` (Hinton scaling).

    The class distribution is a softmax over the C class logits exactly as
    the paper defines it (:450-451, :471) -- YOLOX's head is per-class
    sigmoid, so this normaliser is the paper's, not the head's; it is kept
    as written there.

    Args:
        s_cls / t_cls: student/teacher per-level class logits ``B×C×H×W``.
        s_obj / t_obj: per-level objectness logits, used only for ranking.
        tau: temperature, ``> 0`` (paper: 2).
        eps: floor on ``p~_T`` before the log, so saturated softmax output
            cannot produce ``-inf`` / NaN.
        score_thr / max_dets / topk: see :func:`select_topk`.

    Returns:
        Scalar, the K-weighted average of the per-image, per-level means,
        already multiplied by ``tau^2``.  Zero when nothing is retained.
    """
    tau = float(tau)
    if tau <= 0:
        raise ValueError(f"tau must be > 0, got {tau}")
    n = min(len(s_cls), len(s_obj), len(t_cls), len(t_obj))
    if n == 0:
        raise ValueError("score_kd_rank needs at least one level")
    num: Optional[Tensor] = None
    den = 0.0
    for lvl in range(n):
        if s_cls[lvl].shape[1] != t_cls[lvl].shape[1]:
            raise ValueError(
                "student and teacher must share the class space, got "
                f"{s_cls[lvl].shape[1]} vs {t_cls[lvl].shape[1]} classes "
                f"at level {lvl}")
        idx_s, idx_t, k = _paired_k(s_obj, t_obj, score_thr, max_dets,
                                    topk, lvl)
        if int(k.sum()) == 0:
            continue
        with torch.autocast(device_type=s_cls[lvl].device.type,
                            enabled=False):
            vs, mask = _gather_ranked(s_cls[lvl].float(), idx_s, k)
            vt, _ = _gather_ranked(t_cls[lvl].detach().float(), idx_t, k)
            log_q = F.log_softmax(vs / tau, dim=-1)
            p_t = F.softmax(vt / tau, dim=-1)
            kl = (p_t * (p_t.clamp_min(eps).log() - log_q)).sum(-1)
            term = kl.masked_fill(~mask, 0.0).sum()
        num = term if num is None else num + term
        den += float(k.sum())
    if num is None:
        return _zero_like(s_cls)
    return (num / den) * tau ** 2


def cmold_kd_losses(student_out: Dict[str, tuple],
                    teacher_out: Dict[str, tuple],
                    cfg: Optional[dict] = None) -> Dict[str, Tensor]:
    """Eq. (19): ``alpha * L_obj + beta * L_cls_scaled`` per configured route.

    Args:
        student_out / teacher_out: ``{branch: (cls_score, bbox_pred,
            objectness)}``, each item a per-level list (mmdet YOLOXHead
            layout).  ``bbox_pred`` is never touched.
        cfg: ``obj_weight`` (default 0.5), ``score_weight`` (default 0.5),
            ``tau`` (default 2.0), ``score_thr`` (default 0.3),
            ``max_dets`` (default 100), ``topk`` (default None -> K is the
            min of both retained counts), ``routes`` (default
            :data:`DEFAULT_CMOLD_ROUTES`).

    Returns:
        ``{"obj": scalar, "score": scalar}``; a term whose weight is 0 is
        omitted (so alpha=0 / beta=0 arms need no special casing).  Several
        routes accumulate into the same two keys.

    Raises:
        RuntimeError: no route matched both sides (a config mistake, raised
            in the same spirit as :func:`branch_kd.branch_kd_losses`).
    """
    cfg = cfg or {}
    obj_w = float(cfg.get("obj_weight", 0.5))
    score_w = float(cfg.get("score_weight", 0.5))
    tau = float(cfg.get("tau", 2.0))
    score_thr = float(cfg.get("score_thr", 0.3))
    max_dets = int(cfg.get("max_dets", 100))
    raw_topk = cfg.get("topk")
    topk = None if raw_topk is None else int(raw_topk)
    routes = cfg.get("routes") or DEFAULT_CMOLD_ROUTES

    losses: Dict[str, Tensor] = {}
    matched = 0
    for s_name, t_name in routes.items():
        if s_name not in student_out or t_name not in teacher_out:
            continue
        s_branch, t_branch = student_out[s_name], teacher_out[t_name]
        if len(s_branch) != 3 or len(t_branch) != 3:
            raise ValueError(
                "each branch must be (cls_score, bbox_pred, objectness), got "
                f"{len(s_branch)} and {len(t_branch)} items")
        matched += 1
        s_cls, _, s_obj = s_branch
        t_cls, _, t_obj = t_branch
        if obj_w > 0:
            term = obj_w * objectness_kd_rank(
                s_obj, t_obj, score_thr=score_thr, max_dets=max_dets,
                topk=topk)
            losses["obj"] = losses["obj"] + term if "obj" in losses else term
        if score_w > 0:
            term = score_w * score_kd_rank(
                s_cls, s_obj, t_cls, t_obj, score_thr=score_thr,
                max_dets=max_dets, topk=topk, tau=tau)
            losses["score"] = (losses["score"] + term
                               if "score" in losses else term)
    if matched == 0:
        raise RuntimeError(
            "no CMOLD route matched: "
            f"student={list(student_out)} teacher={list(teacher_out)} "
            f"routes={routes}")
    return losses
