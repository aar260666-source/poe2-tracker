from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import TrackedCharacter


async def add(db: AsyncSession, user_id: int, name: str, league: str) -> TrackedCharacter:
    """Находит существующую запись отслеживания или создаёт новую, добавляет её в БД"""
    exists = await get(db, user_id, name, league)
    if exists:
        return exists
    row = TrackedCharacter(user_id=user_id, name=name, league=league)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def get(db: AsyncSession, user_id: int, name: str, league: str) -> TrackedCharacter | None:
    """Ищет по трём полям (пользователь, имя, лига) одну запись и возвращает её или None"""
    return await db.scalar(
        select(TrackedCharacter).where(
            TrackedCharacter.user_id == user_id,
            TrackedCharacter.name == name,
            TrackedCharacter.league == league,
        )
    )


async def list_for_user(db: AsyncSession, user_id: int) -> list[TrackedCharacter]:
    """Возвращает список всех отслеживаемых персонажей конкретного пользователя."""
    res = await db.scalars(
        select(TrackedCharacter).where(TrackedCharacter.user_id == user_id)
    )
    return list(res)


async def delete(db: AsyncSession, user_id: int, char_id: int) -> bool:
    """Удаляет запись по char_id"""
    row = await db.get(TrackedCharacter, char_id)
    if row is None or row.user_id != user_id:
        return False
    await db.delete(row)
    await db.commit()
    return True
