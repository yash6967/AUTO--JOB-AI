from __future__ import annotations

import os
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import requests


class _HTMLTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self.parts.append(text)

    def text(self) -> str:
        return " ".join(self.parts)


@dataclass(frozen=True)
class GreenhouseBoard:
    url: str
    token: str
    source: str


def parse_board_url(board_url: str) -> GreenhouseBoard:
    parsed = urlparse(board_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid Greenhouse board URL: {board_url}")

    path_parts = [part for part in parsed.path.split("/") if part]
    if not path_parts:
        raise ValueError(f"Greenhouse board URL is missing a board token: {board_url}")

    token = path_parts[0]
    source = "greenhouse" if parsed.netloc.lower() == "boards.greenhouse.io" else "greenhouse-custom-domain"
    return GreenhouseBoard(url=board_url.rstrip("/"), token=token, source=source)


def _description_text(content: str) -> str:
    parser = _HTMLTextParser()
    parser.feed(content or "")
    return parser.text()


def parse_job_description(content: str) -> dict[str, Any]:
    text = _description_text(content)
    lines = [line.strip(" -*\t") for line in re.split(r"[\r\n]+", text) if line.strip()]
    skills: list[str] = []
    skill_pattern = re.compile(
        r"\b(?:Python|Java|JavaScript|TypeScript|Go|Rust|SQL|AWS|Azure|GCP|Docker|Kubernetes|FastAPI|Django|React|Spark|Snowflake)\b",
        re.IGNORECASE,
    )
    for match in skill_pattern.finditer(text):
        skill = match.group(0)
        if skill.lower() not in {item.lower() for item in skills}:
            skills.append(skill)

    years_match = re.search(r"(?:at least\s+)?(\d+)\+?\s+years?", text, re.IGNORECASE)
    responsibility_lines = [
        line for line in lines
        if re.search(r"\b(build|design|develop|maintain|lead|own|manage|collaborate|implement)\b", line, re.IGNORECASE)
    ]
    return {
        "required_skills": skills,
        "years_experience": int(years_match.group(1)) if years_match else None,
        "core_responsibilities": responsibility_lines[:10],
        "raw_text": text,
    }


class GreenhouseClient:
    def __init__(self, session: requests.Session | None = None, timeout: float = 15.0) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout

    def fetch_jobs(self, board_url: str, company: str | None = None) -> list[dict[str, Any]]:
        board = parse_board_url(board_url)
        endpoint = f"https://boards-api.greenhouse.io/v1/boards/{board.token}/jobs"
        response = self.session.get(endpoint, params={"content": "true"}, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        normalized: list[dict[str, Any]] = []
        for job in payload.get("jobs", []):
            content = job.get("content", "")
            normalized.append({
                "title": job.get("title", "Untitled role"),
                "company": company or payload.get("name") or board.token,
                "url": job.get("absolute_url") or f"{board.url}/jobs/{job.get('id', '')}",
                "source": board.source,
                "raw_snippet": _description_text(content)[:500],
                "job_description": parse_job_description(content),
                "greenhouse_board_token": board.token,
                "greenhouse_job_id": str(job.get("id", "")),
                "status": "discovered",
            })
        return normalized

    def search_jobs(self, query: str, company: str | None = None, max_results: int = 25) -> list[dict[str, Any]]:
        api_key = os.getenv("EXA_API_KEY")
        if not api_key or api_key.strip().lower() in {"your_key", "your_api_key", "changeme"}:
            raise ValueError("EXA_API_KEY is missing or still set to a placeholder; remove EXA_API_KEY=your_key and configure the real key in .env")
        response = self.session.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json={"query": f"{query} site:boards.greenhouse.io", "numResults": max_results, "type": "auto"},
            timeout=self.timeout,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            if response.status_code in {401, 403}:
                raise ValueError("EXA_API_KEY was rejected by Exa; verify the key in .env and do not override it with EXA_API_KEY=your_key") from error
            raise
        jobs: list[dict[str, Any]] = []
        for result in response.json().get("results", []):
            url = result.get("url", "")
            if "boards.greenhouse.io/" not in url or "/jobs/" not in url:
                continue
            try:
                jobs.append(self.fetch_job({"url": url, "company": company, "source": "greenhouse"}))
            except (KeyError, ValueError, requests.RequestException):
                continue
        return jobs

    def fetch_job(self, job: dict[str, Any]) -> dict[str, Any]:
        board_token = job.get("greenhouse_board_token")
        job_id = job.get("greenhouse_job_id")
        if not board_token or not job_id:
            parsed = parse_board_url(job["url"])
            path_parts = [part for part in urlparse(job["url"]).path.split("/") if part]
            board_token = parsed.token
            job_id = path_parts[-1]

        endpoint = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}"
        response = self.session.get(endpoint, params={"content": "true"}, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        content = payload.get("content", "")
        return {
            **job,
            "title": payload.get("title", job.get("title", "Untitled role")),
            "company": job.get("company") or payload.get("company_name") or board_token,
            "greenhouse_board_token": board_token,
            "greenhouse_job_id": str(job_id),
            "raw_snippet": _description_text(content)[:500],
            "job_description": parse_job_description(content),
        }