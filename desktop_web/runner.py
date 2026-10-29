"""
Run the LangGraph agent on a background thread and report what happens as events.

The same job as desktop/agent_worker.py (the Qt version), without Qt:

    runner = AgentRunner(emit=print)
    runner.start("https://jobs.example/1")      # returns at once
    # ... emit({"type": "log", "text": "[1/5] ..."})
    # ... emit({"type": "paused", "kind": "review", "payload": {...}, "summary": {...}})
    runner.resume({"decision": "approve", "text": "Dear ..."})
    # ... emit({"type": "finished", "saved_path": ..., "job_id": 3, ...})

Events are plain JSON-able dicts. `emit` is any function: the bridge sends
them to the web page; tests collect them in a list.

Only ONE run at a time: the agent uses the whole LLM, and a second run
would just queue behind it. start()/resume() while busy raise RuntimeError.
"""

import sqlite3
import sys
import threading
import uuid
from contextvars import ContextVar
from typing import Callable

from langgraph.types import Command

from job_agent import runlog
from job_agent.tracing import flush, record_decision, tracing_config

Event = dict
DECISIONS = ("approve", "edit", "reject")


# Where print() goes for the code running right now. A ContextVar, not a
# thread id: LangGraph/LangChain run parallel work on pool threads that
# COPY the caller's context, so prints from there still reach the log.
_log_route: ContextVar[Callable[[str], None] | None] = ContextVar("joblens_log_route", default=None)


class _RoutedStdout:
    """Replaces sys.stdout: print() from inside an agent run becomes a `log`
    event, print() from anywhere else goes to the real stdout.

    (The Qt worker swapped sys.stdout only while a run was going, which also
    captured other threads' prints. Routing by context avoids that.)
    """

    def __init__(self, real):
        self.real = real

    def write(self, text):
        route = _log_route.get()
        if route is None:
            return self.real.write(text)
        if text.strip():
            route(text.strip("\n"))  # CLI prints like print("\n...") add blank lines
        return len(text)

    def flush(self):
        self.real.flush()


def _install_stdout() -> None:
    if not isinstance(sys.stdout, _RoutedStdout):
        sys.stdout = _RoutedStdout(sys.stdout)


def default_graph():
    """The real agent with the on-disk checkpointer (paused runs survive restarts)."""
    from langgraph.checkpoint.sqlite import SqliteSaver

    from job_agent import paths
    from job_agent.cover_note import SAFE_SERDE
    from job_agent.graph import build_job_hunt_graph

    paths.ensure_dirs()
    conn = sqlite3.connect(paths.CHECKPOINT_DB, check_same_thread=False)
    return build_job_hunt_graph(checkpointer=SqliteSaver(conn, serde=SAFE_SERDE))


