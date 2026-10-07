from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, bearer
from app.core.database import get_db
from app.core.redis import get_redis
from app.core.security import create_access_token, hash_password, verify_password
from app.crud import user as crud_user
from app.schemas.auth import LoginIn, RegisterIn, TokenOut, UserOut
from app.services import auth as auth_service
from redis.asyncio import Redis

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
async def register(
    payload: RegisterIn,
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    """
    Регистрация нового пользователя: проверяет уникальность username и email,
    создаёт запись с bcrypt-хэшем пароля, возвращает данные пользователя или ошибки 409.
    """
    if await crud_user.get_by_username(db, payload.username):
        raise HTTPException(409, "Имя занято")
    if await crud_user.get_by_email(db, payload.email):
        raise HTTPException(409, "Email уже используется")

    user = await crud_user.create(
        db, payload.username, payload.email, hash_password(payload.password)
    )
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenOut)
async def login(
    payload: LoginIn,
    db: AsyncSession = Depends(get_db),
    r: Redis = Depends(get_redis),
) -> TokenOut:
    """
    Аутентификация по email или username и паролю, генерирует JWT-токен,
    сохраняет его в Redis и возвращает клиенту.
    """
    user = await crud_user.get_by_email(db, payload.email)

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный email или пароль")

    token = create_access_token(user.id)
    await auth_service.save_token(r, token, user.id)
    return TokenOut(access_token=token)


@router.get("/me", response_model=UserOut)
async def me(current_user=Depends(get_current_user)) -> UserOut:
    """Возвращает данные текущего пользователя, определённого по токену"""
    return current_user


@router.post("/logout")
async def logout(creds: HTTPAuthorizationCredentials = Depends(bearer), r: Redis = Depends(get_redis)) -> dict:
    """Удаляет токен из Redis, мгновенно завершая сессию пользователя."""
    await auth_service.delete_token(r, creds.credentials)
    return {"detail": "Вы вышли из системы"}