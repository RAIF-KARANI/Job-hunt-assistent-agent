"""
Run the LangGraph agent on a background thread and report what happens as events.

The same job the Qt app's agent worker did (v0.3; removed in 12i), without Qt:

    runner = AgentRunner(emit=print)
    runner.start("https://jobs.example/1")      # returns at once
    # ... emit({"type": "log", "text": "[1/5] ..."})
    # ... emit({"type": "paused", "kind": "review", "payload": {...}, "summary": {...}})
    runner.resume({"decision": "approve", "text": "Dear ..."})
    # ... emit({"type": "finished", "saved_path": ..., "job_id": 3, ...})

Events are plain JSON-able dicts. `emit` is any function: the bridge sends
them to the web page; tests collect them in a list.

Progress (Phase 12d): the agent reports progress by print()ing lines like
"[2/5] Comparing your resumes...". Besides passing every line on as a `log`
event, the runner turns the ones that mean something into structured
events, so the page never has to parse log text:

    {"type": "started", "run_id", "url", "at"}
    {"type": "step", "step": 2, "text": "Comparing your resumes with the job", "at"}
    {"type": "step_detail", "step": 2, "text": "best: AI_Engineer.pdf", "warn": False}
    {"type": "reused", "job_id": 3, "at"}         # analysis loaded from the tracker

The runner keeps the current run's events, so a reloaded page can replay them.

Only ONE run at a time: the agent uses the whole LLM, and a second run
would just queue behind it. start()/resume() while busy raise RuntimeError.
"""

import re
import sqlite3
import sys
import threading
import time
import uuid
from contextvars import ContextVar
from typing import Callable

from langchain_core.callbacks import BaseCallbackHandler
from langgraph.types import Command

from job_agent import runlog
from job_agent.llm import RunStopped
from job_agent.tracing import flush, record_decision, tracing_config

Event = dict
DECISIONS = ("approve", "edit", "reject")
MAX_HISTORY = 5000   # events kept for a page reload (a real run has ~100)

# The agent's progress lines (job_agent/graph.py _step, cover_note.py, fit.py).
STEP_LINE = re.compile(r"^\[(\d)/5\]\s*(.*?)\.*$")              # [2/5] Comparing your resumes...
DRAFT_LINE = re.compile(r"^\[draft\] writing draft #(\d+)")       # step 5 has no [5/5] line
REUSED_LINE = re.compile(r"^Already tracked as job #(\d+)")
SCORING_LINE = re.compile(r"^- scoring '(.+?)'")
SCORE_LINE = re.compile(r"^(\d+)/100\s+(.+?)\s+\[")                # 86/100  cv_ai   [skills ...]


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
        # A windowed .exe (PyInstaller, console=False) has no console:
        # sys.stdout is None there, and None.write() would crash every
        # print() that isn't part of a run.
        self.real = real

    def write(self, text):
        route = _log_route.get()
        if route is None:
            return self.real.write(text) if self.real is not None else len(text)
        if text.strip():
            route(text.strip("\n"))  # CLI prints like print("\n...") add blank lines
        return len(text)

    def flush(self):
        if self.real is not None:
            self.real.flush()


def _install_stdout() -> None:
    if not isinstance(sys.stdout, _RoutedStdout):
        sys.stdout = _RoutedStdout(sys.stdout)


