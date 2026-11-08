"""R3a: CMOLD objectness term only (paper Table 5 ablation, rung 3a).

Paper anchor (plan §0/§4): AP@[.50:.95] 0.794, AP75 0.804 -- the paper's own
ablation, i.e. R2 with the classification term removed.  Together with R3b
(cls-only 0.771) it shows which half of the rank-paired loss carries the
gain: 0.794 / 0.771 against R2's 0.797 says both terms matter and neither
alone reproduces R2, which is the argument the paper makes for keeping the
pair (plan §4).

Delta against r2_cmold_yoloxs.py: exactly one number --
score_weight 0.5 -> 0.0.  cmold_kd.py drops a term whose weight is zero
(aodet/models/losses/cmold_kd.py:302) rather than scaling it, so the
classification branch is absent from the loss dict, not present with a zero
factor.  Everything else -- student, data, augmentation, 200-epoch schedule,
teacher topology, teacher_ckpt, routes, tau, score_thr, max_dets, topk --
is inherited unchanged, which is what makes this a valid single-variable
ablation.

Note for anyone touching this file: obj_weight=0 AND score_weight=0 together
degenerate to R0's loss (cmold_kd returns an empty dict, so the run is
bit-for-bit a no-KD run).  That is a useful sanity check, not a config to
train.
"""

_base_ = "./r2_cmold_yoloxs.py"

model = dict(
    cmold=dict(
        # β = 0: keep the objectness (ranking) term only
        obj_weight=0.5,
        score_weight=0.0,
    ),
)
