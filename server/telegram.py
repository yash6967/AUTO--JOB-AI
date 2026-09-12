from __future__ import annotations

from typing import Any

import requests


class TelegramClient:
    def __init__(self, token: str, chat_id: str, session: requests.Session | None = None, timeout: float = 15.0) -> None:
        if not token or not chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")
        self.chat_id = chat_id
        self.session = session or requests.Session()
        self.timeout = timeout
        self.endpoint = f"https://api.telegram.org/bot{token}/sendMessage"

    def send_approval(self, job: dict[str, Any], cover_letter: str = "") -> dict[str, Any]:
        text = (
            f"Job approval required\n"
            f"Role: {job.get('title', 'Unknown')}\n"
            f"Company: {job.get('company', 'Unknown')}\n"
            f"Match score: {job.get('match_score', 0)}\n"
            f"{cover_letter[:500]}"
        )
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "reply_markup": {
                "inline_keyboard": [[
                    {"text": "Approve & Apply", "callback_data": self.callback_data(job, "approve")},
                    {"text": "Skip", "callback_data": self.callback_data(job, "skip")},
                ]]
            },
        }
        response = self.session.post(self.endpoint, json=payload, timeout=self.timeout)
        response.raise_for_status()
        result = response.json()
        if not result.get("ok"):
            raise RuntimeError(f"Telegram API rejected approval message: {result}")
        return result

    @staticmethod
    def callback_data(job: dict[str, Any], decision: str) -> str:
        if decision not in {"approve", "skip"}:
            raise ValueError(f"Unsupported Telegram decision: {decision}")
        thread_id = job.get("thread_id")
        url = job.get("url")
        if not thread_id or not url:
            raise ValueError("Approval callback requires thread_id and job url")
        return f"job:{decision}:{thread_id}:{url}"