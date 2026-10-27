"""
Tests for Phase 9a: where files live, and reading/writing settings.

paths.py decides everything when it's imported, so each test re-imports it
(importlib.reload) after changing the environment.
"""

import importlib
import os

from job_agent import paths, settings


def test_developer_mode_uses_the_repo(monkeypatch):
    monkeypatch.delenv("JOB_HUNT_HOME", raising=False)
    p = importlib.reload(paths)
    assert not p.IS_INSTALLED
    assert p.DATA_DIR == p.REPO_DIR / "data"
    assert p.ENV_FILE == p.REPO_DIR / ".env"


def test_installed_mode_uses_localappdata(monkeypatch, tmp_path):
    monkeypatch.delenv("JOB_HUNT_HOME", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr("sys.frozen", True, raising=False)  # what PyInstaller sets
    p = importlib.reload(paths)
    assert p.IS_INSTALLED
    assert p.APP_HOME == tmp_path / "JobLens"
    assert p.DB_PATH == tmp_path / "JobLens" / "data" / "jobs.db"
    monkeypatch.undo()
    importlib.reload(paths)  # back to developer mode for the other tests


def test_override_with_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("JOB_HUNT_HOME", str(tmp_path))
    p = importlib.reload(paths)
    assert p.ENV_FILE == tmp_path / ".env"
    monkeypatch.delenv("JOB_HUNT_HOME")
    importlib.reload(paths)


def test_save_settings_writes_file_and_applies_now(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    monkeypatch.setattr(settings, "ENV_FILE", env_file)
    monkeypatch.setattr(settings, "APP_HOME", tmp_path)
    monkeypatch.setenv("LLM_MODEL", "qwen3:8b")

    settings.save_settings({"LLM_PROVIDER": "anthropic", "LLM_MODEL": "claude-haiku-5-5"})

    assert os.environ["LLM_MODEL"] == "claude-haiku-5-5"   # applied immediately
    text = env_file.read_text()
    assert "LLM_PROVIDER=anthropic" in text                 # and saved to disk
    assert settings.read_settings()["LLM_MODEL"] == "claude-haiku-5-5"


def test_read_settings_fills_defaults(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ENV_FILE", tmp_path / "missing.env")
    values = settings.read_settings()
    assert values["LLM_PROVIDER"] == "ollama"
    assert values["TRACING"] == "off"
