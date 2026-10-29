import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

@pytest.fixture(autouse=True)
def test_env(monkeypatch):
    """Configuración de entorno controlada para cada test (sin claves reales)."""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("APP_ENV", "development")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

@pytest.fixture
def client():
    """Cliente HTTP que llama a la API en memoria, sin levantar el servidor."""
    with TestClient(app) as test_client:
        yield test_client