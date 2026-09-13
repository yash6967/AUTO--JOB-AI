# tools/lever.py
from __future__ import annotations

import os
from typing import Any

import requests

from tools.greenhouse import parse_job_description

LEVER_POSTINGS_ENDPOINT = "https://api.lever.co/v0/postings/{company}"


class LeverDiscoveryError(RuntimeError):
    """Raised when the Lever Postings API can't produce a usable job list."""


def resolve_company_slug(explicit: str | None = None) -> str:
    """Resolve a Lever company slug from an explicit value or LEVER_COMPANY_SLUG."""
    slug = (explicit or os.getenv("LEVER_COMPANY_SLUG", "")).strip()
    if not slug:
        raise ValueError(
            "Lever company slug is required. Pass one explicitly or set "
            "LEVER_COMPANY_SLUG in .env."
        )
    return slug


def _posting_url(posting: dict[str, Any]) -> str:
    return posting.get("hostedUrl") or posting.get("applyUrl") or ""


def _posting_description(posting: dict[str, Any]) -> str:
    return posting.get("description") or posting.get("descriptionPlain") or ""


class LeverDiscoveryClient:
    """Discovers open postings for a Lever company slug via the public Postings API.

    Distinct from tools.job_router.LeverClient, which only enriches a single
    already-discovered Lever job URL. This one lists an entire company's board.
    """

    def __init__(self, session: requests.Session | None = None, timeout: float = 15.0) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout

    def fetch_jobs(self, company: str | None = None) -> list[dict[str, Any]]:
        company = resolve_company_slug(company)
        endpoint = LEVER_POSTINGS_ENDPOINT.format(company=company)

        try:
            response = self.session.get(endpoint, params={"mode": "json"}, timeout=self.timeout)
            response.raise_for_status()
        except requests.exceptions.RequestException as error:
            raise LeverDiscoveryError(
                f"Lever request failed for company '{company}': {error}"
            ) from error

        try:
            payload = response.json()
        except ValueError as error:
            raise LeverDiscoveryError(
                f"Lever returned a non-JSON response for company '{company}'"
            ) from error

        if payload is None:
            return []
        if not isinstance(payload, list):
            raise LeverDiscoveryError(
                f"Unexpected Lever response for company '{company}': expected a list of "
                f"postings, got {type(payload).__name__}"
            )

        normalized: list[dict[str, Any]] = []
        for posting in payload:
            if not isinstance(posting, dict):
                continue
            url = _posting_url(posting)
            if not url:
                continue
            description = _posting_description(posting)
            categories = posting.get("categories") or {}
            normalized.append({
                "title": posting.get("text", "Untitled role"),
                "company": categories.get("team") or company,
                "url": url,
                "source": "lever",
                "raw_snippet": parse_job_description(description)["raw_text"][:500],
                "job_description": parse_job_description(description),
                "lever_company_slug": company,
                "lever_posting_id": posting.get("id", ""),
                "status": "discovered",
            })
        return normalized