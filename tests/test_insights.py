"""
Tests for Insights (19c, E7): the status history is recorded (and an undo
takes a slip back out), and the numbers are plain counts that never claim
more than the data shows.
"""

import sqlite3
from datetime import datetime

import pytest

from desktop_web.bridge import Api
from job_agent import insights, tracker
from job_agent.models import FitAnalysis, JobPosting, ResumeMatch


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "jobs.db")


def save(url="https://www.linkedin.com/jobs/view/1", fit=70, resume="cv.pdf"):
    job = JobPosting(title="AI Engineer", company="Acme", location="Remote", employment_type="Full-time",
                     seniority="Mid", salary="Not specified", summary="s",
                     required_skills=["Python"], nice_to_have_skills=[], responsibilities=["x"])
    analysis = FitAnalysis(matching_skills=[], missing_skills=[], talking_points=[], verdict="ok")
    return tracker.save_job(url, job, ResumeMatch(resume_name=resume, analysis=analysis, fit_score=fit), None)


# ---- the history ------------------------------------------------------------


def test_every_status_change_is_recorded_once():
    job_id = save()
    tracker.update_status(job_id, "applied")
    tracker.update_status(job_id, "applied")  # no change: nothing recorded
    tracker.update_status(job_id, "interviewing")
    assert [(c["from_status"], c["to_status"]) for c in tracker.status_changes()] == [
        ("researched", "applied"), ("applied", "interviewing")]


def test_an_undo_takes_the_slip_back_out():
    job_id = save()
    tracker.update_status(job_id, "applied")
    tracker.update_status(job_id, "researched")  # the board's Undo
    assert tracker.status_changes() == []


def test_putting_it_back_much_later_is_history():
    job_id = save()
    tracker.update_status(job_id, "applied")
    with sqlite3.connect(tracker.DB_PATH) as db:
        db.execute("UPDATE status_changes SET changed_at = datetime('now', '-1 day')")
    tracker.update_status(job_id, "researched")
    assert len(tracker.status_changes()) == 2


def test_deleting_a_job_deletes_its_history():
    job_id = save()
    tracker.update_status(job_id, "applied")
    tracker.delete_job(job_id)
    assert tracker.status_changes() == []


# ---- the numbers (pure: rows in, numbers out) --------------------------------


def job(i, status, url="https://www.linkedin.com/jobs/view/1", fit=80, resume="AI.pdf"):
    return {"id": i, "status": status, "url": url, "fit_score": fit, "best_resume": resume}


def change(i, a, b, at):
    return {"job_id": i, "from_status": a, "to_status": b, "changed_at": at}


def test_rates_need_five_applications():
    jobs = [job(1, "interviewing"), job(2, "applied"), job(3, "applied"), job(4, "researched")]
    r = insights.compute(jobs, [])
    assert r["applications"] == 3 and r["interviews"] == 1
    assert r["rate"] is None  # 1 of 3 is not "33 %"
    assert r["by_resume"] == [{"name": "AI.pdf", "applications": 3, "interviews": 1, "offers": 0, "rate": None}]

    jobs += [job(5, "offer"), job(6, "applied")]
    r = insights.compute(jobs, [])
    assert r["applications"] == 5 and r["interviews"] == 2 and r["offers"] == 1 and r["rate"] == 0.4


def test_rejected_without_history_is_unknown_not_guessed():
    r = insights.compute([job(1, "rejected"), job(2, "applied")], [])
    assert r["applications"] == 1 and r["unknown"] == 1
    assert r["rejected"] == {"after applying": 0, "after an interview": 0, "before applying": 0, "unknown": 1}


def test_rejected_with_history_is_placed():
    jobs = [job(1, "rejected"), job(2, "rejected"), job(3, "rejected")]
    changes = [
        change(1, "researched", "applied", "2026-11-01 10:00:00"), change(1, "applied", "rejected", "2026-11-08 10:00:00"),
        change(2, "researched", "rejected", "2026-11-01 10:00:00"),  # you dropped it
        change(3, "researched", "applied", "2026-11-01 10:00:00"), change(3, "applied", "interviewing", "2026-11-03 10:00:00"),
        change(3, "interviewing", "rejected", "2026-11-10 10:00:00"),
    ]
    r = insights.compute(jobs, changes)
    assert r["rejected"] == {"after applying": 1, "after an interview": 1, "before applying": 1, "unknown": 0}
    assert r["applications"] == 2 and r["interviews"] == 1  # job 3 reached an interview, then a no


def test_time_to_an_answer_and_still_waiting():
    jobs = [job(1, "interviewing"), job(2, "rejected"), job(3, "applied"), job(4, "applied")]
    changes = [
        change(1, "researched", "applied", "2026-11-01 10:00:00"), change(1, "applied", "interviewing", "2026-11-05 10:00:00"),
        change(2, "researched", "applied", "2026-11-01 10:00:00"), change(2, "applied", "rejected", "2026-11-11 10:00:00"),
        change(3, "researched", "applied", "2026-11-10 10:00:00"),
    ]  # job 4 was applied to before 19c: no time known
    r = insights.compute(jobs, changes, now=datetime(2026, 11, 20, 10, 0))
    assert r["answer_days"] == {"median": 7.0, "count": 2, "fastest": 4.0, "slowest": 10.0}
    assert r["waiting"] == {"count": 1, "longest_days": 10.0}
    assert r["recorded_since"] == "2026-11-01 10:00:00"


def test_groups_by_site_and_fit_band():
    jobs = [
        job(1, "applied", "https://www.linkedin.com/jobs/view/9", fit=90),
        job(2, "interviewing", "https://boards.greenhouse.io/acme/jobs/1", fit=65),
        job(3, "applied", "https://careers.acme.co.uk/jobs/2", fit=50),
        job(4, "applied", "text: pasted posting", fit=None),
    ]
    r = insights.compute(jobs, [])
    assert {g["name"] for g in r["by_site"]} == {"LinkedIn", "Greenhouse", "acme.co.uk", "Pasted job text"}
    assert [g["name"] for g in r["by_fit"]] == ["75 and up", "60 to 74", "under 60", "no score"]


@pytest.mark.parametrize("url, name", [
    ("https://ae.linkedin.com/jobs/view/1", "LinkedIn"),
    ("https://acme.wd5.myworkdayjobs.com/x", "Workday"),
    ("https://jobs.example.com/1", "example.com"),
    ("", "Pasted job text"),
])
def test_site_names(url, name):
    assert insights.site(url) == name


def test_stages_count_every_job():
    r = insights.compute([job(1, "researched"), job(2, "researched"), job(3, "offer")], [])
    assert r["stages"]["researched"] == 2 and r["stages"]["offer"] == 1 and sum(r["stages"].values()) == 3


def test_the_bridge_reads_the_tracker():
    a, b = save("https://www.linkedin.com/jobs/view/1"), save("https://www.indeed.com/viewjob?jk=2")
    tracker.update_status(a, "applied")
    tracker.update_status(b, "applied")
    tracker.update_status(b, "interviewing")
    r = Api(send=lambda e: None, graph=object()).insights()
    assert r["applications"] == 2 and r["interviews"] == 1
    assert {g["name"] for g in r["by_site"]} == {"LinkedIn", "Indeed"}
