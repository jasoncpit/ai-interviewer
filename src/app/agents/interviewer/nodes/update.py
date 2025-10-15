from __future__ import annotations

from app.agents.interviewer.utils.state import (
    add_unique,
    append_log,
    summarise_skills,
    update_latest_history_entry,
)
from app.agents.interviewer.utils.stats import (
    compute_uncertainty,
    effective_sample_count,
    ensure_prior,
    verify_status,
    welford_update,
)
from app.schema.models import InterviewState, Question


def _belief_for_skill(state: InterviewState, skill: str):
    """Get or initialize belief state for a given skill.

    Returns a dict containing statistics about the skill assessment:
    - mean: average score (initialized to 2.5) // in practice, we can set this using a prior from the skill's metadata
    - n: number of assessments
    - m2: sum of squared differences from mean (for variance calculation)
    - se: standard error
    - lcb: lower confidence bound
    """
    beliefs = state.setdefault("belief_state", {})
    belief = beliefs.setdefault(skill, {})
    ensure_prior(belief)
    return belief


def update_node(state: InterviewState) -> InterviewState:
    """Update posterior belief for the current skill and derive verification status.

    This node:
    1. Updates statistical measures for the skill based on latest grade
    2. Marks skills as inactive if score is too low
    3. Marks skills as verified if confidence threshold is met
    4. Updates turn counter and logs the new state
    """
    question: Question | None = state["current_question"]
    grade = state["last_grade"]
    assert question is not None and grade is not None

    # Get current skill and update statistical measures
    skill = question.skill
    beliefs = _belief_for_skill(state, skill)
    welford_update(beliefs, float(grade.score))  # Update running statistics
    compute_uncertainty(beliefs, state["z_value"])  # Refresh SE / LCB (and UCB)

    # Mark skill as inactive if score is below threshold
    if grade.score < 2:
        add_unique(state["inactive_skills"], skill)

    # Check if skill meets verification criteria
    verified = verify_status(
        beliefs,
        state["verification_threshold"],
        state["min_questions_per_skill"],
    )
    if verified:
        add_unique(state["verified_skills"], skill)
    else:
        state["verified_skills"] = [
            s for s in state.get("verified_skills", []) if s != skill
        ]

    # Increment turn counter and log updates
    state["turn"] += 1
    real_n = effective_sample_count(beliefs)
    append_log(
        state,
        (
            f"update → {skill}: n={real_n} mean={beliefs['mean']:.2f} "
            f"SE={beliefs.get('se', 0.0):.3f} LCB={beliefs.get('lcb', 0.0):.2f}"
        ),
    )
    append_log(
        state,
        f"status → verified={skill in state['verified_skills']} "
        f"inactive={skill in state['inactive_skills']}",
    )

    update_latest_history_entry(state, state.get("last_answer"), grade)

    # Update skill summaries for reporting
    state["skill_summaries"] = summarise_skills(state)
    return state
