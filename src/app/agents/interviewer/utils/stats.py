from __future__ import annotations

import math
from typing import Dict, List, Tuple


def welford_update(belief: Dict, score: float) -> None:
    """Online mean/variance update."""
    n0 = int(belief.get("n", 0))
    mu0 = float(belief.get("mean", 2.5))
    m20 = float(belief.get("m2", 0.0))

    n1 = n0 + 1
    mu1 = (mu0 * n0 + score) / n1
    m21 = m20 + (score - mu0) * (score - mu1)

    belief["n"] = n1
    belief["mean"] = mu1
    belief["m2"] = m21


def compute_se_lcb(belief: Dict, z: float) -> None:
    """Compute standard error and lower confidence bound."""
    n = int(belief.get("n", 0))
    mean = float(belief.get("mean", 0.0))
    if n <= 1:
        belief["se"] = 0.0
        belief["lcb"] = mean
        return

    var = float(belief.get("m2", 0.0)) / (n - 1)
    se = math.sqrt(max(0.0, var) / n)
    belief["se"] = se
    belief["lcb"] = mean - z * se


def select_skill_ucb_with_log(
    beliefs: Dict[str, Dict],
    total_turns: int,
    exploration_c: float,
) -> Tuple[str, List[str]]:
    """Return the best skill via UCB along with debug logs."""
    t = max(1, total_turns)
    best_skill = None
    best_ucb = float("-inf")
    logs: List[str] = []

    for skill, stats in beliefs.items():
        mean = float(stats.get("mean", 0.0))
        n = int(stats.get("n", 0))
        exploration = exploration_c * math.sqrt(math.log(t + 1.0) / (n + 1.0))
        ucb = mean + exploration
        logs.append(
            f"UCB[{skill}] mean={mean:.2f} n={n} expl={exploration:.3f} -> {ucb:.3f}"
        )
        if ucb > best_ucb:
            best_skill, best_ucb = skill, ucb

    assert best_skill is not None
    logs.append(f"→ select {best_skill} (UCB={best_ucb:.3f})")
    return best_skill, logs
