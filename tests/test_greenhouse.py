from unittest.mock import Mock

from agent.nodes import discover_jobs
from tools.greenhouse import GreenhouseClient, parse_board_url


def test_parse_board_url_supports_standard_and_custom_domains():
    standard = parse_board_url("https://boards.greenhouse.io/acme")
    custom = parse_board_url("https://careers.acme.example/acme")

    assert standard.token == "acme"
    assert standard.source == "greenhouse"
    assert custom.token == "acme"
    assert custom.source == "greenhouse-custom-domain"


def test_greenhouse_client_normalizes_jobs_and_description():
    response = Mock()
    response.json.return_value = {
        "jobs": [{
            "id": 42,
            "title": "Backend Engineer",
            "absolute_url": "https://boards.greenhouse.io/acme/jobs/42",
            "content": "<p>Build Python services.</p><p>3+ years of SQL experience.</p>",
        }]
    }
    response.raise_for_status.return_value = None
    session = Mock()
    session.get.return_value = response

    jobs = GreenhouseClient(session=session).fetch_jobs("https://boards.greenhouse.io/acme")

    assert jobs[0]["title"] == "Backend Engineer"
    assert jobs[0]["source"] == "greenhouse"
    assert jobs[0]["job_description"]["required_skills"] == ["Python", "SQL"]
    assert jobs[0]["job_description"]["years_experience"] == 3
    session.get.assert_called_once_with(
        "https://boards-api.greenhouse.io/v1/boards/acme/jobs",
        params={"content": "true"},
        timeout=15.0,
    )


def test_discover_jobs_uses_configured_greenhouse_boards(monkeypatch):
    client = Mock()
    client.fetch_jobs.return_value = [{
        "title": "Data Engineer",
        "company": "Acme",
        "url": "https://careers.acme.example/data-engineer",
        "source": "greenhouse-custom-domain",
        "status": "discovered",
    }]
    client_factory = Mock(return_value=client)
    monkeypatch.setattr("agent.nodes.GreenhouseClient", client_factory)

    state = {
        "hardcoded_criteria": {
            "greenhouse_board_urls": ["https://careers.acme.example/acme"],
            "greenhouse_timeout": 3,
        },
        "processing_log": [],
        "validation_notes": [],
    }
    result = discover_jobs(state)

    assert result["discovered_jobs"] == client.fetch_jobs.return_value
    assert result["validation_notes"][-1]["status"] == "complete"
    client_factory.assert_called_once_with(timeout=3.0)
    client.fetch_jobs.assert_called_once_with("https://careers.acme.example/acme", None)