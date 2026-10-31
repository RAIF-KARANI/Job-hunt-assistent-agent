"""
Tests for 1.0.1: an honest Langfuse status with keys you can enter in the
app, and deleting a job (a friend's idea).
"""

import pytest
import requests

from desktop_web import bridge
from desktop_web.bridge import WRITABLE_SETTINGS, Api, langfuse_check
from job_agent import cover_note, settings, tracker
from job_agent.models import FitAnalysis, JobPosting, ResumeMatch


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "jobs.db")
    monkeypatch.setattr(cover_note, "NOTES_DIR", tmp_path / "notes")
    monkeypatch.setattr(settings, "APP_HOME", tmp_path)
    monkeypatch.setattr(settings, "ENV_FILE", tmp_path / ".env")
    for key in [*WRITABLE_SETTINGS, "LANGFUSE_SECRET_KEY"]:
        monkeypatch.setenv(key, settings.DEFAULTS.get(key, ""))


class Answer:
    def __init__(self, status, data=None):
        self.status_code, self._data = status, data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(self.status_code)

    def json(self):
        return self._data


def fake_langfuse(monkeypatch, *, up=True, keys=("pk-lf-1", "sk-lf-1")):
    asked = []

    def get(url, timeout, auth):
        asked.append(auth)
        if not up:
            raise requests.ConnectionError("refused")
        if tuple(auth) != keys:
            return Answer(401)
        return Answer(200, {"data": [{"id": "proj1", "name": "JobLens"}]})

    monkeypatch.setattr(requests, "get", get)
    return asked


# ---- Langfuse ------------------------------------------------------------------

def test_the_three_ways_langfuse_can_fail_are_told_apart(monkeypatch):
    fake_langfuse(monkeypatch)
    assert langfuse_check("http://localhost:3000", "", "") == ("no keys", None)
    assert langfuse_check("http://localhost:3000", "pk-lf-1", "wrong") == ("keys rejected", None)
    assert langfuse_check("http://localhost:3000", "pk-lf-1", "sk-lf-1") == ("running", {"id": "proj1", "name": "JobLens"})
    fake_langfuse(monkeypatch, up=False)
    assert langfuse_check("http://localhost:3000", "pk-lf-1", "sk-lf-1") == ("not reachable", None)


def test_your_case_langfuse_up_but_no_keys_says_no_keys_not_unreachable(monkeypatch):
    fake_langfuse(monkeypatch)
    api = Api(send=lambda e: None, graph=object())
    api.save_settings({"TRACING": "langfuse"})
    assert api.tracing_status()["langfuse"] == "no keys"


def test_keys_entered_in_the_app_make_it_run_and_the_secret_stays_hidden(monkeypatch):
    fake_langfuse(monkeypatch)
    api = Api(send=lambda e: None, graph=object())
    api.save_settings({"TRACING": "langfuse", "LANGFUSE_HOST": "http://localhost:3000", "LANGFUSE_PUBLIC_KEY": "pk-lf-1"})
    shown = api.set_langfuse_secret(" sk-lf-1 ")
    assert "LANGFUSE_SECRET_KEY" not in shown and shown["LANGFUSE_SECRET_KEY_SET"] is True
    assert settings.read_settings()["LANGFUSE_SECRET_KEY"] == "sk-lf-1"
    status = api.tracing_status()
    assert status["langfuse"] == "running" and status["langfuse_sessions"].endswith("/project/proj1/sessions/")
    assert api.test_langfuse()["message"].startswith("Connected to the Langfuse project “JobLens”")


def test_the_test_button_explains_each_failure(monkeypatch):
    asked = fake_langfuse(monkeypatch)
    api = Api(send=lambda e: None, graph=object())
    assert "Add the public and the secret key" in api.test_langfuse("http://localhost:3000", "", "")["message"]
    assert "rejected these keys" in api.test_langfuse("http://localhost:3000", "pk-lf-1", "nope")["message"]
    assert asked[-1] == ("pk-lf-1", "nope")                   # typed keys are tried before saving
    fake_langfuse(monkeypatch, up=False)
    assert "docker compose up -d" in api.test_langfuse("http://localhost:3000", "pk-lf-1", "sk-lf-1")["message"]


def test_bad_langfuse_settings_are_refused():
    api = Api(send=lambda e: None, graph=object())
    with pytest.raises(ValueError, match="http"):
        api.save_settings({"LANGFUSE_HOST": "localhost:3000; rm -rf"})
    with pytest.raises(ValueError):
        api.set_langfuse_secret("sk\nTRACING=off")
    with pytest.raises(ValueError):
        api.save_settings({"LANGFUSE_SECRET_KEY": "x"})        # only through set_langfuse_secret


# ---- delete a job ----------------------------------------------------------------

def save(url="https://jobs.example/1", company="Acme"):
    job = JobPosting(title="AI Engineer", company=company, location="Remote", employment_type="Full-time",
                     seniority="Mid", salary="Not specified", summary="s",
                     required_skills=["Python"], nice_to_have_skills=[], responsibilities=["x"])
    analysis = FitAnalysis(matching_skills=[], missing_skills=[], talking_points=[], verdict="ok")
    best = ResumeMatch(resume_name="cv", analysis=analysis, fit_score=70)
    return tracker.save_job(url, job, best, None), job


def test_delete_removes_the_job_its_cover_notes_files_and_notes(tmp_path):
    keep_id, _ = save("https://jobs.example/keep", "Keep Ltd")
    job_id, job = save()
    cover_note.save_cover_note(job_id, job, "Dear team, ...", approved=True)
    cover_note.save_cover_note(keep_id, job, "Other note", approved=True)
    tracker.save_notes(job_id, {"notes": "secret salary talk", "contact": "Sam"})
    removed = Api(send=lambda e: None, graph=object()).delete_job(job_id)
    assert removed == {"company": "Acme", "title": "AI Engineer", "cover_notes": 1, "files": 1}
    assert tracker.get_job(job_id) is None and tracker.get_cover_notes(job_id) == []
    with tracker._db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM cover_notes WHERE job_id = ?", (job_id,)).fetchone()[0] == 0
    assert [p.name.split("_")[0] for p in (tmp_path / "notes").glob("*.md")] == [str(keep_id)]   # the other job's stays
    assert [j["id"] for j in tracker.list_jobs()] == [keep_id]


def test_deleting_a_job_the_agent_is_working_on_is_refused():
    job_id, _ = save()
    api = Api(send=lambda e: None, graph=object())
    api._runner.history = [{"type": "started", "url": "https://jobs.example/1"}]
    api._runner.last_pause = {"kind": "review"}                 # its cover note waits for you
    with pytest.raises(RuntimeError, match="working on this job"):
        api.delete_job(job_id)
    assert tracker.get_job(job_id) is not None
    with pytest.raises(ValueError):
        api.delete_job(999)


def test_a_deleted_job_can_be_analyzed_again_as_new():
    job_id, job = save()
    tracker.delete_job(job_id)
    assert tracker.find_job_id("https://jobs.example/1") is None   # the agent won't "reuse" a deleted analysis
    new_id, _ = save()
    assert new_id != job_id


def test_bridge_module_still_exports_its_helpers():
    assert callable(bridge._langfuse_project)
