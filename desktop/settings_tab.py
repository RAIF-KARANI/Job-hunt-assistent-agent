"""
Settings tab: the first-run setup screen and the place to change settings.

Three groups, top to bottom, in the order a new user needs them:
  1. AI model  - local Ollama (free, private) or Claude with an API key
  2. Resumes   - which PDFs the agent compares against each job
  3. Options   - evidence double-check, tracing
"""

import shutil
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from desktop.threads import run_in_background
from job_agent import paths
from job_agent.llm import llm_status
from job_agent.settings import DEFAULT_MODELS, read_settings, save_settings

PROVIDERS = [("Local: Ollama (free, private)", "ollama"),
             ("Cloud: Anthropic Claude (API key)", "anthropic")]


class SettingsTab(QWidget):
    # Emitted after saving, so other tabs can refresh (e.g. resume count).
    settings_changed = Signal()
    # Asks the main window to open the Setup Wizard (Phase 10c).
    wizard_requested = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(self._model_group())
        layout.addWidget(self._resume_group())
        layout.addWidget(self._options_group())

        save = QPushButton("Save settings")
        save.setDefault(True)
        save.clicked.connect(self.save)  # signal -> slot
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(save)
        layout.addLayout(row)
        layout.addStretch()

        self.load()

    # ---- building the groups ------------------------------------------------

    def _model_group(self) -> QGroupBox:
        box = QGroupBox("1. AI model")
        form = QFormLayout(box)

        self.provider = QComboBox()
        for label, value in PROVIDERS:
            self.provider.addItem(label, value)  # visible label + hidden value
        self.provider.currentIndexChanged.connect(self._provider_changed)
        form.addRow("Provider", self.provider)

        self.model = QLineEdit()
        form.addRow("Model", self.model)

        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)  # show ••••
        self.api_key.setPlaceholderText("sk-ant-...")
        self.api_key_label = QLabel("API key")
        form.addRow(self.api_key_label, self.api_key)

        check_row = QHBoxLayout()
        self.check_button = QPushButton("Check connection")
        self.check_button.clicked.connect(self.check_connection)
        wizard_button = QPushButton("Run setup wizard...")
        wizard_button.setToolTip("Check this PC, get a recommended model, install Ollama, "
                                 "or switch to an API key")
        wizard_button.clicked.connect(self.wizard_requested)
        check_row.addWidget(wizard_button)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        check_row.addWidget(self.check_button)
        check_row.addWidget(self.status, 1)
        form.addRow(check_row)

        hint = QLabel('Local models need <a href="https://ollama.com">Ollama</a> and '
                      "about 16 GB of RAM. No strong PC? Use Claude with an API key "
                      "(about $0.01 per job with Claude Haiku).")
        hint.setOpenExternalLinks(True)
        hint.setWordWrap(True)
        hint.setObjectName("hint")
        form.addRow(hint)
        return box

    def _resume_group(self) -> QGroupBox:
        box = QGroupBox("2. Your resumes (PDF)")
        v = QVBoxLayout(box)
        self.resumes = QListWidget()
        self.resumes.setMaximumHeight(110)
        v.addWidget(self.resumes)
        row = QHBoxLayout()
        for text, slot in [("Add PDF...", self.add_resume),
                           ("Remove", self.remove_resume),
                           ("Open folder", self.open_folder)]:
            b = QPushButton(text)
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch()
        v.addLayout(row)
        note = QLabel("Every PDF here is a candidate resume; the agent picks the "
                      "best one for each job. Files stay on this PC.")
        note.setWordWrap(True)
        note.setObjectName("hint")
        v.addWidget(note)
        return box

    def _options_group(self) -> QGroupBox:
        box = QGroupBox("3. Options")
        form = QFormLayout(box)
        self.judge = QCheckBox("Double-check skill evidence with a second AI call "
                               "(more accurate, ~30 s slower)")
        form.addRow(self.judge)
        self.tracing = QComboBox()
        self.tracing.addItems(["off", "langfuse", "langsmith"])
        form.addRow("Tracing", self.tracing)
        return box

    # ---- behaviour ------------------------------------------------------------

    def load(self):
        s = read_settings()
        self.provider.setCurrentIndex(max(0, self.provider.findData(s["LLM_PROVIDER"])))
        self.model.setText(s["LLM_MODEL"])
        self.api_key.setText(s.get("ANTHROPIC_API_KEY", ""))
        self.judge.setChecked(s["JUDGE_EVIDENCE"].lower() == "true")
        self.tracing.setCurrentText(s["TRACING"])
        self._provider_changed(keep_model=True)
        self.refresh_resumes()

    def _provider_changed(self, *_, keep_model=False):
        provider = self.provider.currentData()
        is_cloud = provider == "anthropic"
        self.api_key.setVisible(is_cloud)
        self.api_key_label.setVisible(is_cloud)
        if not keep_model:
            self.model.setText(DEFAULT_MODELS[provider])
        self.status.setText("")

    def save(self):
        save_settings({
            "LLM_PROVIDER": self.provider.currentData(),
            "LLM_MODEL": self.model.text().strip(),
            "ANTHROPIC_API_KEY": self.api_key.text().strip(),
            "JUDGE_EVIDENCE": "true" if self.judge.isChecked() else "false",
            "TRACING": self.tracing.currentText(),
        })
        self.settings_changed.emit()
        self.check_connection()

    def check_connection(self):
        # llm_status() may wait up to 5 s on the network: never on the GUI thread.
        self.check_button.setEnabled(False)
        self.status.setText("Checking...")
        run_in_background(llm_status, on_done=self._show_status,
                          on_error=lambda msg: self._show_status((False, msg)))

    def _show_status(self, result):
        ok, message = result
        # Icon + text, never color alone (it must read in grayscale too).
        self.status.setText(("✔ " if ok else "✖ ") + message)
        self.status.setProperty("state", "ok" if ok else "error")
        self.status.style().unpolish(self.status)  # re-apply the stylesheet
        self.status.style().polish(self.status)
        self.check_button.setEnabled(True)

    def refresh_resumes(self):
        self.resumes.clear()
        paths.ensure_dirs()
        pdfs = sorted(paths.DATA_DIR.glob("*.pdf"))
        for pdf in pdfs:
            self.resumes.addItem(pdf.name)
        if not pdfs:
            self.resumes.addItem("(no resumes yet - click 'Add PDF...')")

    def add_resume(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Choose resume PDFs", str(Path.home()),
                                                "PDF files (*.pdf)")
        paths.ensure_dirs()
        for f in files:
            shutil.copy2(f, paths.DATA_DIR / Path(f).name)  # copy, never move the original
        self.refresh_resumes()
        if files:
            self.settings_changed.emit()

    def remove_resume(self):
        item = self.resumes.currentItem()
        target = paths.DATA_DIR / item.text() if item else None
        if not target or not target.exists():
            return
        answer = QMessageBox.question(
            self, "Remove resume",
            f"Remove '{target.name}' from the app?\n\n(Only the app's copy is deleted; "
            "your original file is untouched.)")
        if answer == QMessageBox.StandardButton.Yes:
            target.unlink()
            self.refresh_resumes()
            self.settings_changed.emit()

    def open_folder(self):
        paths.ensure_dirs()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.DATA_DIR)))

    def is_ready(self) -> bool:
        """Enough set up to analyze a job? (At least one resume.)"""
        return any(paths.DATA_DIR.glob("*.pdf"))
