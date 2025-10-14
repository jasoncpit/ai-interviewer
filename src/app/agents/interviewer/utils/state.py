from __future__ import annotations

from typing import Dict, List

from app.schema.models import InterviewState, Question

# Compact helper utilities for maintaining interview state.
# They keep the nodes focused on decision logic rather than bookkeeping.


def append_log(state: InterviewState, message: str) -> None:
    """Append a log entry, initialising the log buffer if needed."""
    state.setdefault("logs", [])
    state["logs"].append(message)


def add_unique(collection: List[str], value: str) -> bool:
    """Add value to collection if absent. Returns True when appended."""
    if value not in collection:
        collection.append(value)
        return True
    return False


def record_question(state: InterviewState, question: Question, source: str) -> None:
    """Cache the current question and log the source."""
    state["current_question"] = question
    append_log(
        state,
        f"{source} → [{question.skill}] d={question.difficulty} {question.text[:60]}...",
    )


SkillSummary = Dict[str, object]


def summarise_skills(state: InterviewState) -> List[SkillSummary]:
    """Build a per-skill summary for UI and telemetry."""
    verified = set(state.get("verified_skills", []))
    inactive = set(state.get("inactive_skills", []))
    summaries: List[Dict[str, object]] = []
    for skill in state.get("skills", []):
        belief = state.get("belief_state", {}).get(skill, {})
        status = (
            "verified"
            if skill in verified
            else "inactive" if skill in inactive else "probing"
        )
        summaries.append(
            {
                "skill": skill,
                "status": status,
                "n": int(belief.get("n", 0)),
                "mean": round(float(belief.get("mean", 0.0)), 2),
                "se": round(float(belief.get("se", 0.0)), 3),
                "lcb": round(float(belief.get("lcb", 0.0)), 2),
            }
        )
    return summaries
