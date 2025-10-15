from __future__ import annotations

import math
from typing import Dict, List, Literal, Tuple

PRIOR_MEAN = 2.5
PRIOR_VARIANCE = 1.5  # prior belief about variance on 1–5 rubric
PRIOR_STRENGTH = 2  # pseudo-samples injected as a prior
SE_FLOOR = 0.25  # guardrail for tiny sample sizes
SE_FLOOR_MIN_REAL = 2  # keep the guardrail until we have this many real samples


def ensure_prior(belief: Dict) -> None:
    """Initialise belief dict with prior pseudo-counts if missing."""
    if "n" not in belief or belief.get("n", 0) == 0:
        belief["n"] = int(PRIOR_STRENGTH)
        belief["mean"] = float(PRIOR_MEAN)
        # m2 = n * variance for the pseudo observations
        belief["m2"] = float(PRIOR_STRENGTH * PRIOR_VARIANCE)
    if "prior_var" not in belief:
        belief["prior_var"] = float(PRIOR_VARIANCE)


def effective_sample_count(belief: Dict) -> int:
    """Real samples collected beyond the prior pseudo-counts."""
    ensure_prior(belief)
    return max(0, int(belief["n"]) - PRIOR_STRENGTH)


def total_effective_questions(beliefs: Dict[str, Dict]) -> int:
    """Total number of graded questions across skills (real samples only)."""
    return sum(effective_sample_count(stats) for stats in beliefs.values())


def welford_update(belief: Dict, score: float) -> None:
    """Single-pass streaming update of mean and M2."""
    ensure_prior(belief)
    n0 = int(belief["n"])
    mu0 = float(belief["mean"])
    m20 = float(belief["m2"])

    n1 = n0 + 1
    delta = score - mu0
    mu1 = mu0 + delta / n1
    m21 = m20 + delta * (score - mu1)

    belief["n"] = n1
    belief["mean"] = mu1
    belief["m2"] = max(m21, 0.0)  # numerical safety: variance never negative


def compute_uncertainty(belief: Dict, z: float, add_ucb: bool = True) -> None:
    """Compute standard error, LCB, and optionally UCB for the belief."""
    ensure_prior(belief)
    n = int(belief["n"])
    mean = float(belief["mean"])
    m2 = float(belief["m2"])

    var = m2 / max(n - 1, 1)  # sample variance
    var = max(var, 0.0)
    se = math.sqrt(var / max(n, 1))

    if effective_sample_count(belief) < SE_FLOOR_MIN_REAL:
        se = max(se, SE_FLOOR)

    lcb = mean - z * se
    belief["se"] = se
    belief["lcb"] = lcb
    if add_ucb:
        belief["ucb"] = mean + z * se


def verify_status(belief: Dict, threshold: float, min_real_samples: int) -> bool:
    """Return True when the skill has enough evidence and the LCB clears the bar."""
    real_n = effective_sample_count(belief)
    lcb = float(belief.get("lcb", -1e9))
    return real_n >= min_real_samples and lcb >= threshold


def select_skill_ucb_with_log(
    beliefs: Dict[str, Dict],
    exploration_c: float,
    mode: Literal["ucb1", "se"] = "ucb1",
) -> Tuple[str, List[str]]:
    """Select next skill using either classic UCB1 or SE-based exploration."""
    total_real = max(1, total_effective_questions(beliefs))
    t = max(2, total_real + 1)

    best_skill = None
    best_ucb = float("-inf")
    logs: List[str] = [f"select_ucb mode={mode} C={exploration_c} t={t}"]

    for skill, stats in beliefs.items():
        ensure_prior(stats)
        mean = float(stats.get("mean", PRIOR_MEAN))
        real_n = effective_sample_count(stats)

        if mode == "se":
            if "se" not in stats:
                compute_uncertainty(stats, z=1.96, add_ucb=False)
            exploration = exploration_c * float(stats["se"])
        else:  # default to classic UCB1 flavour
            exploration = exploration_c * math.sqrt(math.log(t) / max(real_n, 1))

        ucb = mean + exploration
        logs.append(
            f"UCB[{skill}] mean={mean:.2f} real_n={real_n} expl={exploration:.3f} -> {ucb:.3f}"
        )
        if ucb > best_ucb:
            best_skill, best_ucb = skill, ucb

    assert best_skill is not None
    logs.append(f"→ select {best_skill} (UCB={best_ucb:.3f})")
    return best_skill, logs
