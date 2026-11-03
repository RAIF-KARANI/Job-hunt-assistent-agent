"""
Phase 8c: tracing - a flight recorder for every LLM call, tool call and node.

One switch in .env:
    TRACING=off        nothing is recorded (default)
    TRACING=langfuse   self-hosted Langfuse on this PC (infra/langfuse) - private
    TRACING=langsmith  LangChain's cloud - your resume text gets uploaded

How it works:
    LangChain fires an event whenever any runnable (graph, node, LLM, tool)
    starts, ends or fails. A tracing tool is just a CALLBACK HANDLER that
    listens to those events and ships them to its server. We pass the handler
    once, in the graph's config; LangChain propagates it to every nested call
    (on Python 3.11+ via context variables), so none of the nodes needed to
    change.

Golden rule: tracing must never break the agent. If the tracing server is
down, the SDK just logs a warning and the run continues.
"""

import os

from job_agent import settings  # noqa: F401  (loads .env from paths.ENV_FILE)

TRACING = os.getenv("TRACING", "off").lower()


# 15h: is the Langfuse server answering? Asked once per run (cached a minute).
# When it isn't, the run isn't traced: before, every run with Langfuse down
# was saved as "langfuse", its Evals link said "Session not found" (40 runs
# between 31 Oct and 3 Nov), and the SDK retried in the background
# ("Failed to export spans batch ...") for the rest of the session.
LANGFUSE_DOWN = "langfuse_down"  # runs.tracing for a run Langfuse never saw
_reachable: dict = {"at": 0.0, "ok": False}


def langfuse_reachable(timeout: float = 1.5, max_age: float = 60.0) -> bool:
    import time

    import requests

    if time.time() - _reachable["at"] < max_age:
        return _reachable["ok"]
    host = os.getenv("LANGFUSE_HOST", os.getenv("LANGFUSE_BASE_URL", "http://localhost:3000")).rstrip("/")
    try:
        ok = requests.get(f"{host}/api/public/health", timeout=timeout).status_code < 500
    except requests.RequestException:
        ok = False
    _reachable.update(at=time.time(), ok=ok)
    return ok


def tracing_config(session_id: str, interface: str) -> dict:
    """Extra keys to merge into a LangGraph config: {"callbacks": ..., "metadata": ...}.

    session_id: the run's thread_id. A run is often several graph calls (start,
        then a resume after each approval decision); sharing a session groups
        them together in the dashboard.
    interface: "cli", "web" or "desktop", added as a tag so you can filter by it.
    """
    model = os.getenv("LLM_MODEL", "qwen3:8b")
    tags = [interface, model]

    # Phase 11: JobLens' own run log is ALWAYS on, whatever TRACING says. It
    # writes to the local SQLite database, so every user gets the Dashboard's
    # run, quality and feedback charts without Langfuse or Docker.
    from job_agent.runlog import RunRecorder
    langfuse_up = TRACING == "langfuse" and langfuse_reachable()
    recorded = LANGFUSE_DOWN if TRACING == "langfuse" and not langfuse_up else TRACING
    local = RunRecorder(session_id, interface, os.getenv("LLM_PROVIDER", "ollama"), model,
                        tracing=recorded)
    if TRACING == "langfuse" and not langfuse_up:
        print("! Langfuse isn't answering: this run isn't traced (start it with docker compose up -d)")

    if langfuse_up:
        from langfuse.langchain import CallbackHandler

        return {
            "callbacks": [local, CallbackHandler()],  # keys come from LANGFUSE_* in .env
            # Langfuse reads these special metadata keys from the config:
            "metadata": {
                "langfuse_session_id": session_id,
                "langfuse_tags": tags,
                "langfuse_trace_name": "job-hunt-run",
            },
        }

    if TRACING == "langsmith":
        # No handler needed: LangChain sends traces by itself when these env
        # variables are set. We only add grouping info.
        os.environ.setdefault("LANGSMITH_TRACING", "true")
        os.environ.setdefault("LANGSMITH_PROJECT", "job-hunt-assistant")
        if not os.getenv("LANGSMITH_API_KEY"):
            print("! TRACING=langsmith but LANGSMITH_API_KEY is not set - no traces will be sent")
        # LangSmith groups runs into a "thread" via the session_id metadata key.
        return {"callbacks": [local], "tags": tags, "metadata": {"session_id": session_id}}

    return {"callbacks": [local]}


def record_decision(session_id: str, decision: str) -> None:
    """Attach your approve / edit / reject decision to the run as a SCORE.

    Human feedback is the most valuable quality signal an LLM app has. In the
    dashboard you can then filter: "show me runs whose drafts were rejected"
    and read exactly what the model wrote and why.
    """
    if TRACING != "langfuse" or not langfuse_reachable():
        return  # 15h: no score for a run Langfuse never saw
    from langfuse import get_client

    get_client().create_score(
        name="cover_note_decision",
        value=decision,                # "approve" | "edit" | "reject"
        data_type="CATEGORICAL",
        session_id=session_id,
    )


def flush() -> None:
    """Send buffered events now.

    The SDK batches events in a background thread for speed. A short-lived
    CLI process must flush before exiting, or the last events are lost.
    """
    if TRACING == "langfuse" and langfuse_reachable():
        from langfuse import get_client

        get_client().flush()


def check_tracing_ready() -> None:
    """Warn (don't fail) if Langfuse keys are wrong or the server is down."""
    if TRACING != "langfuse":
        return
    from langfuse import get_client

    try:
        ok = get_client().auth_check()
    except Exception as e:
        ok = False
        print(f"! Langfuse check failed: {e}")
    if not ok:
        print("! Langfuse isn't reachable or the keys are wrong - the run continues "
              "without tracing. Start it with: cd infra\\langfuse && docker compose up -d")
