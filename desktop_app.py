"""
Phase 9: start the Job Hunt Assistant desktop app.

Run (venv activated):
    python desktop_app.py

Later (step 9f) PyInstaller turns this file into JobHuntAssistant.exe.
"""

import sys

from PySide6.QtWidgets import QApplication

from desktop.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Job Hunt Assistant")
    window = MainWindow()
    window.show()
    return app.exec()  # Qt's event loop: waits for clicks, redraws, until closed


if __name__ == "__main__":
    sys.exit(main())
