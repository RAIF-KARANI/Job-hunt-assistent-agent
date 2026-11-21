"""
Tests for backup and restore (19a, E7): a round trip gives the same data
back, API keys never go into a backup, a file JobLens didn't make is refused
without changing anything, and the automatic backups keep the last four.
"""

import json
import os
import sqlite3
import zipfile
from datetime import datetime, timedelta

import pytest

from desktop_web.bridge import Api
from job_agent import backup, paths, settings, tracker
from job_agent.models import FitAnalysis, JobPosting, ResumeMatch

ALLOWED = {"LLM_PROVIDER", "LLM_MODEL", "UI_THEME"}


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    """A whole app home in a temp folder: data, notes, settings, backups."""
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(paths, "APP_HOME", tmp_path)
    monkeypatch.setattr(paths, "DATA_DIR", data)
    monkeypatch.setattr(paths, "NOTES_DIR", data / "cover_notes")
    monkeypatch.setattr(tracker, "DB_PATH", data / "jobs.db")
    monkeypatch.setattr(settings, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr(settings, "APP_HOME", tmp_path)
    for key in ("LLM_PROVIDER", "LLM_MODEL", "UI_THEME", "ANTHROPIC_API_KEY", "SOMETHING_ELSE"):
        monkeypatch.setenv(key, os.environ.get(key, ""))  # save_settings() writes os.environ: restored after
    return tmp_path


def save_job(url, company="Acme"):
    job = JobPosting(title="AI Engineer", company=company, location="Remote", employment_type="Full-time",
                     seniority="Mid", salary="Not specified", summary="s",
                     required_skills=["Python"], nice_to_have_skills=[], responsibilities=["x"])
    analysis = FitAnalysis(matching_skills=[], missing_skills=[], talking_points=[], verdict="ok")
    return tracker.save_job(url, job, ResumeMatch(resume_name="cv", analysis=analysis, fit_score=70), None)


def fill(home):
    save_job("https://jobs.example/1")
    save_job("https://jobs.example/2", company="Globex")
    (paths.DATA_DIR / "My CV.pdf").write_bytes(b"%PDF-1.4 mine")
    paths.NOTES_DIR.mkdir()
    (paths.NOTES_DIR / "1_acme-ai-engineer.md").write_text("Dear team", encoding="utf-8")
    settings.save_settings({"LLM_PROVIDER": "anthropic", "LLM_MODEL": "claude-haiku-5-5",
                            "ANTHROPIC_API_KEY": "sk-secret-123"})


def companies():
    return sorted(j["company"] for j in tracker.list_jobs())


def test_a_backup_restores_the_same_data(home):
    fill(home)
    made = backup.create(home / "out" / "b.zip")
    assert made["jobs"] == 2 and made["resumes"] == ["My CV.pdf"] and made["cover_notes"] == 1

    # Everything changes afterwards...
    tracker.delete_job(1)
    (paths.DATA_DIR / "My CV.pdf").unlink()
    (paths.DATA_DIR / "Other.pdf").write_bytes(b"%PDF other")
    (paths.NOTES_DIR / "1_acme-ai-engineer.md").unlink()
    settings.save_settings({"LLM_MODEL": "something-else"})

    result = backup.restore(home / "out" / "b.zip", ALLOWED)
    assert companies() == ["Acme", "Globex"]
    assert sorted(p.name for p in paths.DATA_DIR.glob("*.pdf")) == ["My CV.pdf"]
    assert (paths.NOTES_DIR / "1_acme-ai-engineer.md").read_text(encoding="utf-8") == "Dear team"
    assert settings.read_settings()["LLM_MODEL"] == "claude-haiku-5-5"
    assert result["jobs"] == 2 and result["before"]


def test_api_keys_never_go_into_a_backup_and_survive_a_restore(home):
    fill(home)
    backup.create(home / "b.zip")
    with zipfile.ZipFile(home / "b.zip") as z:
        everything = b"".join(z.read(n) for n in z.namelist())
    assert b"sk-secret-123" not in everything and b"ANTHROPIC_API_KEY" not in everything
    backup.restore(home / "b.zip", ALLOWED)
    assert settings.read_settings()["ANTHROPIC_API_KEY"] == "sk-secret-123"  # the key you have now stays


def test_a_restore_backs_up_what_is_there_first(home):
    fill(home)
    backup.create(home / "b.zip")
    save_job("https://jobs.example/3", company="Initech")  # only in the current data
    result = backup.restore(home / "b.zip", ALLOWED)
    assert "Initech" not in companies()
    backup.restore(result["before"], ALLOWED)  # the undo
    assert "Initech" in companies()


def test_only_known_settings_come_back(home):
    fill(home)
    backup.create(home / "b.zip")
    # A hand-made settings file with a key the app doesn't know and a secret.
    rebuilt = home / "hand.zip"
    with zipfile.ZipFile(home / "b.zip") as src, zipfile.ZipFile(rebuilt, "w") as out:
        for name in src.namelist():
            if name != "settings.env":
                out.writestr(name, src.read(name))
        out.writestr("settings.env", "UI_THEME=light\nSOMETHING_ELSE=1\nANTHROPIC_API_KEY=stolen\n")
    backup.restore(rebuilt, ALLOWED)
    now = settings.read_settings()
    assert now["UI_THEME"] == "light" and "SOMETHING_ELSE" not in now
    assert now["ANTHROPIC_API_KEY"] == "sk-secret-123"


def zip_with(path, files: dict, manifest=None):
    with zipfile.ZipFile(path, "w") as z:
        if manifest is not False:
            z.writestr(backup.MANIFEST, json.dumps(manifest or {"app": "JobLens", "format": 1}))
        for name, data in files.items():
            z.writestr(name, data)
    return path


@pytest.mark.parametrize("files, manifest, says", [
    ({}, False, "joblens-backup.json is missing"),
    ({"../evil.pdf": b"x"}, None, "doesn't make"),
    ({"resumes/../../evil.pdf": b"x"}, None, "doesn't make"),
    ({"resumes/sub/cv.pdf": b"x"}, None, "doesn't make"),
    ({"resumes/CON.pdf": b"x"}, None, "doesn't make"),
    ({"run.exe": b"MZ"}, None, "doesn't make"),
    ({"resumes/cv.exe": b"MZ"}, None, "doesn't make"),
    ({}, {"app": "Other"}, "isn't a JobLens backup"),
    ({}, {"app": "JobLens", "format": 99, "version": "9.0.0"}, "newer JobLens"),
    ({"jobs.db": b"not a database at all"}, None, "can't be read"),
])
def test_a_file_joblens_did_not_make_is_refused_and_nothing_changes(home, files, manifest, says):
    fill(home)
    bad = zip_with(home / "bad.zip", files, manifest)
    with pytest.raises(backup.BackupError, match=says):
        backup.restore(bad, ALLOWED)
    assert companies() == ["Acme", "Globex"]
    assert (paths.DATA_DIR / "My CV.pdf").exists() and (paths.NOTES_DIR / "1_acme-ai-engineer.md").exists()
    assert not (home / "evil.pdf").exists()


def test_not_a_zip_is_refused(home):
    (home / "x.zip").write_bytes(b"hello")
    with pytest.raises(backup.BackupError, match="not a readable .zip"):
        backup.inspect(home / "x.zip")


def test_an_older_backup_gets_todays_columns(home):
    old = home / "old.db"
    with sqlite3.connect(old) as db:  # the jobs table as the first release made it
        db.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT UNIQUE NOT NULL, "
                   "title TEXT NOT NULL, company TEXT NOT NULL, location TEXT, seniority TEXT, salary TEXT, "
                   "fit_score INTEGER, best_resume TEXT, status TEXT NOT NULL DEFAULT 'researched', "
                   "job_json TEXT, fit_json TEXT, company_json TEXT, created_at TEXT, updated_at TEXT)")
        db.execute("INSERT INTO jobs (url, title, company) VALUES ('https://jobs.example/9', 'Dev', 'Oldco')")
    zip_with(home / "old.zip", {"jobs.db": old.read_bytes()})
    assert backup.restore(home / "old.zip", ALLOWED)["jobs"] == 1
    with sqlite3.connect(tracker.DB_PATH) as db:
        columns = {r[1] for r in db.execute("PRAGMA table_info(jobs)")}
    assert {"notes", "interview_at", "posting_text"} <= columns


