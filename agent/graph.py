from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from agent.nodes import discover_jobs, prepare_jobs, route_and_parse_job, score_and_tailor, track_and_submit, wait_for_approval
from agent.state import AgentState


def build_graph(database_path: str | Path = "runtime/agent.sqlite") -> tuple[Any, sqlite3.Connection]:
    database = Path(database_path)
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database, check_same_thread=False)
    checkpointer = SqliteSaver(connection)

    builder = StateGraph(AgentState)
    builder.add_node("discover_jobs", discover_jobs)
    builder.add_node("prepare_jobs", prepare_jobs)
    builder.add_node("route_and_parse_job", route_and_parse_job)
    builder.add_node("score_and_tailor", score_and_tailor)
    builder.add_node("wait_for_approval", wait_for_approval)
    builder.add_node("track_and_submit", track_and_submit)
    builder.add_edge(START, "discover_jobs")
    builder.add_edge("discover_jobs", "prepare_jobs")
    builder.add_edge("prepare_jobs", "route_and_parse_job")
    builder.add_edge("route_and_parse_job", "score_and_tailor")
    builder.add_conditional_edges(
        "score_and_tailor",
        lambda state: "route_and_parse_job" if state.get("active_job") and state.get("active_job", {}).get("match_score", 0) < int(state["hardcoded_criteria"].get("minimum_match_score", 60)) else "wait_for_approval",
        {"route_and_parse_job": "route_and_parse_job", "wait_for_approval": "wait_for_approval"},
    )
    builder.add_edge("wait_for_approval", "track_and_submit")
    builder.add_conditional_edges(
        "track_and_submit",
        lambda state: "route_and_parse_job" if state.get("pending_jobs") else END,
        {"route_and_parse_job": "route_and_parse_job", END: END},
    )

    graph = builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["wait_for_approval"],
    )
    return graph, connection


def checkpoint_config(thread_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": thread_id}}
