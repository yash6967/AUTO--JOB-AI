from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from agent.state import AgentState, JobRecord
from tools.greenhouse import GreenhouseClient
from tools.job_router import route_job
from tools.job_parser import GroqRequirementsParser
from tools.fit_analyzer import GroqFitAnalyzer, deterministic_analysis, deterministic_materials
from server.telegram import TelegramClient
from tools.submission import EmailSubmitter, PlaywrightSubmitter
from tools.tracking import NotionTracker


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
                if criteria.get("max_jobs") and len(jobs) >= int(criteria["max_jobs"]):
                    break
        if criteria.get("max_jobs") and len(jobs) >= int(criteria["max_jobs"]):
            break

    if not jobs:
        jobs = [
            {
                "title": "Backend Engineer",
                "company": "Example Greenhouse Employer",
                "url": "https://boards.greenhouse.io/example/jobs/1001",
                "source": "greenhouse",
                "raw_snippet": "Mock listing for graph-shell validation.",
                "mock": True,
                "status": "discovered",
            },
            {
                "title": "Data Engineer",
                "company": "Example Custom Greenhouse Employer",
                "url": "https://jobs.example.com/greenhouse/data-engineer",
                "source": "greenhouse-custom-domain",
                "raw_snippet": "Mock custom-domain listing for routing validation.",
                "mock": True,
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
        score = (72 if index % 2 == 0 else 45) if job.get("mock") else None
        prepared_job = {
            **job,
            **({"match_score": score} if score is not None else {}),
            "prepared_at": _now(),
            "thread_id": state["hardcoded_criteria"].get("thread_id", "local-run"),
        }
        if score is not None and score < threshold:
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
        "match_score": int(first_job.get("match_score", 0)) if first_job else 0,
        "job_description": {},
        "tailored_materials": {},
        "status": "awaiting_approval" if first_job else "completed",
        "processing_log": log,
        "validation_notes": _note(
            state,
            "preparation_and_tailoring",
            "placeholder",
            "Real jobs are scored and tailored after routing; mock jobs retain deterministic shell scores.",
        ),
    }


def route_and_parse_job(state: AgentState) -> AgentState:
    active = state.get("active_job")
    if not active:
        return {"status": "completed"}

    parser_status = "deterministic"
    if active.get("mock"):
        routed = {
            **active,
            "route": "mock",
            "job_description": {
                "required_skills": [],
                "years_experience": None,
                "core_responsibilities": [active.get("raw_snippet", "")],
                "raw_text": active.get("raw_snippet", ""),
            },
        }
    else:
        routed = route_job(active)
        if state["hardcoded_criteria"].get("groq_enabled", True) and os.getenv("GROQ_API_KEY"):
            raw_text = routed["job_description"].get("raw_text", routed.get("raw_snippet", ""))
            try:
                parsed = GroqRequirementsParser().parse(raw_text)
            except Exception:
                parser_status = "deterministic_fallback"
            else:
                routed = {
                    **routed,
                    "job_description": {**parsed, "raw_text": raw_text},
                }
                parser_status = "groq"

    pending = [routed if job.get("url") == active.get("url") else job for job in state.get("pending_jobs", [])]
    return {
        "active_job": routed,
        "pending_jobs": pending,
        "job_description": routed["job_description"],
        "status": "awaiting_approval",
        "processing_log": _log(
            state,
            "job_routed",
            url=active["url"],
            route=routed.get("route", "unknown"),
            raw_text_length=len(routed["job_description"].get("raw_text", "")),
        ),
        "validation_notes": _note(
            state,
            "job_routing_and_parsing",
            "complete" if routed.get("route") != "mock" else "placeholder",
            f"Routed job through {routed.get('route', 'unknown')} and parsed requirements with {parser_status} parser.",
        ),
    }


def score_and_tailor(state: AgentState) -> AgentState:
    active = state.get("active_job")
    if not active:
        return {"status": "completed"}

    criteria = state["hardcoded_criteria"]
    resume = state.get("normalized_resume", {})
    description = state.get("job_description", {})
    analyzer_status = "deterministic"
    if active.get("mock"):
        analysis = {
            "match_score": int(active.get("match_score", 0)),
            "matching_skills": [],
            "missing_requirements": [],
            "rationale": "Deterministic shell score.",
        }
        materials = {"resume_bullets": [], "cover_letter": "Shell placeholder cover letter."}
    elif criteria.get("groq_enabled", True) and os.getenv("GROQ_API_KEY"):
        analyzer = GroqFitAnalyzer()
        try:
            analysis = analyzer.analyze(resume, description)
        except Exception:
            analysis = deterministic_analysis(resume, description)
            materials = deterministic_materials(resume)
            analyzer_status = "deterministic_fallback"
        else:
            try:
                materials = analyzer.tailor(resume, description, analysis)
            except Exception:
                materials = deterministic_materials(resume)
                analyzer_status = "groq_with_deterministic_tailoring_fallback"
            else:
                analyzer_status = "groq"
    else:
        analysis = deterministic_analysis(resume, description)
        materials = deterministic_materials(resume)

    score = int(analysis["match_score"])
    threshold = int(criteria.get("minimum_match_score", 60))
    updated = {**active, "match_score": score, "fit_analysis": analysis}
    pending = [updated if job.get("url") == active.get("url") else job for job in state.get("pending_jobs", [])]
    if score < threshold:
        skipped = [*state.get("skipped_jobs", []), {**updated, "status": "skipped", "reason": "low_match"}]
        pending = [job for job in pending if job.get("url") != active.get("url")]
        next_job = pending[0] if pending else None
        return {
            "pending_jobs": pending,
            "skipped_jobs": skipped,
            "active_job": next_job,
            "match_score": int(next_job.get("match_score", 0)) if next_job else 0,
            "tailored_materials": {},
            "status": "awaiting_approval" if next_job else "completed",
            "processing_log": _log(state, "job_skipped", url=active["url"], reason="low_match", score=score),
            "validation_notes": _note(state, "match_scoring", "complete", f"Score {score} below threshold {threshold} using {analyzer_status} analysis."),
        }

    return {
        "active_job": updated,
        "pending_jobs": pending,
        "skipped_jobs": [*state.get("skipped_jobs", [])],
        "match_score": score,
        "tailored_materials": materials,
        "status": "awaiting_approval",
        "processing_log": _log(state, "job_prepared", url=active["url"], score=score),
        "validation_notes": _note(state, "match_scoring_and_tailoring", "complete", f"Scored and tailored with {analyzer_status} analysis."),
    }


def wait_for_approval(state: AgentState) -> AgentState:
    if not state.get("active_job"):
        return {"status": "completed"}
    processing_log = _log(state, "approval_gate_reached", url=state["active_job"]["url"])
    validation_notes = _note(
        state,
        "telegram_hitl",
        "placeholder",
        "Telegram approval is not connected; resume this checkpoint with human_decision set to approve or skip.",
    )
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id and not state["active_job"].get("mock"):
        TelegramClient(token, chat_id).send_approval(
            state["active_job"],
            state.get("tailored_materials", {}).get("cover_letter", ""),
        )
        processing_log = [*processing_log, {"at": _now(), "event": "telegram_approval_sent", "url": state["active_job"]["url"]}]
        validation_notes = _note(state, "telegram_hitl", "complete", "Approval message sent with approve and skip actions.")
    return {
        "status": "awaiting_approval",
        "processing_log": processing_log,
        "validation_notes": validation_notes,
    }


def track_and_submit(state: AgentState) -> AgentState:
    active = state.get("active_job")
    if not active:
        return {"status": "completed"}

    decision = state.get("human_decision", "skip").lower()
    pending = [job for job in state.get("pending_jobs", []) if job.get("url") != active.get("url")]
    applied = [*state.get("applied_jobs", [])]
    skipped = [*state.get("skipped_jobs", [])]
    error_logs = [*state.get("error_logs", [])]
    confirmation: dict[str, Any] | None = None
    log = state.get("processing_log", [])

    if decision == "approve":
        submission_result: dict[str, Any] = {"channel": "dry_run"}
        submission_mode = os.getenv("SUBMISSION_MODE", "dry_run").lower()
        try:
            if submission_mode == "email":
                submitter = EmailSubmitter(
                    os.environ["SMTP_HOST"],
                    int(os.getenv("SMTP_PORT", "587")),
                    os.environ["SMTP_USERNAME"],
                    os.environ["SMTP_PASSWORD"],
                )
                submission_result = submitter.submit(
                    active,
                    state.get("normalized_resume", {}),
                    state.get("tailored_materials", {}),
                    state.get("tailored_materials", {}).get("resume_pdf"),
                )
            elif submission_mode == "playwright":
                submission_result = PlaywrightSubmitter().submit(
                    active,
                    state.get("normalized_resume", {}),
                    state.get("tailored_materials", {}),
                    state.get("tailored_materials", {}).get("resume_pdf"),
                )
            elif submission_mode != "dry_run":
                raise ValueError("SUBMISSION_MODE must be dry_run, email, or playwright")
        except Exception as error:
            error_entry = {
                "at": _now(),
                "component": "submission",
                "channel": submission_mode,
                "job_url": active.get("url", ""),
                "job_title": active.get("title", ""),
                "error_type": type(error).__name__,
                "message": str(error),
            }
            error_logs.append(error_entry)
            completed = {**active, "status": "submission_failed", "reason": "submission_error"}
            event = "submission_failed"
        else:
            completed = {**active, "status": "applied", "submitted_at": _now()}
            applied.append(completed)
            confirmation = {
                "status": "applied",
                "message": "Application submitted successfully.",
                "job_title": active.get("title", ""),
                "company": active.get("company", ""),
                "url": active.get("url", ""),
                "submitted_at": completed["submitted_at"],
                "channel": submission_result.get("channel", submission_mode),
            }
            event = "job_applied"
    else:
        completed = {**active, "status": "skipped", "reason": "human_skipped"}
        skipped.append(completed)
        event = "job_skipped"

    notion_token = os.getenv("NOTION_TOKEN")
    notion_database = os.getenv("NOTION_DATABASE_ID")
    tracking_status = "disabled"
    notion_enabled = state.get("hardcoded_criteria", {}).get("notion_enabled", False)
    if notion_enabled and notion_token and notion_database:
        decision_name = "approved" if decision == "approve" else "skipped"
        try:
            NotionTracker(notion_token, notion_database).record_decision(completed, decision_name)
        except Exception as error:
            error_logs.append({
                "at": _now(),
                "component": "notion_tracking",
                "job_url": active.get("url", ""),
                "job_title": active.get("title", ""),
                "error_type": type(error).__name__,
                "message": str(error),
            })
            tracking_status = "error"
        else:
            tracking_status = "notion"

    next_job = pending[0] if pending else None
    return {
        "pending_jobs": pending,
        "active_job": next_job,
        "human_decision": "",
        "match_score": int(next_job["match_score"]) if next_job else 0,
        "status": "awaiting_approval" if next_job else "completed",
        "applied_jobs": applied,
        "error_logs": error_logs,
        "confirmation": confirmation,
        "skipped_jobs": skipped,
        "processing_log": [
            *log,
            {
                "at": _now(),
                "event": event,
                "url": active["url"],
                "submission": submission_result if decision == "approve" else None,
                "tracking": tracking_status,
            },
        ],
        "validation_notes": _note(
            state,
            "notion_and_submission",
            "complete" if tracking_status in {"notion", "disabled"} else "error",
            f"Submission and tracking completed with submission channel {submission_result.get('channel', 'none')} and tracking status {tracking_status}.",
        ),
    }
