from __future__ import annotations

import json
import os
import urllib.parse
import uuid
from typing import Optional

import streamlit as st
from dotenv import load_dotenv

from app.client.client import AgentClient


def init_session_state():
    """Initialize session state variables"""
    if "chat" not in st.session_state:
        st.session_state["chat"] = []  # list of {role, content}
    if "skill_summaries" not in st.session_state:
        st.session_state["skill_summaries"] = []
    if "verified_skills" not in st.session_state:
        st.session_state["verified_skills"] = []
    if "agent_logs" not in st.session_state:
        st.session_state["agent_logs"] = []
    if "session_started" not in st.session_state:
        st.session_state["session_started"] = False


def handle_stream_event(event: str, data: str, log=None) -> Optional[str]:
    """Process a single SSE event. Returns a control token when the caller should pause."""

    try:
        payload = json.loads(data) if data else {}
    except json.JSONDecodeError:
        payload = {}

    if event == "message" and isinstance(payload, dict):
        if payload.get("type") == "question":
            st.session_state["current_question"] = payload
            st.session_state["chat"].append(
                {"role": "assistant", "content": payload.get("text")}
            )
        elif payload.get("type") == "grade":
            aspects = payload.get("aspects") or {}
            aspect_bits = ", ".join(
                f"{name}: {details.get('score')}"
                for name, details in aspects.items()
                if isinstance(details, dict) and "score" in details
            )
            detail_suffix = f" | {aspect_bits}" if aspect_bits else ""
            text = f"Grade: {payload.get('score')} — {payload.get('reason', '')}{detail_suffix}"
            st.session_state["chat"].append({"role": "assistant", "content": text})
        return None

    if event == "state":
        if isinstance(payload, dict) and payload:
            st.session_state["skill_summaries"] = payload.get(
                "skill_summaries",
                st.session_state.get("skill_summaries", []),
            )
            logs = payload.get("logs")
            if logs:
                st.session_state["agent_logs"] = logs
            if log:
                log.write(json.dumps(payload, indent=2))
        elif log and data:
            log.write(data)
        return None

    if event == "interrupt":
        st.session_state["awaiting_answer"] = True
        return "interrupt"

    if event == "done":
        return handle_done_event(payload)

    return None


def handle_done_event(payload: Optional[dict]) -> str:
    """Process a `done` SSE event and return a control token."""

    payload = payload or {}

    if payload.get("error") == "remote_protocol_error":
        st.warning("Stream ended unexpectedly. Please try again.")
        st.session_state["session_started"] = False
        return "done"

    if payload.get("status") == "awaiting_answer":
        st.session_state["awaiting_answer"] = True
        st.session_state["session_started"] = True
        return "interrupt"

    st.session_state["awaiting_answer"] = False
    st.session_state["session_started"] = False
    st.session_state["skill_summaries"] = payload.get("skill_summaries", [])
    st.session_state["verified_skills"] = payload.get("verified", [])
    if payload:
        verified = ", ".join(payload.get("verified", [])) or "None"
        inactive = ", ".join(payload.get("inactive", [])) or "None"
        summary = f"Session complete. Verified: {verified}. Inactive: {inactive}."
        st.session_state["chat"].append({"role": "assistant", "content": summary})
    st.balloons()
    return "done"

SIMULATION_PERSONA_DEFAULT = (
    "You are a data analyst who works primarily with pandas, SQL, and data visualization tools. "
    "You have limited knowledge of deep learning frameworks like PyTorch. Answer honestly about "
    "your data analysis experience while acknowledging gaps in ML engineering knowledge. "
    "Provide 4-6 sentences with practical examples from your analytics work."
)


def render_skill_status() -> None:
    """Render the skill verification status table"""
    summaries = st.session_state.get("skill_summaries") or []
    if not summaries:
        return
    st.subheader("Verification Status")
    st.dataframe(summaries, hide_index=True, use_container_width=True)


