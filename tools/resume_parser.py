from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from docx import Document


REQUIRED_SECTIONS = (
    "contact",
    "summary",
    "experience_array",
    "skills_list",
    "education",
    "additional_information",
)


def empty_resume() -> dict[str, Any]:
    return {
        "contact": {},
        "summary": "",
        "experience_array": [],
        "skills_list": [],
        "education": [],
        "additional_information": [],
    }


def load_resume(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Resume file does not exist: {source}")

    suffix = source.suffix.lower()
    if suffix == ".json":
        with source.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return normalize_resume(data)
    if suffix == ".pdf":
        text = "\n".join(page.extract_text() or "" for page in PdfReader(str(source)).pages)
        return normalize_text_resume(text)
    if suffix == ".docx":
        document = Document(str(source))
        return normalize_text_resume("\n".join(paragraph.text for paragraph in document.paragraphs))
    if suffix in {".txt", ".md"}:
        return normalize_text_resume(source.read_text(encoding="utf-8"))
    raise ValueError("Supported resume formats are .json, .pdf, .docx, .txt, and .md")


def normalize_resume(data: dict[str, Any]) -> dict[str, Any]:
    result = empty_resume()
    result.update({key: data.get(key, default) for key, default in result.items()})
    return result


def normalize_text_resume(text: str) -> dict[str, Any]:
    result = empty_resume()
    sections: dict[str, list[str]] = {section: [] for section in REQUIRED_SECTIONS}
    current = "additional_information"

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        heading = line.lower().rstrip(":")
        if "experience" in heading or "employment" in heading:
            current = "experience_array"
        elif "skill" in heading or "technical" in heading:
            current = "skills_list"
        elif "education" in heading or "academic" in heading:
            current = "education"
        elif "summary" in heading or "profile" in heading:
            current = "summary"
        elif "contact" in heading:
            current = "contact"
        else:
            sections[current].append(line)

    result["summary"] = "\n".join(sections["summary"])
    result["skills_list"] = sections["skills_list"]
    result["experience_array"] = sections["experience_array"]
    result["education"] = sections["education"]
    result["additional_information"] = sections["additional_information"]
    return result
