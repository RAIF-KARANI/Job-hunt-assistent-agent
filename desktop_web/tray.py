"""
The tray icon (13a, D24): JobLens keeps working while its window is closed.

    closing the window while the agent works  -> the window hides to the tray
    closing it when nothing is going on        -> the app quits, as before
    a cover note waits for you (window hidden) -> a Windows notification
    tray menu: Open JobLens, the status, Stop the run, Quit
    14e: "Start with Windows" on -> JobLens lives in the tray: closing the
         window always hides it; jobs due a follow-up get one notification
         a day and a line in the menu
    14f: a run started from the quick box (Ctrl+Alt+J) is always told about,
         window hidden or not: you didn't start it from the window
    1.0.3: while the shortcut is on, closing the window keeps JobLens in the
         tray (the shortcut needs it running); clicking a notification
         opens JobLens on the screen it's about (Analyze or the Tracker)

pystray runs its own Windows message loop on its own thread, next to
pywebview's (which owns the main thread). It is LGPL-3.0, so it ships as
plain .py files the user can replace (joblens.spec, THIRD_PARTY_NOTICES.md).

The decisions are pure functions (close_action, status_text, notification),
so they're tested without a tray or a window (tests/test_tray.py).
"""

from typing import Callable

Event = dict


# ---------------------------------------------------------------------------
# What the tray knows, from the same events the page gets
# ---------------------------------------------------------------------------


class RunState:
    """The agent's state, followed from bridge events."""

    def __init__(self):
        self.busy = False
        self.waiting: str | None = None   # "review" | "paste_posting": the agent waits for you
        self.step: int | None = None
        self.title: str | None = None     # "AI Engineer @ Northwind" once step 1 knows it

    def update(self, event: Event) -> None:
        kind = event.get("type")
        if kind == "busy":
            self.busy = bool(event.get("busy"))
        elif kind == "started":
            self.waiting, self.step, self.title = None, None, None
        elif kind == "step":
            self.waiting, self.step = None, event.get("step")
        elif kind == "step_detail" and event.get("step") == 1 and " @ " in str(event.get("text", "")):
            self.title = event["text"]
        elif kind == "paused":
            self.waiting = event.get("kind")
            summary = event.get("summary") or {}
            if summary.get("title") and summary.get("company"):
                self.title = f"{summary['title']} @ {summary['company']}"
        elif kind in ("finished", "failed", "stopped"):
            self.waiting, self.step = None, None

    @property
    def working(self) -> bool:
        """Something you'd lose by quitting: a step running, or a draft waiting for you."""
        return self.busy or self.waiting is not None


def close_action(state: RunState, keep_in_tray: bool = False) -> str:
    """The window's close button: "hide" (keep working in the tray) or "quit".
    `keep_in_tray`: Start with Windows is on (14e), so JobLens stays."""
    return "hide" if state.working or keep_in_tray else "quit"


STEP_NAMES = {1: "reading the posting", 2: "comparing your resumes", 3: "researching the company",
              4: "saving to the tracker", 5: "writing the cover note"}


def status_text(state: RunState) -> str:
    """The tray menu's first line (and the icon's hover text)."""
    if state.waiting == "review":
        return "Your cover note is ready to review"
    if state.waiting == "paste_posting":
        return "Waiting for you to paste the job text"
    if state.busy:
        return f"Working: {STEP_NAMES.get(state.step, 'starting')} (step {state.step or 1} of 5)"
    return "Idle"


NIN_BALLOONUSERCLICK = 0x0405  # WM_USER + 5: you clicked our notification (shellapi.h)

# Which screen a notification opens when you click it (the page's #/<route>).
NOTE_PAGES = {"Cover note ready": "analyze", "JobLens needs you": "analyze", "Run failed": "analyze",
              "Run finished": "tracker", "Time to follow up": "tracker"}


def notification(event: Event, state: RunState) -> tuple[str, str] | None:
    """(title, message) to show when the window is hidden, or None."""
    kind = event.get("type")
    job = state.title or "your job"
    if kind == "paused" and event.get("kind") == "review":
        return "Cover note ready", f"The draft for {job} is waiting for your review. Click to open it."
    if kind == "paused" and event.get("kind") == "paste_posting":
        return "JobLens needs you", "The job page couldn't be read. Click to open JobLens and paste the job text."
    if kind == "finished":
        return "Run finished", f"{job}: " + ("saved to the tracker." if event.get("decision") == "approve"
                                             else "done.")
    if kind == "failed":
        return "Run failed", f"{job}: {str(event.get('error', ''))[:120]}"
    return None


def follow_up_text(count: int) -> str:
    return f"Follow up on {count} job{'s' if count != 1 else ''}"


def follow_up_notice(count: int, last_day: str | None, today: str) -> tuple[str, str] | None:
    """14e: at most one reminder a day, and only when there's something to do."""
    if count <= 0 or last_day == today:
        return None
    jobs = "1 application has" if count == 1 else f"{count} applications have"
    return "Time to follow up", f"{jobs} had no news for a while. Open the Tracker to send a short follow-up."


# ---------------------------------------------------------------------------
# The icon itself
# ---------------------------------------------------------------------------


