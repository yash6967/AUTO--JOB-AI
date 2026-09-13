import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from tools.playwright_scrape import scrape_job_page
from tools.playwright_submit import SubmissionError, submit_application


def _run(coro):
    return asyncio.run(coro)


# --- playwright_scrape ---

def _scrape_browser(page: Mock) -> Mock:
    browser = Mock()
    browser.new_page = AsyncMock(return_value=page)
    return browser


def test_scrape_returns_raw_text_on_success():
    page = Mock()
    page.goto = AsyncMock()
    locator = Mock()
    locator.inner_text = AsyncMock(return_value="  Some job text  ")
    page.locator = Mock(return_value=locator)

    result = _run(scrape_job_page("https://example.com/job", browser=_scrape_browser(page)))

    assert result == {"raw_text": "Some job text"}


def test_scrape_handles_timeout():
    page = Mock()
    page.goto = AsyncMock(side_effect=PlaywrightTimeoutError("Timeout 30000ms exceeded"))

    result = _run(scrape_job_page("https://example.com/job", browser=_scrape_browser(page)))

    assert result == {"raw_text": "", "error": "timeout"}


def test_scrape_handles_navigation_error():
    page = Mock()
    page.goto = AsyncMock(side_effect=PlaywrightError("net::ERR_NAME_NOT_RESOLVED"))

    result = _run(scrape_job_page("https://example.com/job", browser=_scrape_browser(page)))

    assert result["raw_text"] == ""
    assert result["error"].startswith("navigation_error")


def test_scrape_handles_blank_page():
    page = Mock()
    page.goto = AsyncMock()
    locator = Mock()
    locator.inner_text = AsyncMock(return_value="   ")
    page.locator = Mock(return_value=locator)

    result = _run(scrape_job_page("https://example.com/job", browser=_scrape_browser(page)))

    assert result == {"raw_text": "", "error": "blank_page"}


def test_scrape_requires_url():
    with pytest.raises(ValueError):
        _run(scrape_job_page(""))


# --- playwright_submit ---

class _LocatorStub:
    def __init__(self, count: int = 1):
        self._count = count
        self.first = self
        self.fill = AsyncMock()
        self.set_input_files = AsyncMock()
        self.click = AsyncMock()

    async def count(self):
        return self._count


def _submit_page(selector_counts: dict[str, int], default_count: int = 1):
    stubs: dict[str, _LocatorStub] = {}

    def locator_factory(selector: str):
        count = default_count
        for key, value in selector_counts.items():
            if key in selector:
                count = value
                break
        if selector not in stubs:
            stubs[selector] = _LocatorStub(count=count)
        return stubs[selector]

    page = Mock()
    page.goto = AsyncMock()
    page.screenshot = AsyncMock()
    page.locator = Mock(side_effect=locator_factory)
    return page, stubs


def _submit_browser(page: Mock) -> Mock:
    browser = Mock()
    browser.new_page = AsyncMock(return_value=page)
    return browser


JOB = {"url": "https://example.com/apply", "greenhouse_job_id": "42"}
RESUME = {"contact": {"name": "Ada Lovelace", "email": "ada@example.com", "phone": "555-1234"}}
MATERIALS = {"cover_letter": "I would love to join your team."}


def test_submit_success_fills_fields_uploads_resume_and_submits(monkeypatch, tmp_path):
    import tools.playwright_submit as module
    monkeypatch.setattr(module, "SCREENSHOT_DIR", tmp_path)
    page, stubs = _submit_page({})  # everything found (count=1)

    result = _run(submit_application(JOB, RESUME, MATERIALS, "resume.pdf", browser=_submit_browser(page)))

    assert result["status"] == "applied"
    assert result["screenshot"].endswith("_after.png")
    assert result["screenshot_before"].endswith("_before.png")
    assert page.screenshot.call_count == 2
    filled = [stub.fill for stub in stubs.values() if stub.fill.await_count]
    assert len(filled) == 5  # first name, last name, email, phone, and the cover-letter textarea
    resume_stub = stubs['input[type="file"]']
    resume_stub.set_input_files.assert_awaited_once_with("resume.pdf")
    submit_stub = stubs['button[type="submit"], input[type="submit"]']
    submit_stub.click.assert_awaited_once()


def test_submit_handles_missing_contact_fields_without_crashing(monkeypatch, tmp_path):
    import tools.playwright_submit as module
    monkeypatch.setattr(module, "SCREENSHOT_DIR", tmp_path)
    page, _ = _submit_page({})

    result = _run(submit_application(JOB, {"contact": {}}, {}, None, browser=_submit_browser(page)))

    assert result["status"] == "applied"


def test_submit_handles_no_matching_selectors_without_crashing(monkeypatch, tmp_path):
    import tools.playwright_submit as module
    monkeypatch.setattr(module, "SCREENSHOT_DIR", tmp_path)
    # Every contact field selector reports 0 matches; submit button still found.
    page, _ = _submit_page({"name*=": 0, "placeholder*=": 0, "aria-label*=": 0, 'type="submit"': 1})

    result = _run(submit_application(JOB, RESUME, MATERIALS, None, browser=_submit_browser(page)))

    assert result["status"] == "applied"


def test_submit_reports_incomplete_when_no_submit_button(monkeypatch, tmp_path):
    import tools.playwright_submit as module
    monkeypatch.setattr(module, "SCREENSHOT_DIR", tmp_path)
    page, _ = _submit_page({'type="submit"': 0})

    result = _run(submit_application(JOB, RESUME, MATERIALS, None, browser=_submit_browser(page)))

    assert result["status"] == "incomplete"
    assert result["reason"] == "no_submit_button"


def test_submit_requires_job_url():
    with pytest.raises(SubmissionError):
        _run(submit_application({}, {}, {}))
