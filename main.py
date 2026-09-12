from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from agent.graph import build_graph, checkpoint_config
from agent.state import initial_state
from tools.resume_parser import load_resume
from server.telegram import TelegramClient


DEFAULT_CRITERIA = {
    "roles": ["Software Development Engineer", "Backend Engineer", "Data Engineer"],
    "locations": ["Remote"],
    "remote_only": True,
    "minimum_match_score": 60,
    "greenhouse_board_urls": [],
    "greenhouse_timeout": 15,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the job application agent graph shell.")
    parser.add_argument("--resume", default="assets/resume.json", help="Path to JSON, PDF, DOCX, TXT, or Markdown resume")
    parser.add_argument("--thread-id", default="local-run", help="Persistent LangGraph checkpoint thread id")
    parser.add_argument("--database", default="runtime/agent.sqlite", help="SQLite checkpoint path")
    parser.add_argument(
        "--greenhouse-board-url",
        action="append",
        default=None,
        help="Greenhouse board URL; repeat for multiple boards",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=None,
        help="Limit discovered jobs for a test run",
    )
    parser.add_argument(
        "--telegram-test",
        action="store_true",
        help="Send a standalone Telegram approval test message and exit",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    if args.telegram_test:
        result = TelegramClient(
            os.getenv("TELEGRAM_BOT_TOKEN", ""),
            os.getenv("TELEGRAM_CHAT_ID", ""),
        ).send_approval(
            {
                "title": "Telegram integration test",
                "company": "Auto Job AI",
                "url": "https://example.com/telegram-test",
                "match_score": 100,
                "thread_id": "telegram-test",
            },
            "This is a standalone Telegram approval-node test.",
        )
        print(json.dumps({"telegram_ok": result.get("ok", False), "message_id": result.get("result", {}).get("message_id")}, indent=2))
        return
    resume_path = Path(args.resume)
    normalized_resume = load_resume(resume_path)
    graph, connection = build_graph(args.database)
    criteria = {**DEFAULT_CRITERIA}
    if args.greenhouse_board_url is not None:
        criteria["greenhouse_board_urls"] = args.greenhouse_board_url
    if args.max_jobs is not None:
        if args.max_jobs < 1:
            raise ValueError("--max-jobs must be at least 1")
        criteria["max_jobs"] = args.max_jobs
    criteria["thread_id"] = args.thread_id
    state = initial_state(criteria, str(resume_path))
    state["normalized_resume"] = normalized_resume

    try:
        result = graph.invoke(state, config=checkpoint_config(args.thread_id))
    finally:
        connection.close()

    if result.get("pending_jobs"):
        print("Waiting for mobile approval...")
    print(json.dumps({
        "status": result.get("status"),
        "discovered_jobs": len(result.get("discovered_jobs", [])),
        "pending_jobs": len(result.get("pending_jobs", [])),
        "skipped_jobs": len(result.get("skipped_jobs", [])),
        "applied_jobs": len(result.get("applied_jobs", [])),
        "validation_notes": result.get("validation_notes", []),
        "next_step": "Set human_decision to approve or skip and resume the checkpoint." if result.get("pending_jobs") else "Batch complete.",
    }, indent=2))


if __name__ == "__main__":
    main()
