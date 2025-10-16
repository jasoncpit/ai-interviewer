"""LLM-backed seed question generation."""

from __future__ import annotations

from typing import Any, List

from app.agents.interviewer.prompts.generate import QUESTION_PROMPT
from app.agents.interviewer.utils.state import append_log, history_snippet
import app.core.llm as llm_module
from app.schema.models import InterviewState, Question


async def _draft_question(
    structured_llm: Any,
    skill: str,
    evidence: List[str],
    previous_question: str,
    previous_answer: str,
    previous_reasoning: str,
    recent_history: str,
) -> Question:
    """Invoke the LLM for a single skill."""
    question = await structured_llm.ainvoke(
        QUESTION_PROMPT.format(
            skill=skill,
            difficulty=3,
            last_score="N/A",
            evidence_spans="\n".join(evidence),
            previous_question=previous_question,
            previous_answer=previous_answer,
            previous_reasoning=previous_reasoning,
            recent_history=recent_history,
        )
    )
    # Some models omit the skill field when using structured output; enforce it.
    if getattr(question, "skill", None) != skill:
        try:
            question.skill = skill
        except Exception:
            pass
    return question


async def generate_questions_node(state: InterviewState) -> InterviewState:
    """Initialise a coarse question pool (one per skill) for quick fallbacks.

    Keeping a cached pool makes the planner resilient if a later LLM request
    fails or times out; the selector can reuse these baseline prompts.
    """
    spans_map = state.get("spans_map", {})
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
    # Import via module to keep patching straightforward in unit tests.
    llm = llm_module.get_llm()
    structured_llm = llm.with_structured_output(Question)
    questions: List[Question] = []
    for skill in state.get("skills", []):
        evidence = spans_map.get(skill, [])
        history_ctx = history_snippet(state, skill)
        try:
            questions.append(
                await _draft_question(
                    structured_llm,
                    skill,
                    evidence,
                    previous_question=prev_q,
                    previous_answer=prev_ans,
                    previous_reasoning=prev_reason,
                    recent_history=history_ctx,
                )
            )
        except Exception as exc:  # pragma: no cover - network dependent
            append_log(state, f"generate_questions → failed for {skill}: {exc}")
    state["question_pool"] = questions
    append_log(state, f"generate_questions → seeded {len(questions)} questions")
    return state
