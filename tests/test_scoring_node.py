from agent.nodes import score_and_tailor


def _state(score: int, threshold: int = 60):
    return {
        "hardcoded_criteria": {"minimum_match_score": threshold, "groq_enabled": False},
        "normalized_resume": {"skills_list": ["Python"], "summary": "Backend developer."},
        "active_job": {"url": "https://example.com/job", "title": "Backend Engineer"},
        "pending_jobs": [{"url": "https://example.com/job", "title": "Backend Engineer"}],
        "job_description": {"required_skills": ["Python"] if score >= threshold else ["Rust"]},
        "skipped_jobs": [],
        "processing_log": [],
        "validation_notes": [],
    }


def test_qualifying_score_keeps_job_pending_for_approval():
    result = score_and_tailor(_state(80))

    assert result["status"] == "awaiting_approval"
    assert result["match_score"] == 100
    assert not result["skipped_jobs"]
    assert result["tailored_materials"]["cover_letter"] == "Backend developer."


def test_qualifying_score_carries_resume_pdf_into_application_materials():
    state = _state(80)
    state["hardcoded_criteria"]["application_resume_pdf"] = "assets/resume.pdf"

    result = score_and_tailor(state)

    assert result["tailored_materials"]["resume_pdf"] == "assets/resume.pdf"


def test_below_threshold_score_moves_job_to_skipped():
    result = score_and_tailor(_state(40))

    assert result["status"] == "completed"
    assert result["active_job"] is None
    assert result["skipped_jobs"][0]["reason"] == "low_match"
    assert result["processing_log"][-1]["event"] == "job_skipped"