def get_share_url():
    """Generate shareable URL for the session"""
    try:
        session = st.runtime.get_instance()._session_mgr.list_active_sessions()[0]
        st_base_url = urllib.parse.urlunparse(
            [
                session.client.request.protocol,
                session.client.request.host,
                "",
                "",
                "",
                "",
            ]
        )
    except Exception:
        st_base_url = ""
    if (
        st_base_url
        and not st_base_url.startswith("https")
        and "localhost" not in st_base_url
    ):
        st_base_url = st_base_url.replace("http", "https")
    return f"{st_base_url}?session_id={st.session_state.get('session_id', '')}"


# Initialize app
load_dotenv()
st.set_page_config(page_title="Prolific Interviewer", page_icon="🎤", layout="wide")

# Sidebar: settings, session controls, and verification status
with st.sidebar:
    st.header("Settings")
    default_service_url = os.getenv("AGENT_SERVICE_URL", "http://localhost:8080")
    base_url = st.text_input(
        "Agent Service URL",
        value=default_service_url,
        help="HTTP endpoint of the backend service that streams questions and grades.",
    )
    max_turns = st.number_input(
        "Max turns",
        min_value=1,
        max_value=20,
        value=8,
        help="Maximum number of question/answer cycles before the interview stops.",
    )
    min_q = st.number_input(
        "Min Q per skill",
        min_value=1,
        max_value=10,
        value=2,
        help="Minimum questions per skill before making a verify/continue decision.",
    )
    verify_lcb = st.number_input(
        "Verify LCB",
        min_value=0.0,
        max_value=5.0,
        value=3.75,
        step=0.05,
        help="Lower confidence bound threshold to mark a skill as verified. Higher = stricter.",
    )
    z_value = st.number_input(
        "Z value",
        min_value=0.0,
        max_value=5.0,
        value=1.69,
        step=0.01,
        help="Z-score used for confidence intervals when estimating skill proficiency.",
    )
    ucb_C = st.number_input(
        "UCB C",
        min_value=0.0,
        max_value=5.0,
        value=2.0,
        step=0.1,
        help="Exploration coefficient for UCB selection (higher explores more).",
    )

    st.divider()
    st.subheader("Session")
    current_sid = st.text_input(
        "Session ID",
        value=st.session_state.get("session_id", ""),
        help="Use a fixed ID to resume the same interview later or share with others.",
    )
    if current_sid and current_sid != st.session_state.get("session_id"):
        st.session_state["session_id"] = current_sid
        st.query_params["session_id"] = current_sid

    c1, c2 = st.columns(2)
    with c1:
        if st.button("New session", key="sidebar_new_session"):
            new_sid = f"session-{uuid.uuid4()}"
            st.session_state["session_id"] = new_sid
            st.query_params["session_id"] = new_sid
            st.session_state["chat"] = []
            st.session_state.pop("awaiting_answer", None)
            st.session_state.pop("current_question", None)
            st.session_state["session_started"] = False
            st.rerun()
    with c2:
        if st.button(
            "Continue",
            key="sidebar_continue",
            help="If the interview is waiting for your answer, continue after submitting it.",
        ):
            try:
                client = AgentClient(base_url=base_url)
                payload = {
                    "profile": json.loads(st.session_state.get("profile_json", "{}")),
                    "max_turns": max_turns,
                    "min_q": min_q,
                    "verify_lcb": verify_lcb,
                    "z_value": z_value,
                    "ucb_C": ucb_C,
                }
                sid = st.session_state.get("session_id")
                if sid:
                    for evt in client.stream(payload, session_id=sid):
                        signal = handle_stream_event(evt.get("event"), evt.get("data"))
                        if signal:
                            break
                else:
                    st.warning("No session to continue. Start a session first.")
            except Exception:
                st.error("Could not reach the service to continue the session.")
            st.rerun()

    share_url = get_share_url()
    st.caption("Share/resume link")
    st.code(share_url or "(set a session first)", language="text")

    st.divider()
    # Simple service health check
    if st.button("Service health"):
        try:
            client = AgentClient(base_url=base_url)
            info = client.info()
            st.success(
                f"OK: {info.get('app', 'service')} - models: {', '.join(info.get('models', []))}"
            )
        except Exception as exc:
            st.error(f"Service unreachable: {exc}")
    render_skill_status()
    with st.expander("Agent Logs", expanded=False):
        logs = st.session_state.get("agent_logs", [])
        if logs:
            st.code("\n".join(logs[-200:]), language="text")
        else:
            st.caption("No logs yet. Run an interview to see logs.")

    st.divider()
    st.subheader("Simulation")
    sim_persona_input = st.text_area(
        "Persona prompt",
        value=st.session_state.get("simulation_persona", SIMULATION_PERSONA_DEFAULT),
        height=140,
        help="Used when auto-generating candidate answers via the simulation button.",
    )
    st.session_state["simulation_persona"] = sim_persona_input

