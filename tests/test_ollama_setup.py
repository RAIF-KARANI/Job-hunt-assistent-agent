"""
Tests for the Ollama helper (Phase 10b) - no download, no install.
"""

import pytest

from job_agent import ollama_setup as o


def test_progress_line_gives_a_fraction():
    msg, frac = o.parse_pull_line(
        '{"status": "pulling 8eeb52dfb3bb", "digest": "sha256:x", '
        '"total": 5200000000, "completed": 1300000000}')
    assert frac == 0.25
    assert msg == "pulling: 1.30 GB of 5.20 GB"


def test_small_layers_use_smaller_units():
    msg, _ = o.parse_pull_line('{"status": "pulling abc", "total": 11338, "completed": 11338}')
    assert msg == "pulling: 11 KB of 11 KB"    # not "0.00 of 0.00 GB"


def test_status_only_lines_have_no_fraction():
    assert o.parse_pull_line('{"status": "verifying sha256 digest"}') == ("verifying sha256 digest", None)
    assert o.parse_pull_line('{"status": "success"}') == ("success", None)


def test_server_errors_are_raised():
    with pytest.raises(RuntimeError, match="file does not exist"):
        o.parse_pull_line('{"error": "pull model manifest: file does not exist"}')


def test_untagged_name_means_latest():
    # Found in the wizard: llama3.2 was installed as 'llama3.2:latest' but the
    # list looked for another spelling and offered to download it again.
    assert o.has_model("llama3.2", ["llama3.2:latest", "qwen3:8b"])
    assert o.has_model("llama3.2:latest", ["llama3.2"])
    assert o.has_model("qwen3:8b", ["qwen3:8b"])
    assert not o.has_model("qwen3:4b", ["qwen3:8b"])


def test_install_command_is_per_user_and_non_interactive():
    cmd = o.install_command()
    assert cmd[:4] == ["winget", "install", "--id", "Ollama.Ollama"]
    assert "--scope" in cmd and "user" in cmd           # no admin prompt
    assert "--disable-interactivity" in cmd


def test_find_ollama_uses_the_default_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(o.shutil, "which", lambda name: None)  # not on PATH
    exe = tmp_path / "Programs" / "Ollama" / "ollama.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert o.find_ollama() == exe
