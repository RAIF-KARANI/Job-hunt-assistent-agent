"""
The API the web page calls, and the events it receives (Phase 12b).

JS -> Python: pywebview exposes every public method of `Api` to the page:

    const jobs = await window.pywebview.api.list_jobs()

Each call runs on its own thread, returns JSON, and a raised exception
rejects the JS promise (the page shows the message). So slow calls like
llm_status() never freeze the window.

Python -> JS: events (see runner.py) are pushed with evaluate_js:

    window.joblens.onEvent({"type": "log", "text": "..."})

Lessons from spike 12a:
- The page must ask `app_info()` itself once `window.pywebview.api` exists;
  Python never assumes the page is listening yet.
- evaluate_js doesn't wait for promises, so data flows JS -> Python as
  calls, and Python -> JS only as fire-and-forget events.
- Events sent while the page is (re)loading are lost; `run_state()`
  returns what the page needs to catch up (busy? paused for review? the
  run's events so far).

Security: the page is local, but it renders text from the web (job
postings). So the API key is never sent to the page (only whether one is
set), and settings writes go through an allow-list.
"""

import json
import os
import shutil
import subprocess
import threading
import webbrowser
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import webview

from job_agent import __version__, followup, paths, runlog, settings, tracker
from job_agent.llm import llm_status

from desktop_web.runner import AgentRunner, Event

# Settings the page may change, with the values each accepts (None = free text).
WRITABLE_SETTINGS: dict[str, tuple | None] = {
    "LLM_PROVIDER": ("ollama", "anthropic"),
    "LLM_MODEL": None,
    "OLLAMA_NUM_CTX": None,
    "JUDGE_EVIDENCE": ("true", "false"),
    "TRACING": ("off", "langfuse", "langsmith"),
    "UI_3D": ("animated", "still", "off"),   # D14
    "UI_THEME": ("system", "dark", "light"),
    "SETUP_DONE": ("true", "false"),
    "UPDATE_CHECK": ("true", "false"),        # 13b
    "RESUMES_DEFAULT": None,                  # 14b: file names joined by "|"; "" = all
    "RESUMES_ASK": ("true", "false"),         # 14b: pick the resumes for each job
    "FIT_DETAIL": ("short", "detailed"),      # 14c: talking points + verdict length
    "FOLLOW_UP_DAYS": followup.DAY_CHOICES,   # 14e
    "QUICK_KEY": None,                        # 14f: e.g. "Ctrl+Alt+J", or "off" (checked below)
    "LANGFUSE_HOST": None,                    # 1.0.1: a web address (checked below)
    "LANGFUSE_PUBLIC_KEY": None,              # 1.0.1: the secret key goes through set_langfuse_secret()
}
SECRET_SETTINGS = ("ANTHROPIC_API_KEY", "LANGFUSE_SECRET_KEY", "LANGSMITH_API_KEY")


def to_json(value):
    """Anything -> what JSON can carry (Pydantic models, rows, dates...)."""
    return json.loads(json.dumps(value, default=_default))


def _default(o):
    if hasattr(o, "model_dump"):
        return o.model_dump(mode="json")
    if hasattr(o, "keys"):  # sqlite3.Row
        return dict(o)
    return str(o)


LANGSMITH_URL = "https://smith.langchain.com/"


def setup_needed() -> bool:
    """First launch: the wizard was never finished and there are no resumes
    (same rule as the Qt app, so an existing user never sees it again)."""
    return os.getenv("SETUP_DONE", "").lower() != "true" and not any(paths.DATA_DIR.glob("*.pdf"))


def _resume_path(name: str) -> Path:
    """A resume in the app's data folder, by file name only: a name with a
    folder in it (`../x.pdf`) or another extension is refused."""
    name = (name or "").strip()
    if not name or Path(name).name != name or not name.lower().endswith(".pdf"):
        raise ValueError("Not a resume file name.")
    return paths.DATA_DIR / name


