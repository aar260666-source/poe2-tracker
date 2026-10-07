from redis.asyncio import Redis

from app.config import settings

_redis: Redis | None = None


def get_redis() -> Redis:
    """Ленивое подключение: клиент создаётся при первом обращении."""
    global _redis
    if _redis is None:
        _redis = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
        )
    return _redis


async def close_redis() -> None:
    """Закрываем соединение при остановке приложения."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def check_redis() -> bool:
    """Пинг Redis: вернёт PONG."""
    return await get_redis().ping()
