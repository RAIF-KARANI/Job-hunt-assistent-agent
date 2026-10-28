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
    QButtonGroup, QCheckBox, QDialog, QDialogButtonBox, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QRadioButton,
    QSplitter, QTextBrowser, QTextEdit, QVBoxLayout, QWidget,
)

from desktop.agent_worker import AgentWorker
from job_agent import runlog
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
    # Phase 11c: a rating was saved -> the Dashboard can refresh.
    feedback_saved = Signal()

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
        layout.addWidget(self._build_feedback())

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

    def _build_feedback(self) -> QWidget:
        """Phase 11c: 'How did JobLens do?' - shown when a run ends.

        Your ratings are the one thing automatic checks can't measure: whether
        the fit score matched your own judgment, and whether the note was
        actually usable. They're saved locally and shown on the Dashboard.
        """
        self.feedback_box = QGroupBox("How did JobLens do? (saved on this PC, shown on the Dashboard)")
        v = QVBoxLayout(self.feedback_box)
        self.rating_groups = {}
        for aspect, label in [("fit_score", "The fit score was"),
                              ("cover_note", "The cover note was")]:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            group = QButtonGroup(self)
            for i, option in enumerate(runlog.FEEDBACK_OPTIONS[aspect]):
                button = QRadioButton(option)
                group.addButton(button, i)
                row.addWidget(button)
            row.addStretch()
            self.rating_groups[aspect] = group
            v.addLayout(row)
        row = QHBoxLayout()
        self.feedback_comment = QLineEdit()
        self.feedback_comment.setPlaceholderText("Optional comment, e.g. 'missed my Kubernetes experience'")
        save = QPushButton("Save feedback")
        save.clicked.connect(self.save_feedback)
        skip = QPushButton("Skip")
        skip.clicked.connect(self.feedback_box.hide)
        row.addWidget(self.feedback_comment, 1)
        row.addWidget(save)
        row.addWidget(skip)
        v.addLayout(row)
        self.feedback_box.hide()
        return self.feedback_box

    def _ask_for_feedback(self, job_id):
        self.feedback_run = (self.worker.thread_id if hasattr(self, "worker") else None, job_id)
        for group in self.rating_groups.values():
            group.setExclusive(False)       # allow clearing a previous choice
            for b in group.buttons():
                b.setChecked(False)
            group.setExclusive(True)
        # Pre-select the cover-note rating from what you actually did.
        suggested = runlog.cover_note_outcome(self.decision, self.ai_draft, self.final_text,
                                              self.revision)
        options = runlog.FEEDBACK_OPTIONS["cover_note"]
        self.rating_groups["cover_note"].button(options.index(suggested)).setChecked(True)
        self.feedback_comment.clear()
        self.feedback_box.show()

    def save_feedback(self):
        run_id, job_id = self.feedback_run
        comment = self.feedback_comment.text().strip()
        saved = 0
        for aspect, group in self.rating_groups.items():
            button = group.checkedButton()
            if button:
                runlog.save_feedback(run_id, job_id, aspect, button.text(), comment)
                saved += 1
        self.feedback_box.hide()
        if saved:
            self.step.setText(self.step.text() + "  ·  Thanks, feedback saved.")
            self.feedback_saved.emit()

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
        self.feedback_box.hide()   # never rate the previous run by mistake
        self.ai_draft = None
        self.progress.setValue(0)
        self.set_busy(True, "Starting...")
        self.start_requested.emit(url, self.fresh.isChecked())

    def approve(self):
        self.decision, self.final_text = "approve", self.draft.toPlainText().strip()
        self._answer({"decision": "approve", "text": self.final_text})

    def reject(self):
        self.decision, self.final_text = "reject", ""
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
        self.ai_draft, self.revision = payload["draft"], payload["revision"]  # for 11c
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
        if getattr(self, "ai_draft", None) is not None:
            self._ask_for_feedback(result.get("job_id"))

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
