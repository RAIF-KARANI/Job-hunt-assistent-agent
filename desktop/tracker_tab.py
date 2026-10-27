"""
Tracker tab: every analyzed job in a sortable, searchable table + details.

Qt's model/view architecture:

    SQLite ─► JobsModel ─► QSortFilterProxyModel ─► QTableView
              (the data)   (search + click-to-sort)  (what you see)

The VIEW never holds data; it asks the MODEL ("how many rows? what's in
row 3, column 2?"). The PROXY sits in between and re-orders / hides rows
without changing the model. Call model.load() and every view updates.
"""

import html

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QSplitter, QTableView, QTextBrowser, QVBoxLayout, QWidget,
)

from job_agent.tracker import STATUSES, get_cover_notes, get_job, list_jobs, update_status

SORT_ROLE = Qt.ItemDataRole.UserRole  # raw values for sorting (numbers sort as numbers)


class JobsModel(QAbstractTableModel):
    COLUMNS = [("id", "#"), ("company", "Company"), ("title", "Title"),
               ("fit_score", "Fit"), ("status", "Status"), ("updated_at", "Updated (UTC)")]

    def __init__(self):
        super().__init__()
        self.rows: list[dict] = []

    def load(self):
        # begin/endResetModel tell every attached view "everything changed".
        self.beginResetModel()
        self.rows = [dict(r) for r in list_jobs()]
        self.endResetModel()

    # --- the questions a view asks ---
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section][1]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        key = self.COLUMNS[index.column()][0]
        value = self.rows[index.row()][key]
        if role == Qt.ItemDataRole.DisplayRole:
            return "" if value is None else str(value)
        if role == SORT_ROLE:
            return value
        if role == Qt.ItemDataRole.TextAlignmentRole and key in ("id", "fit_score"):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def job_id(self, row: int) -> int:
        return self.rows[row]["id"]


class TrackerTab(QWidget):
    # Asks the main window to switch to Analyze and draft a note for this URL.
    draft_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.model = JobsModel()
        self.proxy = QSortFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(SORT_ROLE)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)  # search every column
        self.current: dict | None = None
        self.notes: list[dict] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search company, title or status...")
        self.search.textChanged.connect(self.proxy.setFilterFixedString)
        self.count = QLabel()
        self.count.setObjectName("hint")
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        top.addWidget(self.search, 1)
        top.addWidget(self.count)
        top.addWidget(refresh)
        layout.addLayout(top)

        split = QSplitter(Qt.Orientation.Vertical)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(3, Qt.SortOrder.DescendingOrder)  # best fit first
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # title gets the space
        for col in (0, 1, 3, 4, 5):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.selectionModel().currentRowChanged.connect(self.show_details)
        split.addWidget(self.table)
        split.addWidget(self._build_details())
        split.setSizes([300, 420])
        layout.addWidget(split, 1)

    def _build_details(self) -> QWidget:
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        actions = QHBoxLayout()
        actions.addWidget(QLabel("Status"))
        self.status = QComboBox()
        self.status.addItems(STATUSES)
        self.status.activated.connect(self.change_status)  # only user changes, not code
        actions.addWidget(self.status)
        self.open_button = QPushButton("Open posting")
        self.open_button.clicked.connect(self.open_posting)
        self.copy_button = QPushButton("Copy cover note")
        self.copy_button.clicked.connect(self.copy_note)
        self.draft_button = QPushButton("Draft a cover note")
        self.draft_button.clicked.connect(lambda: self.draft_requested.emit(self.current["url"]))
        for b in (self.open_button, self.copy_button, self.draft_button):
            actions.addWidget(b)
        actions.addStretch()
        v.addLayout(actions)
        self.details = QTextBrowser()
        self.details.setOpenExternalLinks(True)
        v.addWidget(self.details, 1)
        self._set_enabled(False)
        return box

    # ---- behaviour --------------------------------------------------------------

    def refresh(self):
        selected = self.current["id"] if self.current else None
        self.model.load()
        self.count.setText(f"{self.model.rowCount()} jobs")
        self.table.sortByColumn(self.proxy.sortColumn(), self.proxy.sortOrder())
        if selected is not None:
            self.select_job(selected)
        elif self.proxy.rowCount():
            self.table.selectRow(0)

    def select_job(self, job_id: int):
        for r in range(self.proxy.rowCount()):
            source = self.proxy.mapToSource(self.proxy.index(r, 0))
            if self.model.job_id(source.row()) == job_id:
                self.table.selectRow(r)
                return

    def show_details(self, current: QModelIndex, _previous=None):
        if not current.isValid():
            self.current = None
            self.details.clear()
            self._set_enabled(False)
            return
        # The view's row number is the PROXY's; map it back to the model's row.
        source_row = self.proxy.mapToSource(current).row()
        data = get_job(self.model.job_id(source_row))
        self.current = {"id": data["id"], "url": data["url"]}
        self.notes = get_cover_notes(data["id"])
        self.status.setCurrentText(data["status"])
        self._set_enabled(True)
        self.copy_button.setEnabled(bool(self.notes))
        self.details.setHtml(self._details_html(data))

    def _details_html(self, data: dict) -> str:
        e = html.escape  # job text comes from the web: never render it as raw HTML
        job, best, brief = data["job"], data["best_match"], data["company_brief"]
        a = best.analysis
        parts = [
            f"<h3>{e(job.title)} @ {e(job.company)}</h3>",
            f"<p>{e(job.location)} · {e(job.seniority)} · salary: {e(job.salary)} · "
            f'<a href="{e(data["url"])}">posting</a></p>',
            f"<p><b>Fit {best.fit_score}/100</b> with {e(best.resume_name)}<br>"
            f"<small>{e(best.score_breakdown)}</small></p>",
            f"<p>{e(a.verdict)}</p>",
            "<p><b>Proven</b></p><ul>" + "".join(
                f"<li>{e(m.requirement)} — <i>“{e(m.resume_evidence)}”</i></li>"
                for m in a.matching_skills) + "</ul>",
            "<p><b>Gaps</b></p><ul>" + "".join(f"<li>{e(g)}</li>" for g in a.missing_skills) + "</ul>",
        ]
        if brief:
            parts.append(f"<p><b>Company</b><br>{e(brief.what_they_do)}</p>")
        if self.notes:
            latest = self.notes[0]
            parts.append(f"<p><b>Approved cover note</b> <small>({e(latest['approved_at'])} UTC)</small></p>"
                         f"<p>{e(latest['text']).replace(chr(10), '<br>')}</p>")
        return "".join(parts)

    def change_status(self, _index: int):
        if not self.current:
            return
        update_status(self.current["id"], self.status.currentText())
        self.refresh()

    def open_posting(self):
        if self.current:
            QDesktopServices.openUrl(QUrl(self.current["url"]))

    def copy_note(self):
        if self.notes:
            QGuiApplication.clipboard().setText(self.notes[0]["text"])
            self.copy_button.setText("Copied ✔")

    def _set_enabled(self, enabled: bool):
        for w in (self.status, self.open_button, self.copy_button, self.draft_button):
            w.setEnabled(enabled)
        self.copy_button.setText("Copy cover note")
