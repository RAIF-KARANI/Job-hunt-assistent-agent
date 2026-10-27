"""
The main window: one window, four tabs.

    Analyze  | Tracker | Dashboard | Settings
    (9c)       (9d)      (9e)        (9b)

Tabs never call each other directly; they're connected here with signals.
"""

import os

from PySide6.QtWidgets import QMainWindow, QMessageBox, QTabWidget

from desktop.analyze_tab import AnalyzeTab
from desktop.dashboard_tab import DashboardTab
from desktop.settings_tab import SettingsTab
from desktop.tracker_tab import TrackerTab
from job_agent import paths

STYLE = """
QWidget { font-size: 10pt; }
QGroupBox { font-weight: 600; margin-top: 14px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
QLabel#hint { color: palette(placeholder-text); }
QLabel[state="ok"]    { color: #006300; }
QLabel[state="error"] { color: #d03b3b; }
QPushButton { padding: 5px 14px; }
QPushButton:default { background: #2a78d6; color: white; border: none; border-radius: 4px; }
QPushButton:default:disabled { background: #9ec5f4; }
QLabel#title { font-size: 13pt; font-weight: 600; }
QLabel#fit   { font-size: 13pt; font-weight: 600; color: #2a78d6; }
QFrame#tile  { border: 1px solid palette(mid); border-radius: 6px; }
QLabel#kpi   { font-size: 18pt; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JobLens — AI job application assistant")
        self.resize(1100, 760)
        self.setStyleSheet(STYLE)

        self.tabs = QTabWidget()
        self.settings_tab = SettingsTab()
        self.analyze_tab = AnalyzeTab()
        self.tracker_tab = TrackerTab()
        self.tabs.addTab(self.analyze_tab, "Analyze")
        self.tabs.addTab(self.tracker_tab, "Tracker")

        self.dashboard_tab = DashboardTab()

        # Tabs talk through signals, never by reaching into each other:
        self.analyze_tab.jobs_changed.connect(self.tracker_tab.refresh)
        self.analyze_tab.jobs_changed.connect(self.dashboard_tab.draw_tracker)
        self.tracker_tab.draft_requested.connect(self.draft_for)
        self.tabs.addTab(self.dashboard_tab, "Dashboard")
        self.tabs.addTab(self.settings_tab, "Settings")
        self.setCentralWidget(self.tabs)

        mode = "installed" if paths.IS_INSTALLED else "developer"
        self.statusBar().showMessage(f"{mode} mode · data: {paths.DATA_DIR}")

        # First run: nothing to work with yet -> start on the Settings tab.
        if not self.settings_tab.is_ready():
            self.tabs.setCurrentWidget(self.settings_tab)
        self.settings_tab.check_connection()

    def draft_for(self, url: str):
        """Tracker -> Analyze: a tracked URL skips straight to drafting."""
        if self.analyze_tab.busy:
            QMessageBox.information(self, "Busy", "The agent is already working on a job.")
            return
        self.tabs.setCurrentWidget(self.analyze_tab)
        self.analyze_tab.url.setText(url)
        self.analyze_tab.fresh.setChecked(False)
        self.analyze_tab.analyze()

    def closeEvent(self, event):
        """Closing while the agent runs: ask, then exit immediately.

        A thread blocked inside an LLM call can't be stopped politely, so we
        end the process. Nothing is corrupted: the checkpointer saved every
        finished step, and the tracker only writes complete rows."""
        if self.analyze_tab.busy:
            answer = QMessageBox.question(
                self, "Agent is working",
                "The agent is still running. Close anyway? (The current run stops.)")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            os._exit(0)
        self.analyze_tab.shutdown()
        event.accept()
