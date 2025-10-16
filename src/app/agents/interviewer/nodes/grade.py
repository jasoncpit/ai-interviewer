from __future__ import annotations

from app.agents.interviewer.prompts.grade import GRADE_PROMPT
from app.agents.interviewer.utils.state import append_log
import app.core.llm as llm_module
from app.schema.models import Grade, InterviewState


async def grade_node(state: InterviewState) -> InterviewState:
    """Call the grading LLM on the latest answer."""
    question = state["current_question"]
    assert question is not None
    answer = state.get("pending_answer") or ""

    llm = llm_module.get_llm()
    structured_llm = llm.with_structured_output(Grade)
    grade = await structured_llm.ainvoke(
        GRADE_PROMPT.format(
            skill=question.skill,
            difficulty=question.difficulty,
            question=question.text,
            response=answer,
        )
    )

    state["last_grade"] = grade
    state["last_answer"] = answer
    state["pending_answer"] = None
    append_log(state, f"grade → {grade.score} ({grade.reasoning})")
    return state
