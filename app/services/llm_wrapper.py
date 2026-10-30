"""Wrapper sobre LiteLLM: la única pieza de la app que habla con los proveedores de LLM.

Añade a cada llamada:
- Fallback entre proveedores (primario → fallback), reintentos y timeout.
- Caché exact-match en Redis (misma entrada → misma respuesta, sin coste).
- Coste en USD, tokens, latencia y logs estructurados.

Expone dos operaciones: `complete()` (respuesta completa) y
`complete_stream()` (texto a trozos + métricas al final).
"""

import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from typing import Any

import litellm
import structlog
from litellm import Router

from app.services.cache import EstimationCache

log = structlog.get_logger()

litellm.suppress_debug_info = True

# Nombres de los dos "grupos de modelos" dentro del Router de LiteLLM
PRIMARY = "primary"
FALLBACK = "fallback"

DEFAULT_MAX_TOKENS = 4000


@dataclass
class StreamMetrics:
    """Métricas de una llamada en streaming. Se rellenan a medida que avanza el stream."""

    model: str = ""
    provider: str = ""
    finish_reason: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    cache_hit: bool = False
    fallback_used: bool = False
    first_token_ms: int | None = None
    latency_ms: int = 0


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def normalise_model_name(model: str) -> str:
    """LiteLLM a veces devuelve el modelo con prefijo de proveedor ('anthropic/claude-...'): lo quitamos."""
    return model.split("/", 1)[1] if "/" in model else model


