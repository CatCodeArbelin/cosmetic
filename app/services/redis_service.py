from __future__ import annotations

from redis.asyncio import Redis

_redis_client: Redis | None = None


def bind_redis(client: Redis) -> None:
    global _redis_client
    _redis_client = client


def get_redis() -> Redis:
    if _redis_client is None:
        raise RuntimeError('Redis is not initialized')
    return _redis_client
