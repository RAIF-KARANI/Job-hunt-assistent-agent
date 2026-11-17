"""JobLens's engine: the Python side of the Rust window (18d1, decision E6).

The Rust program (desktop_tauri/) opens the window and starts this module
beside it; the two talk over a pipe, one JSON object per line.

From the window (Rust -> Python):
    {"id": 7, "method": "list_jobs", "args": []}   the page calls the Api
    {"answer": 3, "result": ...}  or  {"answer": 3, "error": "..."}
                                                  the window answers an `ask`
    {"shell": "page_loaded"}                      what happened to the window
    {"shell": "visibility", "visible": false}

From the engine (Python -> Rust):
    {"id": 7, "result": [...]}  or  {"id": 7, "error": "..."}
    {"event": {...}}                              the same events pywebview gets
    {"do": "show", "args": {}}                    a request, no answer needed
    {"ask": 3, "do": "...", "args": {...}}        a request that waits for its answer

The Api (bridge.py) is the same one the pywebview window uses, so the page
calls exactly the same methods. The engine stops when the window closes its
end of the pipe: it ends a running step and frees the model first, like Quit.

    python -m desktop_web.engine        (normally started by the Rust window)

Smoke test (like `python -m desktop_web --smoke`): with JOBLENS_SMOKE=out.json
(and JOBLENS_SMOKE_SHOT=shot.png for a picture), the engine writes the report
once the page has asked for app_info, then closes the window.
"""

import io
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

Write = Callable[[dict], None]


class Shell:
    """The window, as the engine sees it: ask it to do things."""

    def __init__(self, write: Write):
        self._write = write
        self._lock = threading.Lock()
        self._next = 0
        self._waiting: dict[int, dict] = {}
        self.visible = True

    def do(self, action: str, **args) -> None:
        """Ask the window to do something; don't wait."""
        self._write({"do": action, "args": args})

    def ask(self, action: str, timeout: float | None = None, **args):
        """Ask the window and wait for its answer (a file dialog waits for you)."""
        with self._lock:
            self._next += 1
            number = self._next
            slot = {"done": threading.Event()}
            self._waiting[number] = slot
        self._write({"ask": number, "do": action, "args": args})
        if not slot["done"].wait(timeout):
            with self._lock:
                self._waiting.pop(number, None)
            raise TimeoutError(f"The window didn't answer '{action}'.")
        if "error" in slot:
            raise RuntimeError(slot["error"])
        return slot.get("result")

    def answered(self, message: dict) -> None:
        with self._lock:
            slot = self._waiting.pop(message.get("answer"), None)
        if slot is None:
            return
        if "error" in message:
            slot["error"] = str(message["error"])
        else:
            slot["result"] = message.get("result")
        slot["done"].set()

    def give_up(self) -> None:
        """The window is gone: nobody will answer."""
        with self._lock:
            waiting, self._waiting = self._waiting, {}
        for slot in waiting.values():
            slot["error"] = "The JobLens window closed."
            slot["done"].set()


def file_filter(kind: str) -> dict:
    """pywebview's "CSV file (*.csv)" -> the window's {"name": "CSV file", "extensions": ["csv"]}."""
    name, _, rest = kind.partition("(")
    extensions = [p.strip().lstrip("*.") for p in rest.rstrip(")").split(";") if p.strip().lstrip("*.")]
    return {"name": name.strip() or kind, "extensions": extensions or ["*"]}


class Dialogs:
    """The native Open and Save dialogs, shown by the Rust window (18d2).
    They wait for you as long as you need: no time limit."""

    def __init__(self, shell: Shell):
        self.shell = shell

    def open_files(self, kind: str) -> list[str] | None:
        return self.shell.ask("pick_files", filters=[file_filter(kind)], multiple=True)

    def save_file(self, name: str, kind: str) -> str | None:
        return self.shell.ask("save_file", name=name, filters=[file_filter(kind)])


