from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger
from starlette.responses import FileResponse

from app.api.v1.auth import router as users
from app.core.database import init_db, check_db, delete_tables
from app.core.redis import check_redis, close_redis
from app.services.browser import browser_manager
from app.api.v1.track import router as track
from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    await init_db()
    logger.info("База данных: таблицы созданы")
    await browser_manager.start()

    if await check_db():
        logger.info("Postgres: подключение ок")
    if await check_redis():
        logger.info("Redis: подключение ок")

    yield

    await browser_manager.stop()
    await close_redis()
    logger.info("Redis закрыт")
    # await delete_tables()
    # print("База очищена")


app = FastAPI(title="PoE2 Ladder Tracker", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse("app/static/index.html")


app.include_router(users, prefix="/api/v1")
app.include_router(track, prefix="/api/v1")

