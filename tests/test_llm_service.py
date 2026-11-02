import pytest

from app.prompts.loader import render_estimation_prompt
from app.schemas.estimation import EstimationRequest
from app.services import llm_service
from app.services.llm_service import LLMServiceError, StreamMetrics

REQUEST = EstimationRequest(
    description="Aplicación web para gestionar reservas de salas de reuniones.",
    project_type="web_saas",
    detail_level="detailed",
    output_format="phases_table",
)

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


def test_generate_estimation_sends_rendered_templates_as_separate_messages():
    wrapper = FakeWrapper()

    llm_service.generate_estimation(REQUEST, wrapper)

    system, user = render_estimation_prompt(REQUEST, version="v1")
    assert wrapper.calls[0] == {"system_prompt": system, "user_message": user}


def test_generate_estimation_adds_prompt_version():
    result = llm_service.generate_estimation(REQUEST, FakeWrapper())

    assert result["prompt_version"] == "v1"
    assert result["estimation"] == FAKE_RESULT["estimation"]


def test_generate_estimation_wraps_errors():
    wrapper = FakeWrapper(error=RuntimeError("api down"))

    with pytest.raises(LLMServiceError) as exc_info:
        llm_service.generate_estimation(REQUEST, wrapper)

    assert "api down" in str(exc_info.value)


def test_stream_estimation_yields_chunks_and_passes_metrics():
    metrics = StreamMetrics()

    text = "".join(llm_service.stream_estimation(REQUEST, metrics, FakeWrapper()))

    assert text == "Hola mundo"
    assert metrics.input_tokens == 10


def test_stream_estimation_wraps_errors():
    wrapper = FakeWrapper(error=RuntimeError("api down"))

    with pytest.raises(LLMServiceError):
        list(llm_service.stream_estimation(REQUEST, StreamMetrics(), wrapper))
