from __future__ import annotations

import math
from typing import Dict

from app.agents.interviewer.prompts.grade import GRADE_PROMPT
from app.agents.interviewer.utils.state import append_log
import app.core.llm as llm_module
from app.schema.models import AspectBreakdown, Grade, GradeDraft, InterviewState


_ASPECT_WEIGHTS: Dict[str, float] = {
    "coverage": 1.0,
    "technical_depth": 1.2,
    "evidence": 1.0,
    "communication": 0.6,
}
_ASPECTS_ORDER = tuple(_ASPECT_WEIGHTS.keys())
_WEIGHT_DENOM = sum(_ASPECT_WEIGHTS.values())


def _round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


def _compute_final_score(
    draft: GradeDraft, aspects: Dict[str, AspectBreakdown]
) -> int:
    if draft.factual_error:
        return 1

    numerator = 0.0
    for aspect in _ASPECTS_ORDER:
        score = aspects.get(aspect, AspectBreakdown(score=1, notes="")).score
        weight = _ASPECT_WEIGHTS.get(aspect, 0.0)
        numerator += weight * score

    weighted_average = numerator / _WEIGHT_DENOM if _WEIGHT_DENOM else 1.0
    final_score = _round_half_up(weighted_average)
    final_score = max(1, min(5, final_score))

    if any(
        aspects.get(aspect, AspectBreakdown(score=1, notes="")).score <= 2
        for aspect in _ASPECTS_ORDER
    ):
        final_score = min(final_score, 2)

    return final_score


async def grade_node(state: InterviewState) -> InterviewState:
    """Call the grading LLM on the latest answer."""
    question = state["current_question"]
    assert question is not None
    answer = state.get("pending_answer") or ""

    llm = llm_module.get_llm()
    structured_llm = llm.with_structured_output(GradeDraft)
    draft = await structured_llm.ainvoke(
        GRADE_PROMPT.format(
            skill=question.skill,
            difficulty=question.difficulty,
            question=question.text,
            response=answer,
        )
    )

    aspect_map: Dict[str, AspectBreakdown] = {
        "coverage": draft.coverage,
        "technical_depth": draft.technical_depth,
        "evidence": draft.evidence,
        "communication": draft.communication,
    }

    if draft.factual_error:
        for name, detail in list(aspect_map.items()):
            note = detail.notes
            if note:
                note = f"{note} (factual error override)"
            else:
                note = "Factual error override."
            aspect_map[name] = AspectBreakdown(score=1, notes=note)

    final_score = _compute_final_score(draft, aspect_map)

    grade = Grade(score=final_score, reasoning=draft.reasoning, aspects=aspect_map)

    state["last_grade"] = grade
    state["last_answer"] = answer
    state["pending_answer"] = None
    append_log(state, f"grade → {grade.score} ({grade.reasoning})")
    if getattr(grade, "aspects", None):
        aspect_bits = ", ".join(
            f"{name}:{detail.score}"
            for name, detail in grade.aspects.items()
        )
        if aspect_bits:
            append_log(state, f"grade_aspects → {aspect_bits}")
    return state
