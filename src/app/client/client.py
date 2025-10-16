from __future__ import annotations

import os
from typing import Any, Dict, Iterator, Optional

import httpx


class AgentClient:
    def __init__(
        self, base_url: str = "http://localhost:8080", api_key: str | None = None
    ):
        self.base_url = base_url.rstrip("/")
        # Prefer explicit, else read from common env var names
        self.api_key = (
            api_key
            or os.getenv("API_KEY")
            or os.getenv("SERVICE_API_KEY")
            or os.getenv("AGENT_SERVICE_API_KEY")
        )

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream, application/json;q=0.9",
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def info(self) -> Dict[str, Any]:
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{self.base_url}/info", headers=self._headers())
            r.raise_for_status()
            return r.json()

    def invoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with httpx.Client(timeout=60) as client:
            r = client.post(
                f"{self.base_url}/interviewer/invoke",
                json=payload,
                headers=self._headers(),
            )
            r.raise_for_status()
            return r.json()

    def stream(
        self, payload: Dict[str, Any], session_id: Optional[str] = None
    ) -> Iterator[Dict[str, Any]]:
        headers = self._headers()
        if session_id:
            # FastAPI converts underscores to hyphens in header names
            headers["session-id"] = session_id
        try:
            with httpx.Client(
                timeout=httpx.Timeout(None, read=None, connect=10)
            ) as client:
                with client.stream(
                    "POST",
                    f"{self.base_url}/interviewer/stream",
                    json=payload,
                    headers=headers,
                ) as r:
                    r.raise_for_status()
                    event = None
                    data_parts = []
                    for raw in r.iter_lines():
                        if raw is None:
                            continue
                        if isinstance(raw, bytes):
                            line = raw.decode("utf-8", errors="ignore")
                        else:
                            line = raw
                        if line.startswith(":"):
                            # comment/heartbeat
                            continue
                        if line.startswith("event:"):
                            event = line.split(":", 1)[1].strip()
                        elif line.startswith("data:"):
                            data_parts.append(line.split(":", 1)[1].strip())
                        elif line == "":
                            if event is not None:
                                data = "\n".join(data_parts) if data_parts else "{}"
                                yield {"event": event, "data": data}
                            event = None
                            data_parts = []
        except httpx.RemoteProtocolError:
            # Surface a final done event so UI can recover
            yield {"event": "done", "data": '{"error":"remote_protocol_error"}'}

    def resume(
        self, payload: Dict[str, Any], session_id: Optional[str] = None
    ) -> Iterator[Dict[str, Any]]:
        if not session_id:
            raise ValueError("session_id is required to resume an interview")

        headers = self._headers()
        headers["session-id"] = session_id

        try:
            with httpx.Client(
                timeout=httpx.Timeout(None, read=None, connect=10)
            ) as client:
                with client.stream(
                    "POST",
                    f"{self.base_url}/interviewer/resume",
                    json=payload,
                    headers=headers,
                ) as r:
                    r.raise_for_status()
                    event = None
                    data_parts = []
                    for raw in r.iter_lines():
                        if raw is None:
                            continue
                        if isinstance(raw, bytes):
                            line = raw.decode("utf-8", errors="ignore")
                        else:
                            line = raw
                        if line.startswith(":"):
                            continue
                        if line.startswith("event:"):
                            event = line.split(":", 1)[1].strip()
                        elif line.startswith("data:"):
                            data_parts.append(line.split(":", 1)[1].strip())
                        elif line == "":
                            if event is not None:
                                data = "\n".join(data_parts) if data_parts else "{}"
                                yield {"event": event, "data": data}
                            event = None
                            data_parts = []
        except httpx.RemoteProtocolError:
            yield {"event": "done", "data": '{"error":"remote_protocol_error"}'}

    def simulate_answer(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = self._headers()
        with httpx.Client(timeout=60) as client:
            r = client.post(
                f"{self.base_url}/simulation/answer",
                json=payload,
                headers=headers,
            )
            r.raise_for_status()
            return r.json()
