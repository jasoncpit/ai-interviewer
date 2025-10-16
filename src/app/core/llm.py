from __future__ import annotations

import os
from typing import Any, Optional

try:  # langchain_openai is an optional dependency in some environments
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover - exercised only when dependency missing
    ChatOpenAI = None  # type: ignore[assignment]

from .config import get_settings


class _NoOpLLM:
    """Minimal stand-in so tests can patch over LLM usage."""

    def with_structured_output(self, model_cls: type[Any]) -> "_NoOpLLM":
        return self

    async def ainvoke(self, prompt: Any) -> Any:  # pragma: no cover - fallback only
        raise RuntimeError(
            "LLM support is not configured. Provide OPENAI_API_KEY or patch get_llm."
        )


def _resolve_api_key() -> Optional[str]:
    settings = get_settings()
    if settings.openai_api_key:
        if not os.getenv("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key
        return settings.openai_api_key
    return os.getenv("OPENAI_API_KEY")


def get_llm(temperature: Optional[float] = None, model: Optional[str] = None) -> Any:
    settings = get_settings()
    api_key = _resolve_api_key()

    if api_key is None:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured. Set it in the environment or .env."
        )

    if ChatOpenAI is None:
        return _NoOpLLM()

    kwargs: dict[str, Any] = {}
    kwargs["api_key"] = api_key

    return ChatOpenAI(
        model=model or settings.openai_model,
        temperature=(
            temperature if temperature is not None else settings.openai_temperature
        ),
        **kwargs,
    )
