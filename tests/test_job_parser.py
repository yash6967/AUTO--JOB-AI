from tools.job_parser import JobRequirements, GroqRequirementsParser


def test_job_requirements_schema_has_expected_fields():
    result = JobRequirements(
        required_skills=["Python"],
        years_experience=3,
        core_responsibilities=["Build APIs"],
    )

    assert result.model_dump() == {
        "required_skills": ["Python"],
        "years_experience": 3,
        "core_responsibilities": ["Build APIs"],
    }


def test_groq_parser_validates_structured_result(monkeypatch):
    class FakeModel:
        def invoke(self, prompt):
            assert "Build Python APIs" in prompt
            return {"required_skills": ["Python"], "years_experience": 2, "core_responsibilities": ["Build APIs"]}

    parser = object.__new__(GroqRequirementsParser)
    parser.model = FakeModel()

    assert parser.parse("Build Python APIs with 2 years experience.") == {
        "required_skills": ["Python"],
        "years_experience": 2,
        "core_responsibilities": ["Build APIs"],
    }