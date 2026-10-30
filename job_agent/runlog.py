"""
Phase 11: JobLens' own run log + quality checks + feedback, in local SQLite.

Why: Langfuse needs a server (Docker), so people who download JobLens had no
way to see how the agent performs. This module records the same essentials
in the tracker database - always on, private, nothing to install:

    runs           one row per run (= LangGraph thread_id): time, tokens, status
    run_steps      how long each pipeline step took
    run_llm_calls  every LLM call: model, input/output tokens, seconds
    run_quality    automatic quality checks per run (11b)
    run_feedback   your ratings (11c)

How it records (11a): RunRecorder is a LangChain CALLBACK HANDLER - the same
mechanism Langfuse uses. LangChain calls it when a step / LLM call / tool
starts and ends. It buffers in memory and writes once, when the top-level
graph finishes a segment (verified in Phase 11: that callback fires even when
the run pauses at interrupt(), and carries the full state).
"""

import threading
import time
from datetime import datetime, timezone
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

from job_agent import tracker

# Graph nodes worth timing (pipeline + cover-note subgraph + research agent).
TIMED_STEPS = {
    "check_tracker", "read_posting", "analyze_fit", "research_company",
    "save_to_tracker", "cover_note", "draft", "review", "save", "agent", "tools",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id         TEXT PRIMARY KEY,           -- LangGraph thread_id
    started_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    interface      TEXT,                       -- cli / web / desktop
    provider       TEXT,
    model          TEXT,
    job_id         INTEGER,
    status         TEXT,                       -- paused / done / error
    decision       TEXT,                       -- approve / reject (when done)
    segments       INTEGER DEFAULT 0,          -- 1 = start, +1 per resume
    agent_seconds  REAL DEFAULT 0,             -- working time, waiting excluded
    llm_calls      INTEGER DEFAULT 0,
    input_tokens   INTEGER DEFAULT 0,
    output_tokens  INTEGER DEFAULT 0,
    tool_calls     INTEGER DEFAULT 0,
    tool_failures  INTEGER DEFAULT 0,
    error          TEXT,
    tracing        TEXT                        -- off / langfuse / langsmith (12f2)
);
CREATE TABLE IF NOT EXISTS run_steps (
    run_id TEXT NOT NULL, step TEXT NOT NULL, seconds REAL, started_at TEXT
);
CREATE TABLE IF NOT EXISTS run_llm_calls (
    run_id TEXT NOT NULL, step TEXT, model TEXT,
    input_tokens INTEGER, output_tokens INTEGER, seconds REAL, started_at TEXT
);
CREATE TABLE IF NOT EXISTS run_quality (
    run_id TEXT NOT NULL, check_name TEXT NOT NULL, value REAL,
    PRIMARY KEY (run_id, check_name)          -- recomputed per segment, never duplicated
);
CREATE TABLE IF NOT EXISTS run_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT, job_id INTEGER,
    aspect TEXT NOT NULL,                     -- fit_score / cover_note
    rating TEXT NOT NULL,
    comment TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

# Allowed ratings for your feedback (11c).
FEEDBACK_OPTIONS = {
    "fit_score": ["too low", "about right", "too high"],
    "cover_note": ["usable as is", "needed edits", "not usable"],
}


# Columns added after a table was first released: (table, column, type).
# CREATE TABLE IF NOT EXISTS never changes an existing table, so databases
# made by an older JobLens version need these added - a tiny "migration".
MIGRATIONS = [("runs", "decision", "TEXT"), ("runs", "tracing", "TEXT")]


def init_db() -> None:
    tracker.init_db()
    with tracker._db() as conn:
        conn.executescript(SCHEMA)
        for table, column, sql_type in MIGRATIONS:
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# 11b: automatic quality checks, computed from the run's final state (pure)
# ---------------------------------------------------------------------------