st.title("Prolific AI Interviewer")
init_session_state()

# Handle session ID from query params
qp_sid = st.query_params.get("session_id")
if qp_sid and not st.session_state.get("session_id"):
    st.session_state["session_id"] = qp_sid

# Sample profiles
default_profile = {
    "ID": "123",
    "NAME": "Candidate",
    "SKILLS": [
        {
            "taxonomy_id": "ML/Frameworks/PyTorch",
            "evidence_sources": [
                {"source": "cv", "span": "Built CV pipeline with PyTorch Lightning."}
            ],
        },
        {
            "taxonomy_id": "Data Science/Frameworks/Pandas",
            "evidence_sources": [
                {"source": "cv", "span": "ETL pipelines using Pandas."}
            ],
        },
    ],
}

profiles = {
    "Sample: ML/PyTorch": default_profile,
    "Sample: Data Engineering": {
        "ID": "456",
        "NAME": "Data Engineer",
        "SKILLS": [
            {
                "taxonomy_id": "Data Engineering/Frameworks/Airflow",
                "evidence_sources": [
                    {"source": "cv", "span": "Built DAGs for batch ETL with Airflow."}
                ],
            },
            {
                "taxonomy_id": "Data Engineering/Storage/Redshift",
                "evidence_sources": [
                    {"source": "cv", "span": "Modeled star schemas in Redshift."}
                ],
            },
        ],
    },
    "Sample: Frontend": {
        "ID": "789",
        "NAME": "Frontend Dev",
        "SKILLS": [
            {
                "taxonomy_id": "Frontend/Frameworks/React",
                "evidence_sources": [
                    {"source": "cv", "span": "Built SPA with React and TypeScript."}
                ],
            },
            {
                "taxonomy_id": "Frontend/Styling/TailwindCSS",
                "evidence_sources": [
                    {"source": "cv", "span": "Implemented design system with Tailwind."}
                ],
            },
        ],
    },
}

# Ensure the editor has an initial value on first load
if "profile_json" not in st.session_state:
    st.session_state["profile_json"] = json.dumps(default_profile, indent=2)

# Profile selection
profile_options = list(profiles.keys()) + ["Custom"]
selected_profile = st.selectbox(
    "Choose a profile",
    options=profile_options,
    index=0,
    key="selected_profile",
    help="Pick a starter profile. Choose 'Custom' to freely edit the JSON below.",
)

# Sync the selection with the JSON editor. We only overwrite when a sample is chosen.
if selected_profile != "Custom":
    st.session_state["profile_json"] = json.dumps(profiles[selected_profile], indent=2)

profile_json = st.text_area(
    "Profile JSON",
    height=240,
    key="profile_json",
    help="This is the candidate profile sent to the agent. Edit to customize.",
)

try:
    profile_data = json.loads(profile_json)
except json.JSONDecodeError as exc:
    st.error(f"Profile JSON is invalid: {exc}")
    st.stop()

base_payload = {
    "profile": profile_data,
    "max_turns": max_turns,
    "min_q": min_q,
    "verify_lcb": verify_lcb,
    "z_value": z_value,
    "ucb_C": ucb_C,
}
resume_payload_base = {"profile": profile_data}
simulation_persona = st.session_state.get(
    "simulation_persona", SIMULATION_PERSONA_DEFAULT
)

