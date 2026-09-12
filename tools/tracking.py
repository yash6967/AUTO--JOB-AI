from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


class NotionTracker:
    def __init__(self, token: str, database_id: str, client: Any | None = None) -> None:
        if not token or not database_id:
            raise ValueError("NOTION_TOKEN and NOTION_DATABASE_ID are required")
        if client is None:
            from notion_client import Client

            client = Client(auth=token)
        self.client = client
        self.database_id = database_id

    def validate_database(self) -> None:
        try:
            self.client.databases.retrieve(database_id=self.database_id)
        except Exception as error:
            raise ValueError(
                "NOTION_DATABASE_ID is not an accessible Notion database. "
                "Use the ID from the database URL, share the database with the integration, "
                "and do not use the parent page ID."
            ) from error

    def record_decision(self, job: dict[str, Any], decision: str, document_paths: list[str] | None = None) -> dict[str, Any]:
        self.validate_database()
        status_names = {
            "approved": "Approved",
            "approve": "Approved",
            "applied": "Applied",
            "skipped": "Rejected",
            "skip": "Rejected",
            "rejected": "Rejected",
            "test": "Discovered",
        }
        status_name = status_names.get(decision.lower(), decision)
        properties = {
            "Job Title": {"title": [{"text": {"content": job.get("title", "Unknown role")}}]},
            "Company": {"rich_text": [{"text": {"content": job.get("company", "Unknown company")}}]},
            "Match Score": {"number": job.get("match_score", 0)},
            "Status": {"status": {"name": status_name}},
            "Date Added": {"date": {"start": datetime.now(UTC).date().isoformat()}},
            "Job URL": {"url": job.get("url")},
        }
        if document_paths:
            properties["Documents"] = {"rich_text": [{"text": {"content": ", ".join(document_paths)}}]}
        return self.client.pages.create(parent={"database_id": self.database_id}, properties=properties)