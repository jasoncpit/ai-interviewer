from __future__ import annotations

from typing import Dict, List

from langgraph.graph import START, StateGraph
from langgraph.types import Command

from app.agents.interviewer.nodes.ask import ask_node
from app.agents.interviewer.nodes.decide import decide_node
from app.agents.interviewer.nodes.generate import generate_questions_node
from app.agents.interviewer.nodes.grade import grade_node
from app.agents.interviewer.nodes.select import select_question_node
from app.agents.interviewer.nodes.update import update_node
from app.agents.interviewer.utils.state import append_log, summarise_skills
from app.schema.models import InterviewState


def _initial_belief(skills: List[str]) -> Dict[str, Dict[str, float]]:
    return {
        skill: {"mean": 2.5, "n": 0, "m2": 0.0, "se": 0.0, "lcb": 2.5}
        for skill in skills
    }


def build_state(
    skills: List[str],
    max_turns: int,
    min_q: int,
    verify_lcb: float,
    z_value: float,
    ucb_C: float,
    spans_map: Dict[str, List[str]],
) -> InterviewState:
    state: InterviewState = {
        "skills": skills,
        "belief_state": _initial_belief(skills),
        "question_pool": [],
        "current_question": None,
        "last_grade": None,
        "last_answer": None,  # type: ignore[typeddict-item]
        "pending_answer": None,  # type: ignore[typeddict-item]
        "spans_map": spans_map,
        "turn": 0,
        "max_turns": max_turns,
        "min_questions_per_skill": min_q,
        "verification_threshold": verify_lcb,
        "z_value": z_value,
        "ucb_C": ucb_C,
        "inactive_skills": [],
        "verified_skills": [],
        "logs": [],
        "skill_summaries": [],
    }
    append_log(
        state,
        f"init → skills={skills}, max_turns={max_turns}, threshold={verify_lcb}, z={z_value}, C={ucb_C}",
    )
    state["skill_summaries"] = summarise_skills(state)
    return state  # type: ignore[return-value]


def build_graph():
    g = StateGraph(InterviewState)
    g.add_node("generate", generate_questions_node)
    g.add_node("select", select_question_node)
    g.add_node("ask", ask_node)
    g.add_node("grade", grade_node)
    g.add_node("update", update_node)

    def route(state: InterviewState) -> Command:
        return decide_node(state)

    g.add_edge(START, "generate")
    g.add_edge("generate", "select")
    g.add_edge("select", "ask")
    g.add_edge("grade", "update")
    g.add_conditional_edges("update", route)

    return g.compile()
