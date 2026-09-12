from __future__ import annotations

from agent.graph import build_graph, checkpoint_config
from agent.state import initial_state


def test_batch_preparation_separates_low_matches(tmp_path):
    graph, connection = build_graph(tmp_path / "agent.sqlite")
    try:
        state = initial_state(
            {"minimum_match_score": 60, "greenhouse_board_urls": []},
            "assets/resume.json",
        )
        state["normalized_resume"] = {"summary": "test"}
        result = graph.invoke(state, config=checkpoint_config("test-batch"))
    finally:
        connection.close()

    assert len(result["discovered_jobs"]) == 2
    assert len(result["skipped_jobs"]) == 1
    assert len(result["pending_jobs"]) == 1
    assert result["status"] == "awaiting_approval"
    assert result["validation_notes"]
    assert any(entry["event"] == "approval_gate_reached" for entry in result["processing_log"])


def test_resume_after_decision_processes_remaining_queue(tmp_path):
    graph, connection = build_graph(tmp_path / "agent.sqlite")
    config = checkpoint_config("test-resume")
    try:
        state = initial_state(
            {"minimum_match_score": 60, "greenhouse_board_urls": []},
            "assets/resume.json",
        )
        state["normalized_resume"] = {"summary": "test"}
        first = graph.invoke(state, config=config)
        graph.update_state(config, {"human_decision": "approve"})
        result = graph.invoke(None, config=config)
    finally:
        connection.close()

    assert first["pending_jobs"]
    assert len(result["applied_jobs"]) == 1
    assert result["status"] == "completed"
    assert any(entry["event"] == "job_applied" for entry in result["processing_log"])
