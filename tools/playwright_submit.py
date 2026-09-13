from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

SCREENSHOT_DIR = Path("runtime/screenshots")

FIELD_HINTS: dict[str, list[str]] = {
    "first_name": ["first"],
    "last_name": ["last"],
    "email": ["email"],
    "phone": ["phone", "tel"],
}


class SubmissionError(RuntimeError):
    """Raised only when submission is fundamentally impossible (e.g. no URL)."""


def _fuzzy_selectors(hints: list[str], tag: str = "input") -> list[str]:
    return [f'{tag}[{attr}*="{hint}" i]' for hint in hints for attr in ("name", "placeholder", "aria-label")]


def _split_name(full_name: str) -> tuple[str, str]:
    # The resume schema only stores one "name" field, not first/last separately.
    parts = full_name.strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _job_id(job: dict[str, Any]) -> str:
    for key in ("greenhouse_job_id", "lever_posting_id", "url"):
        value = job.get(key)
        if value:
            return "".join(char if char.isalnum() else "_" for char in str(value))[-80:]
    return "job"


async def _fill_first_match(page: Any, hints: list[str], value: str, label: str) -> None:
    if not value:
        logger.info("Skipping %s: no value supplied", label)
        return
    for selector in _fuzzy_selectors(hints):
        locator = page.locator(selector)
        try:
            if await locator.count():
                await locator.first.fill(value)
                return
        except PlaywrightError as error:
            logger.warning("Selector %s failed for %s: %s", selector, label, error)
    logger.warning("No matching field found for %s; leaving it blank", label)


async def submit_application(
    job: dict[str, Any],
    resume: dict[str, Any],
    materials: dict[str, Any],
    resume_pdf: str | None = None,
    *,
    browser: Any | None = None,
) -> dict[str, Any]:
    url = job.get("url")
    if not url:
        raise SubmissionError("Job is missing a URL to submit to")

    contact = resume.get("contact", {})
    first_name, last_name = _split_name(contact.get("name", ""))
    job_id = _job_id(job)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    before_path = str(SCREENSHOT_DIR / f"{job_id}_before.png")
    after_path = str(SCREENSHOT_DIR / f"{job_id}_after.png")

    async def _run(active_browser: Any) -> dict[str, Any]:
        page = await active_browser.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)

        await _fill_first_match(page, FIELD_HINTS["first_name"], first_name, "first name")
        await _fill_first_match(page, FIELD_HINTS["last_name"], last_name, "last name")
        await _fill_first_match(page, FIELD_HINTS["email"], contact.get("email", ""), "email")
        await _fill_first_match(page, FIELD_HINTS["phone"], contact.get("phone", ""), "phone")

        if resume_pdf:
            file_input = page.locator('input[type="file"]')
            try:
                if await file_input.count():
                    await file_input.first.set_input_files(resume_pdf)
                else:
                    logger.warning("No file input found for resume upload")
            except PlaywrightError as error:
                logger.warning("Resume upload failed: %s", error)

        cover_letter = materials.get("cover_letter", "")
        if cover_letter:
            textarea = page.locator("textarea:visible")
            try:
                if await textarea.count():
                    await textarea.first.fill(cover_letter)
                else:
                    logger.warning("No visible textarea found for cover letter")
            except PlaywrightError as error:
                logger.warning("Cover letter fill failed: %s", error)

        await page.screenshot(path=before_path, full_page=True)

        submit_button = page.locator('button[type="submit"], input[type="submit"]')
        if await submit_button.count():
            await submit_button.first.click()
            await page.screenshot(path=after_path, full_page=True)
            return {"status": "applied", "screenshot": after_path, "screenshot_before": before_path}

        logger.warning("No submit button found; screenshot taken but form not submitted")
        await page.screenshot(path=after_path, full_page=True)
        return {
            "status": "incomplete",
            "reason": "no_submit_button",
            "screenshot": after_path,
            "screenshot_before": before_path,
        }

    if browser is not None:
        return await _run(browser)

    async with async_playwright() as playwright:
        launched = await playwright.chromium.launch(headless=True)
        try:
            return await _run(launched)
        finally:
            await launched.close()
