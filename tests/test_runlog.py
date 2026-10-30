"""
Tests for JobLens' own run log, quality checks and feedback (Phase 11).

The recorder is tested with a tiny real LangGraph graph (no LLM) that
pauses at interrupt() and resumes - the same two-segment shape as a real run.
"""

from typing import TypedDict

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from job_agent import runlog, tracker
from job_agent.models import FitAnalysis, ResumeMatch, SkillMatch


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "jobs.db")


def rows(sql, *args):
    with tracker._db() as conn:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]


# ---- 11a: the recorder with a real (tiny) graph --------------------------------

class S(TypedDict, total=False):
    job_id: int
    draft: str
    warnings: list
    revision: int
    decision: str


def build_graph():
    llm = FakeListChatModel(responses=["Dear Hiring Team"])

    def draft(state):
        return {"job_id": 7, "draft": llm.invoke("write").content, "warnings": ["300"], "revision": 1}

    def review(state):
        return {"decision": interrupt("approve?")}

    g = StateGraph(S)
    g.add_node("draft", draft)
    g.add_node("review", review)
    g.add_edge(START, "draft")
    g.add_edge("draft", "review")
    g.add_edge("review", END)
    return g.compile(checkpointer=InMemorySaver())


def run_segment(graph, graph_input, run_id="run-1"):
    recorder = runlog.RunRecorder(run_id, "desktop", "ollama", "qwen3:8b")
    graph.invoke(graph_input, {"configurable": {"thread_id": run_id}, "callbacks": [recorder]})


def test_paused_then_finished_run_is_one_row_with_two_segments():
    graph = build_graph()
    run_segment(graph, {})                                   # pauses at interrupt()
    run = rows("SELECT * FROM runs")[0]
    assert (run["status"], run["segments"], run["job_id"]) == ("paused", 1, 7)
    assert run["interface"] == "desktop" and run["model"] == "qwen3:8b"

    first_start = run["started_at"]
    run_segment(graph, Command(resume="reject"))             # you decide
    run = rows("SELECT * FROM runs")
    assert len(run) == 1                                     # same run, not a new row
    assert (run[0]["status"], run[0]["segments"], run[0]["decision"]) == ("done", 2, "reject")
    assert run[0]["agent_seconds"] > 0
    assert run[0]["started_at"] == first_start               # a resume keeps the original start


def test_steps_llm_calls_and_quality_are_recorded():
    graph = build_graph()
    run_segment(graph, {})
    steps = {r["step"] for r in rows("SELECT step FROM run_steps")}
    # A node that pauses at interrupt() doesn't "finish" (it ends with a
    # GraphInterrupt event), so only `draft` completed in segment 1...
    assert steps == {"draft"}                                # nodes only, not their insides
    run_segment(graph, Command(resume="approve"))
    steps = [r["step"] for r in rows("SELECT step FROM run_steps ORDER BY rowid")]
    assert steps == ["draft", "review"]                      # ...and `review` completes on resume
    calls = rows("SELECT * FROM run_llm_calls")
    assert len(calls) == 1 and calls[0]["step"] == "draft"
    quality = {r["check_name"]: r["value"] for r in rows("SELECT * FROM run_quality")}
    assert quality == {"number_warnings": 1, "draft_revisions": 1}


def test_quality_rows_are_replaced_not_duplicated_on_resume():
    graph = build_graph()
    run_segment(graph, {})
    run_segment(graph, Command(resume="approve"))
    assert len(rows("SELECT * FROM run_quality WHERE check_name = 'number_warnings'")) == 1


def test_errors_are_recorded_not_raised_by_the_logger():
    def boom(state):
        raise ValueError("model offline")
    g = StateGraph(S)
    g.add_node("draft", boom)
    g.add_edge(START, "draft")
    graph = g.compile(checkpointer=InMemorySaver())
    with pytest.raises(ValueError):                          # the run's own error still surfaces
        run_segment(graph, {}, run_id="bad")
    run = rows("SELECT status, error FROM runs WHERE run_id = 'bad'")[0]
    assert run["status"] == "error" and "model offline" in run["error"]


def test_old_database_gets_new_columns():
    # A runs table from before the `decision` column existed:
    with tracker._db() as conn:
        conn.execute("CREATE TABLE runs (run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, "
                     "updated_at TEXT NOT NULL)")
    runlog.init_db()
    columns = {r["name"] for r in rows("PRAGMA table_info(runs)")}
    assert {"decision", "tracing"} <= columns


def test_the_tracer_in_use_is_recorded():
    graph = build_graph()
    recorder = runlog.RunRecorder("run-t", "desktop", "ollama", "qwen3:8b", tracing="langfuse")
    graph.invoke({}, {"configurable": {"thread_id": "run-t"}, "callbacks": [recorder]})
    assert rows("SELECT tracing FROM runs")[0]["tracing"] == "langfuse"


# ---- 11b: quality checks from state (pure) --------------------------------------

def _match(verified, fake, judged):
    analysis = FitAnalysis(
        matching_skills=[SkillMatch(requirement=f"r{i}", resume_evidence="q") for i in range(verified)],
        missing_skills=[], talking_points=[], verdict="ok")
    return ResumeMatch(resume_name="cv", analysis=analysis,
                       rejected_matches=[SkillMatch(requirement="x", resume_evidence="y")] * fake,
                       unsupported_matches=["z - reason"] * judged)


def test_quality_checks_count_every_safety_net():
    values = {"all_matches": [_match(4, 1, 2), _match(3, 0, 1)],
              "research_checks": {"invented_urls": 2, "invented_dates": 1},
              "draft": "text", "warnings": ["300"], "revision": 2}
    q = runlog.quality_from_state(values)
    assert q["claims_checked"] == 11
    assert q["fake_quotes_caught"] == 1 and q["judge_rejections"] == 3
    assert q["evidence_pass_rate"] == pytest.approx(7 / 11)
    assert q["invented_urls_removed"] == 2 and q["invented_dates_removed"] == 1
    assert q["number_warnings"] == 1 and q["draft_revisions"] == 2


def test_reused_job_has_only_cover_note_checks():
    q = runlog.quality_from_state({"draft": "text", "warnings": [], "revision": 1})
    assert set(q) == {"number_warnings", "draft_revisions"}


def test_status_from_state():
    assert runlog.status_from_state({"decision": "approve"}) == "done"
    assert runlog.status_from_state({"decision": "edit"}) == "paused"   # waiting for the rewrite review
    assert runlog.status_from_state({}) == "paused"


# ---- 11c: feedback ---------------------------------------------------------------

def test_feedback_is_saved_and_validated():
    runlog.save_feedback("run-1", 7, "fit_score", "about right", "spot on")
    runlog.save_feedback("run-1", 7, "cover_note", "needed edits")
    saved = rows("SELECT aspect, rating, comment FROM run_feedback ORDER BY id")
    assert saved == [{"aspect": "fit_score", "rating": "about right", "comment": "spot on"},
                     {"aspect": "cover_note", "rating": "needed edits", "comment": None}]
    with pytest.raises(ValueError):
        runlog.save_feedback("run-1", 7, "fit_score", "amazing")


def test_cover_note_outcome_suggests_a_rating():
    assert runlog.cover_note_outcome("reject", "AI", "AI", 1) == "not usable"
    assert runlog.cover_note_outcome("approve", "AI text", "AI text", 1) == "usable as is"
    assert runlog.cover_note_outcome("approve", "AI text", "My edited text", 1) == "needed edits"
    assert runlog.cover_note_outcome("approve", "AI text", "AI text", 3) == "needed edits"  # rewrites
