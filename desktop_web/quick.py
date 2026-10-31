"""
Quick analyze (14f, D32): the small always-on-top box the shortcut opens.

    Ctrl+Alt+J -> the box (link already filled in if the clipboard has one)
    Analyze    -> the same run as on the Analyze screen, in the background;
                  the box closes
    later      -> a Windows notification (with its sound) when the cover note
                  is ready for review, or if the run needs you or fails

The box is a second pywebview window with its own small API (QuickApi):
the page can't reach the main window's API from there. The run itself is
the main Api's, so the Analyze screen shows it too.
"""

import ctypes
import sys
from typing import Callable
from urllib.parse import urlparse

from job_agent import __version__


def is_link(text: str) -> bool:
    parsed = urlparse((text or "").strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc) and " " not in text.strip()


def clipboard_text() -> str:
    """The clipboard's text, or "" (never raises)."""
    if sys.platform != "win32":
        return ""
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    user32.GetClipboardData.restype = ctypes.c_void_p
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    CF_UNICODETEXT = 13
    if not user32.OpenClipboard(None):
        return ""
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        pointer = kernel32.GlobalLock(handle)
        try:
            return ctypes.wstring_at(pointer)[:2000] if pointer else ""
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


class QuickApi:
    """What the quick box may call. `api` is the main window's bridge.Api."""

    def __init__(self, api, hide: Callable[[], None], on_started: Callable[[], None] = lambda: None,
                 clipboard: Callable[[], str] = clipboard_text):
        self._api, self._hide, self._on_started, self._clipboard = api, hide, on_started, clipboard

    def app_info(self) -> dict:
        settings = self._api.get_settings()
        return {"version": __version__, "quick": True, "settings": settings}

    def clipboard_link(self) -> str:
        """A link to fill in, if you just copied one."""
        try:
            text = self._clipboard().strip()
        except Exception:
            return ""
        return text if is_link(text) else ""

    def quick_start(self, url: str) -> dict:
        url = (url or "").strip()
        if not is_link(url):
            raise ValueError("Paste the job's web link (starting with http).")
        runner = self._api._runner
        if runner.busy:
            raise RuntimeError("JobLens is already analyzing a job. You'll be told when it's done.")
        if runner.last_pause:
            raise RuntimeError("A job in JobLens is waiting for you (a cover note or pasted text). "
                               "Open JobLens and finish it first.")
        status = self._api.llm_status()  # fail now, not minutes in
        if not status["ok"]:
            raise RuntimeError(status["message"])
        result = self._api.start_run(url)  # the default resumes (14b): the box never asks
        self._on_started()
        return result

    def close(self) -> None:
        self._hide()
