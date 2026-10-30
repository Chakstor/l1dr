import hashlib
import json
from typing import Any

import redis
import structlog

log = structlog.get_logger()

KEY_PREFIX = "estimation"

class EstimationCache:
    """Caché exact-match sobre Redis: clave determinista (hash) + caducidad (TTL)."""

    def __init__(self, redis_client: redis.Redis, ttl: int = 86400):
        self.redis = redis_client
        self.ttl = ttl


    @classmethod
    def from_url(cls, url: str, ttl: int = 86400) -> "EstimationCache":
        """Crea la caché conectándose a Redis a partir de una URL."""
        client = redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        return cls(client, ttl=ttl)


    @staticmethod
    def make_key(*, system_prompt: str, user_message: str, model: str, max_tokens: int) -> str:
        """Clave determinista: el mismo input siempre produce la misma clave."""
        payload = json.dumps(
            {
                "system_prompt": system_prompt,
                "user_message": user_message,
                "model": model,
                "max_tokens": max_tokens,
            },
            sort_keys=True,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"{KEY_PREFIX}:{digest}"

    
    def get(self, key: str) -> dict[str, Any] | None:
        """Devuelve la respuesta cacheada, o None si no está o Redis no responde."""
        try:
            cached = self.redis.get(key)
        except redis.RedisError as exc:
            log.warning("cache_get_failed", error=str(exc))
            return None

        if cached is None:
            log.info("cache_miss", key=key[:24])
            return None

        log.info("cache_hit", key=key[:24])
        return json.loads(cached)


    def set(self, key: str, response: dict[str, Any]) -> None:
        """Guarda la respuesta con caducidad. Si Redis falla, se registra y se sigue."""
        try:
            self.redis.set(key, json.dumps(response), ex=self.ttl)
            log.info("cache_stored", key=key[:24], ttl=self.ttl)
        except redis.RedisError as exc:
            log.warning("cache_set_failed", error=str(exc))


    def is_available(self) -> bool:
        """Comprueba si Redis responde. Se usa al arrancar para avisar en los logs."""
        try:
            return bool(self.redis.ping())
        except redis.RedisError:
            return False
