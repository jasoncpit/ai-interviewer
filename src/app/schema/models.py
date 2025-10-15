from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from pydantic import BaseModel, Field


class Question(BaseModel):
    skill: str = Field(description="Canonical skill this question targets.")
    text: str = Field(min_length=5, description="The question content.")
    difficulty: int = Field(ge=1, le=5, description="1=easiest … 5=hardest")


class Grade(BaseModel):
    score: int = Field(ge=1, le=5, description="Rubric score 1..5")
    reasoning: str = Field(default="simulated")


class InterviewState(TypedDict):
    skills: List[str]
    belief_state: Dict[str, Dict]
    question_pool: List[Question]
    current_question: Optional[Question]
    last_grade: Optional[Grade]
    last_answer: Optional[str]
    pending_answer: Optional[str]
    spans_map: Dict[str, List[str]]
    turn: int
    max_turns: int
    min_questions_per_skill: int
    verification_threshold: float
    z_value: float
    ucb_C: float
    inactive_skills: List[str]
    verified_skills: List[str]
    logs: List[str]
    skill_summaries: List[Dict[str, object]]
    question_history: List[Dict[str, object]]


class InvokeRequest(BaseModel):
    profile: Dict[str, Any]
    max_turns: int = 8
    min_q: int = 2
    verify_lcb: float = 3.75
    z_value: float = 1.96
    ucb_C: float = 1.0
    answer: Optional[str] = None


class InvokeResponse(BaseModel):
    state: Dict[str, Any]


class SimulateAnswerRequest(BaseModel):
    question: str = Field(min_length=5)
    skill: str = Field(min_length=1)
    persona: Optional[str] = Field(
        default=None,
        description="Optional persona or tone instructions for the simulated candidate.",
    )
    history: List[str] = Field(
        default_factory=list,
        description="Recent conversation snippets to preserve context.",
    )


class SimulateAnswerResponse(BaseModel):
    answer: str = Field(min_length=1)
