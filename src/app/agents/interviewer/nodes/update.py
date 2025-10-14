from __future__ import annotations

from app.agents.interviewer.utils.state import add_unique, append_log, summarise_skills
from app.agents.interviewer.utils.stats import compute_se_lcb, welford_update
from app.schema.models import InterviewState


def _belief_for_skill(state: InterviewState, skill: str):
    beliefs = state.setdefault("belief_state", {})
    return beliefs.setdefault(
        skill, {"mean": 2.5, "n": 0, "m2": 0.0, "se": 0.0, "lcb": 2.5}
    )


def update_node(state: InterviewState) -> InterviewState:
    """Update posterior belief for the current skill and derive verification status."""
    question = state["current_question"]
    grade = state["last_grade"]
    assert question is not None and grade is not None

    skill = question.skill
    beliefs = _belief_for_skill(state, skill)
    welford_update(beliefs, float(grade.score))
    compute_se_lcb(beliefs, state["z_value"])

    if grade.score <= 2:
        add_unique(state["inactive_skills"], skill)

    verified = (
        beliefs["n"] >= state["min_questions_per_skill"]
        and beliefs["lcb"] >= state["verification_threshold"]
    )
    if verified:
        add_unique(state["verified_skills"], skill)

    state["turn"] += 1
    append_log(
        state,
        (
            f"update → {skill}: n={beliefs['n']} mean={beliefs['mean']:.2f} "
            f"SE={beliefs.get('se', 0.0):.3f} LCB={beliefs.get('lcb', 0.0):.2f}"
        ),
    )
    append_log(
        state,
        f"status → verified={skill in state['verified_skills']} "
        f"inactive={skill in state['inactive_skills']}",
    )

    state["skill_summaries"] = summarise_skills(state)
    return state
