"""
Tests for the desktop Tracker tab (Phase 9d) - temp database, offscreen Qt.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from job_agent import cover_note, tracker  # noqa: E402
from job_agent.models import FitAnalysis, JobPosting, ResumeMatch  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "jobs.db")
    monkeypatch.setattr(cover_note, "NOTES_DIR", tmp_path / "notes")


def _save(url, title, company, score):
    job = JobPosting(title=title, company=company, location="Remote", employment_type="Full-time",
                     seniority="Mid", salary="Not specified", summary="s",
                     required_skills=["Python"], nice_to_have_skills=[], responsibilities=["x"])
    analysis = FitAnalysis(matching_skills=[], missing_skills=["Rust"], talking_points=[], verdict="ok")
    best = ResumeMatch(resume_name="cv", analysis=analysis, fit_score=score, score_breakdown="b")
    return tracker.save_job(url, job, best, None), job


@pytest.fixture()
def tab(app, db):
    _save("https://a.example/1", "Backend Engineer", "Acme", 9)
    _save("https://b.example/2", "AI Engineer", "Globex", 80)
    _save("https://c.example/3", "<script>alert(1)</script> Dev", "Initech", 63)
    from desktop.tracker_tab import TrackerTab
    return TrackerTab()


def _column(tab, col):
    return [tab.proxy.index(r, col).data() for r in range(tab.proxy.rowCount())]


def test_loads_all_jobs_best_fit_first(tab):
    assert tab.model.rowCount() == 3
    assert _column(tab, 3) == ["80", "63", "9"]   # numeric sort, not "9" > "80"


def test_search_filters_rows(tab):
    tab.search.setText("globex")
    assert _column(tab, 1) == ["Globex"]
    tab.search.setText("")
    assert tab.proxy.rowCount() == 3


def test_selecting_shows_escaped_details(tab):
    tab.select_job(3)
    html = tab.details.toHtml()
    assert "Initech" in html
    assert "<script>" not in html                 # web text is shown, never executed
    assert tab.status.currentText() == "researched"
    assert not tab.copy_button.isEnabled()        # no approved note yet


def test_status_change_is_saved(tab):
    tab.select_job(2)
    tab.status.setCurrentText("applied")
    tab.change_status(0)
    assert tracker.get_job(2)["status"] == "applied"
    assert "applied" in _column(tab, 4)


def test_approved_note_is_shown_and_copyable(tab):
    job_id, job = 1, tracker.get_job(1)["job"]
    cover_note.save_cover_note(job_id, job, "Dear Hiring Team,\nHello.", approved=True)
    tab.refresh()
    tab.select_job(job_id)
    assert "Dear Hiring Team" in tab.details.toPlainText()
    assert tab.copy_button.isEnabled()
    tab.copy_note()
    assert QApplication.clipboard().text().startswith("Dear Hiring Team")


def test_draft_button_asks_for_the_jobs_url(tab):
    asked = []
    tab.draft_requested.connect(asked.append)
    tab.select_job(2)
    tab.draft_button.click()
    assert asked == ["https://b.example/2"]


def test_get_cover_notes_newest_first(db):
    job_id, job = _save("https://d.example/4", "Dev", "Umbrella", 50)
    cover_note.save_cover_note(job_id, job, "first", approved=True)
    cover_note.save_cover_note(job_id, job, "second", approved=True)
    assert [n["text"] for n in tracker.get_cover_notes(job_id)] == ["second", "first"]


def test_sort_role_returns_raw_numbers(tab):
    idx = tab.model.index(0, 3)
    assert isinstance(tab.model.data(idx, Qt.ItemDataRole.UserRole), int)
