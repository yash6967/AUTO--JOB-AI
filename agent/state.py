from __future__ import annotations

from typing import Any, TypedDict


class JobRecord(TypedDict, total=False):
    title: str
    company: str
    url: str
    source: str
    raw_snippet: str
    job_description: dict[str, Any]
    status: str
    match_score: int
    reason: str
    prepared_at: str
    submitted_at: str


class ValidationNote(TypedDict):
    component: str
    status: str
    note: str


class AgentState(TypedDict, total=False):
    hardcoded_criteria: dict[str, Any]
    discovered_jobs: list[JobRecord]
    pending_jobs: list[JobRecord]
    active_job: JobRecord | None
    job_description: dict[str, Any]
    match_score: int
    tailored_materials: dict[str, Any]
    human_decision: str
    skipped_jobs: list[JobRecord]
    applied_jobs: list[JobRecord]
    processing_log: list[dict[str, Any]]
    validation_notes: list[ValidationNote]
    status: str
    resume_path: str
    normalized_resume: dict[str, Any]


def initial_state(
    criteria: dict[str, Any],
    resume_path: str,
) -> AgentState:
    return {
        "hardcoded_criteria": criteria,
        "discovered_jobs": [],
        "pending_jobs": [],
        "active_job": None,
        "job_description": {},
        "match_score": 0,
        "tailored_materials": {},
        "human_decision": "",
        "skipped_jobs": [],
        "applied_jobs": [],
        "processing_log": [],
        "validation_notes": [],
        "status": "initialized",
        "resume_path": resume_path,
        "normalized_resume": {},
    }
