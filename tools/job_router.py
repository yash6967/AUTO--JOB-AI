from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlparse

import requests

from tools.greenhouse import GreenhouseClient, parse_job_description


def _hostname(url: str) -> str:
    return urlparse(url).netloc.lower().split(":", 1)[0]


def is_standard_greenhouse_url(url: str) -> bool:
    return _hostname(url) == "boards.greenhouse.io"


def is_custom_greenhouse_job(job: dict[str, Any]) -> bool:
    return job.get("source") == "greenhouse-custom-domain"


def is_lever_url(url: str) -> bool:
    return _hostname(url).endswith("lever.co")


class LeverClient:
    def __init__(self, session: requests.Session | None = None, timeout: float = 15.0) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout

    def fetch_job(self, job: dict[str, Any]) -> dict[str, Any]:
        parts = [part for part in urlparse(job["url"]).path.split("/") if part]
        if len(parts) < 2:
            raise ValueError(f"Invalid Lever job URL: {job['url']}")
        site, posting_id = parts[-2], parts[-1]
        endpoint = f"https://api.lever.co/v0/postings/{site}/{posting_id}"
        response = self.session.get(endpoint, params={"mode": "json"}, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        description = payload.get("description") or payload.get("descriptionPlain", "")
        return {
            **job,
            "title": payload.get("text", job.get("title", "Untitled role")),
            "company": payload.get("categories", {}).get("team", job.get("company", site)),
            "raw_snippet": description[:500],
            "job_description": parse_job_description(description),
        }


def extract_with_playwright(url: str) -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded")
            return page.locator("body").inner_text()
        finally:
            browser.close()


def route_job(
    job: dict[str, Any],
    *,
    greenhouse_client: GreenhouseClient | None = None,
    lever_client: LeverClient | None = None,
    playwright_extractor: Callable[[str], str] = extract_with_playwright,
) -> dict[str, Any]:
    if job.get("job_description"):
        return {**job, "route": "cached"}

    url = job["url"]
    if is_standard_greenhouse_url(url) or is_custom_greenhouse_job(job):
        client = greenhouse_client or GreenhouseClient()
        return {**client.fetch_job(job), "route": "greenhouse"}
    if is_lever_url(url) or job.get("source") == "lever":
        client = lever_client or LeverClient()
        return {**client.fetch_job(job), "route": "lever"}

    raw_text = playwright_extractor(url)
    return {
        **job,
        "raw_snippet": raw_text[:500],
        "job_description": parse_job_description(raw_text),
        "route": "playwright",
    }