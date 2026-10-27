"""
Tests for the tracker (Phase 4) and the approval guardrail (Phase 5).

Every test gets a fresh, empty database in a temporary folder (pytest's
tmp_path), so your real data/jobs.db is never touched.
"""

import pytest

from job_agent import cover_note, tracker
from job_agent.models import FitAnalysis, JobPosting, ResumeMatch


@pytest.fixture(autouse=True)
def temp_storage(tmp_path, monkeypatch):
    """Redirect the database and the notes folder into a temp directory."""
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "jobs.db")
    monkeypatch.setattr(cover_note, "NOTES_DIR", tmp_path / "cover_notes")
    return tmp_path


def _job(title="Backend Engineer"):
    return JobPosting(
        title=title, company="Acme", location="Remote", employment_type="Full-time",
        seniority="Mid", salary="Not specified", summary="s",
        required_skills=["Python"], nice_to_have_skills=[], responsibilities=["code"],
    )


def _best(score=80):
    analysis = FitAnalysis(
        matching_skills=[], missing_skills=[], talking_points=[], verdict="ok",
    )
    return ResumeMatch(resume_name="cv", analysis=analysis, fit_score=score)


URL = "https://example.com/job/1"


# ---- Phase 4: tracker ----------------------------------------------------


def test_save_and_load_roundtrip():
    job_id = tracker.save_job(URL, _job(), _best(), None)
    data = tracker.get_job(job_id)
    assert data["job"].title == "Backend Engineer"   # JSON -> Pydantic again
    assert data["status"] == "researched"
    assert data["company_brief"] is None


def test_same_url_twice_updates_instead_of_duplicating():
    first = tracker.save_job(URL, _job(), _best(70), None)
    second = tracker.save_job(URL, _job("Senior Backend Engineer"), _best(85), None)
    assert first == second
    rows = tracker.list_jobs()
    assert len(rows) == 1
    assert rows[0]["fit_score"] == 85


def test_resaving_keeps_the_users_status():
    job_id = tracker.save_job(URL, _job(), _best(), None)
    tracker.update_status(job_id, "applied")
    tracker.save_job(URL, _job(), _best(), None)   # e.g. re-run with --fresh
    assert tracker.get_job(job_id)["status"] == "applied"


def test_unknown_status_is_rejected():
    job_id = tracker.save_job(URL, _job(), _best(), None)
    with pytest.raises(ValueError):
        tracker.update_status(job_id, "hired")


def test_find_job_id():
    assert tracker.find_job_id(URL) is None
    job_id = tracker.save_job(URL, _job(), _best(), None)
    assert tracker.find_job_id(URL) == job_id


# ---- Phase 5: the approval guardrail -------------------------------------


def test_unapproved_note_is_never_saved(temp_storage):
    job_id = tracker.save_job(URL, _job(), _best(), None)
    with pytest.raises(PermissionError):
        cover_note.save_cover_note(job_id, _job(), "Dear Hiring Team", approved=False)
    assert tracker.get_job(job_id)["status"] == "researched"
    assert not (temp_storage / "cover_notes").exists()


def test_approved_note_is_saved_everywhere(temp_storage):
    job_id = tracker.save_job(URL, _job(), _best(), None)
    path = cover_note.save_cover_note(job_id, _job(), "Dear Hiring Team", approved=True)
    assert path.read_text(encoding="utf-8").endswith("Dear Hiring Team\n")
    assert tracker.get_job(job_id)["status"] == "cover_note_ready"


def test_review_routing():
    assert cover_note.route_after_review({"decision": "approve"}) == "save"
    assert cover_note.route_after_review({"decision": "edit"}) == "draft"
    assert cover_note.route_after_review({"decision": "reject"}) == "__end__"
