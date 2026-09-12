from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from agent.state import AgentState, JobRecord
from tools.greenhouse import GreenhouseClient


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _log(state: AgentState, event: str, **details: Any) -> list[dict[str, Any]]:
    return [*state.get("processing_log", []), {"at": _now(), "event": event, **details}]


def _note(state: AgentState, component: str, status: str, note: str) -> list[dict[str, str]]:
    return [*state.get("validation_notes", []), {"component": component, "status": status, "note": note}]


def discover_jobs(state: AgentState) -> AgentState:
    criteria = state["hardcoded_criteria"]
    jobs: list[JobRecord] = []
    seen: set[str] = set()

    configured_boards = criteria.get("greenhouse_board_urls", [])
    client = GreenhouseClient(timeout=float(criteria.get("greenhouse_timeout", 15)))
    for board_url in configured_boards:
        parsed = urlparse(board_url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid Greenhouse board URL: {board_url}")
        for job in client.fetch_jobs(board_url, criteria.get("company")):
            key = job["url"].rstrip("/").lower()
            if key not in seen:
                seen.add(key)
                jobs.append(job)

    if not jobs:
        jobs = [
            {
                "title": "Backend Engineer",
                "company": "Example Greenhouse Employer",
                "url": "https://boards.greenhouse.io/example/jobs/1001",
                "source": "greenhouse",
                "raw_snippet": "Mock listing for graph-shell validation.",
                "status": "discovered",
            },
            {
                "title": "Data Engineer",
                "company": "Example Custom Greenhouse Employer",
                "url": "https://jobs.example.com/greenhouse/data-engineer",
                "source": "greenhouse-custom-domain",
                "raw_snippet": "Mock custom-domain listing for routing validation.",
                "status": "discovered",
            },
        ]

    return {
        "discovered_jobs": jobs,
        "status": "jobs_discovered",
        "processing_log": _log(state, "jobs_discovered", count=len(jobs)),
        "validation_notes": _note(
            state,
            "job_discovery",
            "complete" if configured_boards else "placeholder",
            "Fetched and normalized Greenhouse board jobs." if configured_boards else "Using deterministic shell jobs until a Greenhouse board is configured.",
        ),
    }


def prepare_jobs(state: AgentState) -> AgentState:
    threshold = int(state["hardcoded_criteria"].get("minimum_match_score", 60))
    normalized_resume = state.get("normalized_resume", {})
    if not normalized_resume:
        raise ValueError("normalized_resume is empty; load and normalize a resume before running the graph")

    pending: list[JobRecord] = []
    skipped: list[JobRecord] = [*state.get("skipped_jobs", [])]
    prepared: list[JobRecord] = []
    log = state.get("processing_log", [])

    for index, job in enumerate(state.get("discovered_jobs", [])):
        score = 72 if index % 2 == 0 else 45
        prepared_job = {**job, "match_score": score, "prepared_at": _now()}
        if score < threshold:
            prepared_job.update(status="skipped", reason="low_match")
            skipped.append(prepared_job)
            log = [*log, {"at": _now(), "event": "job_skipped", "reason": "low_match", "url": job["url"], "score": score}]
            continue

        prepared_job.update(status="awaiting_approval")
        pending.append(prepared_job)
        prepared.append(prepared_job)
        log = [*log, {"at": _now(), "event": "job_prepared", "url": job["url"], "score": score}]

    first_job = pending[0] if pending else None
    return {
        "pending_jobs": pending,
        "skipped_jobs": skipped,
        "active_job": first_job,
        "match_score": int(first_job["match_score"]) if first_job else 0,
        "job_description": {
            "required_skills": ["Python", "API development"],
            "years_experience": 3,
            "core_responsibilities": ["Build reliable backend services"],
        } if first_job else {},
        "tailored_materials": {
            "resume": "Shell placeholder resume draft.",
            "cover_letter": "Shell placeholder cover letter.",
        } if first_job else {},
        "status": "awaiting_approval" if first_job else "completed",
        "processing_log": log,
        "validation_notes": _note(
            state,
            "preparation_and_tailoring",
            "placeholder",
            "Scores and documents are deterministic shell outputs; Groq is not called in Milestone 1.",
        ),
    }


def wait_for_approval(state: AgentState) -> AgentState:
    if not state.get("active_job"):
        return {"status": "completed"}
    return {
        "status": "approval_received",
        "processing_log": _log(state, "approval_gate_reached", url=state["active_job"]["url"]),
        "validation_notes": _note(
            state,
            "telegram_hitl",
            "placeholder",
            "Telegram approval is not connected; resume this checkpoint with human_decision set to approve or skip.",
        ),
    }


def track_and_submit(state: AgentState) -> AgentState:
    active = state.get("active_job")
    if not active:
        return {"status": "completed"}

    decision = state.get("human_decision", "skip").lower()
    pending = [job for job in state.get("pending_jobs", []) if job.get("url") != active.get("url")]
    applied = [*state.get("applied_jobs", [])]
    skipped = [*state.get("skipped_jobs", [])]
    log = state.get("processing_log", [])

    if decision == "approve":
        completed = {**active, "status": "applied", "submitted_at": _now()}
        applied.append(completed)
        event = "job_applied"
    else:
        completed = {**active, "status": "skipped", "reason": "human_skipped"}
        skipped.append(completed)
        event = "job_skipped"

    next_job = pending[0] if pending else None
    return {
        "pending_jobs": pending,
        "active_job": next_job,
        "human_decision": "",
        "match_score": int(next_job["match_score"]) if next_job else 0,
        "status": "awaiting_approval" if next_job else "completed",
        "applied_jobs": applied,
        "skipped_jobs": skipped,
        "processing_log": [*log, {"at": _now(), "event": event, "url": active["url"]}],
        "validation_notes": _note(
            state,
            "notion_and_submission",
            "placeholder",
            "Notion logging and email/browser submission are not connected; this node records the decision only.",
        ),
    }
