"""
Phase 10c: the first-run Setup Wizard.

    Welcome -> How should JobLens run the AI?
                 ├─ On this PC  -> LocalPage: check the PC, recommend a model,
                 │                 install Ollama, download the model
                 └─ Cloud API   -> ApiPage: paste and test a Claude API key
            -> Resumes -> Done (settings saved)

QWizard basics used here:
    - each step is a QWizardPage; the wizard shows Back / Next / Finish
    - nextId() decides which page comes next (branching)
    - isComplete() decides whether Next is enabled; a page calls
      self.completeChanged.emit() whenever that answer may have changed
    - registerField() shares values between pages (e.g. the local/API choice)

Slow work never runs on the GUI thread: the PC check uses the thread pool,
the Ollama install is a QProcess (Qt's way to run a program and stream its
output), and the model download runs on its own QThread with progress signals.
"""

import shutil
from pathlib import Path

from PySide6.QtCore import QProcess, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QPlainTextEdit, QProgressBar, QPushButton, QRadioButton, QVBoxLayout, QWizard,
    QWizardPage,
)

from desktop.threads import run_in_background
from job_agent import ollama_setup, paths
from job_agent.settings import DEFAULT_MODELS, save_settings
from job_agent.system_check import detect_system, recommend_models

WELCOME, CHOICE, LOCAL, API, RESUMES, DONE = range(6)
VERDICT_ICON = {"fast": "✔", "slower": "⚠", "too big": "✖", "no disk space": "✖"}


def hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setObjectName("hint")
    label.setOpenExternalLinks(True)
    return label


class PullWorker(QThread):
    """Downloads a model on its own thread; reports progress with signals."""
    progress = Signal(str, float)   # message, fraction (-1 = unknown)
    done = Signal(bool, str)        # ok, message

    def __init__(self, model: str):
        super().__init__()
        self.model = model

    def run(self):  # runs on the new thread
        try:
            ollama_setup.pull(self.model, lambda msg, frac: self.progress.emit(
                msg, -1.0 if frac is None else frac))
            self.done.emit(True, f"{self.model} is ready.")
        except Exception as e:
            self.done.emit(False, f"Download failed: {e}")


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


class WelcomePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Welcome to JobLens")
        v = QVBoxLayout(self)
        v.addWidget(QLabel(
            "JobLens reads a job posting, compares it with your resumes, researches the "
            "company and drafts a cover note that you approve before anything is saved."))
        v.addWidget(hint("This setup takes a few minutes: choose how the AI runs, then add "
                         "your resumes. Your files stay on this PC."))
        v.addStretch()


class ChoicePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("How should JobLens run the AI?")
        v = QVBoxLayout(self)
        self.local = QRadioButton("On this PC with Ollama (free, private)")
        self.local.setChecked(True)
        v.addWidget(self.local)
        v.addWidget(hint("Nothing leaves your computer. Needs about 8–16 GB of RAM; "
                         "JobLens checks your PC and suggests a model in the next step."))
        self.api = QRadioButton("Cloud API (Anthropic Claude)")
        v.addWidget(self.api)
        v.addWidget(hint("Works on any PC and is fast. Needs an API key (about $0.01 per job "
                         "with Claude Haiku). Job text and your resume are sent to Anthropic."))
        v.addStretch()
        self.registerField("useLocal", self.local)  # read by other pages / the wizard

    def nextId(self):
        return LOCAL if self.local.isChecked() else API


class LocalPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Run the AI on this PC")
        self.setSubTitle("JobLens checked your hardware and suggests a model that fits.")
        self.models: list[str] = []
        self.pull_worker = None
        self.installer = None

        v = QVBoxLayout(self)
        self.summary = QLabel("Checking your PC...")
        self.summary.setWordWrap(True)
        v.addWidget(self.summary)

        self.model_buttons = QButtonGroup(self)
        self.model_box = QVBoxLayout()
        v.addLayout(self.model_box)
        self.model_buttons.idToggled.connect(lambda *_: self._refresh())

        # Ollama
        row = QHBoxLayout()
        self.ollama_status = QLabel()
        self.install_button = QPushButton("Install Ollama")
        self.install_button.clicked.connect(self.install_ollama)
        row.addWidget(self.ollama_status, 1)
        row.addWidget(self.install_button)
        v.addLayout(row)

        # Model download
        row2 = QHBoxLayout()
        self.model_status = QLabel()
        self.download_button = QPushButton("Download model")
        self.download_button.clicked.connect(self.download_model)
        row2.addWidget(self.model_status, 1)
        row2.addWidget(self.download_button)
        v.addLayout(row2)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.hide()
        v.addWidget(self.progress)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(90)
        self.log.hide()
        v.addWidget(self.log)
        v.addStretch()

    # --- lifecycle ---
    def initializePage(self):  # called each time the page is shown
        run_in_background(lambda: recommend_models(detect_system()), on_done=self._show_models,
                          on_error=lambda msg: self.summary.setText(f"Couldn't check the PC: {msg}"))
        self._check_ollama()

    def _show_models(self, result):
        advice, summary = result
        self.summary.setText(summary)
        for b in self.model_buttons.buttons():
            self.model_buttons.removeButton(b)
            b.deleteLater()
        for i, a in enumerate(advice):
            star = "  ★ recommended" if a.recommended else ""
            b = QRadioButton(f"{VERDICT_ICON[a.verdict]} {a.name}  ·  {a.verdict}: {a.reason}  ·  "
                             f"{a.download_gb:.1f} GB download{star}\n      {a.description}")
            b.setEnabled(a.verdict in ("fast", "slower"))
            b.setChecked(a.recommended)
            self.model_buttons.addButton(b, i)
            self.model_box.addWidget(b)
        self.advice = advice
        self._refresh()

    def chosen_model(self) -> str | None:
        i = self.model_buttons.checkedId()
        return self.advice[i].name if i >= 0 else None

    # --- Ollama ---
    def _check_ollama(self):
        def check():
            if ollama_setup.is_installed() and not ollama_setup.is_running():
                ollama_setup.start()  # installed but stopped: start it for the user
            return ollama_setup.is_installed(), ollama_setup.is_running(), ollama_setup.installed_models()
        run_in_background(check, on_done=self._ollama_checked)

    def _ollama_checked(self, result):
        installed, running, models = result
        self.installed, self.running, self.models = installed, running, models
        if running:
            self.ollama_status.setText("✔ Ollama is installed and running.")
        elif installed:
            self.ollama_status.setText("⚠ Ollama is installed but not running. Start the Ollama app.")
        else:
            self.ollama_status.setText("✖ Ollama isn't installed yet.")
        self._refresh()

    def install_ollama(self):
        if not ollama_setup.winget_available():
            QDesktopServices.openUrl(QUrl(ollama_setup.DOWNLOAD_PAGE))
            self.ollama_status.setText("Install Ollama from the page that opened, then click "
                                       "'Check again'.")
            self.install_button.setText("Check again")
            self.install_button.clicked.disconnect()
            self.install_button.clicked.connect(self._check_ollama)
            return
        self.install_button.setEnabled(False)
        self.ollama_status.setText("Installing Ollama with winget (a few minutes)...")
        self.log.show()
        self.installer = QProcess(self)
        self.installer.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.installer.readyReadStandardOutput.connect(
            lambda: self.log.appendPlainText(
                bytes(self.installer.readAllStandardOutput()).decode(errors="replace").strip()))
        self.installer.finished.connect(self._install_finished)
        cmd = ollama_setup.install_command()
        self.installer.start(cmd[0], cmd[1:])

    def _install_finished(self, code, _status):
        self.install_button.setEnabled(True)
        self.log.appendPlainText(f"winget finished (exit code {code}).")
        self._check_ollama()  # starts the server and refreshes the status

    # --- model download ---
    def download_model(self):
        model = self.chosen_model()
        if not model:
            return
        self.download_button.setEnabled(False)
        self.progress.setValue(0)
        self.progress.show()
        self.pull_worker = PullWorker(model)
        self.pull_worker.progress.connect(self._pull_progress)
        self.pull_worker.done.connect(self._pull_done)
        self.pull_worker.start()

    def _pull_progress(self, message: str, fraction: float):
        self.model_status.setText(message)
        if fraction >= 0:
            self.progress.setValue(int(fraction * 100))

    def _pull_done(self, ok: bool, message: str):
        self.model_status.setText(("✔ " if ok else "✖ ") + message)
        self.progress.setVisible(not ok and self.progress.value() < 100)
        self._check_ollama()

    # --- state ---
    def _refresh(self):
        running = getattr(self, "running", False)
        installed = getattr(self, "installed", False)
        model = self.chosen_model() if hasattr(self, "advice") else None
        have_model = model in self.models if model else False
        self.install_button.setVisible(not installed)
        busy = self.pull_worker is not None and self.pull_worker.isRunning()
        self.download_button.setEnabled(running and bool(model) and not have_model and not busy)
        self.download_button.setText(f"Download {model}" if model else "Download model")
        if model and have_model:
            self.model_status.setText(f"✔ {model} is downloaded.")
        elif model and running and not busy:
            self.model_status.setText(f"{model} isn't downloaded yet.")
        self.completeChanged.emit()

    def isComplete(self):
        model = self.chosen_model() if hasattr(self, "advice") else None
        return bool(getattr(self, "running", False) and model and model in self.models)

    def nextId(self):
        return RESUMES


class ApiPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Use the Claude API")
        v = QVBoxLayout(self)
        v.addWidget(hint('Create a key at <a href="https://console.anthropic.com">'
                         "console.anthropic.com</a> (Settings → API Keys) and paste it here."))
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("sk-ant-...")
        self.key.textChanged.connect(lambda: self.completeChanged.emit())
        v.addWidget(self.key)
        self.model = QLineEdit(DEFAULT_MODELS["anthropic"])
        v.addWidget(hint("Model (Claude Haiku is fast and costs about $0.01 per job):"))
        v.addWidget(self.model)
        row = QHBoxLayout()
        self.test_button = QPushButton("Test key")
        self.test_button.clicked.connect(self.test_key)
        self.status = QLabel()
        self.status.setWordWrap(True)
        row.addWidget(self.test_button)
        row.addWidget(self.status, 1)
        v.addLayout(row)
        v.addStretch()

    def test_key(self):
        key, model = self.key.text().strip(), self.model.text().strip()
        self.status.setText("Testing...")

        def call():
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(model=model, api_key=key, max_tokens=5).invoke("Reply OK").content
        run_in_background(call, on_done=lambda _: self.status.setText("✔ The key works."),
                          on_error=lambda msg: self.status.setText(f"✖ {msg[:160]}"))

    def isComplete(self):
        return bool(self.key.text().strip())

    def nextId(self):
        return RESUMES


class ResumesPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Add your resumes")
        self.setSubTitle("Add one or more PDF resumes. For each job, JobLens picks the best one.")
        v = QVBoxLayout(self)
        self.list = QListWidget()
        v.addWidget(self.list)
        add = QPushButton("Add PDF...")
        add.clicked.connect(self.add)
        v.addWidget(add)
        v.addWidget(hint("The files are copied into JobLens' own folder; your originals "
                         "aren't changed."))

    def initializePage(self):
        self.refresh()

    def refresh(self):
        self.list.clear()
        paths.ensure_dirs()
        for pdf in sorted(paths.DATA_DIR.glob("*.pdf")):
            self.list.addItem(pdf.name)
        self.completeChanged.emit()

    def add(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Choose resume PDFs", str(Path.home()),
                                                "PDF files (*.pdf)")
        paths.ensure_dirs()
        for f in files:
            shutil.copy2(f, paths.DATA_DIR / Path(f).name)
        self.refresh()

    def isComplete(self):
        return self.list.count() > 0

    def nextId(self):
        return DONE


class DonePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("All set")
        v = QVBoxLayout(self)
        self.text = QLabel()
        self.text.setWordWrap(True)
        v.addWidget(self.text)
        v.addStretch()

    def initializePage(self):
        w = self.wizard()
        how = (f"on this PC with {w.local_page.chosen_model()}" if self.field("useLocal")
               else f"with Claude ({w.api_page.model.text().strip()})")
        self.text.setText(f"JobLens will run the AI {how}.\n\nClick Finish, then paste a job "
                          "link in the Analyze tab. You can change everything later in Settings.")

    def nextId(self):
        return -1  # last page


# ---------------------------------------------------------------------------
# The wizard
# ---------------------------------------------------------------------------


class SetupWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("JobLens setup")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.resize(760, 560)
        self.local_page, self.api_page = LocalPage(), ApiPage()
        self.setPage(WELCOME, WelcomePage())
        self.setPage(CHOICE, ChoicePage())
        self.setPage(LOCAL, self.local_page)
        self.setPage(API, self.api_page)
        self.setPage(RESUMES, ResumesPage())
        self.setPage(DONE, DonePage())

    def accept(self):
        """Finish: save the choices (only now - Cancel changes nothing)."""
        if self.field("useLocal"):
            save_settings({"LLM_PROVIDER": "ollama", "LLM_MODEL": self.local_page.chosen_model()})
        else:
            save_settings({"LLM_PROVIDER": "anthropic",
                           "LLM_MODEL": self.api_page.model.text().strip(),
                           "ANTHROPIC_API_KEY": self.api_page.key.text().strip()})
        save_settings({"SETUP_DONE": "true"})
        super().accept()


def setup_needed() -> bool:
    """First launch: never finished the wizard and no resumes yet."""
    import os
    return os.getenv("SETUP_DONE", "").lower() != "true" and not any(paths.DATA_DIR.glob("*.pdf"))
