"""
Tests for the follow-up reminders and "Start with Windows" (14e).

The rule is plain dates, so most tests pass `now` instead of waiting a
week. The database is a temp file; the registry tests use their own key
under HKCU\\Software, never the real Run key.
"""

import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from desktop_web import autostart
from desktop_web.bridge import WRITABLE_SETTINGS, Api
from desktop_web.tray import RunState, Tray, close_action, follow_up_notice, follow_up_text
from job_agent import followup, settings, tracker
from job_agent.models import FitAnalysis, JobPosting, ResumeMatch

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)


def at(days_ago: float) -> str:
    return (NOW - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")


def row(status="applied", updated=8, followed=None, snoozed=None):
    return {"status": status, "updated_at": at(updated),
            "followed_up_at": at(followed) if followed is not None else None,
            "snoozed_until": at(snoozed) if snoozed is not None else None}


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "jobs.db")
    monkeypatch.setattr(settings, "APP_HOME", tmp_path)
    monkeypatch.setattr(settings, "ENV_FILE", tmp_path / ".env")
    for key in WRITABLE_SETTINGS:
        monkeypatch.setenv(key, settings.DEFAULTS.get(key, ""))


def save(url="https://jobs.example/1"):
    job = JobPosting(title="AI Engineer", company="Acme", location="Remote", employment_type="Full-time",
                     seniority="Mid", salary="Not specified", summary="s",
                     required_skills=["Python"], nice_to_have_skills=[], responsibilities=["x"])
    analysis = FitAnalysis(matching_skills=[], missing_skills=[], talking_points=[], verdict="ok")
    return tracker.save_job(url, job, ResumeMatch(resume_name="cv", analysis=analysis, fit_score=70), None)


def set_dates(job_id, updated):
    with tracker._db() as conn:
        conn.execute("UPDATE jobs SET updated_at = ? WHERE id = ?", (updated, job_id))


# ---- the rule ------------------------------------------------------------------

def test_a_week_in_applied_or_interviewing_is_due():
    assert followup.is_due(row("applied", updated=7), 7, NOW)
    assert followup.is_due(row("interviewing", updated=10), 7, NOW)
    assert not followup.is_due(row("applied", updated=6.9), 7, NOW)


def test_other_statuses_never_are():
    for status in ("researched", "cover_note_ready", "offer", "rejected"):
        assert not followup.is_due(row(status, updated=30), 7, NOW)


def test_following_up_starts_the_clock_again():
    assert not followup.is_due(row(updated=20, followed=2), 7, NOW)
    assert followup.is_due(row(updated=20, followed=7), 7, NOW)


def test_snoozed_until_the_date_passes():
    assert not followup.is_due(row(updated=20, snoozed=-1), 7, NOW)   # snoozed until tomorrow
    assert followup.is_due(row(updated=20, snoozed=1), 7, NOW)        # snooze ended yesterday


def test_off_means_never(monkeypatch):
    monkeypatch.setenv("FOLLOW_UP_DAYS", "off")
    assert followup.days_setting() is None
    assert not followup.is_due(row(updated=99), followup.days_setting(), NOW)
    monkeypatch.setenv("FOLLOW_UP_DAYS", "14")
    assert followup.days_setting() == 14


# ---- the tracker -----------------------------------------------------------------

def test_an_old_tracker_gets_the_new_columns(tmp_path):
    with sqlite3.connect(tmp_path / "jobs.db") as conn:     # a jobs.db from before 14e
        conn.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY, url TEXT UNIQUE NOT NULL, title TEXT NOT NULL, "
                     "company TEXT NOT NULL, location TEXT, seniority TEXT, salary TEXT, fit_score INTEGER, "
                     "best_resume TEXT, status TEXT NOT NULL DEFAULT 'researched', job_json TEXT, fit_json TEXT, "
                     "company_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        conn.execute("INSERT INTO jobs (url, title, company, status) VALUES ('u', 'Old job', 'Acme', 'applied')")
    jobs = tracker.list_jobs()
    assert jobs[0]["title"] == "Old job" and jobs[0]["followed_up_at"] is None   # kept, and migrated


