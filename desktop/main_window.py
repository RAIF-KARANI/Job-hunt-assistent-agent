"""
The main window: one window, four tabs.

    Analyze  | Tracker | Dashboard | Settings
    (9c)       (9d)      (9e)        (9b)

Tabs not built yet show a placeholder, so the app runs at every step.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget

from desktop.settings_tab import SettingsTab
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
"""


def placeholder(text: str) -> QLabel:
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setObjectName("hint")
    return label


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Job Hunt Assistant")
        self.resize(1100, 760)
        self.setStyleSheet(STYLE)

        self.tabs = QTabWidget()
        self.settings_tab = SettingsTab()
        self.tabs.addTab(placeholder("Analyze: coming in step 9c"), "Analyze")
        self.tabs.addTab(placeholder("Tracker: coming in step 9d"), "Tracker")
        self.tabs.addTab(placeholder("Dashboard: coming in step 9e"), "Dashboard")
        self.tabs.addTab(self.settings_tab, "Settings")
        self.setCentralWidget(self.tabs)

        mode = "installed" if paths.IS_INSTALLED else "developer"
        self.statusBar().showMessage(f"{mode} mode · data: {paths.DATA_DIR}")

        # First run: nothing to work with yet -> start on the Settings tab.
        if not self.settings_tab.is_ready():
            self.tabs.setCurrentWidget(self.settings_tab)
        self.settings_tab.check_connection()
