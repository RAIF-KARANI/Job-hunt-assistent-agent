"""
Tests for the interview calendar (19b, E7): what's upcoming, the reminders
the evening before and an hour before (each once per date), the tray click
that opens the job, and the .ics file.
"""

from datetime import datetime

import pytest

from desktop_web import tray as tray_module
from desktop_web.bridge import Api
from job_agent import interviews, tracker
from job_agent.models import FitAnalysis, JobPosting, ResumeMatch

NOW = datetime(2026, 11, 23, 12, 0)  # a Monday, noon


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "jobs.db")


def save(url="https://jobs.example/1", company="Acme", interview=None, status=None, contact=None):
    job = JobPosting(title="AI Engineer", company=company, location="Dubai, UAE", employment_type="Full-time",
                     seniority="Mid", salary="Not specified", summary="s",
                     required_skills=["Python"], nice_to_have_skills=[], responsibilities=["x"])
    analysis = FitAnalysis(matching_skills=[], missing_skills=[], talking_points=[], verdict="ok")
    job_id = tracker.save_job(url, job, ResumeMatch(resume_name="cv", analysis=analysis, fit_score=70), None)
    if interview or contact:
        tracker.save_notes(job_id, {"interview_at": interview or "", "contact": contact or ""})
    if status:
        tracker.update_status(job_id, status)
    return job_id


def rows():
    return [dict(r) for r in tracker.list_jobs()]


def kinds(now):
    return [(j["company"], k) for j, k in interviews.due(rows(), now)]


def test_upcoming_is_soonest_first_and_leaves_out_the_past_and_rejected():
    save("https://jobs.example/1", "Later", "2026-11-26T09:00")
    save("https://jobs.example/2", "Sooner", "2026-11-24T15:00")
    save("https://jobs.example/3", "Past", "2026-11-23T09:00")
    save("https://jobs.example/4", "Today, no time", "2026-11-23")
    save("https://jobs.example/5", "Rejected", "2026-11-25T10:00", status="rejected")
    save("https://jobs.example/6", "None")
    names = [j["company"] for j in interviews.upcoming(rows(), NOW)]
    assert names == ["Today, no time", "Sooner", "Later"]
    assert [j["company"] for j in interviews.upcoming(rows(), NOW, days=1)] == ["Today, no time", "Sooner"]


def test_the_evening_before_then_an_hour_before_each_once():
    job_id = save(interview="2026-11-24T10:30")
    assert kinds(datetime(2026, 11, 23, 17, 59)) == []
    assert kinds(datetime(2026, 11, 23, 18, 0)) == [("Acme", "evening")]
    interviews.mark_sent(job_id, "2026-11-24T10:30", "evening")
    assert kinds(datetime(2026, 11, 23, 22, 0)) == []  # once
    assert kinds(datetime(2026, 11, 24, 9, 29)) == []
    assert kinds(datetime(2026, 11, 24, 9, 30)) == [("Acme", "hour")]
    interviews.mark_sent(job_id, "2026-11-24T10:30", "hour")
    assert kinds(datetime(2026, 11, 24, 10, 0)) == []
    assert kinds(datetime(2026, 11, 24, 10, 31)) == []  # over


def test_a_late_start_gets_only_the_hour_reminder():
    save(interview="2026-11-24T10:30")
    assert kinds(datetime(2026, 11, 24, 10, 0)) == [("Acme", "hour")]


def test_the_evening_reminder_says_today_when_it_comes_on_the_day():
    save(interview="2026-11-24T15:00")
    job, kind = interviews.due(rows(), datetime(2026, 11, 24, 8, 0))[0]
    assert kind == "evening"
    title, message = interviews.notice(job, kind, datetime(2026, 11, 24, 8, 0))
    assert title == "Interview today" and "today at 15:00" in message


def test_a_new_date_gets_new_reminders():
    job_id = save(interview="2026-11-24T10:30")
    interviews.mark_sent(job_id, "2026-11-24T10:30", "hour")
    tracker.save_notes(job_id, {"interview_at": "2026-11-27T10:30"})  # moved
    assert kinds(datetime(2026, 11, 26, 18, 30)) == [("Acme", "evening")]


