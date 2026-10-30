"""
Tests for the monitoring data layer (job_agent/monitoring.py).

The builders are pure functions (DataFrame in -> DataFrame out), so we feed
them small fake Langfuse records - no Langfuse server needed.
"""

import pandas as pd

from job_agent import monitoring as m


def _obs(name, type_, session, latency, start="2026-10-27T10:00:00Z",
         root=False, tags=("cli", "qwen3:8b"), usage=None):
    return {"name": name, "type": type_, "sessionId": session, "latency": latency,
            "startTime": start, "isRootObservation": root, "tags": list(tags),
            "model": "qwen3:8b" if type_ == "GENERATION" else None,
            "usageDetails": usage}


# One run ("s1"): started from the CLI, paused for approval, then resumed.
FAKE = pd.DataFrame([
    _obs("LangGraph", "CHAIN", "s1", 180.0, root=True),                     # first segment
    _obs("LangGraph", "CHAIN", "s1", 1.0, start="2026-10-27T11:00:00Z", root=True),  # resume
    _obs("read_posting", "CHAIN", "s1", 30.0),
    _obs("analyze_fit", "CHAIN", "s1", 80.0),
    _obs("ChatOllama", "GENERATION", "s1", 20.0, usage={"input": 3000, "output": 800}),
    _obs("ChatOllama", "GENERATION", "s1", 5.0, usage={"input": 4000, "output": 100}),
    # A second run ("s2") from the web UI with one LLM call.
    _obs("LangGraph", "CHAIN", "s2", 12.0, root=True, tags=("web",)),
    _obs("ChatOllama", "GENERATION", "s2", 10.0, tags=("web",), usage={"input": 3300, "output": 270}),
])


def test_runs_sum_agent_time_and_exclude_waiting():
    runs = m.build_runs(FAKE).set_index("sessionId")
    # 180 + 1 seconds of WORK; the hour between the two segments (waiting for
    # the human) must not count.
    assert runs.loc["s1", "agent_seconds"] == 181.0
    assert runs.loc["s1", "segments"] == 2
    assert runs.loc["s1", "llm_calls"] == 2
    assert runs.loc["s1", "input_tokens"] == 7000
    assert runs.loc["s1", "output_tokens"] == 900
    assert runs.loc["s1", "interface"] == "cli"
    assert runs.loc["s2", "interface"] == "web"


def test_llm_calls_extract_tokens():
    calls = m.build_llm_calls(FAKE)
    assert len(calls) == 3
    assert calls["output_tokens"].sum() == 1170


def test_node_latency_is_in_pipeline_order():
    nodes = m.build_node_latency(FAKE)
    assert list(nodes["node"]) == ["read_posting", "analyze_fit"]  # pipeline order, not alphabetical
    assert nodes.set_index("node").loc["analyze_fit", "avg_seconds"] == 80.0


def test_empty_data_gives_empty_tables():
    empty = pd.DataFrame()
    assert m.build_runs(empty).empty
    assert m.build_llm_calls(empty).empty
    assert m.build_node_latency(empty).empty


def test_tool_status_reads_the_error_text():
    # Tools never raise (Phase 3): failure is only visible in the output text.
    assert m.tool_status('{"content": "Search failed (timeout). Try again."}') == "failed"
    assert m.tool_status('{"content": "Title: GitLab\\nURL: https://..."}') == "ok"
    tools = pd.DataFrame([
        {"name": "web_search", "output": "Search failed (No results found.)"},
        {"name": "web_search", "output": "Title: x"},
        {"name": "news_search", "output": "Date: 2026-10-14"},
    ])
    stats = m.build_tool_stats(tools).set_index(["tool", "status"])["calls"]
    assert stats[("web_search", "failed")] == 1
    assert stats[("web_search", "ok")] == 1


def test_decisions_and_funnel_keep_a_fixed_order():
    scores = pd.DataFrame([{"name": "cover_note_decision", "value": v}
                           for v in ["reject", "approve", "reject"]])
    d = m.build_decisions(scores)
    assert list(d["decision"]) == ["approve", "edit", "reject"]
    assert list(d["count"]) == [1, 0, 2]

    jobs = pd.DataFrame({"status": ["researched", "researched", "applied"]})
    f = m.build_status_funnel(jobs)
    assert list(f["status"]) == m.STATUS_ORDER   # lifecycle order, zeros included
    assert f.set_index("status").loc["applied", "jobs"] == 1


# ---- the shared KPI logic (moved from the Qt Dashboard's tests in 12i) -------

def test_kpis_from_runs_calls_decisions():
    runs = pd.DataFrame({"llm_calls": [9, 1, 7], "agent_seconds": [180.0, 10.0, 200.0]})
    calls = pd.DataFrame({"input_tokens": [100, 200], "output_tokens": [10, 20]})
    decisions = pd.DataFrame({"decision": ["approve", "edit", "reject"], "count": [1, 0, 3]})
    k = m.build_kpis(runs, calls, decisions)
    assert k["runs"] == 3 and k["llm_calls"] == 2
    assert (k["tokens_in"], k["tokens_out"]) == (300, 30)
    assert k["median_full_run"] == 190.0       # the 1-call re-draft is excluded
    assert k["approval_rate"] == 0.25


def test_kpis_with_no_data():
    empty_runs = pd.DataFrame(columns=["llm_calls", "agent_seconds"])
    empty_calls = pd.DataFrame(columns=["input_tokens", "output_tokens"])
    k = m.build_kpis(empty_runs, empty_calls, m.build_decisions(pd.DataFrame()))
    assert k["median_full_run"] is None and k["approval_rate"] is None


# ---- local run-log tables (temp database, filled by the real recorder) ----------

def test_local_tables_from_a_recorded_run(tmp_path, monkeypatch):
    from job_agent import runlog, tracker
    from job_agent.models import FitAnalysis, ResumeMatch, SkillMatch

    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "jobs.db")
    rec = runlog.RunRecorder("r1", "desktop", "ollama", "qwen3:8b")
    rec.segment_started_at = runlog._now()
    rec.steps = [("analyze_fit", 80.0, runlog._now())]
    rec.llm_calls = [("analyze_fit", "qwen3:8b", 2500, 800, 30.0, runlog._now())]
    rec.tool_calls, rec.tool_failures = 2, 1
    analysis = FitAnalysis(matching_skills=[SkillMatch(requirement="a", resume_evidence="q")],
                           missing_skills=[], talking_points=[], verdict="ok")
    match = ResumeMatch(resume_name="cv", analysis=analysis, unsupported_matches=["b - no"])
    rec._write(120.0, {"job_id": 1, "all_matches": [match], "decision": "approve"})
    runlog.save_feedback("r1", 1, "fit_score", "too high")

    runs = m.local_runs(None)
    assert runs.loc[0, "sessionId"] == "r1" and runs.loc[0, "decision"] == "approve"
    assert m.local_llm_calls(None)["output_tokens"].tolist() == [800]
    assert m.local_node_latency(None)["node"].tolist() == ["analyze_fit"]
    assert m.local_decisions(None).set_index("decision").loc["approve", "count"] == 1
    quality, pass_rate = m.local_quality(None)
    assert pass_rate == 0.5                                  # 1 verified of 2 claims
    per_run = quality.set_index("check")["per_run"]
    assert per_run["Claims rejected by the judge"] == 1
    assert per_run["Web searches that failed"] == 1          # from the runs table
    fb = m.local_feedback().set_index("label")["count"]
    assert fb["Fit score: too high"] == 1 and fb["Cover note: usable as is"] == 0
