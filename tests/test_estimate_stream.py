import pytest

from app.dependencies import get_llm_wrapper
from app.main import app
from estimator_client import EstimatorAPIError, EstimatorClient, StreamResult, parse_sse

ENDPOINT = "/api/v1/estimate/stream"

VALID_TRANSCRIPTION = (
    "El cliente necesita una web corporativa con blog, formulario de contacto "
    "e integración con HubSpot. El diseño ya existe en Figma."
)


class FakeStreamWrapper:
    """Imita al LLMWrapper en streaming: entrega trozos fijos y rellena las métricas."""

    def __init__(self, chunks=("## Estimación\n", "Total: ", "80 horas"), error=None):
        self.chunks = chunks
        self.error = error

    def complete_stream(self, *, system_prompt, user_message, metrics, max_tokens):
        if self.error:
            raise self.error
        metrics.model = "gpt-4o-mini"
        metrics.provider = "openai"
        metrics.input_tokens = 100
        metrics.output_tokens = 20
        metrics.cost_usd = 0.00003
        metrics.first_token_ms = 5
        metrics.latency_ms = 50
        yield from self.chunks


def use_wrapper(wrapper):
    app.dependency_overrides[get_llm_wrapper] = lambda: wrapper
    return wrapper


def raw_events(client, **kwargs):
    """Llama al endpoint y devuelve la lista de (evento, datos) tal como llegan."""
    with client.stream("POST", ENDPOINT, json={"transcription": VALID_TRANSCRIPTION}, **kwargs) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        return list(parse_sse(response.iter_lines()))


# --- El endpoint, visto "en crudo" ------------------------------------------------


def test_stream_sends_tokens_then_metrics_then_done(client):
    use_wrapper(FakeStreamWrapper())

    events = [event for event, _ in raw_events(client)]

    assert events == ["token", "token", "token", "metrics", "done"]


def test_stream_sends_error_event_when_llm_fails(client):
    use_wrapper(FakeStreamWrapper(error=RuntimeError("provider down")))

    events = raw_events(client)

    assert events[-1][0] == "error"
    assert "provider down" in events[-1][1]


def test_stream_rejects_short_transcription(client):
    response = client.post(ENDPOINT, json={"transcription": "muy corta"})

    assert response.status_code == 422


def test_stream_returns_request_id_header(client):
    use_wrapper(FakeStreamWrapper())

    with client.stream(
        "POST", ENDPOINT, json={"transcription": VALID_TRANSCRIPTION}, headers={"X-Request-ID": "stream-1"}
    ) as response:
        response.read()

    assert response.headers["X-Request-ID"] == "stream-1"


# --- Endpoint + cliente de Streamlit, de punta a punta ----------------------------


def test_client_rebuilds_text_and_gets_metrics(client):
    use_wrapper(FakeStreamWrapper())
    result = StreamResult()

    text = "".join(EstimatorClient("", http_client=client).stream_estimation(VALID_TRANSCRIPTION, result))

    # El salto de línea dentro de un trozo llega intacto
    assert text == "## Estimación\nTotal: 80 horas"
    assert result.metrics["input_tokens"] == 100
    assert result.metrics["cost_usd"] == 0.00003
    assert result.metrics["cache_hit"] is False


def test_client_raises_on_llm_error(client):
    use_wrapper(FakeStreamWrapper(error=RuntimeError("provider down")))

    with pytest.raises(EstimatorAPIError, match="provider down"):
        list(EstimatorClient("", http_client=client).stream_estimation(VALID_TRANSCRIPTION, StreamResult()))


def test_client_raises_readable_error_on_validation_error(client):
    with pytest.raises(EstimatorAPIError, match="422"):
        list(EstimatorClient("", http_client=client).stream_estimation("muy corta", StreamResult()))


# --- GET /context ----------------------------------------------------------------


def test_context_returns_prompt_examples_and_models(client):
    context = EstimatorClient("", http_client=client).get_context()

    assert "EJEMPLO 1" in context["system_prompt"]
    assert len(context["examples"]) >= 2
    assert context["primary_model"] == "gpt-4o-mini"
    assert context["fallback_model"] == "claude-haiku-4-5-20251001"
