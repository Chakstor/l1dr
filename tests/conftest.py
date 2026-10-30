import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_cache, get_llm_wrapper
from app.main import app

def _clear_caches():
    get_settings.cache_clear()
    get_cache.cache_clear()
    get_llm_wrapper.cache_clear()

@pytest.fixture(autouse=True)
def test_env(monkeypatch):
    """Configuración de entorno controlada para cada test (sin claves reales)."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("PRIMARY_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("FALLBACK_MODEL", "claude-haiku-4-5-20251001")
    monkeypatch.setenv("LLM_RETRIES", "0")
    # Puerto donde no hay ningún Redis: si algún test lo usara sin querer, fallaría
    # rápido y sin tocar tu Redis real.
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6390")
    monkeypatch.setenv("APP_ENV", "development")
    _clear_caches()
    yield
    _clear_caches()
    app.dependency_overrides.clear()

@pytest.fixture
def client():
    """Cliente HTTP que llama a la API en memoria, sin levantar el servidor."""
    with TestClient(app) as test_client:
        yield test_client
