from __future__ import annotations

import asyncio

from app.agents.interviewer.nodes.generate import generate_questions_node
from app.agents.interviewer.nodes.grade import grade_node
from app.agents.interviewer.nodes.select import select_question_node
from app.agents.interviewer.utils.stats import ensure_prior
from app.schema.models import AspectBreakdown, Grade, GradeDraft, Question


class _StubStructuredLLM:
    def __init__(self, result):
        self._result = result

    async def ainvoke(self, prompt):
        return self._result


class _StubLLM:
    def __init__(self, result):
        self._result = result

    def with_structured_output(self, model_cls):
        return _StubStructuredLLM(self._result)


def test_generate_questions_node_seeds_question(monkeypatch):
    question = Question(skill="python", text="Describe your Python project.", difficulty=3)
    monkeypatch.setattr("app.core.llm.get_llm", lambda: _StubLLM(question))

    state = {
        "skills": ["python"],
        "question_pool": [],
        "current_question": None,
        "last_grade": None,
        "last_answer": "",
        "spans_map": {"python": ["Built ETL in Python."]},
        "question_history": [],
        "logs": [],
    }

    updated = asyncio.run(generate_questions_node(state))

    assert len(updated["question_pool"]) == 1
    seeded = updated["question_pool"][0]
    assert seeded.skill == "python"
    assert "Describe your Python project" in seeded.text
    assert "generate_questions" in updated["logs"][-1]


def test_grade_node_persists_grade(monkeypatch):
    draft = GradeDraft(
        reasoning="Excellent depth.",
        coverage=AspectBreakdown(score=5, notes="Explained context managers."),
        technical_depth=AspectBreakdown(score=5, notes="Detailed __enter__/__exit__."),
        evidence=AspectBreakdown(score=5, notes="Mentioned cleanup semantics."),
        communication=AspectBreakdown(score=4, notes="Clear and structured."),
    )
    monkeypatch.setattr("app.core.llm.get_llm", lambda: _StubLLM(draft))

    state = {
        "current_question": Question(skill="python", text="Explain context managers.", difficulty=3),
        "pending_answer": "They ensure deterministic cleanup via __enter__/__exit__.",
        "last_answer": None,
        "logs": [],
    }

    updated = asyncio.run(grade_node(state))

    assert updated["last_grade"].score == 5
    assert updated["last_answer"].startswith("They ensure")
    assert updated["pending_answer"] is None
    assert any(entry.startswith("grade → 5") for entry in updated["logs"])


def test_grade_node_caps_on_factual_error(monkeypatch):
    draft = GradeDraft(
        reasoning="Incorrect claim about context managers.",
        factual_error=True,
        coverage=AspectBreakdown(score=4, notes="Addressed the prompt."),
        technical_depth=AspectBreakdown(score=4, notes="Named __enter__/__exit__."),
        evidence=AspectBreakdown(score=4, notes="Provided example."),
        communication=AspectBreakdown(score=4, notes="Clear explanation."),
    )
    monkeypatch.setattr("app.core.llm.get_llm", lambda: _StubLLM(draft))

    state = {
        "current_question": Question(skill="python", text="Explain context managers.", difficulty=3),
        "pending_answer": "They run __init__ after __enter__.",
        "last_answer": None,
        "logs": [],
    }

    updated = asyncio.run(grade_node(state))

    assert updated["last_grade"].score == 1
    for detail in updated["last_grade"].aspects.values():
        assert detail.score == 1
        assert "override" in detail.notes.lower()


def test_select_question_node_prefers_pool(monkeypatch):
    q_from_pool = Question(skill="python", text="Tell me about async IO.", difficulty=3)
    belief = {}
    ensure_prior(belief)

    state = {
        "skills": ["python"],
        "belief_state": {"python": belief},
        "question_pool": [q_from_pool],
        "inactive_skills": [],
        "verified_skills": [],
        "ucb_C": 0.5,
        "logs": [],
        "question_history": [],
        "spans_map": {"python": []},
        "last_grade": None,
        "current_question": None,
        "last_answer": "",
        "turn": 0,
    }

    updated = asyncio.run(select_question_node(state))

    assert updated["current_question"].text == "Tell me about async IO."
    assert updated["question_pool"] == []
    assert updated["question_history"][-1]["source"] == "select_question"


def test_select_question_node_calls_llm_when_pool_empty(monkeypatch):
    generated = Question(skill="python", text="Walk me through type hints.", difficulty=3)
    monkeypatch.setattr("app.core.llm.get_llm", lambda: _StubLLM(generated))

    belief = {}
    ensure_prior(belief)

    state = {
        "skills": ["python"],
        "belief_state": {"python": belief},
        "question_pool": [],
        "inactive_skills": [],
        "verified_skills": [],
        "ucb_C": 0.5,
        "logs": [],
        "question_history": [],
        "spans_map": {"python": ["Authored internal typing guide."]},
        "last_grade": None,
        "current_question": None,
        "last_answer": "",
        "turn": 0,
    }

    updated = asyncio.run(select_question_node(state))

    assert updated["current_question"].text == "Walk me through type hints."
    assert updated["question_history"][-1]["skill"] == "python"
