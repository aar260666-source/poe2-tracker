import asyncio
from contextlib import asynccontextmanager

from loguru import logger
from playwright.async_api import Browser, Page, async_playwright


class BrowserManager:
    """Управляет жизненным циклом браузера и страницы в Playwright, обеспечивает безопасный
    доступ к странице через контекстный менеджер и корректно освобождает ресурсы."""
    def __init__(self) -> None:
        self._pw = None
        self._browser: Browser | None = None
        self._page: Page | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=True)
        self._page = await self._browser.new_page()

    async def stop(self) -> None:
        if self._page is not None:
            try:
                await self._page.close()
            except Exception as e:
                logger.debug(f"Page already closed: {e}")
            self._page = None
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception as e:
                logger.debug(f"Browser already closed: {e}")
            self._browser = None
        if self._pw is not None:
            try:
                await self._pw.stop()
            except Exception as e:
                logger.debug(f"Playwright already stopped: {e}")
            self._pw = None

    @asynccontextmanager
    async def page(self):
        """Выдаёт страницу под локом; лок освобождается автоматически."""
        assert self._page is not None, "Браузер не запущен"
        async with self._lock:
            yield self._page


browser_manager = BrowserManager()

