from datetime import datetime, timedelta, timezone
import jwt
import bcrypt
from app.config import settings


def hash_password(password: str) -> str:
    """Превращает пароль пользователя в хэш с использованием bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Проверяет, совпадает ли введённый пароль с сохранённым хэшем."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: int) -> str:
    """Функция создаёт JWT‑токен доступа для пользователя: формирует payload с ID пользователя
    и временем истечения, затем подписывает его секретным ключом."""
    expire = datetime.now(timezone.utc) + timedelta(seconds=settings.ACCESS_TOKEN_EXPIRE_SECONDS)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Возвращает user_id из токена или None, если токен невалиден/просрочен."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
