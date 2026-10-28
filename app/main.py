import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.config import get_settings
from app.routers.estimations import router as estimations_router

def configure_loggging(app_env: str, log_level: str) -> None:
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
    configure_loggging(settings.APP_ENV, settings.LOG_LEVEL)

    log = structlog.get_logger()
    log.info(
        "app_startup",
        env=settings.APP_ENV,
        provider=settings.LLM_PROVIDER,
        model=settings.LLM_MODEL,
    )

    yield

    log.info("app_shutdown")

app = FastAPI(
    title="Estimador CAG API",
    description="Genera estimaciones de software a partir de transcripciones de reuniones.",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(estimations_router)

@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Health check: indica que el servicio está levantado."""
    return {"status": "ok"}