"""
Tests for the version-2 desktop bridge (Phase 12b): runner + API, no window, no LLM.

The agent is replaced by a tiny real LangGraph graph with the same two
pauses as the real one: interrupt({"kind": "approval", ...}) for the cover
note and interrupt({"kind": "paste_posting", ...}) for an unreadable page.
"""

import json
import sys
import threading
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
                                 "C:\jobs\posting.txt", "ms-settings:", "https://", ""])
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
