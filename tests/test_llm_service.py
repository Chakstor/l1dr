import pytest

from app.services import llm_service
from app.services.llm_service import LLMServiceError, StreamMetrics

FAKE_RESULT = {
    "estimation": "## Estimación de prueba",
    "model": "gpt-4o-mini",
    "provider": "openai",
    "finish_reason": "stop",
    "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    "latency_ms": 42,
    "cost_usd": 0.0001,
    "cache_hit": False,
}


class FakeWrapper:
    """Imita al LLMWrapper: guarda lo que recibe y devuelve respuestas fijas."""

    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls = []

    def complete(self, *, system_prompt, user_message, max_tokens):
        self.calls.append({"system_prompt": system_prompt, "user_message": user_message})
        if self.error:
            raise self.error
        return dict(FAKE_RESULT)

    def complete_stream(self, *, system_prompt, user_message, metrics, max_tokens):
        self.calls.append({"system_prompt": system_prompt, "user_message": user_message})
        if self.error:
            raise self.error
        metrics.model = "gpt-4o-mini"
        metrics.input_tokens = 10
        yield "Hola "
        yield "mundo"


def test_system_prompt_includes_examples():
    prompt = llm_service.build_system_prompt()

    assert "EJEMPLO 1" in prompt
    assert "EJEMPLO 2" in prompt


def test_generate_estimation_sends_cag_prompt_and_transcription():
    wrapper = FakeWrapper()

    result = llm_service.generate_estimation("transcripción de prueba", wrapper)

    assert result == FAKE_RESULT
    assert wrapper.calls[0]["user_message"] == "transcripción de prueba"
    assert wrapper.calls[0]["system_prompt"] == llm_service.build_system_prompt()


def test_generate_estimation_wraps_errors():
    wrapper = FakeWrapper(error=RuntimeError("api down"))

    with pytest.raises(LLMServiceError) as exc_info:
        llm_service.generate_estimation("transcripción de prueba", wrapper)

    assert "api down" in str(exc_info.value)


def test_stream_estimation_yields_chunks_and_passes_metrics():
    metrics = StreamMetrics()

    text = "".join(llm_service.stream_estimation("transcripción de prueba", metrics, FakeWrapper()))

    assert text == "Hola mundo"
    assert metrics.input_tokens == 10


def test_stream_estimation_wraps_errors():
    wrapper = FakeWrapper(error=RuntimeError("api down"))

    with pytest.raises(LLMServiceError):
        list(llm_service.stream_estimation("transcripción de prueba", StreamMetrics(), wrapper))
