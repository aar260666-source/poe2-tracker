from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_by_username(db: AsyncSession, username: str) -> User | None:
    """Ищет пользователя по имени и возвращает объект User или None, если не найден."""
    return (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    """Ищет пользователя по email и возвращает объект User или None, если не найден."""
    return (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()


async def get_by_id(db: AsyncSession, user_id: int) -> User | None:
    """Получает пользователя по первичному ключу (ID) и возвращает User или None."""
    return await db.get(User, user_id)


async def create(db: AsyncSession, username: str, email: str, hashed_password: str) -> User:
    """
    Создаёт нового пользователя с хешированным паролем,
    сохраняет в БД и возвращает объект User.
    """
    user = User(username=username, email=email, hashed_password=hashed_password)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
