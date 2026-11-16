"""16i: "Did you apply?", 24 hours after a cover note was approved.

The rule is a pure function of a job's row and the time, so most tests need
no database; the last ones go through the tracker and the bridge."""

from datetime import datetime, timedelta, timezone

import pytest

from desktop_web.bridge import Api
from desktop_web.tray import NOTE_PAGES, apply_notice
from job_agent import applyreminder as ar
from job_agent import tracker
from job_agent.models import FitAnalysis, JobPosting, ResumeMatch

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)


def at(hours_ago: float) -> str:
    return (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S")


def row(approved=30, status="cover_note_ready", asked=None, snoozed=None, ignored=None, fit=80):
    """A job whose cover note was approved `approved` hours ago."""
    when = lambda hours: at(hours) if hours is not None else None  # noqa: E731
    return {"status": status, "fit_score": fit, "updated_at": at(approved), "note_approved_at": at(approved),
            "apply_asked_at": when(asked), "apply_snoozed_until": when(snoozed), "apply_ignored_at": when(ignored)}


# ---- the rule ---------------------------------------------------------------------

def test_asked_only_after_24_hours():
    assert ar.state(row(approved=23), NOW) == "waiting"
    assert ar.state(row(approved=24), NOW) == "due"
    assert ar.state(row(approved=24 * 30), NOW) == "due"       # an old one that was never shown


def test_only_cover_note_ready_jobs_are_asked():
    for status in ("researched", "applied", "interviewing", "offer", "rejected"):
        assert ar.state(row(status=status), NOW) == "off"


def test_no_answer_for_24_hours_counts_as_ignore():
    assert ar.state(row(approved=60, asked=23), NOW) == "due"       # shown 23 hours ago: still open
    assert ar.state(row(approved=60, asked=24), NOW) == "expired"   # your rule: dropped, not pending
    assert not ar.is_due(row(approved=60, asked=24), NOW)


def test_the_24_hours_start_when_it_was_shown_not_when_it_became_due():
    # approved 5 days ago, PC off since: first shown just now -> a full day to answer
    assert ar.state(row(approved=120, asked=0), NOW) == "due"


def test_not_yet_asks_again_in_24_hours():
    snoozed = row(approved=60, asked=1, snoozed=-23)                # "Not yet" an hour ago
    assert ar.state(snoozed, NOW) == "waiting"
    assert ar.state(snoozed, NOW + timedelta(hours=23)) == "due"    # a new round: the old "asked" doesn't count
    assert not ar.asked_this_round(snoozed)
    again = row(approved=90, asked=2, snoozed=3)                    # shown again 2 hours ago
    assert ar.asked_this_round(again) and ar.state(again, NOW) == "due"
    assert ar.state(again, NOW + timedelta(hours=22)) == "expired"


def test_ignore_is_for_good_until_a_new_cover_note():
    assert ar.state(row(approved=60, ignored=10), NOW) == "ignored"
    assert ar.state(row(approved=60, ignored=10), NOW + timedelta(days=90)) == "ignored"
    assert ar.state(row(approved=30, ignored=40), NOW) == "due"     # a newer cover note: asked again


def test_a_job_without_a_cover_note_uses_its_status_change():
    job = {**row(approved=30), "note_approved_at": None}             # moved to "ready" by hand
    assert ar.state(job, NOW) == "due"
    old_row = {"status": "cover_note_ready", "fit_score": 80, "updated_at": at(30)}  # a row without the new columns
    assert ar.state(old_row, NOW) == "due"


def test_ready_to_apply_is_best_fits_only():
    assert ar.in_ready_list(row(fit=75), NOW) and ar.in_ready_list(row(fit=100, approved=1), NOW)   # waiting counts too
    assert not ar.in_ready_list(row(fit=74), NOW)
    assert not ar.in_ready_list(row(fit=90, status="applied"), NOW)
    assert not ar.in_ready_list(row(fit=90, ignored=1), NOW)        # you said no
    assert ar.in_ready_list(row(fit=90, approved=60, asked=30), NOW)  # the question ran out: still in the list


# ---- with the tracker ---------------------------------------------------------------

@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "jobs.db")


def save(url="https://jobs.example/1", fit=80, approved_hours_ago=30, now=NOW):
    job = JobPosting(title="Engineer", company="Acme", location="Remote", employment_type="Full-time",
                     seniority="Junior", salary="Not specified", summary="x", required_skills=["Python"],
                     nice_to_have_skills=[], responsibilities=[])
    best = ResumeMatch(resume_name="cv.pdf", fit_score=fit,
                       analysis=FitAnalysis(matching_skills=[], missing_skills=[], reasoning="x", talking_points=[]))
    job_id = tracker.save_job(url, job, best, None)
    note_id = tracker.add_cover_note(job_id, "Dear Acme")
    tracker.update_status(job_id, "cover_note_ready")
    with tracker._db() as conn:
        conn.execute("UPDATE cover_notes SET approved_at = ? WHERE id = ?",
                     ((now - timedelta(hours=approved_hours_ago)).strftime("%Y-%m-%d %H:%M:%S"), note_id))
    return job_id


