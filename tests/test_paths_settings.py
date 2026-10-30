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
    # save_settings() writes os.environ too: register both keys so monkeypatch
    # restores them after the test (LLM_PROVIDER used to leak into later tests).
    monkeypatch.setenv("LLM_MODEL", "qwen3:8b")
    monkeypatch.setenv("LLM_PROVIDER", os.environ.get("LLM_PROVIDER", "ollama"))

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


# ---- after a restart, your saved settings are the ones used (31 Oct 2026) ----

FRESH_START_KEYS = ["LLM_PROVIDER", "LLM_MODEL", "JUDGE_EVIDENCE", "TRACING", "UPDATE_CHECK", "OLLAMA_NUM_CTX"]


def fresh_start(monkeypatch, tmp_path, file_text, terminal=None):
    """What happens when JobLens starts: nothing in os.environ yet but what the
    terminal set, then load_settings()."""
    env_file = tmp_path / ".env"
    env_file.write_text(file_text)
    monkeypatch.setattr(settings, "ENV_FILE", env_file)
    for key in FRESH_START_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key, value in (terminal or {}).items():
        monkeypatch.setenv(key, value)
    settings.load_settings()


def test_the_saved_model_is_used_after_a_restart(monkeypatch, tmp_path):
    fresh_start(monkeypatch, tmp_path, "LLM_PROVIDER=ollama\nLLM_MODEL=llama3.2\nJUDGE_EVIDENCE=false\n")
    assert os.environ["LLM_MODEL"] == "llama3.2"          # was qwen3:8b: the default won
    assert os.environ["JUDGE_EVIDENCE"] == "false"
    from job_agent import llm
    assert llm.get_llm().model == "llama3.2"               # what the agent actually calls


def test_a_saved_api_choice_survives_a_restart(monkeypatch, tmp_path):
    fresh_start(monkeypatch, tmp_path, "LLM_PROVIDER=anthropic\nLLM_MODEL=claude-haiku-5-5\n")
    assert (os.environ["LLM_PROVIDER"], os.environ["LLM_MODEL"]) == ("anthropic", "claude-haiku-5-5")


def test_defaults_fill_only_what_the_file_doesnt_set(monkeypatch, tmp_path):
    fresh_start(monkeypatch, tmp_path, "LLM_MODEL=qwen3:14b\n")
    assert os.environ["LLM_MODEL"] == "qwen3:14b"
    assert os.environ["TRACING"] == "off" and os.environ["UPDATE_CHECK"] == "true"


def test_a_terminal_variable_still_beats_the_file(monkeypatch, tmp_path):
    fresh_start(monkeypatch, tmp_path, "LLM_MODEL=llama3.2\n", terminal={"LLM_MODEL": "qwen3:4b"})
    assert os.environ["LLM_MODEL"] == "qwen3:4b"


def test_the_page_and_the_agent_agree(monkeypatch, tmp_path):
    # Settings shows read_settings(); the agent uses os.environ. They must match.
    fresh_start(monkeypatch, tmp_path, "LLM_PROVIDER=ollama\nLLM_MODEL=llama3.2\nTRACING=langfuse\nUPDATE_CHECK=false\n")
    shown = settings.read_settings()
    for key in FRESH_START_KEYS:
        assert os.environ[key] == shown[key], key
