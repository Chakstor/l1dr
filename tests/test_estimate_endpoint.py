from app.services.llm_service import LLMServiceError

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
}


def test_estimate_returns_estimation(client, monkeypatch):
    monkeypatch.setattr(
        "app.routers.estimations.generate_estimation",
        lambda transcription: FAKE_RESULT,
    )

    response = client.post(ENDPOINT, json={ "transcription": VALID_TRANSCRIPTION })

    assert response.status_code == 200
    body = response.json()
    assert body["estimation"] == FAKE_RESULT["estimation"]
    assert body["provider"] == "openai"
    assert body["usage"]["total_tokens"] == 150
    assert body["latency_ms"] == 1234


def test_estimate_rejects_short_transcription(client):
    response = client.post(ENDPOINT, json={"transcription": "muy corta"})

    assert response.status_code == 422


def test_estimate_returns_502_when_llm_fails(client, monkeypatch):
    def failing_generate(transcription):
        raise LLMServiceError("provider down")

    monkeypatch.setattr("app.routers.estimations.generate_estimation", failing_generate)

    response = client.post(ENDPOINT, json={"transcription": VALID_TRANSCRIPTION})

    assert response.status_code == 502
    assert "provider down" in response.json()["detail"]

