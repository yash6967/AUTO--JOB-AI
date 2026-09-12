from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent.graph import build_graph, checkpoint_config
from agent.state import initial_state
from tools.resume_parser import load_resume


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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    resume_path = Path(args.resume)
    normalized_resume = load_resume(resume_path)
    graph, connection = build_graph(args.database)
    criteria = {**DEFAULT_CRITERIA}
    if args.greenhouse_board_url is not None:
        criteria["greenhouse_board_urls"] = args.greenhouse_board_url
    state = initial_state(criteria, str(resume_path))
    state["normalized_resume"] = normalized_resume

    try:
        result = graph.invoke(state, config=checkpoint_config(args.thread_id))
    finally:
        connection.close()

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
