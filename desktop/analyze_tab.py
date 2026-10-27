"""
Analyze tab: paste a job URL, watch the agent work, then approve the note.

Layout:
    [ Job URL ................................ ] [x] Re-analyze  [Analyze]
    [ progress bar ]  step: [2/5] Comparing your resumes...
    ┌ Agent log ─────────────┐┌ Review (appears when the agent pauses) ─┐
    │ [1/5] Reading ...      ││ Title @ Company        Fit 63/100       │
    │ [agent] decides ...    ││ matches / gaps                          │
    │                        ││ editable draft                          │
    │                        ││ [Approve & save] [Reject]  feedback [Rewrite]
    └────────────────────────┘└─────────────────────────────────────────┘

All agent work happens in AgentWorker on its own QThread (see agent_worker.py).
"""

import re

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QSplitter, QTextBrowser, QTextEdit, QVBoxLayout, QWidget,
)

from desktop.agent_worker import AgentWorker
from job_agent.llm import llm_status

STEP_LINE = re.compile(r"^\[(\d)/5\]\s*(.*)")


class PasteDialog(QDialog):
    """Shown when a page can't be read (login wall, JavaScript-only)."""

    def __init__(self, reason: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Paste the job description")
        self.resize(640, 480)
        v = QVBoxLayout(self)
        info = QLabel(f"I couldn't read that page ({reason}).\nOpen it in your browser, "
                      "copy the job description, and paste it here.")
        info.setWordWrap(True)
        v.addWidget(info)
        self.text = QPlainTextEdit()
        v.addWidget(self.text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        v.addWidget(buttons)


class AnalyzeTab(QWidget):
    # GUI -> worker requests. Emitting these queues the call onto the worker thread.
    start_requested = Signal(str, bool)
    resume_requested = Signal(dict)   # approve / edit / reject
    paste_requested = Signal(str)     # pasted job text (when a page can't be read)
    # Tells other tabs (Tracker, Dashboard) that the tracker changed.
    jobs_changed = Signal()

    def __init__(self):
        super().__init__()
        self._build_ui()
        self._start_worker()
        self.set_busy(False)
        self.review.hide()

    # ---- UI --------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.url = QLineEdit()
        self.url.setPlaceholderText("Paste a job posting URL, e.g. https://job-boards.greenhouse.io/...")
        self.url.returnPressed.connect(self.analyze)
        self.fresh = QCheckBox("Re-analyze if already tracked")
        self.analyze_button = QPushButton("Analyze")
        self.analyze_button.setDefault(True)
        self.analyze_button.clicked.connect(self.analyze)
        top.addWidget(self.url, 1)
        top.addWidget(self.fresh)
        top.addWidget(self.analyze_button)
        layout.addLayout(top)

        prog = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 5)
        self.progress.setFormat("step %v of %m")
        self.step = QLabel("Ready.")
        prog.addWidget(self.progress, 1)
        prog.addWidget(self.step, 2)
        layout.addLayout(prog)

        split = QSplitter()
        log_box = QGroupBox("Agent log")
        lv = QVBoxLayout(log_box)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Consolas", 9))
        lv.addWidget(self.log)
        split.addWidget(log_box)
        split.addWidget(self._build_review())
        split.setSizes([420, 680])
        layout.addWidget(split, 1)

    def _build_review(self) -> QWidget:
        self.review = QGroupBox("Review the cover note (the agent is paused, waiting for you)")
        v = QVBoxLayout(self.review)

        head = QHBoxLayout()
        self.job_title = QLabel()
        self.job_title.setObjectName("title")
        self.fit = QLabel()
        self.fit.setObjectName("fit")
        head.addWidget(self.job_title, 1)
        head.addWidget(self.fit)
        v.addLayout(head)
        self.breakdown = QLabel()
        self.breakdown.setObjectName("hint")
        v.addWidget(self.breakdown)

        self.evidence = QTextBrowser()
        self.evidence.setMaximumHeight(120)
        v.addWidget(self.evidence)

        self.warnings = QLabel()
        self.warnings.setWordWrap(True)
        self.warnings.setProperty("state", "error")
        v.addWidget(self.warnings)

        self.draft = QTextEdit()
        self.draft.setAcceptRichText(False)
        self.draft.textChanged.connect(self._count_words)
        v.addWidget(self.draft, 1)
        self.words = QLabel()
        self.words.setObjectName("hint")
        v.addWidget(self.words)

        buttons = QHBoxLayout()
        self.approve_button = QPushButton("Approve && save")  # && = a literal &
        self.approve_button.setDefault(True)
        self.approve_button.clicked.connect(self.approve)
        self.reject_button = QPushButton("Reject")
        self.reject_button.clicked.connect(self.reject)
        self.feedback = QLineEdit()
        self.feedback.setPlaceholderText("Or ask for changes: shorter, more confident...")
        self.rewrite_button = QPushButton("Rewrite")
        self.rewrite_button.clicked.connect(self.rewrite)
        buttons.addWidget(self.approve_button)
        buttons.addWidget(self.reject_button)
        buttons.addWidget(self.feedback, 1)
        buttons.addWidget(self.rewrite_button)
        v.addLayout(buttons)
        return self.review

    # ---- worker thread ---------------------------------------------------------

    def _start_worker(self):
        self.thread = QThread(self)
        self.worker = AgentWorker()
        self.worker.moveToThread(self.thread)
        # Requests go GUI -> worker; results come worker -> GUI. All queued.
        self.start_requested.connect(self.worker.start)
        self.resume_requested.connect(self.worker.resume)
        self.paste_requested.connect(self.worker.resume_with_text)
        self.worker.log.connect(self.on_log)
        self.worker.paused.connect(self.on_paused)
        self.worker.finished.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)
        self.thread.start()

    def shutdown(self):
        self.thread.quit()
        self.thread.wait(2000)

    # ---- actions (GUI thread) -------------------------------------------------

    def analyze(self):
        url = self.url.text().strip()
        if not url:
            return
        ok, message = llm_status()
        if not ok:
            QMessageBox.warning(self, "Model not ready", message + "\n\nSee the Settings tab.")
            return
        self.log.clear()
        self.review.hide()
        self.progress.setValue(0)
        self.set_busy(True, "Starting...")
        self.start_requested.emit(url, self.fresh.isChecked())

    def approve(self):
        self._answer({"decision": "approve", "text": self.draft.toPlainText().strip()})

    def reject(self):
        self._answer({"decision": "reject"})

    def rewrite(self):
        feedback = self.feedback.text().strip()
        if feedback:
            self.feedback.clear()
            self._answer({"decision": "edit", "feedback": feedback})

    def _answer(self, answer: dict):
        self.review.setEnabled(False)
        self.set_busy(True, "Rewriting the draft..." if answer["decision"] == "edit" else "Saving...")
        self.resume_requested.emit(answer)

    # ---- worker -> GUI slots ---------------------------------------------------

    def on_log(self, line: str):
        self.log.appendPlainText(line)
        m = STEP_LINE.match(line.strip())
        if m:
            self.progress.setValue(int(m.group(1)) - 1)
            self.step.setText(m.group(2))

    def on_paused(self, payload: dict, summary: dict):
        if payload.get("kind") == "paste_posting":
            self._ask_for_text(payload)
            return
        self.set_busy(False, "Waiting for your decision.")
        self.progress.setValue(5)
        self.job_title.setText(summary.get("title", ""))
        self.fit.setText(f"Fit {summary.get('fit_score', '?')}/100")
        self.breakdown.setText(f"{summary.get('resume', '')} · {summary.get('breakdown', '')}")
        matches = "".join(f"<li>{m}</li>" for m in summary.get("matches", []))
        gaps = "".join(f"<li>{g}</li>" for g in summary.get("gaps", []))
        self.evidence.setHtml(f"<b>Proven</b><ul>{matches}</ul><b>Gaps</b><ul>{gaps}</ul>")
        warn = payload.get("warnings") or []
        self.warnings.setText("✖ Check these numbers, they aren't in your resume or the "
                              "research: " + ", ".join(warn) if warn else "")
        self.warnings.setVisible(bool(warn))
        self.draft.setPlainText(payload["draft"])
        self.review.setTitle(f"Review draft #{payload['revision']} "
                             "(the agent is paused, waiting for you)")
        self.review.setEnabled(True)
        self.review.show()

    def on_finished(self, result: dict):
        self.review.hide()
        self.review.setEnabled(True)
        if result.get("saved_path"):
            self.set_busy(False, "✔ Approved and saved. Status: cover_note_ready.")
            self.log.appendPlainText(f"\nSaved: {result['saved_path']}")
        else:
            self.set_busy(False, "Rejected: nothing was saved. The job is in your tracker.")
        self.jobs_changed.emit()

    def on_failed(self, message: str):
        self.set_busy(False, "✖ Something went wrong (details in the log).")
        self.review.setEnabled(True)
        self.log.appendPlainText(f"\nERROR: {message}")

    def _ask_for_text(self, payload: dict):
        dialog = PasteDialog(payload.get("reason", ""), self)
        text = dialog.text.toPlainText() if dialog.exec() else ""
        if len(text.strip()) < 200:
            self.set_busy(False, "Stopped: no job description was pasted.")
            return
        self.set_busy(True, "Reading the pasted description...")
        self.paste_requested.emit(text.strip())

    # ---- helpers ---------------------------------------------------------------

    def set_busy(self, busy: bool, message: str = ""):
        self.busy = busy
        self.analyze_button.setEnabled(not busy)
        self.url.setEnabled(not busy)
        if busy:
            self.progress.setFormat("step %v of %m")
        if message:
            self.step.setText(message)

    def _count_words(self):
        self.words.setText(f"{len(self.draft.toPlainText().split())} words")
