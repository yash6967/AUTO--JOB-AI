from __future__ import annotations

from typing import Any

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

DEFAULT_TIMEOUT_MS = 30_000


async def _extract_page_text(page: Any, url: str, timeout_ms: int) -> dict[str, Any]:
    try:
        await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        return {"raw_text": "", "error": "timeout"}
    except PlaywrightError as error:
        return {"raw_text": "", "error": f"navigation_error: {error}"}

    try:
        raw_text = (await page.locator("body").inner_text()).strip()
    except PlaywrightError as error:
        return {"raw_text": "", "error": f"extraction_error: {error}"}

    if not raw_text:
        return {"raw_text": "", "error": "blank_page"}
    return {"raw_text": raw_text}


async def scrape_job_page(
    url: str,
    *,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    browser: Any | None = None,
) -> dict[str, Any]:
    """Scrape a job posting page for raw text, to be handed to Groq for parsing.

    Never raises for ordinary scraping failures (timeout, navigation error, blank
    page) -- those come back as {"raw_text": "", "error": "..."} instead of
    crashing the agent. Pass `browser` (e.g. a mock, or one you already launched)
    to skip the real Chromium launch entirely.
    """
    if not url or not url.strip():
        raise ValueError("A job URL is required to scrape")

    if browser is not None:
        page = await browser.new_page()
        return await _extract_page_text(page, url, timeout_ms)

    async with async_playwright() as playwright:
        launched = await playwright.chromium.launch(headless=True)
        try:
            page = await launched.new_page()
            return await _extract_page_text(page, url, timeout_ms)
        finally:
            await launched.close()
