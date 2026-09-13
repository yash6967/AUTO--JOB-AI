from __future__ import annotations

import os
import logging
from typing import Any
from urllib.parse import unquote

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from agent.graph import build_graph, checkpoint_config

load_dotenv()

app = FastAPI(title="Auto Job AI Telegram Webhook")
logger = logging.getLogger(__name__)


def parse_callback_data(callback_data: str) -> dict[str, str]:
    parts = callback_data.split(":", 2)
    if len(parts) != 3 or parts[0] != "job" or parts[1] not in {"approve", "skip", "submit", "cancel"}:
        raise ValueError("Invalid Telegram callback data")
    return {"decision": parts[1], "thread_id": parts[2], "url": ""}


def resume_approval(payload: dict[str, Any], graph_factory=build_graph) -> dict[str, Any]:
    callback = payload.get("callback_query") or {}
    callback_data = callback.get("data")
    if not isinstance(callback_data, str):
        raise ValueError("Telegram payload does not contain callback data")
    parsed = parse_callback_data(callback_data)
    database = os.getenv("AGENT_DATABASE")
    if not database:
        raise ValueError(
            "AGENT_DATABASE is not configured. Set it to the exact SQLite path used by the CLI."
        )
    graph, connection = graph_factory(database)
    try:
        current = graph.get_state(checkpoint_config(parsed["thread_id"])).values
        if not current or "hardcoded_criteria" not in current:
            raise ValueError(
                f"No valid checkpoint found for thread '{parsed['thread_id']}' in '{database}'. "
                "Use the same --database path for the CLI and webhook, then start a fresh run."
            )
        active = current.get("active_job") or {}
        if not active:
            if current.get("status") == "completed":
                return {
                    "status": "already_completed",
                    "decision": parsed["decision"],
                    "thread_id": parsed["thread_id"],
                    "result": current,
                }
            raise ValueError(f"Checkpoint '{parsed['thread_id']}' has no active job to approve")
        if parsed["url"] and active.get("url") != parsed["url"]:
            raise ValueError("Callback does not match the active job")
        graph.update_state(
            checkpoint_config(parsed["thread_id"]),
            {"human_decision": parsed["decision"]},
            as_node="wait_for_approval",
        )
        result = graph.invoke(None, config=checkpoint_config(parsed["thread_id"]))
    finally:
        connection.close()
    return {"status": "resumed", "decision": parsed["decision"], "thread_id": parsed["thread_id"], "result": result}


@app.post("/telegram/webhook")
def telegram_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        result = resume_approval(payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    final_state = result.get("result", {})
    response = {
        "status": result["status"],
        "decision": result["decision"],
        "thread_id": result["thread_id"],
        "confirmation": final_state.get("confirmation"),
        "error_logs": final_state.get("error_logs", []),
        "applied_jobs": len(final_state.get("applied_jobs", [])),
        "skipped_jobs": len(final_state.get("skipped_jobs", [])),
    }
    logger.info("Telegram callback result: %s", response)
    if response["error_logs"]:
        logger.error("Telegram callback completed with application errors: %s", response["error_logs"])
    return response