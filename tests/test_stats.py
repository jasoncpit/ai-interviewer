from __future__ import annotations

import math

from app.agents.interviewer.utils import stats as stats_utils


def test_compute_uncertainty_sets_bounds():
    belief = {}
    stats_utils.ensure_prior(belief)
    stats_utils.welford_update(belief, 4.0)
    stats_utils.welford_update(belief, 5.0)
    stats_utils.compute_uncertainty(belief, z=1.0)

    assert belief["se"] > 0
    assert belief["ucb"] > belief["mean"]
    assert belief["lcb"] < belief["mean"]


def test_select_skill_ucb_prefers_higher_bound():
    slow = {}
    fast = {}
    stats_utils.ensure_prior(slow)
    stats_utils.ensure_prior(fast)

    for score in [3.0, 3.2, 2.8, 3.1]:
        stats_utils.welford_update(slow, score)
    for score in [4.0, 4.2]:
        stats_utils.welford_update(fast, score)

    stats_utils.compute_uncertainty(slow, z=1.96)
    stats_utils.compute_uncertainty(fast, z=1.96)

    skill, logs = stats_utils.select_skill_ucb_with_log(
        {"slow": slow, "fast": fast}, exploration_c=0.7
    )

    assert skill == "fast"
    assert any("fast" in entry for entry in logs)


def test_verify_status_respects_threshold():
    belief = {}
    stats_utils.ensure_prior(belief)
    for score in [4.0, 4.2, 4.4]:
        stats_utils.welford_update(belief, score)
    stats_utils.compute_uncertainty(belief, z=1.0)

    assert stats_utils.verify_status(belief, threshold=2.9, min_real_samples=2)
    assert not stats_utils.verify_status(belief, threshold=3.5, min_real_samples=4)