# Auto-resume: if a session id is provided via URL and the chat is empty, re-emit the pending question
if (
    st.session_state.get("session_id")
    and not st.session_state.get("auto_resumed")
    and not st.session_state.get("chat")
):
    try:
        client = AgentClient(base_url=base_url)
        payload = dict(base_payload)
        session_id = st.session_state.get("session_id")
        for evt in client.stream(payload, session_id=session_id):
            signal = handle_stream_event(evt.get("event"), evt.get("data"))
            if signal:
                break
        st.session_state["auto_resumed"] = True
        st.rerun()
    except Exception:
        st.session_state["auto_resumed"] = True

chat_history = st.session_state.get("chat", [])
if chat_history:
    st.divider()
    for entry in chat_history:
        role = entry.get("role", "assistant")
        content = entry.get("content", "")
        if not content:
            continue
        with st.chat_message(role):
            st.markdown(content)

show_start_button = not st.session_state.get("session_started")
if show_start_button:
    if st.button(
        "Start Interview",
        disabled=bool(st.session_state.get("awaiting_answer")),
        type="primary",
    ):
        st.session_state["session_started"] = True
        client = AgentClient(base_url=base_url)
        payload = dict(base_payload)
        session_id = st.session_state.get("session_id") or f"session-{uuid.uuid4()}"
        st.session_state["session_id"] = session_id

        try:
            for evt in client.stream(payload, session_id=session_id):
                signal = handle_stream_event(evt.get("event"), evt.get("data"))
                if signal in {"interrupt", "done"}:
                    break
        except Exception:
            st.error("Streaming error. Please check the service and try again.")
        st.rerun()
else:
    st.caption("Interview in progress. Respond to the current question or use the sidebar to resume/end.")

# Handle answer input
if st.session_state.get("awaiting_answer"):
    st.divider()
    answer = st.chat_input("Your answer")
    simulate = st.checkbox(
        "Simulate answer",
        value=False,
        help="When checked, the app will auto-generate an answer using the backend and submit it.",
    )
    if answer:
        st.session_state["chat"].append({"role": "user", "content": answer})
        client = AgentClient(base_url=base_url)
        payload = {**resume_payload_base, "answer": answer}
        session_id = st.session_state.get("session_id") or f"session-{uuid.uuid4()}"
        st.session_state["session_id"] = session_id
        try:
            for evt in client.resume(payload, session_id=session_id):
                signal = handle_stream_event(evt.get("event"), evt.get("data"))
                if signal in {"interrupt", "done"}:
                    break
        except Exception:
            st.error("Streaming error. Please check the service and try again.")
        st.rerun()

    # Optional: auto-generate an answer when simulate is checked
    if simulate and st.session_state.get("awaiting_answer"):
        question = st.session_state.get("current_question") or {}
        try:
            client = AgentClient(base_url=base_url)
            session_id = st.session_state.get("session_id") or f"session-{uuid.uuid4()}"
            st.session_state["session_id"] = session_id
            sim = client.simulate_answer(
                {
                    "question": question.get("text", ""),
                    "skill": question.get("skill", "unknown"),
                    "persona": simulation_persona,
                    "history": [
                        f"{m['role']}: {m['content']}"
                        for m in st.session_state.get("chat", [])[-6:]
                    ],
                },
                session_id=session_id,
            )
            sim_answer = sim.get("answer", "").strip()
        except Exception as exc:
            st.error(f"Simulation error: {exc}")
            sim_answer = ""
        if sim_answer:
            st.session_state["chat"].append({"role": "user", "content": sim_answer})
            client = AgentClient(base_url=base_url)
            payload = {**resume_payload_base, "answer": sim_answer}
            session_id = st.session_state.get("session_id") or f"session-{uuid.uuid4()}"
            st.session_state["session_id"] = session_id
            try:
                for evt in client.resume(payload, session_id=session_id):
                    signal = handle_stream_event(evt.get("event"), evt.get("data"))
                    if signal in {"interrupt", "done"}:
                        break
            except Exception:
                st.error("Streaming error. Please check the service and try again.")
            st.rerun()