def quality_from_state(values: dict) -> dict[str, float]:
    """The safety nets that fired during this run, as numbers.

    Only checks whose data exists are returned: e.g. a tracked job that skips
    the analysis has no evidence checks, only cover-note ones.
    """
    q: dict[str, float] = {}
    matches = values.get("all_matches") or []
    if matches:
        verified = sum(len(m.analysis.matching_skills) for m in matches)
        fake = sum(len(m.rejected_matches) for m in matches)
        judged = sum(len(m.unsupported_matches) for m in matches)
        claimed = verified + fake + judged
        q["claims_checked"] = claimed
        q["fake_quotes_caught"] = fake          # quote not in the resume (Phase 2 check)
        q["judge_rejections"] = judged          # quote real but doesn't prove it (Phase 7 judge)
        if claimed:
            q["evidence_pass_rate"] = verified / claimed
    research = values.get("research_checks")
    if research:
        q["invented_urls_removed"] = research.get("invented_urls", 0)
        q["invented_dates_removed"] = research.get("invented_dates", 0)
    if values.get("draft") is not None:
        q["number_warnings"] = len(values.get("warnings") or [])
        q["draft_revisions"] = values.get("revision", 0)
    return q


def status_from_state(values: dict) -> str:
    """'done' once you approved or rejected; otherwise the run is paused."""
    return "done" if values.get("decision") in ("approve", "reject") else "paused"


# ---------------------------------------------------------------------------
# 11a: the recorder (a LangChain callback handler)
# ---------------------------------------------------------------------------