def test_a_date_without_a_time_gets_only_the_evening_reminder():
    save(interview="2026-11-24")
    assert kinds(datetime(2026, 11, 23, 18, 0)) == [("Acme", "evening")]
    assert kinds(datetime(2026, 11, 24, 8, 0)) == []  # not on the day itself, and no "hour"


class FakeTray:
    def __init__(self):
        self.notes = []

    def notify(self, title, message, page=None):
        self.notes.append((title, message, page))


def test_the_tray_shows_each_reminder_once_and_a_click_opens_the_job():
    job_id = save(interview="2026-11-24T10:30")
    fake = FakeTray()
    assert tray_module.interview_reminders(fake, datetime(2026, 11, 23, 19, 0)) == 1
    assert tray_module.interview_reminders(fake, datetime(2026, 11, 23, 19, 5)) == 0
    title, message, page = fake.notes[0]
    assert title == "Interview tomorrow" and "AI Engineer at Acme, tomorrow at 10:30" in message
    assert page == f"tracker?job={job_id}"


def test_a_real_tray_click_goes_to_the_page_the_notification_named():
    opened = []
    t = tray_module.Tray("icon.png", show=lambda: None, stop_run=lambda: None, quit_app=lambda: None,
                         open_page=opened.append)
    t.notify("Interview soon", "…", page="tracker?job=7")
    t.notification_clicked()
    t.notify("Time to follow up", "…")
    t.notification_clicked()
    assert opened == ["tracker?job=7", "tracker"]


def test_the_ics_file():
    job_id = save(interview="2026-11-24T10:30", contact="Dana Lee; recruiter, dana@example.com")
    text = interviews.ics(tracker.get_job(job_id), now=datetime(2026, 11, 21, 9, 0))
    lines = text.split("\r\n")
    assert lines[0] == "BEGIN:VCALENDAR" and text.endswith("END:VCALENDAR\r\n")
    assert "DTSTART:20261124T103000" in lines and "DTEND:20261124T113000" in lines  # floating: your local time
    assert "TRIGGER:-PT1H" in lines
    unfolded = text.replace("\r\n ", "")
    assert "SUMMARY:Interview: AI Engineer at Acme" in unfolded
    assert "Contact: Dana Lee\\; recruiter\\, dana@example.com" in unfolded
    assert "LOCATION:Dubai\\, UAE" in unfolded
    assert all(len(line.encode("utf-8")) <= 75 for line in lines)


def test_an_all_day_ics_for_a_date_without_a_time():
    job_id = save(interview="2026-11-24")
    lines = interviews.ics(tracker.get_job(job_id)).split("\r\n")
    assert "DTSTART;VALUE=DATE:20261124" in lines and "DTEND;VALUE=DATE:20261125" in lines
    assert "BEGIN:VALARM" not in lines


def test_long_non_english_lines_fold_on_characters_not_bytes():
    job_id = save(company="Łódź Ünïcødé Søftwåre Laboratories and Partners International", interview="2026-11-24T10:30")
    text = interviews.ics(tracker.get_job(job_id))
    assert all(len(line.encode("utf-8")) <= 75 for line in text.split("\r\n"))
    text.encode("utf-8").decode("utf-8")  # no character cut in half
    assert "Łódź Ünïcødé Søftwåre Laboratories and Partners International" in text.replace("\r\n ", "")


def test_the_bridge_exports_the_ics(tmp_path):
    job_id = save(interview="2099-01-05T09:00")
    api = Api(send=lambda e: None, graph=object())
    api._save_path = lambda name, kind: tmp_path / name
    result = api.export_interview_ics(job_id)
    assert result["path"].endswith("Interview - Acme - AI Engineer.ics")
    assert "DTSTART:20990105T090000" in open(result["path"], encoding="utf-8").read()


def test_no_interview_date_no_ics():
    job_id = save()
    api = Api(send=lambda e: None, graph=object())
    with pytest.raises(ValueError, match="no interview date"):
        api.export_interview_ics(job_id)


def test_only_exported_calendar_files_are_opened(tmp_path):
    api = Api(send=lambda e: None, graph=object())
    other = tmp_path / "x.ics"
    other.write_text("x")
    with pytest.raises(ValueError, match="exported in this session"):
        api.open_exported(str(other))
    exe = tmp_path / "x.exe"
    exe.write_text("x")
    api._exported.add(str(exe))
    with pytest.raises(ValueError, match="Only calendar files"):
        api.open_exported(str(exe))
