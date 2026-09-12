from unittest.mock import Mock

import pytest

from server.telegram import TelegramClient
from server.webhook import parse_callback_data, resume_approval
from agent.nodes import wait_for_approval


def test_telegram_client_sends_approval_buttons():
    response = Mock()
    response.json.return_value = {"ok": True, "result": {"message_id": 7}}
    response.raise_for_status.return_value = None
    session = Mock()
    session.post.return_value = response
    client = TelegramClient("token", "123", session=session)

    result = client.send_approval({"title": "Backend Engineer", "company": "Acme", "url": "https://example.com/job", "match_score": 82, "thread_id": "thread-1"}, "Apply carefully.")

    assert result["ok"] is True
    payload = session.post.call_args.kwargs["json"]
    buttons = payload["reply_markup"]["inline_keyboard"][0]
    assert buttons[0]["callback_data"] == "job:approve:thread-1:https://example.com/job"
    assert buttons[1]["callback_data"] == "job:skip:thread-1:https://example.com/job"


def test_parse_callback_data_validates_decision_and_job():
    assert parse_callback_data("job:approve:thread-1:https%3A%2F%2Fexample.com%2Fjob") == {
        "decision": "approve",
        "thread_id": "thread-1",
        "url": "https://example.com/job",
    }
    with pytest.raises(ValueError):
        parse_callback_data("invalid")


def test_resume_approval_updates_matching_checkpoint():
    graph = Mock()
    graph.get_state.return_value.values = {"active_job": {"url": "https://example.com/job"}}
    graph.invoke.return_value = {"status": "completed"}
    connection = Mock()
    factory = Mock(return_value=(graph, connection))

    result = resume_approval({"callback_query": {"data": "job:skip:thread-1:https%3A%2F%2Fexample.com%2Fjob"}}, factory)

    assert result["decision"] == "skip"
    graph.update_state.assert_called_once()
    graph.invoke.assert_called_once()
    connection.close.assert_called_once()


def test_wait_for_approval_sends_configured_telegram_message(monkeypatch):
    client = Mock()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.setattr("agent.nodes.TelegramClient", Mock(return_value=client))
    state = {
        "active_job": {
            "title": "Backend Engineer",
            "company": "Acme",
            "url": "https://example.com/job",
            "match_score": 82,
            "thread_id": "thread-1",
        },
        "tailored_materials": {"cover_letter": "Targeted letter."},
        "processing_log": [],
        "validation_notes": [],
    }

    result = wait_for_approval(state)

    client.send_approval.assert_called_once_with(state["active_job"], "Targeted letter.")
    assert result["processing_log"][-1]["event"] == "telegram_approval_sent"