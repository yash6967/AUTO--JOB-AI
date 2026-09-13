# tests/test_lever.py
from unittest.mock import Mock

import pytest
import requests

from tools.lever import LeverDiscoveryClient, LeverDiscoveryError, resolve_company_slug


def _posting(**overrides):
    base = {
        "id": "posting-1",
        "text": "Backend Engineer",
        "hostedUrl": "https://jobs.lever.co/acme/posting-1",
        "categories": {"team": "Engineering"},
        "descriptionPlain": "Build Python and SQL services. 3+ years experience required.",
    }
    base.update(overrides)
    return base


def test_fetch_jobs_normalizes_postings_list():
    response = Mock()
    response.json.return_value = [_posting()]
    response.raise_for_status.return_value = None
    session = Mock()
    session.get.return_value = response

    jobs = LeverDiscoveryClient(session=session).fetch_jobs("acme")

    assert jobs[0]["title"] == "Backend Engineer"
    assert jobs[0]["company"] == "Engineering"
    assert jobs[0]["source"] == "lever"
    assert jobs[0]["lever_company_slug"] == "acme"
    assert jobs[0]["lever_posting_id"] == "posting-1"
    assert jobs[0]["job_description"]["required_skills"] == ["Python", "SQL"]
    assert jobs[0]["job_description"]["years_experience"] == 3
    session.get.assert_called_once_with(
        "https://api.lever.co/v0/postings/acme",
        params={"mode": "json"},
        timeout=15.0,
    )


def test_fetch_jobs_returns_empty_list_for_no_postings():
    response = Mock()
    response.json.return_value = []
    response.raise_for_status.return_value = None
    session = Mock()
    session.get.return_value = response

    assert LeverDiscoveryClient(session=session).fetch_jobs("acme") == []


def test_fetch_jobs_raises_clear_error_for_malformed_response():
    response = Mock()
    response.json.return_value = {"code": "NotFound", "message": "Unknown site"}
    response.raise_for_status.return_value = None
    session = Mock()
    session.get.return_value = response

    with pytest.raises(LeverDiscoveryError):
        LeverDiscoveryClient(session=session).fetch_jobs("does-not-exist")


def test_fetch_jobs_wraps_http_errors():
    session = Mock()
    session.get.side_effect = requests.exceptions.ConnectionError("boom")

    with pytest.raises(LeverDiscoveryError):
        LeverDiscoveryClient(session=session).fetch_jobs("acme")


def test_fetch_jobs_skips_postings_missing_url():
    response = Mock()
    response.json.return_value = [_posting(hostedUrl="", applyUrl="")]
    response.raise_for_status.return_value = None
    session = Mock()
    session.get.return_value = response

    assert LeverDiscoveryClient(session=session).fetch_jobs("acme") == []


def test_resolve_company_slug_prefers_explicit_then_env(monkeypatch):
    monkeypatch.setenv("LEVER_COMPANY_SLUG", "from-env")
    assert resolve_company_slug("explicit-slug") == "explicit-slug"
    assert resolve_company_slug(None) == "from-env"

    monkeypatch.delenv("LEVER_COMPANY_SLUG", raising=False)
    with pytest.raises(ValueError):
        resolve_company_slug(None)