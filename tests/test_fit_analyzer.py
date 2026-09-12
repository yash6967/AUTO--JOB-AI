from tools.fit_analyzer import FitAnalysis, GroqFitAnalyzer, deterministic_analysis, deterministic_materials


def test_fit_analysis_schema_bounds_score():
    result = FitAnalysis(match_score=80, matching_skills=["Python"], missing_requirements=["Go"])
    assert result.model_dump()["match_score"] == 80


def test_deterministic_analysis_and_materials_preserve_resume_facts():
    resume = {"skills_list": ["Python", "FastAPI"], "summary": "Backend developer.", "experience_array": [{"description": "Built APIs."}]}
    analysis = deterministic_analysis(resume, {"required_skills": ["Python", "Go"]})
    materials = deterministic_materials(resume)

    assert analysis["match_score"] == 50
    assert analysis["matching_skills"] == ["Python"]
    assert analysis["missing_requirements"] == ["Go"]
    assert materials == {"resume_bullets": ["Built APIs."], "cover_letter": "Backend developer."}


def test_groq_fit_analyzer_validates_mocked_structured_outputs():
    class FakeModel:
        def invoke(self, prompt):
            return {"match_score": 75, "matching_skills": ["Python"], "missing_requirements": ["Go"], "rationale": "Strong fit."}

    analyzer = object.__new__(GroqFitAnalyzer)
    analyzer.model = FakeModel()

    result = analyzer.analyze({"skills_list": ["Python"]}, {"required_skills": ["Python", "Go"]})

    assert result["match_score"] == 75
    assert result["missing_requirements"] == ["Go"]