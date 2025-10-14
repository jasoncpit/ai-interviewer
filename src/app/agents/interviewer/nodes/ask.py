from __future__ import annotations

from app.agents.interviewer.utils.state import append_log
from app.schema.models import InterviewState


def ask_node(state: InterviewState) -> InterviewState:
    """Log the outgoing question. The UI handles actually asking the user."""
    q = state["current_question"]
    assert q is not None
    append_log(state, f"ask → {q.skill}: {q.text[:80]}")
    return state
