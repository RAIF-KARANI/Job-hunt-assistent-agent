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


class ShellTray:
    """18d3: the tray for the Rust window. The decisions are tray.py's (the
    same Tray as the pywebview window, unchanged): what the menu says, which
    notification to show, whether closing hides or quits. Only the drawing
    goes to the window: the menu, the tooltip, notifications."""

    MENU_IDS = ("open", "status", "follow_ups", "stop", "quit")

    def __init__(self, shell: Shell, tray):
        self.shell = shell
        self.tray = tray
        # Tray's own drawing calls now go to the window (it never imports pystray here).
        tray.start = self.start
        tray.stop = lambda: None
        tray.notify = self.notify
        tray._refresh = self.refresh

    def menu(self) -> list[dict]:
        from desktop_web.tray import follow_up_text, status_text

        t = self.tray
        return [
            {"id": "open", "text": "Open JobLens"},
            {"id": "status", "text": status_text(t.state), "enabled": False},
            {"id": "follow_ups", "text": follow_up_text(t.follow_ups), "visible": t.follow_ups > 0},
            {"separator": True},
            {"id": "stop", "text": "Stop the run", "visible": t.state.busy},
            {"id": "quit", "text": "Quit JobLens (stops the run)" if t.state.working else "Quit JobLens"},
        ]

    def tooltip(self) -> str:
        from desktop_web.tray import status_text

        return f"JobLens · {status_text(self.tray.state)}"[:127]  # Windows' tooltip limit

    def start(self) -> None:
        self.tray._icon = self  # Tray checks "is there an icon" before hiding to it
        self.refresh()

    def refresh(self) -> None:
        self.shell.do("tray", tooltip=self.tooltip(), menu=self.menu())

    def notify(self, title: str, message: str) -> None:
        self.tray._last_note = title  # what a click on it opens
        self.shell.do("notify", title=title, body=message)

    def clicked(self, item: str) -> None:
        """A tray menu item, or "open" for a click on the icon itself."""
        t = self.tray
        if item == "open":
            t.open()
        elif item == "follow_ups":
            t._open_tracker_now()
        elif item == "stop":
            t._stop_run()
        elif item == "quit":
            t.quit()

    def close_requested(self) -> None:
        """The window's X: Tray decides; hiding needs no answer, quitting ends the app."""
        if self.tray.window_closing(hide=lambda: self.shell.do("hide")):
            self.shell.do("quit")


class Engine:
    """Routes each line from the window. Calls run on workers, so a slow one
    (llm_status waits on the network) never holds up the others; answers to
    `ask` are handled at once, never queued behind the calls waiting for them."""

    def __init__(self, api, write: Write, shell: Shell, on_page_loaded: Callable[[], None] = lambda: None,
                 smoke: Path | None = None, smoke_shot: Path | None = None, tray: "ShellTray | None" = None):
        self.api = api
        self.tray = tray
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
        if os.environ.get("JOBLENS_SMOKE_NOTIFY"):  # 18d3: a notification, to see it arrive
            self.shell.do("notify", title="JobLens test", body="If you can read this, notifications work.")
            report["notified"] = True
            time.sleep(2)  # leave it on screen for the picture
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
            if self.tray:
                self.tray.tray.hidden = not self.shell.visible
        elif kind == "tray" and self.tray:  # 18d3: a tray menu item, or the icon
            self._pool.submit(self.tray.clicked, str(message.get("item", "")))
        elif kind == "notification_clicked" and self.tray:
            self._pool.submit(self.tray.tray.notification_clicked)
        elif kind == "close_requested":
            if self.tray:
                self._pool.submit(self.tray.close_requested)
            else:
                self.shell.do("quit")
        elif kind == "page_loaded" and not self._loaded.is_set():  # a reload loads it again
            self._loaded.set()
            self._on_page_loaded()


NOTIFICATION_SENDER = "JobLens.Desktop"  # the app id Windows shows notifications under


def register_notification_sender(icon: Path, key_root=None) -> None:
    """18d3: Windows shows a notification only for an app it knows. A desktop
    app makes itself known with this small per-user entry (name and icon); the
    uninstaller removes it (18d6). Harmless to write again on every start."""
    import winreg

    root = key_root if key_root is not None else winreg.HKEY_CURRENT_USER
    with winreg.CreateKey(root, rf"Software\Classes\AppUserModelId\{NOTIFICATION_SENDER}") as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "JobLens")
        if icon.exists():
            winreg.SetValueEx(key, "IconUri", 0, winreg.REG_SZ, str(icon))


def _start_tray(shell: Shell, api) -> "ShellTray | None":
    """13a: the tray, as in the pywebview window; drawn by the Rust window."""
    from desktop_web import autostart
    from desktop_web.tray import Tray, follow_up_reminders, keeps_tray
    from job_agent import followup, paths

    def open_page(page: str) -> None:
        shell.do("navigate", page=page)  # also shows the window

    tray = Tray(paths.resource_path("assets/joblens.png"), show=lambda: shell.do("show"),
                stop_run=api.stop_run, quit_app=lambda: shell.do("quit"),
                keep_in_tray=lambda: keeps_tray(api, autostart.enabled),
                follow_ups=lambda: len(followup.due_jobs()), open_tracker=lambda: open_page("tracker"),
                open_page=open_page)
    shell_tray = ShellTray(shell, tray)
    try:
        register_notification_sender(paths.resource_path("assets/joblens.png"))
    except Exception as e:  # without it notifications don't show; the tray still works
        print(f"! notifications: {e}")
    tray.start()
    follow_up_reminders(tray)
    return shell_tray


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
    tray_box: dict = {}

    def send(event: dict) -> None:
        write({"event": event})
        if "tray" in tray_box:  # 13a: the tray follows the same events as the page
            tray_box["tray"].on_event(event)

    api = Api(send=send)
    api._quit = lambda: shell.do("quit")  # the update's installer takes over (13d)
    api._dialogs = Dialogs(shell)  # 18d2: Add PDFs, Save as
    api._is_hidden = lambda: not shell.visible  # 16i: a hidden window shows nobody "Did you apply?"
    startup.after_update(api)
    startup.background_chores()
    tray = _start_tray(shell, api)
    if tray:
        tray_box["tray"] = tray.tray
    smoke = os.environ.get("JOBLENS_SMOKE")
    shot = os.environ.get("JOBLENS_SMOKE_SHOT")
    engine = Engine(api, write, shell, on_page_loaded=lambda: startup.check_for_updates_soon(api),
                    smoke=Path(smoke) if smoke else None, smoke_shot=Path(shot) if shot else None, tray=tray)
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
