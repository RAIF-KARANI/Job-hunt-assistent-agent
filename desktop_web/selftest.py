"""
Self-test for the PACKAGED app (12h), ported from the Qt app's (v0.3; removed in 12i).

    JobLens.exe --self-test report.txt      (checks, no window)
    JobLens.exe --smoke result.json         (opens the window, checks the page)

Packaging bugs (a module PyInstaller didn't bundle, a missing data file,
package metadata not copied) only appear in the frozen .exe, and a windowed
.exe has no console to print errors to. So this imports and RUNS what the
app needs, then writes a report file. build_installer.py refuses to make an
installer unless it passes.
"""

import json
import sys
import traceback


def self_test(report_path: str) -> int:
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
    check("frozen", lambda: f"{getattr(sys, 'frozen', False)}; console: {sys.stdout is not None}")

    def web_files():
        web = paths.resource_path("desktop_web/web")
        js = list((web / "assets").glob("*.js"))
        if not (web / "index.html").exists() or not js:
            raise FileNotFoundError(f"built UI missing in {web}")
        # The 3D galaxy is its own file, loaded only when 3D is on (D19).
        if not any(p.name.startswith("Galaxy3D") for p in js):
            raise FileNotFoundError("the 3D galaxy file (Galaxy3D-*.js) wasn't bundled")
        return f"index.html + {len(js)} scripts"
    check("built UI bundled", web_files)
    check("icon bundled", lambda: paths.resource_path("assets/joblens.png").exists() or 1 / 0)

    for module in ["webview", "langchain_ollama", "langchain_anthropic", "ddgs", "pypdf", "pandas"]:
        check(f"import {module}", lambda m=module: __import__(m) and None)

    def no_console_print():
        # The windowed .exe has sys.stdout = None; the run log router must cope.
        from desktop_web.runner import _install_stdout
        _install_stdout()
        print("self-test: printing without a console")
        return "ok"
    check("print() in the windowed app", no_console_print)

    def build_graph():
        import sqlite3

        from langgraph.checkpoint.sqlite import SqliteSaver

        from job_agent.cover_note import SAFE_SERDE
        from job_agent.graph import build_job_hunt_graph
        g = build_job_hunt_graph(SqliteSaver(sqlite3.connect(":memory:"), serde=SAFE_SERDE))
        return f"{len(g.get_graph().nodes)} nodes"
    check("build LangGraph workflow", build_graph)

    def bridge():
        # The calls each screen makes first, answered as JSON the page can parse.
        from desktop_web.bridge import Api
        api = Api(send=lambda event: None)
        answers = {name: call() for name, call in [
            ("app_info", api.app_info), ("list_jobs", api.list_jobs),
            ("dashboard", lambda: api.dashboard(30)), ("evals", lambda: api.evals(None)),
            ("list_resumes", api.list_resumes), ("run_state", api.run_state)]}
        json.dumps(answers, allow_nan=False)
        return f"{len(answers['list_jobs'])} jobs, {answers['evals']['kpis']['runs']} runs in the log"
    check("bridge calls (Dashboard, Tracker, Evals, Settings)", bridge)

    def model():
        from job_agent.llm import llm_status
        status_ok, message = llm_status()
        return ("ready: " if status_ok else "not ready (fine for the test): ") + message
    check("model status", model)

    # Importing isn't enough: some bundling bugs only appear when code RUNS
    # (native libraries, lazily imported modules). One real search, one real
    # structured LLM call.
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

    lines.append("RESULT: " + ("PASS" if ok else "FAIL"))
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return 0 if ok else 1
