"""
Tests for your own notes per job (14h): notes, an interview date and a
contact, saved in the tracker and checked before they are.
"""

import sqlite3

import pytest

from desktop_web.bridge import Api
from job_agent import tracker
from job_agent.models import FitAnalysis, JobPosting, ResumeMatch


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "jobs.db")


def save(url="https://jobs.example/1"):
    job = JobPosting(title="AI Engineer", company="Acme", location="Remote", employment_type="Full-time",
                     seniority="Mid", salary="Not specified", summary="s",
                     required_skills=["Python"], nice_to_have_skills=[], responsibilities=["x"])
    analysis = FitAnalysis(matching_skills=[], missing_skills=[], talking_points=[], verdict="ok")
    return tracker.save_job(url, job, ResumeMatch(resume_name="cv", analysis=analysis, fit_score=70), None)


def test_notes_date_and_contact_are_saved_and_listed():
    api = Api(send=lambda e: None, graph=object())
    job_id = save()
    saved = api.save_notes(job_id, {"notes": " Asked about evals. ", "interview_at": "2026-11-04T10:30",
                                    "contact": "Dana Lee, dana@acme.example"})
    assert saved == {"notes": "Asked about evals.", "interview_at": "2026-11-04T10:30",
                     "contact": "Dana Lee, dana@acme.example"}
    row = api.list_jobs()[0]
    assert row["interview_at"] == "2026-11-04T10:30" and row["contact"].startswith("Dana")
    assert api.get_job(job_id)["notes"] == "Asked about evals."


def test_only_the_given_fields_change_and_empty_clears():
    job_id = save()
    tracker.save_notes(job_id, {"notes": "keep me", "interview_at": "2026-11-04"})
    tracker.save_notes(job_id, {"interview_at": ""})
    job = tracker.get_job(job_id)
    assert job["notes"] == "keep me" and job["interview_at"] is None


def test_notes_survive_a_re_analysis_and_dont_touch_the_status_clock():
    job_id = save()
    tracker.update_status(job_id, "applied")
    before = tracker.get_job(job_id)["updated_at"]
    tracker.save_notes(job_id, {"notes": "n"})
    assert tracker.get_job(job_id)["updated_at"] == before   # notes aren't news from the company (14e)
    save()                                                     # analyzed again with --fresh
    assert tracker.get_job(job_id)["notes"] == "n"


@pytest.mark.parametrize("values, message", [
    ({"interview_at": "next Tuesday"}, "must look like"),
    ({"interview_at": "2026-13-01"}, "must look like"),
    ({"contact": "x" * 301}, "too long"),
    ({"notes": "x" * 5001}, "too long"),
    ({"status": "offer"}, "Unknown field"),
])
def test_bad_values_are_refused(values, message):
    job_id = save()
    with pytest.raises(ValueError, match=message):
        tracker.save_notes(job_id, values)


def test_an_unknown_job_is_refused():
    with pytest.raises(ValueError):
        tracker.save_notes(999, {"notes": "x"})


def test_an_old_tracker_gets_the_columns(tmp_path):
    with sqlite3.connect(tmp_path / "jobs.db") as conn:
        conn.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY, url TEXT UNIQUE NOT NULL, title TEXT NOT NULL, "
                     "company TEXT NOT NULL, location TEXT, seniority TEXT, salary TEXT, fit_score INTEGER, "
                     "best_resume TEXT, status TEXT NOT NULL DEFAULT 'researched', job_json TEXT, fit_json TEXT, "
                     "company_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        conn.execute("INSERT INTO jobs (url, title, company) VALUES ('u', 'Old', 'Acme')")
    tracker.save_notes(1, {"contact": "Sam"})
    assert tracker.list_jobs()[0]["contact"] == "Sam"
