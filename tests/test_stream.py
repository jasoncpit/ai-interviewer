from __future__ import annotations

import asyncio
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for path in (SRC_ROOT, REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.append(path_str)

try:  # pragma: no cover - optional dependency guard
    from app.schema.models import AspectBreakdown, Grade, GradeDraft, Question  # noqa: E402
    from app.service.service import app  # noqa: E402
except ModuleNotFoundError as exc:  # pragma: no cover - skip when deps missing
    pytest.skip(f"backend dependencies not available: {exc}", allow_module_level=True)


class _StubStructuredLLM:
    def __init__(self, model_cls: type[Any]):
        self._model_cls = model_cls
        self._config = None

    async def ainvoke(self, prompt: Any) -> Any:
        text = ""
        if hasattr(prompt, "to_string"):
            text = prompt.to_string()
        else:
            text = str(prompt)

        if self._model_cls is Question:
            skill = _extract_skill(text) or "unknown"
            return Question(skill=skill, text=f"Tell me about {skill}.", difficulty=3)
        if self._model_cls is GradeDraft:
            return GradeDraft(
                reasoning="Stubbed evaluation.",
                coverage=AspectBreakdown(score=4, notes="Answered main question."),
                technical_depth=AspectBreakdown(
                    score=4, notes="Mentioned key APIs."
                ),
                evidence=AspectBreakdown(score=4, notes="Provided example."),
                communication=AspectBreakdown(score=4, notes="Clear response."),
            )
        return self._model_cls()

    def with_config(self, **kwargs):
        self._config = kwargs
        return self


class _StubLLM:
    def __init__(self):
        self._config = None

    def with_structured_output(self, model_cls: type[Any]) -> _StubStructuredLLM:
        return _StubStructuredLLM(model_cls)

    def with_config(self, **kwargs):
        self._config = kwargs
        return self

    async def ainvoke(self, prompt: Any) -> Any:
        return type("StubMessage", (), {"content": "stubbed"})()


def _extract_skill(text: str) -> str | None:
    match = re.search(r"assess (.+?)\.", text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def _collect_events(
    endpoint: str, payload: Dict[str, Any], session_id: str
) -> List[Tuple[str, Dict[str, Any]]]:
    headers = {"session-id": session_id}
    events: List[Tuple[str, Dict[str, Any]]] = []
    client = TestClient(app)

    response = client.post(endpoint, json=payload, headers=headers)
    response.raise_for_status()

    event = None
    data_parts: List[str] = []

    for line in response.iter_lines():
        if not line:
            if event:
                raw = "\n".join(data_parts) if data_parts else "{}"
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = {}
                events.append((event, parsed))
                if event == "done":
                    break
            event = None
            data_parts = []
            continue

        if isinstance(line, bytes):
            line = line.decode()
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_parts.append(line.split(":", 1)[1].strip())

    return events


def _exercise_stream() -> None:
    payload = {
        "profile": {
            "ID": "123",
            "NAME": "Candidate",
            "SKILLS": [
                {
                    "taxonomy_id": "ML/Frameworks/PyTorch",
                    "evidence_sources": [
                        {
                            "source": "cv",
                            "span": "Built CV pipeline with PyTorch Lightning.",
                        }
                    ],
                }
            ],
        },
        "max_turns": 3,
        "min_q": 1,
        "verify_lcb": 3.0,
        "z_value": 1.0,
        "ucb_C": 0.5,
    }
    session_id = f"session-{uuid.uuid4()}"

    with patch("app.core.llm.get_llm", return_value=_StubLLM()):
        first_pass = _collect_events("/interviewer/stream", payload, session_id)
        assert any(evt == "message" and body.get("type") == "question" for evt, body in first_pass)
        assert first_pass[-1][0] == "done"
        assert first_pass[-1][1].get("status") == "awaiting_answer"

        follow_up_payload = dict(payload, answer="Sure, here's my answer.")
        second_pass = _collect_events("/interviewer/resume", follow_up_payload, session_id)

    assert any(evt == "message" and body.get("type") == "grade" for evt, body in second_pass)
    status_payload = next((body for evt, body in second_pass if evt == "state"), {})
    assert "belief_state" in status_payload
    assert any(evt in {"interrupt", "done"} for evt, _ in second_pass)


def test_stream_round_trip() -> None:
    _exercise_stream()