def test_followed_up_and_snooze_are_saved_and_end_the_reminder():
    first, second = save("https://jobs.example/1"), save("https://jobs.example/2")
    for job_id in (first, second):
        tracker.update_status(job_id, "applied")
        set_dates(job_id, at(9))
    assert {j["id"] for j in followup.due_jobs(NOW)} == {first, second}
    followup.mark_followed_up(first, NOW)
    followup.snooze(second, now=NOW)
    assert followup.due_jobs(NOW) == []
    assert [j["id"] for j in followup.due_jobs(NOW + timedelta(days=3))] == [second]   # the snooze ran out
    assert {j["id"] for j in followup.due_jobs(NOW + timedelta(days=7))} == {first, second}
    with pytest.raises(ValueError):
        followup.snooze(999)


def test_a_status_change_restarts_the_clock():
    job_id = save()
    tracker.update_status(job_id, "applied")
    set_dates(job_id, at(9))
    tracker.update_status(job_id, "interviewing")        # updated_at = now (the real now)
    assert followup.due_jobs() == []


# ---- the bridge ------------------------------------------------------------------

def test_the_page_gets_a_follow_up_flag_and_can_answer_it():
    api = Api(send=lambda e: None, graph=object())
    job_id = save()
    api.set_status(job_id, "applied")
    assert api.list_jobs()[0]["follow_up"] is False       # applied today
    set_dates(job_id, "2020-01-01 00:00:00")
    assert api.list_jobs()[0]["follow_up"] is True
    api.snooze_follow_up(job_id)
    assert api.list_jobs()[0]["follow_up"] is False and api.list_jobs()[0]["snoozed_until"]
    api.save_settings({"FOLLOW_UP_DAYS": "off"})
    with pytest.raises(ValueError):
        api.save_settings({"FOLLOW_UP_DAYS": "2"})


# ---- the tray --------------------------------------------------------------------

def test_one_notification_a_day_and_only_with_something_to_do():
    assert follow_up_notice(0, None, "2026-11-20") is None
    assert follow_up_notice(2, "2026-11-20", "2026-11-20") is None       # already told today
    title, message = follow_up_notice(2, "2026-11-19", "2026-11-20")
    assert title == "Time to follow up" and "2 applications" in message
    assert "1 application has" in follow_up_notice(1, None, "2026-11-20")[1]
    assert follow_up_text(1) == "Follow up on 1 job" and follow_up_text(3) == "Follow up on 3 jobs"


def test_with_start_with_windows_on_closing_keeps_jobLens_in_the_tray():
    idle = RunState()
    assert close_action(idle) == "quit"
    assert close_action(idle, keep_in_tray=True) == "hide"
    tray = Tray("icon.png", show=lambda: None, stop_run=lambda: None, quit_app=lambda: None,
                keep_in_tray=lambda: True, follow_ups=lambda: 2)
    told = []
    tray._icon = type("Icon", (), {"notify": lambda self, m, t: told.append(t), "update_menu": lambda self: None})()
    hidden = []
    assert tray.window_closing(hide=lambda: hidden.append(1)) is False
    assert hidden and tray.hidden and told == ["JobLens is in the tray"]
    assert tray.count_follow_ups() == 2


def test_a_broken_count_never_breaks_the_tray():
    tray = Tray("icon.png", show=lambda: None, stop_run=lambda: None, quit_app=lambda: None,
                follow_ups=lambda: 1 / 0, keep_in_tray=lambda: 1 / 0)
    assert tray.count_follow_ups() == 0
    assert close_action(tray.state) == "quit"


# ---- Start with Windows ---------------------------------------------------------

@pytest.mark.skipif(sys.platform != "win32", reason="the Windows registry")
def test_start_with_windows_writes_and_removes_the_run_value(monkeypatch):
    import winreg

    key = rf"Software\JobLensTest-{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(autostart.paths, "IS_INSTALLED", True)
    try:
        assert autostart.enabled(key) is False
        assert autostart.set_enabled(True, key) is True
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
            value, _ = winreg.QueryValueEx(handle, "JobLens")
        assert value == f'"{sys.executable}" --tray'
        assert autostart.set_enabled(False, key) is False
        assert autostart.set_enabled(False, key) is False    # already off: fine
    finally:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)


def test_developer_mode_cant_turn_it_on(monkeypatch):
    monkeypatch.setattr(autostart.paths, "IS_INSTALLED", False)
    assert autostart.supported() is False
    with pytest.raises(RuntimeError):
        autostart.set_enabled(True, r"Software\JobLensTest-never")
    assert Api(send=lambda e: None, graph=object()).autostart_status()["supported"] is False