def langfuse_check(host: str, public_key: str, secret_key: str) -> tuple[str, dict | None]:
    """Ask Langfuse which project these keys belong to (1.0.1).

    Returns (state, project): "running" with {"id", "name"}, or one of
    "no keys", "keys rejected", "not reachable" with None. Until 1.0.1
    every failure said "not reachable", even when Langfuse was up and only
    the keys were missing (the installed app had none)."""
    import requests

    if not public_key or not secret_key:
        return "no keys", None
    try:
        r = requests.get(f"{host}/api/public/projects", timeout=3, auth=(public_key, secret_key))
    except requests.RequestException:
        return "not reachable", None
    if r.status_code in (401, 403):
        return "keys rejected", None
    try:
        r.raise_for_status()
        project = (r.json().get("data") or [{}])[0]
        return "running", {"id": project.get("id"), "name": project.get("name")}
    except (requests.RequestException, ValueError, AttributeError):
        return "not reachable", None


def _langfuse_project(host: str) -> str | None:
    """The Langfuse project id (for session links), or None."""
    _, project = langfuse_check(host, os.getenv("LANGFUSE_PUBLIC_KEY", ""), os.getenv("LANGFUSE_SECRET_KEY", ""))
    return project and project.get("id")


def _records(df) -> list[dict]:
    """A DataFrame -> JSON rows (numpy numbers become plain ones, NaN -> null)."""
    return json.loads(df.to_json(orient="records"))


