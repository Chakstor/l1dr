import logging
import re
import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request

from app.config import get_settings
from app.dependencies import get_llm_wrapper
from app.routers.estimations import router as estimations_router

REQUEST_ID_HEADER = "X-Request-ID"
# Solo aceptamos IDs entrantes "seguros": letras, números, . _ - y como mucho 64 caracteres
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def configure_logging(app_env: str, log_level: str) -> None:
    """Configura structlog: consola legible en desarrollo, JSON en producción."""

    renderer = (
        structlog.processors.JSONRenderer()
        if app_env == "production"
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            renderer
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, log_level)),
        cache_logger_on_first_use=True
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Se ejecuta una vez al arrancar la app (antes del yield) y al apagarla (después)."""
    settings = get_settings()
    configure_logging(settings.APP_ENV, settings.LOG_LEVEL)

    log = structlog.get_logger()

    # Creamos el wrapper al arrancar (fail fast) y comprobamos si Redis responde.
    # Si Redis no está, la app arranca igual (la caché es una optimización),
    # pero queda avisado en los logs.
    wrapper = get_llm_wrapper()
    cache_available = wrapper.is_cache_available()

    log.info(
        "app_startup",
        env=settings.APP_ENV,
        primary_model=settings.PRIMARY_MODEL,
        fallback_model=settings.FALLBACK_MODEL,
        cache_available=cache_available,
    )
    if not cache_available:
        log.warning("cache_unavailable", redis_url=settings.REDIS_URL)

    yield

    log.info("app_shutdown")

app = FastAPI(
    title="Estimador CAG API",
    description="Genera estimaciones de software a partir de transcripciones de reuniones.",
    version="0.3.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Asigna un request_id a cada petición y lo añade a TODOS los logs que se emitan durante ella."""

    incoming_id = request.headers.get(REQUEST_ID_HEADER, "")
    request_id = incoming_id if _VALID_REQUEST_ID.match(incoming_id) else uuid.uuid4().hex

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )

    log = structlog.get_logger()
    start = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        log.exception("request_failed", duration_ms=int((time.perf_counter() - start) * 1000))
        raise

    response.headers[REQUEST_ID_HEADER] = request_id
    log.info(
        "request_finished",
        status_code=response.status_code,
        duration_ms=int((time.perf_counter() - start) * 1000),
    )
    return response


app.include_router(estimations_router)

@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Health check: indica que el servicio está levantado."""
    return {"status": "ok"}
