import json
from collections.abc import AsyncIterator
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette import EventSourceResponse
from starlette.concurrency import iterate_in_threadpool

from app.config import get_settings
from app.context.examples import ESTIMATION_EXAMPLES
from app.dependencies import get_llm_wrapper
from app.schemas.estimation import ContextResponse, EstimationRequest, EstimationResponse
from app.services.llm_service import (
    LLMServiceError,
    StreamMetrics,
    build_system_prompt,
    generate_estimation,
    stream_estimation,
)
from app.services.llm_wrapper import LLMWrapper

router = APIRouter(prefix="/api/v1", tags=["estimations"])

@router.post("/estimate", response_model=EstimationResponse)
def create_estimation(
    request: EstimationRequest,
    wrapper: LLMWrapper = Depends(get_llm_wrapper),
) -> EstimationResponse:
    """Recibe la transcripción de una reunión y devuelve una estimación."""

    try:
        result = generate_estimation(request.transcription, wrapper)
    except LLMServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # **results same as ...result in JS
    return EstimationResponse(**result)


@router.post("/estimate/stream")
async def create_estimation_stream(
    request: EstimationRequest,
    wrapper: LLMWrapper = Depends(get_llm_wrapper),
) -> EventSourceResponse:
    """Igual que /estimate pero en streaming con Server-Sent Events (SSE).

    Eventos que envía, en este orden:
    - `token`   → {"text": "..."}  un trozo de la estimación (muchos)
    - `metrics` → {...}            tokens, coste, caché, fallback, latencias (uno, al final)
    - `done`    → [DONE]           fin del stream
    Si el LLM falla, en lugar de `metrics` + `done` se envía:
    - `error`   → {"detail": "..."}
    """

    async def event_stream() -> AsyncIterator[dict]:
        metrics = StreamMetrics()
        chunks = stream_estimation(request.transcription, metrics, wrapper)

        try:
            # El wrapper es síncrono: cada trozo se pide en un hilo aparte
            # para no bloquear el servidor mientras esperamos al LLM.
            async for chunk in iterate_in_threadpool(chunks):
                yield {"event": "token", "data": json.dumps({"text": chunk})}
        except LLMServiceError as exc:
            yield {"event": "error", "data": json.dumps({"detail": str(exc)})}
            return

        yield {"event": "metrics", "data": json.dumps(asdict(metrics))}
        yield {"event": "done", "data": "[DONE]"}

    return EventSourceResponse(event_stream())


@router.get("/context", response_model=ContextResponse)
def get_context() -> ContextResponse:
    """Contexto CAG activo: system prompt, ejemplos inyectados y modelos configurados.

    Permite a cualquier cliente (p. ej. Streamlit) mostrarlo sin importar código del backend.
    """
    settings = get_settings()
    return ContextResponse(
        system_prompt=build_system_prompt(),
        examples=ESTIMATION_EXAMPLES,
        primary_model=settings.PRIMARY_MODEL,
        fallback_model=settings.FALLBACK_MODEL,
    )
