from unittest.mock import Mock, patch

from tools.submission import EmailSubmitter
from tools.tracking import NotionTracker
from agent.nodes import track_and_submit


def test_notion_tracker_creates_decision_page():
    client = Mock()
    tracker = NotionTracker("token", "database", client=client)
    tracker.record_decision({"title": "Backend Engineer", "company": "Acme", "url": "https://example.com", "match_score": 80}, "approved")

    payload = client.pages.create.call_args.kwargs
    assert payload["parent"] == {"database_id": "database"}
    assert payload["properties"]["Job Title"]["title"][0]["text"]["content"] == "Backend Engineer"
    assert payload["properties"]["Status"]["status"]["name"] == "Approved"


def test_notion_tracker_normalizes_missing_provider_fields():
    client = Mock()
    tracker = NotionTracker("token", "database", client=client)
    tracker.record_decision({"title": None, "company": None, "url": None, "match_score": None}, "approved")

    payload = client.pages.create.call_args.kwargs["properties"]
    assert payload["Job Title"]["title"][0]["text"]["content"] == "Unknown role"
    assert payload["Company"]["rich_text"][0]["text"]["content"] == "Unknown company"
    assert payload["Match Score"]["number"] == 0
    assert payload["Job URL"]["url"] is None


def test_email_submitter_sends_factual_materials_without_network():
    submitter = EmailSubmitter("smtp.example.com", 587, "user@example.com", "password")
    with patch("tools.submission.smtplib.SMTP") as smtp:
        submitter.submit(
            {"title": "Backend Engineer", "application_email": "jobs@example.com"},
            {"contact": {"name": "Candidate"}},
            {"cover_letter": "I am applying."},
        )
    smtp.return_value.send_message.assert_called_once()


def test_approved_job_is_recorded_as_applied_in_dry_run(monkeypatch):
    monkeypatch.setenv("SUBMISSION_MODE", "dry_run")
    result = track_and_submit({
        "hardcoded_criteria": {"notion_enabled": False, "submission_mode": "dry_run"},
        "active_job": {"url": "https://example.com/job", "title": "Backend Engineer", "match_score": 80},
        "pending_jobs": [{"url": "https://example.com/job", "title": "Backend Engineer", "match_score": 80}],
        "human_decision": "approve",
        "normalized_resume": {},
        "tailored_materials": {"cover_letter": "Apply."},
        "applied_jobs": [],
        "skipped_jobs": [],
        "processing_log": [],
        "validation_notes": [],
    })

    assert result["applied_jobs"][0]["status"] == "applied"
    assert result["processing_log"][-1]["submission"]["channel"] == "dry_run"
    assert result["confirmation"]["status"] == "applied"


def test_submission_failure_is_stored_in_error_logs(monkeypatch):
    monkeypatch.setenv("SUBMISSION_MODE", "email")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    result = track_and_submit({
        "hardcoded_criteria": {"notion_enabled": False, "submission_mode": "email"},
        "active_job": {"url": "https://example.com/job", "title": "Backend Engineer"},
        "pending_jobs": [{"url": "https://example.com/job", "title": "Backend Engineer"}],
        "human_decision": "approve",
        "normalized_resume": {},
        "tailored_materials": {},
        "applied_jobs": [],
        "skipped_jobs": [],
        "processing_log": [],
        "validation_notes": [],
    })

    assert result["error_logs"][0]["component"] == "submission"
    assert result["error_logs"][0]["error_type"] == "KeyError"
    assert result["confirmation"] is None
    assert result["processing_log"][-1]["event"] == "submission_failed"