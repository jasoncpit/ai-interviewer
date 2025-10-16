from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Dict

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, StreamingResponse

from app.agents.interviewer.graph import build_state
from app.agents.interviewer.nodes.ask import ask_node
from app.agents.interviewer.nodes.decide import decide_node
from app.agents.interviewer.nodes.generate import generate_questions_node
from app.agents.interviewer.nodes.grade import grade_node
from app.agents.interviewer.nodes.select import select_question_node
from app.agents.interviewer.nodes.update import update_node
from app.agents.interviewer.utils.state import summarise_skills
from app.service.utils.profile import (
    build_spans_map_from_profile,
    derive_skills_from_profile,
)

from ..core.config import get_settings
from ..core.llm import get_llm
from ..schema.models import (
    InterviewState,
    InvokeRequest,
    InvokeResponse,
    SimulateAnswerRequest,
    SimulateAnswerResponse,
)
from ..storage.store import load_state, save_state

settings = get_settings()

app = FastAPI(title=settings.app_name)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_api_key(x_api_key: str | None) -> None:
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


def _encode_event(event: str, payload: Dict[str, Any]) -> bytes:
    """Serialise an SSE event in the expected ``event: ...`` format."""
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n".encode()


def _load_or_init_state(
    request: InvokeRequest, session_id: str | None
) -> InterviewState:
    """Reuse an existing interview state or bootstrap a brand new ledger."""
    if session_id and (existing := load_state(session_id)):
        existing.setdefault("skill_summaries", summarise_skills(existing))
        return existing
    skills = derive_skills_from_profile(request.profile)
    spans_map = build_spans_map_from_profile(request.profile)
    state = build_state(
        skills,
        request.max_turns,
        request.min_q,
        request.verify_lcb,
        request.z_value,
        request.ucb_C,
        spans_map,
    )
    state["skill_summaries"] = summarise_skills(state)
    return state


def _persist_state(session_id: str | None, state: InterviewState) -> None:
    """Persist state for resumable runs when a session id is provided."""
    if session_id:
        save_state(session_id, state)


@app.get("/info")
async def info() -> Dict[str, Any]:
    return {
        "app": settings.app_name,
        "agents": ["interviewer"],
        "models": [settings.openai_model],
        "streaming": "sse",
    }


@app.post("/interviewer/invoke")
async def invoke(
    request: InvokeRequest,
    x_api_key: str | None = Header(default=None),
    session_id: str | None = Header(default=None),
) -> JSONResponse:
    """Run a single synchronous interview turn (useful for smoke tests)."""
    verify_api_key(x_api_key)
    state = _load_or_init_state(request, session_id)

    state = await generate_questions_node(state)
    state = await select_question_node(state)
    state = ask_node(state)
    state["pending_answer"] = request.answer or ""
    state = await grade_node(state)
    state = update_node(state)

    _persist_state(session_id, state)
    return JSONResponse(InvokeResponse(state=state).model_dump())


@app.post("/interviewer/stream")
async def stream(
    request: InvokeRequest,
    x_api_key: str | None = Header(default=None),
    session_id: str | None = Header(default=None),
) -> StreamingResponse:
    """Kick off a turn and pause once the candidate must respond."""
    verify_api_key(x_api_key)

    async def event_gen() -> AsyncGenerator[bytes, None]:
        state = _load_or_init_state(request, session_id)

        # If interview is already finished per policy, end early
        cmd0 = decide_node(state)
        if cmd0.goto != "select":
            yield _encode_event(
                "done",
                {
                    "verified": state.get("verified_skills", []),
                    "inactive": state.get("inactive_skills", []),
                    "skill_summaries": state.get(
                        "skill_summaries", summarise_skills(state)
                    ),
                    "turn": state.get("turn", 0),
                    "logs": state.get("logs", [])[-10:],
                },
            )
            return

        # If there is already a current question awaiting answer, re-emit it instead of selecting a new one
        if (
            state.get("current_question") is not None
            and (state.get("pending_answer") in (None, ""))
            and (state.get("last_grade") is None or state.get("turn", 0) == 0)
        ):
            yield _encode_event(
                "message",
                {
                    "type": "question",
                    "skill": state["current_question"].skill,
                    "text": state["current_question"].text,
                },
            )
            state = ask_node(state)
            yield b": keep-alive\n\n"
            yield _encode_event("interrupt", {"schema": {"answer": "string"}})
            _persist_state(session_id, state)
            yield _encode_event("done", {"status": "awaiting_answer"})
            return

        # Otherwise, start a new selection
        state = await generate_questions_node(state)
        yield _encode_event("node_end", {"node": "generate"})
        state = await select_question_node(state)
        # Emit the next question so the UI can display it to the interviewer/candidate.
        yield _encode_event(
            "message",
            {
                "type": "question",
                "skill": state["current_question"].skill,
                "text": state["current_question"].text,
            },
        )
        state = ask_node(state)
        yield b": keep-alive\n\n"
        yield _encode_event("interrupt", {"schema": {"answer": "string"}})
        _persist_state(session_id, state)
        yield _encode_event("done", {"status": "awaiting_answer"})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering when present
        },
    )


