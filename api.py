"""
Phase 8d: an HTTP API around the agent, so other tools (n8n, scripts, other
apps) can use it like any web service.

Run:
    python api.py               (http://127.0.0.1:8000, docs at /docs)

Endpoints (all except /health need the header  X-API-Key: <AGENT_API_KEY>):
    GET  /health                          is the API alive?
    POST /runs                            start analyzing a job -> 202 + thread_id
    GET  /runs/{thread_id}                where is this run?
    POST /runs/{thread_id}/decision       approve / edit / reject the draft
    GET  /jobs                            the tracker

Design notes:
- A full run takes ~3 minutes, far too long to hold an HTTP request open.
  So POST /runs answers 202 Accepted immediately and runs the graph in a
  background thread. The caller either polls GET /runs/{id}, or passes a
  callback_url that we POST the result to when the agent pauses or finishes
  (the "webhook" pattern; n8n's Wait node gives us such a URL).
- Same SQLite checkpointer as the web UI (data/checkpoints.db), so a run
  started from n8n can also be seen and continued in the web UI.
- The decision endpoint is the HTTP version of Command(resume=...).
- One run at a time (a lock): there is one local Ollama, and parallel runs
  would just slow each other down.
"""

import os
import sqlite3
import threading
import uuid
from typing import Literal

import requests
from fastapi import Depends, FastAPI, Header, HTTPException
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic import BaseModel

from job_agent.cover_note import SAFE_SERDE
from job_agent.graph import build_job_hunt_graph
from job_agent.llm import check_llm_ready
from job_agent.resume import DATA_DIR
from job_agent.tracing import flush, record_decision, tracing_config
from job_agent.tracker import list_jobs

API_KEY = os.getenv("AGENT_API_KEY", "")

DATA_DIR.mkdir(exist_ok=True)
graph = build_job_hunt_graph(
    checkpointer=SqliteSaver(
        sqlite3.connect(DATA_DIR / "checkpoints.db", check_same_thread=False),
        serde=SAFE_SERDE,
    )
)

_run_lock = threading.Lock()   # one graph run at a time
_running: set[str] = set()     # thread_ids currently executing
_errors: dict[str, str] = {}   # thread_id -> error message

app = FastAPI(
    title="Job Hunt Assistant API",
    description="Analyze job postings and draft cover notes, with human approval.",
)


# ---------------------------------------------------------------------------
# Security: a shared secret header
# ---------------------------------------------------------------------------


def require_api_key(x_api_key: str = Header(default="")) -> None:
    """FastAPI 'dependency': runs before the endpoint; rejects bad keys."""
    if not API_KEY:
        raise HTTPException(500, "AGENT_API_KEY is not set in .env")
    if x_api_key != API_KEY:
        raise HTTPException(401, "Missing or wrong X-API-Key header")


# ---------------------------------------------------------------------------
# Request bodies (Pydantic validates incoming JSON, just like LLM output)
# ---------------------------------------------------------------------------


class StartRun(BaseModel):
    url: str
    fresh: bool = False
    callback_url: str | None = None   # we POST the status here when the run stops


class DecisionIn(BaseModel):
    decision: Literal["approve", "edit", "reject"]
    feedback: str = ""   # for "edit": what should change
    text: str = ""       # for "approve": optional edited text to save instead


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}, **tracing_config(thread_id, "api")}


def run_status(thread_id: str) -> dict:
    """Turn the checkpointer's view of a run into a simple JSON status."""
    if thread_id in _running:
        return {"thread_id": thread_id, "status": "running"}
    if thread_id in _errors:
        return {"thread_id": thread_id, "status": "error", "error": _errors[thread_id]}

    snap = graph.get_state({"configurable": {"thread_id": thread_id}})
    if not snap.values:
        raise HTTPException(404, f"No run with thread_id {thread_id}")

    values = snap.values
    out = {"thread_id": thread_id}
    if values.get("job"):
        out["job"] = {"title": values["job"].title, "company": values["job"].company}
    if values.get("job_id"):
        out["job_id"] = values["job_id"]
    if values.get("best_match"):
        best = values["best_match"]
        out.update(fit_score=best.fit_score, score_breakdown=best.score_breakdown,
                   resume=best.resume_name)

    if snap.interrupts:
        payload = snap.interrupts[0].value
        if payload["kind"] == "paste_posting":
            out.update(status="needs_posting_text", reason=payload["reason"])
        else:
            out.update(status="awaiting_approval", draft=payload["draft"],
                       warnings=payload["warnings"], word_count=payload["word_count"],
                       revision=payload["revision"])
    elif not snap.next:
        saved = values.get("saved_path")
        out.update(status="done", approved=bool(saved), saved_path=saved)
    else:
        out["status"] = "stopped"
    return out


def _execute(graph_input, thread_id: str, callback_url: str | None = None) -> None:
    """Run/resume the graph until it pauses or ends, then notify the callback."""
    _running.add(thread_id)
    try:
        with _run_lock:
            graph.invoke(graph_input, _config(thread_id))
    except Exception as e:  # keep the server alive; report the error instead
        _errors[thread_id] = f"{type(e).__name__}: {e}"
    finally:
        _running.discard(thread_id)
        flush()

    if callback_url:
        try:
            requests.post(callback_url, json=run_status(thread_id), timeout=15)
        except requests.RequestException as e:
            print(f"! callback to {callback_url} failed: {e}")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/runs", status_code=202, dependencies=[Depends(require_api_key)])
def start_run(body: StartRun) -> dict:
    try:
        check_llm_ready()
    except SystemExit as e:  # Ollama down / model missing
        raise HTTPException(503, str(e))
    thread_id = str(uuid.uuid4())
    _running.add(thread_id)  # mark before the thread starts, so a quick GET sees it
    threading.Thread(
        target=_execute,
        args=({"url": body.url, "fresh": body.fresh}, thread_id, body.callback_url),
        daemon=True,
    ).start()
    return {"thread_id": thread_id, "status": "running",
            "status_url": f"/runs/{thread_id}"}


@app.get("/runs/{thread_id}", dependencies=[Depends(require_api_key)])
def get_run(thread_id: str) -> dict:
    return run_status(thread_id)


@app.post("/runs/{thread_id}/decision", dependencies=[Depends(require_api_key)])
def decide(thread_id: str, body: DecisionIn) -> dict:
    """The HTTP version of Command(resume=...). Waits for the result:
    approve/reject finish in under a second, edit re-drafts (~20 s)."""
    current = run_status(thread_id)
    if current["status"] != "awaiting_approval":
        raise HTTPException(409, f"Run is '{current['status']}', not awaiting approval")

    answer = {"decision": body.decision, "feedback": body.feedback}
    if body.text:
        answer["text"] = body.text
    record_decision(thread_id, body.decision)
    _execute(Command(resume=answer), thread_id)
    return run_status(thread_id)


@app.get("/jobs", dependencies=[Depends(require_api_key)])
def jobs() -> list[dict]:
    return [dict(r) for r in list_jobs()]


if __name__ == "__main__":
    import uvicorn

    # 127.0.0.1 = only programs on this PC (incl. Docker containers via
    # host.docker.internal) can reach it, not other devices on your network.
    uvicorn.run(app, host="127.0.0.1", port=8000)
