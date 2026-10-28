"""
Tests for the first-run Setup Wizard (Phase 10c) - offscreen, no Ollama needed.

Background work (hardware check, Ollama status) is replaced by fake
results, so these tests don't depend on this PC's hardware or services.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop import setup_wizard as sw  # noqa: E402
from job_agent import paths, settings  # noqa: E402
from job_agent.system_check import SystemInfo, recommend_models  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def wizard(app, monkeypatch, tmp_path):
    # Fresh profile; no real background checks.
    monkeypatch.setattr(paths, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(settings, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr(settings, "APP_HOME", tmp_path)
    monkeypatch.setattr(sw, "run_in_background", lambda *a, **k: None)
    # save_settings() also writes os.environ: let monkeypatch restore these
    # afterwards, or later tests would run with LLM_PROVIDER=anthropic.
    for key in ("LLM_PROVIDER", "LLM_MODEL", "ANTHROPIC_API_KEY", "SETUP_DONE"):
        monkeypatch.setenv(key, os.environ.get(key, ""))
    return sw.SetupWizard()


def fake_local_state(page, models_installed, running=True):
    pc = SystemInfo(ram_gb=16, gpu_name="RTX", vram_gb=8188 / 1024, vram_exact=True,
                    disk_free_gb=200, cpu_threads=8)
    page._show_models(recommend_models(pc))
    page._ollama_checked((True, running, models_installed))


def test_branching_local_vs_api(wizard):
    choice = wizard.page(sw.CHOICE)
    assert choice.nextId() == sw.LOCAL            # local is the default
    choice.api.setChecked(True)
    assert choice.nextId() == sw.API


def test_local_page_needs_ollama_running_and_model_downloaded(wizard):
    page = wizard.local_page
    fake_local_state(page, models_installed=[])
    assert page.chosen_model() == "qwen3:8b"      # the recommendation is preselected
    assert not page.isComplete()                   # model not downloaded yet
    assert page.download_button.isEnabled()
    fake_local_state(page, models_installed=["qwen3:8b"])
    assert page.isComplete()
    fake_local_state(page, models_installed=["qwen3:8b"], running=False)
    assert not page.isComplete()                   # Ollama stopped


def test_too_big_models_cannot_be_chosen(wizard):
    page = wizard.local_page
    pc = SystemInfo(ram_gb=8, gpu_name=None, vram_gb=None, vram_exact=False,
                    disk_free_gb=200, cpu_threads=4)
    page._show_models(recommend_models(pc))
    enabled = {a.name: b.isEnabled() for a, b in zip(page.advice, page.model_buttons.buttons())}
    assert enabled["qwen3:14b"] is False


def test_api_page_needs_a_key(wizard):
    assert not wizard.api_page.isComplete()
    wizard.api_page.key.setText("sk-ant-x")
    assert wizard.api_page.isComplete()


def test_finish_saves_local_choice(wizard):
    fake_local_state(wizard.local_page, models_installed=["qwen3:8b"])
    wizard.setField("useLocal", True)
    wizard.accept()
    values = settings.read_settings()
    assert values["LLM_PROVIDER"] == "ollama" and values["LLM_MODEL"] == "qwen3:8b"
    assert values["SETUP_DONE"] == "true"


def test_finish_saves_api_choice(wizard):
    wizard.page(sw.CHOICE).api.setChecked(True)
    wizard.api_page.key.setText("sk-ant-secret")
    wizard.accept()
    values = settings.read_settings()
    assert values["LLM_PROVIDER"] == "anthropic"
    assert values["ANTHROPIC_API_KEY"] == "sk-ant-secret"
