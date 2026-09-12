from __future__ import annotations

import os
from typing import Any
from urllib.parse import unquote

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from agent.graph import build_graph, checkpoint_config

load_dotenv()

app = FastAPI(title="Auto Job AI Telegram Webhook")


def parse_callback_data(callback_data: str) -> dict[str, str]:
    parts = callback_data.split(":", 3)
    if len(parts) != 4 or parts[0] != "job" or parts[1] not in {"approve", "skip"}:
        raise ValueError("Invalid Telegram callback data")
    return {"decision": parts[1], "thread_id": parts[2], "url": unquote(parts[3])}


def resume_approval(payload: dict[str, Any], graph_factory=build_graph) -> dict[str, Any]:
    callback = payload.get("callback_query") or {}
    callback_data = callback.get("data")
    if not isinstance(callback_data, str):
        raise ValueError("Telegram payload does not contain callback data")
    parsed = parse_callback_data(callback_data)
    database = os.getenv("AGENT_DATABASE", "runtime/agent.sqlite")
    graph, connection = graph_factory(database)
    try:
        current = graph.get_state(checkpoint_config(parsed["thread_id"])).values
        active = current.get("active_job") or {}
        if active.get("url") != parsed["url"]:
            raise ValueError("Callback does not match the active job")
        graph.update_state(checkpoint_config(parsed["thread_id"]), {"human_decision": parsed["decision"]})
        result = graph.invoke(None, config=checkpoint_config(parsed["thread_id"]))
    finally:
        connection.close()
    return {"status": "resumed", "decision": parsed["decision"], "thread_id": parsed["thread_id"], "result": result}


@app.post("/telegram/webhook")
def telegram_webhook(payload: dict[str, Any]) -> dict[str, str]:
    try:
        result = resume_approval(payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"status": result["status"], "decision": result["decision"], "thread_id": result["thread_id"]}