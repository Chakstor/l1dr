import fakeredis
import pytest

from app.services.cache import EstimationCache
from app.services.llm_wrapper import (
    FALLBACK,
    PRIMARY,
    LLMWrapper,
    StreamMetrics,
    estimate_cost,
    provider_of,
)

PRIMARY_MODEL = "gpt-4o-mini"
FALLBACK_MODEL = "claude-haiku-4-5-20251001"
FAILURE = "litellm.InternalServerError"  # LiteLLM simula un error 500 con este texto


def make_wrapper(primary_response: str, fallback_response: str = "Respuesta del fallback") -> LLMWrapper:
    """Wrapper real (Router real, fallback real) pero sin llamar a ninguna API:
    a cada modelo le decimos qué debe "responder" con `mock_response` de LiteLLM."""
    wrapper = LLMWrapper(
        primary_model=PRIMARY_MODEL,
        fallback_model=FALLBACK_MODEL,
        openai_api_key="test-key",
        anthropic_api_key="test-key",
        timeout=5,
        num_retries=0,
        cache=EstimationCache(fakeredis.FakeRedis(decode_responses=True), ttl=60),
    )
    mocks = {PRIMARY: primary_response, FALLBACK: fallback_response}
    for deployment in wrapper.router.model_list:
        deployment["litellm_params"]["mock_response"] = mocks[deployment["model_name"]]
    return wrapper


def call(wrapper: LLMWrapper) -> dict:
    return wrapper.complete(system_prompt="Eres un estimador", user_message="Una transcripción")


# --- utilidades ------------------------------------------------------------


def test_provider_of_known_models():
    assert provider_of(PRIMARY_MODEL) == "openai"
    assert provider_of(FALLBACK_MODEL) == "anthropic"


def test_estimate_cost_uses_litellm_prices():
    assert estimate_cost(PRIMARY_MODEL, 1_000_000, 0) > 0
    assert estimate_cost("modelo-que-no-existe", 1000, 1000) == 0.0


def test_api_key_is_chosen_by_provider():
    wrapper = LLMWrapper(
        primary_model=PRIMARY_MODEL,
        fallback_model=FALLBACK_MODEL,
        openai_api_key="clave-openai",
        anthropic_api_key="clave-anthropic",
        timeout=5,
        num_retries=0,
        cache=EstimationCache(fakeredis.FakeRedis(decode_responses=True), ttl=60),
    )
    keys = {d["model_name"]: d["litellm_params"]["api_key"] for d in wrapper.router.model_list}

    assert keys == {PRIMARY: "clave-openai", FALLBACK: "clave-anthropic"}


# --- complete() ---------------------------------------------------------------


def test_complete_uses_primary_and_returns_normalised_result():
    result = call(make_wrapper("Respuesta del primario"))

    assert result["estimation"] == "Respuesta del primario"
    assert result["provider"] == "openai"
    assert result["cache_hit"] is False
    assert result["usage"]["total_tokens"] == (
        result["usage"]["input_tokens"] + result["usage"]["output_tokens"]
    )
    assert result["cost_usd"] > 0


def test_complete_falls_back_when_primary_fails():
    result = call(make_wrapper(FAILURE))

    assert result["estimation"] == "Respuesta del fallback"
    assert result["provider"] == "anthropic"


def test_complete_raises_when_both_providers_fail():
    with pytest.raises(Exception):
        call(make_wrapper(FAILURE, FAILURE))


def test_second_identical_call_is_served_from_cache():
    wrapper = make_wrapper("Respuesta del primario")

    first = call(wrapper)
    second = call(wrapper)

    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    assert second["estimation"] == first["estimation"]
    assert second["cost_usd"] == 0.0


# --- complete_stream() -------------------------------------------------------


def stream(wrapper: LLMWrapper, metrics: StreamMetrics) -> str:
    return "".join(
        wrapper.complete_stream(
            system_prompt="Eres un estimador",
            user_message="Una transcripción",
            metrics=metrics,
        )
    )


def test_stream_yields_text_and_fills_metrics():
    metrics = StreamMetrics()

    text = stream(make_wrapper("Respuesta del primario"), metrics)

    assert text == "Respuesta del primario"
    assert metrics.provider == "openai"
    assert metrics.input_tokens > 0
    assert metrics.output_tokens > 0
    assert metrics.cost_usd > 0
    assert metrics.first_token_ms is not None
    assert metrics.latency_ms >= metrics.first_token_ms
    assert metrics.cache_hit is False
    assert metrics.fallback_used is False


def test_stream_falls_back_when_primary_fails():
    metrics = StreamMetrics()

    text = stream(make_wrapper(FAILURE), metrics)

    assert text == "Respuesta del fallback"
    assert metrics.provider == "anthropic"
    assert metrics.fallback_used is True


def test_stream_and_complete_share_the_cache():
    wrapper = make_wrapper("Respuesta del primario")
    stream(wrapper, StreamMetrics())

    cached_metrics = StreamMetrics()
    text = stream(wrapper, cached_metrics)
    blocking = call(wrapper)

    assert text == "Respuesta del primario"
    assert cached_metrics.cache_hit is True
    assert blocking["cache_hit"] is True