class Engine:
    """Routes each line from the window. Calls run on workers, so a slow one
    (llm_status waits on the network) never holds up the others; answers to
    `ask` are handled at once, never queued behind the calls waiting for them."""

    def __init__(self, api, write: Write, shell: Shell, on_page_loaded: Callable[[], None] = lambda: None,
                 smoke: Path | None = None, smoke_shot: Path | None = None):
        self.api = api
        self.write = write
        self.shell = shell
        self._on_page_loaded = on_page_loaded
        self._smoke = smoke
        self._smoke_shot = smoke_shot
        self._smoked = threading.Event()
        self._loaded = threading.Event()
        self._pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="joblens-call")

    def receive(self, line: str) -> None:
        line = line.strip()
        if not line:
            return
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            return
        if "answer" in message:
            self.shell.answered(message)
        elif "shell" in message:
            self._shell_event(message)
        elif "method" in message:
            self._pool.submit(self.call, message)

    def call(self, message: dict) -> None:
        call_id = message.get("id")
        name = str(message.get("method", ""))
        try:
            # Underscore names are the app's own (as in pywebview, they stay hidden from the page).
            if name.startswith("_") or not callable(getattr(self.api, name, None)):
                raise AttributeError(f"JobLens has no '{name}'")
            result = getattr(self.api, name)(*message.get("args", []))
            self.write({"id": call_id, "result": result})
            if name == "app_info" and self._smoke and not self._smoked.is_set():
                self._smoked.set()
                threading.Thread(target=self._smoke_report, args=(result,), daemon=True).start()
        except Exception as e:  # the page shows the message, as with pywebview
            self.write({"id": call_id, "error": str(e) or e.__class__.__name__})

    def _smoke_report(self, info: dict) -> None:
        """The page asked for app_info, so it is alive: report, then close."""
        report = {"ok": True, "window": "tauri", "version": info.get("version"),
                  "theme": (info.get("settings") or {}).get("UI_THEME", "system")}
        dialog = os.environ.get("JOBLENS_SMOKE_DIALOG")  # 18d2: "open" or "save"
        if dialog in ("open", "save"):
            dialogs = Dialogs(self.shell)
            try:
                answer = dialogs.open_files("PDF files (*.pdf)") if dialog == "open" else dialogs.save_file("JobLens test.csv", "CSV file (*.csv)")
                report["dialog"] = {"kind": dialog, "answer": answer}
            except Exception as e:
                report["dialog"] = {"kind": dialog, "error": str(e)}
        if self._smoke_shot:
            time.sleep(1.5)  # let the first screen and the fonts settle
            try:
                from PIL import ImageGrab

                ImageGrab.grab().save(self._smoke_shot)
                report["screenshot"] = str(self._smoke_shot)
            except Exception as e:  # a missing picture must not fail the test
                report["screenshot_error"] = str(e)
        self._smoke.write_text(json.dumps(report, indent=2), encoding="utf-8")
        self.shell.do("quit")

    def _shell_event(self, message: dict) -> None:
        kind = message.get("shell")
        if kind == "visibility":
            self.shell.visible = bool(message.get("visible", True))
        elif kind == "page_loaded" and not self._loaded.is_set():  # a reload loads it again
            self._loaded.set()
            self._on_page_loaded()


def _pipe_writer() -> Write:
    """The pipe is the engine's alone: anything the agent prints goes to
    stderr, or one stray print() would break the protocol."""
    pipe = os.fdopen(os.dup(sys.stdout.fileno()), "w", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr
    lock = threading.Lock()

    def write(message: dict) -> None:
        line = json.dumps(message, default=str)
        with lock:
            pipe.write(line + "\n")
            pipe.flush()

    return write


def main(argv=None) -> int:
    write = _pipe_writer()
    from desktop_web import startup
    from desktop_web.bridge import Api

    startup.prepare()  # cut-off runs, old scores: before the page reads them
    shell = Shell(write)
    api = Api(send=lambda event: write({"event": event}))
    api._quit = lambda: shell.do("quit")  # the update's installer takes over (13d)
    api._dialogs = Dialogs(shell)  # 18d2: Add PDFs, Save as
    api._is_hidden = lambda: not shell.visible  # 16i: a hidden window shows nobody "Did you apply?"
    startup.after_update(api)
    startup.background_chores()
    smoke = os.environ.get("JOBLENS_SMOKE")
    shot = os.environ.get("JOBLENS_SMOKE_SHOT")
    engine = Engine(api, write, shell, on_page_loaded=lambda: startup.check_for_updates_soon(api),
                    smoke=Path(smoke) if smoke else None, smoke_shot=Path(shot) if shot else None)
    write({"event": {"type": "engine_ready"}})

    stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
    for line in stdin:
        engine.receive(line)
    # The window closed its end: stop a running step and free the model, like Quit.
    shell.give_up()
    startup.free_the_gpu(api, tidy=True)
    os._exit(0)  # a run's threads must not keep the engine alive


if __name__ == "__main__":
    sys.exit(main())
