from __future__ import annotations

import json
import os
from typing import Any

from pydantic import BaseModel, Field


class JobRequirements(BaseModel):
    required_skills: list[str] = Field(default_factory=list)
    years_experience: int | None = None
    core_responsibilities: list[str] = Field(default_factory=list)


class GroqRequirementsParser:
    def __init__(self, model: str | None = None) -> None:
        from langchain_groq import ChatGroq

        self.model = ChatGroq(
            model=model or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            temperature=0,
            max_tokens=450,
            max_retries=1,
        ).with_structured_output(JobRequirements)

    def parse(self, raw_text: str) -> dict[str, Any]:
        excerpt = raw_text[:7000]
        result = self.model.invoke(
            "Extract requirements from this posting. Return at most 8 short skills and 6 short responsibilities. "
            "Do not copy long sentences into any field. Return only supported facts.\n\n"
            + excerpt
        )
        parsed = result if isinstance(result, JobRequirements) else JobRequirements.model_validate(result)
        return parsed.model_dump()