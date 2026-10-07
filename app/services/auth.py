from redis.asyncio import Redis

ACCESS_TOKEN_TTL = 30 * 60


def token_key(token: str) -> str:
    """Формирует ключ Redis с префиксом token: для хранения токена."""
    return f"token:{token}"


async def save_token(r: Redis, token: str, user_id: int) -> None:
    """Сохраняет токен с ID пользователя и TTL в 30 минут, синхронизируя срок жизни с JWT."""
    await r.setex(token_key(token), ACCESS_TOKEN_TTL, str(user_id))


async def is_token_valid(r: Redis, token: str) -> bool:
    """Проверяет, существует ли токен в Redis, определяя его действительность."""
    return bool(await r.exists(token_key(token)))


async def delete_token(r: Redis, token: str) -> None:
    """Удаляет токен из Redis, мгновенно завершая сессию (логаут)."""
    await r.delete(token_key(token))
