from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class JobRequirements(BaseModel):
    required_skills: list[str] = Field(default_factory=list)
    years_experience: int | None = None
    core_responsibilities: list[str] = Field(default_factory=list)


class GroqRequirementsParser:
    def __init__(self, model: str = "openai/gpt-oss-120b") -> None:
        from langchain_groq import ChatGroq

        self.model = ChatGroq(model=model, temperature=0).with_structured_output(JobRequirements)

    def parse(self, raw_text: str) -> dict[str, Any]:
        result = self.model.invoke(
            "Extract the job requirements from this posting. Return only requirements supported by the text.\n\n"
            + raw_text
        )
        parsed = result if isinstance(result, JobRequirements) else JobRequirements.model_validate(result)
        return parsed.model_dump()