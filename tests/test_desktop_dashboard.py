"""
Tests for the desktop Dashboard tab (Phase 9e) and the shared KPI logic.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from job_agent import monitoring as m  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# ---- shared KPI logic (used by both dashboards) -----------------------------


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


# ---- the tab ------------------------------------------------------------------


@pytest.fixture()
def tab(app, monkeypatch):
    jobs = pd.DataFrame({"id": [1, 2], "company": ["Acme", "Globex"], "title": ["a", "b"],
                         "fit_score": [42, 90], "status": ["researched", "applied"]})
    monkeypatch.setattr(m, "fetch_jobs", lambda: jobs)
    from desktop.dashboard_tab import DashboardTab
    return DashboardTab()


def test_unreadable_run_log_is_reported_and_tracker_charts_still_work(tab):
    tab.draw_tracker()
    tab.draw_runs(None, error="disk error")
    assert "disk error" in tab.source.text()
    assert tab.refresh_button.isEnabled()


def run_log_data(quality_rows=True, feedback=True):
    return {
        "runs": pd.DataFrame({"sessionId": ["s1"], "llm_calls": [9], "agent_seconds": [186.0],
                              "input_tokens": [15431], "output_tokens": [5260], "interface": ["cli"]}),
        "calls": pd.DataFrame({"input_tokens": [3000, 4000, 2000], "output_tokens": [800, 100, 300],
                               "latency": [30.0, 6.0, 12.0]}),
        "nodes": pd.DataFrame({"node": ["read_posting", "analyze_fit"],
                               "avg_seconds": [36.0, 85.0], "max_seconds": [36.0, 85.0], "count": [1, 1]}),
        "decisions": pd.DataFrame({"decision": ["approve", "edit", "reject"], "count": [1, 0, 1]}),
        "quality": (pd.DataFrame({"check": ["Claims rejected by the judge"], "per_run": [5.0],
                                  "total": [5.0], "runs": [1]}) if quality_rows
                    else pd.DataFrame(columns=["check", "per_run", "total", "runs"])),
        "pass_rate": 0.58 if quality_rows else None,
        "feedback": m.build_feedback(pd.DataFrame({"aspect": ["fit_score"], "rating": ["about right"]})
                                     if feedback else pd.DataFrame()),
    }


def test_run_log_fills_kpis_from_this_pc(tab):
    tab.draw_runs(run_log_data())
    assert tab.tiles["runs"].value.text() == "1"
    assert tab.tiles["tokens"].value.text() == "10,200"
    assert tab.tiles["median"].value.text() == "186 s"
    assert tab.tiles["approval"].value.text() == "50%"
    assert "on this PC" in tab.source.text()               # no Langfuse needed


def test_quality_title_shows_evidence_pass_rate(tab):
    tab.draw_runs(run_log_data())
    title = tab.quality_chart.figure.axes[0].get_title(loc="left")
    assert "evidence verified 58% of claims" in title


def test_empty_quality_and_feedback_show_hints(tab):
    tab.draw_runs(run_log_data(quality_rows=False, feedback=False))
    texts = [t.get_text() for t in tab.feedback_chart.figure.axes[0].texts]
    assert any("Rate a run" in t for t in texts)


# ---- local run-log tables (temp database, filled by the real recorder) ----------


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    from job_agent import tracker
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "jobs.db")


def test_local_tables_from_a_recorded_run(temp_db):
    from job_agent import runlog
    rec = runlog.RunRecorder("r1", "desktop", "ollama", "qwen3:8b")
    rec.segment_started_at = runlog._now()
    rec.steps = [("analyze_fit", 80.0, runlog._now())]
    rec.llm_calls = [("analyze_fit", "qwen3:8b", 2500, 800, 30.0, runlog._now())]
    rec.tool_calls, rec.tool_failures = 2, 1
    from job_agent.models import FitAnalysis, ResumeMatch, SkillMatch
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
