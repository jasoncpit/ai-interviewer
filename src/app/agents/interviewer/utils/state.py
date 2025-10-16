from __future__ import annotations

from typing import Dict, List, Optional

from app.agents.interviewer.utils.stats import (
    compute_uncertainty,
    effective_sample_count,
    ensure_prior,
)
from app.schema.models import Grade, InterviewState, Question

MAX_HISTORY = 10

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
    history = state.setdefault("question_history", [])
    history.append(
        {
            "skill": question.skill,
            "question": question.text,
            "difficulty": question.difficulty,
            "source": source,
            "turn": state.get("turn", 0),
            "answer": None,
            "score": None,
            "reasoning": None,
        }
    )
    if len(history) > MAX_HISTORY:
        del history[0]
    append_log(
        state,
        f"{source} → [{question.skill}] d={question.difficulty} {question.text[:60]}...",
    )


def update_latest_history_entry(
    state: InterviewState, answer: Optional[str], grade: Optional[Grade]
) -> None:
    """Augment the most recent history entry with the candidate answer and grade."""
    history = state.setdefault("question_history", [])
    if not history:
        return
    entry = history[-1]
    entry["answer"] = answer
    if grade is not None:
        entry["score"] = grade.score
        entry["reasoning"] = grade.reasoning
        if getattr(grade, "aspects", None):
            entry["aspects"] = {
                name: {"score": detail.score, "notes": detail.notes}
                for name, detail in grade.aspects.items()
            }


def history_snippet(state: InterviewState, skill: str, limit: int = 3) -> str:
    """Summarise recent Q&A turns for a given skill."""
    entries = []
    for record in reversed(state.get("question_history", [])):
        if record.get("skill") != skill:
            continue
        if not record.get("answer"):
            continue
        answer = record.get("answer", "")
        if len(answer) > 140:
            answer = f"{answer[:137]}..."
        score = record.get("score")
        score_txt = f"score={score}" if score is not None else "score=?"
        entries.append(f"Q: {record.get('question')} | A: {answer} | {score_txt}")
        if len(entries) >= limit:
            break
    if not entries:
        return "None yet – this skill has not been answered."
    return "\n".join(reversed(entries))


SkillSummary = Dict[str, object]


def summarise_skills(state: InterviewState) -> List[SkillSummary]:
    """Build a per-skill summary for UI and telemetry."""
    verified = set(state.get("verified_skills", []))
    inactive = set(state.get("inactive_skills", []))
    summaries: List[Dict[str, object]] = []
    for skill in state.get("skills", []):
        belief = state.get("belief_state", {}).setdefault(skill, {})
        ensure_prior(belief)
        if "se" not in belief or "lcb" not in belief:
            compute_uncertainty(belief, state.get("z_value", 1.96), add_ucb=False)
        status = (
            "verified"
            if skill in verified
            else "inactive" if skill in inactive else "probing"
        )
        summaries.append(
            {
                "skill": skill,
                "status": status,
                "n": effective_sample_count(belief),
                "mean": round(float(belief.get("mean", 0.0)), 2),
                "se": round(float(belief.get("se", 0.0)), 3),
                "lcb": round(float(belief.get("lcb", 0.0)), 2),
            }
        )
    return summaries
