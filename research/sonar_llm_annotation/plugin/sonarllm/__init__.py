"""sonarllm — 用大模型辅助标注声呐图像（候选 / 伪标签，非 GT）。

管线：
    engine (纯 numpy 回波检测)  ->  out/<recording>/proposals.jsonl
                |
                v
    cards  (判读卡 PNG)         ->  out/cards/<sample>.png
                |
                v
    judge  (任何能看图的模型)   ->  out/<recording>/judgments/<sample>.json
                |
                v
    review (人工复核网页, 8771) ->  out/<recording>/reviews.jsonl
                |
                v
    dataset(按既有 paired_role) ->  out/dataset/{images,labels}/...

定位：输出是 **candidate / pseudo-label**，不是 GT、不是 training-ready。
声呐侧的正式 GT 状态仍为 HOLD（原项目 converter 原文：sonar ground-truth
boxes do not exist）。
"""

from pathlib import Path

# .../sonar_llm_annotation/plugin/sonarllm/__init__.py -> parents[2]
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"

__version__ = "0.1.0"
