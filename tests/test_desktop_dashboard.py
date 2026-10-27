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


def test_without_langfuse_tracker_charts_still_work(tab):
    tab.draw_tracker()
    tab.draw_traces(None)
    assert "need Langfuse" in tab.source.text()
    assert tab.tiles["runs"].value.text() == "–"
    assert tab.refresh_button.isEnabled()


def test_with_trace_data_fills_kpis(tab):
    data = {
        "runs": pd.DataFrame({"sessionId": ["s1"], "llm_calls": [9], "agent_seconds": [186.0],
                              "input_tokens": [15431], "output_tokens": [5260], "interface": ["cli"]}),
        "calls": pd.DataFrame({"input_tokens": [3000, 4000, 2000], "output_tokens": [800, 100, 300],
                               "latency": [30.0, 6.0, 12.0]}),
        "nodes": pd.DataFrame({"node": ["read_posting", "analyze_fit"],
                               "avg_seconds": [36.0, 85.0], "max_seconds": [36.0, 85.0], "count": [1, 1]}),
        "decisions": pd.DataFrame({"decision": ["approve", "edit", "reject"], "count": [1, 0, 1]}),
    }
    tab.draw_traces(data)
    assert tab.tiles["runs"].value.text() == "1"
    assert tab.tiles["tokens"].value.text() == "10,200"
    assert tab.tiles["median"].value.text() == "186 s"
    assert tab.tiles["approval"].value.text() == "50%"
    assert "Langfuse" in tab.source.text()
