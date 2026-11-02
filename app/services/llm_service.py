from collections.abc import Iterator

import structlog

from app.dependencies import get_llm_wrapper
from app.prompts.loader import render_estimation_prompt
from app.schemas.estimation import EstimationRequest
from app.services.llm_wrapper import LLMWrapper, StreamMetrics

log = structlog.get_logger()

MAX_TOKENS = 4000
PROMPT_VERSION = "v1"

class LLMServiceError(Exception):
    """Se lanza cuando falla la llamada al proveedor LLM."""


# ---------------------------------------------------------------------------
# Este módulo decide QUÉ se le pide al LLM (las plantillas de prompt).
# CÓMO se llama al proveedor (fallback, caché, coste, logs) lo resuelve el wrapper.
# ---------------------------------------------------------------------------

def _render_prompt(request: EstimationRequest, version: str) -> tuple[str, str]:
    """Renderiza las plantillas y registra qué se ha pedido (sin el texto, solo su tamaño)."""

    system, user = render_estimation_prompt(request, version=version)

    log.info(
        "estimation_request_received",
        prompt_version=version,
        project_type=request.project_type.value,
        detail_level=request.detail_level.value,
        output_format=request.output_format.value,
        description_chars=len(request.description),
    )

    return system, user


def generate_estimation(
    request: EstimationRequest,
    wrapper: LLMWrapper | None = None,
    version: str = PROMPT_VERSION,
) -> dict:
    """Genera una estimación completa. Devuelve el dict del wrapper + `prompt_version`."""

    wrapper = wrapper or get_llm_wrapper()
    system, user = _render_prompt(request, version)

    try:
        result = wrapper.complete(system_prompt=system, user_message=user, max_tokens=MAX_TOKENS)
    except Exception as exc:
        raise LLMServiceError(f"LLM call failed: {exc}") from exc

    return {**result, "prompt_version": version}


def stream_estimation(
    request: EstimationRequest,
    metrics: StreamMetrics,
    wrapper: LLMWrapper | None = None,
    version: str = PROMPT_VERSION,
) -> Iterator[str]:
    """Genera la estimación en streaming. Va entregando el texto a trozos
    y rellena `metrics` (tokens, coste, TTFT, latencia) cuando termina."""

    wrapper = wrapper or get_llm_wrapper()
    system, user = _render_prompt(request, version)

    try:
        yield from wrapper.complete_stream(
            system_prompt=system,
            user_message=user,
            metrics=metrics,
            max_tokens=MAX_TOKENS,
        )
    except Exception as exc:
        raise LLMServiceError(f"LLM stream failed: {exc}") from exc