class StopSignal(BaseCallbackHandler):
    """The Stop button (12j). A thread can't be killed from outside, so the
    run stops itself: once `stop()` is called, the next callback raises
    RunStopped. Ollama calls on_llm_new_token for EVERY token, even in a
    plain .invoke(), so an answer being written is cut off mid-way (its
    connection closes and Ollama stops generating). An API model that
    doesn't stream stops when its current call returns.

    raise_error = True: LangChain lets the exception through instead of
    logging and ignoring it, as it does for other callback errors."""

    raise_error = True

    def __init__(self):
        self.requested = threading.Event()

    def stop(self) -> None:
        self.requested.set()

    def _check(self, *args, **kwargs) -> None:
        if self.requested.is_set():
            raise RunStopped("Stopped by you.")

    on_chain_start = on_chat_model_start = on_llm_start = on_llm_new_token = on_tool_start = _check


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
        self._stop = StopSignal()  # replaced for every segment (_launch)
        self.run_id: str | None = None
        self.last_pause: Event | None = None   # lets a reloaded page show the review again
        self.history: list[Event] = []          # this run's events, for a reloaded page
        self._step = 0
        self._scores: dict[str, int] = {}       # resume -> fit, for "best: cv · fit 86"
        # For the suggested cover-note rating (Phase 11c), set as the run goes.
        self._ai_draft, self._revision, self._decision, self._final_text = "", 0, "", ""

    def emit(self, event: Event) -> None:
        """Deliver an event with log capture OFF. Otherwise anything that prints
        while delivering (a logger, pywebview) would become a log event, which
        is delivered, prints again... forever. (Found by the 12b real-agent run.)"""
        if event["type"] not in ("log", "busy"):
            event.setdefault("at", time.time())   # the page shows how long each step took
        if len(self.history) < MAX_HISTORY:
            self.history.append(event)
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
        with self._lock:
            if self.busy:
                raise RuntimeError("The agent is still working on the current step.")
            self.run_id = str(uuid.uuid4())
            self.history, self._step, self._scores = [], 0, {}
        self.last_pause = None
        self._ai_draft, self._revision, self._decision, self._final_text = "", 0, "", ""
        self.emit({"type": "started", "run_id": self.run_id, "url": url})
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

    def stop(self) -> bool:
        """Stop the step that's running (Stop button). Returns False if nothing
        is running. The run ends with a `stopped` event within moments."""
        with self._lock:
            if not self.busy:
                return False
            self._stop.stop()
        self.emit({"type": "stopping"})
        return True

    def _launch(self, graph_input) -> None:
        with self._lock:  # two quick clicks must not start two runs
            if self.busy:
                raise RuntimeError("The agent is still working on the current step.")
            self.last_pause = None
            self._stop = StopSignal()  # fresh for every segment
            self._thread = threading.Thread(target=self._run, args=(graph_input,),
                                            name="joblens-agent", daemon=True)
            self._thread.start()

    def _on_log(self, text: str) -> None:
        self.emit({"type": "log", "text": text})
        for line in text.splitlines():
            event = self._progress(line.strip())
            if event:
                self.emit(event)

    def _progress(self, line: str) -> Event | None:
        """One printed line -> a structured progress event, or None."""
        if m := STEP_LINE.match(line):
            self._step = int(m.group(1))
            return {"type": "step", "step": self._step, "text": m.group(2)}
        if m := DRAFT_LINE.match(line):
            self._step = 5
            n = int(m.group(1))
            return {"type": "step", "step": 5,
                    "text": "Writing the cover note" if n == 1 else f"Rewriting the cover note (draft {n})"}
        if m := REUSED_LINE.match(line):
            return {"type": "reused", "job_id": int(m.group(1))}
        if not self._step:
            return None
        if m := SCORING_LINE.match(line):
            return {"type": "step_detail", "step": self._step, "text": f"Scoring {m.group(1)}", "warn": False}
        if m := SCORE_LINE.match(line):
            self._scores[m.group(2)] = int(m.group(1))
            return None
        if self._step == 2 and line.startswith("-> best: "):
            name = line[len("-> best: "):]
            fit = f" · fit {self._scores[name]}" if name in self._scores else ""
            return {"type": "step_detail", "step": 2, "text": f"best: {name}{fit}", "warn": False}
        if self._step == 2 and line.startswith("-> ") and "best: " in self._last_detail(2):
            return None  # the verdict paragraph: in the log, too long for the timeline
        if line.startswith("-> "):
            return {"type": "step_detail", "step": self._step, "text": line[3:], "warn": False}
        if line.startswith("! "):
            return {"type": "step_detail", "step": self._step, "text": line[2:], "warn": True}
        return None

    def _last_detail(self, step: int) -> str:
        """The last detail sent for a step (this run)."""
        for e in reversed(self.history):
            if e["type"] == "step_detail" and e["step"] == step:
                return e["text"]
        return ""

    def _config(self) -> dict:
        config = tracing_config(self.run_id, interface=self.interface)
        config["callbacks"] = [*config.get("callbacks", []), self._stop]
        return {"configurable": {"thread_id": self.run_id}, **config}

    def _run(self, graph_input) -> None:
        self.emit({"type": "busy", "busy": True})
        _install_stdout()
        # This thread was started fresh, so its context is ours alone.
        _log_route.set(self._on_log)
        try:
            if self._graph is None:
                self.emit({"type": "log", "text": "Loading the agent..."})
                self._graph = default_graph()
            self._graph.invoke(graph_input, self._config())
            snapshot = self._graph.get_state({"configurable": {"thread_id": self.run_id}})
        except RunStopped:
            # Nothing is saved to the tracker; the steps already done stay in
            # the checkpoint (a "continue" feature could use them: Phase 14).
            self.emit({"type": "stopped", "run_id": self.run_id})
            return
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