class AgentRunner:
    def __init__(self, emit: Callable[[Event], None], graph=None, interface: str = "desktop"):
        self._deliver = emit
        self.interface = interface
        self._graph = graph            # built lazily: importing the agent takes ~2 s
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.run_id: str | None = None
        self.last_pause: Event | None = None   # lets a reloaded page show the review again
        # For the suggested cover-note rating (Phase 11c), set as the run goes.
        self._ai_draft, self._revision, self._decision, self._final_text = "", 0, "", ""

    def emit(self, event: Event) -> None:
        """Deliver an event with log capture OFF. Otherwise anything that prints
        while delivering (a logger, pywebview) would become a log event, which
        is delivered, prints again... forever. (Found by the 12b real-agent run.)"""
        token = _log_route.set(None)
        try:
            self._deliver(event)
        finally:
            _log_route.reset(token)

    # ---- what the bridge calls ------------------------------------------------

    @property
    def busy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, url: str, fresh: bool = False) -> str:
        url = (url or "").strip()
        if not url:
            raise ValueError("Paste a job posting link (or the job text) first.")
        self.run_id = str(uuid.uuid4())
        self.last_pause = None
        self._ai_draft, self._revision, self._decision, self._final_text = "", 0, "", ""
        self._launch({"url": url, "fresh": bool(fresh)})
        return self.run_id

    def resume(self, answer: dict) -> None:
        """Your approve / edit / reject decision (= Command(resume=...))."""
        answer = self._check_answer(answer)
        record_decision(self.run_id, answer["decision"])
        self._decision = answer["decision"]
        self._final_text = answer.get("text", "")
        self._launch(Command(resume=answer))

    def paste_text(self, text: str) -> None:
        """Pasted job description: read_posting's interrupt() expects the text itself."""
        if not (self.last_pause and self.last_pause["kind"] == "paste_posting"):
            raise RuntimeError("The agent isn't waiting for pasted text.")
        if not (text or "").strip():
            raise ValueError("The pasted text is empty.")
        self._launch(Command(resume=text))

    def wait(self, timeout: float | None = None) -> bool:
        """Block until the current segment ends (for tests and shutdown)."""
        if self._thread:
            self._thread.join(timeout)
        return not self.busy

    # ---- internals --------------------------------------------------------------

    def _check_answer(self, answer: dict) -> dict:
        if not (self.last_pause and self.last_pause["kind"] == "review"):
            raise RuntimeError("There is no cover note waiting for your decision.")
        decision = (answer or {}).get("decision")
        if decision not in DECISIONS:
            raise ValueError(f"decision must be one of {', '.join(DECISIONS)}")
        if decision == "approve" and not (answer.get("text") or "").strip():
            raise ValueError("An approved cover note can't be empty.")
        if decision == "edit" and not (answer.get("feedback") or "").strip():
            raise ValueError("Say what should change in the draft.")
        clean = {"decision": decision}
        if decision == "approve":
            clean["text"] = answer["text"].strip()
        if decision == "edit":
            clean["feedback"] = answer["feedback"].strip()
        return clean

    def _launch(self, graph_input) -> None:
        with self._lock:  # two quick clicks must not start two runs
            if self.busy:
                raise RuntimeError("The agent is still working on the current step.")
            self.last_pause = None
            self._thread = threading.Thread(target=self._run, args=(graph_input,),
                                            name="joblens-agent", daemon=True)
            self._thread.start()

    def _config(self) -> dict:
        return {"configurable": {"thread_id": self.run_id},
                **tracing_config(self.run_id, interface=self.interface)}

    def _run(self, graph_input) -> None:
        self.emit({"type": "busy", "busy": True})
        _install_stdout()
        # This thread was started fresh, so its context is ours alone.
        _log_route.set(lambda text: self.emit({"type": "log", "text": text}))
        try:
            if self._graph is None:
                self.emit({"type": "log", "text": "Loading the agent..."})
                self._graph = default_graph()
            self._graph.invoke(graph_input, self._config())
            snapshot = self._graph.get_state({"configurable": {"thread_id": self.run_id}})
        except Exception as e:  # never let an error kill the thread silently
            self.emit({"type": "failed", "error": f"{type(e).__name__}: {e}"})
            return
        finally:
            _log_route.set(None)
            flush()
            self.emit({"type": "busy", "busy": False})

        if snapshot.interrupts:
            payload = dict(snapshot.interrupts[0].value)
            kind = "paste_posting" if payload.get("kind") == "paste_posting" else "review"
            if kind == "review":
                self._ai_draft, self._revision = payload.get("draft", ""), payload.get("revision", 0)
            self.last_pause = {"type": "paused", "kind": kind, "run_id": self.run_id,
                               "payload": payload, "summary": summary(snapshot.values)}
            self.emit(self.last_pause)
        else:
            values = snapshot.values
            suggested = (runlog.cover_note_outcome(self._decision, self._ai_draft,
                                                   self._final_text, self._revision)
                         if self._decision else None)
            self.emit({"type": "finished", "run_id": self.run_id,
                       "saved_path": values.get("saved_path"), "job_id": values.get("job_id"),
                       "decision": self._decision or None, "suggested_rating": suggested})


def summary(values: dict) -> dict:
    """Plain data for the review panel (the page gets JSON, not Pydantic objects)."""
    out = {}
    if values.get("job"):
        out["title"] = values["job"].title
        out["company"] = values["job"].company
    best = values.get("best_match")
    if best:
        out.update(
            fit_score=best.fit_score,
            breakdown=best.score_breakdown,
            resume=best.resume_name,
            matches=[{"requirement": m.requirement, "evidence": m.resume_evidence}
                     for m in best.analysis.matching_skills],
            gaps=list(best.analysis.missing_skills),
        )
    return out
