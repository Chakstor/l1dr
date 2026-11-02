import json
from collections.abc import AsyncIterator
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette import EventSourceResponse
from starlette.concurrency import iterate_in_threadpool

from app.config import get_settings
from app.dependencies import get_llm_wrapper
from app.schemas.estimation import (
    ContextResponse,
    DetailLevel,
    EstimationRequest,
    EstimationResponse,
    FormOptions,
    OutputFormat,
    ProjectType,
    PromptPreviewResponse,
)
from app.services.llm_service import (
    PROMPT_VERSION,
    LLMServiceError,
    StreamMetrics,
    generate_estimation,
    preview_prompt,
    stream_estimation,
)
from app.services.llm_wrapper import LLMWrapper

router = APIRouter(prefix="/api/v1", tags=["estimations"])

@router.post("/estimate", response_model=EstimationResponse)
def create_estimation(
    request: EstimationRequest,
    wrapper: LLMWrapper = Depends(get_llm_wrapper),
) -> EstimationResponse:
    """Recibe los parámetros del formulario y devuelve una estimación."""

    try:
        result = generate_estimation(request, wrapper)
    except LLMServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return EstimationResponse(
        text=result["estimation"],
        prompt_version=result["prompt_version"],
        model=result["model"],
        provider=result["provider"],
        usage=result["usage"],
        finish_reason=result["finish_reason"],
        latency_ms=result["latency_ms"],
        cost_usd=result["cost_usd"],
        cache_hit=result["cache_hit"],
    )


@router.post("/estimate/stream")
async def create_estimation_stream(
    request: EstimationRequest,
    wrapper: LLMWrapper = Depends(get_llm_wrapper),
) -> EventSourceResponse:
    """Igual que /estimate pero en streaming con Server-Sent Events (SSE).

    Eventos que envía, en este orden:
    - `token`   → {"text": "..."}  un trozo de la estimación (muchos)
    - `metrics` → {...}            tokens, coste, caché, fallback, latencias y prompt_version (uno, al final)
    - `done`    → [DONE]           fin del stream
    Si el LLM falla, en lugar de `metrics` + `done` se envía:
    - `error`   → {"detail": "..."}
    """

    async def event_stream() -> AsyncIterator[dict]:
        metrics = StreamMetrics()
        chunks = stream_estimation(request, metrics, wrapper)

        try:
            # El wrapper es síncrono: cada trozo se pide en un hilo aparte
            # para no bloquear el servidor mientras esperamos al LLM.
            async for chunk in iterate_in_threadpool(chunks):
                yield {"event": "token", "data": json.dumps({"text": chunk})}
        except LLMServiceError as exc:
            yield {"event": "error", "data": json.dumps({"detail": str(exc)})}
            return

        yield {"event": "metrics", "data": json.dumps({**asdict(metrics), "prompt_version": PROMPT_VERSION})}
        yield {"event": "done", "data": "[DONE]"}

    return EventSourceResponse(event_stream())


@router.get("/context", response_model=ContextResponse)
def get_context() -> ContextResponse:
    """Configuración para los clientes: modelos, versión del prompt y opciones del formulario.

    Así el formulario de Streamlit (o de cualquier frontend) se construye con los
    valores que acepta la API, sin copiarlos ni importar código del backend.
    """
    settings = get_settings()
    return ContextResponse(
        primary_model=settings.PRIMARY_MODEL,
        fallback_model=settings.FALLBACK_MODEL,
        prompt_version=PROMPT_VERSION,
        options=FormOptions(
            project_type=[option.value for option in ProjectType],
            detail_level=[option.value for option in DetailLevel],
            output_format=[option.value for option in OutputFormat],
        ),
    )


@router.post("/prompt/preview", response_model=PromptPreviewResponse)
def create_prompt_preview(request: EstimationRequest) -> PromptPreviewResponse:
    """Devuelve el prompt exacto (system + user + ejemplos) que se enviaría al LLM
    para esta petición, sin llamarlo. Útil para depurar y para mostrarlo en la interfaz.

    No está disponible en producción: el prompt es parte del "know-how" del producto
    y no debería exponerse a cualquier cliente.
    """
    if get_settings().APP_ENV == "production":
        raise HTTPException(status_code=404, detail="Not Found")

    return PromptPreviewResponse(**preview_prompt(request))
