from __future__ import annotations

import json
from typing import Any, Dict, Optional

from sqlalchemy import Column, MetaData, Table, Text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.schema.models import Grade, Question

from .db import get_engine

_metadata = MetaData()
_sessions = Table(
    "sessions",
    _metadata,
    Column("id", Text, primary_key=True),
    Column("state", Text, nullable=False),
)


def _ensure_tables(engine: Engine) -> None:
    _metadata.create_all(engine, checkfirst=True)


_memory_store: Dict[str, Dict[str, Any]] = {}


def load_state(session_id: str) -> Optional[Dict[str, Any]]:
    try:
        engine = get_engine()
        _ensure_tables(engine)
        with engine.begin() as conn:
            res = conn.execute(
                _sessions.select().where(_sessions.c.id == session_id)
            ).first()
            if not res:
                # fall back to memory if present
                raw = _memory_store.get(session_id)
                return _deserialize_state(raw) if raw else None
            raw = json.loads(res._mapping["state"])  # type: ignore[attr-defined]
            return _deserialize_state(raw)
    except (SQLAlchemyError, Exception):  # pragma: no cover - env dependent
        raw = _memory_store.get(session_id)
        return _deserialize_state(raw) if raw else None


def save_state(session_id: str, state: Dict[str, Any]) -> None:
    payload_obj = _serialize_state(state)
    payload = json.dumps(payload_obj)
    _memory_store[session_id] = payload_obj
    try:
        engine = get_engine()
        _ensure_tables(engine)
        with engine.begin() as conn:
            existing = conn.execute(
                _sessions.select().where(_sessions.c.id == session_id)
            ).first()
            if existing:
                conn.execute(
                    _sessions.update()
                    .where(_sessions.c.id == session_id)
                    .values(state=payload)
                )
            else:
                conn.execute(_sessions.insert().values(id=session_id, state=payload))
    except (SQLAlchemyError, Exception):  # pragma: no cover - env dependent
        # memory fallback already updated
        pass


def _serialize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    def serialize_question(q: Any) -> Any:
        if isinstance(q, Question):
            return q.model_dump()
        return q

    def serialize_grade(g: Any) -> Any:
        if isinstance(g, Grade):
            return g.model_dump()
        return g

    s = dict(state)
    if "current_question" in s and s["current_question"] is not None:
        s["current_question"] = serialize_question(s["current_question"])
    if "question_pool" in s and isinstance(s["question_pool"], list):
        s["question_pool"] = [serialize_question(q) for q in s["question_pool"]]
    if "last_grade" in s and s["last_grade"] is not None:
        s["last_grade"] = serialize_grade(s["last_grade"])
    return s


def _deserialize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    def to_question(obj: Any) -> Any:
        if isinstance(obj, dict) and {"skill", "text", "difficulty"}.issubset(
            obj.keys()
        ):
            try:
                return Question(**obj)
            except Exception:
                return obj
        return obj

    def to_grade(obj: Any) -> Any:
        if isinstance(obj, dict) and {"score", "reasoning"}.issubset(obj.keys()):
            try:
                return Grade(**obj)
            except Exception:
                return obj
        return obj

    s = dict(state)
    if "current_question" in s and s["current_question"] is not None:
        s["current_question"] = to_question(s["current_question"])
    if "question_pool" in s and isinstance(s["question_pool"], list):
        s["question_pool"] = [to_question(q) for q in s["question_pool"]]
    if "last_grade" in s and s["last_grade"] is not None:
        s["last_grade"] = to_grade(s["last_grade"])
    return s