def provider_of(model: str) -> str:
    """Devuelve el proveedor de un modelo ('openai', 'anthropic'...) según LiteLLM."""
    try:
        return litellm.get_llm_provider(model)[1]
    except Exception:
        return "unknown"


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Coste en USD de una llamada, con la tabla de precios que mantiene LiteLLM."""
    try:
        input_cost, output_cost = litellm.cost_per_token(
            model=model,
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
        )
    except Exception:
        log.warning("cost_unknown_model", model=model)
        return 0.0
    return round(input_cost + output_cost, 6)


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _messages(system_prompt: str, user_message: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]


# ---------------------------------------------------------------------------
# Wrapper
# ---------------------------------------------------------------------------


class LLMWrapper:
    """Cliente LLM unificado: caché + fallback + coste + logs."""

    def __init__(
        self,
        *,
        primary_model: str,
        fallback_model: str,
        openai_api_key: str | None,
        anthropic_api_key: str | None,
        timeout: int,
        num_retries: int,
        cache: EstimationCache,
    ):
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.openai_api_key = openai_api_key
        self.anthropic_api_key = anthropic_api_key
        self.cache = cache

        self.router = Router(
            model_list=[
                self._deployment(PRIMARY, primary_model, timeout),
                self._deployment(FALLBACK, fallback_model, timeout),
            ],
            fallbacks=[{PRIMARY: [FALLBACK]}],
            num_retries=num_retries,
        )

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def complete(
        self,
        *,
        system_prompt: str,
        user_message: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> dict[str, Any]:
        """Llamada completa (no streaming). Devuelve el dict de la estimación
        con `usage`, `latency_ms`, `cost_usd` y `cache_hit`."""
        start = time.perf_counter()
        cache_key = self._cache_key(system_prompt, user_message, max_tokens)

        cached = self.cache.get(cache_key)
        if cached is not None:
            latency_ms = _elapsed_ms(start)
            log.info("llm_call_cached", model=cached["model"], latency_ms=latency_ms)
            return {**cached, "latency_ms": latency_ms, "cost_usd": 0.0, "cache_hit": True}

        log.info("llm_call_started", mode="blocking", primary=self.primary_model, fallback=self.fallback_model)

        try:
            response = self.router.completion(
                model=PRIMARY,
                messages=_messages(system_prompt, user_message),
                max_tokens=max_tokens,
            )
        except Exception as exc:
            log.error(
                "llm_call_failed",
                error_type=type(exc).__name__,
                error=str(exc),
                latency_ms=_elapsed_ms(start),
            )
            raise

        result = self._normalise_response(response, latency_ms=_elapsed_ms(start))
        log.info(
            "llm_call_completed",
            model=result["model"],
            provider=result["provider"],
            fallback_used=self._is_fallback(result["model"]),
            finish_reason=result["finish_reason"],
            input_tokens=result["usage"]["input_tokens"],
            output_tokens=result["usage"]["output_tokens"],
            cost_usd=result["cost_usd"],
            latency_ms=result["latency_ms"],
        )

        self.cache.set(cache_key, result)
        return {**result, "cache_hit": False}

    def complete_stream(
        self,
        *,
        system_prompt: str,
        user_message: str,
        metrics: StreamMetrics,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> Iterator[str]:
        """Llamada en streaming: entrega el texto a trozos y rellena `metrics`.

        Si la respuesta está en caché, se entrega de una vez como un único trozo.
        Si no, se hace streaming real y, al terminar, se guarda en caché con el
        mismo formato que `complete()`, así las dos operaciones comparten caché.
        """
        start = time.perf_counter()
        cache_key = self._cache_key(system_prompt, user_message, max_tokens)

        cached = self.cache.get(cache_key)
        if cached is not None:
            metrics.cache_hit = True
            metrics.model = cached["model"]
            metrics.provider = cached["provider"]
            metrics.finish_reason = cached["finish_reason"]
            metrics.input_tokens = cached["usage"]["input_tokens"]
            metrics.output_tokens = cached["usage"]["output_tokens"]
            metrics.first_token_ms = metrics.latency_ms = _elapsed_ms(start)
            log.info("llm_stream_cached", model=metrics.model, latency_ms=metrics.latency_ms)
            yield cached["estimation"]
            return

        log.info("llm_stream_started", primary=self.primary_model, fallback=self.fallback_model)

        parts: list[str] = []
        try:
            stream = self.router.completion(
                model=PRIMARY,
                messages=_messages(system_prompt, user_message),
                max_tokens=max_tokens,
                stream=True,
                stream_options={"include_usage": True},
            )
            for chunk in stream:
                self._update_metrics_from_chunk(chunk, metrics)
                text = self._chunk_text(chunk)
                if text:
                    if metrics.first_token_ms is None:
                        metrics.first_token_ms = _elapsed_ms(start)
                    parts.append(text)
                    yield text
        except Exception as exc:
            log.error(
                "llm_stream_failed",
                error_type=type(exc).__name__,
                error=str(exc),
                latency_ms=_elapsed_ms(start),
            )
            raise

        metrics.latency_ms = _elapsed_ms(start)
        metrics.provider = provider_of(metrics.model)
        metrics.fallback_used = self._is_fallback(metrics.model)
        metrics.cost_usd = estimate_cost(metrics.model, metrics.input_tokens, metrics.output_tokens)
        log.info("llm_stream_completed", **asdict(metrics))

        self.cache.set(
            cache_key,
            {
                "estimation": "".join(parts),
                "model": metrics.model,
                "provider": metrics.provider,
                "finish_reason": metrics.finish_reason,
                "usage": {
                    "input_tokens": metrics.input_tokens,
                    "output_tokens": metrics.output_tokens,
                    "total_tokens": metrics.input_tokens + metrics.output_tokens,
                },
                "latency_ms": metrics.latency_ms,
                "cost_usd": metrics.cost_usd,
            },
        )

    def is_cache_available(self) -> bool:
        return self.cache.is_available()

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _deployment(self, name: str, model: str, timeout: int) -> dict[str, Any]:
        """Configuración de un modelo dentro del Router, con la API key de su proveedor."""
        api_key = self.anthropic_api_key if provider_of(model) == "anthropic" else self.openai_api_key
        return {
            "model_name": name,
            "litellm_params": {"model": model, "api_key": api_key, "timeout": timeout},
        }

    def _cache_key(self, system_prompt: str, user_message: str, max_tokens: int) -> str:
        return EstimationCache.make_key(
            system_prompt=system_prompt,
            user_message=user_message,
            model=self.primary_model,
            max_tokens=max_tokens,
        )

    def _is_fallback(self, response_model: str) -> bool:
        return response_model.startswith(self.fallback_model)

    @staticmethod
    def _normalise_response(response: Any, *, latency_ms: int) -> dict[str, Any]:
        """Convierte la respuesta de LiteLLM al dict que usa el resto de la app."""
        choice = response.choices[0]
        usage = response.usage
        input_tokens = usage.prompt_tokens or 0
        output_tokens = usage.completion_tokens or 0
        model = normalise_model_name(response.model)

        return {
            "estimation": choice.message.content or "",
            "model": model,
            "provider": provider_of(model),
            "finish_reason": choice.finish_reason or "stop",
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
            "latency_ms": latency_ms,
            "cost_usd": estimate_cost(model, input_tokens, output_tokens),
        }

    @staticmethod
    def _update_metrics_from_chunk(chunk: Any, metrics: StreamMetrics) -> None:
        """Cada chunk puede traer el modelo, el motivo de parada o (el último) los tokens."""
        if getattr(chunk, "model", None):
            metrics.model = normalise_model_name(chunk.model)
        usage = getattr(chunk, "usage", None)
        if usage:
            metrics.input_tokens = usage.prompt_tokens or 0
            metrics.output_tokens = usage.completion_tokens or 0
        if chunk.choices and chunk.choices[0].finish_reason:
            metrics.finish_reason = chunk.choices[0].finish_reason

    @staticmethod
    def _chunk_text(chunk: Any) -> str:
        """El trozo de texto nuevo del chunk, o '' si no trae texto."""
        if not chunk.choices:
            return ""
        return chunk.choices[0].delta.content or ""
