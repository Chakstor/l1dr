import structlog

from app.dependencies import get_llm_wrapper
from app.main import app

ENDPOINT = "/api/v1/estimate"

VALID_TRANSCRIPTION = (
    "El cliente necesita una web corporativa con blog, formulario de contacto "
    "e integración con HubSpot. El diseño ya existe en Figma."
)

FAKE_RESULT = {
    "estimation": "## Estimación: Web corporativa\n\nTotal: 80 horas",
    "model": "gpt-4o-mini-2024-07-18",
    "provider": "openai",
    "finish_reason": "stop",
    "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
    "latency_ms": 1234,
    "cost_usd": 0.00045,
    "cache_hit": False,
}


class FakeWrapper:
    """Sustituye al LLMWrapper real en los tests del endpoint."""

    def __init__(self, error: Exception | None = None):
        self.error = error
        self.seen_request_id = None

    def complete(self, *, system_prompt, user_message, max_tokens):
        # Guardamos el request_id que ve el código de dentro del endpoint
        self.seen_request_id = structlog.contextvars.get_contextvars().get("request_id")
        if self.error:
            raise self.error
        return dict(FAKE_RESULT)


def use_wrapper(wrapper):
    """Inyecta un wrapper falso en lugar de get_llm_wrapper (inyección de dependencias de FastAPI)."""
    app.dependency_overrides[get_llm_wrapper] = lambda: wrapper
    return wrapper


def test_estimate_returns_estimation(client):
    use_wrapper(FakeWrapper())

    response = client.post(ENDPOINT, json={"transcription": VALID_TRANSCRIPTION})

    assert response.status_code == 200
    body = response.json()
    assert body["estimation"] == FAKE_RESULT["estimation"]
    assert body["provider"] == "openai"
    assert body["usage"]["total_tokens"] == 150
    assert body["latency_ms"] == 1234
    assert body["cost_usd"] == 0.00045
    assert body["cache_hit"] is False


def test_estimate_rejects_short_transcription(client):
    response = client.post(ENDPOINT, json={"transcription": "muy corta"})

    assert response.status_code == 422


def test_estimate_returns_502_when_llm_fails(client):
    use_wrapper(FakeWrapper(error=RuntimeError("provider down")))

    response = client.post(ENDPOINT, json={"transcription": VALID_TRANSCRIPTION})

    assert response.status_code == 502
    assert "provider down" in response.json()["detail"]


def test_request_id_is_generated_and_returned(client):
    response = client.get("/health")

    request_id = response.headers["X-Request-ID"]
    assert len(request_id) == 32


def test_request_id_from_client_is_reused(client):
    response = client.get("/health", headers={"X-Request-ID": "mi-peticion-123"})

    assert response.headers["X-Request-ID"] == "mi-peticion-123"


def test_invalid_request_id_from_client_is_replaced(client):
    response = client.get("/health", headers={"X-Request-ID": "no-valido <script>"})

    assert response.headers["X-Request-ID"] != "no-valido <script>"
    assert len(response.headers["X-Request-ID"]) == 32


def test_request_id_reaches_code_inside_the_endpoint(client):
    wrapper = use_wrapper(FakeWrapper())

    response = client.post(
        ENDPOINT,
        json={"transcription": VALID_TRANSCRIPTION},
        headers={"X-Request-ID": "trazame-esta"},
    )

    assert response.status_code == 200
    assert wrapper.seen_request_id == "trazame-esta"
