"""
Tests for the version-2 desktop bridge (Phase 12b): runner + API, no window, no LLM.

The agent is replaced by a tiny real LangGraph graph with the same two
pauses as the real one: interrupt({"kind": "approval", ...}) for the cover
note and interrupt({"kind": "paste_posting", ...}) for an unreadable page.
"""

import json
import os
import sys
import threading
import time
from typing import TypedDict

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from desktop_web import runner as runner_mod
from desktop_web.bridge import WRITABLE_SETTINGS, Api
from job_agent import cover_note, settings, tracker
from job_agent.models import FitAnalysis, JobPosting, ResumeMatch


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "jobs.db")
    monkeypatch.setattr(cover_note, "NOTES_DIR", tmp_path / "notes")
    monkeypatch.setattr(settings, "APP_HOME", tmp_path)
    monkeypatch.setattr(settings, "ENV_FILE", tmp_path / ".env")
    # save_settings() writes os.environ too: register every key so it's restored.
    for key in [*WRITABLE_SETTINGS, "ANTHROPIC_API_KEY"]:
        monkeypatch.setenv(key, settings.DEFAULTS.get(key, ""))


# ---- a stand-in agent --------------------------------------------------------

class S(TypedDict, total=False):
    url: str
    fresh: bool
    text: str
    job_id: int
    draft: str
    warnings: list
    revision: int
    answer: dict
    saved_path: str


def review_graph(block: threading.Event | None = None, fail: bool = False):
    def draft(state):
        if block:
            block.wait(5)
        if fail:
            raise RuntimeError("model crashed")
        print("\n[5/5] Drafting the cover note")
        revision = state.get("revision", 0) + 1
        return {"job_id": 7, "draft": f"Dear team, draft {revision}", "warnings": ["40%"],
                "revision": revision}

    def review(state):
        return {"answer": interrupt({"kind": "approval", "draft": state["draft"],
                                     "warnings": state["warnings"], "revision": state["revision"]})}

    def save(state):
        return {"saved_path": "notes/7.md"}

    def route(state):
        return {"approve": "save", "edit": "draft"}.get(state["answer"]["decision"], END)

    g = StateGraph(S)
    g.add_node("draft", draft)
    g.add_node("review", review)
    g.add_node("save", save)
    g.add_edge(START, "draft")
    g.add_edge("draft", "review")
    g.add_conditional_edges("review", route, ["save", "draft", END])
    g.add_edge("save", END)
    return g.compile(checkpointer=InMemorySaver())


def paste_graph():
    def read(state):
        text = interrupt({"kind": "paste_posting", "reason": "403 Forbidden"})
        print(f"read {len(text)} characters")
        return {"text": text}

    g = StateGraph(S)
    g.add_node("read", read)
    g.add_edge(START, "read")
    g.add_edge("read", END)
    return g.compile(checkpointer=InMemorySaver())


def make_api(graph):
    events = []
    return Api(send=events.append, graph=graph), events


def step(api):
    assert api._runner.wait(10), "the run did not finish in time"


def of_type(events, kind):
    return [e for e in events if e["type"] == kind]


# ---- the run -----------------------------------------------------------------

def test_start_streams_logs_then_pauses_for_review():
    api, events = make_api(review_graph())
    run_id = api.start_run("https://jobs.example/1")["run_id"]
    step(api)
    assert events[0]["type"] == "started" and events[0]["url"] == "https://jobs.example/1"
    assert events[1] == {"type": "busy", "busy": True}
    assert {"type": "log", "text": "[5/5] Drafting the cover note"} in events
    paused = of_type(events, "paused")[-1]
    assert paused["kind"] == "review" and paused["run_id"] == run_id
    assert paused["payload"]["draft"] == "Dear team, draft 1"
    assert paused["payload"]["warnings"] == ["40%"]
    # A reloaded page can catch up:
    state = api.run_state()
    assert state["busy"] is False and state["paused"]["kind"] == "review"


def test_approve_finishes_with_saved_note_and_suggested_rating():
    api, events = make_api(review_graph())
    api.start_run("https://jobs.example/1")
    step(api)
    api.resume({"decision": "approve", "text": "  Dear team, draft 1  "})
    step(api)
    done = of_type(events, "finished")[-1]
    assert done["saved_path"] == "notes/7.md" and done["job_id"] == 7
    assert done["decision"] == "approve"
    assert done["suggested_rating"] == "usable as is"   # approved unchanged
    assert api.run_state()["paused"] is None


def test_edit_redrafts_then_reject_saves_nothing():
    api, events = make_api(review_graph())
    api.start_run("https://jobs.example/1")
    step(api)
    api.resume({"decision": "edit", "feedback": "shorter"})
    step(api)
    assert of_type(events, "paused")[-1]["payload"]["revision"] == 2
    api.resume({"decision": "reject"})
    step(api)
    done = of_type(events, "finished")[-1]
    assert done["saved_path"] is None and done["suggested_rating"] == "not usable"