class Api:
    """Everything the page may call. Underscore names are hidden from JS."""

    def __init__(self, send: Callable[[Event], None], graph=None):
        # `send` delivers an event to the page; tests pass list.append.
        self._send = send
        self._runner = AgentRunner(emit=self._emit, graph=graph)
        self._window = None  # set by app.py, for native file dialogs
        self._setup_lock = threading.Lock()  # one install / download at a time
        from desktop_web.updates import UpdateChecker
        self._updates = UpdateChecker(paths.APP_HOME, __version__)  # 13b
        self._update_lock = threading.Lock()  # 13d: one download at a time
        self._update_file = None
        self._http_get = None  # None = requests.get; tests serve a stand-in
        self._quit = None  # set by app.py
        self._hotkey = None  # 14f: the shortcut listener, set by app.py
        self._exported: set[str] = set()  # 14i: files this session wrote (show_in_folder only opens these)

    def _emit(self, event: Event) -> None:
        self._send(to_json(event))

    # ---- app ----------------------------------------------------------------

    def app_info(self) -> dict:
        return {"version": __version__, "installed": paths.IS_INSTALLED,
                "data_dir": str(paths.DATA_DIR), "settings": self.get_settings(),
                "setup_needed": setup_needed()}

    def llm_status(self) -> dict:
        ok, message = llm_status()  # may wait a few seconds on the network
        return {"ok": ok, "message": message}

    # ---- the agent run ------------------------------------------------------

    def start_run(self, url: str, fresh: bool = False, resumes: list | None = None) -> dict:
        """`resumes`: file names picked on Analyze for this job (14b); None = the defaults."""
        return {"run_id": self._runner.start(url, fresh, resumes)}

    def resume(self, answer: dict) -> None:
        self._runner.resume(answer)

    def paste_text(self, text: str) -> None:
        self._runner.paste_text(text)

    def stop_run(self) -> bool:
        """The Stop button (12j): ends the running step; nothing is saved."""
        return self._runner.stop()

    def unfinished_run(self) -> dict | None:
        """14d: the last run, if it stopped before the end and can be continued."""
        return to_json(self._runner.unfinished())

    def continue_run(self, run_id: str) -> None:
        """14d: carry on after the last finished step (finished steps aren't redone)."""
        self._runner.continue_run(str(run_id))

    def discard_run(self, run_id: str) -> None:
        """14d: don't offer that run again. Nothing in the tracker or Evals changes."""
        self._runner.discard(str(run_id))

    def step_estimates(self) -> dict:
        """Typical seconds per timeline step on THIS PC, from the run log
        (all time): {"1": 27.4, "2": 66.4, ...}. Empty before the first run."""
        from job_agent import monitoring as m

        nodes = {r["node"]: r for r in _records(m.local_node_latency(None))}
        # The page's 5 steps = the graph's nodes (job_agent/graph.py, D15).
        parts = {"1": ["check_tracker", "read_posting"], "2": ["analyze_fit"],
                 "3": ["research_company"], "4": ["save_to_tracker"], "5": ["draft"]}
        return {step: round(sum(nodes[n]["avg_seconds"] for n in names if n in nodes), 1)
                for step, names in parts.items() if any(n in nodes for n in names)}

    def run_state(self) -> dict:
        """What a (re)loaded page needs to catch up, including this run's events to replay."""
        return to_json({"busy": self._runner.busy, "run_id": self._runner.run_id,
                        "paused": self._runner.last_pause, "events": list(self._runner.history)})

    def save_feedback(self, run_id: str | None, job_id: int | None, ratings: dict,
                      comment: str = "") -> int:
        """ratings: {"fit_score": "about right", "cover_note": "needed edits"}; returns how many saved."""
        saved = 0
        for aspect, rating in (ratings or {}).items():
            if rating:
                runlog.save_feedback(run_id, job_id, aspect, rating, comment)  # validates
                saved += 1
        return saved

    def feedback_options(self) -> dict:
        return dict(runlog.FEEDBACK_OPTIONS)

    # ---- tracker ------------------------------------------------------------

    def statuses(self) -> list:
        return list(tracker.STATUSES)

    def list_jobs(self) -> list:
        days = followup.days_setting()
        return [{**to_json(dict(row)), "follow_up": followup.is_due(row, days)} for row in tracker.list_jobs()]

    def get_job(self, job_id: int) -> dict:
        job = tracker.get_job(int(job_id))
        if job is None:
            raise ValueError(f"No job with id {job_id}")
        for raw in ("job_json", "fit_json", "company_json"):  # already parsed below
            job.pop(raw, None)
        job["cover_notes"] = tracker.get_cover_notes(job["id"])
        return to_json(job)

    def set_status(self, job_id: int, status: str) -> None:
        tracker.update_status(int(job_id), status)  # rejects unknown statuses

    # ---- export (14i) ----------------------------------------------------------

    def export_tracker(self) -> dict | None:
        """Every job to a CSV file you pick. None = you cancelled."""
        from job_agent import export

        path = self._save_path(export.tracker_file_name(), "CSV file (*.csv)")
        if not path:
            return None
        count = export.export_tracker_csv(path)
        self._exported.add(str(path))
        return {"path": str(path), "count": count}

    def export_cover_note(self, job_id: int, fmt: str) -> dict | None:
        """The job's latest approved cover note as .txt, .docx or .pdf."""
        from job_agent import export

        if fmt not in export.FORMATS:
            raise ValueError(f"Format must be one of {', '.join(export.FORMATS)}")
        job = tracker.get_job(int(job_id))
        if job is None:
            raise ValueError(f"No job with id {job_id}")
        notes = tracker.get_cover_notes(job["id"])
        if not notes:
            raise ValueError("This job has no approved cover note yet.")
        kinds = {"txt": "Text file (*.txt)", "docx": "Word document (*.docx)", "pdf": "PDF document (*.pdf)"}
        path = self._save_path(export.file_name("Cover note", job["company"], job["title"], ext=fmt), kinds[fmt])
        if not path:
            return None
        export.export_cover_note(path, fmt, notes[0]["text"], title=f"Cover note: {job['title']} at {job['company']}")
        self._exported.add(str(path))
        return {"path": str(path)}

    def show_in_folder(self, path: str) -> None:
        """Open Explorer at a file JobLens just exported (never any other path)."""
        if str(path) not in self._exported or not Path(path).exists():
            raise ValueError("Only a file exported in this session can be shown.")
        subprocess.Popen(["explorer", "/select,", str(Path(path))])

    def _save_path(self, name: str, kind: str) -> Path | None:
        """The native Save dialog. Tests replace this."""
        if not self._window:
            raise RuntimeError("No window to show a file dialog in.")
        from webview import FileDialog

        chosen = self._window.create_file_dialog(FileDialog.SAVE, save_filename=name, file_types=(kind,))
        if isinstance(chosen, (list, tuple)):
            chosen = chosen[0] if chosen else None
        if not chosen:
            return None
        path = Path(chosen)
        ext = Path(name).suffix
        return path if path.suffix.lower() == ext else path.with_name(path.name + ext)

    def delete_job(self, job_id: int) -> dict:
        """1.0.1 (a friend's idea): remove a job from the tracker, with its
        analysis, cover notes and your notes. Refused while the agent works on it."""
        job = tracker.get_job(int(job_id))
        if job is None:
            raise ValueError(f"No job with id {job_id}")
        runner = self._runner
        if (runner.busy or runner.last_pause) and runner.history and \
                any(e.get("url") == job["url"] for e in runner.history if e.get("type") in ("started", "continued")):
            raise RuntimeError("The agent is working on this job right now. Finish or stop that run first.")
        removed = tracker.delete_job(int(job_id))
        from job_agent import cover_note  # its .md copies: "<job id>_<company-title>.md"
        files = sorted(cover_note.NOTES_DIR.glob(f"{int(job_id)}_*.md")) if cover_note.NOTES_DIR.exists() else []
        for path in files:
            path.unlink(missing_ok=True)
        return {**removed, "files": len(files)}

    def save_notes(self, job_id: int, values: dict) -> dict:
        """14h: your notes, interview date and contact. Returns them as saved."""
        tracker.save_notes(int(job_id), values)
        job = tracker.get_job(int(job_id))
        return {field: job[field] for field in tracker.NOTE_FIELDS}

    def resume_prompt(self, job_id: int) -> dict:
        """14g: the prompt for improving your resume for this job, with its
        keyword coverage. Plain template: no AI call, your resume isn't in it."""
        from job_agent.resume_prompt import resume_prompt

        job = tracker.get_job(int(job_id))
        if job is None:
            raise ValueError(f"No job with id {job_id}")
        return to_json(resume_prompt(job["job"], job["best_match"]))

    def followed_up(self, job_id: int) -> None:
        """14e: you sent the follow-up; the next reminder is FOLLOW_UP_DAYS away."""
        followup.mark_followed_up(int(job_id))

    def snooze_follow_up(self, job_id: int) -> None:
        followup.snooze(int(job_id))

    def open_link(self, url: str) -> None:
        """Open a web link in your browser, never inside the app window.
        Only http(s): the page shows links from the web, and a file:// or
        other scheme could start a program."""
        url = (url or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("Only web links (http or https) can be opened.")
        webbrowser.open(url)

    # ---- dashboard ----------------------------------------------------------

    def dashboard(self, days: int | None = 30) -> dict:
        """Run-log numbers for the Dashboard, from the same monitoring.py
        functions the Qt Dashboard used, so both show the same numbers.
        `days` = None means all time. Jobs come from list_jobs()."""
        if days is not None and (isinstance(days, bool) or int(days) < 1):
            raise ValueError("days must be a positive number, or None for all time")
        days = None if days is None else int(days)
        from job_agent import monitoring as m  # pandas: loaded when the Dashboard opens

        runs, calls, decisions = m.local_runs(days), m.local_llm_calls(days), m.local_decisions(days)
        quality, pass_rate = m.local_quality(days)
        return {
            "days": days,
            "kpis": to_json(m.build_kpis(runs, calls, decisions)),
            "decisions": dict(zip(decisions["decision"], map(int, decisions["count"]))),
            "steps": _records(m.local_node_latency(days)),
            "quality": _records(quality),
            "pass_rate": pass_rate,
        }

    # ---- evals --------------------------------------------------------------

    def evals(self, model: str | None = None) -> dict:
        """How well the agent did (Evals screen, D9), from the run log.
        `model` = one model's runs only; None = all."""
        from job_agent import monitoring as m

        return to_json(m.local_evals(model or None))

    def tracing_status(self) -> dict:
        """Langfuse / LangSmith state, for trace links. Separate from evals()
        because asking Langfuse can take a few seconds when it's down."""
        mode = settings.read_settings().get("TRACING", "off")
        status = {"mode": mode, "langfuse": "off", "langfuse_sessions": None,
                  "langsmith": "off", "langsmith_url": LANGSMITH_URL}
        if mode == "langsmith":
            status["langsmith"] = "on" if os.getenv("LANGSMITH_API_KEY") else "no key"
        # Old runs may have Langfuse traces even when tracing is now off.
        if mode == "langfuse" or os.getenv("LANGFUSE_PUBLIC_KEY"):
            host = os.getenv("LANGFUSE_HOST", "http://localhost:3000").rstrip("/")
            state, project = langfuse_check(host, os.getenv("LANGFUSE_PUBLIC_KEY", ""),
                                            os.getenv("LANGFUSE_SECRET_KEY", ""))
            if project:
                status["langfuse"] = "running" if mode == "langfuse" else "off"
                status["langfuse_sessions"] = f"{host}/project/{project['id']}/sessions/"
            elif mode == "langfuse":
                status["langfuse"] = state  # "no keys" / "keys rejected" / "not reachable"
        return status

    def test_langfuse(self, host: str | None = None, public_key: str | None = None,
                      secret_key: str | None = None) -> dict:
        """Settings' Test button (1.0.1). Empty fields use what's saved, so the
        secret key never has to come back to the page."""
        host = (host or os.getenv("LANGFUSE_HOST") or "http://localhost:3000").strip().rstrip("/")
        state, project = langfuse_check(host, (public_key or os.getenv("LANGFUSE_PUBLIC_KEY", "")).strip(),
                                        (secret_key or os.getenv("LANGFUSE_SECRET_KEY", "")).strip())
        messages = {
            "running": f"Connected to the Langfuse project “{(project or {}).get('name') or 'unnamed'}”.",
            "no keys": "Add the public and the secret key (Langfuse → Settings → API Keys).",
            "keys rejected": "Langfuse is running, but it rejected these keys. Copy them again from Langfuse → Settings → API Keys.",
            "not reachable": f"Nothing answers at {host}. Start Langfuse: cd infra\\langfuse, then docker compose up -d.",
        }
        return {"ok": state == "running", "state": state, "message": messages[state]}

    def set_langfuse_secret(self, key: str) -> dict:
        """Write-only, like the Claude key: the page can set or clear it, never read it."""
        key = (key or "").strip()
        if any(ord(ch) < 32 for ch in key):
            raise ValueError("The key can't contain line breaks.")
        settings.save_settings({"LANGFUSE_SECRET_KEY": key})
        return self.get_settings()

    # ---- resumes (12g) ------------------------------------------------------

    def list_resumes(self) -> list:
        paths.ensure_dirs()
        return [{"name": p.name, "kb": round(p.stat().st_size / 1024)}
                for p in sorted(paths.DATA_DIR.glob("*.pdf"), key=lambda p: p.name.lower())]

    def add_resumes(self) -> list:
        """Ask for PDFs with Windows' own file dialog and COPY them in (the
        originals are never moved or changed). Returns the names added."""
        chosen = self._choose_files() or []
        paths.ensure_dirs()
        added = []
        for f in chosen:
            src = Path(f)
            if src.suffix.lower() != ".pdf" or not src.is_file():
                continue  # the dialog filters to PDFs; this guards a typed-in name
            shutil.copy2(src, paths.DATA_DIR / src.name)
            added.append(src.name)
        return added

    def remove_resume(self, name: str) -> None:
        """Delete the app's copy of a resume (the page asks first)."""
        target = _resume_path(name)
        if not target.exists():
            raise ValueError(f"No resume called '{name}'.")
        target.unlink()

    def open_data_folder(self) -> None:
        paths.ensure_dirs()
        os.startfile(paths.DATA_DIR)  # Explorer; Windows only, like the app

    def _choose_files(self):
        if not self._window:
            raise RuntimeError("No window to show a file dialog in.")
        return self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=True,
                                               file_types=("PDF files (*.pdf)",))

    def _attach(self, window) -> None:
        """The window, for native dialogs (not callable from JS: underscore)."""
        self._window = window

    # ---- setup: PC check, Ollama, API key (12g) -------------------------------

    def system_check(self, provider: str | None = None, model: str | None = None) -> dict:
        """Hardware, model advice and the 3D level that suits this PC (D14).
        Takes a few seconds (nvidia-smi / PowerShell)."""
        from job_agent import system_check as sc

        info = sc.detect_system()
        advice, summary = sc.recommend_models(info)
        current = settings.read_settings()
        provider = provider or current["LLM_PROVIDER"]
        if model is None:
            picked = next((a.name for a in advice if a.recommended), None)
            model = current["LLM_MODEL"] if provider == current["LLM_PROVIDER"] else picked
        level, reason = sc.recommend_3d(info, provider, model)
        return to_json({"info": info.__dict__, "advice": [a.__dict__ for a in advice],
                        "summary": summary, "ui3d": {"level": level, "reason": reason}})

    def ollama_status(self) -> dict:
        """Installed? Running? Which models? Starts Ollama if it's installed but stopped."""
        from job_agent import ollama_setup as o

        if o.is_installed() and not o.is_running():
            o.start()
        return {"installed": o.is_installed(), "running": o.is_running(),
                "models": o.installed_models(), "winget": o.winget_available()}

    def install_ollama(self) -> dict:
        """Install Ollama with winget (per user, no admin prompt), streaming its
        output as `setup_progress` events. Without winget: open the download page."""
        from job_agent import ollama_setup as o

        if not o.winget_available():
            webbrowser.open(o.DOWNLOAD_PAGE)
            return {"ok": False, "manual": True}
        with self._setup_lock:
            self._progress("install", "Installing Ollama with winget (a few minutes)...")
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            proc = subprocess.Popen(o.install_command(), stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, errors="replace",
                                    creationflags=flags)
            for line in proc.stdout:
                if line.strip():
                    self._progress("install", line.strip())
            code = proc.wait()
            o.start()
            ok = o.is_installed() and o.is_running()
            self._progress("install", "Ollama is installed and running." if ok
                           else f"winget finished (exit code {code}) but Ollama isn't running.",
                           done=True, ok=ok)
            return {"ok": ok, "manual": False}

    def pull_model(self, model: str) -> dict:
        """Download a model (minutes), streaming `setup_progress` events with
        a fraction for the progress bar. One download at a time."""
        from job_agent import ollama_setup as o

        model = (model or "").strip()
        if not model:
            raise ValueError("Choose a model first.")
        if not self._setup_lock.acquire(blocking=False):
            raise RuntimeError("Another download or install is still running.")
        try:
            o.pull(model, lambda message, fraction: self._progress("pull", message, fraction))
        except Exception as e:
            self._progress("pull", f"Download failed: {e}", done=True, ok=False)
            raise
        finally:
            self._setup_lock.release()
        self._progress("pull", f"{model} is ready.", 1.0, done=True, ok=True)
        return {"ok": True, "model": model}

    def test_api_key(self, key: str | None, model: str) -> dict:
        """A 5-token test call. `key` None = the saved key. Nothing is saved here."""
        key = (key or "").strip() or os.getenv("ANTHROPIC_API_KEY", "")
        if not key:
            return {"ok": False, "message": "Paste an API key first."}
        try:
            from langchain_anthropic import ChatAnthropic

            ChatAnthropic(model=model, api_key=key, max_tokens=5, timeout=20).invoke("Reply OK")
            return {"ok": True, "message": "The key works."}
        except Exception as e:  # wrong key, no credit, no network...
            return {"ok": False, "message": str(e)[:240]}

    def _progress(self, what: str, message: str, fraction: float | None = None,
                  done: bool = False, ok: bool | None = None) -> None:
        self._emit({"type": "setup_progress", "what": what, "message": message,
                    "fraction": fraction, "done": done, "ok": ok})

    # ---- updates (13b) --------------------------------------------------------

    def update_status(self) -> dict:
        """The last update check's answer (no network): for the sidebar."""
        from desktop_web import updates

        return {**self._updates.status(), "enabled": updates.enabled()}

    def check_for_updates(self) -> dict:
        """Ask GitHub now ("Check now" in Settings, 13c), even if the switch is off."""
        from desktop_web import updates

        result = self._updates.check(force=True)
        if result.get("newer"):  # the sidebar shows it too
            self._emit({"type": "update_available", "latest": result["latest"], "page": result["page"]})
        return {**result, "enabled": updates.enabled()}

    def download_update(self) -> dict:
        """13d: download the newer installer and verify it (size + SHA-256
        from GitHub), streaming `update_progress` events. Runs nothing."""
        from desktop_web import updates

        status = self._updates.status()
        installer = status.get("installer")
        if not status.get("newer") or not installer:
            raise RuntimeError("There's no newer version to download. Check for updates first.")
        if not self._update_lock.acquire(blocking=False):
            raise RuntimeError("The update is already downloading.")
        try:
            folder = paths.APP_HOME / "updates"
            updates.clean_downloads(folder)
            self._update_file = updates.download(
                installer, folder, get=self._http_get,
                progress=lambda done, total: self._emit({"type": "update_progress", "done": done, "total": total}))
        finally:
            self._update_lock.release()
        self._emit({"type": "update_ready", "latest": status["latest"]})
        return {"ok": True, "latest": status["latest"], "verified": True}

    def install_update(self) -> dict:
        """13d: run the verified installer and close JobLens; the installer
        upgrades in place and starts the new version. Not during a run."""
        from desktop_web import updates

        if self._runner.busy or self._runner.last_pause:
            raise RuntimeError("Finish or stop the current run first: installing closes JobLens.")
        status = self._updates.status()
        path = getattr(self, "_update_file", None)
        if not path or not status.get("installer") or not path.exists():
            raise RuntimeError("Download the update first.")
        updates.launch_installer(path, status["installer"])  # checks the file once more
        if self._quit:
            threading.Timer(1.0, self._quit).start()  # let this answer reach the page first
        return {"ok": True}

    def _on_quit(self, quit_app) -> None:
        """How the app closes itself (app.py) when the installer takes over."""
        self._quit = quit_app

    def _startup_update_check(self) -> None:
        """Run by app.py on a background thread once the window is open: at
        most once a day (cached), and only if the setting is on. Tells the
        page if there's a newer version."""
        from desktop_web import updates

        if not updates.enabled():
            return
        result = self._updates.check()
        if result.get("newer"):
            self._emit({"type": "update_available", "latest": result["latest"], "page": result["page"]})

    # ---- settings -----------------------------------------------------------

    def get_settings(self) -> dict:
        values = settings.read_settings()
        out = {k: v for k, v in values.items() if k not in SECRET_SETTINGS}
        out["ANTHROPIC_API_KEY_SET"] = bool(values.get("ANTHROPIC_API_KEY"))
        out["LANGFUSE_SECRET_KEY_SET"] = bool(values.get("LANGFUSE_SECRET_KEY"))
        return out

    def save_settings(self, updates: dict) -> dict:
        clean = {}
        for key, value in (updates or {}).items():
            if key not in WRITABLE_SETTINGS:
                raise ValueError(f"Setting '{key}' can't be changed from the app.")
            allowed = WRITABLE_SETTINGS[key]
            value = str(value).strip()
            if any(ord(ch) < 32 for ch in value):
                # A line break would write an extra line (another setting) into .env.
                raise ValueError(f"{key} can't contain line breaks or control characters.")
            if allowed and value not in allowed:
                raise ValueError(f"{key} must be one of {', '.join(allowed)}")
            if key == "LANGFUSE_HOST" and value and not value.startswith(("http://", "https://")):
                raise ValueError("The Langfuse address must start with http:// or https://")
            if key == "QUICK_KEY" and value.lower() != "off":
                from desktop_web.hotkey import parse
                value = parse(value)[2]  # raises with a readable message; "ctrl+alt+j" -> "Ctrl+Alt+J"
            clean[key] = value
        settings.save_settings(clean)
        if "QUICK_KEY" in clean and self._hotkey:
            self._hotkey.change(clean["QUICK_KEY"])
        return self.get_settings()

    def quick_key_status(self) -> dict:
        """14f: the registered shortcut, or why there is none (e.g. another program has it)."""
        if self._hotkey is None:
            return {"key": None, "error": "The shortcut isn't available in this window."}
        return self._hotkey.status()

    def autostart_status(self) -> dict:
        """14e: "Start JobLens with Windows". Read from the registry each time."""
        from desktop_web import autostart
        return {"supported": autostart.supported(), "enabled": autostart.enabled()}

    def set_autostart(self, on: bool) -> dict:
        from desktop_web import autostart
        autostart.set_enabled(bool(on))
        return self.autostart_status()

    def set_api_key(self, key: str) -> dict:
        """Write-only: the page can set or clear the key, never read it back."""
        settings.save_settings({"ANTHROPIC_API_KEY": (key or "").strip()})
        return self.get_settings()


def window_sender(window) -> Callable[[Event], None]:
    """Deliver events to the page. Before the page has loaded window.joblens,
    the `&&` drops the event instead of throwing; run_state() recovers it."""
    def send(event: Event) -> None:
        window.evaluate_js(f"window.joblens && window.joblens.onEvent({json.dumps(event)})")
    return send
