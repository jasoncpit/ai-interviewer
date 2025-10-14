from __future__ import annotations

import uuid
from typing import Dict


def ensure_session_id(headers: Dict[str, str]) -> str:
    """Return an existing session id header or create a new one."""
    session_id = headers.get("session-id") or headers.get("Session-Id")
    if session_id:
        return session_id
    return f"session-{uuid.uuid4()}"
