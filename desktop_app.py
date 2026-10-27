"""
Phase 9: start JobLens, the desktop app.

Run (venv activated):
    python desktop_app.py
    python desktop_app.py --self-test report.txt    (checks, no window)

PyInstaller turns this file into JobLens.exe (see joblens.spec, step 9f).
"""

import sys
import traceback


def self_test(report_path: str) -> int:
    """Smoke test for the PACKAGED app.

    Packaging bugs (a module PyInstaller didn't bundle, a missing data file,
    package metadata not copied) only appear in the frozen .exe, and a
    windowed .exe has no console to print errors to. So this imports and
    builds everything the app needs, then writes a report file.
    """
    lines, ok = [], True

    def check(name, fn):
        nonlocal ok
        try:
            detail = fn()
            lines.append(f"OK    {name}{': ' + str(detail) if detail else ''}")
        except Exception:
            ok = False
            lines.append(f"FAIL  {name}\n{traceback.format_exc()}")

    from job_agent import paths
    check("mode", lambda: f"{'installed' if paths.IS_INSTALLED else 'developer'}, "
                          f"data at {paths.DATA_DIR}")
    check("icon bundled", lambda: paths.resource_path("assets/joblens.png").exists() or 1 / 0)
    check("import langchain_ollama", lambda: __import__("langchain_ollama") and None)
    check("import langchain_anthropic", lambda: __import__("langchain_anthropic") and None)
    check("import ddgs (web search)", lambda: __import__("ddgs") and None)
    check("import pypdf", lambda: __import__("pypdf") and None)
    check("import matplotlib Qt backend",
          lambda: __import__("matplotlib.backends.backend_qtagg") and None)

    def build_graph():
        import sqlite3

        from langgraph.checkpoint.sqlite import SqliteSaver

        from job_agent.cover_note import SAFE_SERDE
        from job_agent.graph import build_job_hunt_graph
        g = build_job_hunt_graph(SqliteSaver(sqlite3.connect(":memory:"), serde=SAFE_SERDE))
        return f"{len(g.get_graph().nodes)} nodes"
    check("build LangGraph workflow", build_graph)

    def tracker():
        from job_agent.tracker import list_jobs
        return f"{len(list_jobs())} jobs"
    check("open tracker database", tracker)

    def model():
        from job_agent.llm import llm_status
        status_ok, message = llm_status()
        return ("ready: " if status_ok else "not ready (fine for the test): ") + message
    check("model status", model)

    # Importing isn't enough: some bundling bugs only appear when code RUNS
    # (native libraries, lazily imported modules). So do one real search and
    # one real structured LLM call.
    def search():
        from job_agent.research import web_search
        out = web_search.invoke({"query": "GitLab company"})
        return f"{out.count('URL:')} results" if "URL:" in out else f"no results ({out[:60]})"
    check("web search (runs the tool)", search)

    def llm_call():
        from pydantic import BaseModel

        from job_agent.llm import llm_status, structured_llm
        if not llm_status()[0]:
            return "skipped (model not ready)"

        class Answer(BaseModel):
            capital: str

        reply = structured_llm(Answer).invoke("What is the capital of France? One word.")
        return f"structured output OK: {reply.capital}"
    check("LLM call with structured output", llm_call)

    def window():
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        from desktop.main_window import MainWindow
        from PySide6.QtCore import QThreadPool

        app = QApplication.instance() or QApplication([])
        w = MainWindow()
        tabs = [w.tabs.tabText(i) for i in range(w.tabs.count())]
        w.analyze_tab.shutdown()
        QThreadPool.globalInstance().waitForDone(10000)  # let background checks finish
        app.processEvents()
        return ", ".join(tabs)
    check("build main window", window)

    lines.append("RESULT: " + ("PASS" if ok else "FAIL"))
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return 0 if ok else 1


def main() -> int:
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from desktop.main_window import MainWindow
    from job_agent.paths import resource_path

    app = QApplication(sys.argv)
    app.setApplicationName("JobLens")
    app.setWindowIcon(QIcon(str(resource_path("assets/joblens.png"))))  # title bar + taskbar
    window = MainWindow()
    window.show()
    code = app.exec()  # Qt's event loop: waits for clicks, redraws, until closed
    # Let short background tasks (e.g. a connection check) finish before
    # Python tears everything down, or they'd report to deleted objects.
    from PySide6.QtCore import QThreadPool
    QThreadPool.globalInstance().waitForDone(3000)
    return code


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--self-test":
        sys.exit(self_test(sys.argv[2]))
    sys.exit(main())
