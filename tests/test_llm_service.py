import pytest

from app.config import get_settings
from app.services import llm_service
from app.services.llm_service import LLMServiceError, StreamMetrics

FAKE_PROVIDER_RESULT = {
    "estimation": "## Estimación de prueba",
    "model": "fake-model",
    "provider": "openai",
    "finish_reason": "stop",
    "usage": { "input_tokens": 10, "output_tokens": 5, "total_tokens": 15 },
}


def test_system_prompt_includes_examples():
    prompt = llm_service.build_system_prompt()

    assert "EJEMPLO 1" in prompt
    assert "EJEMPLO 2" in prompt


def test_uses_openai_and_adds_latency(monkeypatch):
    monkeypatch.setattr(llm_service, "_call_openai", lambda system, user: dict(FAKE_PROVIDER_RESULT))

    result = llm_service.generate_estimation("transcripción de prueba")

    assert result["provider"] == "openai"
    assert isinstance(result["latency_ms"], int)
    assert result["latency_ms"] >= 0


def test_uses_anthropic_when_configured(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", "claude-haiku-4-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    get_settings.cache_clear()

    called = {}

    def fake_anthropic(system, user):
        called["anthropic"] = True
        return {**FAKE_PROVIDER_RESULT, "provider": "anthropic"}

    monkeypatch.setattr(llm_service, "_call_anthropic", fake_anthropic)

    result = llm_service.generate_estimation("transcripción de prueba")

    assert called == {"anthropic": True}
    assert result["provider"] == "anthropic"


def test_provider_errors_are_wrapped(monkeypatch):
    def broken_provider(system, user):
        raise RuntimeError("api down")

    monkeypatch.setattr(llm_service, "_call_openai", broken_provider)

    with pytest.raises(LLMServiceError) as exc_info:
        llm_service.generate_estimation("transcripción de prueba")

    assert "api down" in str(exc_info.value)


def test_stream_estimation_yields_chunks_and_fills_metrics(monkeypatch):
    def fake_stream(system, user, metrics):
        metrics.provider = "openai"
        metrics.model = "fake-model"
        metrics.input_tokens = 10
        metrics.output_tokens = 3
        yield "Hola "
        yield "mundo"

    monkeypatch.setattr(llm_service, "_stream_openai", fake_stream)

    metrics = StreamMetrics()
    text = "".join(llm_service.stream_estimation("transcripción de prueba", metrics))

    assert text == "Hola mundo"
    assert metrics.input_tokens == 10
    assert metrics.first_token_ms is not None
    assert metrics.latency_ms >= metrics.first_token_ms


def test_stream_errors_are_wrapped(monkeypatch):
    def broken_stream(system, user, metrics):
        raise RuntimeError("api down")

    monkeypatch.setattr(llm_service, "_stream_openai", broken_stream)

    with pytest.raises(LLMServiceError):
        list(llm_service.stream_estimation("transcripción de prueba", StreamMetrics()))