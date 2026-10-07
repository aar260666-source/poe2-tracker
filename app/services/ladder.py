import asyncio
import json
from collections import defaultdict
from urllib.parse import quote, unquote

from bs4 import BeautifulSoup
from redis.asyncio import Redis

from app.core.redis import get_redis
from app.schemas.track import LadderEntryOut, LadderWindowOut
from app.services.browser import browser_manager

BASE = "https://pathofexile2.com"

LEAGUES_TTL = 24 * 60 * 60 # сколько живёт кеш списка лиг
LADDER_TTL = 15 * 60 # сколько живёт кеш лестницы лиги
LOCK_WAIT_TIMEOUT = 30 # сек, сколько ждать своей очереди на лок

CACHE_LEAGUES_KEY = "poe2:leagues"

PAGE_LOAD_TIMEOUT = 15_000 # таймаут ожидания в миллисекундах прогрузка страницы
PAGE_SETTLE_DELAY = 1 # пауза в секундах после появления селектора
DEFAULT_TOP = 1000 # сколько записей лестницы парсить по умолчанию


BROWSER_SEMAPHORE = asyncio.Semaphore(3) # максимум 3 парсинга одновременно

LEAGUE_BLOCK_SEL = "div.league-ladder"
LEAGUE_LINK_SEL = "a.league-ladder__link"
LADDER_ROW_SEL = "table.league-ladder__entries tbody tr.league-ladder__entry"


class LadderUnavailableError(Exception):
    """Сайт лаббера не отвечает или отдал неожиданную страницу."""


_cache_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
# словарь блокировок по ключу кеша, чтобы одну и ту же лигу не парсили параллельно.

def _key_for_ladder(league: str) -> str:
    """Возвращает Redis-ключ вида poe2:ladder:{лига в нижнем регистре}."""
    return f"poe2:ladder:{league.lower()}"


def _lock_for(key: str) -> asyncio.Lock:
    """Возвращает (и при необходимости создаёт) блокировку для конкретного ключа кеша."""
    return _cache_locks[key]


def _safe_int(text: str, default: int = 0) -> int:
    """Конвертирует строку в число, а при ошибке возвращает значение по умолчанию."""
    try:
        return int(text)
    except (ValueError, TypeError):
        return default

def deep_unquote(s: str) -> str:
    # применяем unquote, пока строка меняется
    while True:
        decoded = unquote(s)
        if decoded == s:
            return s
        s = decoded

def _parse_row(row) -> dict | None:
    """
    Разбирает строку таблицы лестницы (<tr>) в словарь с рангом, аккаунтом,
    именем, классом, уровнем и флагом «dead»; возвращает None для мусорных строк.
    """
    tds = row.find_all("td")
    if len(tds) < 5:
        return None

    rank_text = tds[0].get_text(strip=True)
    if not rank_text.isdigit():
        return None

    raw_name = tds[2].get_text(" ", strip=True)
    lowered = raw_name.lower()
    dead = "(dead)" in lowered
    character = raw_name.replace("(dead)", "").replace("(Dead)", "").strip()
    if not character:
        return None

    return {
        "rank": int(rank_text),
        "account": tds[1].get_text(strip=True),
        "character": character,
        "class": tds[3].get_text(strip=True),
        "level": _safe_int(tds[4].get_text(strip=True)),
        "dead": dead,
    }


async def get_leagues() -> list[str]:
    """
    Возвращает список лиг: сначала из Redis-кеша на 24 часа, иначе парсит
    страницу /ladders через браузер и кеширует результат.
    """
    r: Redis = get_redis()
    cached = await r.get(CACHE_LEAGUES_KEY)
    if cached:
        return json.loads(cached)

    try:
        async with browser_manager.page() as page:
            await page.goto(f"{BASE}/ladders", wait_until="networkidle")
            await page.wait_for_selector(LEAGUE_BLOCK_SEL, timeout=PAGE_LOAD_TIMEOUT)
            soup = BeautifulSoup(await page.content(), "html.parser")

            leagues: list[str] = []
            for block in soup.select(LEAGUE_BLOCK_SEL):
                link = block.select_one(LEAGUE_LINK_SEL)
                if not link:
                    continue
                slug = deep_unquote(link.get("href", "").removeprefix("/ladder/"))
                if slug and slug not in leagues:
                    leagues.append(slug)
    except (asyncio.TimeoutError, Exception) as e:
        raise LadderUnavailableError(f"Не удалось получить список лиг: {e}") from e

    await r.set(CACHE_LEAGUES_KEY, json.dumps(leagues), ex=LEAGUES_TTL)
    return leagues