class RunRecorder(BaseCallbackHandler):
    """Records one graph segment and writes it to SQLite when the segment ends.

    Callbacks can arrive from several threads (LangGraph runs tool calls in
    parallel), so the buffers are protected by a lock.
    """

    def __init__(self, run_id: str, interface: str, provider: str, model: str,
                 tracing: str = "off"):
        self.run_id, self.interface = run_id, interface
        self.provider, self.model = provider, model
        self.tracing = tracing  # so the Evals screen links only runs that have a trace
        self._lock = threading.Lock()
        self._starts: dict[UUID, tuple[float, str, str | None]] = {}  # run -> (t0, kind, step)
        self.steps: list[tuple[str, float, str]] = []
        self.llm_calls: list[tuple[str | None, str, int, int, float, str]] = []
        self.tool_calls = 0
        self.tool_failures = 0

    # --- chains (graph + nodes) ---
    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None,
                       metadata=None, **kwargs):
        name, node = kwargs.get("name"), (metadata or {}).get("langgraph_node")
        if parent_run_id is None:
            self._starts[run_id] = (time.time(), "root", None)
            self.segment_started_at = _now()  # the run's start, not when it's first written
        elif name == node and name in TIMED_STEPS:  # the node itself, not its insides
            self._starts[run_id] = (time.time(), "step", name)

    def on_chain_end(self, outputs, *, run_id, parent_run_id=None, **kwargs):
        start = self._starts.pop(run_id, None)
        if not start:
            return
        t0, kind, step = start
        if kind == "step":
            with self._lock:
                self.steps.append((step, time.time() - t0, _now()))
        else:  # the top-level graph finished this segment (also when paused)
            self._write(time.time() - t0, outputs if isinstance(outputs, dict) else {})

    def on_chain_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        start = self._starts.pop(run_id, None)
        if start and start[1] == "root":
            self._write(time.time() - start[0], {}, error=f"{type(error).__name__}: {error}")

    # --- LLM calls ---
    def on_chat_model_start(self, serialized, messages, *, run_id, metadata=None, **kwargs):
        self._starts[run_id] = (time.time(), "llm", (metadata or {}).get("langgraph_node"))

    def on_llm_end(self, response, *, run_id, **kwargs):
        start = self._starts.pop(run_id, None)
        if not start:
            return
        usage = {}
        try:
            usage = response.generations[0][0].message.usage_metadata or {}
        except (AttributeError, IndexError):
            pass
        with self._lock:
            self.llm_calls.append((start[2], self.model, int(usage.get("input_tokens", 0)),
                                   int(usage.get("output_tokens", 0)), time.time() - start[0],
                                   _now()))

    # --- tools ---
    def on_tool_end(self, output, *, run_id, **kwargs):
        text = getattr(output, "content", output)
        with self._lock:
            self.tool_calls += 1
            if "search failed" in str(text).lower()[:200]:
                self.tool_failures += 1  # tools return errors as text (Phase 3)

    # --- writing ---
    def _write(self, seconds: float, values: dict, error: str | None = None) -> None:
        """One transaction per segment; a logging problem must never break a run."""
        try:
            init_db()
            with self._lock:
                steps, calls = list(self.steps), list(self.llm_calls)
                self.steps.clear()
                self.llm_calls.clear()
                tools, failures = self.tool_calls, self.tool_failures
                self.tool_calls = self.tool_failures = 0
            status = "error" if error else status_from_state(values)
            with tracker._db() as conn:
                decision = values.get("decision") if status == "done" else None
                conn.execute(
                    """INSERT INTO runs (run_id, started_at, updated_at, interface, provider, model,
                                         job_id, status, decision, segments, agent_seconds, llm_calls,
                                         input_tokens, output_tokens, tool_calls, tool_failures, error, tracing)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(run_id) DO UPDATE SET
                           updated_at = excluded.updated_at,
                           job_id = COALESCE(excluded.job_id, runs.job_id),
                           status = excluded.status,
                           decision = COALESCE(excluded.decision, runs.decision),
                           segments = runs.segments + 1,
                           agent_seconds = runs.agent_seconds + excluded.agent_seconds,
                           llm_calls = runs.llm_calls + excluded.llm_calls,
                           input_tokens = runs.input_tokens + excluded.input_tokens,
                           output_tokens = runs.output_tokens + excluded.output_tokens,
                           tool_calls = runs.tool_calls + excluded.tool_calls,
                           tool_failures = runs.tool_failures + excluded.tool_failures,
                           error = excluded.error,
                           tracing = COALESCE(runs.tracing, excluded.tracing)""",
                    # started_at: only used for the first segment (the INSERT); a
                    # resume keeps the original start (not in the UPDATE list).
                    (self.run_id, getattr(self, "segment_started_at", _now()), _now(),
                     self.interface, self.provider, self.model,
                     values.get("job_id"), status, decision, seconds, len(calls),
                     sum(c[2] for c in calls), sum(c[3] for c in calls), tools, failures, error,
                     self.tracing))
                conn.executemany("INSERT INTO run_steps VALUES (?, ?, ?, ?)",
                                 [(self.run_id, s, sec, t) for s, sec, t in steps])
                conn.executemany("INSERT INTO run_llm_calls VALUES (?, ?, ?, ?, ?, ?, ?)",
                                 [(self.run_id, *c) for c in calls])
                conn.executemany(
                    "INSERT OR REPLACE INTO run_quality VALUES (?, ?, ?)",
                    [(self.run_id, k, v) for k, v in quality_from_state(values).items()])
        except Exception as e:  # observability must never break the product
            print(f"! run log not saved: {e}")


# ---------------------------------------------------------------------------
# 11c: your feedback
# ---------------------------------------------------------------------------


def save_feedback(run_id: str | None, job_id: int | None, aspect: str, rating: str,
                  comment: str = "") -> None:
    if rating not in FEEDBACK_OPTIONS.get(aspect, []):
        raise ValueError(f"Unknown rating '{rating}' for {aspect}")
    init_db()
    with tracker._db() as conn:
        conn.execute("INSERT INTO run_feedback (run_id, job_id, aspect, rating, comment) "
                     "VALUES (?, ?, ?, ?, ?)", (run_id, job_id, aspect, rating, comment or None))


def cover_note_outcome(decision: str, ai_draft: str, final_text: str, revision: int) -> str:
    """What you DID with the draft - a suggested cover-note rating.

    (Compare with the AI's draft as shown to you: after approval, review_node
    replaces the state's draft with your edited text, so the state can't tell.)
    """
    if decision == "reject":
        return "not usable"
    edited = final_text.strip() != ai_draft.strip()
    return "needed edits" if (edited or revision > 1) else "usable as is"
