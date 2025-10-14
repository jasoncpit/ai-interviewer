"""Pick the next skill + question to ask."""

from __future__ import annotations

from typing import Any, Optional

from app.agents.interviewer.prompts.generate import QUESTION_PROMPT
from app.agents.interviewer.utils.state import append_log, record_question
from app.agents.interviewer.utils.stats import select_skill_ucb_with_log
from app.core.llm import get_llm
from app.schema.models import InterviewState, Question


def _next_difficulty(last_score: Optional[int], baseline: int = 3) -> int:
    """Adjust difficulty based on the most recent score."""
    if last_score is None:
        return baseline
    if last_score >= 4:
        return min(5, baseline + 1)
    if last_score <= 2:
        return max(1, baseline - 1)
    return baseline


def _pop_existing_question(state: InterviewState, skill: str) -> Optional[Question]:
    pool = state.get("question_pool", [])
    for idx, question in enumerate(pool):
        if question.skill == skill:
            pool.pop(idx)
            return question
    return None


async def _draft_follow_up(
    structured_llm: Any,
    skill: str,
    difficulty: int,
    last_score: Optional[int],
    evidence: str,
    previous_question: str,
    previous_answer: str,
    previous_reasoning: str,
) -> Question:
    """Ask the LLM for the next best follow-up question."""
    question = await structured_llm.ainvoke(
        QUESTION_PROMPT.format(
            skill=skill,
            difficulty=difficulty,
            last_score=last_score if last_score is not None else "N/A",
            evidence_spans=evidence,
            previous_question=previous_question,
            previous_answer=previous_answer,
            previous_reasoning=previous_reasoning,
        )
    )
    if getattr(question, "skill", None) != skill:
        try:
            question.skill = skill
        except Exception:
            pass
    question.difficulty = difficulty
    return question


async def select_question_node(state: InterviewState) -> InterviewState:
    """Select the next skill via UCB and prepare the follow-up question."""
    last_score = (
        state["last_grade"].score
        if state.get("last_grade") and state.get("current_question")
        else None
    )
    # Prefer selecting among active skills only
    inactive = set(state.get("inactive_skills", []))
    active_beliefs = {
        k: v for k, v in state.get("belief_state", {}).items() if k not in inactive
    }
    pool = active_beliefs if active_beliefs else state.get("belief_state", {})
    skill, logs = select_skill_ucb_with_log(pool, state["turn"], state["ucb_C"])
    for entry in logs:
        append_log(state, f"select_ucb → {entry}")

    difficulty = _next_difficulty(last_score)

    # Prefer cached questions first; they give deterministic coverage and keep the flow moving
    # even if the LLM cannot be reached.
    candidate = _pop_existing_question(state, skill)
    source = "pool"
    if candidate and candidate.difficulty != difficulty:
        candidate.difficulty = difficulty

    if candidate is None:
        source = "llm"
        llm = get_llm()
        structured_llm = llm.with_structured_output(Question)
        evidence = "\n".join(state.get("spans_map", {}).get(skill, []))
        prev_q = (
            getattr(state.get("current_question"), "text", "")
            if state.get("current_question")
            else ""
        )
        prev_reason = (
            getattr(state.get("last_grade"), "reasoning", "")
            if state.get("last_grade")
            else ""
        )
        prev_ans = state.get("last_answer") or ""
        candidate = await _draft_follow_up(
            structured_llm,
            skill,
            difficulty,
            last_score,
            evidence,
            previous_question=prev_q,
            previous_answer=prev_ans,
            previous_reasoning=prev_reason,
        )

    record_question(state, candidate, "select_question")
    append_log(state, f"select_question → source={source}")
    return state
