from __future__ import annotations

import pytest

from app.core import config as config_module
from app.core import llm as llm_module


def _reset_settings_cache() -> None:
    config_module.get_settings.cache_clear()


class _DummyChatOpenAI:
    def __init__(self, **kwargs):
        self.params = kwargs


def test_get_settings_reads_openai_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env-token")
    _reset_settings_cache()
    settings = config_module.get_settings()
    assert settings.openai_api_key == "env-token"


def test_get_llm_uses_env_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "abc123")
    _reset_settings_cache()

    captured = {}

    def fake_chat_openai(*, model, temperature, api_key):
        captured["model"] = model
        captured["temperature"] = temperature
        captured["api_key"] = api_key
        return _DummyChatOpenAI(model=model, temperature=temperature, api_key=api_key)

    monkeypatch.setattr(llm_module, "ChatOpenAI", fake_chat_openai)

    instance = llm_module.get_llm(temperature=0.55, model="gpt-unit-test")
    assert isinstance(instance, _DummyChatOpenAI)
    assert captured == {
        "model": "gpt-unit-test",
        "temperature": 0.55,
        "api_key": "abc123",
    }


def test_get_llm_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _reset_settings_cache()

    class _NoKeySettings:
        openai_model = "gpt-fallback"
        openai_temperature = 0.4
        openai_api_key = None

    monkeypatch.setattr(llm_module, "get_settings", lambda: _NoKeySettings())
    monkeypatch.setattr(llm_module, "ChatOpenAI", _DummyChatOpenAI)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        llm_module.get_llm()
