from __future__ import annotations

import json
import os
from typing import Any

from pydantic import BaseModel, Field


class FitAnalysis(BaseModel):
    match_score: int = Field(ge=0, le=100)
    matching_skills: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    rationale: str = ""


class TailoredMaterials(BaseModel):
    resume_bullets: list[str] = Field(default_factory=list)
    cover_letter: str = ""


class GroqFitAnalyzer:
    def __init__(self, model: str | None = None) -> None:
        from langchain_groq import ChatGroq

        model_name = model or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        settings = {"model": model_name, "temperature": 0, "max_tokens": 450, "max_retries": 1}
        self.model = ChatGroq(**settings).with_structured_output(FitAnalysis)
        self.tailoring_model = ChatGroq(**settings).with_structured_output(TailoredMaterials)

    def analyze(self, resume: dict[str, Any], job_description: dict[str, Any]) -> dict[str, Any]:
        compact_job = {key: value for key, value in job_description.items() if key != "raw_text"}
        result = self.model.invoke(
            "Score the candidate against the job from 0 to 100. Only use evidence in the resume.\n"
            f"RESUME:\n{json.dumps(resume, ensure_ascii=True)[:6000]}\n"
            f"JOB:\n{json.dumps(compact_job, ensure_ascii=True)[:5000]}"
        )
        return (result if isinstance(result, FitAnalysis) else FitAnalysis.model_validate(result)).model_dump()

    def tailor(self, resume: dict[str, Any], job_description: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
        compact_job = {key: value for key, value in job_description.items() if key != "raw_text"}
        result = self.tailoring_model.invoke(
            "Tailor materials using only factual information in the resume. Do not invent experience. "
            "Return at most 3 short resume bullets and a cover letter of at most 120 words.\n"
            f"RESUME:\n{json.dumps(resume, ensure_ascii=True)[:6000]}\n"
            f"JOB:\n{json.dumps(compact_job, ensure_ascii=True)[:5000]}\n"
            f"ANALYSIS:\n{json.dumps(analysis, ensure_ascii=True)}"
        )
        return (result if isinstance(result, TailoredMaterials) else TailoredMaterials.model_validate(result)).model_dump()


def deterministic_analysis(resume: dict[str, Any], job_description: dict[str, Any]) -> dict[str, Any]:
    resume_skills = {str(skill).lower(): str(skill) for skill in resume.get("skills_list", [])}
    required = [str(skill) for skill in job_description.get("required_skills", [])]
    matching = [resume_skills[skill.lower()] for skill in required if skill.lower() in resume_skills]
    missing = [skill for skill in required if skill.lower() not in resume_skills]
    score = round((len(matching) / len(required)) * 100) if required else 50
    return {
        "match_score": score,
        "matching_skills": matching,
        "missing_requirements": missing,
        "rationale": "Deterministic skill overlap analysis.",
    }


def deterministic_materials(resume: dict[str, Any]) -> dict[str, Any]:
    bullets = [str(item.get("description", item.get("summary", ""))) for item in resume.get("experience_array", [])]
    return {"resume_bullets": [bullet for bullet in bullets if bullet], "cover_letter": resume.get("summary", "")}