import fakeredis
import pytest
import redis

from app.services.cache import EstimationCache

KEY_ARGS = {
    "system_prompt": "Eres un estimador",
    "user_message": "Una transcripción",
    "model": "gpt-4o-mini",
    "max_tokens": 4000,
}

@pytest.fixture
def cache():
    return EstimationCache(fakeredis.FakeRedis(decode_responses=True), ttl=60)


def test_make_key_is_deterministic():
    assert EstimationCache.make_key(**KEY_ARGS) == EstimationCache.make_key(**KEY_ARGS)


def test_make_key_changes_when_any_input_changes():
    base_key = EstimationCache.make_key(**KEY_ARGS)
    changes = [
        ("system_prompt", "Otro prompt"),
        ("user_message", "Otra transcripción"),
        ("model", "gpt-4o"),
        ("max_tokens", 1000),
    ]
    for field, new_value in changes:
        assert EstimationCache.make_key(**{**KEY_ARGS, field: new_value}) != base_key


def test_make_key_uses_namespace_prefix():
    assert EstimationCache.make_key(**KEY_ARGS).startswith("estimation:")


def test_set_then_get_roundtrips_payload(cache):
    key = EstimationCache.make_key(**KEY_ARGS)
    payload = {"estimation": "## Estimación", "usage": {"input_tokens": 10, "output_tokens": 5}}

    cache.set(key, payload)

    assert cache.get(key) == payload


def test_get_returns_none_on_miss(cache):
    assert cache.get(EstimationCache.make_key(**KEY_ARGS)) is None


def test_set_applies_ttl(cache):
    key = EstimationCache.make_key(**KEY_ARGS)

    cache.set(key, {"x": 1})

    assert 0 < cache.redis.ttl(key) <= 60


class BrokenRedis:
    """Imita un Redis caído: cualquier operación lanza un error de conexión."""

    def get(self, key):
        raise redis.ConnectionError("redis down")

    def setex(self, key, ttl, value):
        raise redis.ConnectionError("redis down")


def test_cache_degrades_gracefully_when_redis_is_down():
    cache = EstimationCache(BrokenRedis(), ttl=60)
    key = EstimationCache.make_key(**KEY_ARGS)

    cache.set(key, {"x": 1})

    assert cache.get(key) is None