def test_showing_the_question_starts_its_24_hours_once():
    job_id = save()
    assert [j["id"] for j in ar.new_jobs(NOW)] == [job_id]
    assert [j["id"] for j in ar.due_jobs(NOW, mark=True)] == [job_id]
    assert ar.new_jobs(NOW) == []                                    # announced once
    later = NOW + timedelta(hours=10)
    ar.due_jobs(later, mark=True)                                    # shown again: the clock is NOT restarted
    assert tracker.list_jobs()[0]["apply_asked_at"] == NOW.strftime("%Y-%m-%d %H:%M:%S")
    assert ar.due_jobs(NOW + timedelta(hours=24)) == []              # unanswered for a day: gone


def test_the_answers_are_saved():
    first, second = save("https://jobs.example/1"), save("https://jobs.example/2")
    ar.due_jobs(NOW, mark=True)
    ar.not_yet(first, NOW)
    ar.ignore(second, NOW)
    assert ar.due_jobs(NOW + timedelta(hours=1)) == []
    assert [j["id"] for j in ar.due_jobs(NOW + timedelta(hours=24))] == [first]
    assert ar.due_jobs(NOW + timedelta(days=30), mark=True) != [] and ar.new_jobs(NOW + timedelta(days=30)) == []
    with pytest.raises(ValueError):
        ar.ignore(999)


def test_the_page_gets_the_question_and_can_answer_it():
    api = Api(send=lambda e: None, graph=object())
    real = datetime.now(timezone.utc)                               # the bridge uses the real clock
    best, low, fresh = (save("https://a.example", 90, 30, real), save("https://b.example", 40, 30, real),
                        save("https://c.example", 95, 2, real))
    jobs = {j["id"]: j for j in api.list_jobs()}
    assert jobs[best]["apply_ask"] and jobs[low]["apply_ask"] and not jobs[fresh]["apply_ask"]
    assert jobs[best]["ready_to_apply"] and jobs[fresh]["ready_to_apply"] and not jobs[low]["ready_to_apply"]
    assert all(j["apply_asked_at"] for j in api.list_jobs() if j["id"] in (best, low))   # shown: the clock runs
    api.apply_answer(best, "yes")
    api.apply_answer(low, "ignore")
    jobs = {j["id"]: j for j in api.list_jobs()}
    assert jobs[best]["status"] == "applied" and not jobs[best]["apply_ask"] and not jobs[best]["ready_to_apply"]
    assert not jobs[low]["apply_ask"]
    api.apply_answer(fresh, "not_yet")
    assert {j["id"]: j for j in api.list_jobs()}[fresh]["apply_snoozed_until"]
    with pytest.raises(ValueError):
        api.apply_answer(fresh, "maybe")


def test_the_notification_names_one_job_or_counts_several():
    assert apply_notice([]) is None
    title, text = apply_notice([{"company": "Acme", "title": "Engineer"}])
    assert title == "Did you apply?" and "Acme" in text and NOTE_PAGES[title] == "tracker"
    assert apply_notice([{"company": "A"}, {"company": "B"}])[1].startswith("2 cover notes")


def test_jobs_already_waiting_when_the_feature_arrives_are_not_asked():
    """Your choice (15 Nov): 43 old cover notes: nobody remembers. An old
    database gets the new columns, and its waiting jobs count as run out."""
    tracker.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tracker._db() as conn:
        conn.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT UNIQUE NOT NULL, "
                     "title TEXT NOT NULL, company TEXT NOT NULL, location TEXT, seniority TEXT, salary TEXT, "
                     "fit_score INTEGER, best_resume TEXT, status TEXT NOT NULL DEFAULT 'researched', job_json TEXT, "
                     "fit_json TEXT, company_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
                     "updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        conn.execute("INSERT INTO jobs (url, title, company, fit_score, status, updated_at) "
                     "VALUES ('u', 'Old job', 'Acme', 90, 'cover_note_ready', datetime('now', '-20 days'))")
    job = tracker.list_jobs()[0]                                    # init_db() migrates
    assert ar.state(job) == "expired" and ar.due_jobs() == [] and ar.new_jobs() == []
    assert ar.in_ready_list(job)                                    # still in "Ready to apply"


def test_a_hidden_window_does_not_start_the_24_hours():
    """Found in the full test (16 Nov): JobLens started with Windows loads its
    page while hidden in the tray. That used to count as "shown", so the
    question ran out before anyone saw it, and the tray never announced it."""
    real = datetime.now(timezone.utc)
    job_id = save("https://a.example", 90, 30, real)
    api = Api(send=lambda e: None, graph=object())
    api._is_hidden = lambda: True
    assert api.list_jobs()[0]["apply_ask"] and api.list_jobs()[0]["apply_asked_at"] is None   # due, but not "shown"
    assert [j["id"] for j in ar.new_jobs()] == [job_id]                    # so the tray still announces it
    api._is_hidden = lambda: False                                         # you opened the window
    assert api.list_jobs()[0]["apply_asked_at"]                            # now the clock runs
    assert ar.new_jobs() == []
