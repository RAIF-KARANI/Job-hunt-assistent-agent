"""
GUI tests for the desktop app (Phase 9) - no LLM, no visible window.

QT_QPA_PLATFORM=offscreen makes Qt render into memory. We don't run the
agent here; instead we call the tab's slots with fake worker signals and
check what the user would see. (The agent itself is tested elsewhere.)
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def tab(app, monkeypatch):
    # Don't start a real agent thread for UI tests.
    from desktop import analyze_tab as mod
    monkeypatch.setattr(mod.AnalyzeTab, "_start_worker", lambda self: None)
    t = mod.AnalyzeTab()
    yield t


def test_step_lines_move_the_progress_bar(tab):
    tab.on_log("[2/5] Comparing your resumes with the job...")
    assert tab.progress.value() == 1
    assert tab.step.text() == "Comparing your resumes with the job..."
    tab.on_log("  [agent] decides to call web_search(...)")   # not a step line
    assert tab.progress.value() == 1
    assert "web_search" in tab.log.toPlainText()


def test_paused_shows_the_review_panel(tab):
    payload = {"kind": "approval", "draft": "Dear Hiring Team,\n\nHello.",
               "warnings": ["300"], "word_count": 5, "revision": 2}
    summary = {"title": "Engineer @ Acme", "fit_score": 63, "breakdown": "4 proven / ...",
               "resume": "cv", "matches": ["Python — “built X”"], "gaps": ["Rust"]}
    tab.on_paused(payload, summary)
    assert not tab.review.isHidden()
    assert tab.fit.text() == "Fit 63/100"
    assert "300" in tab.warnings.text()
    assert tab.draft.toPlainText().startswith("Dear Hiring Team")
    assert "#2" in tab.review.title()
    assert tab.analyze_button.isEnabled()   # not busy while waiting for you


def test_approve_sends_your_edited_text(tab):
    sent = []
    tab.resume_requested.connect(sent.append)
    tab.on_paused({"kind": "approval", "draft": "AI draft", "warnings": [],
                   "word_count": 2, "revision": 1}, {})
    tab.draft.setPlainText("My own edited version")
    tab.approve()
    assert sent == [{"decision": "approve", "text": "My own edited version"}]
    assert tab.busy and not tab.review.isEnabled()


def test_finished_reports_saved_or_rejected(tab):
    tab.on_finished({"saved_path": "C:/x/1_acme.md", "job_id": 1})
    assert "saved" in tab.step.text().lower() and tab.review.isHidden()
    tab.on_finished({"saved_path": None, "job_id": 1})
    assert "nothing was saved" in tab.step.text()


def test_rewrite_needs_feedback(tab):
    sent = []
    tab.resume_requested.connect(sent.append)
    tab.rewrite()                       # empty feedback -> nothing sent
    tab.feedback.setText("shorter")
    tab.rewrite()
    assert sent == [{"decision": "edit", "feedback": "shorter"}]