async def parse_ladder(league: str, top: int = DEFAULT_TOP) -> list[dict]:
    """Возвращает топ записей лестницы лиги и сохраняет в Redis."""
    key = _key_for_ladder(league)
    r: Redis = get_redis()

    cached = await r.get(key)
    if cached:
        return json.loads(cached)

    lock = _lock_for(key)
    try:
        await asyncio.wait_for(lock.acquire(), timeout=LOCK_WAIT_TIMEOUT)
    except TimeoutError:
        raise LadderUnavailableError(
            f"Сервер перегружен, запрос лестницы {league} уже выполняется"
        )
    try:
        cached = await r.get(key)
        if cached:
            return json.loads(cached)

        try:
            async with BROWSER_SEMAPHORE:
                async with browser_manager.page() as page:
                    url = f"{BASE}/ladder/{quote(league)}"
                    entries, seen_ranks, page_num = [], set(), 1

                    while len(entries) < top:
                        target = url if page_num == 1 else f"{url}?page={page_num}"
                        await page.goto(target, wait_until="domcontentloaded")  # 3. см. ниже
                        await page.wait_for_selector(LADDER_ROW_SEL, timeout=PAGE_LOAD_TIMEOUT)
                        await asyncio.sleep(PAGE_SETTLE_DELAY)

                        soup = BeautifulSoup(await page.content(), "html.parser")
                        new_rows = 0

                        for row in soup.select(LADDER_ROW_SEL):
                            parsed = _parse_row(row)
                            if parsed is None:
                                continue
                            rank = parsed["rank"]
                            if rank in seen_ranks:
                                continue
                            seen_ranks.add(rank)
                            entries.append(parsed)
                            new_rows += 1

                        if new_rows == 0:
                            break
                        page_num += 1
        except (asyncio.TimeoutError, Exception) as e:
            raise LadderUnavailableError(
                f"Не удалось загрузить лаббер лиги {league}: {e}"
            ) from e

        entries = entries[:top]
        await r.set(key, json.dumps(entries), ex=LADDER_TTL)
        return entries
    finally:
        lock.release()


def _find_entry_two_pass(entries: list[dict], query: str) -> tuple[dict, int] | None:
    """
    Ищет совпадение имени персонажа или аккаунта в списке записей, возвращает
    пару «запись + индекс», при отсутствии точного совпадения возвращает первый «нечёткий» вариант
    """
    q = query.strip().lower()
    if not q:
        return None

    fuzzy: tuple[dict, int] | None = None
    for idx, e in enumerate(entries):
        char = e["character"].lower()
        acc = e["account"].lower()
        if q == char or q == acc:
            return e, idx
        if fuzzy is None and (q in char or q in acc):
            fuzzy = (e, idx)
    return fuzzy


def _to_out(e: dict) -> LadderEntryOut:
    """Превращает внутренний словарь записи в Pydantic-схему LadderEntryOut для ответа API."""
    return LadderEntryOut(
        rank=e["rank"],
        name=e["character"],
        level=e["level"],
        char_class=e["class"],
        dead=e.get("dead", False),
    )


async def find_window(league: str, name: str) -> LadderWindowOut | None:
    """
    Получает лестницу, находит персонажа через _find_entry_two_pass и возвращает «окно»
    из трёх записей — сосед сверху, сам персонаж, сосед снизу — или None, если не найден.
    """
    entries = await parse_ladder(league)
    found = _find_entry_two_pass(entries, name)
    if found is None:
        return None

    entry, idx = found
    above = entries[idx - 1] if idx > 0 else None
    below = entries[idx + 1] if idx + 1 < len(entries) else None
    return LadderWindowOut(
        above=_to_out(above) if above else None,
        current=_to_out(entry),
        below=_to_out(below) if below else None,
    )
