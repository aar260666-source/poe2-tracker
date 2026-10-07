from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


async_engine = create_async_engine(
    url=settings.DATABASE_URL_asyncpg,
    echo=False
)

class Base(DeclarativeBase):
    pass

async_session = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)


async def get_db():
    """Функция асинхронно предоставляет сессию базы данных в контексте менеджера,
    гарантируя её корректное закрытие после использования."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Создаёт таблицы при старте приложения."""
    async with async_engine .begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def check_db() -> bool:
    """Пинг базы: SELECT 1."""
    async with async_engine .connect() as conn:
        return await conn.execute(text("SELECT 1")) is not None


async def delete_tables():
    """Очистить БД после выключения приложения"""
    async with async_engine.begin() as conn:
       await conn.run_sync(Base.metadata.drop_all)