def test_automatic_backups_keep_the_last_four(home):
    fill(home)
    for i in range(6):
        made = backup.auto_backup("weekly")
        os.utime(made, (1_700_000_000 + i, 1_700_000_000 + i))  # distinct ages, oldest first
    assert len(backup.automatic()) == backup.KEEP


def test_the_weekly_backup_waits_a_week(home):
    fill(home)
    first = backup.auto_backup_if_due()
    assert first is not None
    assert backup.auto_backup_if_due() is None  # made just now
    assert backup.auto_backup_if_due(now=datetime.now() + timedelta(days=8)) is not None
    assert backup.status()["count"] == 2 and backup.status()["last_reason"] == "weekly"


def test_nothing_to_back_up_on_a_new_install(home):
    assert backup.auto_backup_if_due() is None and backup.automatic() == []


def test_the_bridge_asks_before_restoring_and_not_during_a_run(home):
    fill(home)
    api = Api(send=lambda e: None, graph=object())
    api._save_path = lambda name, kind: home / name
    made = api.create_backup()
    assert made["jobs"] == 2 and made["path"] in api._exported

    with pytest.raises(RuntimeError, match="Choose a backup first"):
        api.restore_backup()
    api._choose_files = lambda kind: [made["path"]]
    picked = api.choose_backup()
    assert picked["jobs"] == 2 and picked["file"].startswith("JobLens backup")

    api._runner.last_pause = {"type": "review"}  # a run waiting for you
    with pytest.raises(RuntimeError, match="Finish or stop"):
        api.restore_backup()
    api._runner.last_pause = None
    assert api.restore_backup()["jobs"] == 2
    assert api._picked_backup is None  # one confirmation, one restore


def test_cancelled_dialogs_change_nothing(home):
    api = Api(send=lambda e: None, graph=object())
    api._save_path = lambda name, kind: None
    api._choose_files = lambda kind: []
    assert api.create_backup() is None and api.choose_backup() is None
