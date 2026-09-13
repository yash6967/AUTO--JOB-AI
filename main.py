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
from tools.tracking import NotionTracker


DEFAULT_CRITERIA = {
    "roles": ["Software Development Engineer", "Backend Engineer", "Data Engineer"],
    "locations": ["Remote"],
    "remote_only": True,
    "minimum_match_score": 10,
    "greenhouse_board_urls": [],
    "greenhouse_timeout": 15,
    "auto_apply_score": 90,
    "greenhouse_browser_profile": "runtime/greenhouse-browser",
    "greenhouse_login_wait_seconds": 600,
    "greenhouse_search_enabled": True,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the job application agent graph shell.")
    parser.add_argument("--resume", default="assets/resume.json", help="Path to JSON, PDF, DOCX, TXT, or Markdown resume")
    parser.add_argument("--resume-pdf", default=None, help="PDF file to upload to Greenhouse applications; auto-detects the only PDF in assets when omitted")
    parser.add_argument("--application-profile", default="assets/application_profile.json", help="Path to persistent Greenhouse application answers")
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
    parser.add_argument(
        "--notion-test",
        action="store_true",
        help="Create a standalone Notion tracking test page and exit",
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
    if args.notion_test:
        result = NotionTracker(
            os.getenv("NOTION_TOKEN", ""),
            os.getenv("NOTION_DATABASE_ID", ""),
        ).record_decision(
            {
                "title": "Notion integration test",
                "company": "Auto Job AI",
                "url": "https://example.com/notion-test",
                "match_score": 100,
            },
            "test",
        )
        print(json.dumps({"notion_ok": True, "page_id": result.get("id")}, indent=2))
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
    resume_pdf = Path(args.resume_pdf) if args.resume_pdf else None
    if resume_pdf is None:
        pdf_candidates = sorted(Path("assets").glob("*.pdf"))
        if len(pdf_candidates) == 1:
            resume_pdf = pdf_candidates[0]
    if resume_pdf is not None:
        if not resume_pdf.exists():
            raise FileNotFoundError(f"Resume PDF does not exist: {resume_pdf}")
        criteria["application_resume_pdf"] = str(resume_pdf)
    profile_path = Path(args.application_profile)
    if profile_path.exists():
        with profile_path.open(encoding="utf-8") as handle:
            criteria["application_profile"] = json.load(handle)
    else:
        criteria["application_profile"] = {}
    criteria["notion_enabled"] = bool(os.getenv("NOTION_TOKEN") and os.getenv("NOTION_DATABASE_ID"))
    criteria["submission_mode"] = os.getenv("SUBMISSION_MODE", "dry_run").lower()
    criteria["auto_apply_score"] = int(os.getenv("GREENHOUSE_AUTO_APPLY_SCORE", str(criteria["auto_apply_score"])))
    criteria["greenhouse_browser_profile"] = os.getenv("GREENHOUSE_BROWSER_PROFILE", criteria["greenhouse_browser_profile"])
    criteria["greenhouse_login_wait_seconds"] = int(os.getenv("GREENHOUSE_LOGIN_WAIT_SECONDS", str(criteria["greenhouse_login_wait_seconds"])))
    criteria["greenhouse_post_submit_hold_seconds"] = int(os.getenv("GREENHOUSE_POST_SUBMIT_HOLD_SECONDS", "0"))
    criteria["greenhouse_search_enabled"] = bool(os.getenv("EXA_API_KEY"))
    criteria["greenhouse_search_queries"] = [
        f"{role} {location}" for role in criteria["roles"] for location in criteria["locations"]
    ]
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
        "confirmation": result.get("confirmation"),
        "error_logs": result.get("error_logs", []),
        "validation_notes": result.get("validation_notes", []),
        "next_step": (
            "Keep the Telegram webhook running, then click Approve & Apply or Skip. "
            "The webhook will resume this checkpoint."
            if result.get("pending_jobs")
            else "Batch complete."
        ),
    }, indent=2))


if __name__ == "__main__":
    main()
