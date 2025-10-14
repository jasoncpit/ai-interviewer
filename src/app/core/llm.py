from __future__ import annotations

from typing import Optional

from langchain_openai import ChatOpenAI

from .config import get_settings


def get_llm(
    temperature: Optional[float] = None, model: Optional[str] = None
) -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=model or settings.openai_model,
        temperature=(
            temperature if temperature is not None else settings.openai_temperature
        ),
    )