class Tray:
    """The tray icon for one window. `actions` are callables from app.py:
    show(), hide(), stop_run(), quit()."""

    def __init__(self, icon_path, show: Callable[[], None], stop_run: Callable[[], object],
                 quit_app: Callable[[], None], keep_in_tray: Callable[[], bool] = lambda: False,
                 follow_ups: Callable[[], int] = lambda: 0, open_tracker: Callable[[], None] | None = None,
                 open_page: Callable[[str], None] | None = None):
        self.state = RunState()
        self.hidden = False
        self._show, self._stop_run, self._quit = show, stop_run, quit_app
        self._keep_in_tray, self._open_tracker = keep_in_tray, open_tracker or show
        self._open_page = open_page or (lambda page: show())
        self._last_note: str | None = None  # title of the last notification: what a click opens
        self.follow_ups = 0  # jobs due a follow-up; set by count_follow_ups()
        self.quick = False  # 14f: the current run came from the quick box
        self._count = follow_ups
        self._told_about_tray = False
        self._icon = None
        self._icon_path = icon_path

    # -- lifecycle --
    def start(self) -> None:
        import pystray
        from PIL import Image

        menu = pystray.Menu(
            pystray.MenuItem("Open JobLens", lambda: self.open(), default=True),  # also a click on the icon
            pystray.MenuItem(lambda _: status_text(self.state), None, enabled=False),
            pystray.MenuItem(lambda _: follow_up_text(self.follow_ups), lambda: self._open_tracker_now(),
                             visible=lambda _: self.follow_ups > 0),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Stop the run", lambda: self._stop_run(), visible=lambda _: self.state.busy),
            pystray.MenuItem(lambda _: "Quit JobLens (stops the run)" if self.state.working else "Quit JobLens",
                             lambda: self._quit()),
        )
        self._icon = pystray.Icon("JobLens", Image.open(self._icon_path), "JobLens", menu)
        self._catch_notification_clicks()
        self._icon.run_detached()  # its own thread and Windows message loop

    def _catch_notification_clicks(self) -> None:
        """pystray ignores a click on its notification (NIN_BALLOONUSERCLICK
        arrives on the same callback message as icon clicks); add it."""
        try:
            from pystray._util import win32

            handlers = self._icon._message_handlers
            original = handlers[win32.WM_NOTIFY]

            def on_notify(wparam, lparam):
                if lparam == NIN_BALLOONUSERCLICK:
                    return self.notification_clicked()
                return original(wparam, lparam)
            handlers[win32.WM_NOTIFY] = on_notify
        except Exception:  # another pystray backend or version: clicks just do nothing
            pass

    def notification_clicked(self) -> None:
        """Open JobLens on the screen the last notification was about."""
        self.hidden = False
        self._open_page(NOTE_PAGES.get(self._last_note or "", "analyze"))

    def stop(self) -> None:
        """Remove the icon (its thread isn't a daemon: the app can't exit before this)."""
        if self._icon is not None:
            self._icon.stop()
            self._icon = None

    # -- the window --
    def open(self) -> None:
        self.hidden = False
        self._show()

    def _open_tracker_now(self) -> None:
        self.hidden = False
        self._open_tracker()

    def window_closing(self, hide: Callable[[], None]) -> bool:
        """pywebview's `closing` handler. Returns False to keep the app running."""
        try:
            keep = self._keep_in_tray()
        except Exception:
            keep = False
        if self._icon is None or close_action(self.state, keep) == "quit":
            return True  # no tray icon to come back from: never hide the window
        hide()
        self.hidden = True
        if not self._told_about_tray:  # once per session: after that you know
            self._told_about_tray = True
            if self.state.working:
                self.notify("JobLens is still working",
                            "Closing the window doesn't stop the agent. It's in the tray; you'll be told when it needs you.")
            else:
                self.notify("JobLens is in the tray",
                            "It keeps running so your shortcut and reminders work. To quit, right-click the tray icon.")
        self._refresh()
        return False

    def count_follow_ups(self) -> int:
        """Ask the tracker again (app.py's reminder thread, about every half hour)."""
        try:
            self.follow_ups = int(self._count())
        except Exception:  # a reminder is never worth a crash
            pass
        self._refresh()
        return self.follow_ups

    # -- events (the same ones the page gets) --
    def on_event(self, event: Event) -> None:
        self.state.update(event)
        if self.hidden or self.quick:
            note = notification(event, self.state)
            if note:
                self.notify(*note)  # Windows plays its notification sound with it
        if event.get("type") in ("paused", "finished", "failed", "stopped"):
            self.quick = False  # told once: from here you're in the window
        self._refresh()

    def notify(self, title: str, message: str) -> None:
        self._last_note = title
        if self._icon is not None:
            try:
                self._icon.notify(message, title)
            except Exception:  # a notification is never worth a crash
                pass

    def _refresh(self) -> None:
        if self._icon is not None:
            try:
                self._icon.title = f"JobLens · {status_text(self.state)}"[:127]  # Windows' tooltip limit
                self._icon.update_menu()
            except Exception:
                pass
