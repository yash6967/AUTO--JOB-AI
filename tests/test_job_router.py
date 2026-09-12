from unittest.mock import Mock

from tools.job_router import LeverClient, route_job


def test_standard_greenhouse_job_uses_api_route():
    client = Mock()
    client.fetch_job.return_value = {"title": "Backend Engineer", "job_description": {"required_skills": ["Python"]}}

    result = route_job({
        "title": "Backend Engineer",
        "url": "https://boards.greenhouse.io/acme/jobs/42",
        "source": "greenhouse",
    }, greenhouse_client=client)

    assert result["route"] == "greenhouse"
    assert result["job_description"]["required_skills"] == ["Python"]
    client.fetch_job.assert_called_once()


def test_custom_greenhouse_job_uses_api_route():
    client = Mock()
    client.fetch_job.return_value = {"job_description": {"required_skills": ["SQL"]}}

    result = route_job({
        "url": "https://careers.acme.example/jobs/42",
        "source": "greenhouse-custom-domain",
    }, greenhouse_client=client)

    assert result["route"] == "greenhouse"
    client.fetch_job.assert_called_once()


def test_lever_client_normalizes_api_response():
    response = Mock()
    response.json.return_value = {
        "text": "Data Engineer",
        "descriptionPlain": "Build Python and SQL pipelines.",
        "categories": {"team": "Data"},
    }
    response.raise_for_status.return_value = None
    session = Mock()
    session.get.return_value = response

    result = LeverClient(session=session).fetch_job({
        "url": "https://jobs.lever.co/acme/abc123",
        "source": "lever",
    })

    assert result["title"] == "Data Engineer"
    assert result["job_description"]["required_skills"] == ["Python", "SQL"]
    session.get.assert_called_once_with(
        "https://api.lever.co/v0/postings/acme/abc123",
        params={"mode": "json"},
        timeout=15.0,
    )


def test_generic_job_uses_playwright_extractor():
    result = route_job(
        {"url": "https://jobs.example.com/backend", "source": "web"},
        playwright_extractor=lambda url: "Develop FastAPI services with 4 years experience.",
    )

    assert result["route"] == "playwright"
    assert result["job_description"]["required_skills"] == ["FastAPI"]
    assert result["job_description"]["years_experience"] == 4