@app.post("/interviewer/resume")
async def resume(
    request: InvokeRequest,
    x_api_key: str | None = Header(default=None),
    session_id: str | None = Header(default=None),
) -> StreamingResponse:
    """Resume an interview once the operator submits the candidate's answer."""
    verify_api_key(x_api_key)

    async def event_gen() -> AsyncGenerator[bytes, None]:
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id header required")

        state = load_state(session_id)
        if not state:
            raise HTTPException(status_code=404, detail="session not found")

        if state.get("current_question") is None:
            raise HTTPException(
                status_code=409,
                detail="no pending question for this session",
            )

        state["pending_answer"] = request.answer or ""
        state = await grade_node(state)
        grade = state.get("last_grade")
        if grade is None:
            raise HTTPException(
                status_code=500, detail="grading failed to produce a score"
            )

        yield _encode_event(
            "message",
            {
                "type": "grade",
                "score": grade.score,
                "reason": grade.reasoning,
                "aspects": {
                    name: {"score": detail.score, "notes": detail.notes}
                    for name, detail in grade.aspects.items()
                },
            },
        )

        state = update_node(state)

        yield _encode_event(
            "state",
            {
                "belief_state": state.get("belief_state", {}),
                "skill_summaries": state.get(
                    "skill_summaries", summarise_skills(state)
                ),
                "logs": state.get("logs", [])[-50:],
            },
        )

        cmd = decide_node(state)
        done_payload: Dict[str, Any]

        if cmd.goto == "select":
            seeded = False
            if not state.get("question_pool"):
                state = await generate_questions_node(state)
                seeded = True

            if seeded:
                yield _encode_event("node_end", {"node": "generate"})
            state = await select_question_node(state)
            yield _encode_event(
                "message",
                {
                    "type": "question",
                    "skill": state["current_question"].skill,
                    "text": state["current_question"].text,
                },
            )
            state = ask_node(state)
            yield b": keep-alive\n\n"
            yield _encode_event("interrupt", {"schema": {"answer": "string"}})
            done_payload = {"status": "awaiting_answer"}
        else:
            done_payload = {
                "verified": state.get("verified_skills", []),
                "inactive": state.get("inactive_skills", []),
                "skill_summaries": state.get(
                    "skill_summaries", summarise_skills(state)
                ),
                "turn": state.get("turn", 0),
                "logs": state.get("logs", [])[-50:],
            }

        _persist_state(session_id, state)
        yield _encode_event("done", done_payload)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


DEFAULT_SIM_PERSONA = (
    "You are a cooperative candidate who answers honestly, highlighting strengths "
    "without bluffing. Provide 4-6 sentences with practical detail."
)


@app.post("/simulation/answer", response_model=SimulateAnswerResponse)
async def simulation_answer(
    request: SimulateAnswerRequest,
    x_api_key: str | None = Header(default=None),
) -> SimulateAnswerResponse:
    """Generate a mock candidate answer using the backend's LLM."""

    verify_api_key(x_api_key)

    persona = request.persona.strip() if request.persona else DEFAULT_SIM_PERSONA
    history_block = "\n".join(request.history) if request.history else ""
    prompt_parts = [
        persona,
        f"Skill: {request.skill}",
        f"Question: {request.question}",
    ]
    if history_block:
        prompt_parts.append("Recent context:")
        prompt_parts.append(history_block)
    prompt_parts.append(
        "Answer the question in 4-6 sentences. Be specific, mention trade-offs, "
        "and acknowledge uncertainty if you are unsure."
    )
    prompt = "\n".join(prompt_parts)

    llm = get_llm(temperature=0.4)
    try:
        message = await llm.ainvoke(prompt)
        answer = getattr(message, "content", str(message)).strip()
    except Exception:
        answer = (
            "I would outline the key steps, explain the reasoning behind them, and "
            "note any risks or assumptions before proceeding. (simulated fallback)"
        )

    if not answer:
        answer = (
            "I would start by explaining the core approach and highlight where I "
            "need clarification before moving forward. (simulated fallback)"
        )

    return SimulateAnswerResponse(answer=answer)
