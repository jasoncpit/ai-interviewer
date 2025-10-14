from __future__ import annotations

from langgraph.graph import END
from langgraph.types import Command

from app.agents.interviewer.utils.state import append_log
from app.schema.models import InterviewState


def decide_node(state: InterviewState) -> Command:
    """Decide whether to continue the interview."""
    if state["turn"] >= state["max_turns"]:
        append_log(state, "decide → END (max turns)")
        return Command(goto=END)

    if set(state["verified_skills"]) == set(state["skills"]):
        append_log(state, "decide → END (all verified)")
        return Command(goto=END)

    inactive = set(state.get("inactive_skills", []))
    active = [skill for skill in state.get("skills", []) if skill not in inactive]
    if not active:
        append_log(state, "decide → END (no active skills)")
        return Command(goto=END)

    append_log(state, "decide → continue")
    return Command(goto="select")
