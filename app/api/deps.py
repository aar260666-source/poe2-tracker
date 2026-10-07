from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.core.security import decode_access_token
from app.crud import user as crud_user
from app.models.user import User
from app.services import auth as auth_service

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
    r: Redis = Depends(get_redis),
) -> User:
    """
    Извлекает Bearer-токен из заголовка, проверяет его валидность в Redis и расшифровку JWT,
    затем находит пользователя по ID из токена и возвращает его
    """
    if creds is None:
        raise HTTPException(401, "Токен отсутствует")

    if not await auth_service.is_token_valid(r, creds.credentials):
        raise HTTPException(401, "Сессия недействительна или истекла")

    user_id = decode_access_token(creds.credentials)
    if user_id is None:
        raise HTTPException(401, "Некорректный токен")

    user = await crud_user.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(401, "Пользователь не найден")
    return user