def test_run_is_recorded_in_the_run_log():
    api, _ = make_api(review_graph())
    run_id = api.start_run("https://jobs.example/1")["run_id"]
    step(api)
    with tracker._db() as conn:
        row = conn.execute("SELECT status, interface FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    assert dict(row) == {"status": "paused", "interface": "desktop"}


@pytest.mark.parametrize("answer, error", [
    ({"decision": "maybe"}, ValueError),
    ({"decision": "approve", "text": "   "}, ValueError),
    ({"decision": "edit"}, ValueError),
    (None, ValueError),
])
def test_bad_answers_are_refused(answer, error):
    api, _ = make_api(review_graph())
    api.start_run("https://jobs.example/1")
    step(api)
    with pytest.raises(error):
        api.resume(answer)


def test_nothing_to_resume_before_a_pause():
    api, _ = make_api(review_graph())
    with pytest.raises(RuntimeError):
        api.resume({"decision": "reject"})
    with pytest.raises(ValueError):
        api.start_run("   ")


def test_only_one_run_at_a_time():
    block = threading.Event()
    api, _ = make_api(review_graph(block=block))
    api.start_run("https://jobs.example/1")
    try:
        assert api.run_state()["busy"] is True
        with pytest.raises(RuntimeError):
            api.start_run("https://jobs.example/2")
    finally:
        block.set()
        step(api)


def test_a_crash_becomes_a_failed_event():
    api, events = make_api(review_graph(fail=True))
    api.start_run("https://jobs.example/1")
    step(api)
    assert of_type(events, "failed")[-1]["error"] == "RuntimeError: model crashed"
    assert events[-1] == {"type": "busy", "busy": False}
    assert api.run_state()["busy"] is False


def test_paste_flow():
    api, events = make_api(paste_graph())
    api.start_run("https://linkedin.example/job")
    step(api)
    paused = of_type(events, "paused")[-1]
    assert paused["kind"] == "paste_posting" and paused["payload"]["reason"] == "403 Forbidden"
    with pytest.raises(RuntimeError):         # it wants text, not a decision
        api.resume({"decision": "reject"})
    with pytest.raises(ValueError):
        api.paste_text("  ")
    api.paste_text("Senior Engineer at Acme ...")
    step(api)
    assert {"type": "log", "text": "read 27 characters"} in events
    assert of_type(events, "finished")


def test_a_sink_that_prints_does_not_loop(capsys):
    """Regression: print() inside event delivery used to become a log event,
    which was delivered, printed again... (RecursionError in the agent thread)."""
    events = []

    def noisy_send(event):
        print("delivering", event["type"])        # like a logger or pywebview would
        events.append(event)

    api = Api(send=noisy_send, graph=review_graph())
    api.start_run("https://jobs.example/1")
    step(api)
    logs = [e["text"] for e in of_type(events, "log")]
    assert logs == ["[5/5] Drafting the cover note"]   # the agent's print only
    assert of_type(events, "paused") and not of_type(events, "failed")


def test_stdout_routing_follows_the_run_not_the_thread():
    from langchain_core.runnables.config import ContextThreadPoolExecutor

    real = []
    out = runner_mod._RoutedStdout(real=type("Sink", (), {"write": lambda s, t: real.append(t),
                                                          "flush": lambda s: None})())
    seen = []

    def agent_run():
        runner_mod._log_route.set(seen.append)
        out.write("\nhello\n")
        out.write("   ")                          # blank lines are dropped
        # Pool threads that copy the context (as LangGraph does) still log:
        with ContextThreadPoolExecutor() as pool:
            pool.submit(out.write, "from a tool thread").result()

    t = threading.Thread(target=agent_run)
    t.start()
    t.join()
    out.write("from the main thread")             # not part of any run
    assert seen == ["hello", "from a tool thread"]
    assert real == ["from the main thread"]
    assert sys.stdout is not out                  # nothing global was replaced here


# ---- progress for the steps timeline (12d) -----------------------------------

def progress_graph():
    """Prints exactly what the real agent prints, using its own functions where it has them."""
    from job_agent.graph import _step

    def work(state):
        _step(1, "Reading the job posting...")
        print("  -> AI Engineer @ Acme (Remote)")
        _step(2, "Comparing your resumes with the job...")
        print("  - scoring 'cv_ai'...")
        print("  - writing the verdict...")
        print("   86/100  cv_ai   [skills 34/40]")
        print("  -> best: cv_ai")
        print("  -> Strong match overall; the only gap is Kubernetes.")   # the verdict
        _step(3, "Researching the company (agent picks its own searches)...")
        print("  [agent] decides to call web_search({'query': 'Acme'})")
        print("  ! research failed (timeout) - continuing without it")
        _step(4, "Saving to the job tracker...")
        print("  [draft] writing draft #2...")
        return {}

    g = StateGraph(S)
    g.add_node("work", work)
    g.add_edge(START, "work")
    g.add_edge("work", END)
    return g.compile(checkpointer=InMemorySaver())


def test_progress_lines_become_step_events():
    api, events = make_api(progress_graph())
    api.start_run("https://jobs.example/1")
    step(api)
    progress = [{k: e[k] for k in e if k != "at"} for e in events
                if e["type"] in ("step", "step_detail")]
    assert progress == [
        {"type": "step", "step": 1, "text": "Reading the job posting"},
        {"type": "step_detail", "step": 1, "text": "AI Engineer @ Acme (Remote)", "warn": False},
        {"type": "step", "step": 2, "text": "Comparing your resumes with the job"},
        {"type": "step_detail", "step": 2, "text": "Scoring cv_ai", "warn": False},
        {"type": "step_detail", "step": 2, "text": "Writing the verdict", "warn": False},
        {"type": "step_detail", "step": 2, "text": "best: cv_ai · fit 86", "warn": False},
        {"type": "step", "step": 3, "text": "Researching the company (agent picks its own searches)"},
        {"type": "step_detail", "step": 3, "text": "research failed (timeout) - continuing without it",
         "warn": True},
        {"type": "step", "step": 4, "text": "Saving to the job tracker"},
        {"type": "step", "step": 5, "text": "Rewriting the cover note (draft 2)"},
    ]
    assert all(e["at"] > 0 for e in events if e["type"] == "step")


def test_the_parsed_lines_still_exist_in_the_agent():
    # The lines the runner looks for, where the agent prints them. If one is
    # reworded, the steps timeline would go quiet: this test says so first.
    import inspect

    from job_agent import fit, graph

    assert "Already tracked as job #" in inspect.getsource(graph.check_tracker)
    assert "[draft] writing draft #" in inspect.getsource(cover_note.draft_node)
    assert "- scoring '" in inspect.getsource(fit)
    assert '"  -> ' in inspect.getsource(graph.save_to_tracker)
    fit_lines = inspect.getsource(graph.analyze_fit)
    assert "/100  {m.resume_name}   [" in fit_lines and '"  -> best: ' in fit_lines
    reused = runner_mod.AgentRunner(emit=lambda e: None)._progress(
        "Already tracked as job #12 - reusing saved analysis (use --fresh to redo it).")
    assert reused == {"type": "reused", "job_id": 12}


def test_a_reloaded_page_can_replay_the_run():
    api, events = make_api(review_graph())
    api.start_run("https://jobs.example/1")
    step(api)
    history = api.run_state()["events"]
    assert history == events                      # everything the page was sent
    assert history[0]["type"] == "started" and history[-1]["type"] == "paused"
    api.resume({"decision": "reject"})
    step(api)
    api.start_run("https://jobs.example/2")       # a new run starts a new history
    step(api)
    assert api.run_state()["events"][0]["url"] == "https://jobs.example/2"


# ---- tracker -----------------------------------------------------------------

def _save_job(url="https://jobs.example/1", score=80):
    job = JobPosting(title="AI Engineer", company="Acme", location="Remote", employment_type="Full-time",
                     seniority="Mid", salary="Not specified", summary="s",
                     required_skills=["Python"], nice_to_have_skills=[], responsibilities=["x"])
    analysis = FitAnalysis(matching_skills=[], missing_skills=["Rust"], talking_points=[], verdict="ok")
    best = ResumeMatch(resume_name="cv", analysis=analysis, fit_score=score, score_breakdown="b")
    return tracker.save_job(url, job, best, None)


def test_tracker_calls_return_plain_json():
    api, _ = make_api(review_graph())
    job_id = _save_job()
    jobs = api.list_jobs()
    assert jobs[0]["id"] == job_id and jobs[0]["company"] == "Acme"
    assert jobs[0]["created_at"]                  # "Analyzed 2 days ago" on the board
    job = api.get_job(job_id)
    json.dumps(job)                                # would raise on Pydantic objects
    assert job["job"]["title"] == "AI Engineer"
    assert job["best_match"]["fit_score"] == 80
    assert job["cover_notes"] == [] and "fit_json" not in job
    with pytest.raises(ValueError):
        api.get_job(999)


def test_status_changes_are_validated():
    api, _ = make_api(review_graph())
    job_id = _save_job()
    api.set_status(job_id, "applied")
    assert api.list_jobs()[0]["status"] == "applied"
    with pytest.raises(ValueError):
        api.set_status(job_id, "ghosted")
    assert "applied" in api.statuses()


@pytest.mark.parametrize("url", ["file:///C:/Windows/System32/calc.exe", "javascript:alert(1)",
                                 r"C:\jobs\posting.txt", "ms-settings:", "https://", ""])
def test_only_web_links_are_opened(url, monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", opened.append)
    api, _ = make_api(review_graph())
    with pytest.raises(ValueError):
        api.open_link(url)
    api.open_link(" https://jobs.example/1 ")
    assert opened == ["https://jobs.example/1"]


# ---- settings and feedback ---------------------------------------------------

def test_api_key_is_write_only():
    api, _ = make_api(review_graph())
    assert api.get_settings()["ANTHROPIC_API_KEY_SET"] is False
    after = api.set_api_key("sk-ant-secret")
    assert after["ANTHROPIC_API_KEY_SET"] is True
    assert "sk-ant-secret" not in json.dumps(after)
    assert "sk-ant-secret" not in json.dumps(api.app_info())
    assert api.set_api_key("")["ANTHROPIC_API_KEY_SET"] is False


def test_settings_writes_use_an_allow_list():
    api, _ = make_api(review_graph())
    assert api.save_settings({"UI_3D": "still"})["UI_3D"] == "still"
    assert api.save_settings({"UI_THEME": "light"})["UI_THEME"] == "light"
    with pytest.raises(ValueError):
        api.save_settings({"UI_THEME": "purple"})
    with pytest.raises(ValueError):
        api.save_settings({"UI_3D": "spinny"})
    with pytest.raises(ValueError):
        api.save_settings({"OLLAMA_BASE_URL": "http://evil.example"})
    with pytest.raises(ValueError):
        api.save_settings({"ANTHROPIC_API_KEY": "sneaky"})   # only via set_api_key


def test_feedback_is_validated_and_counted():
    api, _ = make_api(review_graph())
    assert api.save_feedback("run-1", 7, {"fit_score": "about right", "cover_note": ""}) == 1
    with pytest.raises(ValueError):
        api.save_feedback("run-1", 7, {"cover_note": "amazing"})
    assert "usable as is" in api.feedback_options()["cover_note"]


def test_app_info_is_json():
    api, _ = make_api(review_graph())
    info = json.loads(json.dumps(api.app_info()))
    assert info["version"] and "settings" in info


# ---- 12f: dashboard numbers ---------------------------------------------------

def seed_run_log():
    """Two runs this week and one 60 days ago, written the way RunRecorder writes them."""
    from datetime import datetime, timedelta, timezone

    from job_agent import runlog

    def ago(days):
        return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    runlog.init_db()
    with tracker._db() as conn:
        for run_id, days, decision, seconds, tools, failed in [
            ("r1", 1, "approve", 180.0, 4, 1), ("r2", 2, "reject", 200.0, 2, 0),
            ("old", 60, "approve", 400.0, 0, 0)]:
            conn.execute("""INSERT INTO runs (run_id, started_at, updated_at, status, decision,
                            agent_seconds, llm_calls, input_tokens, output_tokens, tool_calls,
                            tool_failures) VALUES (?, ?, ?, 'done', ?, ?, 6, 1000, 100, ?, ?)""",
                         (run_id, ago(days), ago(days), decision, seconds, tools, failed))
            conn.execute("INSERT INTO run_steps (run_id, step, seconds) VALUES (?, 'analyze_fit', ?)",
                         (run_id, seconds / 2))
            # The cover note: `cover_note` pauses for review (~0 s after the resume);
            # `draft` is the model writing.
            conn.executemany("INSERT INTO run_steps (run_id, step, seconds) VALUES (?, ?, ?)",
                             [(run_id, "cover_note", 0.02), (run_id, "draft", 16.0)])
            conn.execute("INSERT INTO run_llm_calls (run_id, step, model, input_tokens, output_tokens,"
                         " seconds) VALUES (?, 'analyze_fit', 'qwen3:8b', 1000, 100, 30)", (run_id,))
            for check, value in [("judge_rejections", 2), ("evidence_pass_rate", 0.5)]:
                conn.execute("INSERT INTO run_quality (run_id, check_name, value) VALUES (?, ?, ?)",
                             (run_id, check, value))


def test_dashboard_numbers_match_the_monitoring_module():
    from job_agent import monitoring as m

    seed_run_log()
    data = Api(send=lambda e: None).dashboard(30)
    json.dumps(data, allow_nan=False)  # what the page can parse: no numpy types, no NaN

    expected = m.build_kpis(m.local_runs(30), m.local_llm_calls(30), m.local_decisions(30))
    assert data["kpis"] == expected
    assert data["kpis"]["runs"] == 2 and data["kpis"]["median_full_run"] == 190.0
    assert data["decisions"] == {"approve": 1, "edit": 0, "reject": 1}
    assert data["steps"] == [{"node": "analyze_fit", "avg_seconds": 95.0, "max_seconds": 100.0, "count": 2},
                             {"node": "draft", "avg_seconds": 16.0, "max_seconds": 16.0, "count": 2}]
    quality = {q["check"]: q for q in data["quality"]}
    assert quality["Claims rejected by the judge"]["total"] == 4
    assert quality["Web searches that failed"]["total"] == 1
    assert data["pass_rate"] == 0.5


def test_dashboard_time_range():
    seed_run_log()
    api = Api(send=lambda e: None)
    assert api.dashboard(7)["kpis"]["runs"] == 2
    assert api.dashboard(None)["kpis"]["runs"] == 3          # all time includes the old run
    assert api.dashboard(None)["days"] is None


def test_dashboard_with_an_empty_run_log():
    data = Api(send=lambda e: None).dashboard(30)
    assert data["kpis"]["runs"] == 0 and data["kpis"]["median_full_run"] is None
    assert data["steps"] == [] and data["quality"] == [] and data["pass_rate"] is None


@pytest.mark.parametrize("days", [0, -5, True])
def test_dashboard_rejects_a_bad_range(days):
    with pytest.raises(ValueError):
        Api(send=lambda e: None).dashboard(days)


# ---- 12f2: evals ---------------------------------------------------------------

def seed_two_models():
    """Three local runs and one API run, the way RunRecorder writes them."""
    from job_agent import runlog

    runlog.init_db()
    job_a = _save_job()  # Acme
    with tracker._db() as conn:
        runs = [  # run, start, model, provider, status, decision, seconds, calls, in, out, tools, failed, tracing
            ("q1", "2026-10-01 10:00:00", "qwen3:8b", "ollama", "done", "approve", 180, 9, 15000, 4000, 3, 1, None),
            ("q2", "2026-10-02 10:00:00", "qwen3:8b", "ollama", "done", "reject", 200, 9, 14000, 3000, 2, 0, "langfuse"),
            ("q3", "2026-10-03 10:00:00", "qwen3:8b", "ollama", "paused", None, 30, 1, 3000, 300, 0, 0, None),
            ("c1", "2026-10-04 10:00:00", "claude-haiku-5-5", "anthropic", "done", "approve", 50, 8, 16000, 3500, 2, 0, None),
        ]
        conn.executemany(
            """INSERT INTO runs (run_id, started_at, updated_at, model, provider, status, decision,
               agent_seconds, llm_calls, input_tokens, output_tokens, tool_calls, tool_failures, tracing,
               job_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(r[0], r[1], r[1], *r[2:], job_a) for r in runs])
        quality = {"q1": {"evidence_pass_rate": 0.5, "claims_checked": 10, "fake_quotes_caught": 2,
                          "judge_rejections": 3, "draft_revisions": 3},
                   "q2": {"evidence_pass_rate": 0.7, "claims_checked": 10, "fake_quotes_caught": 0,
                          "judge_rejections": 3, "draft_revisions": 1},
                   "c1": {"evidence_pass_rate": 0.9, "claims_checked": 10, "judge_rejections": 1,
                          "draft_revisions": 1}}
        conn.executemany("INSERT INTO run_quality VALUES (?, ?, ?)",
                         [(run, k, v) for run, checks in quality.items() for k, v in checks.items()])
        conn.executemany("INSERT INTO run_steps (run_id, step, seconds) VALUES (?, ?, ?)",
                         [("q1", "research_company", 50), ("q2", "research_company", 70)])
        conn.executemany(  # the research agent's own calls are logged under "agent"
            "INSERT INTO run_llm_calls (run_id, step, model, input_tokens, output_tokens, seconds)"
            " VALUES (?, ?, 'qwen3:8b', ?, ?, ?)",
            [("q1", "research_company", 1000, 400, 10), ("q1", "agent", 500, 200, 6),
             ("q2", "research_company", 1000, 600, 14), ("q2", "agent", 800, 0, 1)])
        conn.executemany("INSERT INTO run_feedback (run_id, aspect, rating) VALUES (?, ?, ?)",
                         [("q1", "fit_score", "about right"), ("q1", "cover_note", "needed edits"),
                          ("c1", "fit_score", "too high")])


def sql(query, *args):
    with tracker._db() as conn:
        return conn.execute(query, args).fetchone()[0]


def test_evals_numbers_match_the_run_log():
    seed_two_models()
    data = Api(send=lambda e: None).evals(None)
    json.dumps(data, allow_nan=False)  # NaN would reach the page as invalid JSON
    k = data["kpis"]
    assert k["runs"] == sql("SELECT COUNT(*) FROM runs") == 4
    assert k["pass_rate"] == pytest.approx(sql("SELECT AVG(value) FROM run_quality WHERE check_name = 'evidence_pass_rate'"))
    assert (k["approved"], k["decided"]) == (2, 3)
    assert k["median_seconds"] == 180  # full runs only (>= 5 LLM calls): 50, 180, 200
    assert (k["tool_calls"], k["tool_failures"]) == (7, 1)
    checks = {c["check"]: c for c in data["checks"]}
    assert checks["judge_rejections"]["total"] == sql("SELECT SUM(value) FROM run_quality WHERE check_name = 'judge_rejections'")
    assert checks["draft_rewrites"]["total"] == 2  # revision 3 = two rewrites; revision 1 = none
    assert checks["invented_urls_removed"]["runs"] == 0 and checks["invented_urls_removed"]["per_run"] is None
    research = next(s for s in data["steps"] if s["node"] == "research_company")
    assert research == {"node": "research_company", "avg_seconds": 60, "count": 2, "out_tokens": 600}  # agent's tokens count
    ratings = {r["label"]: r["count"] for r in data["ratings"]}
    assert ratings["Fit score: too high"] == 1 and ratings["Cover note: needed edits"] == 1


def test_evals_for_one_model():
    seed_two_models()
    data = Api(send=lambda e: None).evals("claude-haiku-5-5")
    assert data["kpis"]["runs"] == 1 and data["kpis"]["pass_rate"] == pytest.approx(0.9)
    assert [r["rating"] for r in data["ratings"] if r["count"]] == ["too high"]
    models = {m["model"]: m for m in data["models"]}  # the comparison always shows every model
    assert models["qwen3:8b"]["runs"] == 3 and models["qwen3:8b"]["provider"] == "ollama"
    assert models["qwen3:8b"]["pass_rate"] == pytest.approx(0.6)
    assert models["claude-haiku-5-5"]["tokens_per_run"] == 19500


def test_recent_runs_newest_first_with_results_and_trace():
    seed_two_models()
    recent = Api(send=lambda e: None).evals(None)["recent"]
    assert [r["run_id"] for r in recent] == ["c1", "q3", "q2", "q1"]
    assert [r["result"] for r in recent] == ["approved", "not finished", "rejected", "approved"]
    assert recent[2]["tracing"] == "langfuse" and recent[3]["tracing"] == "off"
    assert recent[0]["job"]["company"] == "Acme" and recent[0]["pass_rate"] == pytest.approx(0.9)


def test_evals_with_an_empty_run_log():
    data = Api(send=lambda e: None).evals(None)
    assert data["kpis"]["runs"] == 0 and data["kpis"]["pass_rate"] is None
    assert data["models"] == [] and data["trend"] == [] and data["recent"] == []


def test_pass_rate_trend_compares_the_latest_runs_with_the_ones_before():
    from job_agent import monitoring as m
    import pandas as pd

    n = 8
    runs = pd.DataFrame({"run_id": [f"r{i}" for i in range(n)], "started_at": [f"2026-10-0{i + 1}" for i in range(n)],
                         "model": "m", "provider": "ollama", "status": "done", "decision": "approve",
                         "agent_seconds": 100.0, "llm_calls": 9, "input_tokens": 1, "output_tokens": 1,
                         "tool_calls": 0, "tool_failures": 0, "job_id": None, "tracing": None})
    quality = pd.DataFrame({"run_id": runs["run_id"], "check_name": "evidence_pass_rate",
                            "value": [0.4, 0.4, 0.4, 0.4, 0.6, 0.6, 0.6, 0.8]})
    empty = pd.DataFrame(columns=["run_id", "step", "seconds", "model", "input_tokens", "output_tokens",
                                  "aspect", "rating"])
    jobs = pd.DataFrame(columns=["id", "company", "title"])
    data = m.build_evals(runs, quality, empty, empty, empty, jobs)
    assert data["kpis"]["pass_rate_window"] == 4
    assert data["kpis"]["pass_rate_delta"] == pytest.approx(0.25)  # 0.65 now vs 0.40 before
    assert [round(t["rate"], 1) for t in data["trend"]] == [0.4, 0.4, 0.4, 0.4, 0.6, 0.6, 0.6, 0.8]


def test_tracing_status_off_by_default(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    status = Api(send=lambda e: None).tracing_status()
    assert (status["mode"], status["langfuse"], status["langsmith"]) == ("off", "off", "off")


def test_tracing_status_langfuse(monkeypatch):
    from desktop_web import bridge

    api = Api(send=lambda e: None)
    api.save_settings({"TRACING": "langfuse"})
    monkeypatch.setenv("LANGFUSE_HOST", "http://localhost:3000/")
    monkeypatch.setattr(bridge, "_langfuse_project", lambda host: "proj-1")
    status = api.tracing_status()
    assert status["langfuse"] == "running"
    assert status["langfuse_sessions"] == "http://localhost:3000/project/proj-1/sessions/"
    monkeypatch.setattr(bridge, "_langfuse_project", lambda host: None)  # Docker not started
    assert api.tracing_status()["langfuse"] == "not reachable"


def test_tracing_status_langsmith_without_a_key(monkeypatch):
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    api = Api(send=lambda e: None)
    api.save_settings({"TRACING": "langsmith"})
    assert api.tracing_status()["langsmith"] == "no key"


# ---- 12g: resumes, setup ----------------------------------------------------------

@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    from job_agent import paths

    folder = tmp_path / "data"
    monkeypatch.setattr(paths, "DATA_DIR", folder)
    return folder


def test_resumes_are_copied_listed_and_removed(data_dir, tmp_path):
    originals = tmp_path / "Downloads"
    originals.mkdir()
    (originals / "CV AI.pdf").write_bytes(b"%PDF-1.4 x" * 200)
    (originals / "notes.txt").write_text("not a resume")
    api = Api(send=lambda e: None)
    api._choose_files = lambda: [str(originals / "CV AI.pdf"), str(originals / "notes.txt")]
    assert api.add_resumes() == ["CV AI.pdf"]                   # the .txt is skipped
    assert (originals / "CV AI.pdf").exists()                   # copied, never moved
    assert api.list_resumes() == [{"name": "CV AI.pdf", "kb": 2}]
    api.remove_resume("CV AI.pdf")
    assert api.list_resumes() == [] and (originals / "CV AI.pdf").exists()


def test_cancelled_file_dialog_adds_nothing(data_dir):
    api = Api(send=lambda e: None)
    api._choose_files = lambda: None  # pywebview returns None on Cancel
    assert api.add_resumes() == []


@pytest.mark.parametrize("name", ["..\\jobs.db.pdf", "../x.pdf", "sub/cv.pdf", "C:cv.pdf", "cv.txt", "", "missing.pdf"])
def test_remove_resume_only_takes_a_resume_in_the_data_folder(data_dir, name):
    data_dir.mkdir()
    with pytest.raises(ValueError):
        Api(send=lambda e: None).remove_resume(name)


def test_setup_is_needed_only_on_a_fresh_install(data_dir, monkeypatch):
    api = Api(send=lambda e: None)
    monkeypatch.setenv("SETUP_DONE", "")
    assert api.app_info()["setup_needed"] is True
    data_dir.mkdir()
    (data_dir / "cv.pdf").write_bytes(b"%PDF")
    assert api.app_info()["setup_needed"] is False              # an existing user: never again
    (data_dir / "cv.pdf").unlink()
    api.save_settings({"SETUP_DONE": "true"})
    assert api.app_info()["setup_needed"] is False


def test_model_download_streams_progress(monkeypatch):
    from job_agent import ollama_setup

    def fake_pull(model, on_progress):
        on_progress("pulling abc: 1.00 GB of 4.00 GB", 0.25)
        on_progress("verifying sha256 digest", None)
    monkeypatch.setattr(ollama_setup, "pull", fake_pull)
    events = []
    assert Api(send=events.append).pull_model("qwen3:8b") == {"ok": True, "model": "qwen3:8b"}
    assert [(e["fraction"], e["done"]) for e in events] == [(0.25, False), (None, False), (1.0, True)]
    assert all(e["type"] == "setup_progress" and e["what"] == "pull" for e in events)
    assert events[-1]["ok"] is True


def test_a_failed_download_says_so(monkeypatch):
    from job_agent import ollama_setup

    def broken(model, on_progress):
        raise RuntimeError("pull model manifest: file does not exist")
    monkeypatch.setattr(ollama_setup, "pull", broken)
    events = []
    with pytest.raises(RuntimeError):
        Api(send=events.append).pull_model("qwen3:99b")
    assert events[-1]["done"] is True and events[-1]["ok"] is False
    assert "file does not exist" in events[-1]["message"]


def test_only_one_download_at_a_time():
    api = Api(send=lambda e: None)
    api._setup_lock.acquire()  # a download is running
    with pytest.raises(RuntimeError, match="still running"):
        api.pull_model("qwen3:8b")


def test_without_winget_the_download_page_opens(monkeypatch):
    from desktop_web import bridge
    from job_agent import ollama_setup

    opened = []
    monkeypatch.setattr(ollama_setup, "winget_available", lambda: False)
    monkeypatch.setattr(bridge.webbrowser, "open", opened.append)
    assert Api(send=lambda e: None).install_ollama() == {"ok": False, "manual": True}
    assert opened == [ollama_setup.DOWNLOAD_PAGE]


def test_api_key_check(monkeypatch):
    import langchain_anthropic

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    api = Api(send=lambda e: None)
    assert api.test_api_key("", "claude-haiku-5-5")["ok"] is False  # nothing to test

    class Fake:
        def __init__(self, api_key, **kwargs):
            self.key = api_key

        def invoke(self, prompt):
            if self.key != "sk-ant-good":
                raise ValueError("authentication_error: invalid x-api-key")
    monkeypatch.setattr(langchain_anthropic, "ChatAnthropic", Fake)
    assert api.test_api_key("sk-ant-good", "claude-haiku-5-5") == {"ok": True, "message": "The key works."}
    bad = api.test_api_key("sk-ant-bad", "claude-haiku-5-5")
    assert bad["ok"] is False and "invalid x-api-key" in bad["message"]
    assert not os.environ.get("ANTHROPIC_API_KEY")  # testing never saves the key


def test_system_check_recommends_a_3d_level(monkeypatch):
    from job_agent import system_check as sc

    monkeypatch.setattr(sc, "detect_system", lambda: sc.SystemInfo(
        ram_gb=16, gpu_name="NVIDIA RTX 4060", vram_gb=8, vram_exact=True, disk_free_gb=200, cpu_threads=16))
    api = Api(send=lambda e: None)
    data = api.system_check("ollama", "qwen3:8b")
    json.dumps(data, allow_nan=False)
    assert data["ui3d"]["level"] == "still"
    assert next(a for a in data["advice"] if a["recommended"])["name"] == "qwen3:8b"
    assert api.system_check("anthropic", "claude-haiku-5-5")["ui3d"]["level"] == "animated"


# ---- 12h: the packaged (windowed) app has no console ---------------------------

def test_print_works_without_a_console():
    """PyInstaller's windowed .exe sets sys.stdout to None."""
    routed = runner_mod._RoutedStdout(None)
    assert routed.write("a warning outside any run\n") == len("a warning outside any run\n")
    routed.flush()
    lines = []
    token = runner_mod._log_route.set(lines.append)
    try:
        routed.write("[1/5] Reading the job posting...\n")  # inside a run: still a log event
    finally:
        runner_mod._log_route.reset(token)
    assert lines == ["[1/5] Reading the job posting..."]


# ---- 12j: Stop, interrupted runs, time estimates --------------------------------

def working_graph(started: threading.Event, seconds: float = 10):
    """A step that keeps working (one small runnable call every 50 ms, like an
    LLM writing tokens) until it's stopped or `seconds` pass."""
    from langchain_core.runnables import RunnableLambda

    def work(state, config):
        print("[2/5] Comparing your resumes with the job...")
        started.set()
        tick = RunnableLambda(lambda x: time.sleep(0.05))
        end = time.time() + seconds
        while time.time() < end:
            tick.invoke(0, config)  # each call passes the callbacks: Stop is checked here
        return {"text": "finished without being stopped"}

    g = StateGraph(S)
    g.add_node("analyze_fit", work)
    g.add_edge(START, "analyze_fit")
    g.add_edge("analyze_fit", END)
    return g.compile(checkpointer=InMemorySaver())


def test_stop_ends_the_running_step():
    started = threading.Event()
    api, events = make_api(working_graph(started))
    run_id = api.start_run("https://jobs.example/1")["run_id"]
    assert started.wait(5)
    t = time.time()
    assert api.stop_run() is True
    step(api)
    assert time.time() - t < 2                                  # moments, not the 10 s the step needed
    kinds = [e["type"] for e in events]
    assert "stopping" in kinds and of_type(events, "stopped")[-1]["run_id"] == run_id
    assert not of_type(events, "finished") and not of_type(events, "failed")
    assert api.run_state()["busy"] is False
    with tracker._db() as conn:                                  # in the run log as "stopped", not an error
        row = conn.execute("SELECT status, error FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    assert (row["status"], row["error"]) == ("stopped", None)


def test_stop_when_nothing_runs():
    api, events = make_api(review_graph())
    assert api.stop_run() is False and events == []


def test_a_run_is_in_the_log_while_it_runs():
    started = threading.Event()
    api, _ = make_api(working_graph(started))
    run_id = api.start_run("https://jobs.example/1")["run_id"]
    assert started.wait(5)
    with tracker._db() as conn:
        assert conn.execute("SELECT status FROM runs WHERE run_id = ?", (run_id,)).fetchone()[0] == "running"
    api.stop_run()
    step(api)


def test_closing_the_app_mid_run_shows_as_interrupted():
    from job_agent import runlog

    runlog.init_db()
    with tracker._db() as conn:
        conn.executemany(
            "INSERT INTO runs (run_id, started_at, updated_at, interface, status) VALUES (?, ?, ?, ?, 'running')",
            [("closed", "2026-10-30 17:03:00", "2026-10-30 17:21:40", "desktop"),
             ("cli-run", "2026-10-30 17:05:00", "2026-10-30 17:06:00", "cli")])
    assert runlog.mark_interrupted() == 1                       # a CLI run going on now is left alone
    data = Api(send=lambda e: None).evals(None)
    recent = {r["run_id"]: r for r in data["recent"]}
    assert recent["closed"]["result"] == "interrupted"
    assert recent["closed"]["agent_seconds"] == 18 * 60 + 40     # start to its last finished step
    assert recent["cli-run"]["result"] == "running"
    assert data["kpis"]["unfinished"] == 1 and data["kpis"]["unfinished_seconds"] == 1120


def test_step_estimates_from_this_pcs_runs():
    seed_run_log()  # analyze_fit 90-200 s in three runs, draft 16 s
    estimates = Api(send=lambda e: None).step_estimates()
    assert estimates["2"] == round((90 + 100 + 200) / 3, 1)
    assert estimates["5"] == 16.0 and "3" not in estimates      # no research step recorded


def test_no_estimates_before_the_first_run():
    assert Api(send=lambda e: None).step_estimates() == {}


# ---- 14b: which resumes to compare ---------------------------------------------

def test_choose_resumes_rules(monkeypatch):
    from job_agent.resume import choose_resumes

    every = {"CV_AI": "a", "CV_AI_UAE": "b", "CV_SE": "c"}
    monkeypatch.setenv("RESUMES_DEFAULT", "")
    assert choose_resumes(every, None) == (every, None)                       # no defaults: all
    monkeypatch.setenv("RESUMES_DEFAULT", "CV_AI.pdf|CV_SE.pdf")
    assert list(choose_resumes(every, None)[0]) == ["CV_AI", "CV_SE"]          # the default set
    assert list(choose_resumes(every, ["CV_AI_UAE.pdf"])[0]) == ["CV_AI_UAE"]  # this job's pick wins
    assert choose_resumes(every, []) == (every, None)                          # empty pick: all
    picked, note = choose_resumes(every, ["CV_AI.pdf", "Old.pdf"])
    assert list(picked) == ["CV_AI"] and "Old" in note                         # a deleted one is skipped
    picked, note = choose_resumes(every, ["Gone.pdf"])
    assert picked == every and "all of them" in note                           # never fail silently


class S14(S, total=False):
    resumes: list | None  # what step 2 reads (job_agent/graph.py)


def test_the_page_choice_reaches_the_agent():
    seen = []
    g = StateGraph(S14)
    g.add_node("analyze_fit", lambda state: seen.append(state.get("resumes")) or {"text": "done"})
    g.add_edge(START, "analyze_fit")
    g.add_edge("analyze_fit", END)
    api, _ = make_api(g.compile(checkpointer=InMemorySaver()))
    api.start_run("https://jobs.example/1", False, ["CV_AI.pdf"])
    step(api)
    api.start_run("https://jobs.example/2")                                   # no choice: the defaults
    step(api)
    assert seen == [["CV_AI.pdf"], None]


@pytest.mark.parametrize("bad", ["CV.pdf", [1, 2], {"a": 1}])
def test_a_bad_resume_list_is_refused(bad):
    api, _ = make_api(review_graph())
    with pytest.raises(ValueError, match="list of file names"):
        api.start_run("https://jobs.example/1", False, bad)


def test_resume_settings_are_writable_and_no_line_breaks_get_into_env():
    api = Api(send=lambda e: None)
    assert api.save_settings({"RESUMES_DEFAULT": "CV_AI.pdf|CV_SE.pdf", "RESUMES_ASK": "true"})["RESUMES_ASK"] == "true"
    with pytest.raises(ValueError, match="line breaks"):
        api.save_settings({"RESUMES_DEFAULT": "CV.pdf\nOLLAMA_BASE_URL=http://evil:11434"})
    with pytest.raises(ValueError, match="line breaks"):
        api.save_settings({"LLM_MODEL": "qwen3:8b\rTRACING=langsmith"})
