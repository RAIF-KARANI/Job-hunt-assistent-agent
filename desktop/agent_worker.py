"""
Run the LangGraph agent on a background thread and talk to the GUI with signals.

The "worker object" pattern (the standard way to do long jobs in Qt):

    worker = AgentWorker()
    thread = QThread()
    worker.moveToThread(thread)   # the worker's slots now RUN on `thread`
    thread.start()

    gui:    self.start_requested.emit(url)   --(queued)-->  worker.start(url)
    worker: self.log.emit("[2/5] ...")        --(queued)-->  gui appends to log

Signals between threads are QUEUED: Qt hands them to the receiving
thread's event loop. So the GUI never calls the 3-minute graph directly,
and the worker never touches a widget. That's the whole trick.
"""

import sqlite3
import sys
import uuid

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from PySide6.QtCore import QObject, Signal, Slot

from job_agent import paths
from job_agent.cover_note import SAFE_SERDE
from job_agent.graph import build_job_hunt_graph
from job_agent.tracing import flush, record_decision, tracing_config


class _SignalWriter:
    """Stands in for sys.stdout while the graph runs: every print() from the
    agent's nodes becomes a `log` signal for the GUI's log panel."""

    def __init__(self, signal):
        self.signal = signal

    def write(self, text):
        if text.strip():
            # strip("\n"): CLI prints like print("\n...") would add blank lines
            self.signal.emit(text.strip("\n"))

    def flush(self):
        pass


class AgentWorker(QObject):
    log = Signal(str)            # one line of progress
    paused = Signal(dict, dict)  # (interrupt payload, summary of the job/fit)
    finished = Signal(dict)      # {"saved_path": ... or None, "job_id": ...}
    failed = Signal(str)         # error message

    def __init__(self):
        super().__init__()
        paths.ensure_dirs()
        conn = sqlite3.connect(paths.CHECKPOINT_DB, check_same_thread=False)
        # Same checkpoint database as the web UI: paused runs live on disk.
        self.graph = build_job_hunt_graph(checkpointer=SqliteSaver(conn, serde=SAFE_SERDE))
        self.thread_id = None

    # ---- slots (run on the worker thread) ------------------------------------

    @Slot(str, bool)
    def start(self, url: str, fresh: bool):
        self.thread_id = str(uuid.uuid4())
        self._run({"url": url, "fresh": fresh})

    @Slot(dict)
    def resume(self, answer: dict):
        """Your approve / edit / reject decision (= Command(resume=...))."""
        record_decision(self.thread_id, answer["decision"])
        self._run(Command(resume=answer))

    @Slot(str)
    def resume_with_text(self, text: str):
        """Pasted job description: read_posting's interrupt() expects the text itself."""
        self._run(Command(resume=text))

    # ---- the actual work -----------------------------------------------------

    def _config(self) -> dict:
        return {"configurable": {"thread_id": self.thread_id},
                **tracing_config(self.thread_id, interface="desktop")}

    def _run(self, graph_input):
        real_stdout, sys.stdout = sys.stdout, _SignalWriter(self.log)
        try:
            self.graph.invoke(graph_input, self._config())
        except Exception as e:  # never let an error kill the thread silently
            self.failed.emit(f"{type(e).__name__}: {e}")
            return
        finally:
            sys.stdout = real_stdout
            flush()

        snapshot = self.graph.get_state({"configurable": {"thread_id": self.thread_id}})
        if snapshot.interrupts:
            self.paused.emit(snapshot.interrupts[0].value, self._summary(snapshot.values))
        else:
            values = snapshot.values
            self.finished.emit({"saved_path": values.get("saved_path"),
                                "job_id": values.get("job_id")})

    @staticmethod
    def _summary(values: dict) -> dict:
        """Plain data for the review panel (widgets need no Pydantic objects)."""
        out = {}
        if values.get("job"):
            out["title"] = f"{values['job'].title} @ {values['job'].company}"
        best = values.get("best_match")
        if best:
            out.update(
                fit_score=best.fit_score,
                breakdown=best.score_breakdown,
                resume=best.resume_name,
                matches=[f"{m.requirement} — “{m.resume_evidence}”"
                         for m in best.analysis.matching_skills],
                gaps=list(best.analysis.missing_skills),
            )
        return out
